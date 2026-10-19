"""Score Lab: how scoring behaves across the catalog. Reads receipts; never recomputes."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from scripts.dashboard import shell
from scripts.dashboard.components.theme import KIND_COLORS, PILLAR_COLORS, TOKENS
from scripts.dashboard.components.ui import kind_label, kpis, table
from scripts.dashboard.saved_views import ABSORB_MIN
from scripts.dashboard.score_index import PILLAR_LABELS, PILLARS, QUALITY_CONFIG

PEER_MIN_N = 30
EPS = 0.05


def rule_impact(receipts: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    """Per receipt line: how often it fires and how many points it moves (as recorded)."""
    if receipts.empty:
        return pd.DataFrame()
    joined = receipts.merge(products[["dsld_id", "module"]], on="dsld_id", how="left")
    grouped = joined.groupby(["pillar", "entry_id", "kind"])
    out = grouped.agg(products=("dsld_id", "nunique"), mean_points=("points", "mean"), median_points=("points", "median"),
                      max_abs=("points", lambda s: s.abs().max()), catalog_total=("points", "sum"),
                      routes=("module", "nunique")).reset_index()
    out["pillar"] = out["pillar"].map(PILLAR_LABELS)
    out["type"] = out["kind"].map(kind_label)
    return out.sort_values("catalog_total", key=lambda s: s.abs(), ascending=False)


def absorption(ledgers: pd.DataFrame) -> pd.DataFrame:
    charged = ledgers[ledgers["nominal_deductions"] < -EPS].copy()
    if charged.empty:
        return pd.DataFrame()
    absorbed = charged["realized_deductions"] - charged["nominal_deductions"]
    charged["outcome"] = np.select(  # fully absorbed first: a small deduction can be both
        [charged["realized_deductions"].abs() <= EPS, absorbed.abs() <= ABSORB_MIN],
        ["fully absorbed by a floor", "fully realized"], default="partly absorbed")
    out = charged.groupby(["pillar", "outcome"]).agg(products=("dsld_id", "nunique"),
                                                     nominal=("nominal_deductions", "sum"),
                                                     realized=("realized_deductions", "sum")).reset_index()
    out["pillar"] = out["pillar"].map(PILLAR_LABELS)
    return out


def peer_percentiles(products: pd.DataFrame) -> pd.DataFrame:
    """Within-category position for complete scored products (n ≥ 30). Context, never a score."""
    pool = products[(products["quality_score_status"] == "scored") & (products["quality_assessment_status"] == "complete")
                    & products["total"].notna() & products["category"].notna()].copy()
    config_column = "config_fingerprint" if "config_fingerprint" in pool else "config_version"
    groups = ["category", config_column] if config_column in pool else ["category"]
    sizes = pool.groupby(groups, dropna=False)["dsld_id"].transform("count")
    pool = pool[sizes >= PEER_MIN_N]
    pool["peer_n"] = pool.groupby(groups, dropna=False)["dsld_id"].transform("count")
    pool["peer_percentile"] = pool.groupby(groups, dropna=False)["total"].rank(pct=True, method="average").mul(100).round(1)
    median = pool.groupby(groups, dropna=False)["total"].transform("median")
    pool["vs_peer_median"] = (pool["total"] - median).round(1)
    return pool[["dsld_id", "product_name", "brand_name", "category", "total", "peer_percentile", "peer_n", "vs_peer_median"]]


def render(ctx: shell.PageContext) -> None:
    if not shell.banner(ctx):
        return
    products = ctx.products()
    receipts = ctx.frame("receipts")
    ledgers = ctx.frame("ledgers")
    scored = products[products["quality_score_status"] == "scored"]
    if scored.empty:
        st.info("No scored products in this run.")
        return

    tabs = st.tabs(["Distributions", "Rule impact", "Neutral usage", "Deductions & floors", "Caps", "Threshold cliffs",
                    "Correlation", "Peer percentile"])
    with tabs[0]:
        pillar = st.segmented_control("Pillar", ["total", *PILLARS], default="total",
                                      format_func=lambda p: "Overall" if p == "total" else PILLAR_LABELS[p], key="sl_pillar")
        column = "total" if pillar in (None, "total") else f"pillar_{pillar}"
        color = TOKENS["accent"] if column == "total" else PILLAR_COLORS[pillar]
        order = scored.groupby("module")[column].median().sort_values().index.tolist()
        fig = go.Figure()
        for module in order:
            values = scored.loc[scored["module"] == module, column]
            fig.add_box(x=values, name=f"{module} (n={len(values):,})", marker={"color": color}, line={"width": 1.5},
                        boxpoints=False, orientation="h")
        fig.update_layout(height=max(260, 34 * len(order)), showlegend=False,
                          title={"text": f"{'Overall score' if column == 'total' else PILLAR_LABELS[pillar]} by route", "font": {"size": 14}})
        st.plotly_chart(fig, width="stretch", key="sl_box")
        st.caption("Each box is one route; drill into products in Product Explorer with the same filters.")
    with tabs[1]:
        impact = rule_impact(receipts, products)
        table(impact[["pillar", "entry_id", "type", "products", "mean_points", "median_points", "max_abs",
                      "catalog_total", "routes"]] if not impact.empty else impact,
              key="sl_impact", name="rule_impact", run_key=ctx.run_key, height=480,
              caption="Recorded receipt points per line. 'Catalog total' is the sum across all products.",
              column_config={c: st.column_config.NumberColumn(format="%.2f") for c in
                             ("mean_points", "median_points", "max_abs", "catalog_total")})
    with tabs[2]:
        neutral = receipts[receipts["kind"] == "neutral"]
        usage = (neutral.groupby(["pillar", "entry_id", "basis"], dropna=False)
                 .agg(products=("dsld_id", "nunique"), points=("points", "mean")).reset_index()
                 .sort_values("products", ascending=False))
        usage["pillar"] = usage["pillar"].map(PILLAR_LABELS)
        kpis([("Dose neutral-only", f"{scored['neutral_only_pillars'].map(lambda v: 'dose' in list(v)).sum():,}", None),
              ("Verification neutral 6", f"{scored['verification_fail_open'].fillna(False).astype(bool).sum():,}",
               "Fail-open neutral: unknown, not failed"),
              ("Unrated forms", f"{scored['receipt_entry_ids'].map(lambda v: bool({'A1_unrated_neutral', 'panel_form_quality_unrated_neutral'} & set(v))).sum():,}", None)])
        table(usage, key="sl_neutral", name="neutral_usage", run_key=ctx.run_key, height=380)
    with tabs[3]:
        led = ledgers[ledgers["dsld_id"].isin(scored["dsld_id"])]
        lost = led.groupby("pillar").agg(deducted=("realized_deductions", "sum"), not_earned=("unawarded", "sum")).reset_index()
        fig = go.Figure()
        fig.add_bar(y=lost["pillar"].map(PILLAR_LABELS), x=-lost["deducted"], orientation="h", name="Points deducted",
                    marker={"color": KIND_COLORS["deduction"]})
        fig.add_bar(y=lost["pillar"].map(PILLAR_LABELS), x=lost["not_earned"], orientation="h", name="Never earned",
                    marker={"color": KIND_COLORS["not_earned"], "line": {"color": TOKENS["border_strong"], "width": 1}})
        fig.update_layout(barmode="group", height=320, xaxis={"title": "points across scored products"},
                          title={"text": "Lost (deducted) vs never earned", "font": {"size": 14}})
        st.plotly_chart(fig, width="stretch", key="sl_lost")
        table(absorption(led), key="sl_absorb", name="deduction_absorption", run_key=ctx.run_key, height=260,
              caption="Nominal = charged by rules; realized = effect on the public score; the difference was absorbed by floors.")
    with tabs[4]:
        caps = receipts[receipts["kind"].isin(["cap", "floor"])]
        summary = caps.groupby(["pillar", "entry_id", "kind"]).agg(products=("dsld_id", "nunique"),
                                                                   points=("points", "sum")).reset_index()
        summary["pillar"] = summary["pillar"].map(PILLAR_LABELS)
        summary["type"] = summary["kind"].map(kind_label)
        table(summary.sort_values("products", ascending=False), key="sl_caps", name="caps_floors", run_key=ctx.run_key,
              height=360, caption="Negative points = withheld by a cap; positive = restored by a floor.")
    with tabs[5]:
        tiers = json.loads(QUALITY_CONFIG.read_text(encoding="utf-8"))["tiers"]
        band = st.slider("Within points of a tier cutoff", 0.1, 2.0, 0.5, 0.1, key="sl_band")
        rows = []
        for tier in tiers:
            if tier["min"] <= 0:
                continue
            near = scored[(scored["total"] - tier["min"]).abs() <= band]
            rows.append({"cutoff": tier["min"], "tier at/above": tier["name"], "products within band": len(near),
                         "ships below the cutoff": int((near["shipped_total"] < tier["min"]).sum())})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        refs = ctx.frame("dose_refs")
        if not refs.empty:
            ul = refs[refs["pct_ul"].between(95, 105) | refs["pct_ul"].between(145, 155)]
            st.caption(f"{ul['dsld_id'].nunique():,} products have an ingredient within 5 points of 100% or 150% of its upper limit.")
            table(ul, key="sl_ul_cliff", name="ul_cliffs", run_key=ctx.run_key, height=260)
    with tabs[6]:
        corr = scored[[f"pillar_{p}" for p in PILLARS]].corr().round(2)
        labels = [PILLAR_LABELS[p] for p in PILLARS]
        fig = go.Figure(go.Heatmap(z=corr.values, x=labels, y=labels, zmin=-1, zmax=1,
                                   colorscale=[[0, "#9F2929"], [0.5, "#F2EFE9"], [1, "#183B3F"]],
                                   text=corr.values, texttemplate="%{text}", hovertemplate="%{y} × %{x}: %{z}<extra></extra>"))
        fig.update_layout(height=420, title={"text": "Pillar correlation (scored products)", "font": {"size": 14}})
        st.plotly_chart(fig, width="stretch", key="sl_corr")
    with tabs[7]:
        st.caption(f"Peer percentile is context within one run and config: complete scored products only, categories "
                   f"with at least {PEER_MIN_N} products, denominator shown. It is never a score and feeds nothing.")
        table(peer_percentiles(products), key="sl_peer", name="peer_percentile", run_key=ctx.run_key, height=440)
