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
    parser.add_argument("--shard-index", type=int)
    parser.add_argument("--shard-count", type=int)
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    for path in iter_profile_paths(args.profile, shard_index=args.shard_index, shard_count=args.shard_count):
        print(path.relative_to(repo_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
