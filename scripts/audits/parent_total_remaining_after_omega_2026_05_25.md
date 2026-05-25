# Parent-total remaining triage after omega slice — 2026-05-25

Source scanner: `scripts/audits/audit_parent_total_invariant_2026_05_25.py`

Baseline persisted-artifact scan before applying current-code omega rule:

- PASS groups: 1,167
- MISS groups: 61

Current-code in-process refinement:

- Slice #2 omega rule fixes 22 additional miss groups against current enriched
  artifacts (`fish_oil` 19, `dha` 3).
- Remaining miss groups: 39.
- No rule changes are proposed in this report.

## Remaining buckets

| Bucket | Count | Classification | Recommendation |
|---|---:|---|---|
| Caffeine multi-source | 8 | valid multi-source | Leave additive. Standalone caffeine plus coffee/green-tea-derived caffeine are distinct labeled sources. |
| Choline form constituents | 6 | needs form-specific design | Do not auto-collapse. Top-level choline plus Alpha-GPC/Cognizin/phosphatidylcholine child rows represent different choline forms and may be intentionally additive or form-disclosed. |
| L-carnitine matrices | 5 | needs human label review | Quantities differ inside sports/proprietary matrices. Do not infer parent-total without label semantics. |
| Chondroitin + BioCell | 4 | needs human label review | Top-level chondroitin plus BioCell-derived chondroitin may be additive label semantics. |
| B-vitamin nested forms | 4 | needs nutrient-form rule design | Pantothenic acid/pantethine and B6/P5P relationships are form-specific, not exact duplicate rows. |
| Marker/extract constituents | 8 | next candidate, lower priority | Diosmin, milk thistle/silymarin, turmeric/tumerones, resveratrol/BioVin, echinacea/cichoric acid. Needs marker-vs-active scoring policy. |
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

## Valid multi-source cases to preserve

These should remain additive and are useful regression guards for future
parent-total rules:

| DSLD | Product | canonical_id | Why additive |
|---|---|---|---|
| 82369 | CVS Health Super Green Tea Extract 250 mg | `caffeine` | Standalone caffeine 50 mg plus green-tea-derived caffeine 15 mg. |
| 274620 | GNC Beyond Raw Concept X Gummy Worm | `caffeine` | Caffeine anhydrous 250 mg plus Coffea robusta caffeine 50 mg. |
| 316791 | GNC AMP Tri-Phase Lemonade | `caffeine` | Caffeine anhydrous 150 mg plus coffee-bean caffeine 50 mg. |
| 317610 | GNC AMP Tri-Phase Cherry Limeade | `caffeine` | Same as above. |
| 319385 | GNC AMP Tri-Phase Lemonade | `caffeine` | Same as above. |
| 319386 | GNC AMP Tri-Phase Lemon Lime | `caffeine` | Same as above. |
| 330833 | GNC Beyond Raw Concept X Sweet & Tart | `caffeine` | Caffeine anhydrous 250 mg plus Coffea robusta caffeine 50 mg. |
| 330834 | GNC Beyond Raw Concept X Orange Mango | `caffeine` | Same as above. |
| 178674 | Spring Valley Fish, Flax & Borage Oil | `fish_oil` | Nested omega row is under `Borage Oil`, not a total-omega disclosure for top-level fish oil. |

## Candidate future slices

Recommended order:

1. **Prebiotic branded constituent rule** — 2 products, narrow shape:
   `PreticX` source material plus `Xylo-oligosaccharides` child under
   `PreticX Prebiotic Fiber`.
2. **Marker/extract constituent policy** — higher count but needs clinical
   semantics: silymarin/silybin, diosmin, BioVin/trans-resveratrol,
   echinacea/cichoric acid, tumerones/curcumin blend.
3. **Nutrient-form rules** — vitamin K total with MK-4/MK-7 and B-vitamin
   total/form disclosures.
4. **Human label review buckets** — L-carnitine matrices, BioCell
   chondroitin, cod-liver ALA.

Do not implement a broad same-canonical parent-total rule. The remaining
groups mix true multi-source disclosures, source-material/constituent
relationships, and form-specific nutrient disclosures.
