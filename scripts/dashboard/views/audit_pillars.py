"""V4 Six-Pillar Audit — replaces the V3 Section A/B/C/D audits.

The V4 scorer is a six-pillar /100 model (formulation 20, dose 20, evidence 20,
transparency 15, verification 15, safety_hygiene 10). Per-pillar component scores
are projected into products_core (pillar_*_v4 columns) by build_final_db. This
view audits each pillar's distribution and surfaces the lowest scorers.

A companion Suppression Audit lists products with
quality_score_status='suppressed_safety' — hidden from users in production and
excluded from every scored view, shown here for review only.
"""
from __future__ import annotations

import plotly.express as px
import streamlit as st

from scripts.dashboard.components.score_breakdown import V4_PILLARS
from scripts.dashboard.data_loader import filter_product_catalog


def render_pillar_audit(data):
    """Six-pillar V4 audit. One tab per pillar (distribution + lowest scorers)."""
    dataset_scope = st.session_state.get("dataset_filter", "All Datasets")
    frame = filter_product_catalog(data)
    st.subheader("V4 Six-Pillar Audit")
    st.caption(
        f"Dataset scope: {dataset_scope} | Rows in scope: "
        f"{0 if frame.empty else len(frame):,} | Safety-suppressed products are "
        "excluded (see Suppression Audit)."
    )
    if frame.empty:
        st.warning("No products in scope.")
        return

    have_pillars = any(
        col in frame.columns and frame[col].notna().any()
        for _lbl, col, _mx in V4_PILLARS
    )
    if not have_pillars:
        st.info(
            "No V4 pillar columns populated in this build yet. Rebuild the catalog "
            "(`scripts/rebuild_dashboard_snapshot.sh`) so build_final_db projects "
            "the six `pillar_*_v4` columns, then reload."
        )
        return

    # Mean-per-pillar summary row.
    cols = st.columns(len(V4_PILLARS))
    for col, (label, column, mx) in zip(cols, V4_PILLARS):
        if column in frame.columns and frame[column].notna().any():
            col.metric(label, f"{frame[column].mean():.1f}/{mx}")
        else:
            col.metric(label, "n/a")

    st.divider()
    tabs = st.tabs([lbl for lbl, _c, _m in V4_PILLARS])
    for tab, (label, column, mx) in zip(tabs, V4_PILLARS):
        with tab:
            _render_single_pillar(frame, label, column, mx)


def _render_single_pillar(frame, label: str, column: str, mx: int):
    if column not in frame.columns or not frame[column].notna().any():
        st.info(f"No `{column}` data in the current build.")
        return

    series = frame[column].dropna()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Scored", f"{len(series):,}")
    c2.metric("Mean", f"{series.mean():.1f}/{mx}")
    c3.metric("Median", f"{series.median():.1f}/{mx}")
    c4.metric("At ceiling", f"{int((series >= mx).sum()):,}")

    fig = px.histogram(x=series, nbins=min(int(mx) + 1, 40))
    fig.update_layout(
        height=260,
        margin=dict(l=20, r=20, t=20, b=20),
        showlegend=False,
        xaxis_title=f"{label} score (max {mx})",
        yaxis_title="Products",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    st.caption(f"Lowest {label} scorers in scope")
    show_cols = [
        c for c in ["dsld_id", "product_name", "brand_name", "v4_module", column, "score_v4", "score"]
        if c in frame.columns
    ]
    lowest = frame.dropna(subset=[column]).sort_values(column).head(50)[show_cols]
    st.dataframe(lowest, width="stretch", hide_index=True)


def render_suppression_audit(data):
    """Products safety-suppressed by the V4 gate — hidden from users in the app.

    Reads the UNFILTERED catalog (filter_product_catalog excludes these), so it
    is the one place the dashboard surfaces them, for audit only.
    """
    st.subheader("Suppression Audit (safety-gated)")
    frame = data.product_catalog
    if frame.empty or "quality_score_status" not in frame.columns:
        st.warning("No catalog / status data available.")
        return

    suppressed = frame[frame["quality_score_status"].fillna("scored") == "suppressed_safety"]
    st.caption(
        f"{len(suppressed):,} products are safety-suppressed "
        "(v4_confidence='blocked_by_safety_gate'). Production hides these from "
        "users; they are excluded from every scored view."
    )
    if suppressed.empty:
        st.success("No safety-suppressed products in the catalog.")
        return

    show_cols = [
        c for c in ["dsld_id", "product_name", "brand_name", "verdict", "v4_module", "blocking_reason"]
        if c in suppressed.columns
    ]
    st.dataframe(
        suppressed[show_cols].sort_values("brand_name" if "brand_name" in show_cols else show_cols[0]),
        width="stretch",
        hide_index=True,
    )
