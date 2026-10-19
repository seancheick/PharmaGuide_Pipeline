"""Market Intelligence: brands, categories, verification and Formula-check prevalence."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from scripts.dashboard import shell
from scripts.dashboard.components.theme import PILLAR_COLORS, TOKENS
from scripts.dashboard.components.ui import kpis, table
from scripts.dashboard.score_index import PILLAR_LABELS, PILLARS

BRAND_MIN = 5
CATEGORY_MIN = 30


def rankable(products: pd.DataFrame) -> pd.DataFrame:
    """Complete, scored products only — suppressed, not-scored and partial rows never rank."""
    return products[(products["quality_score_status"] == "scored") & (products["quality_assessment_status"] == "complete")
                    & products["total"].notna()]


def brand_leaderboard(products: pd.DataFrame, additives: pd.DataFrame, min_products: int = BRAND_MIN) -> pd.DataFrame:
    pool = rankable(products)
    additive_ids = set(additives["dsld_id"]) if not additives.empty else set()
    all_counts = products.groupby("brand_name").agg(catalog_products=("dsld_id", "count"),
                                                    suppressed=("quality_score_status", lambda s: int((s == "suppressed_safety").sum())))
    grouped = pool.groupby("brand_name")
    out = grouped.agg(ranked_products=("dsld_id", "count"), median=("total", "median"),
                      q1=("total", lambda s: s.quantile(0.25)), q3=("total", lambda s: s.quantile(0.75)),
                      pct_70_plus=("total", lambda s: round((s >= 70).mean() * 100, 1)),
                      pct_certified=("verification_cert", lambda s: round((s.fillna(0) > 0).mean() * 100, 1)),
                      pct_additive_deduction=("dsld_id", lambda s: round(s.isin(additive_ids).mean() * 100, 1)))
    out = out.join(all_counts, how="left")
    out["iqr"] = (out["q3"] - out["q1"]).round(1)
    out["completeness_pct"] = (out["ranked_products"] / out["catalog_products"] * 100).round(1)
    out = out[out["ranked_products"] >= min_products].drop(columns=["q1", "q3"]).reset_index()
    return out.sort_values(["median", "ranked_products"], ascending=[False, False])


def render(ctx: shell.PageContext) -> None:
    if not shell.banner(ctx):
        return
    products = ctx.products()
    additives = ctx.frame("additives")
    pool = rankable(products)
    kpis([("Brands", f"{products['brand_name'].nunique():,}", None),
          ("Rankable products", f"{len(pool):,}", "Complete and scored"),
          ("Categories", f"{products['category'].nunique():,}", None),
          ("With additive deduction", f"{additives['dsld_id'].nunique():,}" if not additives.empty else "0", "Formula checks")])
    tabs = st.tabs(["Brand leaderboard", "Categories", "Verification", "Additives", "Ingredients & forms"])
    with tabs[0]:
        minimum = st.slider("Minimum ranked products per brand", 1, 50, BRAND_MIN, key="mk_min")
        board = brand_leaderboard(products, additives, minimum)
        st.caption("Ranks use complete, scored products only. Median and IQR, not averages; completeness shows how much "
                   "of each brand's catalog is rankable.")
        picked = table(board, key="mk_brands", name="brand_leaderboard", run_key=ctx.run_key, select=True, height=460,
                       column_config={"median": st.column_config.NumberColumn(format="%.1f")})
        if picked:
            brand = board.iloc[picked[0]]["brand_name"]
            st.session_state["f_brand"] = [brand]
            shell.go("product-explorer")
    with tabs[1]:
        by_cat = pool.groupby("category").agg(products=("dsld_id", "count"), median=("total", "median"),
                                              **{f"mean_{p}": (f"pillar_{p}", "mean") for p in PILLARS}).reset_index()
        by_cat = by_cat[by_cat["products"] >= CATEGORY_MIN].sort_values("products", ascending=False)
        fig = go.Figure()
        for p in PILLARS:
            fig.add_bar(y=by_cat["category"], x=by_cat[f"mean_{p}"], orientation="h", name=PILLAR_LABELS[p],
                        marker={"color": PILLAR_COLORS[p], "line": {"color": TOKENS["surface"], "width": 2}},
                        hovertemplate=f"%{{y}} · {PILLAR_LABELS[p]} mean %{{x:.1f}}<extra></extra>")
        fig.update_layout(barmode="stack", height=max(320, 26 * len(by_cat) + 80), xaxis={"title": "mean points", "range": [0, 100]},
                          title={"text": f"Pillar composition by category (n ≥ {CATEGORY_MIN})", "font": {"size": 14}})
        st.plotly_chart(fig, width="stretch", key="mk_cat")
        table(by_cat, key="mk_cat_table", name="category_composition", run_key=ctx.run_key, height=300)
    with tabs[2]:
        tiers = products.groupby(["category", "verification_tier"], dropna=False).size().unstack(fill_value=0)
        table(tiers.reset_index(), key="mk_ver", name="verification_by_category", run_key=ctx.run_key, height=420,
              caption="Verification tier by category; 'unknown' is the fail-open neutral, not a failure.")
    with tabs[3]:
        if additives.empty:
            st.info("No additive penalty lines in this run.")
        else:
            prevalence = additives.groupby(["rule_id", "tier"]).agg(products=("dsld_id", "nunique"),
                                                                   mean_penalty=("penalty", "mean")).reset_index()
            table(prevalence.sort_values("products", ascending=False), key="mk_add", name="additive_prevalence",
                  run_key=ctx.run_key, height=420)
    with tabs[4]:
        st.info("Ingredient and form intelligence (form share by brand, dose vs RDA/UL by ingredient) uses the separate "
                "ingredient index, which is not built in this version yet.", icon=":material/construction:")
        refs = ctx.frame("dose_refs")
        if not refs.empty:
            st.caption("Available now from the core index: per-ingredient dose references recorded by the scorer.")
            summary = refs.groupby("nutrient").agg(products=("dsld_id", "nunique"), median_pct_rda=("pct_rda", "median"),
                                                   over_ul=("pct_ul", lambda s: int((s > 100).sum()))).reset_index()
            table(summary.sort_values("products", ascending=False), key="mk_refs", name="dose_reference_summary",
                  run_key=ctx.run_key, height=380)
