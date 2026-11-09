"""Corruption tests distinguish citation presence from retained target support."""
import csv
import json
from copy import deepcopy
from pathlib import Path

import pytest

from cofactormech.seed_audit import audit, audit_repository, pointer
from cofactormech.validate import load

ROOT = Path(__file__).parents[1]


@pytest.fixture
def inputs():
    records = [load(p.read_text()) for p in sorted((ROOT / "data/cofactors").glob("*.yaml"))]
    index = json.loads((ROOT / "data/provenance/seed_sources.json").read_text())
    with (ROOT / "curation/mim_candidates.tsv").open() as stream:
        queue = list(csv.DictReader(stream, delimiter="\t"))
    return deepcopy((records, index, queue))


def test_seed_evidence_is_resolvable():
    result = audit_repository(ROOT)
    assert result["records"] > 0
    assert result["candidate_rows"] > result["supplier_links"]


def test_wrong_target_identity_rejected(inputs):
    records, index, queue = inputs
    records[0]["related_records"][0]["identifier"] = "CHEBI:999999"
    with pytest.raises(ValueError, match="target identifier differs"):
        audit(records, index, queue)


def test_existing_but_unrelated_pathway_edge_rejected(inputs):
    records, index, queue = inputs
    record = next(r for r in records if r["id"] == "CofactorMech:fad")
    link = next(x for x in record["related_records"] if x["corpus"] == "pathwaymech")
    link["evidence"][0]["locator"] = "JSON Pointer /mechanistic_edges/0"
    with pytest.raises(ValueError, match="selected pathway edge"):
        audit(records, index, queue)


def test_deferred_candidate_cannot_disappear(inputs):
    records, index, queue = inputs
    queue.remove(next(r for r in queue if r["disposition"].startswith("DEFERRED")))
    with pytest.raises(ValueError, match="candidate inventory differs"):
        audit(records, index, queue)


def test_promotion_must_match_actual_supplier_link(inputs):
    records, index, queue = inputs
    row = next(r for r in queue if r["cofactor_records"])
    row["cofactor_records"] = "CofactorMech:invented"
    with pytest.raises(ValueError, match="candidate promotion differs"):
        audit(records, index, queue)


def test_missing_locator_rejected():
    with pytest.raises(ValueError, match="missing source locator"):
        pointer({"kept": []}, "JSON Pointer /kept/5")
