# GENERIC_EVIDENCE_NULL_DIRECTION_REVIEW

Measured on the corpus re-scored 2026-09-17. **Nothing here is implemented or proposed as a fix** — it exists so the Evidence-direction semantics can be decided as its own bounded scoring question, outside the evidence-expansion project.

## The rule today

| effect_direction | multiplier |
|---|---:|
| positive_strong | 1.0 |
| positive_weak | 0.85 |
| mixed | 0.6 |
| null | 0.25 |
| negative | 0.0 |

A record's points are `study_type base × evidence_level multiplier × direction multiplier × enrollment band`. `null` keeps 25% of the points and `mixed` 60%, so a rigorous no-benefit trial scores above an ingredient PharmaGuide has never reviewed (which scores 0).

## Records with these directions today

### null — 4 record(s)

| record | study_type | evidence_level | points a match earns | products matching it |
|---|---|---|---:|---:|
| `INGR_BORON` | observational | ingredient-human | 0.45 | 679 |
| `INGR_SAW_PALMETTO` | rct_multiple | ingredient-human | 1.24 | 137 |
| `INGR_VITAMIN_B12` | systematic_review_meta | ingredient-human | 1.35 | 2154 |
| `PRECLIN_DIM` | rct_single | ingredient-human | 0.72 | 46 |

### mixed — 34 record(s)

| record | study_type | evidence_level | points a match earns | products matching it |
|---|---|---|---:|---:|
| `BRAND_ESTERC` | rct_multiple | product-human | 3.00 | 35 |
| `BRAND_MEDIHERB_SILYMARIN` | rct_multiple | branded-rct | 2.16 | 0 |
| `BRAND_NIAGEN` | rct_multiple | product-human | 2.40 | 31 |
| `INGR_ACETYL_L_CARNITINE` | systematic_review_meta | ingredient-human | 3.24 | 75 |
| `INGR_BACOPA` | systematic_review_meta | ingredient-human | 3.24 | 53 |
| `INGR_BERBERINE` | rct_multiple | ingredient-human | 3.24 | 45 |
| `INGR_BLACK_COHOSH` | rct_multiple | ingredient-human | 2.70 | 69 |
| `INGR_CITICOLINE_GENERIC` | rct_multiple | ingredient-human | 2.16 | 19 |
| `INGR_ELDERBERRY` | rct_multiple | ingredient-human | 2.70 | 143 |
| `INGR_GABA` | systematic_review_meta | ingredient-human | 3.24 | 103 |
| `INGR_GINSENG` | systematic_review_meta | ingredient-human | 3.24 | 43 |
| `INGR_GLUCOSAMINE_SULFATE` | systematic_review_meta | ingredient-human | 3.89 | 243 |
| `INGR_INOSITOL` | systematic_review_meta | ingredient-human | 3.24 | 555 |
| `INGR_LION_MANE` | rct_multiple | ingredient-human | 2.16 | 3 |
| `INGR_L_ARGININE` | systematic_review_meta | ingredient-human | 3.24 | 178 |
| `INGR_L_CARNITINE` | systematic_review_meta | ingredient-human | 3.24 | 183 |
| `INGR_L_CITRULLINE` | systematic_review_meta | ingredient-human | 3.24 | 173 |
| `INGR_NAC` | systematic_review_meta | ingredient-human | 3.24 | 115 |
| `INGR_PASSIONFLOWER` | rct_multiple | ingredient-human | 2.16 | 66 |
| `INGR_TART_CHERRY` | systematic_review_meta | ingredient-human | 2.59 | 22 |
| `INGR_THIAMINE_B1` | rct_single | ingredient-human | 2.59 | 1561 |
| `INGR_VALERIAN` | systematic_review_meta | ingredient-human | 3.24 | 43 |
| `INGR_VITAMIN_A_BETA_CAROTENE` | reference | reference | 0.00 | 0 |
| `INGR_VITAMIN_E` | systematic_review_meta | ingredient-human | 3.89 | 1926 |
| `INGR_VITAMIN_K2` | rct_multiple | ingredient-human | 2.70 | 249 |
| `PRECLIN_CHROMIUM_PICOLINATE` | systematic_review_meta | ingredient-human | 3.56 | 1321 |
| `PRECLIN_DGL` | rct_multiple | ingredient-human | 2.70 | 44 |
| `PRECLIN_FISETIN` | rct_single | ingredient-human | 1.73 | 13 |
| `PRECLIN_HUPERZINE_A` | systematic_review_meta | ingredient-human | 2.59 | 72 |
| `PRECLIN_NMN` | rct_multiple | ingredient-human | 2.16 | 18 |
| `PRECLIN_PTEROSTILBENE` | rct_single | ingredient-human | 1.73 | 49 |
| `PRECLIN_QUERCETIN_PHYTOSOME` | rct_multiple | ingredient-human | 2.16 | 19 |
| `PRECLIN_RESVERATROL` | rct_multiple | ingredient-human | 2.16 | 185 |
| `STRAIN_HN019` | clinical_strain | strain-clinical | 1.56 | 0 |

### negative — 0 record(s)

| record | study_type | evidence_level | points a match earns | products matching it |
|---|---|---|---:|---:|

## Product impact of the current rule

Of 10266 scored non-probiotic products with at least one accepted evidence match:

| direction | products matching such a record | products whose ONLY point-carrying matches have this direction |
|---|---:|---:|
| null | 2423 | 249 |
| mixed | 4185 | 874 |
| negative | 0 | 0 |

The second column counts products whose only POINT-CARRYING matches have this direction. 
**Correction (2026-09-18): that is not the same as the score resting on them.** The production projection in `null_direction_projection.json` scored all 2,446 affected products both ways and only **151** change at all. For most of the rest a floor already sets the dimension, so the null record's points are invisible.

Worked example — 252794 Vitamin B12 1% (Cyanocobalamin), measured with the production scorer:

| | clinical_evidence_pipeline | primary_evidence_floor | dimension score |
|---|---:|---:|---:|
| current (null = 0.25) | 1.35 | 10.0 (nutrition authority) | **10.0** |
| candidate (null = 0) | 0.0 | 10.0 (nutrition authority) | **10.0** |

The DRI-essential nutrition-authority floor sets this product's Evidence, not the null record. Any claim that these products are 'scored on evidence that did not show benefit' is wrong for the floor-carrying majority; it is true only for the 151 products listed as movers in the projection, where the dimension goes 1.5 -> 0.0.

### Examples — Evidence carried only by `null` records

| dsld_id | brand | product | Evidence /20 | records |
|---|---|---|---:|---|
| 252794 | BulkSupplements.com | Vitamin B12 1% (Cyanocobalamin) | 11.1 | INGR_VITAMIN_B12 |
| 252800 | BulkSupplements.com | Vitamin B12 1% (Methylcobalamin) | 11.1 | INGR_VITAMIN_B12 |
| 253513 | BulkSupplements.com | Diindolylmethane | 3.1 | PRECLIN_DIM |
| 253520 | BulkSupplements.com | Diindolylmethane (DIM) | 3.1 | PRECLIN_DIM |
| 254655 | BulkSupplements.com | Vitamin B12 1% (Cyanocobalamin) | 11.1 | INGR_VITAMIN_B12 |
| 254686 | BulkSupplements.com | Vitamin B12 1% (Cyanocobalamin) | 11.1 | INGR_VITAMIN_B12 |
| 254688 | BulkSupplements.com | Vitamin B12 1% (Cyanocobalamin) | 11.1 | INGR_VITAMIN_B12 |
| 254690 | BulkSupplements.com | Vitamin B12 1% (Cyanocobalamin) | 11.1 | INGR_VITAMIN_B12 |

### Examples — Evidence carried only by `mixed` records

| dsld_id | brand | product | Evidence /20 | records |
|---|---|---|---:|---|
| 252353 | BulkSupplements.com | Gamma Aminobutyric Acid | 9.3 | INGR_GABA |
| 252410 | BulkSupplements.com | Gamma Aminobutyric Acid 600 mg | 9.3 | INGR_GABA |
| 252451 | BulkSupplements.com | Glucosamine Sulfate | 9.3 | INGR_GLUCOSAMINE_SULFATE |
| 252469 | BulkSupplements.com | D-Glucosamine HCl | 9.3 | INGR_GLUCOSAMINE_SULFATE |
| 252549 | BulkSupplements.com | Inositol 600 mg | 9.3 | INGR_INOSITOL |
| 252576 | BulkSupplements.com | L-Carnitine L-Tartrate | 9.3 | INGR_L_CARNITINE |
| 252577 | BulkSupplements.com | L-Citrulline DL-Malate 1:1 | 9.3 | INGR_L_CITRULLINE |
| 252589 | BulkSupplements.com | L-Arginine Base 500 mg | 9.3 | INGR_L_ARGININE |

## What this means for Wave 1

Curating null and negative evidence accurately is required. Under the current rule some of that evidence would RAISE Evidence on approval. Phase 1 therefore: curates it, keeps it pending, flags every projected rise driven by a null-only record, and does not propose those records for approval until the semantics are decided.

## Open question (for a separate decision, not this project)

"Research exists and is high quality" and "evidence supports this product working" are different facts that the single direction multiplier currently merges. Any replacement needs its own projection and reviewer-benchmark check before it ships.

