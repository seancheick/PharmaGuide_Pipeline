import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock


class MockStreamlit(MagicMock):
    def __getattr__(self, name):
        if name in {"sidebar", "expander"}:
            return MockStreamlit()
        return super().__getattr__(name)

    def columns(self, spec):
        n = spec if isinstance(spec, int) else len(spec)
        return [MockStreamlit() for _ in range(n)]

    def tabs(self, labels):
        return [MockStreamlit() for _ in labels]

    def selectbox(self, label, options=None, **kwargs):
        if options:
            return options[0]
        return None

    def radio(self, label, options=None, **kwargs):
        if options:
            return options[0]
        return None

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


mock_st = MockStreamlit()
mock_st.session_state = {}
mock_st.query_params = {}


def passthrough(func=None, **kwargs):
    if func is not None:
        return func
    return lambda f: f


mock_st.cache_resource = passthrough
mock_st.cache_data = passthrough
sys.modules["streamlit"] = mock_st

from scripts.dashboard.config import DashboardConfig
from scripts.dashboard.components.command_center import render_command_center
from scripts.dashboard.components.page_frame import render_page_frame
from scripts.dashboard.data_loader import load_dashboard_data
from scripts.dashboard.page_meta import get_page_meta
from scripts.dashboard.views import (
    render_batch_diff,
    render_diff,
    render_health,
    render_inspector,
    render_intelligence,
    render_observability,
    render_quality,
)


def _create_empty_export(build_root: Path) -> None:
    build_root.mkdir(parents=True, exist_ok=True)
    (build_root / "detail_blobs").mkdir(exist_ok=True)
    (build_root / "detail_index.json").write_text("{}")
    (build_root / "export_manifest.json").write_text(
        """{
  "db_version": "empty-test",
  "pipeline_version": "test",
  "scoring_version": "test",
  "generated_at": "2026-04-09T00:00:00+00:00",
  "product_count": 0,
  "checksum": "sha256:test",
  "detail_blob_count": 0,
  "detail_blob_unique_count": 0,
  "detail_index_checksum": "sha256:test",
  "min_app_version": "1.0.0",
  "schema_version": 1,
  "errors": []
}"""
    )
    (build_root / "export_audit_report.json").write_text(
        """{
  "counts": {
    "total_exported": 0,
    "total_errors": 0,
    "enriched_only": 0,
    "scored_only": 0,
    "has_banned_substance": 0,
    "has_recalled_ingredient": 0,
    "has_harmful_additives": 0,
    "has_allergen_risks": 0,
    "has_watchlist_hit": 0,
    "has_high_risk_hit": 0,
    "verdict_blocked": 0,
    "verdict_unsafe": 0,
    "verdict_caution": 0,
    "verdict_not_scored": 0
  },
  "contract_failures": [],
  "products_with_warnings_count": 0,
  "products_with_warnings_sample": []
}"""
    )
    conn = sqlite3.connect(build_root / "pharmaguide_core.db")
    conn.execute(
        """
        CREATE TABLE products_core (
            dsld_id TEXT,
            product_name TEXT,
            brand_name TEXT,
            score_100_equivalent REAL,
            grade TEXT,
            verdict TEXT,
            mapped_coverage REAL,
            blocking_reason TEXT,
            supplement_type TEXT,
            form_factor TEXT,
            product_status TEXT,
            upc_sku TEXT
        )
        """
    )
    conn.execute("CREATE VIRTUAL TABLE products_fts USING fts5(dsld_id, product_name, brand_name)")
    conn.commit()
    conn.close()


def test_dashboard_views_handle_empty_db(tmp_path: Path):
    build_root = tmp_path / "build"
    scan_dir = tmp_path / "scan"
    scan_dir.mkdir()
    (scan_dir / "logs").mkdir()
    (scan_dir / "logs" / "processing_state.json").write_text(
        '{"started":"2026-04-09T00:00:00Z","last_updated":"2026-04-09T00:00:00Z","processed_files":0,"total_files":0,"errors":[],"can_resume":true}'
    )
    _create_empty_export(build_root)

    config = DashboardConfig(scan_dir=scan_dir.resolve(), build_root=build_root.resolve())
    data = load_dashboard_data(config)

    view_renderers = [
        ("command-center", lambda: render_command_center(data)),
        ("product-inspector", lambda: render_inspector(data)),
        ("pipeline-health", lambda: render_health(data)),
        ("data-quality", lambda: render_quality(data)),
        ("observability", lambda: render_observability(data)),
        ("release-diff", lambda: render_diff(data)),
        ("batch-diff", lambda: render_batch_diff(data)),
        ("intelligence", lambda: render_intelligence(data)),
    ]

    for slug, renderer in view_renderers:
        render_page_frame(get_page_meta(slug, data), renderer)
