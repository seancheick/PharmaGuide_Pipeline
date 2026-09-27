# Reviewer persistence repair — 2026-09-11

Approved submissions were loading only the current reviewer's working draft.
The separate, authoritative approved-label record was intact but never restored
to the editor. The console now shows that record read-only, including raw JSON.
It does not rewrite approval, attestations, ingredients, or scores.

Replacement images and the chosen front image were previously page-local state.
The selection now belongs to the existing reviewer draft and is evidence-bound.
The existing image finalizer checks uploaded bytes before selection is saved.
Reopening recovers uploaded images and issues fresh private preview links;
periodic link renewal preserves unsaved label edits.

## Verification

- Regression tests demonstrated both original failures before the fixes.
- Console suite: 94 passed, 11 opt-in local-stack tests skipped.
- Final focused console rerun: 47 passed.
- Database migration-chain harness: 105 cases passed.
- Reviewer Edge Function tests: 56 passed; type-check passed.
- Production contained 3 approved labels with ingredient rows before deployment.
- Production readback through the repaired reviewer loader returned all 3 with
  ingredient rows after deployment. No product was approved or deleted by this repair.
- Migration `20260911195341_persist_reviewer_product_picture.sql` deployed first,
  then `review-product-submissions` v18. Remote migration dry-run is up to date.
- Security advisor at error level returned no issues before deployment.

The user must refresh their existing console page to load the new JavaScript;
we did not reload it over their active edits. New browser upload/reopen behavior
has automated coverage, not a claimed manual production upload test.

Catalog release remains separate: `scripts/test.sh release` stops at existing
`data_vs_enriched` and `scored_vs_dist` staleness. No bypass or catalog rebuild
was performed. This repair does not complete the remaining product reviews.
