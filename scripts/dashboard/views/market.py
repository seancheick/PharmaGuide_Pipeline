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
                      pct_70_plus=("shipped_total", lambda s: round((s >= 70).mean() * 100, 1)),
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
        labelled = products.assign(category=products["category"].fillna("none"),
                                   verification_tier=products["verification_tier"].fillna("none"))
        tiers = labelled.groupby(["category", "verification_tier"]).size().unstack(fill_value=0)
        tiers.columns = [str(column) for column in tiers.columns]  # NaN labels break Arrow serialization
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
        _ingredients(ctx, products)


def form_share(ingredients: pd.DataFrame, products: pd.DataFrame, canonical_id: str,
               min_products: int = BRAND_MIN) -> pd.DataFrame:
    """Share of each recorded form among a brand's products containing one ingredient."""
    rows = ingredients[ingredients["canonical_id"] == canonical_id].drop_duplicates(["dsld_id", "matched_form"])
    rows = rows.merge(products[["dsld_id", "brand_name"]], on="dsld_id", how="inner")
    rows["form"] = rows["matched_form"].fillna("form not identified")
    counts = rows.groupby(["brand_name", "form"])["dsld_id"].nunique().rename("products").reset_index()
    brand_products = rows.groupby("brand_name")["dsld_id"].nunique()
    counts["share_pct"] = (counts["products"] / counts["brand_name"].map(brand_products) * 100).round(1)
    return counts[counts["brand_name"].map(brand_products) >= min_products]


def _ingredients(ctx: shell.PageContext, products: pd.DataFrame) -> None:
    status = ctx.index.ingredient_staleness()
    if not status["built"]:
        st.info("The ingredient index is not built yet. It is separate from the core index because it reads the "
                "large enriched set.", icon=":material/construction:")
        st.code("python -m scripts.dashboard.score_index refresh --ingredients", language="bash")
        return
    if status["stale"]:
        st.warning(f"Ingredient index is stale ({len(status['changed'])} batch(es) changed since "
                   f"{status['built_at']}). Run `refresh --ingredients`.", icon=":material/update:")
    ingredients = ctx.index.ingredient_frame()
    meta = ctx.index.ingredient_frame("product_meta")
    named = ingredients.dropna(subset=["canonical_id"])
    usage = named.groupby("canonical_id").agg(products=("dsld_id", "nunique"), name=("standard_name", "first")) \
        .reset_index().sort_values("products", ascending=False)
    labels = {r.canonical_id: f"{r.name or r.canonical_id} · {r.products:,} products" for r in usage.head(400).itertuples()}
    if not labels:
        st.info("No mapped ingredients in the ingredient index.")
        return
    picked = st.selectbox("Ingredient", list(labels), format_func=labels.get, key="mk_ing")
    rows = ingredients[ingredients["canonical_id"] == picked]
    with_scores = rows.drop_duplicates("dsld_id").merge(
        products[["dsld_id", "total", "quality_score_status", "brand_name"]], on="dsld_id", how="left")
    forms = rows.assign(form=rows["matched_form"].fillna("form not identified")).groupby("form").agg(
        products=("dsld_id", "nunique"), mean_bio_score=("bio_score", "mean")).reset_index()
    scored = with_scores[with_scores["quality_score_status"] == "scored"]
    kpis([("Products", f"{rows['dsld_id'].nunique():,}", None),
          ("Brands", f"{with_scores['brand_name'].nunique():,}", None),
          ("Forms recorded", f"{rows['matched_form'].nunique():,}", None),
          ("Median score", f"{scored['total'].median():.1f}" if not scored.empty else "—", "Scored products containing it")])
    left, right = st.columns([3, 2])
    with left:
        share = form_share(ingredients, products, picked)
        if share.empty:
            st.caption(f"No brand has {BRAND_MIN}+ products with this ingredient.")
        else:
            top = share.groupby("brand_name")["products"].sum().sort_values(ascending=False).head(20).index
            share = share[share["brand_name"].isin(top)]
            fig = go.Figure()
            for form, group in share.groupby("form"):
                fig.add_bar(y=group["brand_name"], x=group["share_pct"], orientation="h", name=str(form)[:40],
                            customdata=group["products"], marker={"line": {"color": TOKENS["surface"], "width": 2}},
                            hovertemplate=f"{form}<br>%{{y}}: %{{x:.0f}}% (%{{customdata}} products)<extra></extra>")
            fig.update_layout(barmode="stack", height=max(320, 24 * len(top) + 140),
                              xaxis={"title": "% of the brand's products", "range": [0, 100]},
                              title={"text": f"Form share by brand (brands with ≥ {BRAND_MIN} products)", "font": {"size": 14}})
            st.plotly_chart(fig, width="stretch", key="mk_form_share")
    with right:
        table(forms.sort_values("products", ascending=False), key="mk_forms", name=f"forms_{picked}", run_key=ctx.run_key,
              height=320, column_config={"mean_bio_score": st.column_config.NumberColumn(format="%.1f")})
    refs = ctx.frame("dose_refs")
    refs = refs[refs["canonical_id"] == picked] if not refs.empty else refs
    if not refs.empty:
        over = int((refs["pct_ul"] > 100).sum())
        fig = go.Figure(go.Histogram(x=refs["pct_rda"].dropna().clip(upper=1000), nbinsx=50,
                                     marker={"color": TOKENS["accent"]},
                                     hovertemplate="%{x:.0f}% of RDA/AI: %{y:,} products<extra></extra>"))
        fig.update_layout(height=260, xaxis={"title": "% of RDA/AI per day (capped at 1000%)"},
                          title={"text": f"Dose vs reference — {over:,} rows above the upper limit", "font": {"size": 14}})
        st.plotly_chart(fig, width="stretch", key="mk_dose_hist")
    if not meta.empty:
        years = meta.merge(rows[["dsld_id"]].drop_duplicates(), on="dsld_id", how="inner")
        years["year"] = pd.to_datetime(years["entry_date"], errors="coerce").dt.year
        years["market"] = years["off_market"].map({True: "off market", False: "on market"}).fillna("unknown")
        trend = years.dropna(subset=["year"]).groupby(["year", "market"]).size().rename("products").reset_index()
        fig = go.Figure()
        for market_state, group in trend.groupby("market"):
            fig.add_bar(x=group["year"], y=group["products"], name=market_state)
        fig.update_layout(barmode="stack", height=260, xaxis={"title": "DSLD entry year"}, yaxis={"title": "products"},
                          title={"text": "New labels by DSLD entry year", "font": {"size": 14}})
        st.plotly_chart(fig, width="stretch", key="mk_years")
