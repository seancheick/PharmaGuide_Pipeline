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
    "test_score_supplements.py",
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
    "test_release_export_parity.py",
    "test_release_gate_banned_safe_contradictions.py",
    "test_safety_audit_gates.py",
    "test_safety_copy_contract.py",
    "test_scoring_snapshot_v1.py",
    "test_unii_cache.py",
    "test_unii_exoneration_allowlist.py",
    "test_v4_canary_coverage.py",
})


def iter_profile_paths(profile: str, tests_dir: Path | None = None) -> Iterable[Path]:
    """Yield deterministic test paths owned by one named profile."""
    root = tests_dir or Path(__file__).resolve().parent / "tests"
    all_tests = sorted(root.glob("test_*.py"))

    if profile == "fast":
        excluded = SLOW_TEST_FILES | RELEASE_TEST_FILES | ARTIFACT_TEST_FILES
        return (
            path for path in all_tests
            if path.name not in excluded and not path.name.endswith("_live.py")
        )
    if profile == "slow":
        owned = SLOW_TEST_FILES
    elif profile == "release":
        owned = RELEASE_TEST_FILES
    elif profile == "artifact":
        owned = ARTIFACT_TEST_FILES
    else:
        raise ValueError(f"Unknown test profile: {profile}")
    return (path for path in all_tests if path.name in owned)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", choices=("fast", "slow", "release", "artifact"))
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    for path in iter_profile_paths(args.profile):
        print(path.relative_to(repo_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
