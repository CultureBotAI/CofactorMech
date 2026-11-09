"""Native closed-schema, link and history boundaries, using synthetic records."""

import subprocess
from argparse import Namespace
from copy import deepcopy
from pathlib import Path

import pytest
from kg_microbe_history.scaffold import build_record

from cofactormech.cli import new_history
from cofactormech.validate import (
    CORPORA,
    load,
    validate_history_links,
    validate_record,
    validate_repository,
)


@pytest.fixture
def record():
    return {
        "id": "CofactorMech:fixture", "name": "Synthetic fixture",
        "chemical_id": "CHEBI:1", "categories": ["COENZYME", "PROSTHETIC_GROUP"],
        "description": "Synthetic test only; no scientific assertion.",
        "evidence": [{"reference": "https://example.org/source", "title": "Fixture source",
                      "claim": "Synthetic test", "locator": "fixture section"}],
        "research_gaps": [{"corpus": corpus, "reason": "Synthetic fixture has no real links"}
                          for corpus in CORPORA],
        "curation_history": [{"timestamp": "2026-11-08T12:00:00Z", "curator": "fixture",
                              "action": "CREATE", "summary": "Create synthetic test",
                              "history_file": "history/records/fixture/session.yaml"}],
    }


@pytest.fixture
def link(record):
    return {
        "corpus": "mediaingredientmech", "identifier": "CHEBI:1", "relation": "SUPPLIED_BY",
        "basis": "Synthetic fixture only", "source_version": "a" * 40,
        "source_path": "data/ingredients/fixture.yaml",
        "source_url": "https://github.com/CultureBotAI/MediaIngredientMech/blob/"
                      + "a" * 40 + "/data/ingredients/fixture.yaml",
        "status": "PROVISIONAL", "evidence": deepcopy(record["evidence"]),
    }


def test_valid_overlap_and_provisional_link(record, link):
    record["related_records"] = [link]
    validate_record(record)


@pytest.mark.parametrize("location", ["root", "evidence", "history", "link"])
def test_unknown_fields_are_rejected_recursively(record, link, location):
    record["related_records"] = [link]
    targets = {"root": record, "evidence": record["evidence"][0],
               "history": record["curation_history"][0], "link": link}
    targets[location]["unknown_field"] = "must not pass"
    with pytest.raises(Exception, match="Additional properties"):
        validate_record(record)


@pytest.mark.parametrize("field,value", [
    ("categories", []), ("evidence", []), ("curation_history", []),
    ("chemical_id", "not-a-curie"), ("name", " "), ("categories", ["VITAMIN"]),
])
def test_invalid_record_shapes(record, field, value):
    record[field] = value
    with pytest.raises(Exception):
        validate_record(record)


@pytest.mark.parametrize("field,value", [
    ("source_version", "main"), ("source_url", "https://github.com/Other/Repo/blob/" + "a" * 40 + "/fixture.yaml"),
    ("source_path", "../escape.yaml"), ("relation", "REQUIRED_BY"),
    ("status", "VERIFIED"), ("evidence", []),
])
def test_invalid_links(record, link, field, value):
    link[field] = value
    record["related_records"] = [link]
    with pytest.raises(Exception):
        validate_record(record)


def test_missing_corpus_is_an_explicit_gap(record):
    record["research_gaps"] = record["research_gaps"][:2]
    with pytest.raises(ValueError, match="each corpus"):
        validate_record(record)


@pytest.mark.parametrize("timestamp", ["2206-11-08T12:00:00Z", "2026-11-08", "2026-11-08T12:00:00",
                                       "2026-02-30T12:00:00Z", "2026-11-08T12:00:00+01:00"])
def test_invalid_timestamps(record, timestamp):
    record["curation_history"][0]["timestamp"] = timestamp
    with pytest.raises(Exception):
        validate_record(record)


def test_duplicate_yaml_keys_are_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        load("id: one\nid: two\n")


def test_missing_and_wrong_history_target_fail(tmp_path, record):
    with pytest.raises(FileNotFoundError):
        validate_history_links(tmp_path, record, "data/cofactors/fixture.yaml")
    sidecar = build_record(kind="record", slug="fixture", target_path="data/cofactors/other.yaml",
                           session_id="session", timestamp="2026-11-08T12:00:00Z",
                           summary="Create synthetic test", details="Synthetic fixture only",
                           event="CREATE", actor_name="fixture", actor_type="human")
    with pytest.raises(ValueError, match="target differs"):
        validate_history_links(tmp_path, record, "data/cofactors/fixture.yaml",
                               {"history/records/fixture/session.yaml": sidecar})


def test_deleted_inventory_directory_is_not_an_empty_corpus(tmp_path):
    with pytest.raises(ValueError, match="required inventory"):
        validate_repository(tmp_path)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    for args in (["init"], ["config", "user.name", "Fixture"],
                 ["config", "user.email", "fixture@example.invalid"],
                 ["remote", "add", "origin", "https://github.com/CultureBotAI/CofactorMech.git"],
                 ["commit", "--allow-empty", "-m", "Fixture"]):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    (root / "data/cofactors").mkdir(parents=True)
    (root / "history").mkdir()
    return root


def test_history_writer_dry_run_apply_and_append_only(repo, record):
    import json
    record.pop("curation_history")
    source = repo / "input.yaml"
    source.write_text(json.dumps(record))
    args = Namespace(record="data/cofactors/fixture.yaml", input=str(source), actor="fixture",
                     actor_type="human", summary="Create synthetic test", details="Fixture only",
                     action="CREATE", model=None, agent_tool=None, apply=False)
    result = new_history(repo, args)
    assert result["applied"] is False
    assert not (repo / args.record).exists()
    assert not list((repo / "history").rglob("*.yaml"))
    args.apply = True
    new_history(repo, args)
    assert validate_repository(repo) == 1
    saved = load((repo / args.record).read_text())
    assert {key: value for key, value in saved.items() if key != "curation_history"} == record
    original_event = deepcopy(saved["curation_history"][0])
    source.write_text(json.dumps(saved))
    args.action = "EDIT"
    new_history(repo, args)
    updated = load((repo / args.record).read_text())
    assert updated["curation_history"][0] == original_event
    assert len(updated["curation_history"]) == 2
    assert validate_repository(repo) == 1
    updated["curation_history"] = []
    source.write_text(json.dumps(updated))
    with pytest.raises(ValueError, match="preserve existing"):
        new_history(repo, args)
    assert len(list((repo / "history").rglob("*.yaml"))) == 2


def test_history_writer_invalid_input_changes_nothing(repo, record):
    import json
    record.pop("curation_history")
    record["evidence"] = []
    source = repo / "input.yaml"
    source.write_text(json.dumps(record))
    args = Namespace(record="data/cofactors/fixture.yaml", input=str(source), actor="fixture",
                     actor_type="human", summary="Create synthetic test", details="Fixture only",
                     action="CREATE", model=None, agent_tool=None, apply=True)
    with pytest.raises(Exception):
        new_history(repo, args)
    assert not (repo / args.record).exists()
    assert not list((repo / "history").rglob("*.yaml"))


def test_native_ci_runs_required_gate_on_pr_push_and_merge_group():
    root = Path(__file__).resolve().parents[1]
    # BaseLoader retains YAML's literal 'on' key.
    import yaml
    workflow = yaml.load((root / ".github/workflows/validate-strict.yaml").read_text(),
                         Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"pull_request", "push", "merge_group"}
    assert workflow["on"]["pull_request"] == {}
    assert workflow["on"]["merge_group"]["types"] == ["checks_requested"]
    job = workflow["jobs"]["validate-strict"]
    assert "if" not in job
    commands = [step.get("run") for step in job["steps"]]
    assert "just check" in commands and "just check-vendored" in commands


def test_pin_and_installed_dependency_share_revision():
    import tomllib
    root = Path(__file__).resolve().parents[1]
    config = tomllib.loads((root / "pyproject.toml").read_text())
    assert config["tool"]["uv"]["sources"]["kg-microbe-orchestration"]["rev"] == (
        root / "scripts/.vendored_canon_ref").read_text().strip()


def test_conjugate_form_needs_distinct_target_chemical(record, link):
    link.update(corpus="pathwaymech", relation="CONJUGATE_FORM_PRODUCED_BY", status="VERIFIED")
    link["source_url"] = link["source_url"].replace("MediaIngredientMech", "PathwayMech")
    record["related_records"] = [link]
    with pytest.raises(ValueError, match="distinct target"):
        validate_record(record)
    link["target_chemical_id"] = record["chemical_id"]
    with pytest.raises(ValueError, match="distinct target"):
        validate_record(record)
    link["target_chemical_id"] = "CHEBI:2"
    validate_record(record)
    link["relation"] = "PRODUCED_BY"
    with pytest.raises(ValueError, match="explicit conjugate"):
        validate_record(record)


def test_stable_mim_ids_have_seven_digits(record, link):
    link["status"] = "VERIFIED"
    record["related_records"] = [link]
    for bad in ("MIM:1", "MIM:12345678", "MIM:abcdefg"):
        link["identifier"] = bad
        with pytest.raises(ValueError, match="stable MIM"):
            validate_record(record)
    link["identifier"] = "MIM:0000001"
    validate_record(record)


def test_provisional_legacy_identifiers_remain_distinct_by_source_path(record, link):
    second = deepcopy(link)
    second["source_path"] = "data/ingredients/second.yaml"
    second["source_url"] = second["source_url"].replace("fixture.yaml", "second.yaml")
    record["related_records"] = [link, second]
    validate_record(record)
    record["related_records"].append(deepcopy(link))
    with pytest.raises(ValueError, match="duplicate cross-corpus"):
        validate_record(record)


@pytest.mark.parametrize("relative", ["data", "data/cofactors", "history"])
@pytest.mark.parametrize("external", [False, True])
def test_symlinked_inventory_and_history_roots_are_rejected(tmp_path, relative, external):
    root = tmp_path / "repo"
    (root / "data/cofactors").mkdir(parents=True)
    (root / "history").mkdir()
    source = root / relative
    destination = tmp_path / "outside" if external else root / "alternate"
    source.rename(destination)
    source.symlink_to(destination, target_is_directory=True)
    assert source.is_symlink() and source.is_dir()
    assert source.resolve().is_relative_to(root) is not external
    with pytest.raises(ValueError, match="must not be a symlink or escape"):
        validate_repository(root)


def test_valid_empty_scaffold_directories_pass(tmp_path):
    (tmp_path / "data/cofactors").mkdir(parents=True)
    (tmp_path / "history").mkdir()
    assert validate_repository(tmp_path) == 0
