"""
Section D (Brand Trust) Audit Dashboard

Monitors brand trust scoring, third-party testing, full disclosure,
manufacturer reputation, and certification gaps.
"""

from __future__ import annotations

from collections import defaultdict

import pandas as pd
import plotly.express as px
import streamlit as st

from scripts.dashboard.components.data_table import data_table
from scripts.dashboard.components.metric_cards import metric_row
from scripts.dashboard.data_loader import filter_product_catalog


def render_audit_section_d(data):
    """Main rendering function for Section D audit dashboard."""
    filtered_catalog = filter_product_catalog(data)
    allowed_ids = set(filtered_catalog["dsld_id"].astype(str)) if not filtered_catalog.empty else None
    st.caption(f"Release rows in scope: {0 if filtered_catalog.empty else len(filtered_catalog)}")

    section_d_data = _extract_section_d_data(data, allowed_ids)

    _render_summary(section_d_data)
    st.divider()
    _render_score_distribution(section_d_data)
    st.divider()

    tab_trust, tab_gaps, tab_brands, tab_details = st.tabs(
        ["Trust Signal Breakdown", "Trust Gaps", "Brand Leaderboard", "Detailed Analysis"]
    )
    with tab_trust:
        _render_trust_signals(section_d_data)
    with tab_gaps:
        _render_trust_gaps(section_d_data)
    with tab_brands:
        _render_brand_trust_leaderboard(section_d_data)
    with tab_details:
        _render_detailed_analysis(section_d_data)


def _extract_section_d_data(data, allowed_ids):
    result = {"products": [], "scores": []}
    if data.product_catalog.empty:
        st.warning("No release product catalog available")
        return result

    for _, row in data.product_catalog.iterrows():
        dsld_id = str(row["dsld_id"])
        if allowed_ids is not None and dsld_id not in allowed_ids:
            continue
        sec_d = float(row.get("section_d_score") or 0)
        sec_d_max = float(row.get("section_d_max") or 5)
        result["products"].append({
            "dsld_id": dsld_id,
            "product_name": row["product_name"],
            "brand_name": row["brand_name"],
            "supplement_type": row.get("supplement_type", ""),
            "section_d_score": sec_d,
            "section_d_max": sec_d_max,
            "score_100": float(row.get("score") or 0),
            "verdict": row.get("verdict", ""),
            "trusted_mfr": bool(row.get("is_trusted_manufacturer")),
            "third_party": bool(row.get("has_third_party_testing")),
            "full_disclosure": bool(row.get("has_full_disclosure")),
        })
        result["scores"].append(sec_d)
    return result


def _render_summary(data):
    st.write("### Section D Brand Trust Summary")
    if not data["products"]:
        st.info("No data available.")
        return

    total = len(data["products"])
    avg = sum(data["scores"]) / total if total else 0
    trusted = sum(1 for p in data["products"] if p["trusted_mfr"])
    tpt = sum(1 for p in data["products"] if p["third_party"])
    fd = sum(1 for p in data["products"] if p["full_disclosure"])
    zero_trust = sum(1 for s in data["scores"] if s == 0)
    max_trust = sum(1 for s in data["scores"] if s >= 4.5)

    metric_row([
        ("Total Products", total),
        ("Avg Section D", f"{avg:.1f}/5"),
        ("Trusted Manufacturer", f"{trusted} ({trusted/total*100:.0f}%)"),
        ("Third-Party Tested", f"{tpt} ({tpt/total*100:.0f}%)"),
        ("Full Disclosure", f"{fd} ({fd/total*100:.0f}%)"),
        ("Zero Trust", zero_trust),
        ("Max Trust (4.5+)", max_trust),
    ])


def _render_score_distribution(data):
    st.write("### Section D Score Distribution")
    if not data["scores"]:
        return

    col1, col2 = st.columns([3, 1])
    with col2:
        threshold = st.slider("Trust threshold", 0.0, 5.0, 2.0, 0.5, key="d_threshold")
    with col1:
        df = pd.DataFrame({"score": data["scores"]})
        fig = px.histogram(df, x="score", nbins=20, title="Score Distribution",
                           labels={"score": "Section D Score (out of 5)"})
        fig.add_vline(x=threshold, line_dash="dash", line_color="orange",
                      annotation_text=f"Threshold: {threshold}")
        fig.update_xaxes(range=[0, 5])
        st.plotly_chart(fig, width="stretch")

    below = sum(1 for s in data["scores"] if s < threshold)
    st.caption(f"**{below}** products below threshold of {threshold}")


def _render_trust_signals(data):
    st.write("### Trust Signal Breakdown")
    if not data["products"]:
        return

    total = len(data["products"])
    signals = {
        "Trusted Manufacturer": sum(1 for p in data["products"] if p["trusted_mfr"]),
        "Third-Party Tested": sum(1 for p in data["products"] if p["third_party"]),
        "Full Disclosure": sum(1 for p in data["products"] if p["full_disclosure"]),
    }

    col1, col2 = st.columns(2)
    with col1:
        sig_df = pd.DataFrame([{"Signal": k, "Products": v, "Pct": round(v/total*100, 1)}
                                for k, v in signals.items()])
        fig = px.bar(sig_df, x="Signal", y="Products", title="Trust Signal Coverage",
                     text="Pct", color="Signal")
        fig.update_traces(texttemplate='%{text}%', textposition='outside')
        st.plotly_chart(fig, width="stretch")

    with col2:
        # Signal combinations
        combos = defaultdict(int)
        for p in data["products"]:
            sigs = []
            if p["trusted_mfr"]:
                sigs.append("Trusted")
            if p["third_party"]:
                sigs.append("3P-Tested")
            if p["full_disclosure"]:
                sigs.append("Disclosed")
            combos[" + ".join(sorted(sigs)) if sigs else "None"] += 1

        st.write("#### Signal Combinations")
        combo_df = pd.DataFrame([{"Signals": k, "Count": v, "Pct": round(v/total*100, 1)}
                                  for k, v in sorted(combos.items(), key=lambda x: -x[1])])
        data_table(combo_df, max_rows=15)


def _render_trust_gaps(data):
    st.write("### Trust Gaps — Products Missing Signals")
    if not data["products"]:
        return

    col1, col2 = st.columns([1, 1])
    with col1:
        missing_filter = st.multiselect("Show products missing",
            ["Trusted Manufacturer", "Third-Party Testing", "Full Disclosure"],
            default=["Trusted Manufacturer"], key="d_gap_filter")
    with col2:
        only_safe = st.checkbox("Only SAFE/CAUTION products", value=True, key="d_only_safe")

    gap_products = []
    for p in data["products"]:
        if only_safe and p["verdict"] not in ("SAFE", "CAUTION"):
            continue
        missing = []
        if "Trusted Manufacturer" in missing_filter and not p["trusted_mfr"]:
            missing.append("Manufacturer")
        if "Third-Party Testing" in missing_filter and not p["third_party"]:
            missing.append("3P Testing")
        if "Full Disclosure" in missing_filter and not p["full_disclosure"]:
            missing.append("Disclosure")
        if missing:
            gap_products.append({**p, "missing_signals": ", ".join(missing)})

    st.metric("Products with trust gaps", len(gap_products))
    if gap_products:
        gap_products.sort(key=lambda p: p["section_d_score"])
        df = pd.DataFrame([{
            "DSLD ID": p["dsld_id"],
            "Product": f"{p['brand_name']} - {p['product_name'][:35]}",
            "Type": p["supplement_type"],
            "Section D": f"{p['section_d_score']:.1f}/5",
            "Score 100": f"{p['score_100']:.0f}",
            "Verdict": p["verdict"],
            "Trusted": "Y" if p["trusted_mfr"] else "",
            "3P Test": "Y" if p["third_party"] else "",
            "Disclosed": "Y" if p["full_disclosure"] else "",
            "Missing": p["missing_signals"],
        } for p in gap_products[:500]])
        st.dataframe(df, width="stretch", height=400)
        csv = df.to_csv(index=False)
        st.download_button("Download CSV", csv, "section_d_trust_gaps.csv", "text/csv", key="d_csv1")


def _render_brand_trust_leaderboard(data):
    st.write("### Brand Trust Leaderboard")
    if not data["products"]:
        return

    brand_data = defaultdict(lambda: {"scores": [], "trusted": 0, "tpt": 0, "fd": 0})
    for p in data["products"]:
        b = brand_data[p["brand_name"]]
        b["scores"].append(p["section_d_score"])
        if p["trusted_mfr"]:
            b["trusted"] += 1
        if p["third_party"]:
            b["tpt"] += 1
        if p["full_disclosure"]:
            b["fd"] += 1

    rows = []
    for brand, d in brand_data.items():
        total = len(d["scores"])
        if total < 2:
            continue
        rows.append({
            "Brand": brand,
            "Products": total,
            "Avg D": round(sum(d["scores"]) / total, 2),
            "Trusted Mfr": "Y" if d["trusted"] > 0 else "",
            "3P Tested %": round(d["tpt"] / total * 100, 0),
            "Disclosed %": round(d["fd"] / total * 100, 0),
        })

    col1, col2 = st.columns(2)
    with col1:
        st.write("#### Highest Trust")
        top = sorted(rows, key=lambda r: r["Avg D"], reverse=True)
        data_table(pd.DataFrame(top[:25]), max_rows=25)
    with col2:
        st.write("#### Lowest Trust")
        bottom = sorted(rows, key=lambda r: r["Avg D"])
        data_table(pd.DataFrame(bottom[:25]), max_rows=25)


def _render_detailed_analysis(data):
    st.write("### Detailed Analysis")
    if not data["products"]:
        return

    col1, col2 = st.columns(2)
    with col1:
        st.write("#### Trust by Supplement Type")
        type_data = defaultdict(list)
        for p in data["products"]:
            type_data[p["supplement_type"]].append(p["section_d_score"])
        rows = [{"Type": t, "Products": len(s), "Avg D": round(sum(s)/len(s), 2),
                 "Zero Trust": sum(1 for x in s if x == 0)}
                for t, s in type_data.items() if s]
        rows.sort(key=lambda r: r["Avg D"], reverse=True)
        data_table(pd.DataFrame(rows), max_rows=20)

    with col2:
        st.write("#### Trust Score vs Overall Score")
        sample = data["products"][:500]
        if sample:
            scatter_df = pd.DataFrame([{
                "Section D": p["section_d_score"],
                "Score 100": p["score_100"],
                "Type": p["supplement_type"],
            } for p in sample])
            fig = px.scatter(scatter_df, x="Section D", y="Score 100", color="Type",
                             title="Trust vs Overall Score", opacity=0.5)
            st.plotly_chart(fig, width="stretch")

    st.divider()
    st.write("#### Score Statistics")
    scores = data["scores"]
    if scores:
        sorted_scores = sorted(scores)
        stats = {
            "Mean": f"{sum(scores)/len(scores):.2f}",
            "Median": f"{sorted_scores[len(scores)//2]:.2f}",
            "Zero": sum(1 for s in scores if s == 0),
            "0-1": sum(1 for s in scores if 0 < s <= 1),
            "1-2": sum(1 for s in scores if 1 < s <= 2),
            "2-3": sum(1 for s in scores if 2 < s <= 3),
            "3-4": sum(1 for s in scores if 3 < s <= 4),
            "4-5": sum(1 for s in scores if 4 < s <= 5),
        }
        cols = st.columns(len(stats))
        for i, (label, value) in enumerate(stats.items()):
            with cols[i]:
                st.metric(label, value)
