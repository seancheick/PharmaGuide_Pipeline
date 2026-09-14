# Wave 2 clinical curation report — 2026-09-14

Read-only. The corpus was not re-enriched or re-scored; contract snapshots are untouched.
No identity stubs were added: the DDS-1 combination partner already exists as `STRAIN_LACTIS_UABla12`,
and trials whose partner strains have no registry identity stay reviewed-not-recorded (wave2_read_log.md).

## What was curated

- Contexts authored: 59 across 11 owning identities, citing 59 PubMed records read title/abstract on 2026-09-14 (full read log: wave2_read_log.md).
- Combination contexts: 24 (joined to every component through `components`; never individual applicability). RC-14, R0175, UABla-12, CRL-431 and LGG join only through combinations.
- Contexts with a machine-readable studied daily dose: 18; the rest are `unresolved` because the retrieved abstract did not state it or lost the exponent.
- Publication families: 57 (`trial_family`), so papers from one cohort cannot count twice.
- Primary-outcome directions: {'null': 6, 'positive': 6}; all-outcome directions: {'positive': 95, 'null': 41, 'mixed': 1, 'unresolved': 2}; outcome kinds: {'patient_important': 94, 'surrogate': 45}.
- Designs: {'rct': 46, 'open_label': 2, 'meta_analysis': 7, 'systematic_review': 2, 'crossover_rct': 2}; source tiers: {'C': 21, 'D': 27, 'E': 2, 'B': 9}.
- Every context is `source_verified_pending_clinical_review`. Nothing scores until a clinician sets `clinician_approved`.

| identity | products (scored) | contexts total | authored Wave 2 | joined via combinations | mean Evidence today |
|---|---:|---:|---:|---:|---:|
| STRAIN_COAGULANS_IS2 | 20 | 9 | 9 | 9 | 6.2 |
| STRAIN_COAGULANS_MTCC5856 | 19 | 6 | 6 | 6 | 7.05 |
| STRAIN_ACIDOPHILUS_DDS1 | 17 | 8 | 8 | 8 | 4.0 |
| STRAIN_PLANTARUM_299V | 12 | 8 | 8 | 8 | 8.0 |
| STRAIN_ACIDOPHILUS_LA5 | 12 | 8 | 8 | 8 | 7.0 |
| STRAIN_LACTIS_BB12 | 15 | 5 | 4 | 13 | 7.33 |
| STRAIN_BREVE_M16V | 10 | 3 | 3 | 3 | 6.0 |
| STRAIN_HELVETICUS_R0052 | 8 | 4 | 4 | 4 | 4.0 |
| STRAIN_PLANTARUM_LP01 | 7 | 1 | 1 | 1 | 2.31 |
| STRAIN_COAGULANS_GBI30 | 4 | 3 | 3 | 3 | 7.5 |
| STRAIN_RHAMNOSUS_GR1 | 4 | 5 | 5 | 5 | 8.0 |
| STRAIN_FERMENTUM_RC14 | 4 | 0 | 0 | 5 | 8.0 |
| STRAIN_LONGUM_R0175 | 4 | 0 | 0 | 4 | 2.0 |

## Scoring effect

- Nothing changes today: every Wave 2 context is pending and pending never scores.
- The product-level what-if was NOT computable in this checkout (scripts/products/output_*_{enriched,scored} not present in this checkout; re-run this script in a checkout that has the corpus to compute the evidence what-if (wave1_projection.json was built against 548 scored probiotics).)
- Owner action: run `wave2_projection.py` then re-run this builder in the corpus checkout to fill this section.

## Null, negative and conflicting evidence kept

- STRAIN_COAGULANS_GBI30: `bc30_synbiotic_pasta_cardiometabolic_31162597` — hs_crp:null, lipid_profile:null (PMIDs 31162597)
- STRAIN_COAGULANS_MTCC5856: `mtcc5856_pediatric_acute_diarrhea_38269290` — stool_frequency:null (PMIDs 38269290)
- STRAIN_COAGULANS_MTCC5856: `mtcc5856_healthy_microbiome_37335737` — gut_microbiome_composition:null (PMIDs 37335737)
- STRAIN_COAGULANS_IS2: `is2_adult_ibs_multicenter_31434935` — serum_cytokines:null (PMIDs 31434935)
- STRAIN_COAGULANS_IS2: `is2_constipation_lactulose_cotherapy_34599466` — stool_frequency_vs_lactulose:mixed (PMIDs 34599466)
- STRAIN_COAGULANS_IS2: `is2_infrequent_bowel_movements_40456531` — gastrointestinal_symptoms:null, quality_of_life:null, gut_microbiota_composition:null (PMIDs 40456531)
- STRAIN_COAGULANS_IS2: `is2_chronic_constipation_meta_36372047` — stool_frequency_is2_subgroup:null (PMIDs 36372047)
- STRAIN_COAGULANS_IS2: `is2_moderate_covid19_adjunct_39866999` — crp_ldh_il6:null (PMIDs 39866999)
- STRAIN_PLANTARUM_299V: `lp299v_iron_absorption_meta_31816981` — iron_status_markers:null (PMIDs 31816981)
- STRAIN_PLANTARUM_299V: `lp299v_female_athletes_iron_32365981` — serum_ferritin:null, reticulocyte_hemoglobin:null (PMIDs 32365981)
- STRAIN_PLANTARUM_299V: `lp299v_cancer_home_enteral_nutrition_33015813` — overall_nutritional_status:null, quality_of_life:null (PMIDs 33015813)
- STRAIN_PLANTARUM_299V: `lp299v_exam_stress_cortisol_28101105` — salivary_iga:null (PMIDs 28101105)
- STRAIN_PLANTARUM_299V: `lp299v_colon_resection_22434095` — enteric_bacterial_load:null, bacterial_translocation:null, postoperative_complications:null (PMIDs 22434095)
- STRAIN_LACTIS_BB12: `lgg_bb12_preterm_administration_route_37020105` — microbiota_change_via_maternal_route:null (PMIDs 37020105)
- STRAIN_ACIDOPHILUS_LA5: `la5_bb12_aad_incidence_24772726` — aad_incidence:null (PMIDs 24772726)
- STRAIN_ACIDOPHILUS_LA5: `la5_bb12_hpylori_yogurt_aad_21871144` — h_pylori_urease_activity:null (PMIDs 21871144)
- STRAIN_ACIDOPHILUS_LA5: `la5_bb12_lc01_yogurt_aad_30439760` — aad_incidence:null (PMIDs 30439760)
- STRAIN_ACIDOPHILUS_LA5: `la5_bb12_primal_preterm_mdro_39102225` — mdro_colonization:null (PMIDs 39102225)
- STRAIN_RHAMNOSUS_GR1: `gr1_rc14_bv_metronidazole_adjunct_34295831` — bv_cure_rate_30_and_90_days:null, strain_detection_vaginal_fecal:null (PMIDs 34295831)
- STRAIN_RHAMNOSUS_GR1: `gr1_rc14_pregnancy_bv_30932317` — bacterial_vaginosis_18_20_weeks:null, vaginal_colonization:null, microbiota_composition:null (PMIDs 30932317)
- STRAIN_RHAMNOSUS_GR1: `gr1_rc14_pregnancy_colonization_32325794` — vaginal_colonization_administered_strains:null (PMIDs 32325794)
- STRAIN_RHAMNOSUS_GR1: `gr1_rc14_sci_mdr_colonization_31953482` — existing_colonization_clearance:null (PMIDs 31953482)
- STRAIN_BREVE_M16V: `m16v_simpro_five_year_followup_41515257` — neurodevelopment_5_years:null, growth_5_years:null, blood_pressure_5_years:null, atopy_5_years:null (PMIDs 41515257)
- STRAIN_HELVETICUS_R0052: `r0052_r0175_healthy_adults_null_37049546` — whole_sample_psychological_outcomes:null (PMIDs 37049546)
- STRAIN_ACIDOPHILUS_DDS1: `dds1_night_shift_stress_markers_33584665` — stress_marker_night_shift_interactions:null (PMIDs 33584665)
- STRAIN_ACIDOPHILUS_DDS1: `dds1_uabla12_fos_pediatric_ari_26463725` — ari_incidence:null (PMIDs 26463725)
- STRAIN_PLANTARUM_LP01: `lp01_bb12_synbiotic_constipation_29949873` — stool_evacuation:null, pac_sym:null, pac_qol:null (PMIDs 29949873)

## Schema limitations met

- Abstract text from the PubMed API strips superscript exponents; doses such as `4 x 10^9` can arrive as `4 x 10`. Full-text reads are required before any dose can be approved.
- Combination totals (for example DDS-1 + UABla-12 at 5 x 10^9 CFU/day) are recorded on the combination context only and never become an individual-strain dose.
- Two recorded combination trials used a product with one extra non-registry strain (LC-01; an unnamed B. longum subsp. infantis). Both are nulls, recorded with the formulation named in limitations for the clinician to weigh.
- Meta-analyses have no single dose or sample size; `hierarchy: unresolved` is used for strain-level rankings inside class-level pooled analyses, and endpoint hierarchies the abstract did not state are `unresolved` rather than guessed.

## Remaining

- Unreviewed identities after Wave 2: 84 of 105.
- Wave 3 (the rest, including the 56 label-resolution stubs) remains queued in QUEUE.md; LP01's controlled evidence base is largely non-registry multi-strain formulations (see wave2_read_log.md).
- Owner decisions: (a) full-text dose resolution for contexts with `unresolved` doses; (b) the dose-window applicability policy; (c) whether the UABla-12 solo arm of PMID 32019158 and the classic BB-12 colic/daycare trials get their own curation pass.
