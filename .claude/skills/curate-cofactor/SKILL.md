---
name: curate-cofactor
description: "Curate a microbial cofactor and verify its ingredient, pathway and protein requirement links."
---

Read `AGENTS.md` and the source record. Locate an authoritative source for the chemical species and its biological cofactor function. Treat MIM roles as discovery candidates; a vitamin may be a precursor and a salt may supply an ion. Inspect every cross-corpus target at a full immutable commit and cite the evidence for the relation, not merely its existence. Keep provisional MIM identities visible. Use explicit research gaps where support is missing.

Prepare the complete record, then use `just new-history` in dry-run mode followed by the authorized apply. Run `just check` and `just check-vendored`. For scientific record review, follow `docs/record-reviews.md` and `docs/record-review-profile.md`, and persist the validated bundle through `scripts/record_review.py`; prose alone is not a completed structured review. Independent PR review and user merge decisions remain separate.
