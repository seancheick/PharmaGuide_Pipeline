# Category And Gate Audit

- Generated from release artifacts dated `2026-04-09T22:58:28.167533+00:00`
- Product count: `1901`
- Detail blobs: `1901`
- Unique detail blobs: `1901`
- Contract failures: `0`

## Final Supplement Type Distribution

- `targeted`: 598 (31.5%)
- `multivitamin`: 572 (30.1%)
- `specialty`: 367 (19.3%)
- `single_nutrient`: 226 (11.9%)
- `probiotic`: 70 (3.7%)
- `herbal_blend`: 68 (3.6%)

## Enriched -> Resolved Type Change Matrix

- `specialty -> targeted`: 598 (31.5%)
- `specialty -> multivitamin`: 572 (30.1%)
- `specialty -> specialty`: 367 (19.3%)
- `specialty -> single_nutrient`: 226 (11.9%)
- `specialty -> probiotic`: 70 (3.7%)
- `specialty -> herbal_blend`: 68 (3.6%)

### Highest-Impact Reclassifications

#### specialty -> multivitamin

| DSLD ID | Product | Score | Flags |
| --- | --- | --- | --- |
| 298038 | Multi-Vitamin Elite - A.M. | 80.6 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 313918 | A.M. | 80.5 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 336315 | A.M. | 80.5 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 232866 | A.M. | 79.5 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 260489 | A.M. | 79.4 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 328833 | A.M. | 79.4 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 298107 | A.M. | 79.2 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 313916 | A.M. | 79.2 | ['SUPPLEMENT_TYPE_REINFERRED'] |

#### specialty -> targeted

| DSLD ID | Product | Score | Flags |
| --- | --- | --- | --- |
| 74344 | Basic Bone Nutrients | 70.7 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 306244 | Berberine | 70.2 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 328820 | Berberine | 70.2 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 182060 | Basic Bone Nutrients | 69.5 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 16106 | Methyl-Guard | 68.0 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 298048 | Quercetin Phytosome | 66.8 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 336310 | Quercetin Phytosome | 66.8 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 35440 | Quercetin Phytosome | 66.8 | ['SUPPLEMENT_TYPE_REINFERRED'] |

#### specialty -> probiotic

| DSLD ID | Product | Score | Flags |
| --- | --- | --- | --- |
| 306291 | Sacro-B | 65.1 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 323130 | Sacro-B | 65.1 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 336354 | Sacro-B | 65.1 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 337873 | Sacro-B | 65.1 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 22101 | Sacro-B | 64.5 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 269933 | Sacro-B | 63.8 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 16077 | Sacro-B | 63.2 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 46495 | Sacro-B | 63.2 | ['SUPPLEMENT_TYPE_REINFERRED'] |

#### specialty -> single_nutrient

| DSLD ID | Product | Score | Flags |
| --- | --- | --- | --- |
| 63793 | Magnesium Bisglycinate | 69.2 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 74313 | Magnesium Bisglycinate | 69.2 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 181813 | Magnesium Bisglycinate | 67.9 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 217381 | Magnesium Bisglycinate | 67.9 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 251237 | Magnesium Bisglycinate | 67.9 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 284233 | Magnesium Bisglycinate | 66.7 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 291773 | Beta Alanine-SR | 66.3 | ['SUPPLEMENT_TYPE_REINFERRED'] |
| 336362 | Creatine | 66.3 | ['SUPPLEMENT_TYPE_REINFERRED'] |

## Gate Outcomes

### Scoring Basis

- `bioactives_scored`: 1881 (98.9%)
- `safety_block`: 19 (1.0%)
- `no_scorable_ingredients`: 1 (0.1%)

### Evaluation Stage

- `scoring`: 1882 (99.0%)
- `safety`: 19 (1.0%)

### Verdicts

- `SAFE`: 1747 (91.9%)
- `CAUTION`: 72 (3.8%)
- `POOR`: 62 (3.3%)
- `BLOCKED`: 19 (1.0%)
- `NOT_SCORED`: 1 (0.1%)

### Flag Counts

- `SUPPLEMENT_TYPE_REINFERRED`: 1534
- `PROPRIETARY_BLEND_PRESENT`: 382
- `B0_HIGH_RISK_SUBSTANCE`: 35
- `B0_WATCHLIST_SUBSTANCE`: 35
- `BANNED_MATCH_REVIEW_NEEDED`: 2
- `NO_ACTIVES_DETECTED`: 1

### Probiotic Eligibility Outcomes

- `no_probiotic_signal`: 1788 (94.1%)
- `strict_gate_failed`: 57 (3.0%)
- `supplement_type_probiotic`: 56 (2.9%)

#### Promoted Probiotic-Dominant Formulas

No examples in this bucket.

#### Probiotic Strict-Gate Failures

| DSLD ID | Product | Resolved Type | Score | Bonus |
| --- | --- | --- | --- | --- |
| 16243 | MediClear Plus | multivitamin | 79.0 | 0.0 |
| 20142 | MediClear Plus | multivitamin | 77.8 | 0.0 |
| 65844 | MediPro Vegan All-In-One Shake Chocolate Flavored | multivitamin | 76.6 | 0.0 |
| 37364 | MediPro Vegan All-In-One Shake Vanilla | multivitamin | 75.3 | 0.0 |
| 37372 | MediPro Vegan All-In-One Shake Vanilla | multivitamin | 75.3 | 0.0 |
| 66401 | MediPro Vegan All-In-One Shake Vanilla Flavored | multivitamin | 75.3 | 0.0 |
| 37366 | Medipro Vegan All-In-One Shake Chai | multivitamin | 75.3 | 0.0 |
| 16245 | MediClear-SGS Chocolate | multivitamin | 75.1 | 0.0 |

#### Supplement-Type-Probiotic Awards

| DSLD ID | Product | Resolved Type | Score | Bonus |
| --- | --- | --- | --- | --- |
| 306291 | Sacro-B | probiotic | 65.1 | 2.0 |
| 323130 | Sacro-B | probiotic | 65.1 | 2.0 |
| 336354 | Sacro-B | probiotic | 65.1 | 2.0 |
| 337873 | Sacro-B | probiotic | 65.1 | 2.0 |
| 22101 | Sacro-B | probiotic | 64.5 | 1.0 |
| 269933 | Sacro-B | probiotic | 63.8 | 2.0 |
| 16077 | Sacro-B | probiotic | 63.2 | 1.0 |
| 46495 | Sacro-B | probiotic | 63.2 | 1.0 |

## Export Integrity

- `products_core` rows: `1901`
- `detail_blobs` files: `1901`
- `detail_index.json` entries: `1901`
- `audit.contract_failures`: `0`
- `audit.counts.total_errors`: `0`

## Interpretation

- `SUPPLEMENT_TYPE_REINFERRED` appears on `1534` products. Combined with the remaining `367` final-`specialty` products, that means the current release set entered scoring with stale `specialty` typing across the board.
- The rebuilt release export is internally aligned now: row counts, detail blobs, manifest, and contract audit all agree.
- Remaining work is semantic QA, not silent pipeline drift. The next best audit is a curated spot-check set for products near category boundaries and for probiotic-signaled products that still fail the strict gate.
