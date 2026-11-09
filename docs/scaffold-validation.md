# Scaffold validation

Native gate: `just check` passes with 145 tests passed and three skipped.
The skips are the governed skill-frontmatter command-file parameterizations;
this scaffold defines no project-local slash commands. There are zero scientific
seed records. `just check-vendored` verifies 22 exact governed artifacts at
claw revision `5790569efd881bd8bca82a04ea278cc462c0c2c8`.

Six fresh-process mutation checks each exited 1 after deliberately weakening a
guard: recursive closed schema, seven-digit MIM IDs, source URL/commit/path
binding, preservation of existing curation history, distinct conjugate-form
chemical identity, and provisional legacy identity distinguished by source path.
Each original source file was restored, then the native gate passed again.
The fresh processes used distinct bytecode cache roots so stale caches could
not conceal a mutation.

Native history authoring emits deterministic JSON, which is a YAML subset.
It round-trips the input's scientific values, appends an event through the
canonical history builder, and stages both the record and sidecar in the shared
validated transaction. Shared corpus serialization remains unverified and
`kg_microbe_write.dump_record` refuses it; this scaffold does not pretend the
native authoring contract establishes a shared emit profile.

These are structural and behavioral checks, not a scientific review or an
independent adversarial review. The latter is a separate PR gate. Canonical
provider workflows are not invoked by the native gate. The repository merge
queue automation is paused; every merge remains a user decision.

The bootstrap pin is published on the claw onboarding branch. Fleet release is
still held on the active release lane and a separately authorized common-pin
rollout; successful local synchronization does not establish deployed release.

Independent review of the initial scaffold found issue #2: a symlinked empty
inventory directory passed as zero records. Validation now checks `data`,
`data/cofactors` and `history` before traversal, rejecting both symlinks within
the repository and links escaping it. Six real symlink regression cases all
failed when the new guard was reverted in a fresh pytest process; restored
code passes, and a separate case preserves valid empty scaffold directories.
The complete native gate and all 22 governed artifact checks passed after the
fix. Independent re-review of the published fix remains a separate gate.

Further independent review found issue #9: the native writer accepted an
internal directory symlink even though inventory validation rejected the
resulting layout. Before any staging or transaction-journal creation, native
history authoring now checks the shared inventory-root contract and every
component of both record and history paths. Reading existing history applies
the same component checks. Internal aliases and escaping directory links are
both rejected, including `history/records` and the per-record history directory.

Twenty regression cases cover dry-run and apply across five directory positions
and both internal and external symlink targets. Assertions concern refusal and
unchanged record, sidecar and journal state, independently of diagnostic wording.
Against the original committed writer, six cases fail: internal aliases at
`history`, `history/records` and `history/records/fixture`, in dry-run and apply.
The three apply cases actually create a record, sidecar and journal; the three
dry runs incorrectly accept the invalid layout without writing. The other 14
cases already refuse safely and remain passing controls. This distinction was
verified in an isolated worktree with fresh Python bytecode caches and a separate
20-case observation receipt. The earlier diagnostic-sensitive mutation report
is superseded by this behavioral result.

The fixed complete gate passes 145 tests with three expected skips, including
all 20 symlink cases and normal create, dry-run, edit and history-preservation
cases. Governance remains unchanged. The updated PR stays draft until independent
re-review and its new remote checks pass; no scientific record was modified.
