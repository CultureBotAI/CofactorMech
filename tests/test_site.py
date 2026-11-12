"""Exercise real HTML output, provenance, unsafe inputs and deployment boundaries."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from cofactormech.site import build, check_site, render_environment, safe_url

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("site-source")
    # A clean miniature Git source with the actual unchanged scientific corpus.
    for name in ("data", "history", "src/cofactormech/schema"):
        shutil.copytree(ROOT / name, root / name)
    shutil.copyfile(ROOT / "LICENSE", root / "LICENSE")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=Site test",
                    "-c", "user.email=site-test@example.invalid", "commit", "-qm", "Fixture"],
                   check=True)
    return root, build(root)


def bytes_tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


def test_complete_deterministic_catalogue_and_source_downloads(built):
    root, output = built
    first = bytes_tree(output)
    assert check_site(output)["records"] == len(list((root / "data/cofactors").glob("*.yaml")))
    manifest = json.loads((output / "site-manifest.json").read_text())
    assert len(list((output / "records").glob("*/index.html"))) == manifest["record_count"]
    for source in (root / "data/cofactors").glob("*.yaml"):
        assert (output / "sources" / source.name).read_bytes() == source.read_bytes()
        record = json.loads(source.read_text())
        detail = (output / "records" / source.stem / "index.html").read_text()
        assert record["id"] in detail
        for link in record.get("related_records", []):
            assert link["status"] in detail and link["source_version"] in detail
    build(root)
    assert bytes_tree(output) == first


def test_dirty_corpus_cannot_claim_committed_source(built):
    root, _ = built
    source = next((root / "data/cofactors").glob("*.yaml"))
    raw = source.read_bytes()
    try:
        source.write_bytes(raw + b"\n")
        with pytest.raises(ValueError, match="commit source changes"):
            build(root)
    finally:
        source.write_bytes(raw)


def test_changed_artifact_and_broken_link_fail_check(built):
    _, output = built
    index = output / "index.html"
    raw = index.read_bytes()
    try:
        index.write_bytes(raw + b'<a href="records/missing/index.html">Missing</a>')
        with pytest.raises(ValueError, match="missing or escaped"):
            check_site(output)
        index.write_bytes(raw + b"\n")
        with pytest.raises(ValueError, match="artifact changed"):
            check_site(output)
    finally:
        index.write_bytes(raw)


def test_unowned_output_is_preserved(built):
    root, output = built
    marker = output / ".site-generated"
    raw = marker.read_bytes()
    try:
        marker.unlink()
        with pytest.raises(ValueError, match="unowned"):
            build(root)
        assert (output / "index.html").is_file()
    finally:
        marker.write_bytes(raw)


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,hi", "//evil.test",
                                 "https://user:password@example.org", "https://x.test/\nfoo"])
def test_unsafe_reference_never_becomes_link(url):
    assert safe_url(url) is None
    template = render_environment().get_template("evidence.html")
    content = template.module.evidence([dict(title='<img src=x onerror="x">', claim="<script>x</script>",
                                            reference=url, locator="a&b", source_license="CC0")])
    assert "<script>" not in content and "<img" not in content and "href=" not in content
    assert "&lt;script&gt;" in content


def test_link_and_manifest_binding(built):
    _, output = built
    manifest = json.loads((output / "site-manifest.json").read_text())
    for relative, checksum in manifest["files_sha256"].items():
        assert hashlib.sha256((output / relative).read_bytes()).hexdigest() == checksum
    assert 'href="https://culturebotai.github.io/mechs/"' in (output / "index.html").read_text()


def test_pages_pr_jobs_have_no_deployment_authority():
    workflow = yaml.safe_load((ROOT / ".github/workflows/pages.yaml").read_text())
    assert workflow["permissions"] == {"contents": "read"}
    build_job = workflow["jobs"]["build-site"]
    assert "permissions" not in build_job
    assert all("configure-pages" not in step.get("uses", "") for step in build_job["steps"])
    deploy = workflow["jobs"]["deploy"]
    assert deploy["needs"] == "build-site"
    assert deploy["permissions"] == {"pages": "write", "id-token": "write"}
    assert deploy["environment"]["name"] == "github-pages"
    # Both publication-capable paths use exactly the same explicit gate.
    package = next(s for s in build_job["steps"] if "upload-pages-artifact" in s.get("uses", ""))
    assert package["if"] == deploy["if"]
    for condition in (package["if"], deploy["if"]):
        assert "vars.PAGES_DEPLOYMENT_ENABLED == 'true'" in condition
        assert "github.ref == 'refs/heads/main'" in condition
        assert "github.event_name == 'push'" in condition
        assert "github.event_name == 'workflow_dispatch' && inputs.deploy" in condition


def test_deleted_record_cannot_claim_full_committed_corpus(built):
    root, output = built
    source = next((root / "data/cofactors").glob("*.yaml"))
    record = json.loads(source.read_text())
    removed = [source] + [root / event["history_file"] for event in record["curation_history"]]
    originals = {path: path.read_bytes() for path in removed}
    prior = bytes_tree(output)
    try:
        for path in removed:
            path.unlink()
        with pytest.raises(ValueError, match="source inventory"):
            build(root)
        assert bytes_tree(output) == prior
    finally:
        for path, raw in originals.items():
            path.write_bytes(raw)
