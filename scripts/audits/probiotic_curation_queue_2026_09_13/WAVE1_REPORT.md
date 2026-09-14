# Wave 1 clinical curation report — 2026-09-13

Read-only. The corpus was not re-enriched or re-scored; contract snapshots are untouched.

## What was curated

- Contexts authored: 50 across 8 owning identities, citing 55 PubMed records read title/abstract on 2026-09-13.
- Combination contexts: 13 (joined to every component through `components`; never individual applicability).
- Contexts with a machine-readable studied daily dose: 9; the rest are `unresolved` because the retrieved abstract did not state it or did not support a reliable exponent.
- Publication families: 46 (`trial_family`), so papers from one cohort cannot count twice.
- Primary-outcome directions: {'positive': 28, 'null': 22, 'mixed': 1, 'unresolved': 3}; outcome kinds: {'patient_important': 95, 'surrogate': 45}.
- Designs: {'meta_analysis': 8, 'rct': 40, 'crossover_rct': 1, 'systematic_review': 1}; source tiers: {'B': 9, 'C': 10, 'D': 31}.
- Every context is `source_verified_pending_clinical_review`. Nothing scores until a clinician sets `clinician_approved`.

| identity | products (scored) | contexts total | authored Wave 1 | joined via combinations | mean Evidence today |
|---|---:|---:|---:|---:|---:|
| STRAIN_LGG | 112 | 9 | 7 | 7 | 8.0 |
| STRAIN_LACTIS_BL04 | 84 | 5 | 3 | 7 | 5.58 |
| STRAIN_ACIDOPHILUS_NCFM | 52 | 10 | 8 | 8 | 4.84 |
| STRAIN_PARACASEI_LPC37 | 51 | 2 | 0 | 5 | 6.64 |
| STRAIN_LONGUM_BB536 | 41 | 5 | 5 | 5 | 6.05 |
| STRAIN_RHAMNOSUS_HN001 | 32 | 6 | 6 | 9 | 8.0 |
| STRAIN_LACTIS_BI07 | 34 | 2 | 0 | 6 | 5.13 |
| STRAIN_LACTIS_HN019 | 31 | 7 | 5 | 8 | 6.5 |
| STRAIN_SUBTILIS_DE111 | 31 | 7 | 7 | 7 | 6.23 |
| STRAIN_SACCHAROMYCES | 16 | 12 | 9 | 9 | 8.0 |

## Scoring effect

- Products carrying a Wave 1 identity: 261. Products whose score changes today: 0.
- If a clinician approved every Wave 1 context exactly as authored: products gaining dose applicability = 0; mean Evidence delta = 0.0.
- Why approved contexts still would not apply (context-product pairs):

  - `not_individual_strain_scope`: 1849
  - `study_daily_dose_unresolved`: 1415
  - `label_dose_unknown`: 228
  - `outside_tested_daily_doses`: 48
  - `no_positive_primary_patient_important_outcome`: 7

Reading: the bridge is correct and strict. Before any context can score it needs (1) studied daily doses resolved from full texts where abstracts omit or corrupt the exponent, and (2) an attributable clinician approval of identity, dose, outcome, and applicability. The frozen policy requires exact equality with one tested daily arm; values between or near arms earn no applicability credit. Combination and species-level contexts are recorded as research but can never become single-strain applicability by design.

## Formulation effect of the new identities (approximation)

- Scored probiotics whose identity-code credit would change once the stubs are live in enrichment: 196 of 548.
- Raw component delta distribution (of 8 points): {'2.0': 14, '1.0': 35, '5.0': 28, '7.0': 48, '4.0': 20, '3.0': 32, '8.0': 19}.
- Approximate shipped formulation-pillar mean delta for those products: 4.02 (reference 22.0).
- Approximation: identity ownership in scoring also requires the label row proof (source_row_ref); real numbers come from a re-enrichment.

## Null, negative and conflicting evidence kept

- STRAIN_LGG: `lgg_icu_ventilator_pneumonia_prospect_34546300` — primary ventilator_associated_pneumonia:null (PMIDs 34546300)
- STRAIN_LGG: `lgg_adult_ibs_open_label_vs_diet_25473176` — primary ibs_severity_score_change:null (PMIDs 25473176)
- STRAIN_LACTIS_HN019: `hn019_functional_constipation_dose_ranging_28d_29227175` — primary colonic_transit_time:null (PMIDs 29227175)
- STRAIN_LACTIS_HN019: `hn019_hn001_functional_constipation_vs_fibers_37078654` — primary bowel_movement_frequency:null (PMIDs 37078654)
- STRAIN_ACIDOPHILUS_NCFM: `ncfm_infant_colic_41998618` — primary responder_rate_day_28:null (PMIDs 41998618)
- STRAIN_ACIDOPHILUS_NCFM: `ncfm_lpc37_bl04_bi07_hn019_constipation_bloating_2wk_31131616` — primary bloating:null (PMIDs 31131616)
- STRAIN_ACIDOPHILUS_NCFM: `bi07_lpc37_ncfm_bl04_omega3_elderly_inflammation_36235651` — primary hs_crp:null (PMIDs 36235651)
- STRAIN_ACIDOPHILUS_NCFM: `ncfm_lpc37_bl04_bi07_bb02_chemotherapy_diarrhea_41379184` — primary grade_2_3_diarrhea:null (PMIDs 41379184)
- STRAIN_ACIDOPHILUS_NCFM: `ncfm_hn001_lpc37_hn019_caloric_restriction_obese_men_39842252` — primary body_weight_change:null, body_fat_change:null (PMIDs 39842252)
- STRAIN_SACCHAROMYCES: `sb_cncm_i745_h_pylori_triple_therapy_gistar_37942999` — primary eradication_rate_itt:mixed (PMIDs 37942999)
- STRAIN_SACCHAROMYCES: `sb_adult_acute_viral_diarrhea_37400812` — primary symptom_severity:null (PMIDs 37400812)
- STRAIN_LONGUM_BB536: `bb536_male_athletes_high_protein_gi_symptoms_42046285` — primary gastrointestinal_symptoms:null (PMIDs 42046285)
- STRAIN_SUBTILIS_DE111: `de111_female_athletes_offseason_training_33105368` — primary strength_and_performance:null (PMIDs 33105368)
- STRAIN_SUBTILIS_DE111: `de111_daycare_children_microbiome_33161736` — primary overall_microbiome_equilibrium:null (PMIDs 33161736)
- STRAIN_SUBTILIS_DE111: `de111_whey_protein_amino_acid_response_33462163` — primary plasma_amino_acid_auc_after_whey:null (PMIDs 33462163)
- STRAIN_RHAMNOSUS_HN001: `hn001_b420_pregnancy_fishoil_child_allergy_37622257` — primary physician_diagnosed_food_allergy:null, atopic_eczema:null, atopy:null (PMIDs 37622257, 37642166)
- STRAIN_RHAMNOSUS_HN001: `hn001_perceived_stress_happiness_39275252` — primary oxford_happiness_questionnaire:null (PMIDs 39275252)
- STRAIN_RHAMNOSUS_HN001: `hn019_hn001_fos_immune_parameters_healthy_adults_37614109` — primary plasma_c_reactive_protein:null (PMIDs 37614109)
- STRAIN_LACTIS_BL04: `bl04_rhinovirus_challenge_phase2_34927036` — primary rhinovirus_associated_illness:null (PMIDs 34927036)
- STRAIN_LACTIS_BL04: `bl04_cardiovascular_risk_markers_healthy_33161737` — primary cardiovascular_risk_parameters:null (PMIDs 33161737)

## Schema limitations met

- Abstract text from the PubMed API strips italics, which removes genus/species tokens and superscript exponents; doses such as `1 x 10^10` arrive as `1 x 10`. Full-text reads are required before any dose can be approved.
- PMID 33462163 is explicitly unresolved: its PubMed abstract prints `1 x 10-9 CFU`, so the apparent exponent is not silently repaired to 1 billion CFU.
- Mass-dosed organisms (S. boulardii, 250-1000 mg/day) cannot be expressed in the CFU-only dose block; recorded as `unresolved` with the mass in limitations.
- Studies of a strain plus a non-registry strain (for example BB536 + MCC1274, HN001 + LE16) cannot be authored as combinations; B. lactis 420 was added as an identity for that reason. MCC1274, LE16 and B. lactis DN-173 010 remain candidates.
- Meta-analyses have no single dose or sample size; `hierarchy: unresolved` is used for strain-level rankings inside class-level pooled analyses.

## Remaining

- Unreviewed identities after Wave 1: 94 of 105.
- Wave 2 (13 identities) and Wave 3 (the rest, including the 56 label-resolution stubs) are queued in QUEUE.md.
- Owner decisions: (a) full-text dose resolution for the Wave 1 contexts with `unresolved` doses; (b) the dose-window policy for applicability; (c) whether to run the curation sprint before or after the single full re-score.
