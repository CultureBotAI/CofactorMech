"""Read-only checks of seed targets and selected source projections, without network calls.

This verifies identifiers, source locations and retained graph assertions. It does
not establish scientific truth, source authenticity, or literature completeness.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from .validate import CORPORA, load

ROLES = {"COFACTOR_PROVIDER", "VITAMIN_SOURCE", "TRACE_ELEMENT"}


def pointer(data, locator):
    """Resolve the explicit JSON Pointer into a selected source document."""
    prefix = "JSON Pointer "
    if not locator.startswith(prefix) or not locator[len(prefix):].startswith("/"):
        raise ValueError(f"unsupported source locator: {locator}")
    try:
        for token in locator[len(prefix) + 1:].split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            data = data[int(token)] if isinstance(data, list) else data[token]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError(f"missing source locator: {locator}") from exc
    return data


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(records, index, queue):
    """Audit in-memory inputs, including drafts before repository publication."""
    _require(index.get("format_version") == 1, "unsupported projection format")
    sources = {}
    conjugates = defaultdict(set)
    for source in index["sources"]:
        ref = source["reference"]
        _require(ref not in sources, f"duplicate source: {ref}")
        _require(re.fullmatch(r"[a-f0-9]{64}", source["source_sha256"]), "invalid source digest")
        _require(source.get("source_license") and source.get("projection_note"), "missing source provenance")
        sources[ref] = source
        for direction in source["data"].get("ontology_relations", {}).values():
            for relation in direction:
                if relation["relation_type"] in {"is conjugate base of", "is conjugate acid of"}:
                    a, b = ("CHEBI:" + str(relation[k]) for k in ("init_id", "final_id"))
                    conjugates[a].add(b)
                    conjugates[b].add(a)

    def evidence_values(entries):
        values = []
        for entry in entries:
            ref = entry["reference"]
            _require(ref in sources, f"evidence source not retained: {ref}")
            _require(entry.get("source_license") == sources[ref]["source_license"], "source license differs")
            values.append(pointer(sources[ref]["data"], entry["locator"]))
        return values

    def conjugate(a, b):
        seen, pending = set(), [a]
        while pending:
            node = pending.pop()
            if node == b:
                return True
            if node not in seen:
                seen.add(node)
                pending.extend(conjugates[node] - seen)
        return False

    linked = defaultdict(set)
    ids = set()
    for record in records:
        rid, chem = record["id"], record["chemical_id"]
        _require(rid not in ids, "duplicate seed ID")
        ids.add(rid)
        own = sources.get("https://www.ebi.ac.uk/chebi/" + chem, {}).get("data", {})
        _require(own.get("chebi_accession") == chem, f"chemical identity differs: {rid}")
        role_ids = {r["chebi_accession"] for r in own.get("roles_classification") or []}
        _require(role_ids & {"CHEBI:23357", "CHEBI:23354", "CHEBI:26348"}, f"missing cofactor role: {rid}")
        evidence_values(record["evidence"])
        for link in record["related_records"]:
            corpus = link["corpus"]
            _require(link["source_version"] == index["source_commits"][corpus], "source commit differs")
            expected = f'https://github.com/{CORPORA[corpus]}/blob/{link["source_version"]}/{link["source_path"]}'
            _require(link["source_url"] == expected and expected in sources, "target source missing or differs")
            src = sources[expected]
            _require(src.get("source_commit") == link["source_version"] and src.get("source_path") == link["source_path"], "target provenance differs")
            target = src["data"]
            _require(target.get("id" if corpus == "pathwaymech" else "identifier") == link["identifier"], "target identifier differs")
            selected = evidence_values(link["evidence"])
            chemical = link.get("target_chemical_id", chem)
            if link["relation"].startswith("CONJUGATE_FORM_"):
                _require(chemical != chem and conjugate(chem, chemical), "unverified conjugate relationship")
            if corpus == "mediaingredientmech":
                linked[link["source_path"]].add(rid)
            elif corpus == "pathwaymech":
                # A valid target alone is insufficient: inspect the exact selected edge.
                edges = [x for x in selected if isinstance(x, dict) and "predicate" in x]
                predicate = {"produces"} if link["relation"].endswith("PRODUCED_BY") else {"consumes", "has_cofactor"}
                aliases = {chemical}
                for entries in own.get("database_accessions", {}).values():
                    aliases |= {"MetaCyc:" + e["accession_number"] for e in entries if e.get("source_name") == "MetaCyc"}
                _require(any(e["predicate"] in predicate and (e["subject"] if e["predicate"] == "consumes" else e["object"]) in aliases for e in edges), "selected pathway edge does not support relation")
            elif "canonical_examples" in target:
                examples = {x["protein_id"] for x in target["canonical_examples"]}
                matched = False
                for ev in link["evidence"]:
                    protein = sources[ev["reference"]]["data"]
                    if "UniProtKB:" + protein.get("primaryAccession", "") not in examples:
                        continue
                    selected_comment = pointer(protein, ev["locator"])
                    matched |= any(c.get("cofactorCrossReference", {}).get("id") == chemical for c in selected_comment.get("cofactors", []))
                _require(matched, "named enzyme cofactor is not retained")
            else:
                _require(chemical in target.get("xrefs", []), "trait chemical differs")

    candidates = index["candidate_source_paths"]
    _require(len(candidates) == len(set(candidates)), "duplicate inventory path")
    _require(len(queue) == len({r["source_path"] for r in queue}), "duplicate candidate row")
    _require({r["source_path"] for r in queue} == set(candidates), "candidate inventory differs")
    role_records, role_assertions = Counter(), Counter()
    for row in queue:
        _require(row["source_url"] in sources, "candidate source missing")
        source = sources[row["source_url"]]
        data = source["data"]
        _require(source["source_path"] == row["source_path"] and source["source_commit"] == row["source_commit"] == index["source_commits"]["mediaingredientmech"], "candidate provenance differs")
        _require(data["identifier"] == row["legacy_identifier"], "candidate identifier differs")
        roles = [r["role"] for r in data["nutritional_roles"] if r["role"] in ROLES]
        _require(roles and set(roles) == set(row["roles"].split("|")) and len(roles) == int(row["role_assertion_count"]), "candidate roles differ")
        role_records.update(set(roles))
        role_assertions.update(roles)
        listed = set(filter(None, row["cofactor_records"].split("|")))
        _require(listed == linked[row["source_path"]], "candidate promotion differs from links")
        _require(bool(listed) == (row["disposition"] == "CURATED_SUPPLIER_LINK"), "candidate disposition differs")
        _require(bool(row["reason"].strip()), "candidate reason missing")
    _require(set(linked) <= set(candidates), "supplier missing from candidate queue")
    inventory = index["inventory"]
    _require(len(queue) == inventory["mim_unique_candidates"] and dict(role_records) == inventory["mim_role_record_counts"] and dict(role_assertions) == inventory["mim_role_assertion_counts"], "inventory totals differ")
    return {"records": len(records), "candidate_rows": len(queue), "supplier_links": sum(map(len, linked.values())), "source_projections": len(sources)}


def audit_repository(root):
    index = load((root / "data/provenance/seed_sources.json").read_text())
    with (root / "curation/mim_candidates.tsv").open(newline="") as stream:
        queue = list(csv.DictReader(stream, delimiter="\t"))
    records = [load(path.read_text()) for path in sorted((root / "data/cofactors").glob("*.yaml"))]
    return audit(records, index, queue)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        print(json.dumps(audit_repository(args.root), sort_keys=True))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
