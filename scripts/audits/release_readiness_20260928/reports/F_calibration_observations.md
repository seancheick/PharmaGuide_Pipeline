# Calibration observations from the 143-label replay (input to N; no formula proposed here)

Real products at HEAD (`~/pg_quality/rr_20260928/head.jsonl`, probes in `probe/`). Each line is a fact the candidate evaluator should be able to explain, not a verdict.

| # | Product | Fact at HEAD | Owner / lever | Fairness question |
|---|---|---|---|---|
| C-1 | 336348 PharmaGABA-250 | `gaba powder` bio 6/15 (IQM's own rating) → Formulation 18.7/20 because the parent's best form is 6 (dynamic ceiling, RR-01) | `parent_best_form_quality` | A parent with only mediocre forms scores as if perfect |
| C-2 | 252451 Glucosamine Sulfate | crystalline sulfate bio 11 → 20/20 (ceiling 11) | same | same |
| C-3 | 288632 Riboflavin 5'-Phosphate | bio 10 → 18/20 (ceiling 10; riboflavin plain also 10) | same | R5P and plain riboflavin tie at the top: is the tie authored? |
| C-4 | 77225 life'sDHA 200 mg (vegetarian DHA) | Dose 4.0/20, Evidence 0/20 (below the 376 mg omega floor), total 39.6 POOR; pre-window 66.4 | `omega_dose` bands; `evidence_magnitudes.omega.purpose_standards` (376 mg editorial floor, 6c3a0d57) | 200 mg DHA is the standard algal/prenatal DHA dose (PMID 18184094 sits in the same record, but only for prenatal titles) |
| C-5 | 1179 Ravage, 14168 Rampant, 282638 Green Superfood, 243271 Golden Milk, 299755 Raw Organic Fiber, 315089 | Evidence 15.2/11.1/18/7.2/6.1/7.2 → 0 with state `clinical_review_not_covered` after owner-scoping (owners are proprietary blends or a greens blend with no reviewed record) | `generic_evidence` owner scoping + `_pillar_evidence` (RR-05) | Honest state, but the total pays 0 for the pipeline's backlog |
| C-6 | 233404/233406 Keto Brain (BHB 6 g, resistant dextrin 20 g, calcium, magnesium, mangiferin 150 mg) | Formulation **0/20**: `A1_bio_score` 0 although the five scorable rows carry bio 3/5/10/5/9; `botanical_profile_applied` with `weak_or_unidentified_botanical −4` | `generic_formulation` × `botanical_profile` (to confirm: does the botanical profile zero A1 for a non-botanical product because of one 150 mg mangiferin row?) | Candidate engineering bug, see RR-07 once confirmed |
| C-7 | multi/prenatal (n=18) | Evidence +4.06 mean (authority panel coverage), Transparency +2.67 (B3 removed, panel rescaled), Formulation +1.86 (ceilings) → +4.06 total mean | f2efb793, 1929d398, dd2cf1ff | A complete panel now reaches 20/20 Evidence without literature; a core nutrient's presence feeds three pillars |
| C-8 | omega (n=7) | −7.31 mean total: Formulation −1.77 (IQM form owner, undefined 6 → 4.57), Dose −2.43 (minimum basis, A13 per-column merge), Evidence −2.99 (exposure gate) | 6a3ab83f, e9f1a54c, 25decbf5, 5db560e4 | Omega is the route the window moved most; 3 of 7 lost all Evidence |
| C-9 | sports (n=26) | Evidence −2.17 mean (owner scoping), Formulation +1.25, Dose +0.68 (18 → 20 bands) | ff77935e, 59a59132 | — |
| C-10 | 59952 Doctor's Best BCAA Capsules (500 mg) | Dose 3.2/20 (`bcaa_under_3_g`), Evidence 0, total 51.5 | sports_dose bands | a 500 mg BCAA capsule is honestly under-dosed; the label directs how many capsules? (basis RR-03) |
| C-11 | 24 % of scored candidate products carry Evidence 0 (2,740 applicability_unestablished, 419 no qualifying human evidence, 322 null, 670 no assessable actives, 309 not covered) | corpus census (candidate 0d4d59a6) | `evidence_resolver` dispositions | Only the 309 are the pipeline's gap; the 2,740 are reviewed conclusions whose copy must say so |

Not established: the printed unit on 213472's label (PDF did not render in the audit browser); the corpus count of the RR-03 route asymmetry.
