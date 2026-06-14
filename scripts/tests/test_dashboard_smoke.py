"""Headless smoke tests: every dashboard view must render without raising.

The Streamlit dashboard is exercised against a hermetic mock provided by the
``dashboard_app`` fixture (see conftest.py), which makes the import-time
streamlit swap robust regardless of test order. These tests don't assert on
rendered output — they guard against a view crashing on real data shapes (e.g.
NULL pillar columns), so they must keep rendering all views, not skip them.
"""
from pathlib import Path


def test_all_dashboard_views_smoke_render(dashboard_app):
    config = dashboard_app.DashboardConfig(
        scan_dir=Path("scripts/products").resolve(),
        build_root=Path("scripts/final_db_output").resolve(),
    )
    data = dashboard_app.load_dashboard_data(config)

    views = dashboard_app.views
    view_renderers = [
        ("command-center", lambda: dashboard_app.render_command_center(data)),
        ("product-inspector", lambda: views.render_inspector(data)),
        ("pipeline-health", lambda: views.render_health(data)),
        ("data-quality", lambda: views.render_quality(data)),
        ("observability", lambda: views.render_observability(data)),
        ("release-diff", lambda: views.render_diff(data)),
        ("batch-diff", lambda: views.render_batch_diff(data)),
        ("intelligence", lambda: views.render_intelligence(data)),
        ("pillar-audit", lambda: views.render_pillar_audit(data)),
        ("suppression-audit", lambda: views.render_suppression_audit(data)),
        ("scoring-integrity", lambda: views.render_scoring_integrity(data)),
        ("module-health", lambda: views.render_module_health(data)),
    ]

    for slug, renderer in view_renderers:
        dashboard_app.render_page_frame(dashboard_app.get_page_meta(slug, data), renderer)


def test_inspector_drilldown_renders_v4_for_real_product(dashboard_app):
    """The smoke test above can't reach the Inspector drill-down (empty search
    short-circuits), so exercise it directly against a real product to cover the
    V4 six-pillar rendering path."""
    config = dashboard_app.DashboardConfig(
        scan_dir=Path("scripts/products").resolve(),
        build_root=Path("scripts/final_db_output").resolve(),
    )
    data = dashboard_app.load_dashboard_data(config)
    if data.product_catalog.empty:
        return
    dsld_id = str(data.product_catalog.iloc[0]["dsld_id"])
    dashboard_app.render_drill_down(dsld_id, data)  # must not raise
