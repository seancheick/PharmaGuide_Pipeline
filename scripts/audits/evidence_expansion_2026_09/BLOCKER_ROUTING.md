# Evidence=0 products that evidence curation cannot fix

496 of 4045 Evidence=0 products (non-probiotic lane). Adding papers will not move any of them. Each class is handed to its existing owner; this project modifies none of those pipelines.

| class | products | owner | why | examples |
|---|---:|---|---|---|
| C | 86 | identity normalization / applicability owner | A record exists but correctly does not join (form excluded, or one canonical lumps distinct materials), or the label identity is unresolved. | BulkSupplements.com — L-Carnitine Fumarate; BulkSupplements.com — L-Carnitine HCl |
| E | 2 | clinical evidence registry owner (legacy backfill) | The matched record is reference-only and can never carry efficacy points by design. | GNC Natural Brand — Triple Chlorophyll; GNC SuperFoods — Triple Chlorophyll with Phytonutrients |
| H | 408 | ingredient role / identity classification owner | The label's active rows were demoted before scoring, so no evidence record can reach them. | BulkSupplements.com — Carrot Powder; BulkSupplements.com — Glycerol Monostearate |

## Sub-reasons

| detail | products |
|---|---:|
| `H_label_active_demoted_blend_header_total_weight_only` | 205 |
| `H_label_active_demoted_nested_under_non_therapeutic_parent` | 184 |
| `H_label_active_demoted_is_additive` | 113 |
| `H_label_active_demoted_excluded_nutrition_fact` | 93 |
| `C_record_key_overlap_not_joined` | 78 |
| `H_only_zero_amount_panel_rows` | 14 |
| `C_rejected_clinical_form_mismatch` | 5 |
| `C_no_mapped_active` | 3 |
| `E_accepted_match_zero_points` | 2 |
| `H_label_active_demoted_recognized_non_scorable` | 1 |
| `H_no_active_rows` | 1 |

## Most affected brands

| brand | products |
|---|---:|
| BulkSupplements.com | 184 |
| Nature's Way | 64 |
| Life Extension | 31 |
| Pure Encapsulations | 22 |
| Doctor's Best | 16 |
| GNC Pro Performance | 16 |
| Garden of Life | 13 |
| Nutricost | 10 |
| Equate | 9 |
| Nature's Bounty | 9 |

## Identities appearing most often in blocked products

| identity | products |
|---|---:|
| `fiber` | 88 |
| `BLEND_GENERAL` | 70 |
| `digestive_enzymes` | 67 |
| `bromelain` | 29 |
| `protein` | 27 |
| `iron` | 26 |
| `calcium` | 25 |
| `alpha_amylase` | 25 |
| `vitamin_a` | 24 |
| `l_carnitine` | 20 |
| `OI_GUAR_GUM` | 18 |
| `spinach` | 18 |
| `strawberry` | 18 |
| `l_arginine` | 16 |
| `ginger` | 16 |
| `vitamin_c` | 16 |
| `NHA_MONK_FRUIT` | 15 |
| `prebiotics` | 14 |
| `PII_XYLANASE` | 14 |
| `NHA_CHILI_PEPPER` | 14 |

