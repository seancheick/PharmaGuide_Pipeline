# EnhancedDSLDNormalizer state map (scripts/enhanced_normalizer.py)

157 methods; 78 instance attributes: init_and_rebuilt 10, load_once 41, never_written_here 7, per_run_mutable 20

| method | line | len | params | self reads | self writes | self calls | module globals |
|---|---|---|---|---|---|---|---|
| _process_single_ingredient_enhanced | 7472 | 1296 | 2 | 5 | 0:  | 49 | 1 |
| normalize_product | 6394 | 708 | 1 | 4 | 4: _canonical_serving_row, _display_ingredients_buffer, _display_source_rows, _label_ledger_omissions | 35 | 3 |
| _perform_ingredient_mapping | 3911 | 488 | 4 | 15 | 0:  | 10 | 1 |
| _build_display_ingredients | 10738 | 423 | 2 | 0 | 0:  | 9 | 0 |
| _flatten_nested_ingredients | 5392 | 404 | 2 | 1 | 0:  | 21 | 2 |
| _process_ingredients_sequential | 8814 | 277 | 1 | 1 | 0:  | 15 | 1 |
| _process_quantity | 9970 | 201 | 1 | 0 | 0:  | 3 | 1 |
| _process_ingredients_enhanced | 7259 | 116 | 2 | 0 | 0:  | 12 | 1 |
| _process_other_ingredients_enhanced | 8769 | 43 | 1 | 1 | 0:  | 1 | 0 |
| _process_serving_sizes | 10204 | 31 | 1 | 0 | 0:  | 2 | 0 |
| _process_statements | 10172 | 15 | 1 | 0 | 0:  | 0 | 0 |
| _process_claims | 10188 | 15 | 1 | 0 | 0:  | 0 | 0 |

## Transitive helper closure per selected method

Peers (prefix `_process_`): 8 methods reach 97 helpers (5,778 LOC); shared core (helpers reached by ≥3 peers) 52 helpers, 2,380 LOC: _activity_dose_from_notes, _build_unmapped_detail, _classify_hierarchy_type, _daily_value_target_group_from_dv_group, _default_display_resolution_type, _enhanced_allergen_check, _enhanced_allergen_check_cached, _enhanced_harmful_check, _enhanced_harmful_check_cached, _enhanced_ingredient_mapping, _enhanced_ingredient_mapping_cached, _exact_ingredient_group_lookup …

| method | closure methods | closure LOC | exclusive helpers | exclusive LOC | transitive self reads | transitive writes | module globals | most-shared-with (shared helpers) |
|---|---|---|---|---|---|---|---|---|
| normalize_product | 139 | 9,774 | 0 | 0 | 46 | _allergen_variations_cache, _cache_stats, _canonical_serving_row, _display_ingredients_buffer, _display_source_rows | 17 | _process_ingredients_enhanced (95), _process_single_ingredient_enhanced (93), _flatten_nested_ingredients (58) |
| _process_ingredients_enhanced | 94 | 5,594 | 2 | 1,316 | 38 | _allergen_variations_cache, _cache_stats, _display_ingredients_buffer, _form_variations_cache, _harmful_variations_cache | 12 | normalize_product (95), _process_single_ingredient_enhanced (93), _flatten_nested_ingredients (55) |
| _process_single_ingredient_enhanced | 92 | 5,458 | 0 | 0 | 38 | _allergen_variations_cache, _cache_stats, _display_ingredients_buffer, _form_variations_cache, _harmful_variations_cache | 12 | normalize_product (93), _process_ingredients_enhanced (93), _flatten_nested_ingredients (55) |
| _flatten_nested_ingredients | 57 | 2,886 | 0 | 0 | 31 | _allergen_variations_cache, _cache_stats, _display_ingredients_buffer, _form_variations_cache, _harmful_variations_cache | 9 | normalize_product (58), _process_ingredients_enhanced (55), _process_single_ingredient_enhanced (55) |
| _process_other_ingredients_enhanced | 55 | 2,723 | 1 | 277 | 32 | _allergen_variations_cache, _cache_stats, _display_ingredients_buffer, _form_variations_cache, _harmful_variations_cache | 6 | normalize_product (56), _process_ingredients_sequential (55), _process_ingredients_enhanced (52) |
| _process_ingredients_sequential | 54 | 2,680 | 0 | 0 | 31 | _allergen_variations_cache, _cache_stats, _display_ingredients_buffer, _form_variations_cache, _harmful_variations_cache | 6 | normalize_product (55), _process_other_ingredients_enhanced (55), _process_ingredients_enhanced (52) |
| _build_display_ingredients | 34 | 2,181 | 0 | 0 | 22 | _allergen_variations_cache, _cache_stats, _form_variations_cache, _harmful_variations_cache, _ingredient_variations_cache | 2 | normalize_product (35), _process_ingredients_enhanced (29), _process_single_ingredient_enhanced (29) |
| _perform_ingredient_mapping | 11 | 621 | 0 | 0 | 18 | _allergen_variations_cache, _cache_stats, _form_variations_cache, _harmful_variations_cache, _ingredient_variations_cache | 1 | normalize_product (12), _process_ingredients_enhanced (12), _process_single_ingredient_enhanced (12) |
| _process_quantity | 5 | 288 | 0 | 0 | 0 | - | 1 | normalize_product (6), _process_ingredients_enhanced (6), _process_single_ingredient_enhanced (6) |
| _process_serving_sizes | 2 | 76 | 0 | 0 | 0 | - | 1 | normalize_product (3), _process_ingredients_enhanced (2), _process_single_ingredient_enhanced (2) |
| _process_statements | 0 | 15 | 0 | 0 | 0 | - | 0 | normalize_product (1) |
| _process_claims | 0 | 15 | 0 | 0 | 0 | - | 0 | normalize_product (1) |

## Per-run mutable attributes (written outside __init__)

| attribute | written in | read in (methods) |
|---|---|---|
| _cache_stats | __init__, _enhanced_allergen_check, _enhanced_harmful_check, _enhanced_ingredient_mapping, _enhanced_non_harmful_check | 0 |
| _display_source_rows | _record_unsupported_label_source, _stamp_raw_source_paths, normalize_product | 0 |
| _allergen_variations_cache | __init__, allergen_variations | 0 |
| _canonical_id_by_std_name | __init__, _build_canonical_id_reverse_index | 2 |
| _display_ingredients_buffer | _queue_display_ingredient, normalize_product | 0 |
| _form_variations_cache | __init__, form_variations | 0 |
| _harmful_variations_cache | __init__, harmful_variations | 0 |
| _identity_unii_to_payload_lookup | _build_fast_lookups_impl, _build_unii_to_payload_lookup | 0 |
| _ingredient_variations_cache | __init__, ingredient_variations | 0 |
| _label_ledger_omissions | _queue_label_ledger_omission, normalize_product | 0 |
| _non_harmful_variations_cache | __init__, non_harmful_variations | 0 |
| _safety_unii_to_payload_lookup | _build_fast_lookups_impl, _build_unii_to_payload_lookup | 0 |
| _unii_to_payload_lookup | _build_fast_lookups_impl, _build_unii_to_payload_lookup | 1 |
| unmapped_details | __init__, _record_unmapped_ingredient | 2 |
| unmapped_ingredients | __init__, _record_unmapped_ingredient | 3 |
| unmapped_tracker | __init__, set_output_directory | 1 |
| _canonical_identity_registry | _build_canonical_id_reverse_index | 4 |
| _canonical_parent_relationships | _build_canonical_id_reverse_index | 2 |
| _canonical_serving_row | normalize_product | 0 |
| _fast_exact_lookup | _build_fast_lookups_impl | 2 |
| _group_exact_lookup | _build_fast_lookups_impl | 1 |
| _iqm_branded_form_names | _build_iqm_branded_form_names | 0 |
| _safety_exact_lookup | _build_fast_lookups_impl | 2 |
| allergen_lookup | _build_enhanced_indices | 4 |
| harmful_lookup | _build_enhanced_indices | 5 |
| ingredient_alias_lookup | _build_enhanced_indices | 3 |
| ingredient_context_lookup | _build_enhanced_indices | 1 |
| ingredient_forms_lookup | _build_enhanced_indices | 2 |
| other_ingredients_exact_lookup | _build_enhanced_indices | 6 |
| other_ingredients_lookup | _build_enhanced_indices | 7 |
