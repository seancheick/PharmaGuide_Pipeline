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


def test_all_dashboard_views_smoke_render():
    config = DashboardConfig(
        scan_dir=Path("scripts/products").resolve(),
        build_root=Path("scripts/final_db_output").resolve(),
    )
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
