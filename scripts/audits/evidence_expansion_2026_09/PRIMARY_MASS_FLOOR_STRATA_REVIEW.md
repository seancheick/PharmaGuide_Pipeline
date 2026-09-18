# PRIMARY-MASS FLOOR — 13-STRATUM SANITY REVIEW

Policy under review: `direction_ceiling`. Representative per stratum is the lowest
dsld_id among its members, so the selection is reproducible and not curated.

`floor` is the raw floor the anchor proposes; `final` is Evidence after the
policy applies. A stratum with no member is printed EMPTY rather than filled
with an invented example.

## `positive_strong_reviewed`  (n=3223)

*a reviewed positive_strong primary may keep the strong floor*

| field | value |
|---|---|
| product | `695` (GNC) |
| module / archetype | generic / generic_botanical_branded |
| mass-dominant active | `curcumin` |
| anchor record | `INGR_TURMERIC` — Curcumin |
| provenance | **REVIEWED (in registry)** |
| evidence direction | `positive_strong` |
| study type / level | systematic_review_meta / ingredient-human |
| raw pipeline Evidence (floor suppressed) | 7.0 |
| candidate floor | 14.0 |

| policy | Evidence | total | tier |
|---|---|---|---|
| baseline | 15.6 | 74.7 | Good |
| `direction_ceiling` | 15.6 | 74.7 | Good |
| no_primary_mass_floor | 7.8 | 66.9 | Needs improvement |

## `positive_weak_reviewed`  (n=1139)

*positive_weak must NOT be promoted to a strong floor*

| field | value |
|---|---|
| product | `698` (GNC) |
| module / archetype | generic / generic_botanical_branded |
| mass-dominant active | `rhodiola rosea` |
| anchor record | `INGR_RHODIOLA` — Rhodiola Rosea |
| provenance | **REVIEWED (in registry)** |
| evidence direction | `positive_weak` |
| study type / level | systematic_review_meta / ingredient-human |
| raw pipeline Evidence (floor suppressed) | 4.59 |
| candidate floor | 11.9 |

| policy | Evidence | total | tier |
|---|---|---|---|
| baseline | 13.2 | 86.2 | Very good |
| `direction_ceiling` | 10.4 | 83.4 | Very good |
| no_primary_mass_floor | 5.1 | 78.1 | Good |

## `mixed_reviewed`  (n=641)

*mixed evidence must be ceiling-constrained*

| field | value |
|---|---|
| product | `702` (GNC) |
| module / archetype | generic / generic_botanical_branded |
| mass-dominant active | `elderberry extract` |
| anchor record | `INGR_ELDERBERRY` — Elderberry Extract |
| provenance | **REVIEWED (in registry)** |
| evidence direction | `mixed` |
| study type / level | rct_multiple / ingredient-human |
| raw pipeline Evidence (floor suppressed) | 2.7 |
| candidate floor | 8.4 |

| policy | Evidence | total | tier |
|---|---|---|---|
| baseline | 9.3 | 69.7 | Good |
| `direction_ceiling` | 7.3 | 67.7 | Needs improvement |
| no_primary_mass_floor | 3.0 | 63.4 | Needs improvement |

## `null_direction`  (n=0)

*null evidence must never create an affirmative floor*

**EMPTY — no product in the corpus matches this stratum.**

Structurally empty, not merely absent: `_EFFECT_FLOOR_MULTIPLIER['null'] = 0.0`, and `_primary_mass_floor` skips any
anchor whose multiplier is <= 0. No policy can create this case.

## `negative_direction`  (n=0)

*negative evidence must never create an affirmative floor*

**EMPTY — no product in the corpus matches this stratum.**

Structurally empty, not merely absent: `_EFFECT_FLOOR_MULTIPLIER['negative'] = 0.0`, and `_primary_mass_floor` skips any
anchor whose multiplier is <= 0. No policy can create this case.

## `unreviewed_anchor`  (n=24)

*an anchor outside the reviewed registry must not pass as reviewed evidence*

| field | value |
|---|---|
| product | `239811` (Spring_Valley) |
| module / archetype | generic / generic_botanical_branded |
| mass-dominant active | `collagen` |
| anchor record | `RECOVERED_COLLAGEN_PEPTIDES_V1` — Collagen |
| provenance | **RECOVERED -> verified against reviewed INGR_COLLAGEN_PEPTIDES** |
| evidence direction | `positive_strong` |
| study type / level | systematic_review_meta / ingredient-human |
| raw pipeline Evidence (floor suppressed) | 9.538 |
| candidate floor | 14.0 |

| policy | Evidence | total | tier |
|---|---|---|---|
| baseline | 15.6 | 78.6 | Good |
| `direction_ceiling` | 15.6 | 78.6 | Good |
| no_primary_mass_floor | 10.6 | 73.6 | Good |

## `nutrition_authority`  (n=672)

*adequacy stays separately owned and is held out of the comparison*

| field | value |
|---|---|
| product | `843` (GNC) |
| module / archetype | generic / generic_single_molecule |
| mass-dominant active | `vitamin k2 mk 7` |
| anchor record | `INGR_VITAMIN_K2` — Vitamin K2 (MK-7) |
| provenance | **n/a (authority floor)** |
| evidence direction | `mixed` |
| study type / level | rct_multiple / ingredient-human |
| raw pipeline Evidence (floor suppressed) | 10.0 |
| candidate floor | 10.0 |

| policy | Evidence | total | tier |
|---|---|---|---|
| baseline | 11.1 | 75.5 | Good |
| `direction_ceiling` | 11.1 | 75.5 | Good |
| no_primary_mass_floor | 11.1 | 75.5 | Good |

## `shadowed_by_pipeline`  (n=458)

*when pipeline Evidence already exceeds the floor, final Evidence is unchanged*

| field | value |
|---|---|
| product | `1055` (GNC) |
| module / archetype | generic / generic_single_molecule |
| mass-dominant active | `calcium` |
| anchor record | `INGR_CALCIUM` — Calcium |
| provenance | **REVIEWED (in registry)** |
| evidence direction | `positive_strong` |
| study type / level | systematic_review_meta / ingredient-human |
| raw pipeline Evidence (floor suppressed) | 14.526 |
| candidate floor | 14.0 |

| policy | Evidence | total | tier |
|---|---|---|---|
| baseline | 16.1 | 77.1 | Good |
| `direction_ceiling` | 16.1 | 77.1 | Good |
| no_primary_mass_floor | 16.1 | 77.1 | Good |

## `branded_rct`  (n=222)

*a branded RCT anchor behaves like its direction, not like its branding*

| field | value |
|---|---|
| product | `2692` (GNC) |
| module / archetype | generic / generic_botanical_branded |
| mass-dominant active | `pycnogenol` |
| anchor record | `BRAND_PYCNOGENOL` — Pycnogenol |
| provenance | **REVIEWED (in registry)** |
| evidence direction | `positive_strong` |
| study type / level | rct_multiple / branded-rct |
| raw pipeline Evidence (floor suppressed) | 4.5 |
| candidate floor | 18.0 |

| policy | Evidence | total | tier |
|---|---|---|---|
| baseline | 20.0 | 92.0 | Excellent |
| `direction_ceiling` | 20.0 | 92.0 | Excellent |
| no_primary_mass_floor | 5.0 | 77.0 | Good |

## `product_human`  (n=141)

*product-level human evidence behaves like its direction*

| field | value |
|---|---|
| product | `832` (GNC) |
| module / archetype | generic / generic_single_molecule |
| mass-dominant active | `optimsm` |
| anchor record | `BRAND_OPTIMSM` — OptiMSM |
| provenance | **REVIEWED (in registry)** |
| evidence direction | `positive_strong` |
| study type / level | rct_multiple / product-human |
| raw pipeline Evidence (floor suppressed) | 13.2636 |
| candidate floor | 18.0 |

| policy | Evidence | total | tier |
|---|---|---|---|
| baseline | 15.6 | 80.9 | Very good |
| `direction_ceiling` | 15.6 | 80.9 | Very good |
| no_primary_mass_floor | 14.7 | 80.0 | Very good |

## `strain_clinical`  (n=2)

*strain-clinical evidence behaves like its direction*

| field | value |
|---|---|
| product | `183996` (Pure_Encapsulations) |
| module / archetype | generic / generic_single_molecule |
| mass-dominant active | `lactobacillus rhamnosus gg` |
| anchor record | `STRAIN_LGG` — Lactobacillus rhamnosus GG |
| provenance | **REVIEWED (in registry)** |
| evidence direction | `positive_strong` |
| study type / level | clinical_strain / strain-clinical |
| raw pipeline Evidence (floor suppressed) | 2.6 |
| candidate floor | 11.0 |

| policy | Evidence | total | tier |
|---|---|---|---|
| baseline | 12.2 | 67.7 | Needs improvement |
| `direction_ceiling` | 12.2 | 67.7 | Needs improvement |
| no_primary_mass_floor | 2.9 | 58.4 | Needs improvement |

## `single_rct_anchor`  (n=339)

*the weakest study type still cannot overstate its direction*

| field | value |
|---|---|
| product | `3558` (GNC) |
| module / archetype | generic / generic_single_molecule |
| mass-dominant active | `vitamin b3 niacin` |
| anchor record | `INGR_VITAMIN_B3_NIACIN` — Vitamin B3 (Niacin) |
| provenance | **REVIEWED (in registry)** |
| evidence direction | `positive_strong` |
| study type / level | rct_single / ingredient-human |
| raw pipeline Evidence (floor suppressed) | 10.0 |
| candidate floor | 11.0 |

| policy | Evidence | total | tier |
|---|---|---|---|
| baseline | 12.2 | 57.9 | Needs improvement |
| `direction_ceiling` | 12.2 | 57.9 | Needs improvement |
| no_primary_mass_floor | 11.1 | 56.8 | Needs improvement |

## `tier_changing`  (n=2690)

*a floor that moves the PUBLIC tier is the highest-visibility case*

| field | value |
|---|---|
| product | `695` (GNC) |
| module / archetype | generic / generic_botanical_branded |
| mass-dominant active | `curcumin` |
| anchor record | `INGR_TURMERIC` — Curcumin |
| provenance | **REVIEWED (in registry)** |
| evidence direction | `positive_strong` |
| study type / level | systematic_review_meta / ingredient-human |
| raw pipeline Evidence (floor suppressed) | 7.0 |
| candidate floor | 14.0 |

| policy | Evidence | total | tier |
|---|---|---|---|
| baseline | 15.6 | 74.7 | Good |
| `direction_ceiling` | 15.6 | 74.7 | Good |
| no_primary_mass_floor | 7.8 | 66.9 | Needs improvement |

## Findings

None.
