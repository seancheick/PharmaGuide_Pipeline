from typing import Any

import streamlit as st


def metric_card(label: str, value: Any, color: str = "#14b8a6"):
    """Renders a styled metric card."""
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(240,253,250,0.92) 100%);
            border: 1px solid rgba(15,23,42,0.08);
            border-top: 4px solid {color};
            border-radius: 18px;
            padding: 16px 18px;
            box-shadow: 0 14px 28px rgba(15, 23, 42, 0.06);
            min-height: 96px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        ">
          <div style="
              font-family: 'Plus Jakarta Sans', sans-serif;
              font-size: 0.82rem;
              text-transform: uppercase;
              letter-spacing: 0.08em;
              color: #475569;
              margin-bottom: 0.45rem;
          ">{label}</div>
          <div style="
              font-family: 'Source Serif 4', serif;
              font-size: 1.45rem;
              line-height: 1.1;
              color: #0f172a;
          ">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def metric_row(metrics: list[tuple[str, Any]]):
    """Renders a row of metric cards."""
    try:
        cols = st.columns(len(metrics))
        if not isinstance(cols, (list, tuple)) or len(cols) < len(metrics):
            raise ValueError("columns unavailable")
    except Exception:
        cols = [st for _ in metrics]
    for i, (label, value) in enumerate(metrics):
        with cols[i]:
            metric_card(label, value)
