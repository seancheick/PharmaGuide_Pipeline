import streamlit as st

from .command_center import render_command_center
from .page_frame import inject_dashboard_theme, render_page_frame
from .source_chips import render_source_chips


def _safe_columns(spec):
    try:
        columns = st.columns(spec)
        expected = spec if isinstance(spec, int) else len(spec)
        if isinstance(columns, (list, tuple)) and len(columns) >= expected:
            return list(columns[:expected])
    except Exception:
        pass
    fallback_count = spec if isinstance(spec, int) else len(spec)
    return [st for _ in range(fallback_count)]


def _safe_tabs(labels):
    try:
        tabs = st.tabs(labels)
        if isinstance(tabs, (list, tuple)) and len(tabs) >= len(labels):
            return list(tabs[: len(labels)])
    except Exception:
        pass
    return [st for _ in labels]
