"""
Section C (Evidence & Research) Audit Dashboard

Monitors clinical evidence scoring, identifies products with zero evidence,
and highlights gaps in backed clinical studies coverage.
"""

from __future__ import annotations

from collections import defaultdict

import pandas as pd
import plotly.express as px
import streamlit as st

from scripts.dashboard.components.data_table import data_table
from scripts.dashboard.components.metric_cards import metric_row
from scripts.dashboard.data_loader import filter_product_catalog


def render_audit_section_c(data):
    """Main rendering function for Section C audit dashboard."""
    filtered_catalog = filter_product_catalog(data)
    allowed_ids = set(filtered_catalog["dsld_id"].astype(str)) if not filtered_catalog.empty else None
    st.caption(f"Release rows in scope: {0 if filtered_catalog.empty else len(filtered_catalog)}")

    section_c_data = _extract_section_c_data(data, allowed_ids)

    _render_summary(section_c_data)
    st.divider()
    _render_score_distribution(section_c_data)
    st.divider()

    tab_zero, tab_high, tab_by_type, tab_details = st.tabs(
        ["Zero Evidence", "Strongest Evidence", "By Supplement Type", "Detailed Analysis"]
    )
    with tab_zero:
        _render_zero_evidence(section_c_data)
    with tab_high:
        _render_high_evidence(section_c_data)
    with tab_by_type:
        _render_by_supplement_type(section_c_data)
    with tab_details:
        _render_detailed_analysis(section_c_data)


def _extract_section_c_data(data, allowed_ids):
    result = {"products": [], "scores": []}
    if data.product_catalog.empty:
        st.warning("No release product catalog available")
        return result

    for _, row in data.product_catalog.iterrows():
        dsld_id = str(row["dsld_id"])
        if allowed_ids is not None and dsld_id not in allowed_ids:
            continue
        sec_c = float(row.get("section_c_score") or 0)
        sec_c_max = float(row.get("section_c_max") or 20)
        result["products"].append({
            "dsld_id": dsld_id,
            "product_name": row["product_name"],
            "brand_name": row["brand_name"],
            "supplement_type": row.get("supplement_type", ""),
            "section_c_score": sec_c,
            "section_c_max": sec_c_max,
            "score_100": float(row.get("score") or 0),
            "verdict": row.get("verdict", ""),
            "section_a_score": float(row.get("section_a_score") or 0),
        })
        result["scores"].append(sec_c)
    return result


def _render_summary(data):
    st.write("### Section C Evidence & Research Summary")
    if not data["products"]:
        st.info("No data available.")
        return

    total = len(data["products"])
    avg = sum(data["scores"]) / total if total else 0
    zero_evidence = sum(1 for s in data["scores"] if s == 0)
    has_evidence = total - zero_evidence
    high_evidence = sum(1 for s in data["scores"] if s >= 10)

    metric_row([
        ("Total Products", total),
        ("Avg Section C", f"{avg:.1f}/20"),
        ("Zero Evidence", f"{zero_evidence} ({zero_evidence/total*100:.0f}%)"),
        ("Has Evidence", f"{has_evidence} ({has_evidence/total*100:.0f}%)"),
        ("Strong Evidence (10+)", high_evidence),
    ])


def _render_score_distribution(data):
    st.write("### Section C Score Distribution")
    if not data["scores"]:
        return

    col1, col2 = st.columns([3, 1])
    with col2:
        threshold = st.slider("Evidence threshold", 0.0, 20.0, 5.0, 0.5, key="c_threshold")
    with col1:
        df = pd.DataFrame({"score": data["scores"]})
        fig = px.histogram(df, x="score", nbins=20, title="Score Distribution",
                           labels={"score": "Section C Score (out of 20)"})
        fig.add_vline(x=threshold, line_dash="dash", line_color="orange",
                      annotation_text=f"Threshold: {threshold}")
        fig.update_xaxes(range=[0, 20])
        st.plotly_chart(fig, width="stretch")

    below = sum(1 for s in data["scores"] if s < threshold)
    st.caption(f"**{below}** products below threshold of {threshold}")


def _render_zero_evidence(data):
    st.write("### Products With Zero Evidence Score")
    if not data["products"]:
        return

    col1, col2 = st.columns([1, 1])
    with col1:
        verdict_filter = st.multiselect("Filter by verdict",
            ["SAFE", "CAUTION", "POOR", "UNSAFE", "BLOCKED", "NOT_SCORED"],
            default=["SAFE", "CAUTION"], key="c_verdict_filter")
    with col2:
        type_filter = st.multiselect("Filter by type",
            sorted(set(p["supplement_type"] for p in data["products"])),
            key="c_type_filter")

    zero_products = [
        p for p in data["products"]
        if p["section_c_score"] == 0
        and (not verdict_filter or p["verdict"] in verdict_filter)
        and (not type_filter or p["supplement_type"] in type_filter)
    ]
    zero_products.sort(key=lambda p: p["score_100"], reverse=True)

    st.metric("Zero-evidence products matching filters", len(zero_products))
    st.caption("These products have NO clinical evidence backing. High-scoring SAFE products here are candidates for evidence enrichment.")

    if zero_products:
        df = pd.DataFrame([{
            "DSLD ID": p["dsld_id"],
            "Product": f"{p['brand_name']} - {p['product_name'][:35]}",
            "Type": p["supplement_type"],
            "Section A": f"{p['section_a_score']:.1f}",
            "Section C": f"{p['section_c_score']:.1f}/20",
            "Score 100": f"{p['score_100']:.0f}",
            "Verdict": p["verdict"],
        } for p in zero_products[:500]])
        st.dataframe(df, width="stretch", height=400)
        csv = df.to_csv(index=False)
        st.download_button("Download CSV", csv, "section_c_zero_evidence.csv", "text/csv", key="c_csv1")


def _render_high_evidence(data):
    st.write("### Strongest Evidence Products")
    if not data["products"]:
        return

    threshold = st.slider("Min evidence score", 0.0, 20.0, 10.0, 0.5, key="c_high_thresh")
    high = sorted([p for p in data["products"] if p["section_c_score"] >= threshold],
                  key=lambda p: p["section_c_score"], reverse=True)

    st.metric("Products with strong evidence", len(high))
    if high:
        df = pd.DataFrame([{
            "DSLD ID": p["dsld_id"],
            "Product": f"{p['brand_name']} - {p['product_name'][:35]}",
            "Type": p["supplement_type"],
            "Section C": f"{p['section_c_score']:.1f}/20",
            "Score 100": f"{p['score_100']:.0f}",
            "Verdict": p["verdict"],
        } for p in high[:200]])
        st.dataframe(df, width="stretch", height=400)


def _render_by_supplement_type(data):
    st.write("### Evidence Coverage by Supplement Type")
    if not data["products"]:
        return

    type_data = defaultdict(lambda: {"scores": [], "zero": 0, "has": 0})
    for p in data["products"]:
        t = p["supplement_type"]
        type_data[t]["scores"].append(p["section_c_score"])
        if p["section_c_score"] == 0:
            type_data[t]["zero"] += 1
        else:
            type_data[t]["has"] += 1

    rows = []
    for t, d in type_data.items():
        total = len(d["scores"])
        rows.append({
            "Type": t,
            "Products": total,
            "Avg C": round(sum(d["scores"]) / total, 1) if total else 0,
            "Zero Evidence": d["zero"],
            "Has Evidence": d["has"],
            "Coverage %": round(d["has"] / total * 100, 1) if total else 0,
        })
    rows.sort(key=lambda r: r["Coverage %"])

    col1, col2 = st.columns(2)
    with col1:
        df = pd.DataFrame(rows)
        if not df.empty:
            fig = px.bar(df, x="Type", y="Coverage %", title="Evidence Coverage by Type",
                         color="Coverage %", color_continuous_scale="RdYlGn")
            st.plotly_chart(fig, width="stretch")
    with col2:
        data_table(pd.DataFrame(rows), max_rows=20)


def _render_detailed_analysis(data):
    st.write("### Detailed Analysis")
    if not data["products"]:
        return

    col1, col2 = st.columns(2)
    with col1:
        st.write("#### Evidence by Brand (top coverage)")
        brand_data = defaultdict(list)
        for p in data["products"]:
            brand_data[p["brand_name"]].append(p["section_c_score"])
        rows = [{"Brand": b, "Products": len(s), "Avg C": round(sum(s)/len(s), 1),
                 "With Evidence": sum(1 for x in s if x > 0),
                 "Coverage %": round(sum(1 for x in s if x > 0) / len(s) * 100, 1)}
                for b, s in brand_data.items() if len(s) >= 3]
        rows.sort(key=lambda r: r["Coverage %"], reverse=True)
        data_table(pd.DataFrame(rows[:30]), max_rows=30)

    with col2:
        st.write("#### Evidence by Brand (worst coverage)")
        rows_worst = sorted(rows, key=lambda r: r["Coverage %"])
        data_table(pd.DataFrame(rows_worst[:30]), max_rows=30)

    st.divider()
    st.write("#### Score Statistics")
    scores = data["scores"]
    if scores:
        sorted_scores = sorted(scores)
        stats = {
            "Mean": f"{sum(scores)/len(scores):.1f}",
            "Median": f"{sorted_scores[len(scores)//2]:.1f}",
            "Zero": sum(1 for s in scores if s == 0),
            "1-5": sum(1 for s in scores if 0 < s <= 5),
            "6-10": sum(1 for s in scores if 5 < s <= 10),
            "11-15": sum(1 for s in scores if 10 < s <= 15),
            "16-20": sum(1 for s in scores if 15 < s <= 20),
        }
        cols = st.columns(len(stats))
        for i, (label, value) in enumerate(stats.items()):
            with cols[i]:
                st.metric(label, value)
