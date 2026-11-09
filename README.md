# CofactorMech

CofactorMech curates evidence-backed microbial coenzymes, prosthetic groups and metal ions. Ingredient role assignments are discovery candidates, not proof that an ingredient is itself a cofactor. Vitamin precursors and metal salts are distinguished from the active chemical species they can supply.

The initial seed contains 14 cofactor entities, with 28 ingredient supply links and explicit dispositions for all 162 current-role MIM candidates. See [seed provenance and coverage](data/provenance/README.md) for source commits, chemical distinctions and limitations. Records link to the supplying MediaIngredientMech ingredients, PathwayMech pathways and ProteinTraitsMech requirements only when the target and relation have been verified. A missing match is an explicit research gap. MIM references remain provisional until the stable `MIM:` identifier migration is available.

## Development

Install [uv](https://docs.astral.sh/uv/) and [just](https://just.systems/), then run:

```sh
uv sync --locked
just check
just check-vendored
```

`just check` is the same native lint, schema, data, history, source-projection, and test gate used by CI. `just check-vendored` verifies every governed file against the immutable claw commit in `scripts/.vendored_canon_ref`; it requires public GitHub access. Both run in the required `validate-strict` CI job, including merge groups.

Records live at `data/cofactors/<slug>.yaml`. The installed LinkML schema is `src/cofactormech/schema/cofactormech.yaml`. JSON Schema is generated directly from LinkML at validation time, with unknown fields rejected at every object level. Semantic checks enforce evidence coverage, link provenance and history target matching. These structural checks do not establish scientific truth; curators must read the cited sources.

For a new or updated record, prepare a YAML input outside `data/` and use:

```sh
just new-history --record data/cofactors/example.yaml --input workspace/example.yaml --summary "Describe the change" --details "Sources inspected and what changed" --actor curator
just new-history --record data/cofactors/example.yaml --input workspace/example.yaml --summary "Describe the change" --details "Sources inspected and what changed" --actor curator --apply
```

The first command validates a dry run. Apply records an append-only canonical history sidecar and a matching inline event in one validated transaction; existing history is preserved. The default action is `EDIT`; use `--action CREATE` for a new record. Git identity is checked, writes use the repository lock, and transaction journals are retained under `workspace/write-journals/` for recovery.

## Governance and release state

This bootstrap uses a published immutable claw onboarding-branch commit. It is not a completed fleet release. The claw registration PR and the shared-pin rollout require separate user merge decisions after the active fleet release lane permits a consumer change. The claw dependency in `pyproject.toml` and `uv.lock` deliberately uses the same pin as `scripts/.vendored_canon_ref`; update those together on future re-pins.

No automatic merge is authorized by this scaffold. Independent review, fixes, re-review and green checks precede a user merge decision. Native source, reviews and evidence remain durable under `~/agent-work/CofactorMech/`; session state and helper scripts never belong in `/tmp`.

Original code and schemas are offered under CC0. Curated scientific records are CC-BY-4.0, retaining upstream attribution and source licences; imported or vendored files retain their original notices. External sources are cited rather than copied wholesale. The history command emits deterministic JSON, a strict subset of YAML, as this repository's native record format.

Shared `kg_microbe_write.dump_record` intentionally refuses this corpus while its fleet serialization profile is unverified. Native authoring owns the JSON-as-YAML representation; it is not a general cross-corpus serializer.
