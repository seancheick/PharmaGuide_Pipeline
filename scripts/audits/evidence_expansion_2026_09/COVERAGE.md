# Evidence coverage — non-probiotic lane (Phase 1 baseline)

Built from the corpus re-enriched and re-scored 2026-09-17 (15109 scored products; the probiotic lane has its own registry and queue and is excluded except where stated).

Three columns are kept apart: **evidence strength**, **applicability**, **review completeness**. No non-probiotic identity has a completed review today, so every identity is either `not reviewed` or `legacy record, review state not established`. "Legacy record" is not "reviewed".

## Catalog

| scored products | 15109 |
|---|---:|
| non-probiotic lane | 14561 |
| product-active slots (non-probiotic) | 69575 |
| unique mapped identities | 773 |
| Evidence = 0 products (non-probiotic) | 4045 (27.8%) |
| Evidence = 0 products (probiotic lane) | 186 |
| legacy registry entries | 202 |
| documented bounded reviews | 0 |

## Review coverage

| review state | identities | mapped slots | share of slots |
|---|---:|---:|---:|
| legacy record, review state not established | 175 | 57038 | 82.0% |
| not reviewed (no record) | 598 | 12531 | 18.0% |

### How many identities cover the catalog

| share of mapped product-active slots | identities needed |
|---|---:|
| 80% | 66 |
| 90% | 143 |
| 95% | 248 |

Measured from the corpus, not assumed: the top 66 identities cover 80% of mapped slots, and the long tail beyond 248 covers the last 5%.

## Category rollup (mapped slots by review state)

| category | slots | not reviewed | legacy record | reviewed |
|---|---:|---:|---:|---:|
| vitamins | 27568 | 3.5% | 96.5% | 0.0% |
| minerals | 17387 | 3.6% | 96.4% | 0.0% |
| herbs | 6380 | 41.1% | 58.9% | 0.0% |
| antioxidants | 5110 | 39.3% | 60.7% | 0.0% |
| amino_acids | 4596 | 46.8% | 53.2% | 0.0% |
| fatty_acids | 2980 | 24.0% | 76.0% | 0.0% |
| unknown | 2263 | 89.9% | 10.1% | 0.0% |
| functional_foods | 987 | 91.0% | 9.0% | 0.0% |
| fibers | 829 | 10.9% | 89.1% | 0.0% |
| other | 601 | 33.8% | 66.2% | 0.0% |
| enzymes | 412 | 18.7% | 81.3% | 0.0% |
| proteins | 344 | 10.2% | 89.8% | 0.0% |
| mushroom_extracts | 112 | 82.1% | 17.9% | 0.0% |

## Why Evidence = 0 (A–H taxonomy)

4045 products, classified through the production match seam. Every applicable reason is kept; the table shows the primary one.

| letter | meaning | products |
|---|---|---:|
| H | no active row the scorer can use (label actives demoted upstream) | 408 |
| E | evidence matched but carries no efficacy credit (null/negative/reference-only) | 11 |
| C | identity / form / linkage unresolved | 109 |
| A | identity not reviewed — no evidence record exists | 3517 |

### Sub-reasons

| detail | products |
|---|---:|
| `H_label_active_demoted_blend_header_total_weight_only` | 205 |
| `H_label_active_demoted_nested_under_non_therapeutic_parent` | 184 |
| `H_label_active_demoted_is_additive` | 113 |
| `C_record_key_overlap_not_joined` | 101 |
| `H_label_active_demoted_excluded_nutrition_fact` | 93 |
| `H_only_zero_amount_panel_rows` | 14 |
| `E_accepted_match_zero_points` | 11 |
| `C_rejected_clinical_form_mismatch` | 5 |
| `C_no_mapped_active` | 3 |
| `H_label_active_demoted_recognized_non_scorable` | 1 |
| `H_no_active_rows` | 1 |

## Bottleneck: what evidence curation alone can move

- **3549** of the 4045 (87.7%) have a mapped, dose-bearing active with no evidence record at all — curation is the blocker.
- **496** (12.3%) are blocked elsewhere: the label's actives were demoted upstream, the identity or form is unresolved, the record is formula-scoped, or a matched record carries no efficacy credit. More literature will not move these.

Identities blocking the most Evidence=0 products:

| identity | Evidence=0 products | review state | blocker |
|---|---:|---|---|
| `fiber` | 153 | not reviewed (no record) | evidence curation |
| `BLEND_GENERAL` | 83 | unmapped / not in inventory | identity normalization |
| `digestive_enzymes` | 80 | legacy record, review state not established | record exists — check identity/form/dose |
| `l_lysine` | 68 | not reviewed (no record) | evidence curation |
| `l_glutamine` | 66 | not reviewed (no record) | evidence curation |
| `cla` | 65 | not reviewed (no record) | evidence curation |
| `pomegranate` | 61 | not reviewed (no record) | evidence curation |
| `mct_oil` | 56 | not reviewed (no record) | evidence curation |
| `methionine` | 52 | not reviewed (no record) | evidence curation |
| `maca` | 51 | not reviewed (no record) | evidence curation |
| `l_carnosine` | 51 | not reviewed (no record) | evidence curation |
| `ginkgo` | 49 | not reviewed (no record) | evidence curation |
| `l_phenylalanine` | 47 | not reviewed (no record) | evidence curation |
| `l_tyrosine` | 47 | not reviewed (no record) | evidence curation |
| `blueberry` | 46 | not reviewed (no record) | evidence curation |

## Source coverage of the legacy records

Legacy records are counted by what they claim, not by a completed review:

| study_type | records |
|---|---:|
| systematic_review_meta | 83 |
| rct_multiple | 70 |
| rct_single | 31 |
| clinical_strain | 6 |
| reference | 5 |
| animal_study | 3 |
| in_vitro | 2 |
| observational | 2 |

| effect_direction | records |
|---|---:|
| positive_strong | 120 |
| positive_weak | 44 |
| mixed | 34 |
| null | 4 |
