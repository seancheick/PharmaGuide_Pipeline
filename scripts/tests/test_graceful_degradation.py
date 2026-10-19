"""Dashboard must degrade gracefully when DB, artifacts or the index are missing.

Exercised against the hermetic Streamlit mock from the ``dashboard_app``
fixture (see conftest.py) so the import-time streamlit swap is robust to test
order.
"""
from pathlib import Path

from scripts.release_artifact_paths import final_build_dir


def test_graceful_degradation(dashboard_app, tmp_path, monkeypatch):
    """Every page renders without raising when scan/build paths and the index don't exist."""
    monkeypatch.setenv("PG_DASHBOARD_CACHE", str(tmp_path / "no_index"))
    config = dashboard_app.DashboardConfig(
        scan_dir=Path("non_existent_scan").resolve(),
        build_root=Path("non_existent_build").resolve(),
    )
    data = dashboard_app.load_dashboard_data(config)
    ctx = dashboard_app.shell.init(data)
    assert not ctx.ready
    for spec in dashboard_app.navigation.PAGES:
        dashboard_app.view(spec.module).render(ctx)  # must not raise


def test_trace_on_real_product(dashboard_app):
    config = dashboard_app.DashboardConfig(
        scan_dir=Path("scripts/products").resolve(),
        build_root=final_build_dir(),
    )
    data = dashboard_app.load_dashboard_data(config)
    ctx = dashboard_app.shell.init(data)
    if not ctx.ready:
        return
    row = ctx.products().iloc[0]
    dashboard_app.st.session_state["trace_dsld_id"] = str(row["dsld_id"])
    dashboard_app.view("trace").render(ctx)
