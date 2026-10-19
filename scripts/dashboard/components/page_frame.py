from __future__ import annotations

from collections.abc import Callable
from typing import Any

import streamlit as st

from scripts.dashboard.components.ui import chips, page_header


def render_page_frame(meta: dict[str, Any], body_renderer: Callable[[], None]) -> None:
    """Full-width page: header, the page body, then sources and freshness on demand."""
    page_header(meta["page_title"], meta["page_summary"])
    if meta.get("show_mixed_plane_warning") and meta.get("mixed_plane_warning"):
        st.caption(meta["mixed_plane_warning"])
    body_renderer()
    with st.expander("Sources, freshness and notes", icon=":material/info:"):
        chips((plane, "accent") for plane in meta.get("data_planes", []))
        for item in meta.get("freshness_display", []):
            st.caption(f"{item['label']}: {item['value']}")
        for note in meta.get("usage_notes", []):
            st.caption(note)
        st.code("\n".join(meta.get("source_paths", [])) or "—", language="text")
