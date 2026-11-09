"""Closed LinkML validation plus offline provenance and history invariants."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from functools import lru_cache
from importlib.resources import files
from pathlib import Path, PurePosixPath

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from linkml.generators.jsonschemagen import JsonSchemaGenerator

CORPORA = {
    "mediaingredientmech": "CultureBotAI/MediaIngredientMech",
    "pathwaymech": "CultureBotAI/PathwayMech",
    "proteintraitsmech": "CultureBotAI/proteintraitsmech",
}
RELATIONS = {
    "mediaingredientmech": {"SUPPLIED_BY", "PRECURSOR_SUPPLIED_BY"},
    "pathwaymech": {"PRODUCED_BY", "USED_BY", "CONJUGATE_FORM_PRODUCED_BY", "CONJUGATE_FORM_USED_BY"},
    "proteintraitsmech": {"REQUIRED_BY", "CONJUGATE_FORM_REQUIRED_BY"},
}


class StrictLoader(yaml.SafeLoader):
    """Reject duplicate keys and retain timestamp strings for schema validation."""


StrictLoader.yaml_implicit_resolvers = {
    key: [(tag, pattern) for tag, pattern in values if tag != "tag:yaml.org,2002:timestamp"]
    for key, values in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str) or key in result:
            raise ValueError(f"duplicate or non-string YAML key: {key!r}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load(text: str) -> dict:
    value = yaml.load(text, Loader=StrictLoader)
    if not isinstance(value, dict):
        raise ValueError("document must be an object")
    return value


@lru_cache(maxsize=2)
def validator(kind: str = "CofactorRecord") -> Draft202012Validator:
    schema = files("cofactormech").joinpath("schema/cofactormech.yaml")
    generated = json.loads(JsonSchemaGenerator(
        str(schema), top_class=kind, not_closed=False, include_null=False
    ).serialize())
    Draft202012Validator.check_schema(generated)
    return Draft202012Validator(generated, format_checker=FormatChecker())


def relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (not value or not path.parts or path.is_absolute() or ".." in path.parts
            or str(path) != value or any(c in value for c in "\\\n\r?#")):
        raise ValueError(f"unsafe repository-relative path: {value!r}")
    return path


def utc_timestamp(value: str) -> None:
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)", value):
        raise ValueError(f"timestamp must be a full UTC timestamp in 2000..2099: {value}")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("timestamp must use UTC")


def _nonempty(value) -> None:
    if isinstance(value, str) and not value.strip():
        raise ValueError("strings must not be empty or whitespace")
    if isinstance(value, dict):
        for item in value.values():
            _nonempty(item)
    elif isinstance(value, list):
        for item in value:
            _nonempty(item)


def validate_history(record: dict) -> None:
    validator("HistoryRecord").validate(record)
    _nonempty(record)
    if record["history_version"] != 1:
        raise ValueError("history_version must be 1")
    utc_timestamp(record["session"]["timestamp"])
    relative_path(record["target"]["path"])


def validate_record(record: dict) -> None:
    validator().validate(record)
    _nonempty(record)
    if len(record["categories"]) != len(set(record["categories"])):
        raise ValueError("duplicate cofactor category")
    links = record.get("related_records", [])
    gaps = record.get("research_gaps", [])
    covered = {link["corpus"] for link in links} | {gap["corpus"] for gap in gaps}
    if covered != set(CORPORA):
        raise ValueError("each corpus needs an evidence-backed link or an explicit research gap")
    seen = set()
    for link in links:
        corpus = link["corpus"]
        if link["relation"] not in RELATIONS[corpus]:
            raise ValueError(f"relation is incompatible with corpus: {corpus}")
        if link["relation"].startswith("CONJUGATE_FORM_"):
            if not link.get("target_chemical_id") or link["target_chemical_id"] == record["chemical_id"]:
                raise ValueError("conjugate-form links require a distinct target chemical ID")
        elif link.get("target_chemical_id") not in (None, record["chemical_id"]):
            raise ValueError("different chemical forms require an explicit conjugate-form relation")
        relative_path(link["source_path"])
        expected = (f"https://github.com/{CORPORA[corpus]}/blob/"
                    f"{link['source_version']}/{link['source_path']}")
        if link["source_url"] != expected:
            raise ValueError("source URL must identify the declared corpus, commit and path")
        if corpus == "mediaingredientmech":
            if link["status"] == "VERIFIED" and not re.fullmatch(r"MIM:[0-9]{7}", link["identifier"]):
                raise ValueError("verified MIM links need a stable MIM identifier")
        elif link["status"] != "VERIFIED":
            raise ValueError("only MIM identity links may be provisional")
        key = tuple(link[field] for field in ("corpus", "identifier", "relation", "source_version", "source_path"))
        if key in seen:
            raise ValueError("duplicate cross-corpus link")
        seen.add(key)
    seen_history = set()
    for event in record["curation_history"]:
        utc_timestamp(event["timestamp"])
        path = relative_path(event["history_file"])
        if path.parts[:2] != ("history", "records") or path.suffix != ".yaml":
            raise ValueError("history_file must name a record sidecar under history/records")
        if event["history_file"] in seen_history:
            raise ValueError("duplicate curation history sidecar")
        seen_history.add(event["history_file"])


def validate_history_links(root: Path, record: dict, record_path: str, proposed=None) -> set[str]:
    proposed = proposed or {}
    referenced = set()
    for event in record["curation_history"]:
        relative = event["history_file"]
        source = root / relative
        if source.is_symlink() or not source.resolve().is_relative_to(root.resolve()):
            raise ValueError("history sidecar must not escape the repository or be a symlink")
        sidecar = proposed.get(relative)
        if sidecar is None:
            sidecar = load(source.read_text())
        validate_history(sidecar)
        if sidecar["target"]["path"] != record_path:
            raise ValueError("history sidecar target differs from record path")
        if sidecar["session"]["id"] != Path(relative).stem:
            raise ValueError("history session ID differs from filename")
        if sidecar["session"]["timestamp"] != event["timestamp"]:
            raise ValueError("inline event and history timestamp differ")
        if event["curator"] not in {actor["name"] for actor in sidecar["session"]["actors"]}:
            raise ValueError("inline curator missing from history actors")
        if not any(item["summary"] == event["summary"] and item["type"] == event["action"]
                   for item in sidecar["events"]):
            raise ValueError("inline event differs from canonical history event")
        referenced.add(relative)
    return referenced


def validate_repository(root: Path) -> int:
    validator()
    validator("HistoryRecord")
    if not (root / "data/cofactors").is_dir() or not (root / "history").is_dir():
        raise ValueError("required inventory or history directory is missing")
    ids = set()
    referenced = set()
    paths = sorted((root / "data/cofactors").glob("*.yaml"))
    for path in paths:
        if path.is_symlink():
            raise ValueError(f"record must not be a symlink: {path}")
        record = load(path.read_text())
        validate_record(record)
        if record["id"] in ids:
            raise ValueError(f"duplicate record identifier: {record['id']}")
        if path.stem != record["id"].split(":", 1)[1]:
            raise ValueError("record filename must match its identifier slug")
        ids.add(record["id"])
        referenced |= validate_history_links(root, record, str(path.relative_to(root)))
    sidecars = {str(path.relative_to(root)) for path in (root / "history").rglob("*.yaml")}
    if sidecars != referenced:
        raise ValueError(f"unreferenced or missing history sidecars: {sorted(sidecars ^ referenced)}")
    return len(paths)
