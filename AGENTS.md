# CofactorMech agent instructions

Read the README and `just --list`. This repository owns curated cofactor records and their evidence-backed links; it does not own upstream ingredients, pathways or protein traits.

- Verify current files and remote revisions before reporting counts or status. Include ignored files in absence searches (`rg --no-ignore --hidden`).
- Work in isolated clones/worktrees under `~/agent-work/CofactorMech/`. Keep retained reviews, batch state, helper scripts and handoffs there; never `/tmp`, `/private/tmp` or `$TMPDIR`. Disposable test fixtures are the exception. Push authorized committed batch branches to origin the same day and verify their exact remote heads. A failed push is a blocker. Do not force-push.
- Curate coenzymes, prosthetic groups and metal ions. Ingredient roles are candidates. Distinguish a precursor or salt from the active cofactor and name organism/context limitations.
- Every asserted scientific relation requires a source supporting that relation. Verify each linked corpus target at a full immutable commit; record the target path, identifier, commit and source URL. Do not infer a mechanistic dependency from a shared name, protein or reaction. Missing targets are research gaps.
- MIM links remain `PROVISIONAL` until stable MIM identifiers are adopted; retain the exact source identifier. `VERIFIED` MIM links require an actual `MIM:` identifier from the cited revision. No invented IDs or links.
- Add or append curation history through `just new-history`; preserve existing events and history sidecars. The command validates dry runs, requires `--apply` to write, and uses a repository lock and recoverable validated transaction.
- Governed files and their pin are immutable locally. Use claw's supported `kg-microbe-governance sync` from its reviewed published revision. Update the pinned claw dependency and lockfile with the pin; never patch governed tests or payload to make CI pass.
- Run `just check` and `just check-vendored`. Repaired failure modes need regression tests and a fresh-process mutation check showing that reverting the fix makes the test fail.
- Each PR requires an independent adversarial review, issues for confirmed findings, fixes, re-review and green checks. Stop before merge; the user decides. Never enable auto-merge or send input to other sessions. No at-mentions.
- Record reviews follow `docs/record-reviews.md` and the repository profile in `docs/record-review-profile.md`. Do not mislabel structural validation as a scientific review.
