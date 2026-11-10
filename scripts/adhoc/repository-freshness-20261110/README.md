# Freshness preparation helper archive

Date: 2026-11-10. Issue: [CofactorMech #12](https://github.com/CultureBotAI/CofactorMech/issues/12).

These are the three exact helper scripts used to produce and verify the four
inert candidate files in `workflow/candidates/repository-freshness-v1/` at
`666a56cf152227f7aa625c08d51460d55030bf1b`. They were omitted from that result
commit. This follow-up commits the historical helpers alongside those unchanged
results; it does not rerun generation or replace the original evidence.

| Helper | Purpose and inputs | Outputs and effects in the original preparation |
| --- | --- | --- |
| `prepare_consumer.py` | Prepare an explicitly owned consumer using the pinned claw source, repository key/root, scaffold/main/seed revisions and actual ownership map. | Creates an isolated worktree; performs canonical dry run and apply; writes configuration, before, root-map, dry-run, applied and readback evidence. |
| `verify_candidate.py` | Check persisted candidate bytes against pinned Git blobs, candidate schema, original plan, scaffold and evidence directory. | Writes a timestamped verification receipt; checks all scaffold blobs/modes and rejects the proposal as an adoption. |
| `final_inventory.py` | Inventory the original two public consumers, their PRs/checks, review receipts, branches, pins and canonical release observations. | Reads Git/GitHub state and writes the original final handoff; does not merge, queue or activate. |

`provenance.json` binds the original helper SHA-256 values, all four candidate
hashes, exact source/scaffold/result revisions and hashes of retained evidence.
The original helpers and evidence remain under
`~/agent-work/claw/stream-c-freshness-20261110/`; consumer evidence remains under
`~/agent-work/CofactorMech/freshness-20261110/evidence/` and
`~/agent-work/AssayMech/freshness-20261110/evidence/`. The original canary receipt
and Assay start receipt preserve the completed Cofactor-before-Assay generation
order. This archive correction does not rewrite those observations.

## Historical execution limits

These files are an audit archive, not portable current rollout commands. No
helper packaging or behavior edits were made. They retain the original absolute
host paths, expected revisions, environment and output locations. The canonical
source was the reviewed, unreleased PR revision recorded in the manifest; no
release/adoption readiness is asserted. `prepare_consumer.py` creates state and
calls the original generator's apply mode. The other two scripts execute their
checks and evidence writes even on import. Do not run or import these archives
as part of installation, CI, activation or a new generation attempt.

`verify_candidate.py` intentionally accepts only the original candidate-only
diff. `final_inventory.py` intentionally requires four PR files and the original
heads, so neither is a verifier for this expanded PR. These historical guards
have not been weakened. For this correction, run the offline integrity checks:

```sh
uv run --locked pytest -q tests/test_freshness_helper_archive.py
```

Those checks read bytes without importing or executing archived code. They bind
all three exact originals and all four unchanged candidates to the recorded
hashes and fail when an archive is missing or changed. Native repository checks
remain required. The PR now includes four candidate files plus three archived
helpers, this README, provenance JSON and the integrity test.

The public additions were inspected for secrets, email addresses and unrelated
private-repository data. The two-consumer inventory remains intact because both
consumers are within the original public preparation scope. No credentials,
private repository data or raw environment/configuration dumps are included.

Scaffold/base refresh, verified canonical publication and provenance refresh,
consumer merge, active workflow/profile integration, boundary adoption and
runtime decisions remain separate outstanding steps. Queue/auto-merge holds
remain in force. This archive grants no execution or merge authority.
