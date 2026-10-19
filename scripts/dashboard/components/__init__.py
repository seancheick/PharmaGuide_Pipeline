"""Dashboard UI components (theme, shared widgets, page frame)."""

import streamlit as st


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

