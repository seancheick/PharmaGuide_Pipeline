from __future__ import annotations

import pandas as pd
import streamlit as st

from scripts.dashboard.components import _safe_columns, _safe_tabs
from scripts.dashboard.components.data_table import data_table


def render_intelligence(data):
    tab_market, tab_ingredients, tab_brands, tab_scoring = _safe_tabs(
        ["Market Intelligence", "Ingredient Intelligence", "Brand Leaderboard", "Scoring Sensitivity"]
    )
    with tab_market:
        _render_market_intel(data)
    with tab_ingredients:
        _render_ingredient_intel(data)
    with tab_brands:
        _render_brand_leaderboard(data)
    with tab_scoring:
        _render_scoring_sensitivity(data)


def _render_market_intel(data):
    if data.db_conn is None:
        st.info("No database connection available.")
        return
    explainers = {
        str(row["dsld_id"]): row
        for row in data.blob_analytics.get("product_explainers", [])
    }
    categories = pd.read_sql_query(
        """
        SELECT supplement_type, dsld_id, product_name, brand_name, score_100_equivalent AS score, grade, verdict
        FROM products_core
        WHERE supplement_type IS NOT NULL
        ORDER BY supplement_type, score DESC
        """,
        data.db_conn,
    )
    for category, frame in categories.groupby("supplement_type"):
        with st.expander(f"Top products: {category}"):
            top_frame = frame.head(10).copy()
            top_frame["why_it_ranks_high"] = top_frame["dsld_id"].astype(str).map(
                lambda dsld_id: explainers.get(dsld_id, {}).get("explanation", "Detail blob explainer unavailable.")
            )
            data_table(top_frame, max_rows=10)

    st.write("### Why Top Products Rank High")
    top_products = categories.head(15).copy()
    if top_products.empty:
        st.info("No ranked products available.")
    else:
        explainer_rows = []
        for row in top_products.to_dict("records"):
            explainer = explainers.get(str(row["dsld_id"]), {})
            explainer_rows.append(
                {
                    "supplement_type": row["supplement_type"],
                    "dsld_id": row["dsld_id"],
                    "product_name": row["product_name"],
                    "brand_name": row["brand_name"],
                    "score": row["score"],
                    "top_bonuses": ", ".join(explainer.get("top_bonuses", [])[:3]) or "No bonus trace available",
                    "top_penalties": ", ".join(explainer.get("top_penalties", [])[:3]) or "No penalty trace available",
                }
            )
        data_table(pd.DataFrame(explainer_rows), max_rows=15)


def _render_ingredient_intel(data):
    analytics = data.blob_analytics
    query = st.text_input("Ingredient search", placeholder="Search ingredient name")
    query = query.strip() if isinstance(query, str) else ""
    if query:
        query_lower = query.lower().strip()
        matches = []
        for ingredient_name, rows in analytics.get("ingredient_products", {}).items():
            if query_lower in ingredient_name:
                matches.extend(rows)
        matches = sorted(
            matches,
            key=lambda row: (
                str(row.get("ingredient_name", "")).lower(),
                -(float(row.get("score") or 0.0)),
            ),
        )
        if matches:
            st.write("### Ingredient Search Results")
            data_table(pd.DataFrame(matches).head(100), max_rows=100)
        else:
            st.info(f"No ingredient matches found for '{query}'.")

    left, right = _safe_columns(2)
    with left:
        st.write("### Most Used Ingredients")
        usage_df = pd.DataFrame(analytics.get("ingredient_usage", []))
        if usage_df.empty:
            st.info("No ingredient usage analytics available.")
        else:
            data_table(usage_df.head(25), max_rows=25)

        st.write("### Best Forms by Ingredient")
        forms = pd.DataFrame(analytics.get("ingredient_forms", []))
        if forms.empty:
            st.info("No detail blob analytics available.")
        else:
            best_forms = forms.sort_values(["ingredient_name", "avg_product_score"], ascending=[True, False]).groupby("ingredient_name").head(1)
            data_table(best_forms.head(50), max_rows=50)
    with right:
        st.write("### High-Risk Ingredients")
        risk_df = pd.DataFrame(analytics.get("high_risk_ingredients", []))
        if risk_df.empty:
            st.info("No high-risk ingredient analytics available.")
        else:
            data_table(risk_df.head(25), max_rows=25)

        st.write("### Lowest Quality Ingredients")
        low_quality = pd.DataFrame(analytics.get("low_quality_ingredients", []))
        if low_quality.empty:
            st.info("No low-quality ingredient analytics available.")
        else:
            data_table(low_quality.head(50), max_rows=50)


def _render_brand_leaderboard(data):
    if data.db_conn is None:
        st.info("No database connection available.")
        return
    raw = pd.read_sql_query(
        """
        SELECT
            brand_name,
            score_100_equivalent AS score,
            verdict
        FROM products_core
        """,
        data.db_conn,
    )
    df = (
        raw.groupby("brand_name", as_index=False)
        .agg(
            product_count=("score", "size"),
            avg_score=("score", "mean"),
            safe_pct=("verdict", lambda values: (values.eq("SAFE").mean() * 100.0) if len(values) else 0.0),
            score_stddev=("score", lambda values: values.std(ddof=0)),
        )
        .sort_values(["avg_score", "product_count"], ascending=[False, False])
    )
    df["avg_score"] = df["avg_score"].round(1)
    df["safe_pct"] = df["safe_pct"].round(1)
    df["score_stddev"] = df["score_stddev"].fillna(0.0).round(2)
    data_table(df, max_rows=100)


def _render_scoring_sensitivity(data):
    analytics = data.blob_analytics
    left, right = _safe_columns(2)
    with left:
        st.write("### Most Common Bonuses")
        bonus_df = pd.DataFrame(analytics.get("bonus_frequency", []))
        if bonus_df.empty:
            st.info("No bonus analytics available.")
        else:
            data_table(bonus_df.head(25), max_rows=25)
    with right:
        st.write("### Most Common Penalties")
        penalty_df = pd.DataFrame(analytics.get("penalty_frequency", []))
        if penalty_df.empty:
            st.info("No penalty analytics available.")
        else:
            data_table(penalty_df.head(25), max_rows=25)

    st.write("### Average Driver Impact")
    driver_df = pd.DataFrame(analytics.get("driver_impacts", []))
    if driver_df.empty:
        st.info("No scoring driver analytics available.")
    else:
        data_table(driver_df.head(50), max_rows=50)
