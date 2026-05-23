"""Pytest configuration shared across the scripts/tests/ suite.

Centralizes sys.path setup so individual test files don't each need their
own copy-paste `sys.path.insert(...)` hack. Without this, tests that
import scripts/* modules directly (e.g. `from enhanced_normalizer import …`)
work in the full-suite run only because *other* tests happen to run first
and set the path. Standalone runs (`pytest scripts/tests/test_X.py`) would
otherwise fail with ModuleNotFoundError.

This file is auto-discovered by pytest. No imports needed in test files.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# scripts/ directory — where enhanced_normalizer, score_supplements, etc. live.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


SLOW_TEST_FILES = {
    "test_clean_unmapped_alias_regressions.py",
    "test_enrichment_regressions.py",
    "test_pipeline_regressions.py",
    "test_scorable_classification.py",
    "test_score_supplements.py",
}

RELEASE_TEST_FILES = {
    "test_active_banned_recalled_parity.py",
    "test_cert_audit_canary.py",
    "test_final_db_integrity_gate.py",
    "test_manifest_contract.py",
    "test_python_runtime_contract.py",
    "test_release_export_parity.py",
    "test_release_gate_banned_safe_contradictions.py",
    "test_source_of_truth_contract.py",
    "test_v4_canary_coverage.py",
}

ARTIFACT_TEST_FILES = {
    "test_active_banned_recalled_parity.py",
    "test_cert_audit_canary.py",
    "test_dashboard_smoke.py",
    "test_d53_detail_blob_top_level_contract.py",
    "test_d54_dr_pham_fields_propagate.py",
    "test_form_sensitive_nutrient_gate.py",
    "test_graceful_degradation.py",
    "test_label_fidelity_contract.py",
    "test_release_export_parity.py",
    "test_release_gate_banned_safe_contradictions.py",
    "test_safety_audit_gates.py",
    "test_safety_copy_contract.py",
    "test_v4_canary_coverage.py",
}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Centralize suite tiers without editing hundreds of test files.

    Full-suite pytest remains accuracy-first. The wrapper in scripts/test.sh
    uses these markers to give local development fast/release/full profiles.
    """
    for item in items:
        filename = Path(str(item.path)).name
        if filename in SLOW_TEST_FILES:
            item.add_marker(pytest.mark.slow)
        if filename in RELEASE_TEST_FILES:
            item.add_marker(pytest.mark.release)
        if filename in ARTIFACT_TEST_FILES:
            item.add_marker(pytest.mark.artifact)
