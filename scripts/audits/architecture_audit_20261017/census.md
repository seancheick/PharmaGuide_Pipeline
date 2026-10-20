# Census at `5fb2be1ca`

Production modules 339, LOC 207,853; functions 5,141 (137 over 150 lines, 43 over 300); annotated 93%; broad excepts 295; print 1803 vs logger 537; lazy imports 399; Level-2 modules 98.

## LOC by layer

| layer | LOC |
|---|---|
| core | 142,018 |
| api_audit | 35,721 |
| release_safety | 9,173 |
| submission_review | 9,089 |
| dashboard | 8,308 |
| tools | 1,325 |
| reports | 1,115 |
| identity | 1,104 |

## Largest modules

| module | LOC | funcs | longest | max nesting | lazy | broad except | commits | tests ref | tier |
|---|---|---|---|---|---|---|---|---|---|
| enrich_supplements_v3.py | 25,186 | 396 | SupplementEnricherV3._collect_rda_ul_data 2278L | 18 | 26 | 16 | 268 | 259 | L2 |
| enhanced_normalizer.py | 12,722 | 234 | EnhancedDSLDNormalizer._process_single_ingredient_enhanced 1296L | 12 | 7 | 5 | 114 | 171 | L2 |
| build_final_db.py | 11,289 | 232 | build_detail_blob 1684L | 8 | 19 | 7 | 164 | 113 | L2 |
| scoring_input_contract.py | 6,451 | 190 | derive_product_scoring_evidence 468L | 5 | 11 | 7 | 130 | 72 | L2 |
| enrichment_contract_validator.py | 3,123 | 36 | EnrichmentContractValidator._validate_label_ledger_omissions 461L | 6 | 2 | 0 | 8 | 6 | L2 |
| audit_source_of_truth_contract.py | 2,191 | 60 | audit_scoring 305L | 12 | 0 | 11 | 34 | 11 | L2 |
| batch_processor.py | 2,105 | 49 | BatchProcessor.process_batch 252L | 7 | 4 | 18 | 9 | 7 | L2 |
| supplement_taxonomy.py | 2,033 | 25 | classify_supplement 1117L | 30 | 3 | 0 | 28 | 75 | L2 |
| scoring_v4/modules/generic_evidence.py | 1,893 | 55 | score_evidence 246L | 5 | 18 | 2 | 81 | 35 | L2 |
| db_integrity_sanity_check.py | 1,804 | 45 | check_ingredient_interaction_rules 268L | 8 | 2 | 2 | 19 | 14 | L2 |
| sync_to_supabase.py | 1,736 | 47 | sync 324L | 5 | 6 | 10 | 19 | 12 | L2 |
| api_audit/verify_interactions.py | 1,694 | 37 | verify_entry 333L | 7 | 5 | 5 | 4 | 11 | L2 |
| constants.py | 1,693 | 0 | - | 0 | 0 | 0 | 8 | 27 | L2 |
| evidence_resolver.py | 1,682 | 32 | resolve_evidence_for_row 661L | 7 | 17 | 0 | 39 | 16 | L2 |
| scoring_v4/quality_score.py | 1,682 | 51 | _pillar_verification 139L | 9 | 1 | 0 | 67 | 54 | L2 |
| api_audit/verify_certifications.py | 1,630 | 45 | main 119L | 7 | 10 | 1 | 2 | 9 | L2 |
| api_audit/iqm_identifier_sweep.py | 1,589 | 24 | assess_umls_concept 152L | 4 | 0 | 6 | 1 | 9 | L2 |
| api_audit/verify_unii.py | 1,555 | 40 | verify_iqm_file 139L | 7 | 0 | 1 | 2 | 3 | L2 |
| product_submission_import.py | 1,543 | 37 | materialize_approved_submissions 156L | 4 | 1 | 0 | 19 | 7 | L2 |
| dashboard/data_loader.py | 1,524 | 32 | _compute_blob_analytics 431L | 7 | 1 | 0 | 6 | 1 | L2 |
| scoring_v4/gate_safety.py | 1,468 | 46 | evaluate_safety_gate 172L | 5 | 0 | 4 | 36 | 30 | L2 |
| api_audit/fda_weekly_sync.py | 1,424 | 30 | main 135L | 5 | 3 | 1 | 5 | 2 | L2 |
| assessment_readiness.py | 1,354 | 27 | _dose_readiness 354L | 13 | 5 | 0 | 30 | 24 | L2 |
| api_audit/fda_manufacturer_violations_sync.py | 1,333 | 30 | main 333L | 5 | 0 | 2 | 4 | 4 | L2 |
| dsld_api_sync.py | 1,312 | 38 | parity_check 103L | 6 | 0 | 7 | 6 | 3 | L2 |
| preflight.py | 1,295 | 23 | run_preflight 207L | 6 | 31 | 7 | 27 | 15 | L2 |
| cert_resolver.py | 1,273 | 41 | resolve 225L | 7 | 3 | 0 | 13 | 11 | L2 |
| api_audit/discover_clinical_evidence.py | 1,246 | 26 | main 171L | 5 | 2 | 0 | 4 | 1 | L2 |
| studied_formulas.py | 1,220 | 47 | assess_probiotic_component_disposition 137L | 9 | 6 | 0 | 30 | 27 | L2 |
| validate_safety_copy.py | 1,217 | 23 | validate_depletion_entry 174L | 4 | 0 | 0 | 4 | 3 | L2 |
| inactive_ingredient_resolver.py | 1,212 | 26 | InactiveIngredientResolver.resolve 136L | 6 | 0 | 0 | 13 | 22 | L2 |
| audit_raw_to_final.py | 1,209 | 44 | audit_product 96L | 7 | 2 | 4 | 11 | 6 | L2 |
| identity_integrity.py | 1,194 | 30 | resolve_identity 375L | 11 | 0 | 0 | 39 | 9 | L2 |
| coverage_gate.py | 1,163 | 14 | CoverageGate.check_product 156L | 4 | 0 | 1 | 7 | 5 | L2 |
| api_audit/verify_rda_uls.py | 1,137 | 8 | main 121L | 6 | 3 | 1 | 1 | 0 | L2 |
| api_audit/verify_pubchem.py | 1,129 | 32 | verify_flat_file 136L | 5 | 0 | 1 | 0 | 1 | L2 |
| build_interaction_db.py | 1,070 | 28 | run_build 156L | 3 | 0 | 1 | 6 | 9 | L2 |
| scoring_v4/modules/generic_transparency.py | 989 | 35 | _score_b5_proprietary_blend_penalty 152L | 4 | 1 | 0 | 17 | 8 | L2 |
| run_pipeline.py | 976 | 19 | PipelineRunner.run_pipeline 234L | 3 | 3 | 5 | 10 | 8 | L2 |
| cleanup_old_versions.py | 968 | 17 | quarantine_orphan_blob_batch 453L | 5 | 10 | 12 | 14 | 9 | L2 |

## Longest functions

| function | lines | nesting | params | nested defs | self.* | branches |
|---|---|---|---|---|---|---|
| enrich_supplements_v3.py:21693 SupplementEnricherV3._collect_rda_ul_data | 2278 | 18 | 4 | 4 | 20 | 163 |
| build_final_db.py:6600 build_detail_blob | 1684 | 5 | 3 | 4 | 0 | 97 |
| enrich_supplements_v3.py:9483 SupplementEnricherV3._match_quality_map_impl | 1355 | 8 | 10 | 27 | 20 | 182 |
| enhanced_normalizer.py:7472 EnhancedDSLDNormalizer._process_single_ingredient_enhanced | 1296 | 9 | 3 | 1 | 54 | 139 |
| supplement_taxonomy.py:613 classify_supplement | 1117 | 30 | 1 | 0 | 0 | 98 |
| enrich_supplements_v3.py:4640 SupplementEnricherV3._collect_ingredient_quality_data | 940 | 5 | 2 | 0 | 43 | 70 |
| enrich_supplements_v3.py:16382 SupplementEnricherV3._collect_probiotic_data | 853 | 5 | 2 | 9 | 11 | 112 |
| enhanced_normalizer.py:6394 EnhancedDSLDNormalizer.normalize_product | 708 | 7 | 2 | 5 | 43 | 125 |
| evidence_resolver.py:632 resolve_evidence_for_row | 661 | 5 | 2 | 0 | 0 | 54 |
| enrich_supplements_v3.py:14345 SupplementEnricherV3._collect_proprietary_data | 570 | 5 | 2 | 3 | 7 | 61 |
| build_final_db.py:10682 build_final_db | 549 | 5 | 6 | 0 | 0 | 40 |
| enrich_supplements_v3.py:20086 SupplementEnricherV3._collect_interaction_profile | 531 | 6 | 3 | 1 | 14 | 77 |
| enhanced_normalizer.py:11776 EnhancedDSLDNormalizer._is_nutrition_fact | 526 | 5 | 7 | 0 | 5 | 37 |
| enhanced_normalizer.py:3911 EnhancedDSLDNormalizer._perform_ingredient_mapping | 488 | 7 | 5 | 0 | 25 | 72 |
| scoring_input_contract.py:1813 derive_product_scoring_evidence | 468 | 5 | 1 | 2 | 0 | 51 |
| enhanced_normalizer.py:4927 EnhancedDSLDNormalizer._merge_alternate_serving_rows | 464 | 3 | 2 | 20 | 0 | 58 |
| enrichment_contract_validator.py:1886 EnrichmentContractValidator._validate_label_ledger_omissions | 461 | 4 | 4 | 0 | 4 | 41 |
| cleanup_old_versions.py:230 quarantine_orphan_blob_batch | 453 | 5 | 9 | 7 | 0 | 57 |
| dashboard/data_loader.py:773 _compute_blob_analytics | 431 | 4 | 3 | 0 | 0 | 27 |
| enhanced_normalizer.py:10738 EnhancedDSLDNormalizer._build_display_ingredients | 423 | 4 | 3 | 4 | 9 | 44 |
| enrich_supplements_v3.py:15450 SupplementEnricherV3._collect_evidence_data | 416 | 6 | 3 | 4 | 14 | 64 |
| enhanced_normalizer.py:5392 EnhancedDSLDNormalizer._flatten_nested_ingredients | 404 | 8 | 3 | 0 | 22 | 49 |
| enrich_supplements_v3.py:8286 SupplementEnricherV3._match_multi_form | 404 | 5 | 4 | 1 | 11 | 40 |
| unit_converter.py:155 UnitConverter.convert_nutrient | 381 | 3 | 7 | 0 | 4 | 29 |
| enrich_supplements_v3.py:8698 SupplementEnricherV3._build_form_info_from_cleaned | 376 | 4 | 4 | 2 | 7 | 44 |
| identity_integrity.py:820 resolve_identity | 375 | 11 | 7 | 0 | 0 | 23 |
| build_final_db.py:1689 validate_export_contract | 372 | 6 | 2 | 0 | 0 | 54 |
| enrich_supplements_v3.py:24455 SupplementEnricherV3._build_match_ledger | 371 | 6 | 3 | 0 | 2 | 29 |
| assessment_readiness.py:900 _dose_readiness | 354 | 3 | 3 | 6 | 0 | 33 |
| enrich_supplements_v3.py:12142 SupplementEnricherV3._check_banned_substances | 352 | 7 | 3 | 0 | 11 | 47 |

## Import graph

Top-level edges 688, lazy edges 289; top-level cycles 0; cycles once lazy imports count 3 (sizes [12, 3, 2]).

| fan-in (top-level importers) | n |
|---|---|
| scoring_v4.quality_score_config | 37 |
| scoring_v4.modules.generic_helpers | 36 |
| scoring_input_contract | 30 |
| env_loader | 24 |
| supabase_client | 17 |
| normalization | 15 |
| constants | 12 |
| probiotic_measurements | 11 |
| run_artifacts | 10 |
| scoring_reference_resolver | 10 |
| dashboard.components.metric_cards | 9 |
| dashboard.data_loader | 9 |
| scoring_v4.modules.generic_formulation | 9 |
| stage_manifest | 9 |
| submission_review.extraction.extractor | 9 |

| fan-out | n |
|---|---|
| enrich_supplements_v3 | 25 |
| build_final_db | 22 |
| score_supplements_v4 | 16 |
| scoring_v4.modules.b_complex | 12 |
| api_audit.audit_v4_profile_cutover_impact | 10 |
| enhanced_normalizer | 10 |
| scoring_v4.modules.generic_dose | 10 |
| scoring_v4.modules.multi_prenatal | 10 |
| scoring_v4.modules.omega | 10 |
| scoring_v4.modules.probiotic | 10 |

### Cycle edges

| importer | imports | line | in function | comment hint |
|---|---|---|---|---|
| audit_identity_integrity | build_final_db | 215 | audit_product |  |
| build_final_db | audit_identity_integrity | 57 | module level |  |
| clinical_applicability | scoring_input_contract | 105 | _evidence_subject_refs |  |
| clinical_applicability | scoring_input_contract | 178 | _resolved_identity_by_ref |  |
| clinical_applicability | scoring_input_contract | 260 | _linked_rows |  |
| dsld_validator | product_submission_import | 68 | validate_product |  |
| enhanced_normalizer | dsld_validator | 9941 | _validate_upc |  |
| evidence_resolver | clinical_applicability | 997 | resolve_evidence_for_row |  |
| evidence_resolver | clinical_applicability | 1200 | resolve_evidence_for_row |  |
| evidence_resolver | probiotic_measurements | 830 | resolve_evidence_for_row |  |
| evidence_resolver | scoring_input_contract | 251 | resolve_omega_evidence_standard |  |
| evidence_resolver | scoring_input_contract | 443 | _essential_nutrient_canonicals |  |
| evidence_resolver | scoring_input_contract | 749 | resolve_evidence_for_row |  |
| evidence_resolver | scoring_input_contract | 1302 | _evidence_subject_roles |  |
| evidence_resolver | scoring_input_contract | 1378 | _evidence_owner_selection |  |
| evidence_resolver | scoring_input_contract | 1431 | _evidence_claim_purposes |  |
| evidence_resolver | scoring_input_contract | 1490 | resolve_product_evidence |  |
| evidence_resolver | scoring_input_contract | 1502 | resolve_product_evidence |  |
| evidence_resolver | scoring_input_contract | 1621 | resolve_authority_panel_evidence |  |
| evidence_resolver | scoring_v4.route_features | 448 | _essential_nutrient_canonicals |  |
| evidence_resolver | studied_formulas | 806 | resolve_evidence_for_row |  |
| evidence_resolver | studied_formulas | 838 | resolve_evidence_for_row |  |
| probiotic_measurements | studied_formulas | 253 | probiotic_label_identity_summary |  |
| probiotic_measurements | studied_formulas | 520 | pending_afu_measurements |  |
| probiotic_measurements | studied_formulas | 688 | derived_context_evidence |  |
| probiotic_measurements | studied_formulas | 944 | label_strain_identity_resolution |  |
| product_submission_import | enhanced_normalizer | 503 | _pipeline_other_ingredient_rows |  |
| scoring_input_contract | evidence_resolver | 1820 | derive_product_scoring_evidence |  |
| scoring_input_contract | evidence_resolver | 3358 | _is_ineligible_evidence_subject |  |
| scoring_input_contract | evidence_resolver | 6227 | _role_function_claim_source |  |
| scoring_input_contract | probiotic_measurements | 47 | module level |  |
| scoring_input_contract | probiotic_measurements | 1319 | _derive_probiotic_cfu_evidence |  |
| scoring_input_contract | probiotic_measurements | 4168 | _route_is_probiotic_class |  |
| scoring_input_contract | probiotic_measurements | 6115 | _role_is_probiotic_strain |  |
| scoring_input_contract | scoring_v4.modules.immune_support | 6265 | _role_context |  |
| scoring_input_contract | scoring_v4.modules.sports_helpers | 6273 | _role_context |  |
| scoring_input_contract | scoring_v4.route_features | 48 | module level |  |
| scoring_input_contract | scoring_v4.route_features | 6084 | role_driver_canonicals |  |
| scoring_input_contract | scoring_v4.router | 6258 | _role_context | yes |
| scoring_v4.dose_safety | scoring_v4.modules.generic_helpers | 41 | module level |  |
| scoring_v4.modules.generic_helpers | scoring_input_contract | 24 | module level |  |
| scoring_v4.modules.generic_helpers | scoring_input_contract | 462 | score_declared_serving_dose |  |
| scoring_v4.modules.generic_helpers | scoring_v4.quality_score | 201 | archetype_dose_reference |  |
| scoring_v4.modules.immune_support | scoring_input_contract | 21 | module level |  |
| scoring_v4.modules.immune_support | scoring_v4.modules.generic_helpers | 12 | module level |  |
| scoring_v4.modules.sports_helpers | scoring_input_contract | 7 | module level |  |
| scoring_v4.modules.sports_helpers | scoring_v4.modules.generic_helpers | 13 | module level |  |
| scoring_v4.modules.sports_helpers | scoring_v4.route_features | 9 | module level |  |
| scoring_v4.quality_score | scoring_v4.dose_safety | 27 | module level |  |
| scoring_v4.route_features | probiotic_measurements | 335 | _probiotic_features |  |
| scoring_v4.router | scoring_input_contract | 14 | module level |  |
| studied_formulas | clinical_applicability | 16 | module level |  |
| studied_formulas | probiotic_measurements | 20 | module level |  |
| studied_formulas | probiotic_measurements | 436 | _label_strain_identity_candidates |  |
| studied_formulas | probiotic_measurements | 772 | species_with_clinical_strain_evidence |  |
| studied_formulas | probiotic_measurements | 802 | assess_probiotic_component_disposition |  |

## Duplication

Exact cross-file groups 5; structural cross-file groups 11 (~364 duplicated lines).

| structural group | files | lines |
|---|---|---|
| api_audit/enrich_chembl_bioactivity.py:162 ChEMBLClient._get ; api_audit/verify_clinical_trials.py:150 ClinicalTrialsClient._get | 2 | 44 |
| scoring_v4/modules/joint_support.py:183 _row_quantity_mg ; scoring_v4/modules/sleep_support.py:156 _row_quantity_mg | 2 | 31 |
| release_safety/delete_stale_version_dirs.py:637 _list_paginated ; release_safety/storage_audit.py:539 _list_paginated | 2 | 29 |
| dashboard/views/audit_section_c.py:21 render_audit_section_c ; dashboard/views/audit_section_d.py:21 render_audit_section_d | 2 | 24 |
| api_audit/enrich_chembl_bioactivity.py:108 ChEMBLClient.__init__ ; api_audit/verify_clinical_trials.py:96 ClinicalTrialsClient.__init__ ; api_audit/verify_pubchem.py:225 PubChemClient.__init__ ; api_audit/verify_unii.py:332 GSRSClient.__init__ | 4 | 21 |
| api_audit/audit_unii_data_quality.py:64 _normalize_unii ; enhanced_normalizer.py:116 _normalize_unii ; enrich_supplements_v3.py:544 _normalize_unii | 3 | 19 |
| scoring_v4/modules/generic_trust.py:261 _label_asserted_program_key ; scoring_v4/modules/omega_trust.py:200 _cert_program_key | 2 | 19 |
| api_audit/audit_v4_profile_consistency.py:45 _row ; api_audit/audit_v4_route_consistency.py:37 _row | 2 | 17 |
| scoring_v4/modules/generic.py:228 GenericModuleResult.to_breakdown ; scoring_v4/modules/multi_prenatal.py:101 MultiPrenatalModuleResult.to_breakdown ; scoring_v4/modules/omega.py:125 OmegaModuleResult.to_breakdown ; scoring_v4/modules/probiotic.py:119 ProbioticModuleResult.to_breakdown | 4 | 17 |
| api_audit/enrich_chembl_bioactivity.py:132 ChEMBLClient._cache_get ; api_audit/verify_clinical_trials.py:120 ClinicalTrialsClient._cache_get ; api_audit/verify_comptox.py:117 CompToxClient._cache_get ; api_audit/verify_pubchem.py:249 PubChemClient._cache_get | 5 | 14 |
| scoring_v4/dose_safety.py:173 dose_safety_scope ; scoring_v4/gate_safety.py:1449 safety_gate_scope | 2 | 12 |

| same-name private helper | files |
|---|---|
| _norm | 29 |
| _safe_dict | 20 |
| _safe_list | 18 |
| _parse_args | 12 |
| _clamp | 11 |
| _as_float | 10 |
| _cache_get | 9 |
| _key | 8 |
| _cache_set | 7 |
| _get | 7 |
| _load | 6 |
| _load_json | 6 |
| _normalize | 6 |
| _load_rubric | 5 |
| _make_ssl_ctx | 5 |

## Churn since 2026-07-01 (2590 commits)

| file | commits |
|---|---|
| scripts/enrich_supplements_v3.py | 268 |
| scripts/build_final_db.py | 164 |
| scripts/scoring_input_contract.py | 130 |
| scripts/enhanced_normalizer.py | 114 |
| scripts/scoring_v4/modules/generic_evidence.py | 81 |
| scripts/scoring_v4/quality_score.py | 67 |
| scripts/release_full.sh | 53 |
| scripts/evidence_resolver.py | 39 |
| scripts/identity_integrity.py | 39 |
| scripts/scoring_v4/gate_safety.py | 36 |
| scripts/audit_source_of_truth_contract.py | 34 |
| scripts/probiotic_measurements.py | 32 |
| scripts/assessment_readiness.py | 30 |
| scripts/studied_formulas.py | 30 |
| scripts/supplement_taxonomy.py | 28 |
| scripts/preflight.py | 27 |
| scripts/scoring_v4/modules/generic_dose.py | 27 |
| scripts/score_supplements_v4.py | 26 |
| scripts/scoring_v4/modules/generic_helpers.py | 26 |
| scripts/scoring_v4/scored_artifact.py | 26 |
| scripts/test.sh | 26 |
| scripts/scoring_v4/modules/generic_formulation.py | 24 |
| scripts/unit_converter.py | 23 |
| scripts/clinical_applicability.py | 22 |
| scripts/scoring_v4/modules/probiotic_evidence.py | 20 |

Co-change: 773 commits touch the watched files; 208 touch ≥2 groups, 70 touch ≥3 (1 bulk commits skipped).

| pair | commits |
|---|---|
| scripts/scoring_input_contract.py + scripts/scoring_v4/* | 66 |
| scripts/build_final_db.py + scripts/scoring_v4/* | 53 |
| scripts/enrich_supplements_v3.py + scripts/scoring_v4/* | 53 |
| scripts/enhanced_normalizer.py + scripts/enrich_supplements_v3.py | 45 |
| scripts/build_final_db.py + scripts/enrich_supplements_v3.py | 37 |
| scripts/enrich_supplements_v3.py + scripts/scoring_input_contract.py | 33 |
| scripts/enhanced_normalizer.py + scripts/scoring_v4/* | 19 |
| scripts/build_final_db.py + scripts/scoring_input_contract.py | 17 |
| scripts/evidence_resolver.py + scripts/scoring_v4/* | 17 |
| scripts/enhanced_normalizer.py + scripts/scoring_input_contract.py | 12 |
| scripts/evidence_resolver.py + scripts/scoring_input_contract.py | 12 |
| scripts/scoring_input_contract.py + scripts/supplement_taxonomy.py | 12 |
| scripts/build_final_db.py + scripts/enhanced_normalizer.py | 10 |
| scripts/enrich_supplements_v3.py + scripts/supplement_taxonomy.py | 8 |
| scripts/scoring_v4/* + scripts/supplement_taxonomy.py | 8 |

## Tests

1069 files, 290,307 LOC, 253 fixture files; profiles {'SLOW_TEST_FILES': 20, 'LOCAL_ONLY_TEST_FILES': 25, 'RELEASE_TEST_FILES': 11, 'ARTIFACT_TEST_FILES': 19}; marks {'parametrize': 1898, 'skipif': 21, 'slow': 2, 'timeout': 1}.

## CI run 39070168203 (main 5fb2be1ca, success, wall 717s)

| job | fast rung s | job s |
|---|---|---|
| fast (0) | 404 | 472 |
| fast (1) | 651 | 715 |
| fast (2) | 343 | 403 |
| fast (3) | 390 | 461 |

## Pipeline timing (existing logs only)

- `scripts/products/reports/batch_run_summary_20260521_042114.txt`: 26 brands (23 complete, 23 succeeded), wall 3872s, products 10134, stage wall sums clean/enrich/gates/score = 109/3712/16/27 s
- `scripts/products/reports/batch_run_summary_20260521_172104.txt`: 1 brands (0 complete, 0 succeeded), wall 5s, products 0, stage wall sums clean/enrich/gates/score = 4/None/None/None s
- `scripts/products/reports/batch_run_summary_20260521_172535.txt`: 27 brands (25 complete, 25 succeeded), wall 3836s, products 10144, stage wall sums clean/enrich/gates/score = 113/3664/21/33 s
- `scripts/products/reports/batch_run_summary_20260522_023152.txt`: 27 brands (25 complete, 25 succeeded), wall 3764s, products 10144, stage wall sums clean/enrich/gates/score = 112/3600/14/27 s
- `scripts/products/reports/batch_run_summary_20260522_153218.txt`: 3 brands (3 complete, 3 succeeded), wall 745s, products 974, stage wall sums clean/enrich/gates/score = 18/719/3/4 s
- `scripts/products/reports/batch_run_summary_20260522_162852.txt`: 2 brands (1 complete, 1 succeeded), wall 78s, products 349, stage wall sums clean/enrich/gates/score = None/76/0/1 s
- `scripts/products/reports/batch_run_summary_20260522_163420.txt`: 1 brands (1 complete, 1 succeeded), wall 44s, products 10, stage wall sums clean/enrich/gates/score = None/43/0/1 s
- `scripts/products/reports/batch_run_summary_20260522_163513.txt`: 2 brands (2 complete, 2 succeeded), wall 121s, products 359, stage wall sums clean/enrich/gates/score = None/119/0/2 s
- `scripts/products/reports/batch_run_summary_20260522_164505.txt`: 2 brands (2 complete, 2 succeeded), wall 142s, products 359, stage wall sums clean/enrich/gates/score = 8/132/1/1 s
- `scripts/products/reports/batch_run_summary_20260522_164825.txt`: 1 brands (1 complete, 1 succeeded), wall 90s, products 349, stage wall sums clean/enrich/gates/score = 4/85/0/1 s
- `scripts/products/reports/batch_run_summary_20260522_172626.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260522_172650.txt`: 1 brands (1 complete, 1 succeeded), wall 80s, products 349, stage wall sums clean/enrich/gates/score = None/79/0/1 s
- `scripts/products/reports/batch_run_summary_20260522_180533.txt`: 1 brands (1 complete, 1 succeeded), wall 2s, products 0, stage wall sums clean/enrich/gates/score = None/None/1/1 s
- `scripts/products/reports/batch_run_summary_20260522_180541.txt`: 1 brands (1 complete, 1 succeeded), wall 9s, products 0, stage wall sums clean/enrich/gates/score = None/None/5/4 s
- `scripts/products/reports/batch_run_summary_20260522_180550.txt`: 1 brands (1 complete, 1 succeeded), wall 0s, products 0, stage wall sums clean/enrich/gates/score = None/None/0/0 s
- `scripts/products/reports/batch_run_summary_20260522_181054.txt`: 1 brands (1 complete, 1 succeeded), wall 1s, products 0, stage wall sums clean/enrich/gates/score = None/None/0/1 s
- `scripts/products/reports/batch_run_summary_20260522_181433.txt`: 3 brands (3 complete, 3 succeeded), wall 1207s, products 974, stage wall sums clean/enrich/gates/score = 24/1170/6/7 s
- `scripts/products/reports/batch_run_summary_20260522_183556.txt`: 3 brands (3 complete, 3 succeeded), wall 14s, products 0, stage wall sums clean/enrich/gates/score = None/None/6/8 s
- `scripts/products/reports/batch_run_summary_20260522_185630.txt`: 1 brands (1 complete, 1 succeeded), wall 1030s, products 615, stage wall sums clean/enrich/gates/score = None/1022/4/4 s
- `scripts/products/reports/batch_run_summary_20260522_191346.txt`: 2 brands (2 complete, 2 succeeded), wall 1s, products 0, stage wall sums clean/enrich/gates/score = None/None/0/1 s
- `scripts/products/reports/batch_run_summary_20260522_191517.txt`: 1 brands (1 complete, 1 succeeded), wall 984s, products 615, stage wall sums clean/enrich/gates/score = None/977/3/4 s
- `scripts/products/reports/batch_run_summary_20260522_193725.txt`: 1 brands (1 complete, 1 succeeded), wall 974s, products 615, stage wall sums clean/enrich/gates/score = None/967/3/4 s
- `scripts/products/reports/batch_run_summary_20260522_195449.txt`: 2 brands (2 complete, 2 succeeded), wall 1s, products 0, stage wall sums clean/enrich/gates/score = None/None/0/1 s
- `scripts/products/reports/batch_run_summary_20260522_203125.txt`: 1 brands (1 complete, 1 succeeded), wall 177s, products 615, stage wall sums clean/enrich/gates/score = None/177/None/None s
- `scripts/products/reports/batch_run_summary_20260522_211700.txt`: 27 brands (27 complete, 27 succeeded), wall 1318s, products 10144, stage wall sums clean/enrich/gates/score = 124/1047/28/38 s
- `scripts/products/reports/batch_run_summary_20260522_222429.txt`: 2 brands (2 complete, 2 succeeded), wall 216s, products 964, stage wall sums clean/enrich/gates/score = None/207/3/6 s
- `scripts/products/reports/batch_run_summary_20260522_223001.txt`: 1 brands (1 complete, 1 succeeded), wall 191s, products 615, stage wall sums clean/enrich/gates/score = None/184/3/4 s
- `scripts/products/reports/batch_run_summary_20260522_223637.txt`: 1 brands (1 complete, 1 succeeded), wall 23s, products 349, stage wall sums clean/enrich/gates/score = None/21/1/1 s
- `scripts/products/reports/batch_run_summary_20260522_223807.txt`: 1 brands (1 complete, 1 succeeded), wall 7s, products 10, stage wall sums clean/enrich/gates/score = None/7/0/0 s
- `scripts/products/reports/batch_run_summary_20260523_032458.txt`: 27 brands (27 complete, 27 succeeded), wall 28717s, products 10144, stage wall sums clean/enrich/gates/score = 134/1137/28/41 s
- `scripts/products/reports/batch_run_summary_20260524_155748.txt`: 27 brands (27 complete, 27 succeeded), wall 17040s, products 10144, stage wall sums clean/enrich/gates/score = 13606/1011/24/40 s
- `scripts/products/reports/batch_run_summary_20260524_213959.txt`: 27 brands (27 complete, 27 succeeded), wall 1782s, products 10144, stage wall sums clean/enrich/gates/score = 126/1069/25/39 s
- `scripts/products/reports/batch_run_summary_20260525_001301.txt`: 1 brands (1 complete, 1 succeeded), wall 16s, products 349, stage wall sums clean/enrich/gates/score = None/15/1/0 s
- `scripts/products/reports/batch_run_summary_20260525_003742.txt`: 1 brands (1 complete, 1 succeeded), wall 35s, products 485, stage wall sums clean/enrich/gates/score = None/33/1/1 s
- `scripts/products/reports/batch_run_summary_20260525_004019.txt`: 1 brands (1 complete, 1 succeeded), wall 34s, products 485, stage wall sums clean/enrich/gates/score = None/32/1/1 s
- `scripts/products/reports/batch_run_summary_20260525_005519.txt`: 2 brands (2 complete, 2 succeeded), wall 433s, products 2829, stage wall sums clean/enrich/gates/score = None/412/9/12 s
- `scripts/products/reports/batch_run_summary_20260525_012020.txt`: 4 brands (4 complete, 4 succeeded), wall 24s, products 0, stage wall sums clean/enrich/gates/score = None/None/10/14 s
- `scripts/products/reports/batch_run_summary_20260525_121523.txt`: 27 brands (27 complete, 27 succeeded), wall 1523s, products 10144, stage wall sums clean/enrich/gates/score = 130/1125/23/44 s
- `scripts/products/reports/batch_run_summary_20260525_142153.txt`: 27 brands (27 complete, 27 succeeded), wall 1415s, products 10144, stage wall sums clean/enrich/gates/score = 125/1059/25/35 s
- `scripts/products/reports/batch_run_summary_20260526_070608.txt`: 27 brands (27 complete, 27 succeeded), wall 1534s, products 10144, stage wall sums clean/enrich/gates/score = 127/1079/27/39 s
- `scripts/products/reports/batch_run_summary_20260526_122258.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260526_122312.txt`: 2 brands (1 complete, 1 succeeded), wall 389s, products 2214, stage wall sums clean/enrich/gates/score = None/370/7/11 s
- `scripts/products/reports/batch_run_summary_20260526_135258.txt`: 27 brands (27 complete, 27 succeeded), wall 1344s, products 10144, stage wall sums clean/enrich/gates/score = 123/1078/22/36 s
- `scripts/products/reports/batch_run_summary_20260526_145745.txt`: 27 brands (27 complete, 27 succeeded), wall 1875s, products 10144, stage wall sums clean/enrich/gates/score = 122/1059/26/35 s
- `scripts/products/reports/batch_run_summary_20260527_013853.txt`: 27 brands (27 complete, 27 succeeded), wall 1430s, products 10144, stage wall sums clean/enrich/gates/score = 124/1069/25/39 s
- `scripts/products/reports/batch_run_summary_20260528_015142.txt`: 27 brands (27 complete, 27 succeeded), wall 1474s, products 10144, stage wall sums clean/enrich/gates/score = 126/1094/29/38 s
- `scripts/products/reports/batch_run_summary_20260528_152322.txt`: 27 brands (27 complete, 27 succeeded), wall 1889s, products 10144, stage wall sums clean/enrich/gates/score = 157/1305/32/43 s
- `scripts/products/reports/batch_run_summary_20260529_210730.txt`: 27 brands (27 complete, 27 succeeded), wall 1816s, products 10144, stage wall sums clean/enrich/gates/score = 140/1380/26/41 s
- `scripts/products/reports/batch_run_summary_20260530_203801.txt`: 27 brands (27 complete, 27 succeeded), wall 3091s, products 10144, stage wall sums clean/enrich/gates/score = 126/1410/27/57 s
- `scripts/products/reports/batch_run_summary_20260531_015815.txt`: 27 brands (27 complete, 27 succeeded), wall 2395s, products 10144, stage wall sums clean/enrich/gates/score = 193/1676/40/86 s
- `scripts/products/reports/batch_run_summary_20260601_020754.txt`: 27 brands (27 complete, 27 succeeded), wall 1784s, products 10144, stage wall sums clean/enrich/gates/score = 135/1387/27/55 s
- `scripts/products/reports/batch_run_summary_20260602_021807.txt`: 27 brands (27 complete, 27 succeeded), wall 2035s, products 10144, stage wall sums clean/enrich/gates/score = 137/1403/24/64 s
- `scripts/products/reports/batch_run_summary_20260602_111757.txt`: 27 brands (27 complete, 27 succeeded), wall 1935s, products 10144, stage wall sums clean/enrich/gates/score = 142/1486/27/65 s
- `scripts/products/reports/batch_run_summary_20260602_163323.txt`: 27 brands (27 complete, 27 succeeded), wall 1947s, products 10144, stage wall sums clean/enrich/gates/score = 145/1426/30/65 s
- `scripts/products/reports/batch_run_summary_20260602_173148.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260602_175552.txt`: 1 brands (1 complete, 1 succeeded), wall 478s, products 2214, stage wall sums clean/enrich/gates/score = 25/428/7/18 s
- `scripts/products/reports/batch_run_summary_20260604_031237.txt`: 27 brands (27 complete, 27 succeeded), wall 1845s, products 10144, stage wall sums clean/enrich/gates/score = 148/1412/25/70 s
- `scripts/products/reports/batch_run_summary_20260604_214024.txt`: 27 brands (27 complete, 27 succeeded), wall 2083s, products 10144, stage wall sums clean/enrich/gates/score = 152/1419/29/62 s
- `scripts/products/reports/batch_run_summary_20260605_003522.txt`: 27 brands (27 complete, 27 succeeded), wall 2087s, products 10144, stage wall sums clean/enrich/gates/score = 150/1485/32/78 s
- `scripts/products/reports/batch_run_summary_20260605_022707.txt`: 27 brands (27 complete, 27 succeeded), wall 1815s, products 10144, stage wall sums clean/enrich/gates/score = 136/1397/28/73 s
- `scripts/products/reports/batch_run_summary_20260606_004701.txt`: 27 brands (27 complete, 27 succeeded), wall 2237s, products 10144, stage wall sums clean/enrich/gates/score = 129/1788/27/68 s
- `scripts/products/reports/batch_run_summary_20260606_074019.txt`: 27 brands (27 complete, 27 succeeded), wall 2120s, products 10144, stage wall sums clean/enrich/gates/score = 131/1716/24/70 s
- `scripts/products/reports/batch_run_summary_20260606_224905.txt`: 27 brands (27 complete, 27 succeeded), wall 2903s, products 10144, stage wall sums clean/enrich/gates/score = 207/2226/41/92 s
- `scripts/products/reports/batch_run_summary_20260607_185205.txt`: 1 brands (0 complete, 0 succeeded), wall 1s, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260607_185340.txt`: 27 brands (27 complete, 27 succeeded), wall 2502s, products 10144, stage wall sums clean/enrich/gates/score = 133/2011/29/82 s
- `scripts/products/reports/batch_run_summary_20260608_045107.txt`: 27 brands (27 complete, 27 succeeded), wall 2469s, products 10144, stage wall sums clean/enrich/gates/score = 143/2027/29/78 s
- `scripts/products/reports/batch_run_summary_20260608_130800.txt`: 27 brands (27 complete, 27 succeeded), wall 2481s, products 10144, stage wall sums clean/enrich/gates/score = 134/1998/30/80 s
- `scripts/products/reports/batch_run_summary_20260608_180908.txt`: 27 brands (27 complete, 27 succeeded), wall 2707s, products 10144, stage wall sums clean/enrich/gates/score = 136/2008/34/78 s
- `scripts/products/reports/batch_run_summary_20260608_231639.txt`: 27 brands (27 complete, 27 succeeded), wall 3906s, products 10144, stage wall sums clean/enrich/gates/score = 125/1934/28/78 s
- `scripts/products/reports/batch_run_summary_20260609_010959.txt`: 27 brands (27 complete, 27 succeeded), wall 2455s, products 10144, stage wall sums clean/enrich/gates/score = 124/1919/28/74 s
- `scripts/products/reports/batch_run_summary_20260609_115904.txt`: 1 brands (1 complete, 1 succeeded), wall 247s, products 0, stage wall sums clean/enrich/gates/score = None/None/8/21 s
- `scripts/products/reports/batch_run_summary_20260609_153042.txt`: 6 brands (6 complete, 6 succeeded), wall 990s, products 3789, stage wall sums clean/enrich/gates/score = None/722/12/28 s
- `scripts/products/reports/batch_run_summary_20260609_160628.txt`: 27 brands (27 complete, 27 succeeded), wall 326s, products 0, stage wall sums clean/enrich/gates/score = None/None/28/70 s
- `scripts/products/reports/batch_run_summary_20260609_212549.txt`: 27 brands (27 complete, 27 succeeded), wall 2388s, products 10144, stage wall sums clean/enrich/gates/score = 130/1843/29/75 s
- `scripts/products/reports/batch_run_summary_20260612_001442.txt`: 2 brands (1 complete, 1 succeeded), wall 59s, products 240, stage wall sums clean/enrich/gates/score = 7/41/1/1 s
- `scripts/products/reports/batch_run_summary_20260612_042950.txt`: 27 brands (27 complete, 27 succeeded), wall 2334s, products 10144, stage wall sums clean/enrich/gates/score = 123/1805/23/76 s
- `scripts/products/reports/batch_run_summary_20260614_133211.txt`: 27 brands (27 complete, 27 succeeded), wall 2451s, products 10144, stage wall sums clean/enrich/gates/score = 127/1883/29/80 s
- `scripts/products/reports/batch_run_summary_20260614_214532.txt`: 5 brands (4 complete, 4 succeeded), wall 120s, products 853, stage wall sums clean/enrich/gates/score = None/113/1/4 s
- `scripts/products/reports/batch_run_summary_20260614_215923.txt`: 12 brands (11 complete, 11 succeeded), wall 7629s, products 4796, stage wall sums clean/enrich/gates/score = 6463/1100/19/47 s
- `scripts/products/reports/batch_run_summary_20260615_002524.txt`: 22 brands (21 complete, 21 succeeded), wall 6705s, products 9275, stage wall sums clean/enrich/gates/score = 4699/1884/35/81 s
- `scripts/products/reports/batch_run_summary_20260615_023820.txt`: 1 brands (1 complete, 1 succeeded), wall 246s, products 0, stage wall sums clean/enrich/gates/score = 246/None/None/None s
- `scripts/products/reports/batch_run_summary_20260615_024534.txt`: 1 brands (1 complete, 1 succeeded), wall 4s, products 0, stage wall sums clean/enrich/gates/score = 4/None/None/None s
- `scripts/products/reports/batch_run_summary_20260615_024644.txt`: 1 brands (1 complete, 1 succeeded), wall 4s, products 0, stage wall sums clean/enrich/gates/score = 4/None/None/None s
- `scripts/products/reports/batch_run_summary_20260615_024740.txt`: 27 brands (27 complete, 27 succeeded), wall 2954s, products 10144, stage wall sums clean/enrich/gates/score = 688/1833/26/76 s
- `scripts/products/reports/batch_run_summary_20260615_102000.txt`: 27 brands (27 complete, 27 succeeded), wall 2341s, products 10144, stage wall sums clean/enrich/gates/score = 119/1818/25/76 s
- `scripts/products/reports/batch_run_summary_20260615_132458.txt`: 27 brands (27 complete, 27 succeeded), wall 2454s, products 10144, stage wall sums clean/enrich/gates/score = 124/1877/25/77 s
- `scripts/products/reports/batch_run_summary_20260616_021519.txt`: 27 brands (27 complete, 27 succeeded), wall 2447s, products 10144, stage wall sums clean/enrich/gates/score = 128/1883/27/76 s
- `scripts/products/reports/batch_run_summary_20260616_144210.txt`: 27 brands (27 complete, 27 succeeded), wall 2459s, products 10144, stage wall sums clean/enrich/gates/score = 123/1889/28/77 s
- `scripts/products/reports/batch_run_summary_20260617_121528.txt`: 27 brands (27 complete, 27 succeeded), wall 3484s, products 10144, stage wall sums clean/enrich/gates/score = 186/2468/51/121 s
- `scripts/products/reports/batch_run_summary_20260619_123214.txt`: 27 brands (27 complete, 27 succeeded), wall 2676s, products 10144, stage wall sums clean/enrich/gates/score = 141/2069/35/85 s
- `scripts/products/reports/batch_run_summary_20260620_165651.txt`: 27 brands (27 complete, 27 succeeded), wall 2664s, products 10144, stage wall sums clean/enrich/gates/score = 127/2077/28/80 s
- `scripts/products/reports/batch_run_summary_20260622_093720.txt`: 1 brands (1 complete, 1 succeeded), wall 18s, products 0, stage wall sums clean/enrich/gates/score = 18/None/None/None s
- `scripts/products/reports/batch_run_summary_20260622_110428.txt`: 1 brands (1 complete, 1 succeeded), wall 24s, products 0, stage wall sums clean/enrich/gates/score = 24/None/None/None s
- `scripts/products/reports/batch_run_summary_20260622_112510.txt`: 1 brands (1 complete, 1 succeeded), wall 19s, products 0, stage wall sums clean/enrich/gates/score = 19/None/None/None s
- `scripts/products/reports/batch_run_summary_20260622_190935.txt`: 1 brands (1 complete, 1 succeeded), wall 25s, products 0, stage wall sums clean/enrich/gates/score = 25/None/None/None s
- `scripts/products/reports/batch_run_summary_20260622_194955.txt`: 1 brands (1 complete, 1 succeeded), wall 24s, products 0, stage wall sums clean/enrich/gates/score = 24/None/None/None s
- `scripts/products/reports/batch_run_summary_20260622_203543.txt`: 1 brands (1 complete, 1 succeeded), wall 23s, products 0, stage wall sums clean/enrich/gates/score = 23/None/None/None s
- `scripts/products/reports/batch_run_summary_20260622_212439.txt`: 1 brands (1 complete, 1 succeeded), wall 31s, products 0, stage wall sums clean/enrich/gates/score = 31/None/None/None s
- `scripts/products/reports/batch_run_summary_20260622_220040.txt`: 28 brands (28 complete, 28 succeeded), wall 208s, products 0, stage wall sums clean/enrich/gates/score = 197/None/None/None s
- `scripts/products/reports/batch_run_summary_20260622_222225.txt`: 28 brands (28 complete, 28 succeeded), wall 227s, products 0, stage wall sums clean/enrich/gates/score = 221/None/None/None s
- `scripts/products/reports/batch_run_summary_20260622_222930.txt`: 28 brands (28 complete, 28 succeeded), wall 146s, products 0, stage wall sums clean/enrich/gates/score = 139/None/None/None s
- `scripts/products/reports/batch_run_summary_20260622_224302.txt`: 1 brands (1 complete, 1 succeeded), wall 43s, products 0, stage wall sums clean/enrich/gates/score = 43/None/None/None s
- `scripts/products/reports/batch_run_summary_20260622_224600.txt`: 2 brands (2 complete, 2 succeeded), wall 17s, products 0, stage wall sums clean/enrich/gates/score = 17/None/None/None s
- `scripts/products/reports/batch_run_summary_20260622_225020.txt`: 28 brands (28 complete, 28 succeeded), wall 166s, products 0, stage wall sums clean/enrich/gates/score = 159/None/None/None s
- `scripts/products/reports/batch_run_summary_20260622_233302.txt`: 4 brands (4 complete, 4 succeeded), wall 39s, products 0, stage wall sums clean/enrich/gates/score = 39/None/None/None s
- `scripts/products/reports/batch_run_summary_20260622_233741.txt`: 1 brands (1 complete, 1 succeeded), wall 22s, products 0, stage wall sums clean/enrich/gates/score = 22/None/None/None s
- `scripts/products/reports/batch_run_summary_20260622_234512.txt`: 15 brands (15 complete, 15 succeeded), wall 89s, products 0, stage wall sums clean/enrich/gates/score = 89/None/None/None s
- `scripts/products/reports/batch_run_summary_20260622_235420.txt`: 6 brands (6 complete, 6 succeeded), wall 52s, products 0, stage wall sums clean/enrich/gates/score = 52/None/None/None s
- `scripts/products/reports/batch_run_summary_20260622_235549.txt`: 1 brands (1 complete, 1 succeeded), wall 6s, products 0, stage wall sums clean/enrich/gates/score = 6/None/None/None s
- `scripts/products/reports/batch_run_summary_20260623_000135.txt`: 10 brands (10 complete, 10 succeeded), wall 65s, products 0, stage wall sums clean/enrich/gates/score = 64/None/None/None s
- `scripts/products/reports/batch_run_summary_20260623_000347.txt`: 1 brands (1 complete, 1 succeeded), wall 22s, products 0, stage wall sums clean/enrich/gates/score = 22/None/None/None s
- `scripts/products/reports/batch_run_summary_20260623_004448.txt`: 28 brands (28 complete, 28 succeeded), wall 141s, products 0, stage wall sums clean/enrich/gates/score = 136/None/None/None s
- `scripts/products/reports/batch_run_summary_20260623_130402.txt`: 28 brands (28 complete, 28 succeeded), wall 208s, products 0, stage wall sums clean/enrich/gates/score = 198/None/None/None s
- `scripts/products/reports/batch_run_summary_20260623_130831.txt`: 28 brands (28 complete, 28 succeeded), wall 17005s, products 14193, stage wall sums clean/enrich/gates/score = 134/2117/31/79 s
- `scripts/products/reports/batch_run_summary_20260623_225046.txt`: 1 brands (0 complete, 0 succeeded), wall 2s, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260623_225633.txt`: 28 brands (28 complete, 28 succeeded), wall 2836s, products 14193, stage wall sums clean/enrich/gates/score = 148/2201/30/83 s
- `scripts/products/reports/batch_run_summary_20260624_222528.txt`: 28 brands (28 complete, 28 succeeded), wall 3121s, products 14193, stage wall sums clean/enrich/gates/score = 163/2316/32/94 s
- `scripts/products/reports/batch_run_summary_20260627_035958.txt`: 28 brands (28 complete, 28 succeeded), wall 2690s, products 14193, stage wall sums clean/enrich/gates/score = 136/2061/26/83 s
- `scripts/products/reports/batch_run_summary_20260628_052244.txt`: 28 brands (28 complete, 28 succeeded), wall 2696s, products 14193, stage wall sums clean/enrich/gates/score = 137/2066/28/82 s
- `scripts/products/reports/batch_run_summary_20260628_192100.txt`: 28 brands (28 complete, 28 succeeded), wall 2987s, products 14193, stage wall sums clean/enrich/gates/score = 158/2287/34/88 s
- `scripts/products/reports/batch_run_summary_20260630_131607.txt`: 28 brands (28 complete, 28 succeeded), wall 14477s, products 14193, stage wall sums clean/enrich/gates/score = 11846/2069/27/79 s
- `scripts/products/reports/batch_run_summary_20260701_010909.txt`: 28 brands (28 complete, 28 succeeded), wall 12302s, products 14193, stage wall sums clean/enrich/gates/score = 5261/6526/24/78 s
- `scripts/products/reports/batch_run_summary_20260703_033439.txt`: 28 brands (28 complete, 28 succeeded), wall 2610s, products 14193, stage wall sums clean/enrich/gates/score = 140/1919/26/79 s
- `scripts/products/reports/batch_run_summary_20260703_212044.txt`: 28 brands (28 complete, 28 succeeded), wall 6212s, products 14193, stage wall sums clean/enrich/gates/score = 142/4954/27/362 s
- `scripts/products/reports/batch_run_summary_20260704_122206.txt`: 1 brands (0 complete, 0 succeeded), wall 16s, products 0, stage wall sums clean/enrich/gates/score = 16/None/None/None s
- `scripts/products/reports/batch_run_summary_20260704_155626.txt`: 28 brands (28 complete, 28 succeeded), wall 3097s, products 14193, stage wall sums clean/enrich/gates/score = 132/1918/26/191 s
- `scripts/products/reports/batch_run_summary_20260704_220128.txt`: 28 brands (28 complete, 28 succeeded), wall 3082s, products 14193, stage wall sums clean/enrich/gates/score = 133/1910/27/185 s
- `scripts/products/reports/batch_run_summary_20260705_172529.txt`: 28 brands (28 complete, 28 succeeded), wall 3127s, products 14193, stage wall sums clean/enrich/gates/score = 137/1939/28/184 s
- `scripts/products/reports/batch_run_summary_20260706_030513.txt`: 28 brands (28 complete, 28 succeeded), wall 3057s, products 14193, stage wall sums clean/enrich/gates/score = 132/1881/29/182 s
- `scripts/products/reports/batch_run_summary_20260709_110912.txt`: 28 brands (28 complete, 28 succeeded), wall 3105s, products 14193, stage wall sums clean/enrich/gates/score = 138/1912/26/186 s
- `scripts/products/reports/batch_run_summary_20260710_134230.txt`: 1 brands (1 complete, 1 succeeded), wall 113s, products 794, stage wall sums clean/enrich/gates/score = None/105/1/7 s
- `scripts/products/reports/batch_run_summary_20260710_134719.txt`: 1 brands (1 complete, 1 succeeded), wall 114s, products 794, stage wall sums clean/enrich/gates/score = None/105/2/7 s
- `scripts/products/reports/batch_run_summary_20260710_140130.txt`: 7 brands (6 complete, 6 succeeded), wall 1156s, products 7116, stage wall sums clean/enrich/gates/score = None/818/13/57 s
- `scripts/products/reports/batch_run_summary_20260710_171707.txt`: 28 brands (28 complete, 28 succeeded), wall 3623s, products 14193, stage wall sums clean/enrich/gates/score = 141/2381/29/186 s
- `scripts/products/reports/batch_run_summary_20260712_050909.txt`: 28 brands (28 complete, 28 succeeded), wall 5177s, products 14193, stage wall sums clean/enrich/gates/score = 138/4255/26/165 s
- `scripts/products/reports/batch_run_summary_20260713_145808.txt`: 13 brands (12 complete, 12 succeeded), wall 1582s, products 8845, stage wall sums clean/enrich/gates/score = 84/1337/21/138 s
- `scripts/products/reports/batch_run_summary_20260713_163401.txt`: 28 brands (28 complete, 28 succeeded), wall 3333s, products 14193, stage wall sums clean/enrich/gates/score = 152/2090/29/188 s
- `scripts/products/reports/batch_run_summary_20260713_201829.txt`: 28 brands (28 complete, 28 succeeded), wall 3225s, products 14193, stage wall sums clean/enrich/gates/score = 143/1966/27/196 s
- `scripts/products/reports/batch_run_summary_20260713_215026.txt`: 1 brands (1 complete, 1 succeeded), wall 150s, products 839, stage wall sums clean/enrich/gates/score = 8/131/2/9 s
- `scripts/products/reports/batch_run_summary_20260713_225558.txt`: 3 brands (3 complete, 3 succeeded), wall 371s, products 1464, stage wall sums clean/enrich/gates/score = None/303/4/64 s
- `scripts/products/reports/batch_run_summary_20260713_230232.txt`: 1 brands (1 complete, 1 succeeded), wall 98s, products 794, stage wall sums clean/enrich/gates/score = None/90/1/7 s
- `scripts/products/reports/batch_run_summary_20260714_142121.txt`: 2 brands (0 complete, 0 succeeded), wall 304s, products 4049, stage wall sums clean/enrich/gates/score = 21/281/None/None s
- `scripts/products/reports/batch_run_summary_20260714_143441.txt`: 6 brands (5 complete, 5 succeeded), wall 507s, products 4902, stage wall sums clean/enrich/gates/score = 55/400/1/14 s
- `scripts/products/reports/batch_run_summary_20260715_013747.txt`: 1 brands (0 complete, 0 succeeded), wall 243s, products 0, stage wall sums clean/enrich/gates/score = 17/None/None/None s
- `scripts/products/reports/batch_run_summary_20260715_015402.txt`: 28 brands (21 complete, 21 succeeded), wall 2213s, products 14193, stage wall sums clean/enrich/gates/score = 147/2006/2/51 s
- `scripts/products/reports/batch_run_summary_20260715_091346.txt`: 7 brands (7 complete, 7 succeeded), wall 1557s, products 5078, stage wall sums clean/enrich/gates/score = 59/992/4/61 s
- `scripts/products/reports/batch_run_summary_20260715_103342.txt`: 28 brands (28 complete, 28 succeeded), wall 3009s, products 14193, stage wall sums clean/enrich/gates/score = 155/2271/7/111 s
- `scripts/products/reports/batch_run_summary_20260715_122451.txt`: 7 brands (7 complete, 7 succeeded), wall 557s, products 2421, stage wall sums clean/enrich/gates/score = None/473/1/81 s
- `scripts/products/reports/batch_run_summary_20260715_141131.txt`: 7 brands (7 complete, 7 succeeded), wall 550s, products 2421, stage wall sums clean/enrich/gates/score = None/468/1/80 s
- `scripts/products/reports/batch_run_summary_20260715_143508.txt`: 0 brands (0 complete, 0 succeeded), wall 4s, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260715_143526.txt`: 28 brands (28 complete, 28 succeeded), wall 2440s, products 14193, stage wall sums clean/enrich/gates/score = 145/2070/7/211 s
- `scripts/products/reports/batch_run_summary_20260716_142937.txt`: 28 brands (28 complete, 28 succeeded), wall 4860s, products 14193, stage wall sums clean/enrich/gates/score = 160/3651/238/807 s
- `scripts/products/reports/batch_run_summary_20260716_180113.txt`: 7 brands (6 complete, 6 succeeded), wall 6559s, products 7116, stage wall sums clean/enrich/gates/score = 66/6211/1/277 s
- `scripts/products/reports/batch_run_summary_20260716_201722.txt`: 28 brands (28 complete, 28 succeeded), wall 6184s, products 14193, stage wall sums clean/enrich/gates/score = None/1314/5/4859 s
- `scripts/products/reports/batch_run_summary_20260716_231047.txt`: 1 brands (0 complete, 0 succeeded), wall 86s, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260717_013903.txt`: 28 brands (28 complete, 28 succeeded), wall 1415s, products 14193, stage wall sums clean/enrich/gates/score = None/1246/8/156 s
- `scripts/products/reports/batch_run_summary_20260717_102108.txt`: 28 brands (28 complete, 28 succeeded), wall 1357s, products 14193, stage wall sums clean/enrich/gates/score = None/1197/8/146 s
- `scripts/products/reports/batch_run_summary_20260717_105709.txt`: 6 brands (5 complete, 5 succeeded), wall 420s, products 4902, stage wall sums clean/enrich/gates/score = 61/197/0/26 s
- `scripts/products/reports/batch_run_summary_20260717_113521.txt`: 28 brands (28 complete, 28 succeeded), wall 1528s, products 14193, stage wall sums clean/enrich/gates/score = 154/1212/9/145 s
- `scripts/products/reports/batch_run_summary_20260717_122515.txt`: 2 brands (0 complete, 0 succeeded), wall 1s, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260717_122543.txt`: 2 brands (2 complete, 2 succeeded), wall 493s, products 3053, stage wall sums clean/enrich/gates/score = 35/410/1/46 s
- `scripts/products/reports/batch_run_summary_20260717_125945.txt`: 28 brands (28 complete, 28 succeeded), wall 1419s, products 14193, stage wall sums clean/enrich/gates/score = 147/1127/6/134 s
- `scripts/products/reports/batch_run_summary_20260719_235807.txt`: 1 brands (0 complete, 0 succeeded), wall 1s, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260720_005529.txt`: 1 brands (0 complete, 0 succeeded), wall 1s, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260720_012904.txt`: 28 brands (28 complete, 28 succeeded), wall 1461s, products 14193, stage wall sums clean/enrich/gates/score = 151/1156/4/145 s
- `scripts/products/reports/batch_run_summary_20260720_022900.txt`: 1 brands (1 complete, 1 succeeded), wall 5s, products 0, stage wall sums clean/enrich/gates/score = None/None/0/4 s
- `scripts/products/reports/batch_run_summary_20260720_023132.txt`: 28 brands (28 complete, 28 succeeded), wall 181s, products 0, stage wall sums clean/enrich/gates/score = None/None/5/141 s
- `scripts/products/reports/batch_run_summary_20260720_103546.txt`: 28 brands (0 complete, 0 succeeded), wall 1362s, products 14193, stage wall sums clean/enrich/gates/score = 159/1191/None/None s
- `scripts/products/reports/batch_run_summary_20260720_124223.txt`: 28 brands (0 complete, 0 succeeded), wall 1375s, products 14193, stage wall sums clean/enrich/gates/score = 161/1202/None/None s
- `scripts/products/reports/batch_run_summary_20260720_133011.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260720_133020.txt`: 1 brands (0 complete, 0 succeeded), wall 8s, products 10, stage wall sums clean/enrich/gates/score = 2/6/None/None s
- `scripts/products/reports/batch_run_summary_20260720_133155.txt`: 1 brands (1 complete, 1 succeeded), wall 10s, products 10, stage wall sums clean/enrich/gates/score = 3/6/0/1 s
- `scripts/products/reports/batch_run_summary_20260720_164413.txt`: 28 brands (8 complete, 8 succeeded), wall 1352s, products 14193, stage wall sums clean/enrich/gates/score = 158/1176/1/3 s
- `scripts/products/reports/batch_run_summary_20260720_234708.txt`: 28 brands (28 complete, 28 succeeded), wall 2454s, products 14193, stage wall sums clean/enrich/gates/score = 159/1165/9/161 s
- `scripts/products/reports/batch_run_summary_20260721_184925.txt`: 28 brands (28 complete, 28 succeeded), wall 2650s, products 14193, stage wall sums clean/enrich/gates/score = 178/1255/10/169 s
- `scripts/products/reports/batch_run_summary_20260721_210649.txt`: 28 brands (28 complete, 28 succeeded), wall 2416s, products 14193, stage wall sums clean/enrich/gates/score = 159/1178/8/160 s
- `scripts/products/reports/batch_run_summary_20260722_212421.txt`: 7 brands (6 complete, 6 succeeded), wall 647s, products 7116, stage wall sums clean/enrich/gates/score = 79/496/3/66 s
- `scripts/products/reports/batch_run_summary_20260724_130244.txt`: 28 brands (28 complete, 28 succeeded), wall 1475s, products 14193, stage wall sums clean/enrich/gates/score = 156/1145/7/159 s
- `scripts/products/reports/batch_run_summary_20260724_142123.txt`: 28 brands (28 complete, 28 succeeded), wall 1477s, products 14193, stage wall sums clean/enrich/gates/score = 157/1150/4/161 s
- `scripts/products/reports/batch_run_summary_20260724_164659.txt`: 1 brands (1 complete, 1 succeeded), wall 23s, products 147, stage wall sums clean/enrich/gates/score = 3/17/0/3 s
- `scripts/products/reports/batch_run_summary_20260724_165215.txt`: 1 brands (1 complete, 1 succeeded), wall 18s, products 147, stage wall sums clean/enrich/gates/score = None/16/1/1 s
- `scripts/products/reports/batch_run_summary_20260724_165300.txt`: 2 brands (1 complete, 0 succeeded), wall 156s, products 4049, stage wall sums clean/enrich/gates/score = 16/119/1/17 s
- `scripts/products/reports/batch_run_summary_20260724_165515.txt`: 1 brands (0 complete, 0 succeeded), wall 18s, products 0, stage wall sums clean/enrich/gates/score = 17/None/None/None s
- `scripts/products/reports/batch_run_summary_20260724_165610.txt`: 2 brands (1 complete, 1 succeeded), wall 172s, products 4049, stage wall sums clean/enrich/gates/score = 23/128/1/19 s
- `scripts/products/reports/batch_run_summary_20260724_170544.txt`: 28 brands (28 complete, 28 succeeded), wall 1456s, products 14193, stage wall sums clean/enrich/gates/score = 150/1139/6/154 s
- `scripts/products/reports/batch_run_summary_20260724_193901.txt`: 2 brands (2 complete, 2 succeeded), wall 239s, products 1245, stage wall sums clean/enrich/gates/score = None/207/1/31 s
- `scripts/products/reports/batch_run_summary_20260724_200031.txt`: 28 brands (28 complete, 28 succeeded), wall 2434s, products 14193, stage wall sums clean/enrich/gates/score = 154/1147/5/155 s
- `scripts/products/reports/batch_run_summary_20260728_131904.txt`: 21 brands (20 complete, 20 succeeded), wall 1430s, products 12568, stage wall sums clean/enrich/gates/score = 149/1107/9/157 s
- `scripts/products/reports/batch_run_summary_20260728_171242.txt`: 28 brands (28 complete, 28 succeeded), wall 1480s, products 14193, stage wall sums clean/enrich/gates/score = 156/1151/6/159 s
- `scripts/products/reports/batch_run_summary_20260728_182253.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260728_182331.txt`: 6 brands (5 complete, 5 succeeded), wall 577s, products 6992, stage wall sums clean/enrich/gates/score = 64/446/2/62 s
- `scripts/products/reports/batch_run_summary_20260728_183615.txt`: 5 brands (4 complete, 4 succeeded), wall 241s, products 4778, stage wall sums clean/enrich/gates/score = 29/175/2/24 s
- `scripts/products/reports/batch_run_summary_20260728_184300.txt`: 20 brands (20 complete, 20 succeeded), wall 1370s, products 13389, stage wall sums clean/enrich/gates/score = 131/1075/10/147 s
- `scripts/products/reports/batch_run_summary_20260728_191442.txt`: 28 brands (28 complete, 28 succeeded), wall 1323s, products 14193, stage wall sums clean/enrich/gates/score = None/1149/9/156 s
- `scripts/products/reports/batch_run_summary_20260728_200015.txt`: 20 brands (20 complete, 20 succeeded), wall 1210s, products 13389, stage wall sums clean/enrich/gates/score = None/1051/7/149 s
- `scripts/products/reports/batch_run_summary_20260729_111658.txt`: 28 brands (28 complete, 28 succeeded), wall 1507s, products 14193, stage wall sums clean/enrich/gates/score = 159/1172/9/160 s
- `scripts/products/reports/batch_run_summary_20260730_035008.txt`: 14 brands (0 complete, 0 succeeded), wall 5s, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260730_052538.txt`: 28 brands (28 complete, 28 succeeded), wall 2463s, products 14193, stage wall sums clean/enrich/gates/score = 151/1148/8/159 s
- `scripts/products/reports/batch_run_summary_20260804_124910.txt`: 28 brands (0 complete, 0 succeeded), wall 8s, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260804_125224.txt`: 8 brands (0 complete, 0 succeeded), wall 3s, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260804_125910.txt`: 6 brands (0 complete, 0 succeeded), wall 2s, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260804_131821.txt`: 28 brands (28 complete, 28 succeeded), wall 2735s, products 14193, stage wall sums clean/enrich/gates/score = 171/1293/12/181 s
- `scripts/products/reports/batch_run_summary_20260804_145636.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260804_145706.txt`: 1 brands (1 complete, 1 succeeded), wall 19s, products 196, stage wall sums clean/enrich/gates/score = None/16/1/2 s
- `scripts/products/reports/batch_run_summary_20260804_150111.txt`: 7 brands (7 complete, 7 succeeded), wall 719s, products 4714, stage wall sums clean/enrich/gates/score = None/625/3/87 s
- `scripts/products/reports/batch_run_summary_20260805_134559.txt`: 0 brands (0 complete, 0 succeeded), wall 2s, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260805_134615.txt`: 8 brands (0 complete, 0 succeeded), wall 3s, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260805_150712.txt`: 28 brands (0 complete, 0 succeeded), wall 8s, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260805_150829.txt`: 28 brands (28 complete, 28 succeeded), wall 233s, products 0, stage wall sums clean/enrich/gates/score = None/None/8/180 s
- `scripts/products/reports/batch_run_summary_20260805_155257.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260805_155318.txt`: 28 brands (28 complete, 28 succeeded), wall 228s, products 0, stage wall sums clean/enrich/gates/score = None/None/9/176 s
- `scripts/products/reports/batch_run_summary_20260805_162544.txt`: 28 brands (28 complete, 28 succeeded), wall 231s, products 0, stage wall sums clean/enrich/gates/score = None/None/6/179 s
- `scripts/products/reports/batch_run_summary_20260806_003706.txt`: 6 brands (0 complete, 0 succeeded), wall 2s, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260806_003959.txt`: 7 brands (0 complete, 0 succeeded), wall 2s, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260806_011734.txt`: 28 brands (28 complete, 28 succeeded), wall 1523s, products 14193, stage wall sums clean/enrich/gates/score = 156/1187/9/165 s
- `scripts/products/reports/batch_run_summary_20260806_110704.txt`: 7 brands (6 complete, 6 succeeded), wall 669s, products 7116, stage wall sums clean/enrich/gates/score = 80/507/4/76 s
- `scripts/products/reports/batch_run_summary_20260806_111934.txt`: 28 brands (28 complete, 28 succeeded), wall 2434s, products 14193, stage wall sums clean/enrich/gates/score = 154/1166/7/157 s
- `scripts/products/reports/batch_run_summary_20260806_134204.txt`: 28 brands (28 complete, 28 succeeded), wall 2461s, products 14193, stage wall sums clean/enrich/gates/score = 168/1191/8/166 s
- `scripts/products/reports/batch_run_summary_20260806_170411.txt`: 1 brands (0 complete, 0 succeeded), wall 6s, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260806_171833.txt`: 28 brands (28 complete, 28 succeeded), wall 2450s, products 14193, stage wall sums clean/enrich/gates/score = 155/1164/6/158 s
- `scripts/products/reports/batch_run_summary_20260807_000524.txt`: 1 brands (0 complete, 0 succeeded), wall 19s, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260807_005004.txt`: 28 brands (28 complete, 28 succeeded), wall 1480s, products 14193, stage wall sums clean/enrich/gates/score = 153/1155/6/158 s
- `scripts/products/reports/batch_run_summary_20260807_135252.txt`: 28 brands (28 complete, 28 succeeded), wall 5784s, products 14193, stage wall sums clean/enrich/gates/score = 178/2860/9/190 s
- `scripts/products/reports/batch_run_summary_20260807_233250.txt`: 1 brands (0 complete, 0 succeeded), wall 31s, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260808_051851.txt`: 6 brands (5 complete, 5 succeeded), wall 242s, products 4902, stage wall sums clean/enrich/gates/score = None/180/2/26 s
- `scripts/products/reports/batch_run_summary_20260808_072545.txt`: 28 brands (28 complete, 28 succeeded), wall 2686s, products 14193, stage wall sums clean/enrich/gates/score = 171/1292/11/178 s
- `scripts/products/reports/batch_run_summary_20260808_135813.txt`: 28 brands (24 complete, 24 succeeded), wall 3163s, products 14193, stage wall sums clean/enrich/gates/score = 809/928/4/105 s
- `scripts/products/reports/batch_run_summary_20260808_183235.txt`: 28 brands (28 complete, 28 succeeded), wall 2416s, products 14193, stage wall sums clean/enrich/gates/score = 157/1150/7/161 s
- `scripts/products/reports/batch_run_summary_20260813_130117.txt`: 28 brands (28 complete, 28 succeeded), wall 2652s, products 14193, stage wall sums clean/enrich/gates/score = 169/1246/12/176 s
- `scripts/products/reports/batch_run_summary_20260818_231755.txt`: 28 brands (28 complete, 28 succeeded), wall 2748s, products 14193, stage wall sums clean/enrich/gates/score = 181/1294/12/183 s
- `scripts/products/reports/batch_run_summary_20260819_042836.txt`: 12 brands (11 complete, 11 succeeded), wall 982s, products 8006, stage wall sums clean/enrich/gates/score = 99/726/4/108 s
- `scripts/products/reports/batch_run_summary_20260819_044503.txt`: 28 brands (28 complete, 28 succeeded), wall 1523s, products 14193, stage wall sums clean/enrich/gates/score = 153/1184/9/169 s
- `scripts/products/reports/batch_run_summary_20260819_151540.txt`: 28 brands (28 complete, 28 succeeded), wall 1619s, products 14193, stage wall sums clean/enrich/gates/score = 167/1256/10/175 s
- `scripts/products/reports/batch_run_summary_20260819_220538.txt`: 28 brands (28 complete, 28 succeeded), wall 171s, products 0, stage wall sums clean/enrich/gates/score = 167/None/None/None s
- `scripts/products/reports/batch_run_summary_20260820_000344.txt`: 28 brands (28 complete, 28 succeeded), wall 180s, products 0, stage wall sums clean/enrich/gates/score = 175/None/None/None s
- `scripts/products/reports/batch_run_summary_20260820_000921.txt`: 9 brands (9 complete, 9 succeeded), wall 34s, products 0, stage wall sums clean/enrich/gates/score = 32/None/None/None s
- `scripts/products/reports/batch_run_summary_20260820_001935.txt`: 10 brands (9 complete, 9 succeeded), wall 548s, products 5384, stage wall sums clean/enrich/gates/score = 74/294/2/44 s
- `scripts/products/reports/batch_run_summary_20260820_003259.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260820_003312.txt`: 4 brands (4 complete, 4 succeeded), wall 11s, products 0, stage wall sums clean/enrich/gates/score = 10/None/None/None s
- `scripts/products/reports/batch_run_summary_20260820_003429.txt`: 9 brands (8 complete, 8 succeeded), wall 219s, products 1219, stage wall sums clean/enrich/gates/score = None/194/1/21 s
- `scripts/products/reports/batch_run_summary_20260820_003822.txt`: 1 brands (1 complete, 1 succeeded), wall 54s, products 278, stage wall sums clean/enrich/gates/score = None/47/0/7 s
- `scripts/products/reports/batch_run_summary_20260820_005154.txt`: 5 brands (5 complete, 5 succeeded), wall 18s, products 0, stage wall sums clean/enrich/gates/score = 17/None/None/None s
- `scripts/products/reports/batch_run_summary_20260820_005221.txt`: 9 brands (9 complete, 9 succeeded), wall 227s, products 1219, stage wall sums clean/enrich/gates/score = None/195/1/28 s
- `scripts/products/reports/batch_run_summary_20260820_011214.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260820_011232.txt`: 3 brands (3 complete, 3 succeeded), wall 63s, products 374, stage wall sums clean/enrich/gates/score = 9/47/1/6 s
- `scripts/products/reports/batch_run_summary_20260820_011607.txt`: 1 brands (1 complete, 1 succeeded), wall 23s, products 197, stage wall sums clean/enrich/gates/score = None/20/0/3 s
- `scripts/products/reports/batch_run_summary_20260820_012000.txt`: 1 brands (1 complete, 1 succeeded), wall 26s, products 197, stage wall sums clean/enrich/gates/score = 3/20/0/3 s
- `scripts/products/reports/batch_run_summary_20260820_012238.txt`: 1 brands (1 complete, 1 succeeded), wall 23s, products 197, stage wall sums clean/enrich/gates/score = None/19/0/3 s
- `scripts/products/reports/batch_run_summary_20260820_012938.txt`: 1 brands (1 complete, 1 succeeded), wall 3s, products 0, stage wall sums clean/enrich/gates/score = 3/None/None/None s
- `scripts/products/reports/batch_run_summary_20260820_012942.txt`: 3 brands (3 complete, 3 succeeded), wall 36s, products 302, stage wall sums clean/enrich/gates/score = None/30/1/5 s
- `scripts/products/reports/batch_run_summary_20260820_013644.txt`: 2 brands (2 complete, 2 succeeded), wall 44s, products 218, stage wall sums clean/enrich/gates/score = 7/33/0/4 s
- `scripts/products/reports/batch_run_summary_20260820_015251.txt`: 4 brands (4 complete, 4 succeeded), wall 175s, products 805, stage wall sums clean/enrich/gates/score = 15/137/1/19 s
- `scripts/products/reports/batch_run_summary_20260820_015924.txt`: 2 brands (2 complete, 2 succeeded), wall 85s, products 475, stage wall sums clean/enrich/gates/score = 8/66/2/9 s
- `scripts/products/reports/batch_run_summary_20260820_020735.txt`: 3 brands (3 complete, 3 succeeded), wall 71s, products 415, stage wall sums clean/enrich/gates/score = 10/52/0/9 s
- `scripts/products/reports/batch_run_summary_20260820_021726.txt`: 1 brands (1 complete, 1 succeeded), wall 15s, products 102, stage wall sums clean/enrich/gates/score = 3/10/0/2 s
- `scripts/products/reports/batch_run_summary_20260820_023536.txt`: 9 brands (9 complete, 9 succeeded), wall 228s, products 1219, stage wall sums clean/enrich/gates/score = None/198/1/29 s
- `scripts/products/reports/batch_run_summary_20260820_030118.txt`: 7 brands (6 complete, 6 succeeded), wall 443s, products 3174, stage wall sums clean/enrich/gates/score = None/137/1/21 s
- `scripts/products/reports/batch_run_summary_20260820_032211.txt`: 5 brands (5 complete, 5 succeeded), wall 430s, products 2746, stage wall sums clean/enrich/gates/score = None/371/3/55 s
- `scripts/products/reports/batch_run_summary_20260820_042152.txt`: 1 brands (1 complete, 1 succeeded), wall 48s, products 197, stage wall sums clean/enrich/gates/score = None/41/0/7 s
- `scripts/products/reports/batch_run_summary_20260820_042209.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260820_042230.txt`: 9 brands (9 complete, 9 succeeded), wall 278s, products 5436, stage wall sums clean/enrich/gates/score = None/239/3/34 s
- `scripts/products/reports/batch_run_summary_20260820_043217.txt`: 9 brands (9 complete, 9 succeeded), wall 207s, products 1219, stage wall sums clean/enrich/gates/score = None/176/2/29 s
- `scripts/products/reports/batch_run_summary_20260820_043856.txt`: 1 brands (1 complete, 1 succeeded), wall 4s, products 0, stage wall sums clean/enrich/gates/score = 4/None/None/None s
- `scripts/products/reports/batch_run_summary_20260820_043919.txt`: 9 brands (9 complete, 9 succeeded), wall 205s, products 1219, stage wall sums clean/enrich/gates/score = None/176/2/27 s
- `scripts/products/reports/batch_run_summary_20260820_045306.txt`: 1 brands (1 complete, 1 succeeded), wall 13s, products 102, stage wall sums clean/enrich/gates/score = None/11/0/2 s
- `scripts/products/reports/batch_run_summary_20260820_050527.txt`: 1 brands (1 complete, 1 succeeded), wall 14s, products 102, stage wall sums clean/enrich/gates/score = 2/10/0/2 s
- `scripts/products/reports/batch_run_summary_20260820_051014.txt`: 1 brands (1 complete, 1 succeeded), wall 14s, products 102, stage wall sums clean/enrich/gates/score = 3/10/0/1 s
- `scripts/products/reports/batch_run_summary_20260820_051611.txt`: 1 brands (1 complete, 1 succeeded), wall 14s, products 102, stage wall sums clean/enrich/gates/score = 3/10/0/1 s
- `scripts/products/reports/batch_run_summary_20260820_054025.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260820_054115.txt`: 9 brands (8 complete, 8 succeeded), wall 232s, products 1219, stage wall sums clean/enrich/gates/score = 26/176/1/27 s
- `scripts/products/reports/batch_run_summary_20260820_054922.txt`: 1 brands (1 complete, 1 succeeded), wall 8s, products 61, stage wall sums clean/enrich/gates/score = 2/5/0/1 s
- `scripts/products/reports/batch_run_summary_20260820_055631.txt`: 1 brands (1 complete, 1 succeeded), wall 19s, products 91, stage wall sums clean/enrich/gates/score = 3/13/1/2 s
- `scripts/products/reports/batch_run_summary_20260820_055657.txt`: 9 brands (9 complete, 9 succeeded), wall 233s, products 1219, stage wall sums clean/enrich/gates/score = 27/176/1/27 s
- `scripts/products/reports/batch_run_summary_20260820_061110.txt`: 1 brands (1 complete, 1 succeeded), wall 51s, products 197, stage wall sums clean/enrich/gates/score = 4/40/0/7 s
- `scripts/products/reports/batch_run_summary_20260820_121149.txt`: 23 brands (22 complete, 22 succeeded), wall 1518s, products 11962, stage wall sums clean/enrich/gates/score = 144/1143/9/181 s
- `scripts/products/reports/batch_run_summary_20260821_151121.txt`: 10 brands (9 complete, 9 succeeded), wall 817s, products 7598, stage wall sums clean/enrich/gates/score = 91/667/4/49 s
- `scripts/products/reports/batch_run_summary_20260822_210651.txt`: 37 brands (37 complete, 37 succeeded), wall 1874s, products 15412, stage wall sums clean/enrich/gates/score = 202/1432/8/215 s
- `scripts/products/reports/batch_run_summary_20260824_115034.txt`: 37 brands (37 complete, 37 succeeded), wall 2246s, products 15412, stage wall sums clean/enrich/gates/score = 206/1674/12/342 s
- `scripts/products/reports/batch_run_summary_20260825_041153.txt`: 37 brands (37 complete, 37 succeeded), wall 3302s, products 15412, stage wall sums clean/enrich/gates/score = 190/1590/8/348 s
- `scripts/products/reports/batch_run_summary_20260825_143729.txt`: 37 brands (37 complete, 35 succeeded), wall 2223s, products 15412, stage wall sums clean/enrich/gates/score = 216/1648/10/339 s
- `scripts/products/reports/batch_run_summary_20260825_155756.txt`: 2 brands (2 complete, 2 succeeded), wall 68s, products 0, stage wall sums clean/enrich/gates/score = None/None/1/63 s
- `scripts/products/reports/batch_run_summary_20260825_155957.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260825_161350.txt`: 1 brands (1 complete, 1 succeeded), wall 176s, products 4049, stage wall sums clean/enrich/gates/score = 18/130/0/28 s
- `scripts/products/reports/batch_run_summary_20260825_223640.txt`: 37 brands (37 complete, 37 succeeded), wall 2367s, products 15412, stage wall sums clean/enrich/gates/score = 217/1748/14/374 s
- `scripts/products/reports/batch_run_summary_20260825_233522.txt`: 1 brands (1 complete, 1 succeeded), wall 9s, products 0, stage wall sums clean/enrich/gates/score = None/None/1/7 s
- `scripts/products/reports/batch_run_summary_20260825_235928.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260826_011538.txt`: 14 brands (14 complete, 14 succeeded), wall 1623s, products 12490, stage wall sums clean/enrich/gates/score = None/1300/10/306 s
- `scripts/products/reports/batch_run_summary_20260827_102252.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260827_111359.txt`: 20 brands (20 complete, 20 succeeded), wall 1702s, products 6041, stage wall sums clean/enrich/gates/score = 86/658/5/124 s
- `scripts/products/reports/batch_run_summary_20260903_163626.txt`: 37 brands (37 complete, 37 succeeded), wall 433s, products 0, stage wall sums clean/enrich/gates/score = None/None/14/364 s
- `scripts/products/reports/batch_run_summary_20260908_105712.txt`: 38 brands (38 complete, 38 succeeded), wall 2252s, products 15415, stage wall sums clean/enrich/gates/score = 193/1675/10/366 s
- `scripts/products/reports/batch_run_summary_20260908_124224.txt`: 13 brands (13 complete, 13 succeeded), wall 1142s, products 9251, stage wall sums clean/enrich/gates/score = None/915/5/220 s
- `scripts/products/reports/batch_run_summary_20260910_035538.txt`: 38 brands (38 complete, 38 succeeded), wall 3943s, products 15415, stage wall sums clean/enrich/gates/score = 207/1732/10/375 s
- `scripts/products/reports/batch_run_summary_20260911_125828.txt`: 4 brands (0 complete, 0 succeeded), wall 1s, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260911_125939.txt`: 4 brands (4 complete, 4 succeeded), wall 570s, products 2811, stage wall sums clean/enrich/gates/score = 38/413/2/116 s
- `scripts/products/reports/batch_run_summary_20260911_133024.txt`: 10 brands (10 complete, 10 succeeded), wall 1024s, products 7598, stage wall sums clean/enrich/gates/score = 84/760/5/172 s
- `scripts/products/reports/batch_run_summary_20260912_045003.txt`: 39 brands (39 complete, 39 succeeded), wall 4994s, products 15419, stage wall sums clean/enrich/gates/score = 196/1712/9/378 s
- `scripts/products/reports/batch_run_summary_20260913_020406.txt`: 38 brands (38 complete, 38 succeeded), wall 4875s, products 15418, stage wall sums clean/enrich/gates/score = 205/1729/12/378 s
- `scripts/products/reports/batch_run_summary_20260914_183533.txt`: 2 brands (1 complete, 1 succeeded), wall 79s, products 91, stage wall sums clean/enrich/gates/score = None/18/0/5 s
- `scripts/products/reports/batch_run_summary_20260914_191403.txt`: 31 brands (28 complete, 28 succeeded), wall 2168s, products 14346, stage wall sums clean/enrich/gates/score = 194/1184/6/266 s
- `scripts/products/reports/batch_run_summary_20260914_202021.txt`: 20 brands (19 complete, 19 succeeded), wall 1688s, products 9751, stage wall sums clean/enrich/gates/score = 139/1202/6/300 s
- `scripts/products/reports/batch_run_summary_20260915_013125.txt`: 37 brands (35 complete, 35 succeeded), wall 2234s, products 15412, stage wall sums clean/enrich/gates/score = 201/1338/9/293 s
- `scripts/products/reports/batch_run_summary_20260915_064146.txt`: 37 brands (37 complete, 37 succeeded), wall 2277s, products 15412, stage wall sums clean/enrich/gates/score = 194/1689/6/378 s
- `scripts/products/reports/batch_run_summary_20260915_173939.txt`: 10 brands (9 complete, 9 succeeded), wall 584s, products 5384, stage wall sums clean/enrich/gates/score = 78/352/2/71 s
- `scripts/products/reports/batch_run_summary_20260915_211309.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260915_235300.txt`: 10 brands (9 complete, 9 succeeded), wall 801s, products 5384, stage wall sums clean/enrich/gates/score = 78/371/0/72 s
- `scripts/products/reports/batch_run_summary_20260916_002353.txt`: 2 brands (1 complete, 1 succeeded), wall 166s, products 91, stage wall sums clean/enrich/gates/score = 22/20/0/5 s
- `scripts/products/reports/batch_run_summary_20260916_002612.txt`: 2 brands (1 complete, 1 succeeded), wall 47s, products 91, stage wall sums clean/enrich/gates/score = 22/20/0/5 s
- `scripts/products/reports/batch_run_summary_20260916_004258.txt`: 37 brands (37 complete, 37 succeeded), wall 2522s, products 15412, stage wall sums clean/enrich/gates/score = 188/1887/9/427 s
- `scripts/products/reports/batch_run_summary_20260916_021505.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260916_021950.txt`: 37 brands (37 complete, 37 succeeded), wall 517s, products 0, stage wall sums clean/enrich/gates/score = None/None/8/455 s
- `scripts/products/reports/batch_run_summary_20260916_024949.txt`: 38 brands (38 complete, 38 succeeded), wall 3002s, products 15418, stage wall sums clean/enrich/gates/score = None/1840/6/422 s
- `scripts/products/reports/batch_run_summary_20260916_122219.txt`: 37 brands (36 complete, 36 succeeded), wall 2780s, products 15412, stage wall sums clean/enrich/gates/score = 218/1919/12/374 s
- `scripts/products/reports/batch_run_summary_20260916_144405.txt`: 10 brands (9 complete, 9 succeeded), wall 1025s, products 7598, stage wall sums clean/enrich/gates/score = 76/872/5/67 s
- `scripts/products/reports/batch_run_summary_20260916_161754.txt`: 7 brands (7 complete, 7 succeeded), wall 453s, products 5127, stage wall sums clean/enrich/gates/score = 40/352/0/60 s
- `scripts/products/reports/batch_run_summary_20260916_164939.txt`: 34 brands (33 complete, 33 succeeded), wall 2754s, products 14891, stage wall sums clean/enrich/gates/score = 205/2073/10/453 s
- `scripts/products/reports/batch_run_summary_20260916_223635.txt`: 37 brands (37 complete, 37 succeeded), wall 2642s, products 15412, stage wall sums clean/enrich/gates/score = 194/1984/9/442 s
- `scripts/products/reports/batch_run_summary_20260916_233739.txt`: 37 brands (37 complete, 37 succeeded), wall 2439s, products 15412, stage wall sums clean/enrich/gates/score = None/1979/7/448 s
- `scripts/products/reports/batch_run_summary_20260917_062143.txt`: 37 brands (37 complete, 37 succeeded), wall 2494s, products 15412, stage wall sums clean/enrich/gates/score = None/2009/11/465 s
- `scripts/products/reports/batch_run_summary_20260917_121921.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20260917_124532.txt`: 37 brands (37 complete, 37 succeeded), wall 2599s, products 15412, stage wall sums clean/enrich/gates/score = None/2100/10/481 s
- `scripts/products/reports/batch_run_summary_20260917_140925.txt`: 37 brands (37 complete, 37 succeeded), wall 2665s, products 15412, stage wall sums clean/enrich/gates/score = None/2142/11/505 s
- `scripts/products/reports/batch_run_summary_20260918_101225.txt`: 37 brands (37 complete, 37 succeeded), wall 2746s, products 15412, stage wall sums clean/enrich/gates/score = 201/2063/14/460 s
- `scripts/products/reports/batch_run_summary_20260918_202140.txt`: 37 brands (37 complete, 37 succeeded), wall 2783s, products 15412, stage wall sums clean/enrich/gates/score = 204/2085/8/477 s
- `scripts/products/reports/batch_run_summary_20260919_031303.txt`: 38 brands (38 complete, 38 succeeded), wall 5569s, products 15421, stage wall sums clean/enrich/gates/score = 198/2001/5/452 s
- `scripts/products/reports/batch_run_summary_20260921_025937.txt`: 37 brands (24 complete, 24 succeeded), wall 2447s, products 15412, stage wall sums clean/enrich/gates/score = 201/1902/4/150 s
- `scripts/products/reports/batch_run_summary_20260921_133329.txt`: 1 brands (1 complete, 1 succeeded), wall 94s, products 653, stage wall sums clean/enrich/gates/score = 6/76/1/11 s
- `scripts/products/reports/batch_run_summary_20260921_133519.txt`: 38 brands (38 complete, 38 succeeded), wall 2665s, products 15421, stage wall sums clean/enrich/gates/score = 191/1942/11/518 s
- `scripts/products/reports/batch_run_summary_20260921_163556.txt`: 37 brands (37 complete, 37 succeeded), wall 2771s, products 15412, stage wall sums clean/enrich/gates/score = 194/2017/13/541 s
- `scripts/products/reports/batch_run_summary_20260921_183859.txt`: 37 brands (37 complete, 37 succeeded), wall 2773s, products 15412, stage wall sums clean/enrich/gates/score = 197/2014/12/547 s
- `scripts/products/reports/batch_run_summary_20260921_202924.txt`: 37 brands (37 complete, 37 succeeded), wall 2865s, products 15412, stage wall sums clean/enrich/gates/score = 195/2087/11/565 s
- `scripts/products/reports/batch_run_summary_20260922_103939.txt`: 10 brands (9 complete, 9 succeeded), wall 1030s, products 7598, stage wall sums clean/enrich/gates/score = 86/859/5/77 s
- `scripts/products/reports/batch_run_summary_20260922_120941.txt`: 1 brands (0 complete, 0 succeeded), wall 3s, products 0, stage wall sums clean/enrich/gates/score = 3/None/None/None s
- `scripts/products/reports/batch_run_summary_20260922_130539.txt`: 37 brands (37 complete, 37 succeeded), wall 2824s, products 15412, stage wall sums clean/enrich/gates/score = 192/2019/4/605 s
- `scripts/products/reports/batch_run_summary_20260929_031838.txt`: 37 brands (37 complete, 37 succeeded), wall 3300s, products 15412, stage wall sums clean/enrich/gates/score = 245/2051/22/974 s
- `scripts/products/reports/batch_run_summary_20260929_044400.txt`: 1 brands (1 complete, 1 succeeded), wall 7s, products 9, stage wall sums clean/enrich/gates/score = 4/2/0/1 s
- `scripts/products/reports/batch_run_summary_20260929_045419.txt`: 38 brands (38 complete, 38 succeeded), wall 4083s, products 15421, stage wall sums clean/enrich/gates/score = 248/2059/21/981 s
- `scripts/products/reports/batch_run_summary_20260929_112122.txt`: 37 brands (37 complete, 37 succeeded), wall 3318s, products 15412, stage wall sums clean/enrich/gates/score = 251/2068/24/968 s
- `scripts/products/reports/batch_run_summary_20260929_151416.txt`: 38 brands (38 complete, 38 succeeded), wall 3397s, products 15421, stage wall sums clean/enrich/gates/score = 254/2117/26/985 s
- `scripts/products/reports/batch_run_summary_20261001_231906.txt`: 38 brands (38 complete, 38 succeeded), wall 3704s, products 15421, stage wall sums clean/enrich/gates/score = 283/2340/24/1047 s
- `scripts/products/reports/batch_run_summary_20261002_234041.txt`: 11 brands (10 complete, 10 succeeded), wall 1697s, products 8213, stage wall sums clean/enrich/gates/score = 109/1166/9/410 s
- `scripts/products/reports/batch_run_summary_20261003_003215.txt`: 38 brands (38 complete, 38 succeeded), wall 3583s, products 15421, stage wall sums clean/enrich/gates/score = 261/2215/24/1075 s
- `scripts/products/reports/batch_run_summary_20261003_084815.txt`: 38 brands (38 complete, 38 succeeded), wall 1168s, products 9, stage wall sums clean/enrich/gates/score = 4/4/42/1066 s
- `scripts/products/reports/batch_run_summary_20261003_123535.txt`: 1 brands (0 complete, 0 succeeded), wall 0s, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20261003_123945.txt`: 38 brands (38 complete, 38 succeeded), wall 3675s, products 15421, stage wall sums clean/enrich/gates/score = 261/2311/24/1071 s
- `scripts/products/reports/batch_run_summary_20261003_161037.txt`: 38 brands (38 complete, 38 succeeded), wall 3458s, products 15421, stage wall sums clean/enrich/gates/score = 3/2307/28/1071 s
- `scripts/products/reports/batch_run_summary_20261003_171418.txt`: 37 brands (37 complete, 37 succeeded), wall 3657s, products 15412, stage wall sums clean/enrich/gates/score = 253/2310/19/1067 s
- `scripts/products/reports/batch_run_summary_20261004_073713.txt`: 38 brands (38 complete, 38 succeeded), wall 3678s, products 15421, stage wall sums clean/enrich/gates/score = 254/2312/28/1074 s
- `scripts/products/reports/batch_run_summary_20261004_134709.txt`: 38 brands (38 complete, 38 succeeded), wall 5317s, products 15421, stage wall sums clean/enrich/gates/score = 285/2431/28/1106 s
- `scripts/products/reports/batch_run_summary_20261004_173701.txt`: 38 brands (38 complete, 38 succeeded), wall 4530s, products 15421, stage wall sums clean/enrich/gates/score = 261/2373/26/1056 s
- `scripts/products/reports/batch_run_summary_20261005_145737.txt`: 38 brands (38 complete, 38 succeeded), wall 4086s, products 15421, stage wall sums clean/enrich/gates/score = 267/2523/23/1265 s
- `scripts/products/reports/batch_run_summary_20261005_164122.txt`: 38 brands (38 complete, 38 succeeded), wall 1351s, products 9, stage wall sums clean/enrich/gates/score = 4/4/38/1249 s
- `scripts/products/reports/batch_run_summary_20261005_194817.txt`: 38 brands (38 complete, 38 succeeded), wall 3827s, products 15421, stage wall sums clean/enrich/gates/score = 250/2384/25/1158 s
- `scripts/products/reports/batch_run_summary_20261006_002121.txt`: 38 brands (38 complete, 38 succeeded), wall 3893s, products 15421, stage wall sums clean/enrich/gates/score = 262/2453/26/1143 s
- `scripts/products/reports/batch_run_summary_20261006_070547.txt`: 38 brands (38 complete, 38 succeeded), wall 3856s, products 15421, stage wall sums clean/enrich/gates/score = 263/2433/24/1130 s
- `scripts/products/reports/batch_run_summary_20261006_172922.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20261006_195549.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20261006_204250.txt`: 38 brands (38 complete, 38 succeeded), wall 4040s, products 15421, stage wall sums clean/enrich/gates/score = 276/2542/28/1187 s
- `scripts/products/reports/batch_run_summary_20261007_071313.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20261007_081335.txt`: 38 brands (38 complete, 38 succeeded), wall 4014s, products 15421, stage wall sums clean/enrich/gates/score = 266/2541/27/1172 s
- `scripts/products/reports/batch_run_summary_20261007_191917.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20261007_193303.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20261007_215802.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20261007_224400.txt`: 38 brands (38 complete, 38 succeeded), wall 3893s, products 15421, stage wall sums clean/enrich/gates/score = 267/2443/26/1150 s
- `scripts/products/reports/batch_run_summary_20261008_013616.txt`: 38 brands (38 complete, 38 succeeded), wall 3892s, products 15421, stage wall sums clean/enrich/gates/score = 264/2437/21/1163 s
- `scripts/products/reports/batch_run_summary_20261008_115919.txt`: 19 brands (19 complete, 19 succeeded), wall 2779s, products 9751, stage wall sums clean/enrich/gates/score = 158/1619/18/981 s
- `scripts/products/reports/batch_run_summary_20261008_131655.txt`: 19 brands (19 complete, 19 succeeded), wall 5249s, products 5670, stage wall sums clean/enrich/gates/score = 117/3922/64/330 s
- `scripts/products/reports/batch_run_summary_20261008_194640.txt`: 37 brands (37 complete, 37 succeeded), wall 16512s, products 15412, stage wall sums clean/enrich/gates/score = 301/10598/30/5572 s
- `scripts/products/reports/batch_run_summary_20261009_031839.txt`: 38 brands (38 complete, 38 succeeded), wall 5581s, products 15421, stage wall sums clean/enrich/gates/score = 260/2448/24/1143 s
- `scripts/products/reports/batch_run_summary_20261012_002522.txt`: 0 brands (0 complete, 0 succeeded), wall 14s, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20261012_013820.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20261012_023903.txt`: 27 brands (26 complete, 26 succeeded), wall 3244s, products 12793, stage wall sums clean/enrich/gates/score = 200/1986/20/1010 s
- `scripts/products/reports/batch_run_summary_20261012_042526.txt`: 38 brands (38 complete, 38 succeeded), wall 3798s, products 15421, stage wall sums clean/enrich/gates/score = 255/2374/27/1134 s
- `scripts/products/reports/batch_run_summary_20261012_065155.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20261012_072519.txt`: 38 brands (38 complete, 38 succeeded), wall 3815s, products 15421, stage wall sums clean/enrich/gates/score = 260/2391/22/1136 s
- `scripts/products/reports/batch_run_summary_20261012_163253.txt`: 38 brands (38 complete, 38 succeeded), wall 4097s, products 15421, stage wall sums clean/enrich/gates/score = 283/2568/24/1210 s
- `scripts/products/reports/batch_run_summary_20261012_185447.txt`: 38 brands (38 complete, 38 succeeded), wall 3860s, products 15421, stage wall sums clean/enrich/gates/score = 254/2425/25/1145 s
- `scripts/products/reports/batch_run_summary_20261012_221949.txt`: 38 brands (38 complete, 38 succeeded), wall 3846s, products 15421, stage wall sums clean/enrich/gates/score = 254/2411/26/1146 s
- `scripts/products/reports/batch_run_summary_20261013_014020.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20261013_021138.txt`: 38 brands (38 complete, 38 succeeded), wall 4002s, products 15426, stage wall sums clean/enrich/gates/score = 268/2521/22/1184 s
- `scripts/products/reports/batch_run_summary_20261013_120626.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20261013_191133.txt`: 2 brands (1 complete, 1 succeeded), wall 61s, products 91, stage wall sums clean/enrich/gates/score = 26/27/0/7 s
- `scripts/products/reports/batch_run_summary_20261013_231748.txt`: 38 brands (38 complete, 38 succeeded), wall 4794s, products 15426, stage wall sums clean/enrich/gates/score = 271/2483/21/1176 s
- `scripts/products/reports/batch_run_summary_20261014_090141.txt`: 38 brands (38 complete, 38 succeeded), wall 7553s, products 15426, stage wall sums clean/enrich/gates/score = 272/2473/24/1171 s
- `scripts/products/reports/batch_run_summary_20261015_164153.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20261015_164217.txt`: 0 brands (0 complete, 0 succeeded), wall Nones, products 0, stage wall sums clean/enrich/gates/score = None/None/None/None s
- `scripts/products/reports/batch_run_summary_20261015_174328.txt`: 38 brands (38 complete, 38 succeeded), wall 4525s, products 15426, stage wall sums clean/enrich/gates/score = 299/2880/27/1299 s
- enrichment_summary.json: 28 brands, 14193 products in 1921 s, median 0.156 s/product, timestamps 2026-07-14T00:23:16.583922Z .. 2026-07-14T03:04:02.301940Z

## Matrix owners

| owner | concepts |
|---|---|
| scripts/enrich_supplements_v3.py | 11 |
| scripts/enhanced_normalizer.py | 7 |
| scripts/scoring_input_contract.py | 3 |
| scripts/scoring_v4/scored_artifact.py | 3 |
| scripts/inactive_ingredient_resolver.py | 2 |
| scripts/normalization.py | 2 |
| scripts/release_full.sh | 2 |
| scripts/supplement_taxonomy.py | 2 |
| scripts/data/ingredient_interaction_rules.json | 1 |
| scripts/dose_assessment.py | 1 |
| scripts/form_factor_normalizer.py | 1 |
| scripts/ingredient_category_normalizer.py | 1 |
| scripts/prebiotic_catalog.py | 1 |
| scripts/probiotic_measurements.py | 1 |
| scripts/release_interaction_artifact.py | 1 |
| scripts/scoring_v4 | 1 |
| scripts/scoring_v4/cert_evidence.py | 1 |
| scripts/scoring_v4/modules/generic_helpers.py | 1 |
| scripts/scoring_v4/quality_score.py | 1 |
| scripts/scoring_v4/route_features.py | 1 |

## Level-2 modules (98)

| module | reasons |
|---|---|
| scripts/api_audit/audit_v4_profile_cutover_impact.py | fan-out 10 |
| scripts/api_audit/backfill_unii_from_cache.py | loc 850 |
| scripts/api_audit/discover_clinical_evidence.py | loc 1246 |
| scripts/api_audit/fda_manufacturer_violations_sync.py | loc 1333; function main 333L nesting 5 |
| scripts/api_audit/fda_weekly_sync.py | loc 1424 |
| scripts/api_audit/iqm_identifier_sweep.py | loc 1589 |
| scripts/api_audit/verify_certifications.py | loc 1630 |
| scripts/api_audit/verify_comptox.py | loc 902; function import_comptox_csv 54L nesting 10 |
| scripts/api_audit/verify_cui.py | loc 895 |
| scripts/api_audit/verify_interactions.py | loc 1694; function verify_entry 333L nesting 4 |
| scripts/api_audit/verify_pubchem.py | loc 1129 |
| scripts/api_audit/verify_rda_uls.py | loc 1137 |
| scripts/api_audit/verify_unii.py | loc 1555 |
| scripts/assessment_readiness.py | loc 1354; function _dose_readiness 354L nesting 3; churn 30 |
| scripts/audit_identity_integrity.py | lazy-import cycle member |
| scripts/audit_raw_to_final.py | loc 1209 |
| scripts/audit_source_of_truth_contract.py | loc 2191; function audit_scoring 305L nesting 6; churn 34 |
| scripts/batch_processor.py | loc 2105 |
| scripts/build_final_db.py | loc 11289; function build_detail_blob 1684L nesting 5; churn 164; lazy-import cycle member; fan-out 22; release chain |
| scripts/build_interaction_db.py | loc 1070; release chain |
| scripts/cert_resolver.py | loc 1273 |
| scripts/cleanup_old_versions.py | loc 968; function quarantine_orphan_blob_batch 453L nesting 5 |
| scripts/clinical_applicability.py | lazy-import cycle member |
| scripts/constants.py | loc 1693 |
| scripts/coverage_gate.py | loc 1163 |
| scripts/dashboard/app.py | function _render_current_view 29L nesting 14 |
| scripts/dashboard/data_loader.py | loc 1524; function _compute_blob_analytics 431L nesting 4 |
| scripts/dashboard/views/quality.py | loc 803 |
| scripts/db_integrity_sanity_check.py | loc 1804 |
| scripts/dose_assessment.py | function build_dose_assessment 167L nesting 11 |
| scripts/dsld_api_sync.py | loc 1312 |
| scripts/dsld_validator.py | lazy-import cycle member |
| scripts/enhanced_normalizer.py | loc 12722; function EnhancedDSLDNormalizer._process_single_ingredient_enhanced 1296L nesting 9; churn 114; lazy-import cycle member; fan-out 10; owns 7 matrix concepts |
| scripts/enrich_supplements_v3.py | loc 25186; function SupplementEnricherV3._collect_rda_ul_data 2278L nesting 18; churn 268; fan-out 25; owns 11 matrix concepts |
| scripts/enrichment_contract_validator.py | loc 3123; function EnrichmentContractValidator._validate_label_ledger_omissions 461L nesting 4 |
| scripts/env_loader.py | fan-in 24 |
| scripts/evidence_resolver.py | loc 1682; function resolve_evidence_for_row 661L nesting 5; churn 39; lazy-import cycle member |
| scripts/generate_pharmacist_review_packet.py | function build_packet 310L nesting 2 |
| scripts/identity_integrity.py | loc 1194; function resolve_identity 375L nesting 11; churn 39 |
| scripts/inactive_ingredient_resolver.py | loc 1212; owns 2 matrix concepts |
| scripts/iqm_form_evidence.py | loc 930 |
| scripts/normalization.py | loc 860; fan-in 15; owns 2 matrix concepts |
| scripts/preflight.py | loc 1295 |
| scripts/probiotic_measurements.py | loc 955; churn 32; lazy-import cycle member |
| scripts/product_submission_import.py | loc 1543; lazy-import cycle member |
| scripts/promote_release_artifacts.py | release chain |
| scripts/release_catalog_artifact.py | loc 936; release chain |
| scripts/release_interaction_artifact.py | loc 843; release chain |
| scripts/release_safety/__init__.py | release chain |
| scripts/release_safety/audit_log.py | release chain |
| scripts/release_safety/backfill_catalog_releases.py | release chain |
| scripts/release_safety/blob_inventory.py | release chain |
| scripts/release_safety/bundle_alignment.py | release chain |
| scripts/release_safety/catalog_diff.py | release chain |
| scripts/release_safety/delete_stale_version_dirs.py | loc 920; release chain |
| scripts/release_safety/gates.py | release chain |
| scripts/release_safety/index_validator.py | release chain |
| scripts/release_safety/lock.py | release chain |
| scripts/release_safety/orphan_reconcile.py | release chain |
| scripts/release_safety/protected_blobs.py | release chain |
| scripts/release_safety/quarantine.py | release chain |
| scripts/release_safety/quarantine_sweeper.py | release chain |
| scripts/release_safety/registry.py | release chain |
| scripts/release_safety/retire_release.py | release chain |
| scripts/release_safety/storage_audit.py | loc 829; release chain |
| scripts/release_safety/transient.py | release chain |
| scripts/row_ledger.py | function build_row_ledger 210L nesting 13 |
| scripts/run_pipeline.py | loc 976 |
| scripts/score_supplements_v4.py | fan-out 16 |
| scripts/scoring_input_contract.py | loc 6451; function derive_product_scoring_evidence 468L nesting 5; churn 130; lazy-import cycle member; fan-in 30; owns 3 matrix concepts |
| scripts/scoring_v4/confidence.py | function _verification_confidence 68L nesting 10 |
| scripts/scoring_v4/dose_safety.py | lazy-import cycle member |
| scripts/scoring_v4/gate_safety.py | loc 1468; churn 36 |
| scripts/scoring_v4/modules/b_complex.py | fan-out 12 |
| scripts/scoring_v4/modules/botanical_profile.py | loc 911 |
| scripts/scoring_v4/modules/generic_dose.py | loc 801; fan-out 10 |
| scripts/scoring_v4/modules/generic_evidence.py | loc 1893; churn 81 |
| scripts/scoring_v4/modules/generic_helpers.py | lazy-import cycle member; fan-in 36 |
| scripts/scoring_v4/modules/generic_transparency.py | loc 989 |
| scripts/scoring_v4/modules/immune_support.py | lazy-import cycle member |
| scripts/scoring_v4/modules/multi_prenatal.py | fan-out 10 |
| scripts/scoring_v4/modules/omega.py | fan-out 10 |
| scripts/scoring_v4/modules/probiotic.py | fan-out 10 |
| scripts/scoring_v4/modules/sports.py | fan-out 10 |
| scripts/scoring_v4/modules/sports_helpers.py | lazy-import cycle member |
| scripts/scoring_v4/quality_score.py | loc 1682; churn 67; lazy-import cycle member |
| scripts/scoring_v4/quality_score_config.py | fan-in 37 |
| scripts/scoring_v4/route_features.py | loc 861; lazy-import cycle member |
| scripts/scoring_v4/router.py | lazy-import cycle member |
| scripts/scoring_v4/scored_artifact.py | owns 3 matrix concepts |
| scripts/studied_formulas.py | loc 1220; churn 30; lazy-import cycle member |
| scripts/submission_review/extraction/benchmark.py | loc 956 |
| scripts/supabase_client.py | fan-in 17 |
| scripts/supplement_taxonomy.py | loc 2033; function classify_supplement 1117L nesting 30; owns 2 matrix concepts |
| scripts/sweep_quarantine.py | function _execute 303L nesting 7 |
| scripts/sync_to_supabase.py | loc 1736; function sync 324L nesting 2; release chain |
| scripts/unit_converter.py | loc 906; function UnitConverter.convert_nutrient 381L nesting 3 |
| scripts/validate_safety_copy.py | loc 1217 |
