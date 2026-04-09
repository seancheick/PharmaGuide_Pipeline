from __future__ import annotations

import streamlit as st
from scripts.dashboard.components.status_badge import status_badge


def _safe_columns(spec):
    try:
        columns = st.columns(spec)
    except Exception:
        return []
    if isinstance(columns, (list, tuple)):
        return list(columns)
    return []

def product_header(
    name: str, 
    brand: str, 
    verdict: str, 
    grade: str, 
    score: float,
    percentile: str | None = None
):
    """
    Renders the product header with name, brand, verdict badge, grade, and score.
    """
    verdict_colors = {
        "SAFE": "safe",
        "CAUTION": "caution",
        "POOR": "poor",
        "UNSAFE": "unsafe",
        "BLOCKED": "blocked",
        "NOT_SCORED": "not_scored"
    }
    
    header_cols = _safe_columns([3, 1])
    if len(header_cols) >= 2:
        col1, col2 = header_cols[:2]
        with col1:
            st.subheader(name)
            st.caption(f"Brand: {brand}")

        with col2:
            status_badge(verdict, verdict_colors.get(verdict, "info"))
    else:
        try:
            st.subheader(name)
            st.caption(f"Brand: {brand}")
        except Exception:
            return

    metric_cols = _safe_columns(3)
    if len(metric_cols) >= 3:
        m1, m2, m3 = metric_cols[:3]
        with m1:
            st.metric("Final Score", f"{score:.1f}/100")
        with m2:
            st.metric("Grade", grade)
        with m3:
            if percentile:
                st.metric("Percentile", percentile)
            else:
                st.metric("Percentile", "N/A")
    else:
        try:
            st.write(f"Final Score: {score:.1f}/100")
            st.write(f"Grade: {grade}")
            st.write(f"Percentile: {percentile or 'N/A'}")
        except Exception:
            return
