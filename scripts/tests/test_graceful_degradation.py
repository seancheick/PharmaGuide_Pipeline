"""Dashboard must degrade gracefully when DB/artifacts are missing.

Exercised against the hermetic Streamlit mock from the ``dashboard_app``
fixture (see conftest.py) so the import-time streamlit swap is robust to test
order.
"""
from pathlib import Path


def test_graceful_degradation(dashboard_app):
    """Views render without raising even when scan/build paths don't exist."""
    config = dashboard_app.DashboardConfig(
        scan_dir=Path("non_existent_scan").resolve(),
        build_root=Path("non_existent_build").resolve(),
    )

    data = dashboard_app.load_dashboard_data(config)

    # Must not raise on a fully empty/missing dataset.
    dashboard_app.views.render_inspector(data)
    dashboard_app.views.render_health(data)
    dashboard_app.views.render_quality(data)


def test_inspector_drill_down_real_product(dashboard_app):
    config = dashboard_app.DashboardConfig(
        scan_dir=Path("scripts/products").resolve(),
        build_root=Path("scripts/final_db_output").resolve(),
    )

    data = dashboard_app.load_dashboard_data(config)

    if data.db_conn is None:
        return

    row = data.db_conn.execute(
        "SELECT dsld_id FROM products_core LIMIT 1"
    ).fetchone()
    assert row is not None

    dashboard_app.render_drill_down(row["dsld_id"], data)
