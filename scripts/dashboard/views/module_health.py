"""Module Health — per-module V4 pillar comparison.

V4 routes each product to a scoring module (generic / multi_or_prenatal / omega /
probiotic / sports). A systematic scorer bug usually shows up as ONE module's
pillar distribution collapsing relative to the others — invisible in a
catalog-wide average. This view puts module means/medians side by side so a
broken module is a single bad row, not a support ticket.

`module_pillar_summary` is a pure function (DataFrame -> DataFrame) for testing.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from scripts.dashboard.components.score_breakdown import V4_PILLARS
from scripts.dashboard.data_loader import filter_product_catalog

PILLAR_COLS = [col for _lbl, col, _mx in V4_PILLARS]


def module_pillar_summary(df: pd.DataFrame) -> pd.DataFrame:
    """One row per v4_module: product count, mean total, and mean per pillar."""
    if df.empty or "v4_module" not in df.columns:
        return pd.DataFrame()
    rows = []
    for module, grp in df.groupby(df["v4_module"].fillna("(none)")):
        row = {"v4_module": module, "products": len(grp)}
        total_col = "score_v4" if "score_v4" in grp.columns else ("score" if "score" in grp.columns else None)
        row["mean_total"] = round(grp[total_col].mean(), 1) if total_col and grp[total_col].notna().any() else None
        for lbl, col, _mx in V4_PILLARS:
            row[lbl] = round(grp[col].mean(), 1) if col in grp.columns and grp[col].notna().any() else None
        rows.append(row)
    out = pd.DataFrame(rows)
    return out.sort_values("products", ascending=False).reset_index(drop=True)


def render_module_health(data):
    st.subheader("Module Health (per-module pillar comparison)")
    frame = filter_product_catalog(data)
    st.caption(
        f"Rows in scope: {0 if frame.empty else len(frame):,}. Compare each "
        "scoring module's pillar means — an outlier column is a systematic bug signal."
    )
    if frame.empty or "v4_module" not in frame.columns:
        st.warning("No module data in scope.")
        return

    summary = module_pillar_summary(frame)
    if summary.empty:
        st.warning("No products with a v4_module assignment.")
        return

    pillar_labels = [lbl for lbl, _c, _m in V4_PILLARS]
    have_pillars = any(summary[lbl].notna().any() for lbl in pillar_labels if lbl in summary.columns)

    st.markdown("#### Per-module pillar means")
    st.dataframe(summary, width="stretch", hide_index=True)

    if not have_pillars:
        st.info(
            "Pillar means are empty until the catalog is rebuilt "
            "(`scripts/rebuild_dashboard_snapshot.sh`). Product counts + mean "
            "total are shown above in the meantime."
        )
        return

    # Heatmap-style comparison: pillars on x, modules on y.
    melt = summary.melt(
        id_vars=["v4_module"],
        value_vars=[lbl for lbl in pillar_labels if lbl in summary.columns],
        var_name="pillar",
        value_name="mean",
    ).dropna(subset=["mean"])
    if not melt.empty:
        import plotly.express as px

        fig = px.density_heatmap(
            melt, x="pillar", y="v4_module", z="mean",
            color_continuous_scale="RdYlGn", text_auto=True,
        )
        fig.update_layout(
            height=320, margin=dict(l=20, r=20, t=20, b=20),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
