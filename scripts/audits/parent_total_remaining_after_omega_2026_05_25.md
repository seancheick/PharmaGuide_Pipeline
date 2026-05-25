# Parent-total remaining triage after omega slice - 2026-05-25

Source scanner: `scripts/audits/audit_parent_total_invariant_2026_05_25.py`

Scope: report-only classification. No rule changes are proposed here.

## Current artifact caveat

The current persisted enriched artifacts still report the pre-omega state:

- PASS groups: 1,167
- MISS groups: 61

That is expected if the enriched corpus has not been rebuilt after commit
`61c4d8ce` (`fix(enrichment): mark omega source oil rows as parent totals`).
Applying the omega rule's documented predicate to the scanner output removes
22 omega source-oil/constituent misses (`fish_oil` 19, `dha` 3), leaving the
39 groups classified below.

## Remaining buckets

| Bucket | Count | Classification | Recommendation |
|---|---:|---|---|
| Caffeine multi-source | 8 | valid multi-source | Leave additive. Standalone caffeine plus coffee/green-tea-derived caffeine are distinct labeled sources. |
| Choline form constituents | 6 | needs form-specific design | Do not auto-collapse. Top-level choline plus Alpha-GPC/Cognizin/phosphatidylcholine child rows represent different choline forms and may be intentionally additive or form-disclosed. |
| L-carnitine matrices | 5 | needs human label review | Quantities differ inside sports/proprietary matrices. Do not infer parent-total without label semantics. |
| Chondroitin + BioCell | 4 | needs human label review | Top-level chondroitin plus BioCell-derived chondroitin may be additive label semantics. |
| B-vitamin nested forms | 4 | needs nutrient-form rule design | Pantothenic acid/pantethine and B6/P5P relationships are form-specific, not exact duplicate rows. |
| Marker/extract constituents | 7 | next candidate, lower priority | Diosmin, milk thistle/silymarin, turmeric/tumerones, resveratrol/BioVin, echinacea/cichoric acid. Needs marker-vs-active scoring policy. |
| Prebiotic branded constituent | 2 | next candidate, narrow | PreticX total plus XOS constituent looks like a source-material/active-constituent pattern. Candidate for a dedicated prebiotic constituent rule. |
| Residual omega/fish-oil | 2 | leave / human review | Spring Valley Fish/Flax/Borage is valid additive oil-source context; cod-liver ALA needs label review. |
| Vitamin K forms | 1 | nutrient-form rule design | Vitamin K total plus K2 MK-4/MK-7 child rows need a dedicated vitamin-K form rule, not generic parent-total collapse. |

## Remaining groups by canonical_id

| canonical_id | Count |
|---|---:|
| `caffeine` | 8 |
| `choline` | 6 |
| `l_carnitine` | 5 |
| `chondroitin` | 4 |
| `vitamin_b5_pantothenic` | 3 |
| `prebiotics` | 2 |
| `diosmin` | 2 |
| `milk_thistle` | 2 |
| `alpha_linolenic_acid` | 1 |
| `turmeric` | 1 |
| `resveratrol` | 1 |
| `vitamin_b6_pyridoxine` | 1 |
| `echinacea` | 1 |
| `fish_oil` | 1 |
| `vitamin_k` | 1 |

## Product-level classification

### Valid multi-source cases to preserve

| DSLD | Brand | Product | canonical_id | Top-level row | Nested row |
|---|---|---|---|---|---|
| 82369 | CVS Health | Super Green Tea Extract 250 mg | `caffeine` | Caffeine 50 mg | Caffeine 15 mg under Green Tea extract |
| 274620 | GNC Beyond Raw | Concept X Gummy Worm | `caffeine` | Caffeine Anhydrous 250 mg | Caffeine 50 mg under Coffea robusta Seed Extract |
| 316791 | GNC AMP Advanced Muscle Performance | Tri-Phase Lemonade | `caffeine` | Caffeine Anhydrous 150 mg | Caffeine 50 mg under Coffee Bean Extract |
| 317610 | GNC AMP Advanced Muscle Performance | Tri-Phase Cherry Limeade | `caffeine` | Caffeine Anhydrous 150 mg | Caffeine 50 mg under Coffee Bean Extract |
| 319385 | GNC AMP Advanced Muscle Performance | Tri-Phase Lemonade | `caffeine` | Caffeine Anhydrous 150 mg | Caffeine 50 mg under Coffee Bean Extract |
| 319386 | GNC AMP Advanced Muscle Performance | Tri-Phase Lemon Lime | `caffeine` | Caffeine Anhydrous 150 mg | Caffeine 50 mg under Coffee Bean Extract |
| 330833 | GNC Beyond Raw | Concept X Sweet & Tart | `caffeine` | Caffeine Anhydrous 250 mg | Caffeine 50 mg under Coffea robusta Seed Extract |
| 330834 | GNC Beyond Raw | Concept X Orange Mango | `caffeine` | Caffeine Anhydrous 250 mg | Caffeine 50 mg under Coffea robusta Seed Extract |
| 178674 | Spring Valley | Fish, Flax & Borage Oil | `fish_oil` | Fish Oil 800 mg | Omega-3 Fatty Acids 800 mg under Borage Oil |

### Choline form constituents - design needed

| DSLD | Brand | Product | Top-level row | Nested row |
|---|---|---|---|---|
| 243663 | GNC | Triple Strength Krill Oil Mini | Choline 70 mg | Phosphatidyl Choline 480 mg under Total Phospholipids |
| 75286 | GNC | Triple Strength Krill Oil Mini | Choline 70 mg | Phosphatidyl Choline 480 mg under Total Phospholipids |
| 246189 | Pure Encapsulations | Longevity Nutrients | Choline 20 mg | Alpha-GPC 25 mg under CognitivePro Complex |
| 246190 | Pure Encapsulations | Longevity Nutrients | Choline 20 mg | Alpha-GPC 25 mg under CognitivePro Complex |
| 277710 | Pure Encapsulations | Longevity Nutrients | Choline 20 mg | Cognizin 50 mg under CognitivePro Complex |
| 287428 | Pure Encapsulations | Longevity Nutrients | Choline 20 mg | Cognizin 50 mg under CognitivePro Complex |

### L-carnitine matrices - human label review

| DSLD | Brand | Product | Top-level row | Nested row |
|---|---|---|---|---|
| 228714 | GNC AMP Advanced Muscle Performance | Wheybolic Ripped Cookies and Cream | L-Carnitine 666 mg | L-Carnitine 333 mg under Thermo Ripped Matrix |
| 228812 | GNC AMP Advanced Muscle Performance | Wheybolic Ripped Strawberries and Cream | L-Carnitine 666 mg | L-Carnitine 333 mg under Thermo Ripped Matrix |
| 228817 | GNC AMP Advanced Muscle Performance | Wheybolic Ripped Classic Vanilla | L-Carnitine 666 mg | L-Carnitine 333 mg under Thermo Ripped Matrix |
| 228822 | GNC AMP Advanced Muscle Performance | Wheybolic Ripped Chocolate Fudge | L-Carnitine 666 mg | L-Carnitine 333 mg under Thermo Ripped Matrix |
| 214377 | Solgar | gPLC Glycine Propionyl L-Carnitine | GlycoCarn 925 mg | Propionyl L-Carnitine 600 mg under GlycoCarn Glycine Propionyl L-Carnitine HCl |

### Chondroitin + BioCell - human label review

| DSLD | Brand | Product | Top-level row | Nested row |
|---|---|---|---|---|
| 269587 | Doctor's Best | Glucosamine Chondroitin MSM + Hyaluronic Acid | Chondroitin Sulfate 1000 mg | Chondroitin Sulfate 200 mg under BioCell Collagen |
| 302663 | Doctor's Best | Glucosamine Chondroitin MSM + Hyaluronic Acid | Chondroitin Sulfate 1000 mg | Chondroitin Sulfate 200 mg under BioCell Collagen |
| 201285 | Solgar | Extra Strength Glucosamine Hyaluronic Acid Chondroitin MSM Shellfish-Free | Chondroitin Sulfate 1200 mg | Chondroitin Sulfate 48 mg under BioCell Collagen II |
| 201287 | Solgar | Extra Strength Glucosamine Hyaluronic Acid Chondroitin MSM Shellfish-Free | Chondroitin Sulfate 1200 mg | Chondroitin Sulfate 48 mg under BioCell Collagen II |

### B-vitamin nested forms - design needed

| DSLD | Brand | Product | canonical_id | Top-level row | Nested row |
|---|---|---|---|---|---|
| 61982 | Life Extension | Life Extension Mix Tablets | `vitamin_b5_pantothenic` | Pantothenic Acid 600 mg | Pantethine 5 mg under Calcium D-Pantothenate |
| 61983 | Life Extension | Life Extension Mix Tablets | `vitamin_b5_pantothenic` | Pantothenic Acid 600 mg | Pantethine 5 mg under Calcium D-Pantothenate |
| 62097 | Life Extension | Life Extension Mix Tablets With Extra Niacin | `vitamin_b5_pantothenic` | Pantothenic Acid 600 mg | Pantethine 5 mg under Vitamin B6 |
| 64333 | Life Extension | Life Extension Mix Tablets With Extra Niacin & Without Copper | `vitamin_b6_pyridoxine` | Vitamin B6 105 mg | Pyridoxal 5-Phosphate 100 mg and Pyridoxine Hydrochloride 5 mg under Niacin |

### Marker/extract constituents - policy needed

| DSLD | Brand | Product | canonical_id | Top-level row | Nested row |
|---|---|---|---|---|---|
| 232420 | Life Extension | Youthful Legs | `diosmin` | Micronized Purified Flavonoid Fraction 500 mg | Diosmin 450 mg under Sweet Orange extract |
| 328799 | Life Extension | Youthful Legs | `diosmin` | Micronized Purified Flavonoid Fraction 500 mg | Diosmin 450 mg under Sweet Orange Peel Extract |
| 59514 | Life Extension | European Milk Thistle | `milk_thistle` | Siliphos Phytosome Milk Thistle extract 80 mg | Silymarin/Silybin constituents under Milk Thistle extract / phospholipid blend |
| 328071 | Nature's Way | Super Milk Thistle | `milk_thistle` | Milk Thistle seed extract 254 mg | Silybin 140 mg under Silymarin |
| 232507 | Life Extension | Advanced Curcumin Elite | `turmeric` | Tumerones 60 mg | Tumerones 15 mg under Curcumin Elite Proprietary CGM Blend |
| 62796 | Life Extension | Booster Softgels | `resveratrol` | BioVin 25 mg | Trans-Resveratrol 5 mcg under BioVin Full Spectrum Grape Extract |
| 180410 | Nature Made | Echinacea 350 mg | `echinacea` | Echinacea purpurea 350 mg | Cichoric Acid 2.45 mg under Polyphenols |

### Prebiotic branded constituent - narrow future candidate

| DSLD | Brand | Product | Top-level row | Nested row |
|---|---|---|---|---|
| 210865 | Life Extension Florassist | Prebiotic Chewable Natural Strawberry Flavor | PreticX 1400 mg | Xylo-oligosaccharides 1000 mg under PreticX Prebiotic Fiber |
| 232350 | Life Extension Florassist | Prebiotic Chewable Natural Strawberry Flavor | PreticX 1400 mg | Xylo-oligosaccharides 1000 mg under PreticX Prebiotic Fiber |

### Residual omega/fish-oil - human review

| DSLD | Brand | Product | canonical_id | Top-level row | Nested row |
|---|---|---|---|---|---|
| 4283 | Garden Of Life | Oceans 3 Beyond Omega-3 Cod Liver Oil Orange Tangerine Flavor | `alpha_linolenic_acid` | Alpha-Linolenic Acid 150 mg | Alpha-Linolenic Acid 50 mg under Other Omega-3 Fatty Acids |
| 178674 | Spring Valley | Fish, Flax & Borage Oil | `fish_oil` | Fish Oil 800 mg | Omega-3 Fatty Acids 800 mg under Borage Oil |

### Vitamin K forms - design needed

| DSLD | Brand | Product | Top-level row | Nested row |
|---|---|---|---|---|
| 328817 | Thorne | Vitamin K | Vitamin K 6090 mcg | Menaquinone-4 5 mg and Menaquinone-7 90 mcg under Vitamin K2 |

## Candidate future slices

Recommended order:

1. **Prebiotic branded constituent rule** - 2 products, narrow shape:
   `PreticX` source material plus `Xylo-oligosaccharides` child under
   `PreticX Prebiotic Fiber`.
2. **Marker/extract constituent policy** - higher count but needs clinical
   semantics: silymarin/silybin, diosmin, BioVin/trans-resveratrol,
   echinacea/cichoric acid, tumerones/curcumin blend.
3. **Nutrient-form rules** - vitamin K total with MK-4/MK-7 and B-vitamin
   total/form disclosures.
4. **Human label review buckets** - L-carnitine matrices, BioCell
   chondroitin, cod-liver ALA.

Do not implement a broad same-canonical parent-total rule. The remaining
groups mix true multi-source disclosures, source-material/constituent
relationships, and form-specific nutrient disclosures.
