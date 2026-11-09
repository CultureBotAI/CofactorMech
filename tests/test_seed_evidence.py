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


@pytest.mark.parametrize("token", ["-1", "01", "+1", "1.0", "-", "~2"])
def test_noncanonical_array_indices_rejected(token):
    with pytest.raises(ValueError, match="missing source locator"):
        pointer({"kept": ["a", "b"]}, "JSON Pointer /kept/" + token)


def test_numeric_object_keys_are_not_array_indices():
    assert pointer({"01": "valid key"}, "JSON Pointer /01") == "valid key"


def test_negative_protein_comment_locator_rejected(inputs):
    records, index, queue = inputs
    record = next(r for r in records if r["id"] == "CofactorMech:thiamine-diphosphate")
    enzyme = next(x for x in record["related_records"] if "enzyme-class" in x["basis"])
    ev = next(e for e in enzyme["evidence"] if "/uniprotkb/" in e["reference"])
    source = next(s for s in index["sources"] if s["reference"] == ev["reference"])
    positive = int(ev["locator"].rsplit("/", 1)[1])
    ev["locator"] = "JSON Pointer /comments/" + str(positive - len(source["data"]["comments"]))
    with pytest.raises(ValueError, match="missing source locator"):
        audit(records, index, queue)


def test_original_chemical_alias_cannot_match_conjugate_endpoint(inputs):
    records, index, queue = inputs
    record = next(r for r in records if r["id"] == "CofactorMech:biotin")
    link = next(x for x in record["related_records"] if x["corpus"] == "pathwaymech")
    assert link["target_chemical_id"] != record["chemical_id"]
    source = next(s for s in index["sources"] if s["reference"] == link["source_url"])
    edge = pointer(source["data"], link["evidence"][0]["locator"])
    edge["object"] = "MetaCyc:BIOTIN"
    with pytest.raises(ValueError, match="selected pathway edge"):
        audit(records, index, queue)


def test_evidence_from_another_pathway_cannot_support_target(inputs):
    records, index, queue = inputs
    fad = next(r for r in records if r["id"] == "CofactorMech:fad")
    biotin = next(r for r in records if r["id"] == "CofactorMech:biotin")
    link = next(x for x in fad["related_records"] if x["corpus"] == "pathwaymech")
    other = next(x for x in biotin["related_records"] if x["corpus"] == "pathwaymech")
    for field in ("identifier", "source_path", "source_url"):
        link[field] = other[field]
    # Both targets and citations exist, but the selected FAD edge is in a
    # different pathway from the newly asserted target.
    with pytest.raises(ValueError, match="selected pathway edge"):
        audit(records, index, queue)
