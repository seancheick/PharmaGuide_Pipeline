# Synergy threshold-unit fail-closed inventory — 2026-09-04

Scope: report-only follow-up after the frozen `_collect_synergy_data` fix. No
new clinical threshold semantics, no new unit conversions, and no runtime policy
expansion were introduced here.

## Fixed behavior

Thresholded synergy matches now fail closed when the converter cannot bridge the
source amount/unit to the threshold unit.

- Preserve the matched source `quantity` and `unit`.
- Set `evaluated_quantity = None`.
- Set `evaluated_unit = None`.
- Set `dose_evaluable = False`.
- Set `meets_minimum = False`.

This prevents raw numeric comparison across incompatible units such as `mg` ↔
`CFU`, unsupported units such as `spoon`, unresolved vitamin forms, enzyme
activity units, or marker-density units.

## RED → GREEN evidence

Focused RED before the branch fix:

- `scripts/tests/test_synergy_dose_native_units.py`
  - cross-dimensional false-positive solo cluster
  - unsupported-unit false-positive solo cluster
  - emitted multi-ingredient cluster must keep the row but mark it unevaluable

Observed RED result:

- `3 failed, 15 passed`
- all three failures were the new unconvertible-threshold tests

Focused GREEN after the branch fix:

- `PG_TEST_WORKERS=2 scripts/test.sh fast scripts/tests/test_clinical_source_owner_projection.py scripts/tests/test_synergy_dose_native_units.py scripts/tests/test_synergy_unit_aware.py`
- `20 passed in 2.61s`

The owner-side regression checks also stayed green in the frozen code:

- quantified nested child dose remains the synergy owner
- standardized-botanical collection stays on the disclosed child only
- absorption does not borrow a non-scorable parent target

## Inventory scope and limitations

Generated report:

- `reports/probiotic_rubric_review_2026_09_04/synergy_unit_inventory.json`

Inventory method:

- scan current manifest-owned enriched outputs only
- inspect stored `formulation_data.synergy_clusters[*].matched_ingredients[*]`
- restrict to rows with `min_effective_dose > 0`
- re-run the current converter against each stored matched row
- classify whether each affected product ID is inside the completed
  `full_reenrichment_ids` selection from
  `corpus_preparation_control_cea87d01_source_owners.json`

This is a stored-match inventory, not a replay. It does not enumerate
hypothetical matches that were never emitted into `matched_ingredients`.

## Why hidden non-emitted failed conversions do not newly gain credit

The frozen behavior matters only when a thresholded row already participates in
an emitted synergy structure.

- Single-ingredient clusters only matter numerically when they either meet the
  minimum or satisfy the existing `underdosed_single >= 50%` branch.
- A failed conversion below that half-dose branch was already non-emitting and
  therefore already zero-scoring.
- Multi-ingredient clusters emit when at least two ingredients are matched, so
  thresholded conversion failures on emitted multi-cluster members are already
  present in stored `matched_ingredients` and therefore captured by the
  inventory.

So this report bounds numeric impact to the stored affected set. It does not
claim there are no other semantic data issues; it only states that hidden
non-emitted failed conversions should not newly acquire synergy credit from this
fix.

## Unresolved threshold-unit policy

This work deliberately does not guess missing or ambiguous unit semantics.

Examples that remain unresolved until explicitly verified by policy:

- vitamin A threshold `3000` must not be assumed to mean `IU`
- folate `mcg DFE` must not be silently treated as plain `mcg`
- vitamin E `IU` must not be raw-compared to `mg`
- bromelain activity units (`FCCPU`, `PU`) must not be raw-compared to `mg`
- garlic density units (`mcg/g`) must not be raw-compared to `mg`

The correct fail-safe is unresolved adequacy, not cross-unit numeric borrowing.

## Inventory summary

From the frozen stored-match scan:

- `2210` affected matched rows
- `1290` affected product IDs
- `287` affected IDs outside the 7791 targeted selection
- `635` stored rows currently marked `meets_minimum = true` despite conversion failure
- `112` stored-true affected IDs outside the 7791 targeted selection

Largest unresolved buckets in stored data:

- `vitamin a / form_unknown`
- `vitamin e / form_unknown`
- `folate / no_conversion_rule`

Non-vitamin stored true positives were smaller but real:

- `bromelain / unit_not_comparable`
- `garlic extract / unit_not_comparable`

Those unresolved semantics were inventoried only. They were not normalized,
reinterpreted, or clinically re-thresholded in this work.
