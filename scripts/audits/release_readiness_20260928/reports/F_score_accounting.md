# F. Score accounting — every magnitude in `scripts/scoring_v4/config/quality_score.json` (HEAD 391b87c5)

Config `_metadata`: {"version": "1.21.3-omega-transparency-owner", "schema_version": "1.0.0", "last_updated": "2026-09-26"}. Reachability column: count of sample products (HEAD replay, 127 scored) whose module dimensions carry a non-zero value for the component/penalty of that name (`head_component_census.json`); '—' = not a per-product component (a cap, reference, threshold or table).


## pillars (6 numeric entries)

| key | value | reached on sample |
|---|---|---|
| `formulation.weight` | 20 | — |
| `dose.weight` | 20 | — |
| `evidence.weight` | 20 | — |
| `transparency.weight` | 15 | — |
| `verification.weight` | 15 | — |
| `safety_hygiene.weight` | 10 | — |

## safety_hygiene_subscale (3 numeric entries)

| key | value | reached on sample |
|---|---|---|
| `base_max` | 10.0 | — |
| `additive_or_sweetener_max_penalty` | 4.0 | — |
| `over_ul_max_penalty` | 3.0 | — |

## clean_label_subscale (8 numeric entries)

| key | value | reached on sample |
|---|---|---|
| `role_multiplier.active` | 1.5 | — |
| `role_multiplier.major` | 1.5 | — |
| `role_multiplier.claim_prominent` | 1.0 | — |
| `role_multiplier.adjunct` | 0.5 | — |
| `role_multiplier.inactive` | 0.5 | — |
| `tier_base.elevated` | 2.0 | — |
| `tier_base.informational` | 0.5 | — |
| `max_total_penalty` | 5.0 | — |

## evidence_subscale (13 numeric entries)

| key | value | reached on sample |
|---|---|---|
| `archetype_reference.sports_single` | 18.0 | — |
| `archetype_reference.sports_pre_workout` | 18.0 | — |
| `archetype_reference.sports_protein` | 18.0 | — |
| `archetype_reference.sports_bcaa_eaa` | 18.0 | — |
| `archetype_reference.generic_single_molecule` | 18.0 | — |
| `archetype_reference.generic_botanical_branded` | 18.0 | — |
| `archetype_reference.immune_support` | 17.0 | — |
| `archetype_reference.fiber_digestive` | 18.0 | — |
| `archetype_reference.b_complex` | 20.0 | — |
| `archetype_reference.omega` | 20.0 | — |
| `archetype_reference.probiotic` | 20.0 | — |
| `archetype_reference.prenatal_multi` | 20.0 | — |
| `default_reference` | 20.0 | — |

## dose_subscale (13 numeric entries)

| key | value | reached on sample |
|---|---|---|
| `archetype_reference.sports_single` | 25.0 | — |
| `archetype_reference.sports_pre_workout` | 25.0 | — |
| `archetype_reference.sports_protein` | 25.0 | — |
| `archetype_reference.sports_bcaa_eaa` | 25.0 | — |
| `archetype_reference.generic_single_molecule` | 22.0 | — |
| `archetype_reference.generic_botanical_branded` | 21.0 | — |
| `archetype_reference.immune_support` | 22.0 | — |
| `archetype_reference.fiber_digestive` | 25.0 | — |
| `archetype_reference.b_complex` | 25.0 | — |
| `archetype_reference.omega` | 20.0 | — |
| `archetype_reference.probiotic` | 22.0 | — |
| `archetype_reference.prenatal_multi` | 23.0 | — |
| `default_reference` | 22.0 | — |

## formulation_subscale (16 numeric entries)

| key | value | reached on sample |
|---|---|---|
| `profile_reference.generic_iqm` | 15.0 | — |
| `profile_reference.botanical` | 15.0 | — |
| `profile_reference.collagen` | 15.0 | — |
| `archetype_reference.sports_single` | 24.0 | — |
| `archetype_reference.sports_pre_workout` | 30.0 | — |
| `archetype_reference.sports_protein` | 29.0 | — |
| `archetype_reference.sports_bcaa_eaa` | 25.0 | — |
| `archetype_reference.generic_single_molecule` | 24.0 | — |
| `archetype_reference.generic_botanical_branded` | 24.0 | — |
| `archetype_reference.immune_support` | 30.0 | — |
| `archetype_reference.fiber_digestive` | 28.0 | — |
| `archetype_reference.b_complex` | 23.0 | — |
| `archetype_reference.omega` | 12.0 | — |
| `archetype_reference.probiotic` | 15.0 | — |
| `archetype_reference.prenatal_multi` | 14.0 | — |
| `default_reference` | 25.0 | — |

## formulation_penalties (6 numeric entries)

| key | value | reached on sample |
|---|---|---|
| `b1_harmful_additive_points.critical` | 4.0 | — |
| `b1_harmful_additive_points.high` | 3.0 | — |
| `b1_harmful_additive_points.moderate` | 2.0 | — |
| `b1_harmful_additive_points.low` | 0.5 | — |
| `b1_harmful_additive_points.none` | 0.0 | — |
| `b1_harmful_additive_cap` | 15.0 | — |

## formulation_magnitudes (19 numeric entries)

| key | value | reached on sample |
|---|---|---|
| `dimension_cap` | 30.0 | — |
| `presence_floor` | 2.0 | — |
| `a1_bio_score_cap` | 15.0 | — |
| `a3_delivery_cap` | 3.0 | — |
| `a3_delivery_tier_points.1` | 3.0 | — |
| `a3_delivery_tier_points.2` | 2.0 | — |
| `a3_delivery_tier_points.3` | 1.0 | — |
| `a4_absorption_cap` | 3.0 | — |
| `a5b_standardized_full` | 1.0 | — |
| `a5b_standardized_marker_only` | 0.5 | — |
| `b0_high_risk_penalty` | 10.0 | — |
| `b0_watchlist_penalty` | 5.0 | — |
| `b0_moderate_penalty` | 10.0 | — |
| `dietary_sugar_low_added_penalty` | 1.0 | — |
| `dietary_sugar_sugar_alcohol_penalty` | 1.0 | — |
| `dietary_sugar_high_glycemic_or_syrup_penalty` | 2.0 | — |
| `dietary_sugar_moderate_penalty` | 3.0 | — |
| `dietary_sugar_high_penalty` | 4.0 | — |
| `dietary_sugar_cap` | 4.0 | — |

## dose_safety_policy (3 numeric entries)

| key | value | reached on sample |
|---|---|---|
| `ul_pct_threshold` | 150.0 | — |
| `per_flag_penalty` | 2.0 | — |
| `cap` | 3.0 | — |

## dose_magnitudes (38 numeric entries)

| key | value | reached on sample |
|---|---|---|
| `generic.cap_supplemental_window` | 22.0 | — |
| `generic.dimension_cap` | 25.0 | — |
| `generic.window_rda_threshold` | 25.0 | — |
| `generic.window_ul_partial_band` | 100.0 | — |
| `generic.window_overdose_credit` | 11.0 | — |
| `generic.window_high_source_pct` | 20.0 | — |
| `generic.window_full_adequacy_pct` | 100.0 | — |
| `generic.no_reference_individual_dose_credit` | 16.0 | — |
| `generic.no_reference_product_evidence_credit` | 12.0 | — |
| `multi_prenatal.dimension_cap` | 25.0 | — |
| `multi_prenatal.cap_rda_ai_coverage` | 15.0 | — |
| `multi_prenatal.cap_panel_breadth` | 3.0 | — |
| `multi_prenatal.cap_critical_nutrient_coverage` | 5.0 | — |
| `multi_prenatal.cap_prenatal_complement_support` | 2.0 | — |
| `multi_prenatal.panel_breadth_full_count` | 18 | — |
| `multi_prenatal.prenatal_dha_full_mg` | 200.0 | — |
| `multi_prenatal.prenatal_dha_partial_mg` | 100.0 | — |
| `multi_prenatal.targeted_multi_selected_anchors` | 5 | — |
| `multi_prenatal.critical_min_pct_rda.folate` | 50.0 | — |
| `multi_prenatal.critical_min_pct_rda.iron` | 50.0 | — |
| `multi_prenatal.critical_min_pct_rda.iodine` | 50.0 | — |
| `multi_prenatal.critical_min_pct_rda.vitamin_d` | 50.0 | — |
| `multi_prenatal.critical_min_pct_rda.vitamin_b12` | 50.0 | — |
| `multi_prenatal.critical_min_pct_rda.choline` | 25.0 | — |
| `probiotic.cap_dose` | 25.0 | — |
| `probiotic.cap_per_strain_cfu_disclosure` | 10.0 | — |
| `probiotic.cap_cfu_adequacy` | 15.0 | — |
| `probiotic.aggregate_cfu_low_tier_presence_floor` | 2.0 | — |
| `probiotic.aggregate_cfu_low_named_strain_total_floor` | 4.0 | — |
| `probiotic.cap_direct_strain_mass_floor` | 5.0 | — |
| `probiotic.v3_cfu_adequacy_cap` | 5.0 | — |
| `probiotic.tier_points.low` | 0.0 | — |
| `probiotic.tier_points.adequate` | 1.0 | — |
| `probiotic.tier_points.good` | 2.0 | — |
| `probiotic.tier_points.excellent` | 3.0 | — |
| `omega.cap_dose` | 25.0 | — |
| `sports.dimension_cap` | 25.0 | — |
| `fiber_digestive.dimension_cap` | 25.0 | — |

## evidence_magnitudes (48 numeric entries)

| key | value | reached on sample |
|---|---|---|
| `generic.cap_total` | 20.0 | — |
| `generic.cap_per_ingredient` | 7.0 | — |
| `generic.supra_clinical_multiple` | 3.0 | — |
| `generic.enrollment_default_multiplier` | 1.2 | — |
| `generic.primary_floor_strong` | 14.0 | — |
| `generic.primary_floor_moderate` | 11.0 | — |
| `generic.primary_floor_branded_strong` | 18.0 | — |
| `generic.primary_floor_branded_moderate` | 17.0 | — |
| `generic.nutrition_authority_floor` | 10.0 | — |
| `generic.primary_mass_fraction` | 0.5 | — |
| `generic.effect_direction_multipliers.positive_strong` | 1.0 | — |
| `generic.effect_direction_multipliers.positive_weak` | 0.85 | — |
| `generic.effect_direction_multipliers.mixed` | 0.6 | — |
| `generic.effect_direction_multipliers.null` | 0.0 | — |
| `generic.effect_direction_multipliers.negative` | 0.0 | — |
| `generic.top_n_weights` | [1.0, 0.7, 0.5, 0.3] | — |
| `probiotic.cap_evidence` | 20.0 | — |
| `probiotic.cap_strain_clinical` | 12.0 | — |
| `probiotic.cap_dose_applicability` | 8.0 | — |
| `probiotic.effect_direction_multipliers.positive_strong` | 1.0 | — |
| `probiotic.effect_direction_multipliers.positive_weak` | 0.85 | — |
| `probiotic.effect_direction_multipliers.mixed` | 0.6 | — |
| `probiotic.effect_direction_multipliers.null` | 0.0 | — |
| `probiotic.effect_direction_multipliers.negative` | 0.0 | — |
| `probiotic.native_strain_evidence_points.strong` | 12.0 | — |
| `probiotic.native_strain_evidence_points.high` | 12.0 | — |
| `probiotic.native_strain_evidence_points.moderate` | 9.0 | — |
| `probiotic.native_strain_evidence_points.medium` | 9.0 | — |
| `probiotic.native_strain_evidence_points.weak` | 4.5 | — |
| `probiotic.native_strain_evidence_points.low` | 4.5 | — |
| `probiotic.native_strain_evidence_points.limited` | 4.5 | — |
| `probiotic.native_strain_evidence_weights` | [1.0] | — |
| `probiotic.dose_applicability_policy.credit.EXACT_TESTED_DOSE` | 1.0 | — |
| `probiotic.dose_applicability_policy.credit.WITHIN_TESTED_RANGE` | 0.0 | — |
| `probiotic.dose_applicability_policy.credit.NEAR_TESTED_RANGE` | 0.0 | — |
| `probiotic.dose_applicability_policy.credit.OUTSIDE_TESTED_RANGE` | 0.0 | — |
| `probiotic.dose_applicability_policy.credit.DOSE_UNKNOWN` | 0.0 | — |
| `multi_prenatal.cap_evidence` | 20.0 | — |
| `multi_prenatal.generic_cap_evidence` | 20.0 | — |
| `omega.cap_evidence` | 20.0 | — |
| `omega.purpose_standards.omega_reviewed_weak.pillar_score` | 10.4 | — |
| `omega.purpose_standards.omega_reviewed_weak.minimum_daily_epa_dha_mg` | 376 | — |
| `omega.purpose_standards.triglyceride_strong.pillar_score` | 20.0 | — |
| `omega.purpose_standards.triglyceride_strong.minimum_daily_epa_dha_mg` | 2000 | — |
| `omega.purpose_standards.triglyceride_strong.graduated_from_daily_epa_dha_mg` | 1000 | — |
| `omega.purpose_standards.prenatal_dha_intake_authority.pillar_score` | 11.1 | — |
| `omega.purpose_standards.prenatal_dha_intake_authority.minimum_daily_dha_mg` | 200 | — |
| `omega.purpose_standards.high_dose_atrial_fibrillation_context.minimum_daily_epa_dha_mg` | 1000 | — |

## verification_magnitudes (29 numeric entries)

| key | value | reached on sample |
|---|---|---|
| `generic_trust.dimension_cap` | 15.0 | — |
| `generic_trust.b4a_cap` | 12.0 | — |
| `generic_trust.b4a_scope_points.sku` | [8.0, 4.0, 2.0] | — |
| `generic_trust.b4a_scope_points.product_line` | [6.0, 3.0, 1.0] | — |
| `generic_trust.b4a_scope_points.label_asserted_product` | [2.0, 1.0, 0.0] | — |
| `generic_trust.b4a_scope_points.brand_only` | [0.0, 0.0, 0.0] | — |
| `generic_trust.b4a_scope_points.needs_review` | [0.0, 0.0, 0.0] | — |
| `generic_trust.b4a_scope_points.claimed_only` | [0.0, 0.0, 0.0] | — |
| `generic_trust.b4a_scope_strength.sku` | 3 | — |
| `generic_trust.b4a_scope_strength.product_line` | 2 | — |
| `generic_trust.b4a_scope_strength.label_asserted_product` | 1 | — |
| `generic_trust.b4b_gmp_certified` | 4.0 | — |
| `generic_trust.b4c_coa` | 1.0 | — |
| `generic_trust.b4c_batch_lookup` | 1.0 | — |
| `manufacturer.manufacturer_trust_cap` | 5.0 | — |
| `manufacturer.d1_trusted` | 2.0 | — |
| `manufacturer.d1_mid_tier` | 1.0 | — |
| `manufacturer.d2_disclosure` | 1.0 | — |
| `manufacturer.d3_physician` | 0.5 | — |
| `manufacturer.d4_high_standard_region` | 1.0 | — |
| `manufacturer.d5_sustainability` | 0.5 | — |
| `manufacturer.d3_d4_d5_cap` | 2.0 | — |
| `manufacturer.mfg_cap_default` | -25.0 | — |
| `manufacturer.mfg_cap_two_class_i` | -35.0 | — |
| `manufacturer.mfg_cap_three_or_more_class_i` | -50.0 | — |
| `brand_testing.hard_evidence_score` | 2.0 | — |
| `brand_testing.soft_quality_score` | 1.0 | — |
| `verification_bonus.cap` | 8.0 | — |
| `omega_trust.cap_trust` | 15.0 | — |

## transparency_magnitudes (36 numeric entries)

| key | value | reached on sample |
|---|---|---|
| `generic.dimension_cap` | 10.0 | — |
| `generic.clear_disclosure_base` | 6.0 | 97 |
| `generic.complete_active_disclosure_bonus` | 4.0 | — |
| `generic.b2_cap` | 2.0 | — |
| `generic.b2_severity_points.high` | 2.0 | — |
| `generic.b2_severity_points.moderate` | 1.5 | — |
| `generic.b2_severity_points.low` | 1.0 | — |
| `generic.b3_cap` | 0.0 | — |
| `generic.b3_allergen_free` | 0.0 | — |
| `generic.b3_gluten_free` | 0.0 | — |
| `generic.b3_vegan_or_vegetarian` | 0.0 | — |
| `generic.b5_base.full` | 0.0 | — |
| `generic.b5_base.partial` | 1.0 | — |
| `generic.b5_base.none` | 2.0 | — |
| `generic.b5_prop_coef.full` | 0.0 | — |
| `generic.b5_prop_coef.partial` | 3.0 | — |
| `generic.b5_prop_coef.none` | 5.0 | — |
| `generic.b5_cap` | 10.0 | — |
| `generic.b5_count_denom_min` | 8 | — |
| `generic.b5_class_multipliers.probiotic` | 0.4 | — |
| `generic.b5_class_multipliers.multi_or_prenatal` | 1.3 | — |
| `generic.b5_class_multipliers.sports_active` | 1.5 | — |
| `generic.b5_class_multipliers.generic` | 1.0 | — |
| `generic.b5_trivial_micro_blend_hidden_mass_mg` | 1.0 | — |
| `generic.b5_trivial_micro_blend_max_impact` | 0.01 | — |
| `generic.b6_disease_claim_penalty` | 5.0 | — |
| `multi_prenatal.dimension_cap` | 15.0 | — |
| `multi_prenatal.cap_panel_identity_disclosure` | 5.0 | — |
| `multi_prenatal.cap_panel_individual_dose_disclosure` | 10.0 | — |
| `multi_prenatal.adjunct_blend_panel_disclosure_threshold` | 0.9 | — |
| `multi_prenatal.adjunct_blend_b5_cap` | 2.0 | — |
| `probiotic.dimension_cap` | 15.0 | — |
| `probiotic.cap_strain_identities` | 8.0 | — |
| `probiotic.cap_per_strain_cfu` | 7.0 | — |
| `probiotic.cap_aggregate_cfu_disclosure_proxy` | 4.0 | — |
| `omega.cap_transparency` | 11.0 | — |

## formulation_variant_magnitudes (27 numeric entries)

| key | value | reached on sample |
|---|---|---|
| `multi_prenatal.cap_formulation` | 14.0 | — |
| `multi_prenatal.formulation_presence_floor` | 2.0 | — |
| `multi_prenatal.cap_panel_form_quality` | 12.0 | — |
| `multi_prenatal.cap_panel_disclosure_structure` | 2.0 | — |
| `multi_prenatal.panel_form_neutral_floor` | 9.0 | — |
| `multi_prenatal.bio_score_max` | 15.0 | — |
| `omega.cap_formulation` | 25.0 | — |
| `probiotic.cap_formulation` | 15.0 | — |
| `probiotic.cap_total_potency_disclosure` | 4.0 | — |
| `probiotic.cap_exact_identity_completeness` | 8.0 | — |
| `probiotic.cap_delivery_survivability` | 3.0 | — |
| `sports.dimension_cap` | 30.0 | — |
| `fiber_digestive.dimension_cap` | 30.0 | — |
| `botanical.botanical_formulation_cap` | 15.0 | — |
| `botanical.standardization_tier_full` | 4.0 | — |
| `botanical.standardization_tier_near` | 3.0 | — |
| `botanical.standardization_tier_half` | 2.0 | — |
| `botanical.standardization_tier_disclosed` | 1.0 | — |
| `botanical.botanical_dose_within` | 21.0 | — |
| `botanical.botanical_dose_near` | 16.0 | — |
| `botanical.botanical_dose_above` | 12.0 | — |
| `botanical.botanical_dose_below` | 12.0 | — |
| `botanical.botanical_dose_disclosed_no_ref` | 12.0 | — |
| `botanical.botanical_dose_blend_total` | 10.0 | — |
| `botanical.botanical_dose_primary_no_dose` | 5.0 | — |
| `botanical.botanical_dose_no_active` | 0.0 | — |
| `collagen.collagen_formulation_cap` | 15.0 | — |

## category_magnitudes (45 numeric entries)

| key | value | reached on sample |
|---|---|---|
| `generic.manufacturer_trust_cap` | 5 | — |
| `generic.manufacturer_violations_floor` | -25 | — |
| `generic.botanical_raw_floor` | 40.0 | — |
| `b_complex.formulation_cap` | 23.0 | — |
| `b_complex.dose_cap` | 25.0 | — |
| `b_complex.evidence_cap` | 20.0 | — |
| `immune_support.evidence_cap` | 17.0 | — |
| `immune_support.high_variability_botanical_stack_min_count` | 3 | — |
| `immune_support.high_variability_botanical_stack_penalty` | 3.0 | — |
| `immune_support.dose_cap` | 22.0 | — |
| `immune_support.dose_bands.vitamin_c_mg.low` | 100.0 | — |
| `immune_support.dose_bands.vitamin_c_mg.high` | 1000.0 | — |
| `immune_support.dose_bands.vitamin_c_mg.points` | 3.0 | — |
| `immune_support.dose_bands.vitamin_d_mcg.low` | 15.0 | — |
| `immune_support.dose_bands.vitamin_d_mcg.high` | 50.0 | — |
| `immune_support.dose_bands.vitamin_d_mcg.points` | 3.0 | — |
| `immune_support.dose_bands.zinc_mg.low` | 8.0 | — |
| `immune_support.dose_bands.zinc_mg.high` | 25.0 | — |
| `immune_support.dose_bands.zinc_mg.points` | 3.0 | — |
| `immune_support.dose_bands.copper_mg.low` | 0.5 | — |
| `immune_support.dose_bands.copper_mg.high` | 2.0 | — |
| `immune_support.dose_bands.copper_mg.points` | 1.5 | — |
| `immune_support.dose_bands.selenium_mcg.low` | 45.0 | — |
| `immune_support.dose_bands.selenium_mcg.high` | 200.0 | — |
| `immune_support.dose_bands.selenium_mcg.points` | 1.5 | — |
| `immune_support.dose_bands.beta_glucan_mg.low` | 100.0 | — |
| `immune_support.dose_bands.beta_glucan_mg.high` | 250.0 | — |
| `immune_support.dose_bands.beta_glucan_mg.points` | 3.0 | — |
| `immune_support.dose_bands.quercetin_mg.low` | 250.0 | — |
| `immune_support.dose_bands.quercetin_mg.high` | 1000.0 | — |
| `immune_support.dose_bands.quercetin_mg.points` | 2.5 | — |
| `immune_support.dose_bands.elderberry_mg.low` | 100.0 | — |
| `immune_support.dose_bands.elderberry_mg.high` | 600.0 | — |
| `immune_support.dose_bands.elderberry_mg.points` | 2.5 | — |
| `immune_support.dose_above_band_fraction` | 0.5 | — |
| `immune_support.daily_use_discipline_points` | 2.0 | — |
| `immune_support.high_zinc_threshold_mg` | 40.0 | — |
| `immune_support.high_vitamin_d_threshold_mcg` | 100.0 | — |
| `joint_support.evidence_cap` | 14.0 | — |
| `joint_support.target_dose_mg.glucosamine` | 1500.0 | — |
| `joint_support.target_dose_mg.chondroitin` | 1200.0 | — |
| `joint_support.target_dose_mg.msm` | 1500.0 | — |
| `joint_support.target_dose_mg.uc_ii` | 40.0 | — |
| `joint_support.target_dose_mg.hyaluronic_acid` | 120.0 | — |
| `safety_hygiene.cap` | 4.0 | — |

## verification_subscale (12 numeric entries)

| key | value | reached on sample |
|---|---|---|
| `cap` | 15.0 | — |
| `neutral_baseline` | 6.0 | — |
| `reputation_cap` | 2.0 | — |
| `tier_ceilings.claim_or_brand` | 8.0 | — |
| `tier_ceilings.manufacturing` | 10.0 | — |
| `product_level_floor` | 11.0 | — |
| `cert_tiers` | [{"min_b4a": 10.0, "points": 12.0}, {"min_b4a": 6.0, "points": 9.0}, {"min_b4a": 1.0, "points": 5.0}] | — |
| `coa_batch_max` | 5.0 | — |
| `gmp_certified_points` | 2.0 | — |
| `brand_testing_points` | 2.0 | — |
| `brand_only_cert_points` | 2.0 | — |
| `label_asserted_cert_points` | 2.0 | — |

## tiers (1 numeric entries)

| key | value | reached on sample |
|---|---|---|
| `` | [{"min": 95.0, "name": "Exceptional"}, {"min": 90.0, "name": "Excellent"}, {"min": 80.0, "name": "Very good"}, {"min": 70.0, "name": "Good"}, {"min": 55.0, "nam | — |

## suppression (0 numeric entries)

| key | value | reached on sample |
|---|---|---|

## Window changes to this file (7b031050 → HEAD): 78 changed value lines; version 1.21.3-omega-transparency-owner

```diff
-      "b_complex": 14.0,
+      "b_complex": 20.0,
-      "prenatal_multi": 18.0
+      "prenatal_multi": 20.0
-      "probiotic": 16.0,
+      "probiotic": 15.0,
-      "cap_multi_form_bonus": 3.0,
-      "multi_form_premium_bio_threshold": 12.0,
-      "multi_form_min_group_count": 2,
-      "native_strain_evidence_points": { "strong": 8.0, "high": 8.0, "moderate": 6.0, "medium": 6.0, "weak": 3.0, "low": 3.0, "limited": 3.0 },
-      "native_strain_evidence_weights": [1.0, 0.7, 0.5, 0.3],
+      "native_strain_evidence_points": { "strong": 12.0, "high": 12.0, "moderate": 9.0, "medium": 9.0, "weak": 4.5, "low": 4.5, "limited": 4.5 },
+      "native_strain_evidence_weights": [1.0],
-    "omega": { "cap_evidence": 20.0 }
+    "omega": {
+      "cap_evidence": 20.0,
+      "purpose_standards": {
+        "omega_reviewed_weak": {
+          "pillar_score": 10.4,
+          "minimum_daily_epa_dha_mg": 376
+        "triglyceride_strong": {
+          "pillar_score": 20.0,
+          "minimum_daily_epa_dha_mg": 2000,
+          "graduated_from_daily_epa_dha_mg": 1000
+        "prenatal_dha_intake_authority": {
+          "pillar_score": 11.1,
+          "minimum_daily_dha_mg": 200
+        "prenatal_preterm_birth_outcome": {
+          "score_eligible": false
+        "epa_predominant_depression": {
+          "score_eligible": false
+        "high_dose_atrial_fibrillation_context": {
+          "minimum_daily_epa_dha_mg": 1000,
+          "score_eligible": false
-      "complete_active_disclosure_bonus": 3.0,
+      "complete_active_disclosure_bonus": 4.0,
-      "b3_cap": 4.0,
-      "b3_allergen_free": 2.0,
-      "b3_gluten_free": 1.0,
-      "b3_vegan_or_vegetarian": 1.0,
+      "b3_cap": 0.0,
+      "b3_allergen_free": 0.0,
+      "b3_gluten_free": 0.0,
+      "b3_vegan_or_vegetarian": 0.0,
-      "cap_panel_identity_disclosure": 4.0,
-      "cap_panel_individual_dose_disclosure": 7.0,
+      "cap_panel_identity_disclosure": 5.0,
+      "cap_panel_individual_dose_disclosure": 10.0,
-    "omega": { "cap_transparency": 13.0 }
+    "omega": { "cap_transparency": 11.0 }
-      "cap_formulation": 16.0,
+      "cap_formulation": 15.0,
-      "cap_delivery_survivability": 3.0,
-      "cap_prebiotic_complement": 1.0
+      "cap_delivery_survivability": 3.0
-    "omega": { "dimension_caps": [["formulation", 25], ["dose", 25], ["evidence", 20], ["transparency", 13]] },
-    "probiotic": { "dimension_caps": [["formulation", 16], ["dose", 25], ["evidence", 20], ["transparency", 15]] },
+    "omega": { "dimension_caps": [["formulation", 25], ["dose", 25], ["evidence", 20], ["transparency", 11]] },
+    "probiotic": { "dimension_caps": [["formulation", 15], ["dose", 25], ["evidence", 20], ["transparency", 15]] },
-    "immune_support": { "evidence_cap": 17.0 },
+    "immune_support": {
+      "evidence_cap": 17.0,
+      "high_variability_botanical_stack_min_count": 3,
+      "high_variability_botanical_stack_penalty": 3.0,
+      "dose_cap": 22.0,
+      "dose_bands": {
+        "vitamin_c_mg": { "low": 100.0, "high": 1000.0, "points": 3.0 },
+        "vitamin_d_mcg": { "low": 15.0, "high": 50.0, "points": 3.0 },
+        "zinc_mg": { "low": 8.0, "high": 25.0, "points": 3.0 },
+        "copper_mg": { "low": 0.5, "high": 2.0, "points": 1.5 },
+        "selenium_mcg": { "low": 45.0, "high": 200.0, "points": 1.5 },
+        "beta_glucan_mg": { "low": 100.0, "high": 250.0, "points": 3.0 },
+        "quercetin_mg": { "low": 250.0, "high": 1000.0, "points": 2.5 },
+        "elderberry_mg": { "low": 100.0, "high": 600.0, "points": 2.5 }
+      "dose_above_band_fraction": 0.5,
+      "daily_use_discipline_points": 2.0,
+      "high_zinc_threshold_mg": 40.0,
+      "high_vitamin_d_threshold_mcg": 100.0
```


## Normalization and denominators (from `quality_score.py` and the replay records)
- Public pillar = raw dimension score × pillar weight ÷ `normalization_references[route][dimension]` (archetype reference), capped at the weight. The reference is distinct from the module cap; e.g. probiotic dose raw 20 / ref 22 → 18.2; omega transparency native cap 13 mapped to 15/15; generic evidence reference 18.
- Per-route references seen on the sample (`pillars.*.components.reference`): generic formulation 15, dose 25, evidence 18; sports_single dose 25, evidence 18; omega dose 20, transparency 13; probiotic dose 22, formulation 15; b_complex evidence 20; prenatal evidence 20.
- Facts reaching more than one pillar (answer to §13): (1) a core nutrient's *presence with identity* → Transparency `panel_identity_disclosure` + Evidence `essential_panel_authority` + Dose `panel_breadth`/`critical_nutrient_coverage` (multi/prenatal, B-complex); (2) a row's *form* → Formulation A1 (parent-relative) and Dose eligibility/adequacy via the form's conversion (non-delivering forms 372be31d) and Evidence applicability (form exclusions); (3) *dose disclosure* → Transparency `complete_active_identity_dose_disclosure` + Dose adequacy input (one owner `dose_disclosure_status`, two consumers, by design); (4) *UL excess* → Dose `B7_dose_safety` penalty + Safety/Hygiene + the CAUTION verdict (three surfaces, one fact: `dose_safety_evaluation` owner; the quality/safety double deduction is the D12 open policy); (5) *harmful additives* → Formulation `B1_harmful_additives` + Safety/Hygiene `additive_or_sweetener_penalty` (two pillars, one fact: D12 lists this as an open policy, "product-level penalties at equal public points in every rubric"); (6) *proprietary blend opacity* → Transparency B5 + Dose (undisclosed amounts earn no adequacy) — one fact, two pillars, arguably legitimate (disclosure vs adequacy); (7) *certification* → Verification only (attribution-based); no stacking found on the sample; NSF Certified + NSF Sport stacking on 28 corpus products deferred by 2da82226.
