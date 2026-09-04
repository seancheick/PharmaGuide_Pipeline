# Botanical source identity projection — 2026-09-04

## Observed source ownership defect

Read-only, full-product in-memory replays of manifest-owned GNC products 312254
and 312701 reproduced a remaining identity inconsistency. Their literal source
is `Black Tea Leaf Extract`, with raw taxonomy `Black Tea` and the owned form
`Camellia sinensis Leaf Extract`:

| Product | Source row | Label amount | Before-correction total / evidence |
| --- | --- | --- | --- |
| 312254 | `ingredientRows[1]` | 272 mg | 55.4 / 13.7 |
| 312701 | `ingredientRows[7]` | 100 mg | 55.7 / 16.0 |

Active rows retained `green_tea_extract / ingredient_quality_map / Green Tea
Extract`. IQD already used `black_tea_leaf / botanical_ingredients` but kept
`standard_name=Green Tea Extract`. IQD disposition was `taxonomy_only`, with
`botanical_marker_lineage` recognition. Scoring projected the black-tea ID/db
but retained the old standard name. Both products were scored, with complete
identity readiness and coverage 1.0; green-tea evidence was excluded by the
separate source-preparation applicability gate.

The existing final projection loop already visits the marker branch. The
producer helper's `repaired`-only guard—not the branch's earlier `continue`—
prevented active projection. The marker producer also discarded the recognized
registry's preferred name. The actual existing botanical registry record is
`black_tea_leaf`, preferred name `Black Tea Leaf`; no new identity is needed.

## Single-producer correction

The existing bounded botanical source lookup now returns ID, owning registry,
and preferred name together. A by-ID lookup is built during the existing
recognition-index pass; raw-label normalization/preprocessing is unchanged and
ordinary misses still never invoke exhaustive recognition.

The marker producer stamps this tuple and its recognized-entry metadata
together. The one existing final projection writer admits `taxonomy_only`
only for `botanical_marker_lineage` with a matching validated source tuple;
ordinary repaired identities keep their previous requirements. Literal names,
forms, amounts, source taxonomy, source references and child ownership remain
unchanged. The former canonical remains in the identity audit.

A missing source record or preferred name is not permission to use an IQM
marker. The marker-block decision retains the declared botanical hint only
as a blocking condition. The producer emits an explicit unresolved identity
with reason `botanical_source_identity_unresolved`, retains required coverage,
and does not assign an approved botanical or marker identity.

The tests also exposed an existing rating leak: identity resolution could
recover a coherent IQM candidate after the marker guard had rejected it.
For `Cinnamon bark powder` with source `cinnamon_bark`, this retained bio score
8; an invalid source declaring literal caffeine retained 13. The blocked path
now passes no candidate to the existing IQD stamp, reusing its quality-clearing
logic. This is a real rating correction, not merely a metadata change. The
parent's complete score comparison must account for any downstream numerical
effects. Reviewed source/preparation relationships, exact equivalents and
unblocked IQM candidates retain their existing behavior.

## Test-first and regression evidence

- Two real Black Tea owner projections: **2 failed**, then **2 passed**.
- Missing record, absent preferred name and blank preferred name, each in
  strict and compatibility consumption: **6 failed**, then the focused
  eight-case set passed. Each malformed owner plus a Vitamin C peer retains
  one unresolved required row, coverage 0.5, and `not_scored` readiness.
- Cinnamon and invalid caffeine exposed retained ratings before the blocked
  stamp correction; both now have no quality/form rating.
- Focused adjacent backstop: **334 passed in 5.76 seconds**, then a fresh final
  run with the parent's additional green-tea cases **338 passed in 5.65 seconds**, through
  `scripts/test.sh fast`, covering botanical projection, existing IQM recovery,
  preparation projection, green-tea evidence, botanical form/separation
  boundaries and clinical applicability. Additional controls preserve the
  original 10 mg caffeine and 60 mg polyphenol children of the 100 mg Black Tea
  source, source-owned Green Coffee/Chlorogenic Acids context, and reviewed
  same-identity exceptions.

The old direct helper expectation now includes `Globe Artichoke` as the third
tuple element. One positive legacy fixture used nonexistent source ID
`mulberry`; it now uses the actual existing `white_mulberry / White Mulberry`
record. Explicit nonexistent-record negatives remain; production was not
weakened to accommodate the invalid old fixture.

## Conservative corpus selection

A read-only inventory used all 58 stored enriched inputs named by
`corpus_preparation_continuation_final.json` under the main report directory.
It selected every product whose `ingredient_quality_data.ingredients` contains
`recognition_type=botanical_marker_lineage`, not just mismatched Black Tea rows:

- **587 products / 694 IQD source rows** in the existing branch.
- **361 products / 402 rows** differ between active and IQD canonical ID/db.
- The remaining 226 products also require verification: preferred-name and
  quality clearing can affect them even without an ID/db change.
- All **587 IDs** are already included in the report's **6,650** full-clean
  replay IDs. Outside count **0**, outside IDs `[]`.

The family includes ordinary and standardized botanicals: ginger, cinnamon,
cranberry/blueberry, alfalfa, garlic, ginkgo, coffeeberry/NeuroFactor, tart cherry,
black/green tea and others. This is a conservative observed-branch selection,
not a claim that every product's score is unchanged. The parent owns the full
6,650 clean replay and all 15,415 score comparisons. No corpus outputs,
reference data, clinical claims, numerical weights or dose thresholds were
edited by this correction.
