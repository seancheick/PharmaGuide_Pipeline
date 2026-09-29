# D. Sample integrity report — 143 real DSLD labels replayed at pre-window (7b031050) and HEAD (391b87c5)

Inputs: `~/pg_quality/rr_20260928/frozen` (143 raw labels, manifest sha in `frozen/manifest.json`); snapshots `prewindow.jsonl`, `head.jsonl`; compare `delta_prewindow_head.json`; report `report_prewindow_head.json`; probes `probe/*.json` (61 labels, row level). Selection reasons: `sample_manifest.tsv`.

## D.1 Status and routes

- Both arms: 143/143 captured, 0 errors. HEAD status: [('scored', 127), ('not_scored', 11), ('suppressed_safety', 5)]; pre-window: [('scored', 138), ('suppressed_safety', 4), ('not_scored', 1)].
- Transitions: [(('scored', 'scored'), 127), (('scored', 'not_scored'), 11), (('suppressed_safety', 'suppressed_safety'), 4), (('not_scored', 'suppressed_safety'), 1)]. The 11 newly `not_scored` all carry `strict_scoring_contract: disclosed_form_unmapped` (D20 vanadyl/vanadium aspartate ×5, D21 species ×4, calcium sulfate ×1, EAA gummy anchor ×1): explainable holds, not silent loss.
- Route changes: [('214586', 'fiber_digestive', 'generic'), ('233404', 'fiber_digestive', 'generic'), ('233406', 'fiber_digestive', 'generic'), ('243271', 'fiber_digestive', 'generic'), ('282638', 'fiber_digestive', 'generic'), ('28613', 'generic', 'omega')] (5 fiber→generic per A12 claim-aware routing incl. the FiberSMART pair; 1 generic→omega).

## D.2 Score movement (127 scored in both arms)

- unchanged 17, up 63, down 47; mean -0.93, median +0.00; |Δ|≥5: 51; |Δ|≥10: 11.

| route | n | mean Δ total | formulation | dose | evidence | transparency | verification | safety_hygiene |
|---|---|---|---|---|---|---|---|---|
| sports | 26 | -0.82 | +1.25 | +0.68 | -2.17 | -0.59 | +0.00 | +0.00 |
| multi_or_prenatal | 18 | +4.06 | +1.86 | +0.12 | -0.58 | +2.67 | +0.00 | +0.00 |
| generic | 58 | -2.17 | +0.35 | -0.15 | -1.67 | -0.62 | +0.09 | -0.17 |
| fiber_digestive | 9 | -0.49 | -0.24 | +2.93 | -0.68 | -2.50 | +0.00 | +0.00 |
| probiotic | 5 | +2.00 | +0.56 | +0.74 | +1.40 | -0.70 | +0.00 | +0.00 |
| b_complex | 4 | +0.52 | +1.65 | +0.00 | +0.00 | -1.12 | +0.00 | +0.00 |
| omega | 7 | -7.31 | -1.77 | -2.43 | -2.99 | -0.13 | +0.00 | +0.00 |

### Largest decreases (read against the label; see FINDINGS / F_calibration_observations)

| id | route | before → after | pillars that moved | reading |
|---|---|---|---|---|
| 233404 Keto Brain and Body Boost Peac | generic | 83.0 → 40.4 (-42.6) | {'formulation': (16.1, 0.0), 'dose': (19.2, 11.4), 'evidence': (14.2, 0.0), 'transparency': (13.5, 9.0)} | FiberSMART now maps (fiber → resistant dextrin) and scores; Formulation 0 is RR-07 (botanical profile hijack); Evidence 0 (owner scoping) |
| 233406 Keto Brain and Body Boost Peac | generic | 83.0 → 40.4 (-42.6) | {'formulation': (16.1, 0.0), 'dose': (19.2, 11.4), 'evidence': (14.2, 0.0), 'transparency': (13.5, 9.0)} | same as 233404 |
| 77225 Naturally Sourced Omega-3 Vege | omega | 66.4 → 39.6 (-26.8) | {'formulation': (10.8, 9.7), 'dose': (16.8, 4.0), 'evidence': (10.0, 0.0), 'transparency': (13.8, 10.9)} | A13: algal carrier oil no longer counted as DHA (200 mg DHA); Evidence 0 below the 376 mg omega floor (C-4) |
| 243271 Golden Milk | generic | 55.8 → 39.1 (-16.7) | {'formulation': (16.4, 11.3), 'dose': (7.2, 2.8), 'evidence': (7.2, 0.0)} | Evidence → 0 `clinical_review_not_covered` after owner scoping (RR-05); Formulation −5 |
| 282638 Raw Organic Perfect Food Green | generic | 59.6 → 43.5 (-16.1) | {'formulation': (16.4, 16.0), 'dose': (7.2, 9.5), 'evidence': (18.0, 0.0)} | Evidence 18 → 0 not covered (RR-05); greens blend owner unreviewed |
| 311716 Turkey Rhubarb Extract | generic | 56.5 → 41.7 (-14.8) | {'formulation': (16.0, 9.3), 'dose': (9.5, 11.4), 'safety_hygiene': (10.0, 0.0)} | Safety/Hygiene 10 → 0: rhubarb root watchlist (a66c71bb) now penalizes; Formulation −6.7 |
| 299755 Raw Organic Fiber | fiber_digestive | 70.1 → 57.4 (-12.7) | {'formulation': (16.4, 12.1), 'dose': (19.2, 18.4), 'evidence': (6.1, 0.0), 'transparency': (3.4, 1.9)} | Evidence 6.1 → 0 not covered; Transparency −1.5 |
| 29341 Dual Spectrum Lutein with Zeax | omega | 58.2 → 46.0 (-12.2) | {'formulation': (15.0, 12.6), 'evidence': (10.3, 0.0), 'transparency': (10.4, 10.9)} | Evidence 10.3 → 0 (omega exposure gate) |
| 14168 Rampant | generic | 57.3 → 46.2 (-11.1) | {'evidence': (11.1, 0.0)} | Evidence 11.1 → 0 not covered (proprietary blends) |
| 25704 Ultra Amino Complex Watermelon | sports | 60.9 → 51.9 (-9.0) | {'formulation': (9.0, 11.3), 'evidence': (10.4, 3.6), 'transparency': (13.5, 9.0)} | Evidence 10.4 → 3.6 (owner scoping), Transparency −4.5 (B3 removed) |
| 239467 Fish Oil 1000 mg | omega | 36.1 → 27.7 (-8.4) | {'formulation': (10.0, 7.6), 'evidence': (5.5, 0.0), 'transparency': (4.6, 4.1)} | Evidence 5.5 → 0 (1000 mg fish oil below floor) |
| 311734 Intra Peach Mango | generic | 77.6 → 69.2 (-8.4) | {'formulation': (11.3, 11.2), 'evidence': (18.0, 9.7)} | Evidence 18 → 9.7 (owner scoping) |
| 309959 Preseries Lean Pre-Workout Tro | sports | 83.1 → 75.1 (-8.0) | {'evidence': (16.5, 8.5)} | Evidence 16.5 → 8.5 (owner scoping) |
| 77108 BCAA+ With Hydration Complex 6 | sports | 69.4 → 61.5 (-7.9) | {'formulation': (9.6, 11.6), 'dose': (16.0, 17.6), 'evidence': (17.4, 10.4), 'transparency': (10.4, 5.9)} | Evidence 17.4 → 10.4, Transparency −4.5 (B3), Dose +1.6 (band 18→20) |

### Largest increases

| id | route | before → after | pillars that moved | reading |
|---|---|---|---|---|
| 336348 PharmaGABA-250 | generic | 74.0 → 86.0 (+12.0) | {'formulation': (6.7, 18.7)} | GABA powder bio 6 → Formulation 18.7 via dynamic parent ceiling (RR-01, C-1) |
| 184924 G.I. Integrity | fiber_digestive | 61.1 → 71.7 (+10.6) | {'formulation': (16.4, 11.8), 'dose': (2.4, 17.6)} | Dose 2.4 → 17.6: daily exposure + typed dose (A10/B2) |
| 259484 Omega-3 Extra Strength EPA 150 | omega | 72.5 → 81.8 (+9.3) | {'formulation': (13.3, 10.9), 'evidence': (10.0, 20.0), 'transparency': (9.2, 10.9)} | Evidence 10 → 20 (omega purpose standard at 1.5 g EPA), Transparency +1.7 |
| 252451 Glucosamine Sulfate | generic | 67.2 → 76.5 (+9.3) | {'formulation': (10.7, 20.0)} | glucosamine sulfate crystalline bio 11 → Formulation 20 (RR-01) |
| 270561 DreamWorks Trolls Complete Mul | multi_or_prenatal | 68.5 → 77.4 (+8.9) | {'formulation': (9.6, 9.8), 'evidence': (15.3, 20.0), 'transparency': (11.0, 15.0)} | multi: Evidence → 20 (authority panel), Transparency 11 → 15 (rescale) |
| 3565 Mega Men | multi_or_prenatal | 71.2 → 79.6 (+8.4) | {'formulation': (12.6, 15.6), 'evidence': (18.6, 20.0), 'transparency': (7.6, 11.6)} | multi (was withheld in the candidate): Formulation +3, Transparency +4 |
| 82372 Beanaid | fiber_digestive | 55.6 → 63.8 (+8.2) | {'formulation': (13.3, 20.0), 'transparency': (13.5, 15.0)} | enzyme: Formulation 13.3 → 20, Transparency 15 (A15 activity units disclosed) |
| 12012 Spectravite Advanced Formula | multi_or_prenatal | 65.7 → 73.6 (+7.9) | {'formulation': (5.6, 8.7), 'dose': (17.5, 17.9), 'evidence': (18.6, 20.0), 'transparency': (12.0, 15.0)} | multi: Transparency +3, Evidence 20 |
| 19067 Digestive Health Probiotic | probiotic | 69.9 → 77.5 (+7.6) | {'formulation': (14.4, 15.3), 'dose': (14.5, 18.2), 'evidence': (6.0, 9.0)} | probiotic: single strain full Evidence 6 → 9, Dose 14.5 → 18.2 (count reward removed) |
| 17192 Colon Cleanser | fiber_digestive | 51.3 → 58.8 (+7.5) | {'dose': (8.0, 20.0), 'transparency': (13.5, 9.0)} | fiber: Dose 8 → 20 (daily exposure), Transparency 13.5 → 9 (B3 removed) |
| 312819 HMB (Calcium HMB) | sports | 67.2 → 74.5 (+7.3) | {'formulation': (12.7, 10.7), 'dose': (3.5, 12.8)} | HMB: Dose 3.5 → 12.8 (daily exposure, A10) |
| 31148 Active Mixed Berry | multi_or_prenatal | 54.7 → 61.7 (+7.0) | {'formulation': (6.7, 8.1), 'dose': (14.4, 14.6), 'evidence': (18.6, 20.0), 'transparency': (1.0, 5.0)} | multi: Transparency 1 → 5, Evidence 20 |
| 180316 Prenatal Multi + DHA | multi_or_prenatal | 88.1 → 95.1 (+7.0) | {'formulation': (13.1, 15.4), 'dose': (19.6, 19.7), 'evidence': (18.4, 20.0), 'transparency': (12.0, 15.0)} | prenatal: Evidence 20, Transparency 15, Formulation +2.3 |
| 288632 Riboflavin 5'-Phosphate | generic | 86.9 → 93.6 (+6.7) | {'formulation': (11.3, 18.0)} | riboflavin-5-phosphate bio 10 → Formulation 18 (RR-01, C-3) |

## D.3 Row conservation (61 probed labels, every raw row at every depth traced to its cleaned/enriched/blob disposition)

Method: raw `ingredientRows` walked recursively → cleaned `activeIngredients[].raw_source_path` → enriched IQD rows → scoring rows → blob `ingredients`. `conservation_rowlevel.json` holds the per-row lists.

| id | raw rows | cleaned actives | excluded: nutrition facts | excluded: merged serving columns | other exclusions | cleaner-created rows | enricher-added rows |
|---|---|---|---|---|---|---|---|
| 1179 Ravage Fruit Punch | 15 | 28 | 4 | 0 | 4 | 21 | 0 |
| 14168 Rampant | 9 | 22 | 0 | 0 | 2 | 15 | 0 |
| 17192 Colon Cleanser | 12 | 10 | 2 | 0 | 0 | 0 | 0 |
| 180210 Probiotic Assorted Fruit | 22 | 16 | 5 | 0 | 1 | 0 | 0 |
| 180316 Prenatal Multi + DHA | 22 | 21 | 1 | 0 | 0 | 0 | 0 |
| 182627 Life Extension Mix Table | 65 | 65 | 0 | 0 | 0 | 0 | 0 |
| 184004 Artery Advantage | 7 | 6 | 1 | 0 | 0 | 0 | 0 |
| 184924 G.I. Integrity | 4 | 4 | 0 | 0 | 0 | 0 | 0 |
| 19067 Digestive Health Probiot | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| 200745 Sweet Defense | 20 | 20 | 0 | 0 | 0 | 0 | 0 |
| 206312 Baby DHA Drops with Vita | 27 | 5 | 9 | 10 | 3 | 0 | 0 |
| 213472 Cell Formula | 12 | 11 | 1 | 0 | 0 | 0 | 0 |
| 219819 Precision EAA Elevated G | 28 | 22 | 6 | 0 | 0 | 0 | 0 |
| 223147 Creatine HCl | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| 224794 Beta-Carotene 15 mg | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| 233404 Keto Brain and Body Boos | 8 | 6 | 2 | 0 | 0 | 0 | 0 |
| 236915 Time Released Niacin 250 | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| 239462 Prenatal Vitamins | 13 | 13 | 0 | 0 | 0 | 0 | 0 |
| 243271 Golden Milk | 22 | 18 | 4 | 0 | 0 | 0 | 0 |
| 249741 Preseries Bulk Blue Rasp | 19 | 19 | 0 | 0 | 0 | 0 | 0 |
| 252414 BCAA 2:1:1 | 3 | 3 | 0 | 0 | 0 | 0 | 0 |
| 252451 Glucosamine Sulfate | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| 252542 Guar Gum | 4 | 2 | 2 | 0 | 0 | 0 | 0 |
| 252699 Mannitol | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| 25712 Amplified Wheybolic Extr | 49 | 41 | 7 | 0 | 1 | 0 | 0 |
| 259484 Omega-3 Extra Strength E | 10 | 3 | 6 | 0 | 1 | 0 | 0 |
| 269317 BCAA 1000 mg | 4 | 3 | 0 | 0 | 1 | 0 | 0 |
| 270253 BCAA 6 g Unflavored | 4 | 4 | 0 | 0 | 0 | 0 | 0 |
| 278009 Nutrient 950 without Iro | 29 | 29 | 0 | 0 | 0 | 0 | 0 |
| 282638 Raw Organic Perfect Food | 76 | 68 | 5 | 0 | 3 | 0 | 3 |
| 288632 Riboflavin 5'-Phosphate | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| 295064 BCAA 2:1:1 | 4 | 4 | 0 | 0 | 0 | 0 | 0 |
| 295773 Bulk Strawberry Kiwi | 23 | 21 | 2 | 0 | 0 | 0 | 0 |
| 297614 50 & Wiser Women | 65 | 64 | 0 | 0 | 1 | 0 | 0 |
| 299755 Raw Organic Fiber | 25 | 19 | 6 | 0 | 0 | 0 | 0 |
| 304647 One Daily Multi | 36 | 36 | 0 | 0 | 0 | 0 | 0 |
| 306181 BCAA 6 g Pink Drink | 21 | 17 | 4 | 0 | 0 | 0 | 0 |
| 306183 BCAA+ Peach Mango | 10 | 6 | 4 | 0 | 0 | 0 | 0 |
| 306235 Intra Pink Lemonade | 17 | 13 | 3 | 0 | 1 | 0 | 0 |
| 307569 Buffered Vitamin C + Cit | 3 | 3 | 0 | 0 | 0 | 0 | 0 |
| 307773 BCAA+ Raspberry Lemonade | 10 | 6 | 4 | 0 | 0 | 0 | 0 |
| 310608 Acai Berry Extract | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| 310970 BCAA 3:1:2 | 3 | 3 | 0 | 0 | 0 | 0 | 0 |
| 311187 Buckthorn Bark Extract | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| 31148 Active Mixed Berry | 125 | 119 | 5 | 0 | 1 | 0 | 0 |
| 311536 Sarsaparilla Root Extrac | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| 311733 Intra Blue Raspberry | 17 | 13 | 3 | 0 | 1 | 0 | 0 |
| 311734 Intra Peach Mango | 17 | 13 | 3 | 0 | 1 | 0 | 0 |
| 312819 HMB (Calcium HMB) | 2 | 2 | 0 | 0 | 0 | 0 | 0 |
| 315332 One Daily Multivitamin E | 33 | 33 | 0 | 0 | 0 | 0 | 0 |
| 315810 50 Plus One Daily Multi | 37 | 37 | 0 | 0 | 0 | 0 | 0 |
| 330285 Pine Bark Extract Powder | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| 33360 Mithras Dimethandrosteno | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| 336348 PharmaGABA-250 | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| 3565 Mega Men | 51 | 51 | 0 | 0 | 0 | 0 | 0 |
| 59952 BCAA Capsules | 4 | 4 | 0 | 0 | 0 | 0 | 0 |
| 67304 Carnitine 1000 + BCAA Or | 11 | 5 | 5 | 0 | 1 | 0 | 0 |
| 77108 BCAA+ With Hydration Com | 16 | 16 | 0 | 0 | 0 | 0 | 0 |
| 77225 Naturally Sourced Omega- | 4 | 2 | 2 | 0 | 0 | 0 | 0 |
| 82372 Beanaid | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| 9080 Iron Supplement | 1 | 1 | 0 | 0 | 0 | 0 | 0 |

Dispositions of the 'other exclusions' (all explained by reading the raw row):
- Nested "Sugar" under Total Carbohydrate (1179, 25712, 31148, 67304): Nutrition Facts child → `nutritionalInfo`, not an active. Correct.
- "Total Omega-3 Fatty Acids" (206312 ×3) and "DHA, EPA" (259484): parent-total / combined rows under a repeated serving block → merged by `_merge_alternate_serving_rows` (A13). Correct.
- Blend headers whose components DSLD stored as `forms` (1179 ×3, 14168 ×2): the cleaner expands each form into a child row (`ingredientRows[n].forms[i]` paths, "cleaner-created rows" column) and keeps the header as a non-scorable row. Correct (documented child_ingredients contract).
- "Maltodextrin" nested under a blend (180210): inactive carrier → inactive list. Correct.
- "Chloride" top-level (311733, 311734, 306235) and "2:1:1 BCAA" header (269317 only; kept on 270253): **checked by running the cleaner alone — see D.4**.
- Probiotic rows nested two levels deep (282638 ×3): dropped by the cleaner, re-added by the enricher's probiotic identity pass ("enricher-added rows" = 3) → conserved, but through a second row source (L note).
- "Lactobacillus bulgaricus, Lactobacillus plantarum" combined row (297614): dropped and not re-added → **one row lost** (combined-name probiotic row; P3 data/cleaner gap, count NOT ESTABLISHED corpus-wide).
