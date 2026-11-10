"""Offline integrity checks; never import or execute historical helpers."""
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "scripts/adhoc/repository-freshness-20261110"
CANDIDATES = ROOT / "workflow/candidates/repository-freshness-v1"
HELPERS = ("prepare_consumer.py", "verify_candidate.py", "final_inventory.py")
PAYLOADS = ("SKILL.md", "contract.yaml", "proposal.json", "schema.yaml")


@pytest.mark.parametrize("filename", HELPERS)
def test_original_helper_bytes_are_committed(filename):
    provenance = json.loads((ARCHIVE / "provenance.json").read_text())
    assert hashlib.sha256((ARCHIVE / filename).read_bytes()).hexdigest() == (
        provenance["original_helpers_sha256"][filename]
    )


@pytest.mark.parametrize("filename", PAYLOADS)
def test_original_candidate_bytes_are_preserved(filename):
    provenance = json.loads((ARCHIVE / "provenance.json").read_text())
    assert hashlib.sha256((CANDIDATES / filename).read_bytes()).hexdigest() == (
        provenance["candidate_sha256"][filename]
    )


def test_archive_preserves_original_scope_and_order():
    provenance = json.loads((ARCHIVE / "provenance.json").read_text())
    assert set(provenance["original_helpers_sha256"]) == set(HELPERS)
    assert set(provenance["candidate_sha256"]) == set(PAYLOADS)
    assert provenance["packaging_edits"] == []
    order = provenance["generation_order"]
    assert order["cofactor_canary_completed_at"] < order["assay_preparation_started_at"]
