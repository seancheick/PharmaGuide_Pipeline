# SupplementEnricherV3 state map (scripts/enrich_supplements_v3.py)

291 methods; 78 instance attributes: init_and_rebuilt 23, load_once 6, never_written_here 28, per_run_mutable 21

| method | line | len | params | self reads | self writes | self calls | module globals |
|---|---|---|---|---|---|---|---|
| _collect_rda_ul_data | 21693 | 2278 | 3 | 5 | 1: _rda_ul_warning_count | 14 | 16 |
| _match_quality_map_impl | 9483 | 1355 | 9 | 4 | 4: _ambiguity_warning_count, _parent_fallback_details, _parent_fallback_info_count, match_counters | 12 | 1 |
| _collect_ingredient_quality_data | 4640 | 940 | 1 | 2 | 0:  | 41 | 0 |
| _collect_probiotic_data | 16382 | 853 | 1 | 3 | 0:  | 8 | 4 |
| _collect_proprietary_data | 14345 | 570 | 1 | 3 | 0:  | 4 | 1 |
| _collect_interaction_profile | 20086 | 531 | 2 | 1 | 0:  | 13 | 0 |
| _collect_evidence_data | 15450 | 416 | 2 | 2 | 0:  | 12 | 0 |
| _build_match_ledger | 24455 | 371 | 2 | 1 | 0:  | 1 | 1 |
| _check_banned_substances | 12142 | 352 | 2 | 1 | 0:  | 10 | 0 |
| _collect_synergy_data | 11715 | 340 | 1 | 1 | 0:  | 5 | 0 |
| enrich_product | 23976 | 313 | 1 | 7 | 3: _product_text_cache, _product_text_cache_enabled, _product_text_lower_cache | 28 | 0 |
| _collect_serving_basis_data | 18260 | 213 | 1 | 0 | 0:  | 7 | 0 |
| _collect_compliance_data | 13114 | 194 | 2 | 1 | 0:  | 3 | 0 |
| _collect_standardized_botanicals | 11154 | 177 | 1 | 1 | 0:  | 8 | 0 |
| _project_scoring_fields | 15188 | 168 | 1 | 0 | 0:  | 0 | 0 |
| _collect_absorption_data | 10957 | 134 | 1 | 1 | 0:  | 3 | 0 |
| _collect_product_scoring_evidence | 17262 | 130 | 1 | 0 | 0:  | 2 | 0 |
| _collect_delivery_data | 10847 | 109 | 1 | 1 | 1: _last_delivery_data | 2 | 1 |
| _collect_certification_data | 13717 | 90 | 1 | 1 | 0:  | 10 | 0 |
| _enrich_display_ingredients | 15947 | 79 | 1 | 0 | 0:  | 0 | 0 |
| _match_quality_map | 9118 | 64 | 10 | 0 | 1: _match_quality_cache | 3 | 0 |
| _collect_manufacturer_cert_signals | 13985 | 64 | 1 | 2 | 0:  | 2 | 0 |
| _collect_nutrition_summary | 18127 | 63 | 1 | 0 | 0:  | 0 | 0 |
| _collect_product_signals | 15129 | 58 | 5 | 0 | 0:  | 2 | 0 |
| _collect_claims_from_rules_db | 13491 | 54 | 2 | 1 | 0:  | 5 | 0 |
| _collect_special_use_flags | 20929 | 53 | 1 | 0 | 0:  | 1 | 1 |
| _collect_organic_data | 11107 | 46 | 2 | 2 | 0:  | 1 | 0 |
| apply_taxonomy_projection | 17562 | 42 | 1 | 0 | 0:  | 3 | 0 |
| _collect_dietary_sensitivity_data | 18084 | 42 | 1 | 0 | 0:  | 4 | 0 |
| _collect_profile_context | 19159 | 37 | 1 | 0 | 0:  | 0 | 0 |
| _collect_contaminant_data | 12060 | 29 | 1 | 0 | 0:  | 4 | 0 |
| _collect_manufacturer_data | 15920 | 26 | 1 | 0 | 0:  | 4 | 0 |
| _collect_bonus_features | 16335 | 19 | 1 | 1 | 0:  | 1 | 0 |
| _collect_clinical_aliases | 2841 | 17 | 1 | 0 | 0:  | 0 | 0 |
| _collect_traceability_data | 14199 | 15 | 1 | 1 | 0:  | 0 | 0 |
| _collect_formulation_data | 11092 | 14 | 1 | 0 | 0:  | 4 | 0 |
| _collect_gmp_data | 14185 | 13 | 1 | 1 | 0:  | 0 | 0 |
| _collect_product_scoring_classification | 17551 | 10 | 1 | 0 | 0:  | 0 | 0 |

## Transitive helper closure per selected method

Peers (prefix `_collect_`): 30 methods reach 240 helpers (14,012 LOC); shared core (helpers reached by ≥3 peers) 62 helpers, 4,134 LOC: _active_ingredient_from_scoring_row, _base_comparison_unit, _brand_family_exact_match, _build_form_info_from_cleaned, _build_quality_parent_context_index, _check_claim_with_validation, _check_top_manufacturer, _collect_claims_from_rules_db, _convert_amount_to_target_unit, _convert_amount_to_target_unit_with_evidence, _convert_mass, _counter_ion_form …

| method | closure methods | closure LOC | exclusive helpers | exclusive LOC | transitive self reads | transitive writes | module globals | most-shared-with (shared helpers) |
|---|---|---|---|---|---|---|---|---|
| enrich_product | 271 | 21,985 | 0 | 0 | 50 | _ambiguity_warning_count, _canonical_identity_databases, _canonical_identity_registry, _canonical_registry_id_cache, _cert_registry_cache | 37 | _collect_ingredient_quality_data (99), apply_taxonomy_projection (44), _collect_product_scoring_evidence (41) |
| _collect_ingredient_quality_data | 98 | 7,704 | 52 | 3,334 | 13 | _ambiguity_warning_count, _canonical_identity_databases, _canonical_identity_registry, _canonical_registry_id_cache, _identity_parent_descendants | 12 | enrich_product (99), apply_taxonomy_projection (37), _collect_product_scoring_evidence (37) |
| _collect_proprietary_data | 36 | 3,834 | 1 | 195 | 9 | _ambiguity_warning_count, _marker_names_cache, _match_quality_cache, _parent_fallback_details, _parent_fallback_info_count | 9 | enrich_product (37), _collect_ingredient_quality_data (35), apply_taxonomy_projection (34) |
| _collect_rda_ul_data | 27 | 3,791 | 13 | 1,022 | 6 | _rda_ul_warning_count | 19 | enrich_product (28), _collect_ingredient_quality_data (8), _collect_evidence_data (7) |
| apply_taxonomy_projection | 43 | 3,449 | 0 | 0 | 8 | _ambiguity_warning_count, _marker_names_cache, _match_quality_cache, _parent_fallback_details, _parent_fallback_info_count | 8 | enrich_product (44), _collect_product_scoring_evidence (41), _collect_ingredient_quality_data (37) |
| _collect_product_scoring_evidence | 40 | 3,241 | 1 | 25 | 8 | _ambiguity_warning_count, _marker_names_cache, _match_quality_cache, _parent_fallback_details, _parent_fallback_info_count | 8 | enrich_product (41), apply_taxonomy_projection (41), _collect_ingredient_quality_data (37) |
| _match_quality_map | 33 | 3,016 | 0 | 0 | 8 | _ambiguity_warning_count, _marker_names_cache, _match_quality_cache, _parent_fallback_details, _parent_fallback_info_count | 8 | enrich_product (34), _collect_ingredient_quality_data (34), _collect_proprietary_data (34) |
| _match_quality_map_impl | 33 | 3,016 | 0 | 0 | 8 | _ambiguity_warning_count, _marker_names_cache, _match_quality_cache, _parent_fallback_details, _parent_fallback_info_count | 8 | enrich_product (34), _collect_ingredient_quality_data (34), _collect_proprietary_data (34) |
| _collect_compliance_data | 39 | 2,069 | 1 | 29 | 7 | _hyphen_space_pattern_cache, _low_precision_token_alias_cache, _product_text_cache, _product_text_lower_cache, _regex_pattern_cache | 1 | enrich_product (40), _collect_contaminant_data (30), _check_banned_substances (18) |
| _collect_formulation_data | 32 | 1,817 | 3 | 563 | 10 | _product_text_cache | 2 | enrich_product (33), _collect_standardized_botanicals (16), _collect_synergy_data (15) |
| _collect_interaction_profile | 29 | 1,603 | 20 | 875 | 6 | _canonical_registry_id_cache | 0 | enrich_product (30), _collect_formulation_data (8), _collect_synergy_data (7) |
| _collect_contaminant_data | 29 | 1,393 | 0 | 0 | 6 | _hyphen_space_pattern_cache, _low_precision_token_alias_cache, _regex_pattern_cache, _safe_token_alias_cache, _short_acronym_alias_cache | 0 | enrich_product (30), _collect_compliance_data (30), _check_banned_substances (18) |
| _collect_probiotic_data | 15 | 1,315 | 6 | 305 | 7 | - | 6 | enrich_product (16), _collect_ingredient_quality_data (3), _collect_rda_ul_data (3) |
| _collect_certification_data | 22 | 1,254 | 8 | 473 | 10 | _cert_registry_cache, _product_text_cache | 1 | enrich_product (23), _collect_compliance_data (10), _collect_formulation_data (10) |
| _collect_evidence_data | 20 | 1,211 | 8 | 301 | 7 | _product_text_cache, _product_text_lower_cache | 2 | enrich_product (21), _collect_formulation_data (8), _collect_standardized_botanicals (8) |
| _collect_synergy_data | 14 | 888 | 0 | 0 | 8 | - | 0 | enrich_product (15), _collect_formulation_data (15), _collect_interaction_profile (7) |
| _check_banned_substances | 17 | 804 | 0 | 0 | 5 | _hyphen_space_pattern_cache, _low_precision_token_alias_cache, _regex_pattern_cache, _safe_token_alias_cache, _short_acronym_alias_cache | 0 | enrich_product (18), _collect_compliance_data (18), _collect_contaminant_data (18) |
| _collect_standardized_botanicals | 15 | 696 | 0 | 0 | 3 | _product_text_cache | 1 | enrich_product (16), _collect_formulation_data (16), _collect_evidence_data (8) |
| _collect_manufacturer_data | 12 | 519 | 4 | 200 | 5 | _product_text_cache, _top_mfr_country_cache | 0 | enrich_product (13), _collect_certification_data (8), _collect_manufacturer_cert_signals (6) |
| _collect_organic_data | 6 | 444 | 0 | 0 | 4 | - | 1 | enrich_product (7), _collect_formulation_data (7), _collect_compliance_data (6) |
| _collect_dietary_sensitivity_data | 12 | 409 | 8 | 338 | 6 | - | 0 | enrich_product (13), _collect_formulation_data (4), _collect_interaction_profile (4) |
| _collect_serving_basis_data | 7 | 406 | 4 | 161 | 1 | - | 0 | enrich_product (8), _collect_probiotic_data (2), _collect_delivery_data (1) |
| _collect_claims_from_rules_db | 5 | 398 | 0 | 0 | 2 | - | 1 | enrich_product (6), _collect_compliance_data (6), _collect_formulation_data (6) |
| _build_match_ledger | 1 | 388 | 0 | 0 | 1 | - | 1 | enrich_product (2), _collect_ingredient_quality_data (1), _collect_proprietary_data (1) |
| _collect_absorption_data | 7 | 377 | 0 | 0 | 2 | - | 0 | enrich_product (8), _collect_formulation_data (7), _collect_standardized_botanicals (7) |
| _collect_manufacturer_cert_signals | 6 | 289 | 0 | 0 | 4 | - | 0 | enrich_product (7), _collect_certification_data (7), _collect_manufacturer_data (6) |
| _project_scoring_fields | 0 | 168 | 0 | 0 | 0 | - | 0 | enrich_product (1) |
| _collect_delivery_data | 2 | 161 | 0 | 0 | 1 | _last_delivery_data | 1 | enrich_product (3), _collect_ingredient_quality_data (1), _collect_rda_ul_data (1) |
| _collect_product_signals | 3 | 142 | 1 | 16 | 0 | _product_text_cache | 0 | enrich_product (4), _collect_ingredient_quality_data (2), _collect_compliance_data (2) |
| _collect_bonus_features | 2 | 87 | 0 | 0 | 1 | _product_text_cache | 0 | enrich_product (3), _collect_manufacturer_data (3), _collect_ingredient_quality_data (2) |
| _enrich_display_ingredients | 0 | 79 | 0 | 0 | 0 | - | 0 | enrich_product (1) |
| _collect_special_use_flags | 1 | 70 | 0 | 0 | 0 | - | 1 | enrich_product (2), _collect_rda_ul_data (2), _collect_ingredient_quality_data (1) |
| _collect_nutrition_summary | 0 | 63 | 0 | 0 | 0 | - | 0 | enrich_product (1) |
| _collect_profile_context | 0 | 37 | 0 | 0 | 0 | - | 0 | enrich_product (1), _collect_interaction_profile (1) |
| _collect_clinical_aliases | 0 | 17 | 0 | 0 | 0 | - | 0 | enrich_product (1), _collect_evidence_data (1) |
| _collect_traceability_data | 0 | 15 | 0 | 0 | 1 | - | 0 | enrich_product (1), _collect_certification_data (1) |
| _collect_gmp_data | 0 | 13 | 0 | 0 | 1 | - | 0 | enrich_product (1), _collect_certification_data (1) |
| _collect_product_scoring_classification | 0 | 10 | 0 | 0 | 0 | - | 0 | enrich_product (1), apply_taxonomy_projection (1) |

## Per-run mutable attributes (written outside __init__)

| attribute | written in | read in (methods) |
|---|---|---|
| _product_text_cache | __init__, _get_all_product_text, enrich_product | 0 |
| _product_text_lower_cache | __init__, _get_all_product_text_lower, enrich_product | 0 |
| _ambiguity_warning_count | __init__, _match_quality_map_impl | 0 |
| _form_fallback_details | __init__, _record_form_curation_gaps | 2 |
| _hyphen_space_pattern_cache | __init__, _hyphen_space_token_pattern | 0 |
| _iqm_exact_index | __init__, _build_performance_indexes | 2 |
| _iqm_norm_index | __init__, _build_performance_indexes | 2 |
| _low_precision_token_alias_cache | __init__, _is_low_precision_token_alias | 0 |
| _match_quality_cache | __init__, _match_quality_map | 0 |
| _nonscorable_index | __init__, _build_performance_indexes | 2 |
| _nonscorable_unii_index | __init__, _build_performance_indexes | 1 |
| _parent_fallback_details | __init__, _match_quality_map_impl | 1 |
| _parent_fallback_info_count | __init__, _match_quality_map_impl | 0 |
| _product_text_cache_enabled | __init__, enrich_product | 0 |
| _quality_parent_context_index_cache | __init__, _infer_preferred_parent_from_context_cached | 0 |
| _rda_ul_warning_count | __init__, _collect_rda_ul_data | 0 |
| _regex_pattern_cache | __init__, _cached_compile_regex | 0 |
| _safe_token_alias_cache | __init__, _filter_safe_token_aliases | 0 |
| _short_acronym_alias_cache | __init__, _is_short_acronym_alias | 0 |
| _token_bounded_pattern_cache | __init__, _cached_token_bounded_pattern | 0 |
| databases | __init__, _load_all_databases | 57 |
| match_counters | __init__, _match_quality_map_impl | 1 |
| unmapped_tracker | __init__, _track_unmapped | 1 |
| _botanical_source_identities | _build_performance_indexes | 1 |
| _canonical_identity_databases | _current_canonical_identity_registry | 0 |
| _canonical_identity_registry | _current_canonical_identity_registry | 0 |
| _canonical_registry_id_cache | _canonical_registry_ids | 0 |
| _cert_registry_cache | _resolve_verified_cert_programs | 0 |
| _clinical_study_index_source | _build_performance_indexes | 1 |
| _clinical_study_key_index | _build_performance_indexes | 1 |
| _clinical_study_norm_index | _build_performance_indexes | 1 |
| _identity_parent_descendants | _identity_parent_predicate | 0 |
| _identity_parent_quality_map | _identity_parent_predicate | 0 |
| _identity_parent_relationship_document | _identity_parent_predicate | 0 |
| _last_delivery_data | _collect_delivery_data | 0 |
| _marker_names_cache | _standardization_marker_names | 0 |
| _standardized_botanical_iqm_parents | _build_performance_indexes | 1 |
| _top_mfr_country_cache | _top_manufacturer_country | 0 |
| blend_detector | _init_scoring_modules | 1 |
| compiled_patterns | _compile_patterns | 9 |
| dosage_normalizer | _init_scoring_modules | 1 |
| rda_calculator | _init_scoring_modules | 3 |
| reference_versions | _log_reference_versions | 4 |
| unit_converter | _init_scoring_modules | 3 |
