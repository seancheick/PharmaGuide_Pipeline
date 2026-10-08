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

from test_profiles import (  # noqa: E402
    ARTIFACT_TEST_FILES,
    RELEASE_TEST_FILES,
    SLOW_TEST_FILES,
)


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
        "   heavy suite (~1 hr). See AGENTS.md > Tests.\033[0m\n\n"
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

# Preparation keeps a complete collection inventory before selecting source
# nodes. This is structured process evidence, never a clinical approval.
_PREPARATION = {'nodes': [], 'outcomes': {}, 'collection_errors': [], 'collection_skips': []}
_PREPARATION_CONFIG = None
_PREPARATION_WRITTEN = 0.0
_PREPARATION_ACTIVE = set()


def pytest_sessionstart(session):
    global _PREPARATION_CONFIG, _PREPARATION_WRITTEN
    _PREPARATION_CONFIG = session.config
    _PREPARATION_WRITTEN = 0.0
    _PREPARATION_ACTIVE.clear()
    if os.environ.get('PG_PREPARATION_REPORT'):
        _PREPARATION.clear()
        _PREPARATION.update(nodes=[], outcomes={}, collection_errors=[], collection_skips=[])
        _write_preparation_progress()


@pytest.hookimpl(trylast=True)
def pytest_collection_finish(session):
    if not os.environ.get('PG_PREPARATION_REPORT'):
        return
    _PREPARATION['selection'] = {key: getattr(session.config.option, key, None)
        for key in ('keyword', 'markexpr', 'deselect', 'ignore', 'ignore_glob')}
    _PREPARATION['selection']['args'] = list(session.config.args)
    from test_profiles import preparation_phase
    for item in session.items:
        phase, reason = preparation_phase(Path(str(item.path)).name, item.originalname or item.name,
            markers=[marker.name for marker in item.iter_markers()])
        _PREPARATION['nodes'].append({'nodeid': item.nodeid, 'phase': phase, 'reason': reason})
    if os.environ.get('PG_PREPARATION_MODE') == 'source' and not session.config.option.collectonly:
        selected = {row['nodeid'] for row in _PREPARATION['nodes'] if row['phase'] == 'source'}
        removed = [item for item in session.items if item.nodeid not in selected]
        session.items[:] = [item for item in session.items if item.nodeid in selected]
        session.config.hook.pytest_deselected(items=removed)
        session.testscollected = len(session.items)
    _PREPARATION['selected_tests'] = sum(row['phase'] == 'source' for row in _PREPARATION['nodes'])
    _write_preparation_progress(force=True)


def _write_preparation_progress(*, force=False):
    global _PREPARATION_WRITTEN
    import time
    if _PREPARATION_CONFIG is not None and hasattr(_PREPARATION_CONFIG, 'workerinput'):
        return
    now = time.monotonic()
    if not force and now - _PREPARATION_WRITTEN < 5:
        return
    _PREPARATION_WRITTEN = now
    path = os.environ.get('PG_PREPARATION_REPORT')
    if path:
        from preflight import _atomic_report
        _atomic_report(Path(path), dict(_PREPARATION, completed=False, exit_code=None))


def pytest_collectreport(report):
    if os.environ.get('PG_PREPARATION_REPORT') and report.skipped:
        _PREPARATION['collection_skips'].append({'nodeid': report.nodeid, 'reason': str(report.longrepr)})
        _write_preparation_progress()
    if os.environ.get('PG_PREPARATION_REPORT') and report.failed:
        _PREPARATION['collection_errors'].append(str(report.longrepr))
        _write_preparation_progress()


def pytest_runtest_logreport(report):
    if not os.environ.get('PG_PREPARATION_REPORT'):
        return
    outcome = {'when': report.when, 'outcome': report.outcome}
    if report.skipped:
        outcome['reason'] = str(report.longrepr[2]) if isinstance(report.longrepr, tuple) else str(report.longrepr)
    _PREPARATION['outcomes'].setdefault(report.nodeid, []).append(outcome)
    if report.failed or report.skipped:
        outcome['details'] = str(report.longrepr)
    if report.failed:
        _PREPARATION.setdefault('failures', []).append(report.nodeid)
        print(f'FAILED: {report.nodeid}', file=sys.stderr, flush=True)
    if report.when == 'teardown':
        _PREPARATION_ACTIVE.discard(report.nodeid)
        _PREPARATION['current_test'] = ' | '.join(sorted(_PREPARATION_ACTIVE)) or 'finishing'
        _PREPARATION['finished_tests'] = _PREPARATION.get('finished_tests', 0) + 1
        _emit_preparation_progress()
    _write_preparation_progress(force=report.failed or report.skipped)


def pytest_sessionfinish(session, exitstatus):
    path = os.environ.get('PG_PREPARATION_REPORT')
    if path:
        from preflight import _atomic_report, _combine_preparation_workers
        if hasattr(session.config, 'workerinput'):
            session.config.workeroutput['preparation'] = dict(_PREPARATION, completed=True, exit_code=int(exitstatus))
            return
        workers = _PREPARATION.pop('workers', [])
        evidence = _combine_preparation_workers(workers) if getattr(session.config.option, 'numprocesses', None) else dict(_PREPARATION)
        evidence.update(completed=True, exit_code=int(exitstatus))
        _atomic_report(Path(path), evidence)


@pytest.hookimpl(optionalhook=True)
def pytest_testnodedown(node, error):
    if not os.environ.get('PG_PREPARATION_REPORT'):
        return
    payload = node.workeroutput.get('preparation')
    if error or not isinstance(payload, dict):
        payload = {'completed': False, 'collection_errors': [str(error or 'Missing worker evidence')]}
    _PREPARATION.setdefault('workers', []).append(payload)


@pytest.hookimpl(optionalhook=True)
def pytest_xdist_node_collection_finished(node, ids):
    if os.environ.get('PG_PREPARATION_REPORT'):
        _PREPARATION['selected_tests'] = len(ids)
        _write_preparation_progress(force=True)


def _emit_preparation_progress():
    if _PREPARATION_CONFIG is None or not hasattr(_PREPARATION_CONFIG, 'workerinput'):
        import json
        progress = {'current_test': _PREPARATION.get('current_test', 'collecting'),
                    'finished_tests': _PREPARATION.get('finished_tests', 0),
                    'selected_tests': _PREPARATION.get('selected_tests', '?')}
        print('PG_PREPARATION_PROGRESS:' + json.dumps(progress), file=sys.stderr, flush=True)


def pytest_runtest_logstart(nodeid, location):
    if os.environ.get('PG_PREPARATION_REPORT'):
        _PREPARATION_ACTIVE.add(nodeid)
        _PREPARATION['current_test'] = ' | '.join(sorted(_PREPARATION_ACTIVE))
        _emit_preparation_progress()
        _write_preparation_progress()
