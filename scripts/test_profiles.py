#!/usr/bin/env python3
"""Single authoritative ownership manifest for pytest execution profiles."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import FrozenSet, Iterable


SLOW_TEST_FILES: FrozenSet[str] = frozenset({
    "test_canonical_id_e2e_continuity.py",
    "test_clean_unmapped_alias_regressions.py",
    "test_dsld_317006_piperine_demotion_2026_05_25.py",
    "test_enrichment_regressions.py",
    "test_pipeline_regressions.py",
    "test_scorable_classification.py",
    "test_scoring_evidence_contract_v1.py",
    "test_unii_match_method_in_ledger.py",
    "test_v4_banned_form_evidence_gate.py",
    "test_v4_cross_module_canary_diversity.py",
    "test_v4_gate_canary_diversity.py",
    "test_v4_multi_prenatal_canary_diversity_p3.py",
    "test_v4_omega_canary_diversity_p161.py",
    "test_v4_omega_dose_p162.py",
    "test_v4_omega_evidence_p163.py",
    "test_v4_omega_final_assembly_p166.py",
    "test_v4_omega_transparency_p165.py",
    "test_v4_omega_trust_p164.py",
    "test_v4_opaque_stimulant_blend.py",
    "test_v4_probiotic_final_assembly_p26.py",
})

RELEASE_TEST_FILES: FrozenSet[str] = frozenset({
    "test_active_banned_recalled_parity.py",
    "test_catalog_stamp_parity_release.py",
    "test_cert_audit_canary.py",
    "test_final_db_integrity_gate.py",
    "test_manifest_contract.py",
    "test_python_runtime_contract.py",
    "test_release_export_parity.py",
    "test_release_gate_banned_safe_contradictions.py",
    "test_source_of_truth_contract.py",
    "test_v4_canary_coverage.py",
    "test_v4_safety_parity_release.py",
})

ARTIFACT_TEST_FILES: FrozenSet[str] = frozenset({
    "test_active_banned_recalled_parity.py",
    "test_cert_audit_canary.py",
    "test_dashboard_smoke.py",
    "test_d53_detail_blob_top_level_contract.py",
    "test_d54_dr_pham_fields_propagate.py",
    "test_dsld_278523_folate_parent_total_2026_05_25.py",
    "test_form_sensitive_nutrient_gate.py",
    "test_graceful_degradation.py",
    "test_label_fidelity_contract.py",
    "test_pipeline_data_flow_artifacts.py",
    "test_release_export_parity.py",
    "test_release_gate_banned_safe_contradictions.py",
    "test_safety_audit_gates.py",
    "test_safety_copy_contract.py",
    "test_scoring_snapshot_v1.py",
    "test_serving_basis_corpus_invariant.py",
    "test_unii_cache.py",
    "test_unii_exoneration_allowlist.py",
    "test_v4_canary_coverage.py",
})


# Fast-profile files whose tests need what only Sean's Mac has: the 11 GB
# product corpus, built exports, canary baselines, or an opt-in local tool.
# CI (a clean checkout) skips them; `scripts/test.sh local` runs exactly these.
# scripts/ci_skip_guard.py fails CI when a test skips outside this list, so a
# new local-only test cannot pass unseen.
LOCAL_ONLY_TEST_FILES: FrozenSet[str] = frozenset({
    "test_context_canonical_overrides_2026_05_24.py",
    "test_identity_unii_literal_proof.py",
    "test_interaction_rule_every_declared_form.py",
    "test_rc4_blend_header_total_contract.py",
    "test_active_count_reconciliation.py",
    "test_canonical_id_delivers_markers_emit.py",
    "test_cert_needs_review_cluster_p171.py",
    "test_cert_population_identity.py",
    "test_cleaner_forms_preservation.py",
    "test_condition_id_shape_consistency.py",
    "test_cross_module_probiotic_evidence.py",
    "test_e1_2_2_preflight_invariant.py",
    "test_e1_5_x_4_ul_fallback_and_status.py",
    "test_inactive_ingredient_preservation.py",
    "test_inactive_penalty_ledger_parity.py",
    "test_inactive_role_label_from_functional_roles.py",
    "test_no_silently_mapped_rows.py",
    "test_plant_part_preservation_closeout.py",
    "test_probiotic_cfu_adequacy.py",
    "test_probiotic_confidence_hybrid.py",
    "test_probiotic_structured_form_identity.py",
    "test_reviewer_doc_constituent_forms.py",
    "test_submission_extraction_live_stack.py",
    "test_submission_print_fidelity.py",
    "test_submission_review_live_stack.py",
})

# Exact observed skip reasons; a declared file never excuses another failure.
CI_SKIP_ALLOWED_REASONS = {
    'test_identity_unii_literal_proof.py': ('local\\ staging\\ label\\ unavailable;\\ the\\ fixture\\ test\\ covers\\ CI',),
    'test_interaction_rule_every_declared_form.py': ('raw\\ reference\\ label\\ unavailable',),
    'test_rc4_blend_header_total_contract.py': ('Staging\\ dir\\ not\\ available\\ on\\ this\\ machine',),
    'test_context_canonical_overrides_2026_05_24.py': (
        r'raw DSLD staging dataset not mounted at /[^ ]+/Downloads/PharmaGuide_Datasets/staging/brands(?: or (?:Jarrow_Formulas/265081|Pure_Encapsulations/317962|Natures_Way/25930[46])\.json missing)?',
        r'raw DSLD (?:Jarrow_Formulas/265081|Pure_Encapsulations/317962|Natures_Way/25930[46])\.json not mounted at /[^ ]+/Downloads/PharmaGuide_Datasets/staging/brands',
    ),
    'test_active_count_reconciliation.py': (
        '\\d+\\ canary\\ missing',
        '\\d+\\ canary\\ not\\ rebuilt\\ yet',
    ),
    'test_canonical_id_delivers_markers_emit.py': (
        'no\\ build\\ directory\\ available',
        'no\\ build\\ directory\\ available\\ —\\ run\\ targeted\\ rebuild\\ first',
    ),
    'test_cert_needs_review_cluster_p171.py': (
        'no\\ enriched\\ products\\ dir\\ present\\ in\\ this\\ checkout',
    ),
    'test_cert_population_identity.py': (
        'local\\ cleaned\\ corpus\\ not\\ available',
        'local\\ enriched\\ corpus\\ not\\ available',
    ),
    'test_cleaner_forms_preservation.py': (
        'No\\ pipeline\\ output',
    ),
    'test_condition_id_shape_consistency.py': (
        '\\d+\\ canary\\ not\\ rebuilt\\ yet',
    ),
    'test_cross_module_probiotic_evidence.py': (
        'enriched\\ corpus\\ not\\ present\\ \\(output_Doctors_Best_enriched\\)',
        'enriched\\ corpus\\ not\\ present\\ \\(output_Garden_of_life_enriched\\)',
        'enriched\\ corpus\\ not\\ present\\ \\(output_Jarrow_Formulas_enriched\\)',
        'enriched\\ corpus\\ not\\ present\\ \\(output_Life_Extension_enriched\\)',
        'enriched\\ corpus\\ not\\ present\\ \\(output_MegaFood_enriched\\)',
        'enriched\\ corpus\\ not\\ present\\ \\(output_Ora_enriched\\)',
    ),
    'test_data_file_metadata_contract.py': (
        'banned_match_allowlist\\.json:\\ total_entries\\ tracks\\ allowlist\\ only;\\ denylist\\ is\\ auxiliary\\ and\\ tracked\\ separately\\.\\ Pinned\\ by\\ test_banned_match_allowlist_contract\\.py\\.',
        'canary_products\\.json:\\ _metadata\\ has\\ no\\ total_entries\\ field',
        'canonical_equivalences\\.json:\\ shape\\ not\\ recognized\\ by\\ universal\\ classifier\\ \\(needs\\ a\\ bespoke\\ per\\-file\\ test;\\ add\\ to\\ INTENTIONAL_EXCEPTIONS\\ with\\ a\\ pointer\\ to\\ that\\ test\\)\\.',
        'catalog_brand_registry\\.json:\\ total_entries\\ tracks\\ canonical\\ brand\\-family\\ records;\\ wave_1\\ is\\ an\\ execution\\ manifest,\\ not\\ another\\ brand\\ catalog\\.\\ Pinned\\ by\\ test_brand_identity\\.py\\.',
        "cert_claim_rules\\.json:\\ total_entries\\ =\\ Σ\\(non\\-_\\-prefixed\\ rule\\ keys\\ across\\ rules\\.\\*\\),\\ excluding\\ each\\ category's\\ _metadata\\ config\\ sub\\-key\\.\\ Pinned\\ by\\ test_cert_claim_rules_contract\\.py\\.",
        'cert_registry\\.json:\\ _metadata\\ has\\ no\\ total_entries\\ field',
        'clinical_risk_taxonomy\\.json:\\ UNIQUE\\ convention\\ —\\ total_entries\\ =\\ SUM\\ of\\ all\\ 7\\ taxonomy\\ arrays\\ \\(conditions\\ \\+\\ drug_classes\\ \\+\\ severity_levels\\ \\+\\ evidence_levels\\ \\+\\ profile_flags\\ \\+\\ product_forms\\ \\+\\ sources\\)\\.\\ Pinned\\ by\\ test_clinical_risk_taxonomy_contract\\.py\\.',
        'color_indicators\\.json:\\ total_entries\\ tracks\\ natural_indicators\\ only;\\ artificial_indicators\\ \\+\\ explicit_natural_dyes\\ \\+\\ explicit_artificial_dyes\\ are\\ auxiliary\\.\\ Pinned\\ by\\ test_color_indicators_contract\\.py\\.',
        'functional_ingredient_groupings\\.json:\\ total_entries\\ tracks\\ functional_groupings\\ only;\\ vague_terms_to_flag\\ \\+\\ transparency_bonuses\\ are\\ auxiliary\\.\\ Pinned\\ by\\ test_functional_ingredient_groupings_contract\\.py\\.',
        'high_dose_rule_exemptions\\.json:\\ _metadata\\ has\\ no\\ total_entries\\ field',
        'iqm_excellent_evidence_backlog\\.json:\\ shape\\ not\\ recognized\\ by\\ universal\\ classifier\\ \\(needs\\ a\\ bespoke\\ per\\-file\\ test;\\ add\\ to\\ INTENTIONAL_EXCEPTIONS\\ with\\ a\\ pointer\\ to\\ that\\ test\\)\\.',
        'manufacture_deduction_expl\\.json:\\ Structural\\ config\\ file\\ \\(1\\ scalar\\ total_deduction_cap\\ \\+\\ 4\\ nested\\ dicts\\ for\\ violation_categories\\ /\\ modifiers\\ /\\ calculation_rules\\ /\\ score_thresholds\\)\\.\\ total_entries=5\\ tracks\\ count\\ of\\ top\\-level\\ non\\-_metadata\\ sub\\-sections\\ —\\ meaningful\\ but\\ not\\ entry\\-shaped\\.\\ Pinned\\ by\\ test_manufacture_deduction_expl_contract\\.py\\.',
        'migration_report\\.json:\\ total_entries\\ tracks\\ alias_collisions_resolved\\ \\(the\\ headline\\ number\\ of\\ this\\ migration\\);\\ other\\ arrays/dicts\\ are\\ scaffolding\\.\\ Pinned\\ by\\ test_migration_report_contract\\.py\\.',
        'omega_rubric\\.json:\\ _metadata\\ has\\ no\\ total_entries\\ field',
        'unit_conversions\\.json:\\ total_entries\\ tracks\\ vitamin_conversions\\ only;\\ mass_conversions\\ and\\ form_detection_patterns\\ are\\ static\\ rule\\ config,\\ not\\ vitamin\\ entries\\.\\ Pinned\\ by\\ test_unit_conversions_contract\\.py\\.',
    ),
    'test_e1_2_2_preflight_invariant.py': (
        'baseline\\ \\d+\\.json\\ missing',
    ),
    'test_e1_5_x_4_ul_fallback_and_status.py': (
        'dist/detail_blobs\\ not\\ present\\ —\\ run\\ rebuild\\ first',
    ),
    'test_inactive_ingredient_preservation.py': (
        '\\d+\\ canary\\ not\\ rebuilt\\ yet',
    ),
    'test_inactive_penalty_ledger_parity.py': (
        'enriched\\ corpus\\ not\\ available',
    ),
    'test_inactive_role_label_from_functional_roles.py': (
        'no\\ build\\ directory\\ available\\ —\\ run\\ targeted\\ rebuild\\ first',
    ),
    'test_no_silently_mapped_rows.py': (
        'No\\ pipeline\\ output\\ directory\\ present',
    ),
    'test_plant_part_preservation_closeout.py': (
        'canary\\ \\d+\\ not\\ rebuilt\\ yet',
    ),
    'test_probiotic_cfu_adequacy.py': (
        '\\d+\\ canary\\ not\\ rebuilt\\ yet',
    ),
    'test_probiotic_confidence_hybrid.py': (
        '\\d+\\ canary\\ not\\ rebuilt\\ yet',
    ),
    'test_probiotic_structured_form_identity.py': (
        'Local\\ Fortify\\ source\\ unavailable;\\ synthetic\\ ownership\\ cases\\ remain\\ unconditional',
        "Local\\ Nature's\\ Way\\ cleaned\\ corpus\\ is\\ absent;\\ synthetic\\ ownership\\ cases\\ are\\ unconditional",
        'Local\\ manifest\\-owned\\ direct\\-strain\\ control\\ is\\ absent',
    ),
    'test_reviewer_doc_constituent_forms.py': (
        'shipped\\ detail\\ blobs\\ not\\ built',
    ),
    'test_submission_extraction_live_stack.py': (
        'explicitly\\ opt\\ in\\ with\\ PG_RUN_LOCAL_EXTRACTION_TESTS=\\d+',
    ),
    'test_submission_print_fidelity.py': (
        'needs\\ PG_RUN_OCR_FIDELITY_TESTS=\\d+\\ and\\ the\\ OCR\\ engine',
    ),
    'test_submission_review_live_stack.py': (
        'explicitly\\ opt\\ in\\ with\\ PG_RUN_LOCAL_REVIEW_TESTS=\\d+',
    ),
}

# Node ownership for mixed files. A file-level speed/local/release label is not
# a dependency: synthetic tmp_path fixtures and raw source probes run early.
# Only the named nodes below consume previously generated corpus/catalog data.
PREPARATION_ARTIFACT_NODES = {
    'test_canonical_id_e2e_continuity.py': {'test_evidence_rows_carry_identity_chain_fields', 'test_scoring_parent_id_matches_evidence_canonical_id', 'test_scorable_rows_lack_evidence_origin', 'test_evidence_origin_is_compatibility_derived', 'test_clean_identity_id_traces_to_row_canonical'},
    'test_scoring_evidence_contract_v1.py': {'test_identity_bearing_blend_total_reaches_v4_as_anchor_mass_evidence', 'test_protein_macro_reaches_v4_as_sports_primary_dose_evidence', 'test_enzyme_evidence_carries_new_identity_fields', 'test_enzyme_activity_reaches_v4_as_non_mass_dose_evidence', 'test_printed_epa_dha_members_own_their_doses_under_a_blend_total', 'test_blend_anchor_cannot_hide_title_material_unresolved_vitamin_dose', 'test_omega_aggregate_and_forms_reach_v4_as_epa_dha_evidence'},
    'test_v4_cross_module_canary_diversity.py': {'test_sports_real_catalog_canary_score_and_traits', 'test_generic_real_catalog_canary_score_and_traits', 'test_probiotic_real_catalog_canary_score_and_traits'},
    'test_v4_gate_canary_diversity.py': {'test_v4_real_catalog_gate_and_confidence_canary'},
    'test_v4_multi_prenatal_canary_diversity_p3.py': {'test_multi_canary_routes_to_multi_or_prenatal', 'test_multi_false_positive_does_not_route_to_multi'},
    'test_v4_omega_canary_diversity_p161.py': {'test_false_positive_omega_routes_to_generic', 'test_every_canary_is_in_the_catalog', 'test_omega_canary_routes_and_scores_in_range', 'test_canary_set_covers_score_ranges'},
    'test_v4_omega_dose_p162.py': {'test_canary_dose_scores'},
    'test_v4_omega_evidence_p163.py': {'test_canary_indication_relevance', 'test_canary_evidence_score_in_range'},
    'test_v4_omega_final_assembly_p166.py': {'test_canary_sports_research_improves_vs_v3_baseline', 'test_canary_final_score_in_range'},
    'test_v4_omega_transparency_p165.py': {'test_canary_nordic_has_no_form_disclosed', 'test_canary_transparency_in_range'},
    'test_v4_omega_trust_p164.py': {'test_canary_trust_matches_curated_override_state'},
    'test_v4_banned_form_evidence_gate.py': {'test_corpus_pho_products_are_v4_native_blocked', 'test_corpus_pho_canary_declares_pho_and_blocks'},
    'test_unii_match_method_in_ledger.py': {'test_gnc_ledger_includes_unii_or_alternate_methods', 'test_gnc_ledger_records_unii_exact_match', 'test_gnc_ledger_does_not_misattribute_unii_as_exact'},
    'test_v4_opaque_stimulant_blend.py': {'test_real_gnc_amino_energy_botanical_bound'},
    'test_v4_probiotic_final_assembly_p26.py': {'test_canary_spring_valley_probiotic_50b_scoreable_at_p26'},
    'test_active_banned_recalled_parity.py': {'test_active_parity_audit_clean', 'test_no_banned_active_ships_with_severity_status_na', 'test_no_corpus_red_yeast_rice_label_is_unmatched', 'test_corpus_canary_178791_flags_its_film_coating_additives'},
    'test_active_count_reconciliation.py': {'test_canary_carries_raw_actives_count_and_reasons', 'test_plantizyme_raw_actives_count_matches_expected'},
    'test_canonical_id_delivers_markers_emit.py': {'test_canary_active_carries_canonical_id', 'test_canary_active_carries_delivers_markers_field', 'test_canonical_id_emit_rate_at_least_90_percent_on_mapped'},
    'test_cert_audit_canary.py': {'test_audit_detects_cert_overcredit_at_scale', 'test_audit_report_emits_top_level_queues'},
    'test_cert_needs_review_cluster_p171.py': {'test_cluster_handles_real_catalog_shape_smoke'},
    'test_cert_population_identity.py': {'test_real_cleaned_product_full_enrichment_does_not_inherit_another_formulation', 'test_real_label_form_detail_preserves_complete_registry_identity', 'test_real_named_variant_never_inherits_generic_sku', 'test_real_culturelle_form_descriptor_supplies_registry_identity_at_producer_boundary'},
    'test_cleaner_forms_preservation.py': {'test_every_form_has_name', 'test_every_form_is_dsld_structured_or_name_extracted', 'test_dsld_structured_forms_preserve_all_fields'},
    'test_condition_id_shape_consistency.py': {'test_canary_blobs_have_plural_arrays_only', 'test_vitafusion_cbd_preserves_pregnancy_condition'},
    'test_cross_module_probiotic_evidence.py': {'test_megafood_zinc_s_cerevisiae_is_not_probiotic_active', 'test_jarrow_beta_glucan_s_cerevisiae_is_not_probiotic_active', 'test_garden_of_life_md_protein_de111_finished_review_is_terminal', 'test_life_extension_digestive_enzymes_with_mtcc5856', 'test_doctors_best_digestive_enzymes_bacillus_subtilis', 'test_garden_of_life_collagen_creamer_bacillus_subtilis', 'test_ora_break_it_down_bacillus_subtilis', 'test_companion_points_preserve_probiotic_component_state'},
    'test_d53_detail_blob_top_level_contract.py': {'test_every_blob_key_is_declared', 'test_every_ingredient_row_key_is_declared', 'test_every_blob_has_required_top_level_keys', 'test_rda_ul_data_always_present', 'test_warnings_profile_gated_is_a_list'},
    'test_d54_dr_pham_fields_propagate.py': {'test_warning_types_cover_expected_universe', 'test_harmful_additive_dr_pham_fields', 'test_interaction_dr_pham_fields', 'test_display_mode_default_populated_on_every_warning', 'test_severity_contextual_populated_on_avoid_rules'},
    'test_dashboard_smoke.py': {'test_all_dashboard_views_smoke_render', 'test_inspector_drilldown_renders_v4_for_real_product'},
    'test_e1_5_x_4_ul_fallback_and_status.py': {'test_highest_ul_populated_for_ul_defined_nutrients', 'test_blob_ul_for_default_profile_is_separate_field', 'test_blob_preserves_indeterminate_ul_review_flags'},
    'test_graceful_degradation.py': {'test_inspector_drill_down_real_product'},
    'test_form_sensitive_nutrient_gate.py': {'test_no_form_sensitive_violations_in_build_output'},
    'test_label_fidelity_contract.py': {'test_blob_capsimax_display_label_invariants', 'test_no_np_leaks_to_display', 'test_standardization_note_preserved', 'test_no_false_well_dosed_on_undisclosed', 'test_branded_identity_preserved', 'test_inactive_ingredients_complete', 'test_plant_part_preserved', 'test_projection_label_text_comes_from_the_label_ledger', 'test_label_display_name_drives_display_label', 'test_display_name_never_canonical', 'test_plant_part_present_in_form_metadata'},
    'test_inactive_ingredient_preservation.py': {'test_canary_inactives_preserved_and_no_placeholder_leak'},
    'test_inactive_penalty_ledger_parity.py': {'test_no_charged_inactive_row_renders_green', 'test_module_propagates_whole_shared_metadata'},
    'test_no_silently_mapped_rows.py': {'test_zero_silently_mapped_active_rows', 'test_canonical_source_db_matches_canonical_presence'},
    'test_probiotic_cfu_adequacy.py': {'test_canary_19067_probiotic_ingredient_carries_adequacy_tier'},
    'test_probiotic_confidence_hybrid.py': {'test_canary_19067_probiotic_confidence_fields', 'test_non_probiotic_canary_does_not_get_confidence_fields'},
    'test_probiotic_structured_form_identity.py': {'test_real_fortify_subblend_opacity_uses_source_owner_not_first_child_index', 'test_real_327965_retains_three_distinct_howaru_source_owners', 'test_real_direct_name_generic_form_controls'},
    'test_reviewer_doc_constituent_forms.py': {'test_no_chemically_unrelated_rollup_survives_on_the_shipped_corpus', 'test_parent_index_encoding_is_acyclic_and_well_formed', 'test_known_false_pairs_are_gone_from_the_corpus'},
    'test_safety_audit_gates.py': {'test_audit_inactive_safety_passes_on_current_build', 'test_audit_active_banned_recalled_parity_passes_on_current_build'},
    'test_scoring_snapshot_v1.py': {'test_scored_product_matches_snapshot'},
    'test_source_of_truth_contract.py': {'test_live_interaction_db_has_no_orphan_canonicals'},
    'test_v4_canary_coverage.py': {'test_every_canary_is_live_or_explicitly_quarantined'},
    'test_v4_safety_parity_release.py': {'test_v3_blocked_release_products_remain_v4_blocked'},
}
PREPARATION_ARTIFACT_FILES = frozenset({
    'test_catalog_stamp_parity_release.py', 'test_dsld_317006_piperine_demotion_2026_05_25.py',
    'test_dsld_278523_folate_parent_total_2026_05_25.py', 'test_e1_2_2_preflight_invariant.py',
    'test_inactive_role_label_from_functional_roles.py',
    'test_pipeline_data_flow_artifacts.py', 'test_plant_part_preservation_closeout.py',
    'test_release_export_parity.py', 'test_release_gate_banned_safe_contradictions.py',
    'test_safety_copy_contract.py', 'test_serving_basis_corpus_invariant.py',
})
PREPARATION_EXTERNAL_FILES = {
    'test_submission_extraction_live_stack.py': 'PG_RUN_LOCAL_EXTRACTION_TESTS=1, disposable Supabase stack and OCR worker; remote writes require explicit opt-in',
    'test_submission_review_live_stack.py': 'PG_RUN_LOCAL_REVIEW_TESTS=1 and disposable Supabase stack; remote writes require explicit opt-in',
}


def preparation_phase(filename, test_name, *, markers=()):
    """Dependency phase independent of the unchanged execution speed profiles."""
    test_name = test_name.split('[')[0]
    if filename in PREPARATION_EXTERNAL_FILES:
        return 'external', PREPARATION_EXTERNAL_FILES[filename]
    if filename == 'test_submission_print_fidelity.py' and test_name == 'test_preparation_costs_nothing_at_the_working_operating_point':
        return 'external', 'PG_RUN_OCR_FIDELITY_TESTS=1 and OCR engine; never enabled by preparation'
    if filename.endswith('_live.py') or {'live', 'network'} & set(markers):
        return 'external', 'PHARMAGUIDE_LIVE_TESTS=1, RxNorm/PubMed/UMLS access (UMLS_API_KEY for UMLS); existing explicit opt-in remains authoritative'
    if (filename in PREPARATION_ARTIFACT_FILES
            or test_name in PREPARATION_ARTIFACT_NODES.get(filename, ())
            or ('artifact' in markers and filename not in ARTIFACT_TEST_FILES)):
        return 'artifact', 'Current generated corpus/catalog/bundle required; run after planned regeneration'
    return 'source', 'Current source/reference/raw inputs or isolated synthetic fixtures; no generated output prerequisite'


def iter_profile_paths(profile: str, tests_dir: Path | None = None, *,
                       shard_index: int | None = None, shard_count: int | None = None) -> Iterable[Path]:
    """Yield deterministic test paths owned by one named profile."""
    root = tests_dir or Path(__file__).resolve().parent / "tests"
    all_tests = sorted(root.glob("test_*.py"))

    if profile == "fast":
        excluded = SLOW_TEST_FILES | RELEASE_TEST_FILES | ARTIFACT_TEST_FILES
        paths = [path for path in all_tests
                 if path.name not in excluded and not path.name.endswith("_live.py")]
        if shard_index is None and shard_count is None:
            return iter(paths)
        if (shard_index is None or shard_count is None or shard_count < 1
                or not 0 <= shard_index < shard_count):
            raise ValueError("shard requires 0 <= index < positive count")
        return iter(paths[shard_index::shard_count])
    if shard_index is not None or shard_count is not None:
        raise ValueError("only the fast profile can be sharded")
    if profile == "slow":
        owned = SLOW_TEST_FILES
    elif profile == "release":
        owned = RELEASE_TEST_FILES
    elif profile == "artifact":
        owned = ARTIFACT_TEST_FILES
    elif profile == "local":
        owned = LOCAL_ONLY_TEST_FILES
    else:
        raise ValueError(f"Unknown test profile: {profile}")
    return (path for path in all_tests if path.name in owned)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", choices=("fast", "slow", "release", "artifact", "local"))
    parser.add_argument("--shard", help="Existing one-based i/n shard selector")
    parser.add_argument("--shard-index", type=int)
    parser.add_argument("--shard-count", type=int)
    args = parser.parse_args()
    if args.shard is not None:
        if args.shard_index is not None or args.shard_count is not None:
            parser.error("choose --shard or --shard-index/--shard-count")
        try:
            index, count = map(int, args.shard.split("/"))
        except ValueError:
            parser.error("--shard must be i/n")
        args.shard_index, args.shard_count = index - 1, count
    repo_root = Path(__file__).resolve().parent.parent
    for path in iter_profile_paths(args.profile, shard_index=args.shard_index, shard_count=args.shard_count):
        print(path.relative_to(repo_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
