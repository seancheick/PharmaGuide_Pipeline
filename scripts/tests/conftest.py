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

import importlib
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# scripts/ directory — where enhanced_normalizer, score_supplements, etc. live.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


SLOW_TEST_FILES = {
    # Heavy real-catalog / V4-canary integration tests. Kept in sync with
    # scripts/test.sh SLOW_FILES. Expanded 2026-06-24 from a --durations=40 pass
    # (worst offenders ran 25s-485s each).
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
    "test_v4_safety_parity_release.py",
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


def pytest_configure(config: pytest.Config) -> None:  # noqa: ARG001
    """Nudge when pytest is invoked directly instead of via scripts/test.sh.

    The runner pins the project interpreter (pyenv 3.13; macOS/Xcode `python3`
    is 3.9) and applies the fast/release/full profiles. A raw
    `python3 -m pytest scripts/tests/` uses the wrong interpreter AND runs the
    full heavy suite (one catalog test alone is ~8 min; whole run ~1 hr). The
    runner sets PG_TEST_RUNNER=1; its absence means pytest was launched raw."""
    if os.environ.get("PG_TEST_RUNNER"):
        return
    sys.stderr.write(
        "\n\033[1;33m⚠  Run tests via scripts/test.sh, not raw pytest:\n"
        "     scripts/test.sh fast     # dev loop (~3-5 min, pinned Python 3.13)\n"
        "     scripts/test.sh full     # full suite, pre-ship / CI\n"
        "   Raw `python3 -m pytest` uses Xcode's Python 3.9 and runs the full\n"
        "   heavy suite (~1 hr). See AGENTS.md > Running tests.\033[0m\n\n"
    )


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


# ---------------------------------------------------------------------------
# Dashboard smoke-test isolation
#
# The Streamlit dashboard views capture `import streamlit as st` at *import*
# time. The smoke tests render those views headlessly by swapping a MagicMock
# into sys.modules["streamlit"] in place of the real package.
#
# That swap is only safe if it happens before any dashboard view module is
# imported. When another test imports the real streamlit (and, transitively,
# the dashboard — e.g. `from scripts.dashboard.views.scoring_integrity import …`)
# *first*, the view modules' module-level `st` stays bound to the real package.
# Replacing sys.modules["streamlit"] with a non-package MagicMock afterwards then
# makes real code paths such as `st.info()` -> `extract_leading_emoji()` ->
# `from streamlit.emojis import …` raise:
#
#     ModuleNotFoundError: No module named 'streamlit.emojis';
#     'streamlit' is not a package
#
# i.e. the lazy submodule import can't find its parent because the parent in
# sys.modules is now the mock. Whether this fires depends purely on test order
# (and pytest-xdist makes order nondeterministic), so it can silently mask real
# dashboard regressions during a full-suite run.
#
# The `dashboard_app` fixture below makes the dashboard tests order-independent:
# it snapshots and purges the dashboard package, installs the mock, re-imports
# the dashboard fresh (so every view binds st=mock uniformly), yields the import
# surface the tests need, then restores sys.modules so no later test inherits
# the mock.
# ---------------------------------------------------------------------------


class _DashboardStreamlitMock(MagicMock):
    """Headless Streamlit stand-in for dashboard smoke tests.

    Returns deterministic values for the widget calls the views make so the
    render functions exercise their real logic without a Streamlit runtime.
    This is the superset of the mocks the dashboard test files previously
    defined inline (widgets + container managers + ``__format__``).
    """

    def __getattr__(self, name):
        if name in {"sidebar", "expander"}:
            return _DashboardStreamlitMock()
        return super().__getattr__(name)

    def columns(self, spec):
        n = spec if isinstance(spec, int) else len(spec)
        return [_DashboardStreamlitMock() for _ in range(n)]

    def tabs(self, labels):
        return [_DashboardStreamlitMock() for _ in labels]

    def selectbox(self, label, options=None, **kwargs):
        return options[0] if options else None

    def radio(self, label, options=None, **kwargs):
        return options[0] if options else None

    def text_input(self, *args, **kwargs):
        return kwargs.get("value", "") or ""

    def button(self, *args, **kwargs):
        return False

    def toggle(self, *args, **kwargs):
        return False

    def checkbox(self, *args, **kwargs):
        return False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def __format__(self, format_spec):
        return "MockValue"


def _build_dashboard_streamlit_mock() -> _DashboardStreamlitMock:
    def passthrough(func=None, **kwargs):
        # Mirror @st.cache_data / @st.cache_resource used with or without args.
        if func is not None:
            return func
        return lambda f: f

    mock = _DashboardStreamlitMock()
    mock.session_state = {}
    mock.query_params = {}
    mock.cache_resource = passthrough
    mock.cache_data = passthrough
    return mock


def _is_streamlit_or_dashboard(name: str) -> bool:
    return (
        name == "streamlit"
        or name.startswith("streamlit.")
        or name == "scripts.dashboard"
        or name.startswith("scripts.dashboard.")
    )


@pytest.fixture
def dashboard_app():
    """Import the Streamlit dashboard against a hermetic mock, order-independent.

    Yields a namespace of the dashboard entry points the smoke tests render. The
    dashboard package is (re)imported while the mock is installed so every view's
    module-level ``import streamlit as st`` binds to the mock — never to a real
    streamlit a prior test may have left in sys.modules. The original sys.modules
    state is restored on teardown so the mock never leaks to other tests.
    """
    # Snapshot everything we are about to mutate so teardown can fully restore.
    saved = {
        name: module
        for name, module in sys.modules.items()
        if _is_streamlit_or_dashboard(name)
    }
    # Drop any already-imported dashboard modules so they re-bind to the mock.
    # (Dashboard modules only do `import streamlit as st`, never submodule
    # imports, so the real streamlit.* entries can stay cached untouched.)
    for name in list(sys.modules):
        if name == "scripts.dashboard" or name.startswith("scripts.dashboard."):
            del sys.modules[name]

    mock_st = _build_dashboard_streamlit_mock()
    sys.modules["streamlit"] = mock_st
    try:
        views = importlib.import_module("scripts.dashboard.views")
        yield types.SimpleNamespace(
            st=mock_st,
            DashboardConfig=importlib.import_module(
                "scripts.dashboard.config"
            ).DashboardConfig,
            load_dashboard_data=importlib.import_module(
                "scripts.dashboard.data_loader"
            ).load_dashboard_data,
            get_page_meta=importlib.import_module(
                "scripts.dashboard.page_meta"
            ).get_page_meta,
            render_page_frame=importlib.import_module(
                "scripts.dashboard.components.page_frame"
            ).render_page_frame,
            render_command_center=importlib.import_module(
                "scripts.dashboard.components.command_center"
            ).render_command_center,
            render_drill_down=importlib.import_module(
                "scripts.dashboard.views.inspector"
            ).render_drill_down,
            views=views,
        )
    finally:
        for name in list(sys.modules):
            if _is_streamlit_or_dashboard(name):
                del sys.modules[name]
        sys.modules.update(saved)
