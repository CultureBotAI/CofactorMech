"""Deterministic, local-only HTML projection of the validated curated corpus."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from jinja2 import Environment, FileSystemLoader, select_autoescape

from cofactormech.validate import load, validate_repository

PROJECT = "CofactorMech"
CORPUS = "data/cofactors"
SCHEMA = "src/cofactormech/schema"
PACKAGE = Path(__file__).parent
MARKER = "Generated CofactorMech catalogue; disposable build output.\n"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def safe_url(value: str) -> str | None:
    """Only web references become clickable; unsafe URI text remains visible."""
    try:
        parsed = urlsplit(value)
        if (parsed.scheme in {"https", "http"} and parsed.hostname
                and not parsed.username and not parsed.password
                and not any(ord(c) < 33 or ord(c) == 127 for c in value)
                and "\\" not in value):
            return value
    except ValueError:
        pass
    return None


def label(value: str) -> str:
    return value.replace("_", " ").capitalize()


def render_environment() -> Environment:
    env = Environment(loader=FileSystemLoader(PACKAGE / "site_templates"),
                      autoescape=select_autoescape(["html"]))
    env.filters.update(label=label, safe_url=safe_url)
    return env


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.ids = set()
        self.main_count = 0
        self.h1_count = 0
        self.language = None
        self.title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            if attrs["id"] in self.ids:
                raise ValueError("duplicate HTML id")
            self.ids.add(attrs["id"])
        if tag == "html":
            self.language = attrs.get("lang")
        self.main_count += tag == "main"
        self.h1_count += tag == "h1"
        self.title |= tag == "title"
        for attr in ("href", "src"):
            if attrs.get(attr):
                self.links.append(attrs[attr])


def check_site(output: Path) -> dict:
    """Check actual generated pages, local URLs/fragments and bound file bytes."""
    manifest = json.loads((output / "site-manifest.json").read_text())
    pages = sorted(output.rglob("*.html"))
    if manifest["record_count"] < 1 or len(pages) != manifest["record_count"] + 1:
        raise ValueError("site must contain the complete, nonempty catalogue and details")
    parsed = {}
    for path in pages:
        parser = PageParser()
        parser.feed(path.read_text())
        if (parser.language != "en" or parser.main_count != 1
                or parser.h1_count != 1 or not parser.title):
            raise ValueError(f"incomplete page landmarks: {path}")
        parsed[path.resolve()] = parser
    for path, parser in parsed.items():
        for href in parser.links:
            parts = urlsplit(href)
            if parts.scheme or parts.netloc:
                if not safe_url(href):
                    raise ValueError(f"unsafe URL: {href}")
                continue
            if parts.path.startswith("/"):
                raise ValueError(f"site links must be relative: {href}")
            target = (path.parent / unquote(parts.path)).resolve() if parts.path else path
            if not target.is_relative_to(output.resolve()) or not target.is_file():
                raise ValueError(f"missing or escaped local link: {href} from {path.name}")
            if parts.fragment and target in parsed:
                if unquote(parts.fragment) not in parsed[target].ids:
                    raise ValueError(f"missing local fragment: {href}")
    for relative, expected in manifest["files_sha256"].items():
        path = output / relative
        if path.is_symlink() or not path.is_file() or digest(path.read_bytes()) != expected:
            raise ValueError(f"build artifact changed: {relative}")
    return {"records": manifest["record_count"], "pages": len(pages),
            "local_links_and_fragments": "valid", "bound_file_hashes": "valid"}


def build(root: Path) -> Path:
    """Replace only the marked build/site directory, never corpus or arbitrary paths."""
    root = root.resolve()
    count = validate_repository(root)
    if not count:
        raise ValueError("refusing to build an empty catalogue")
    revision = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    inputs = sorted((root / CORPUS).glob("*.yaml"))
    schemas = sorted((root / SCHEMA).glob("*.yaml"))
    committed_paths = subprocess.check_output(
        ["git", "-C", str(root), "ls-tree", "-r", "--name-only", revision,
         "--", CORPUS, SCHEMA, "LICENSE"], text=True).splitlines()
    expected_paths = {p for p in committed_paths if p.endswith(".yaml") or p == "LICENSE"}
    actual_paths = {p.relative_to(root).as_posix() for p in inputs + schemas + [root / "LICENSE"]}
    if actual_paths != expected_paths:
        raise ValueError("commit source inventory changes before building")
    # Download links must describe the exact corpus and schema bytes being rendered.
    for path in inputs + schemas + [root / "LICENSE"]:
        relative = path.relative_to(root).as_posix()
        committed = subprocess.check_output(["git", "-C", str(root), "show",
                                             f"{revision}:{relative}"])
        if path.is_symlink() or committed != path.read_bytes():
            raise ValueError(f"commit source changes before building: {relative}")
    records = []
    for path in inputs:
        record = load(path.read_text())
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", path.stem):
            raise ValueError(f"unsafe record route: {path.name}")
        record = dict(record, slug=path.stem, source_path=path.relative_to(root).as_posix())
        records.append(record)
    records.sort(key=lambda r: (r["name"].casefold(), r["id"]))
    categories = Counter(c for r in records for c in r["categories"])
    corpus_hashes = {p.relative_to(root).as_posix(): digest(p.read_bytes()) for p in inputs}
    corpus_stamp = digest(json.dumps(corpus_hashes, sort_keys=True).encode())
    schema_hashes = {p.name: digest(p.read_bytes()) for p in schemas}
    common = {"project": PROJECT, "revision": revision, "corpus_stamp": corpus_stamp,
              "schema_hash": schema_hashes["cofactormech.yaml"], "count": count,
              "github": f"https://github.com/CultureBotAI/{PROJECT}",
              "schema_name": "cofactormech.yaml"}
    build_root = root / "build"
    if build_root.is_symlink():
        raise ValueError("build directory must not be a symlink")
    build_root.mkdir(exist_ok=True)
    output = build_root / "site"
    if output.exists() or output.is_symlink():
        if (output.is_symlink() or not output.is_dir()
                or not (output / ".site-generated").is_file()
                or (output / ".site-generated").read_text() != MARKER
                or any(p.is_symlink() for p in output.rglob("*"))):
            raise ValueError("refusing to replace unowned or symlinked build/site")
    env = render_environment()
    with tempfile.TemporaryDirectory(prefix=".site-stage-", dir=build_root) as directory:
        stage = Path(directory) / "site"
        stage.mkdir()
        for sub in ("records", "sources", "schema"):
            (stage / sub).mkdir()
        shutil.copytree(PACKAGE / "site_assets", stage / "assets")
        (stage / ".site-generated").write_text(MARKER)
        (stage / ".nojekyll").write_text("")
        shutil.copyfile(root / "LICENSE", stage / "LICENSE.txt")
        for path in schemas:
            shutil.copyfile(path, stage / "schema" / path.name)
        for record in records:
            route = stage / "records" / record["slug"]
            route.mkdir()
            (route / "index.html").write_text(env.get_template("record.html").render(
                **common, record=record, prefix="../../", catalogue=False))
            shutil.copyfile(root / record["source_path"],
                            stage / "sources" / (record["slug"] + ".yaml"))
        (stage / "index.html").write_text(env.get_template("catalogue.html").render(
            **common, records=records, categories=dict(sorted(categories.items())),
            prefix="", catalogue=True))
        manifest = {"project": PROJECT, "revision": revision, "record_count": count,
                    "categories": dict(sorted(categories.items())),
                    "corpus_sha256": corpus_stamp, "source_files_sha256": corpus_hashes,
                    "schema_files_sha256": schema_hashes,
                    "files_sha256": {p.relative_to(stage).as_posix(): digest(p.read_bytes())
                                     for p in sorted(stage.rglob("*")) if p.is_file()}}
        (stage / "site-manifest.json").write_text(json.dumps(manifest, indent=2,
                                                           sort_keys=True) + "\n")
        check_site(stage)
        if output.exists():
            shutil.rmtree(output)
        shutil.move(str(stage), output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true", help="check existing build/site only")
    args = parser.parse_args()
    output = args.root.resolve() / "build/site"
    if args.check:
        print(json.dumps(check_site(output), sort_keys=True))
    else:
        print(build(args.root))


if __name__ == "__main__":
    main()
