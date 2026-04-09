from __future__ import annotations

import streamlit as st


PLANE_STYLES = {
    "Release Snapshot": ("#e0f2fe", "#0f172a", "#0d9488"),
    "Pipeline Logs": ("#fff7ed", "#0f172a", "#f59e0b"),
    "Dataset Outputs": ("#ecfeff", "#0f172a", "#14b8a6"),
}


def render_source_chips(data_planes: list[str]) -> None:
    chips = []
    for plane in data_planes:
        background, text, border = PLANE_STYLES.get(plane, ("#f8fafc", "#0f172a", "#cbd5e1"))
        chips.append(
            f"""
            <span style="
                display:inline-block;
                margin:0 8px 8px 0;
                padding:6px 10px;
                border-radius:999px;
                background:{background};
                color:{text};
                border:1px solid {border};
                font-size:0.82rem;
                font-weight:600;
            ">{plane}</span>
            """
        )
    try:
        st.markdown("".join(chips), unsafe_allow_html=True)
    except Exception:
        return
