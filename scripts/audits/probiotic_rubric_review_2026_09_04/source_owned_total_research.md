# Owned-total mass comparison — defect, lineage rule, and fix (cloud continuation)

2026-09-05, cloud continuation of the 2026-09-04 handoff §5. Companion to
[CLAUDE_HANDOFF_2026_09_04.md](CLAUDE_HANDOFF_2026_09_04.md) and
[cloud_source_lineage_fixtures.json](cloud_source_lineage_fixtures.json).

## Defect

`_primary_mass_floor` (and the stricter recovery gate
`_recover_verified_primary_ingredient_matches`) compared every candidate
against `PRIMARY_MASS_FRACTION × max(all active masses)`. A structural blend
total row — same physical material as the active it quantifies — was included
in that maximum, so DSLD 213475's 500 mg SerinAid complex total pushed the
threshold to 250 mg and its own 100 mg phosphatidylserine child (the only
evidenced active) below dominance: primary floor 0 instead of the control 18.
This is an ownership defect, not proof of inadequate clinical dosing.

## Lineage rule implemented

One shared physical-source comparison (`_row_physical_source_refs`,
`_same_physical_source`, `_competing_active_mass` in
`scoring_v4/modules/generic_evidence.py`):

- Two rows are the same physical source **only** when one declared source path
  equals or structurally contains the other (`ingredientRows[1]` owns
  `ingredientRows[1].nestedRows[0]` and vice versa), including paths declared
  through `linked_rows`/`source_row_ref` back into the original label tree.
- Canonical IDs, standard names, display names and normalized keys are
  deliberately excluded: identity similarity is never lineage.
- With proven lineage, rows sharing the candidate's physical source are
  excluded from the dominance denominator. Without proven refs the historical
  whole-product maximum stands unchanged.
- A zero-mass evidence match still never anchors a floor (explicit guard,
  preserving prior behavior where the positive global threshold rejected it).

Doses, source references, weights, cutoffs and `quality_score.json` are
unchanged. No score was tuned; the control equality (`floor == control floor`,
`score == control score`) is asserted rather than any target number.

## Fixture-verified coverage (tests mirror exact source shapes)

Verified against `cloud_source_lineage_fixtures.json` (all three
`projection_sha256` values recomputed and matched before use):

- **213475** (Nature's Way): complex total `ingredientRows[1]`
  (blend_header_total, 500 mg) owns PS child `ingredientRows[1].nestedRows[0]`
  (active_scorable, 100 mg). Floor preserved. The synthetic
  `activeIngredients` duplicate is linked through the declared original tree
  (`linked_rows` → `ingredientRows[1]`); a synthetic total whose declared links
  do **not** reach the original tree keeps competing even though it shares the
  child's canonical_id (both directions tested).
- **218600** (Solgar): reverse hierarchy — PS 200 mg at `ingredientRows[2]`
  owns its supplying 1,000 mg complex at `ingredientRows[2].nestedRows[0]`
  (blend_header_total nested beneath the active). Floor preserved via the same
  containment rule, no generic ancestor assumption.
- **218838** (Solgar): `Phosphatidylserine Complex` 500 mg
  (`ingredientRows[2]`), PS 100 mg (`ingredientRows[3]`) and
  phosphatidylcholine 60 mg (`ingredientRows[4]`) are siblings with **no**
  owner links. No linkage was invented: the complex still competes and the
  floor stays 0. **Open review item:** the label likely intends the complex to
  supply the PS row, but the source structure does not prove it; resolving
  218838 requires exact-label/producer evidence, not canonical inference.

Competition locks retained: unrelated aggregates at sibling paths (500 mg /
5,000 mg PS-labelled, 25 g protein) still compete with a trace active; a
heavier co-constituent nested **beside** the evidenced child
(`ingredientRows[1].nestedRows[1]`) still competes inside its own blend;
`product_level_evidence` rows are never dropped wholesale.

## Verification

- Before fix: `1 failed, 175 passed` across the seven handoff suites
  (reproduced exactly as the checkpoint recorded), then `3 failed, 6 passed`
  after adding the new lineage tests (RED on 213475, 218600 and the
  tree-linked synthetic case; GREEN on every competition lock).
- After fix: `9 passed` in `test_evidence_primary_source_ownership.py`;
  `181 passed` across the seven handoff suites; `278 passed, 11 skipped`
  across fifteen adjacent evidence/applicability/blend suites (skips are the
  documented "canary not in catalog" historical artifacts).

## Adjacent observations (deliberately unchanged, for reviewer disposition)

- `_has_primary_collagen_peptide_identity` compares max peptide mass against
  the whole-product max with the same global pattern. Its semantics are a
  product-level gate rather than per-entry ownership; changing it was outside
  this defect's scope and has no RED. Flagged for the later rubric review.
- An evidence entry with **no** `matched_source_row_refs` still resolves mass
  through identity tokens, where a total's mass can stand in for its child's
  (`index[key] = max(...)`). Current enrichment stamps refs; only legacy
  artifacts without refs keep the historical behavior. Left unchanged to avoid
  widening; noted for the corpus comparison review.
- The 156 safety-only-primary and 24 EDTA/mannitol holds from the expanded
  replay are untouched by this fix, as required.
