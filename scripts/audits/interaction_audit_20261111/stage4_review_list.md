## G1. Highest-volume rules per profile (baseline sample, 4,000 products)

| Profile (share warned) | Subject (products) | Sub-rule | Severity | Evidence | Dose gate | Amount named in text, not gated | Sources |
|---|---|---|---|---|---|---|---|
| anticoagulants (38.6%) | vitamin_e (534) | `RULE_IQM_VITAMIN_E_PREGNANCY_EXCESS` drug_class_rules[0] | caution | established | no | 400 IU | 1 |
| anticoagulants (38.6%) | dha (226) | `RULE_IQM_DHA_BLEEDING` drug_class_rules[0] | caution | theoretical | no |  | 1 |
| anticoagulants (38.6%) | epa (203) | `RULE_IQM_EPA_BLEEDING` drug_class_rules[0] | caution | theoretical | no |  | 1 |
| anticoagulants (38.6%) | vitamin_d (187) | `RULE_INGREDIENT_VITAMIN_D` drug_class_rules[0] | monitor | theoretical | no | 10,000 IU | 2 |
| anticoagulants (38.6%) | ginger (136) | `RULE_IQM_GINGER_BLEEDING` drug_class_rules[0] | caution | probable | no |  | 1 |
| antihypertensives (25.2%) | potassium (396) | `RULE_IQM_POTASSIUM_HYPERTENSION` drug_class_rules[0] | caution | established | no |  | 1 |
| antihypertensives (25.2%) | iron (265) | `RULE_IQM_IRON_HYPERTENSION` drug_class_rules[0] | caution | limited | no |  | 3 |
| antihypertensives (25.2%) | magnesium (160) | `RULE_IQM_MAGNESIUM_HYPERTENSION` drug_class_rules[0] | monitor | probable | no |  | 1 |
| antihypertensives (25.2%) | green_tea_extract (82) | `RULE_IQM_GREEN_TEA_HYPERTENSION` drug_class_rules[0] | caution | theoretical | no | 400 mg | 2 |
| antihypertensives (25.2%) | l_theanine (56) | `RULE_IQM_L_THEANINE_ANTIHYPERTENSIVES` drug_class_rules[0] | caution | theoretical | no | 200 mg, 250 mg | 2 |
| pregnancy (40.7%) | calcium (565) | via pregnancy_lactation block or curated pair | | | | | |
| pregnancy (40.7%) | zinc (471) | via pregnancy_lactation block or curated pair | | | | | |
| pregnancy (40.7%) | vitamin_b6_pyridoxine (448) | `RULE_IQM_VITAMIN_B6_LACTATION` condition_rules[0] | monitor | probable | no |  | 2 |
| pregnancy (40.7%) | magnesium (383) | via pregnancy_lactation block or curated pair | | | | | |
| pregnancy (40.7%) | potassium (328) | via pregnancy_lactation block or curated pair | | | | | |
| lactation (46.2%) | vitamin_b6_pyridoxine (499) | `RULE_IQM_VITAMIN_B6_LACTATION` condition_rules[1] | caution | theoretical | no | 1.9 mg, 2.0 mg, 50 mg, 600 mg | 3 |
| lactation (46.2%) | calcium (312) | via pregnancy_lactation block or curated pair | | | | | |
| lactation (46.2%) | vitamin_c (248) | via pregnancy_lactation block or curated pair | | | | | |
| lactation (46.2%) | vitamin_d (216) | via pregnancy_lactation block or curated pair | | | | | |
| lactation (46.2%) | potassium (204) | via pregnancy_lactation block or curated pair | | | | | |
| diabetes (18.2%) | vitamin_b3_niacin (513) | `RULE_IQM_NIACIN_DIABETES` condition_rules[0] | caution | established | no | 1g | 1 |
| diabetes (18.2%) | alpha_lipoic_acid (123) | `RULE_IQM_ALPHA_LIPOIC_ACID_DIABETES` condition_rules[0] | caution | probable | no |  | 1 |
| diabetes (18.2%) | fenugreek (35) | `RULE_IQM_FENUGREEK_DIABETES` condition_rules[0] | caution | probable | no |  | 2 |
| diabetes (18.2%) | stinging_nettle (25) | `RULE_IQM_STINGING_NETTLE_DIABETES` condition_rules[0] | caution | probable | no | 18 mg, 500 mg | 2 |
| diabetes (18.2%) | ginseng (25) | `RULE_INGREDIENT_GINSENG` condition_rules[1] | monitor | probable | no | 100 mg | 2 |
| kidney_disease (17.8%) | magnesium (484) | `RULE_IQM_MAGNESIUM_HYPERTENSION` condition_rules[2] | avoid | established | no |  | 4 |
| kidney_disease (17.8%) | potassium (411) | `RULE_IQM_POTASSIUM_HYPERTENSION` condition_rules[1] | avoid | established | no |  | 1 |
| kidney_disease (17.8%) | tribulus (16) | `RULE_IQM_TRIBULUS_METABOLIC` condition_rules[3] | monitor | theoretical | no |  | 1 |
| kidney_disease (17.8%) | dandelion (16) | `RULE_IQM_DANDELION_KIDNEY` condition_rules[0] | caution | limited | no |  | 3 |
| kidney_disease (17.8%) | senna (5) | `RULE_IQM_SENNA_PREGNANCY` condition_rules[1] | caution | probable | no |  | 2 |
| heart_disease (13.6%) | potassium (403) | `RULE_IQM_POTASSIUM_HYPERTENSION` condition_rules[2] | caution | established | no |  | 1 |
| heart_disease (13.6%) | l_arginine (80) | `RULE_IQM_L_ARGININE_HYPERTENSION` condition_rules[1] | caution | probable | no |  | 1 |
| heart_disease (13.6%) | calcium (47) | `RULE_IQM_CALCIUM` condition_rules[0] | caution | theoretical | yes |  | 3 |
| heart_disease (13.6%) | vitamin_d (23) | `RULE_INGREDIENT_VITAMIN_D` condition_rules[0] | monitor | probable | yes |  | 2 |
| heart_disease (13.6%) | guarana (14) | `RULE_IQM_GUARANA` condition_rules[1] | caution | probable | no | 200 mg | 2 |
| thyroid_medications (28.3%) | calcium (684) | `RULE_IQM_CALCIUM` drug_class_rules[0] | caution | established | no | 1000 mg | 4 |
| thyroid_medications (28.3%) | zinc (597) | `RULE_IQM_ZINC` drug_class_rules[0] | caution | theoretical | no |  | 1 |
| thyroid_medications (28.3%) | magnesium (484) | `RULE_IQM_MAGNESIUM_HYPERTENSION` drug_class_rules[1] | caution | probable | no |  | 3 |
| thyroid_medications (28.3%) | chromium (370) | `RULE_IQM_CHROMIUM_GLUCOSE` drug_class_rules[2] | caution | probable | no |  | 1 |
| thyroid_medications (28.3%) | iron (265) | `RULE_IQM_IRON_HYPERTENSION` drug_class_rules[1] | caution | established | no |  | 2 |

## G2. Theoretical or limited-evidence sub-rules at caution or above

| Rule | Sub-rule | Target | Severity | Evidence | Sources |
|---|---|---|---|---|---|
| `RULE_BANNED_7KETO_DHEA_PREGNANCY` | condition_rules[0] | pregnancy | contraindicated | limited | 2 |
| `RULE_BANNED_BITTER_ORANGE_HYPERTENSION` | condition_rules[0] | hypertension | avoid | theoretical | 1 |
| `RULE_BANNED_BITTER_ORANGE_HYPERTENSION` | drug_class_rules[0] | antihypertensives | avoid | theoretical | 1 |
| `RULE_IQM_BERBERINE_DIABETES` | drug_class_rules[2] | statins | caution | limited | 1 |
| `RULE_IQM_BERBERINE_DIABETES` | drug_class_rules[3] | maois | avoid | theoretical | 2 |
| `RULE_IQM_BLACK_COHOSH_PREGNANCY` | condition_rules[1] | liver_disease | avoid | theoretical | 2 |
| `RULE_IQM_GLUCOMANNAN_DIABETES` | drug_class_rules[2] | thyroid_medications | caution | theoretical | 1 |
| `RULE_IQM_GINKGO_HYPERTENSION` | drug_class_rules[0] | antihypertensives | caution | theoretical | 2 |
| `RULE_INGREDIENT_GINSENG` | drug_class_rules[3] | cardiac_glycosides | caution | theoretical | 2 |
| `RULE_INGREDIENT_GINSENG` | drug_class_rules[4] | maois | caution | theoretical | 2 |
| `RULE_IQM_GREEN_TEA_HYPERTENSION` | drug_class_rules[0] | antihypertensives | caution | theoretical | 2 |
| `RULE_IQM_IODINE_PREGNANCY_EXCESS` | drug_class_rules[1] | lithium | caution | theoretical | 1 |
| `RULE_IQM_IRON_HYPERTENSION` | condition_rules[0] | liver_disease | caution | limited | 3 |
| `RULE_IQM_IRON_HYPERTENSION` | drug_class_rules[0] | antihypertensives | caution | limited | 3 |
| `RULE_INGREDIENT_ST_JOHNS_WORT` | drug_class_rules[6] | maois | contraindicated | theoretical | 1 |
| `RULE_BOTAN_BLUE_COHOSH_PREGNANCY` | condition_rules[0] | pregnancy | contraindicated | limited | 1 |
| `RULE_BOTAN_MUGWORT_PREGNANCY` | condition_rules[0] | pregnancy | contraindicated | limited | 1 |
| `RULE_BOTAN_RUE_PREGNANCY` | condition_rules[0] | pregnancy | contraindicated | limited | 1 |
| `RULE_IQM_KAVALACTONES_LIVER` | condition_rules[0] | liver_disease | avoid | limited | 2 |
| `RULE_IQM_KAVALACTONES_LIVER` | condition_rules[1] | seizure_disorder | caution | limited | 4 |
| `RULE_IQM_VALERIAN_LIVER` | drug_class_rules[0] | sedatives | caution | theoretical | 2 |
| `RULE_IQM_SAW_PALMETTO_LIVER` | condition_rules[3] | ttc | caution | theoretical | 3 |
| `RULE_IQM_TURMERIC_LIVER` | drug_class_rules[0] | anticoagulants | caution | theoretical | 1 |
| `RULE_IQM_TURMERIC_LIVER` | drug_class_rules[1] | antiplatelets | caution | theoretical | 2 |
| `RULE_INGREDIENT_CURCUMIN` | condition_rules[1] | pregnancy | caution | theoretical | 1 |
| `RULE_INGREDIENT_CURCUMIN` | drug_class_rules[0] | anticoagulants | caution | theoretical | 1 |
| `RULE_INGREDIENT_CURCUMIN` | drug_class_rules[1] | antiplatelets | caution | theoretical | 3 |
| `RULE_INGREDIENT_CHAMOMILE` | drug_class_rules[3] | sedatives | caution | theoretical | 1 |
| `RULE_INGREDIENT_CAT_S_CLAW` | condition_rules[0] | bleeding_disorders | caution | theoretical | 1 |
| `RULE_INGREDIENT_CAT_S_CLAW` | drug_class_rules[0] | anticoagulants | caution | theoretical | 2 |
| `RULE_IQM_CALCIUM` | condition_rules[0] | heart_disease | caution | theoretical | 3 |
| `RULE_IQM_ZINC` | drug_class_rules[0] | thyroid_medications | caution | theoretical | 1 |
| `RULE_INGREDIENT_ECHINACEA__AUTOIMMUNE` | condition_rules[0] | autoimmune | caution | theoretical | 2 |
| `RULE_INGREDIENT_ECHINACEA__AUTOIMMUNE` | drug_class_rules[0] | immunosuppressants | avoid | theoretical | 2 |
| `RULE_INGREDIENT_ASTRAGALUS__AUTOIMMUNE` | drug_class_rules[0] | immunosuppressants | avoid | theoretical | 1 |
| `RULE_INGREDIENT_REISHI__AUTOIMMUNE` | condition_rules[0] | autoimmune | caution | theoretical | 1 |
| `RULE_INGREDIENT_REISHI__AUTOIMMUNE` | drug_class_rules[0] | immunosuppressants | caution | theoretical | 1 |
| `RULE_INGREDIENT_PASSIONFLOWER__SEDATIVES` | drug_class_rules[0] | sedatives | caution | theoretical | 1 |
| `RULE_IQM_CITRUS_BERGAMOT_CHOLESTEROL` | drug_class_rules[0] | statins | avoid | limited | 4 |
| `RULE_IQM_CITRUS_BERGAMOT_CHOLESTEROL` | drug_class_rules[1] | calcium_channel_blockers | avoid | limited | 4 |
| `RULE_IQM_CITRUS_BERGAMOT_CHOLESTEROL` | drug_class_rules[2] | immunosuppressants | contraindicated | limited | 4 |
| `RULE_IQM_CITRUS_BERGAMOT_CHOLESTEROL` | drug_class_rules[3] | antiarrhythmics | avoid | limited | 4 |
| `RULE_IQM_CITRUS_BERGAMOT_CHOLESTEROL` | drug_class_rules[4] | anticoagulants | caution | limited | 3 |
| `RULE_IQM_VITAMIN_B6_LACTATION` | condition_rules[1] | lactation | caution | theoretical | 3 |
| `RULE_IQM_VITAMIN_B6_LACTATION` | condition_rules[2] | seizure_disorder | caution | theoretical | 3 |
| `RULE_IQM_SAGE_LACTATION` | condition_rules[0] | pregnancy | avoid | theoretical | 1 |
| `RULE_IQM_SAGE_LACTATION` | condition_rules[1] | lactation | caution | theoretical | 2 |
| `RULE_IQM_GOTU_KOLA_HEPATOTOXICITY` | drug_class_rules[0] | sedatives | caution | theoretical | 2 |
| `RULE_IQM_RHODIOLA_IMMUNE_BP` | drug_class_rules[1] | immunosuppressants | caution | theoretical | 2 |
| `RULE_IQM_WILD_YAM_PREGNANCY` | condition_rules[0] | pregnancy | avoid | theoretical | 1 |
| `RULE_IQM_WILD_YAM_PREGNANCY` | condition_rules[1] | lactation | caution | theoretical | 1 |
| `RULE_IQM_WILD_YAM_PREGNANCY` | condition_rules[2] | ttc | caution | theoretical | 1 |
| `RULE_IQM_YERBA_MATE_CARDIOVASCULAR` | drug_class_rules[0] | anticoagulants | caution | theoretical | 2 |
| `RULE_IQM_ANDROGRAPHIS` | condition_rules[0] | bleeding_disorders | caution | theoretical | 3 |
| `RULE_IQM_ANDROGRAPHIS` | condition_rules[1] | autoimmune | caution | theoretical | 3 |
| `RULE_IQM_ANDROGRAPHIS` | drug_class_rules[2] | immunosuppressants | caution | theoretical | 2 |
| `RULE_IQM_RED_CLOVER` | drug_class_rules[0] | anticoagulants | caution | theoretical | 3 |
| `RULE_IQM_COPPER_LIVER` | condition_rules[0] | liver_disease | caution | theoretical | 2 |
| `RULE_IQM_MANGANESE_LIVER` | condition_rules[0] | liver_disease | caution | theoretical | 2 |
| `RULE_IQM_5HTP_SEROTONIN` | condition_rules[0] | pregnancy | avoid | theoretical | 2 |
| `RULE_IQM_SENNA_PREGNANCY` | drug_class_rules[0] | cardiac_glycosides | avoid | theoretical | 3 |
| `RULE_IQM_CASCARA_SAGRADA_PREGNANCY` | drug_class_rules[0] | cardiac_glycosides | avoid | theoretical | 2 |
| `RULE_IQM_ALOE_FEROX` | drug_class_rules[0] | cardiac_glycosides | avoid | theoretical | 2 |
| `RULE_IQM_CHINESE_SKULLCAP_LIVER` | condition_rules[0] | pregnancy | avoid | theoretical | 2 |
| `RULE_IQM_BLACK_SEED_OIL_DIABETES` | drug_class_rules[0] | anticoagulants | caution | theoretical | 1 |
| `RULE_IQM_BLACK_SEED_OIL_DIABETES` | drug_class_rules[3] | antihypertensives | caution | theoretical | 1 |
| `RULE_IQM_DHA_BLEEDING` | drug_class_rules[0] | anticoagulants | caution | theoretical | 1 |
| `RULE_IQM_DHA_BLEEDING` | drug_class_rules[1] | antiplatelets | caution | theoretical | 1 |
| `RULE_IQM_EPA_BLEEDING` | drug_class_rules[0] | anticoagulants | caution | theoretical | 1 |
| `RULE_IQM_EPA_BLEEDING` | drug_class_rules[1] | antiplatelets | caution | theoretical | 1 |
| `RULE_IQM_L_THEANINE_ANTIHYPERTENSIVES` | drug_class_rules[0] | antihypertensives | caution | theoretical | 2 |
| `RULE_IQM_L_THEANINE_ANTIHYPERTENSIVES` | drug_class_rules[1] | sedatives | caution | theoretical | 2 |
| `RULE_IQM_BACOPA_THYROID` | drug_class_rules[0] | thyroid_medications | caution | theoretical | 1 |
| `RULE_IQM_BACOPA_THYROID` | drug_class_rules[1] | sedatives | caution | theoretical | 2 |
| `RULE_IQM_DANDELION_KIDNEY` | condition_rules[0] | kidney_disease | caution | limited | 3 |
| `RULE_IQM_DANDELION_KIDNEY` | drug_class_rules[2] | hypoglycemics_high_risk | caution | theoretical | 1 |
| `RULE_IQM_DANDELION_KIDNEY` | drug_class_rules[4] | hypoglycemics_unknown | caution | theoretical | 1 |
| `RULE_IQM_ALCAR_THYROID` | condition_rules[0] | thyroid_disorder | caution | theoretical | 1 |
| `RULE_IQM_ALCAR_THYROID` | drug_class_rules[0] | thyroid_medications | caution | theoretical | 1 |
| `RULE_IQM_ALCAR_THYROID` | drug_class_rules[1] | anticoagulants | caution | theoretical | 1 |
| `RULE_IQM_WHITE_WILLOW_BARK_BLEEDING` | condition_rules[1] | surgery_scheduled | avoid | limited | 2 |
| `RULE_IQM_L_TYROSINE_THYROID` | drug_class_rules[0] | maois | contraindicated | theoretical | 2 |
| `RULE_IQM_L_TYROSINE_THYROID` | drug_class_rules[1] | thyroid_medications | caution | theoretical | 2 |
| `RULE_IQM_SILYMARIN_LIVER` | drug_class_rules[0] | immunosuppressants | caution | theoretical | 1 |
| `RULE_IQM_SILYMARIN_LIVER` | drug_class_rules[1] | statins | caution | theoretical | 1 |
| `RULE_IQM_FORSKOLIN_ANTIHYPERTENSIVES` | drug_class_rules[1] | anticoagulants | caution | theoretical | 1 |
| `RULE_IQM_HORNY_GOAT_WEED_HEART` | condition_rules[0] | heart_disease | caution | theoretical | 4 |
| `RULE_IQM_HORNY_GOAT_WEED_HEART` | drug_class_rules[0] | antihypertensives | caution | theoretical | 3 |
| `RULE_IQM_STINGING_NETTLE_BLOOD_PRESSURE` | drug_class_rules[0] | antihypertensives | caution | theoretical | 2 |
| `RULE_IQM_OLIVE_LEAF_DIABETES` | drug_class_rules[0] | antihypertensives | caution | theoretical | 1 |
| `RULE_IQM_CORDYCEPS_AUTOIMMUNE` | condition_rules[0] | autoimmune | caution | theoretical | 1 |
| `RULE_IQM_CORDYCEPS_AUTOIMMUNE` | drug_class_rules[0] | immunosuppressants | avoid | theoretical | 1 |
| `RULE_IQM_CORDYCEPS_AUTOIMMUNE` | drug_class_rules[1] | anticoagulants | caution | theoretical | 1 |
| `RULE_IQM_LIONS_MANE_ANTICOAGULANTS` | drug_class_rules[0] | anticoagulants | caution | theoretical | 1 |
| `RULE_IQM_RESVERATROL_BLEEDING` | condition_rules[0] | bleeding_disorders | caution | theoretical | 1 |
| `RULE_IQM_RESVERATROL_BLEEDING` | drug_class_rules[0] | anticoagulants | caution | theoretical | 2 |
| `RULE_IQM_RESVERATROL_BLEEDING` | drug_class_rules[1] | antiplatelets | caution | theoretical | 1 |
| `RULE_BANNED_TANSY_PREGNANCY` | condition_rules[0] | pregnancy | contraindicated | limited | 2 |
| `RULE_IQM_HOLY_BASIL_PREGNANCY` | condition_rules[0] | pregnancy | caution | limited | 1 |
| `RULE_BOTAN_WHITE_MULBERRY_DIABETES` | condition_rules[0] | diabetes | caution | theoretical | 1 |
| `RULE_IQM_PHENYLETHYLAMINE` | drug_class_rules[0] | maois | contraindicated | theoretical | 1 |
| `RULE_BANNED_ADD_HORDENINE` | drug_class_rules[0] | maois | contraindicated | theoretical | 1 |
| `RULE_IQM_SAME` | drug_class_rules[0] | maois | avoid | limited | 3 |
| `RULE_BOTAN_BUPLEURUM_CYP2D6` | drug_class_rules[0] | cyp2d6_substrates | caution | theoretical | 1 |
| `RULE_BOT_WEEPING_WILLOW_BARK` | condition_rules[0] | bleeding_disorders | caution | theoretical | 2 |
| `RULE_BOT_WEEPING_WILLOW_BARK` | condition_rules[1] | surgery_scheduled | caution | theoretical | 2 |
| `RULE_BOT_WEEPING_WILLOW_BARK` | drug_class_rules[0] | anticoagulants | caution | theoretical | 2 |
| `RULE_BOT_WEEPING_WILLOW_BARK` | drug_class_rules[1] | antiplatelets | caution | theoretical | 2 |
| `RULE_BOT_WEEPING_WILLOW_BARK` | drug_class_rules[2] | nsaids | caution | theoretical | 2 |

109 sub-rules.

## G3. Timing rules not published (review_status other than verified)

| Rule | Status | Reason held |
|---|---|---|
| `timing_iron_calcium_separate` | needs_revision | interval_not_supported_by_cited_source |
| `timing_iron_zinc_separate` | needs_revision | interval_not_supported_by_cited_source |
| `timing_calcium_vitamin_d_together` | needs_revision | awaiting_clinician_decision |
| `timing_melatonin_before_bed` | needs_revision | citation_not_content_verified |
| `timing_probiotics_by_formulation` | needs_revision | canonical_identity_unresolved |
| `timing_psyllium_water_med_spacing` | needs_revision | awaiting_clinician_decision |
| `timing_egcg_iron_separate` | needs_revision | form_specific_evidence_missing |
| `timing_thyroid_med_magnesium_separate` | needs_revision | interval_not_supported_by_cited_source |
| `timing_quercetin_vitamin_c_together` | needs_revision | awaiting_clinician_decision |
| `timing_bromelain_timing_by_purpose` | needs_revision | citation_not_content_verified |
| `timing_l_theanine_caffeine_together` | needs_revision | awaiting_clinician_decision |
| `timing_calcium_carbonate_with_food` | needs_revision | canonical_identity_unresolved; catalog_identity_missing_upstream |
| `timing_thyroid_med_soy_separate` | needs_revision | interval_not_supported_by_cited_source; canonical_identity_unresolved |

13 rules.
