import sys
from pathlib import Path
from unittest.mock import MagicMock


class MockStreamlit(MagicMock):
    def __getattr__(self, name):
        if name in {"sidebar", "expander"}:
            return MockStreamlit()
        return super().__getattr__(name)

    def columns(self, spec, **kwargs):
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

from scripts.dashboard.components.command_center import render_command_center
from scripts.dashboard.components.page_frame import render_page_frame
from scripts.dashboard.config import DashboardConfig
from scripts.dashboard.data_loader import load_dashboard_data
from scripts.dashboard.page_meta import get_page_meta


def test_command_center_and_page_frame_render():
    config = DashboardConfig(
        scan_dir=Path("scripts/products").resolve(),
        build_root=Path("scripts/final_db_output").resolve(),
    )
    data = load_dashboard_data(config)
    meta = get_page_meta("command-center", data)

    render_page_frame(meta, lambda: render_command_center(data))
