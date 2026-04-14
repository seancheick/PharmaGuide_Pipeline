"""
Section B (Safety & Purity) Audit Dashboard

Monitors safety scoring, banned/recalled substances, harmful additives,
allergen risks, and dose safety issues across the product catalog.
"""

from __future__ import annotations

from collections import defaultdict

import pandas as pd
import plotly.express as px
import streamlit as st

from scripts.dashboard.components.data_table import data_table
from scripts.dashboard.components.metric_cards import metric_row
from scripts.dashboard.data_loader import filter_product_catalog


def render_audit_section_b(data):
    """Main rendering function for Section B audit dashboard."""
    filtered_catalog = filter_product_catalog(data)
    allowed_ids = set(filtered_catalog["dsld_id"].astype(str)) if not filtered_catalog.empty else None
    st.caption(f"Release rows in scope: {0 if filtered_catalog.empty else len(filtered_catalog)}")

    section_b_data = _extract_section_b_data(data, allowed_ids)

    _render_summary(section_b_data)
    st.divider()
    _render_score_distribution(section_b_data)
    st.divider()

    tab_flags, tab_blocked, tab_low, tab_details = st.tabs(
        ["Safety Flag Breakdown", "Blocked & Unsafe", "Lowest Safety Scores", "Detailed Analysis"]
    )
    with tab_flags:
        _render_safety_flags(section_b_data)
    with tab_blocked:
        _render_blocked_products(section_b_data)
    with tab_low:
        _render_low_safety(section_b_data)
    with tab_details:
        _render_detailed_analysis(section_b_data)


def _extract_section_b_data(data, allowed_ids):
    result = {"products": [], "scores": []}
    if data.product_catalog.empty:
        st.warning("No release product catalog available")
        return result

    for _, row in data.product_catalog.iterrows():
        dsld_id = str(row["dsld_id"])
        if allowed_ids is not None and dsld_id not in allowed_ids:
            continue
        sec_b = float(row.get("section_b_score") or 0)
        sec_b_max = float(row.get("section_b_max") or 30)
        result["products"].append({
            "dsld_id": dsld_id,
            "product_name": row["product_name"],
            "brand_name": row["brand_name"],
            "supplement_type": row.get("supplement_type", ""),
            "section_b_score": sec_b,
            "section_b_max": sec_b_max,
            "score_100": float(row.get("score") or 0),
            "verdict": row.get("verdict", ""),
            "has_banned": bool(row.get("has_banned_substance")),
            "has_recalled": bool(row.get("has_recalled_ingredient")),
            "has_harmful": bool(row.get("has_harmful_additives")),
            "has_allergens": bool(row.get("has_allergen_risks")),
            "blocking_reason": str(row["blocking_reason"]) if pd.notna(row.get("blocking_reason")) else "",
        })
        result["scores"].append(sec_b)
    return result


def _render_summary(data):
    st.write("### Section B Safety & Purity Summary")
    if not data["products"]:
        st.info("No data available.")
        return

    total = len(data["products"])
    avg = sum(data["scores"]) / total if total else 0
    banned = sum(1 for p in data["products"] if p["has_banned"])
    recalled = sum(1 for p in data["products"] if p["has_recalled"])
    harmful = sum(1 for p in data["products"] if p["has_harmful"])
    allergens = sum(1 for p in data["products"] if p["has_allergens"])
    blocked = sum(1 for p in data["products"] if p["verdict"] in ("BLOCKED", "UNSAFE"))
    clean = sum(1 for p in data["products"] if not any([p["has_banned"], p["has_recalled"], p["has_harmful"], p["has_allergens"]]))

    metric_row([
        ("Total Products", total),
        ("Avg Section B", f"{avg:.1f}/30"),
        ("Clean (no flags)", f"{clean} ({clean/total*100:.0f}%)"),
        ("Banned", banned),
        ("Harmful Additives", harmful),
        ("Allergen Risks", allergens),
        ("Blocked/Unsafe", blocked),
    ])


def _render_score_distribution(data):
    st.write("### Section B Score Distribution")
    if not data["scores"]:
        return

    col1, col2 = st.columns([3, 1])
    with col2:
        threshold = st.slider("Safety alert threshold", 0.0, 30.0, 20.0, 0.5, key="b_threshold")
    with col1:
        df = pd.DataFrame({"score": data["scores"]})
        fig = px.histogram(df, x="score", nbins=30, title="Score Distribution",
                           labels={"score": "Section B Score (out of 30)"})
        fig.add_vline(x=threshold, line_dash="dash", line_color="red",
                      annotation_text=f"Alert: {threshold}")
        fig.update_xaxes(range=[0, 30])
        st.plotly_chart(fig, width="stretch")

    below = sum(1 for s in data["scores"] if s < threshold)
    st.caption(f"**{below}** products below threshold of {threshold}")


def _render_safety_flags(data):
    st.write("### Safety Flag Breakdown")
    if not data["products"]:
        return

    flag_counts = {
        "Banned substance": sum(1 for p in data["products"] if p["has_banned"]),
        "Recalled ingredient": sum(1 for p in data["products"] if p["has_recalled"]),
        "Harmful additives": sum(1 for p in data["products"] if p["has_harmful"]),
        "Allergen risks": sum(1 for p in data["products"] if p["has_allergens"]),
    }

    col1, col2 = st.columns(2)
    with col1:
        flag_df = pd.DataFrame([{"Flag": k, "Products": v} for k, v in flag_counts.items() if v > 0])
        if not flag_df.empty:
            fig = px.bar(flag_df, x="Flag", y="Products", title="Products by Safety Flag", color="Flag")
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No safety flags detected.")

    with col2:
        # Overlap analysis
        combos = defaultdict(int)
        for p in data["products"]:
            flags = []
            if p["has_banned"]:
                flags.append("Banned")
            if p["has_recalled"]:
                flags.append("Recalled")
            if p["has_harmful"]:
                flags.append("Harmful")
            if p["has_allergens"]:
                flags.append("Allergens")
            if flags:
                combos[" + ".join(sorted(flags))] += 1
        if combos:
            st.write("#### Flag Combinations")
            combo_df = pd.DataFrame([{"Flags": k, "Count": v} for k, v in sorted(combos.items(), key=lambda x: -x[1])])
            data_table(combo_df, max_rows=20)

    # Filterable flag table
    st.write("#### Products with Safety Flags")
    flag_filter = st.multiselect("Filter by flag", ["Banned", "Recalled", "Harmful", "Allergens"],
                                 default=["Banned"], key="b_flag_filter")
    flagged = []
    for p in data["products"]:
        match = False
        if "Banned" in flag_filter and p["has_banned"]:
            match = True
        if "Recalled" in flag_filter and p["has_recalled"]:
            match = True
        if "Harmful" in flag_filter and p["has_harmful"]:
            match = True
        if "Allergens" in flag_filter and p["has_allergens"]:
            match = True
        if match:
            flagged.append(p)

    if flagged:
        df = pd.DataFrame([{
            "DSLD ID": p["dsld_id"],
            "Product": f"{p['brand_name']} - {p['product_name'][:35]}",
            "Type": p["supplement_type"],
            "Section B": f"{p['section_b_score']:.1f}/30",
            "Verdict": p["verdict"],
            "Banned": "Y" if p["has_banned"] else "",
            "Recalled": "Y" if p["has_recalled"] else "",
            "Harmful": "Y" if p["has_harmful"] else "",
            "Allergens": "Y" if p["has_allergens"] else "",
            "Block Reason": p["blocking_reason"][:40] if p["blocking_reason"] else "",
        } for p in flagged])
        st.dataframe(df, width="stretch", height=400)
        csv = df.to_csv(index=False)
        st.download_button("Download CSV", csv, "section_b_flags.csv", "text/csv", key="b_csv1")
    else:
        st.info("No products match the selected flags.")


def _render_blocked_products(data):
    st.write("### Blocked & Unsafe Products")
    blocked = [p for p in data["products"] if p["verdict"] in ("BLOCKED", "UNSAFE")]
    st.metric("Total", len(blocked))

    if not blocked:
        st.info("No blocked or unsafe products.")
        return

    # Group by blocking reason
    by_reason = defaultdict(list)
    for p in blocked:
        by_reason[p["blocking_reason"] or "Unknown reason"].append(p)

    for reason, products in sorted(by_reason.items(), key=lambda x: -len(x[1])):
        with st.expander(f"{reason} ({len(products)} products)"):
            df = pd.DataFrame([{
                "DSLD ID": p["dsld_id"],
                "Brand": p["brand_name"],
                "Product": p["product_name"][:40],
                "Type": p["supplement_type"],
                "Verdict": p["verdict"],
            } for p in products[:100]])
            data_table(df, max_rows=100)


def _render_low_safety(data):
    st.write("### Lowest Safety Scores")
    if not data["products"]:
        return

    col1, col2 = st.columns([1, 1])
    with col1:
        threshold = st.number_input("Score threshold", value=20.0, min_value=0.0, max_value=30.0, key="b_low_thresh")
    with col2:
        exclude_blocked = st.checkbox("Exclude BLOCKED/UNSAFE", value=True, key="b_exclude_blocked")

    products = sorted(data["products"], key=lambda p: p["section_b_score"])
    if exclude_blocked:
        products = [p for p in products if p["verdict"] not in ("BLOCKED", "UNSAFE")]
    products = [p for p in products if p["section_b_score"] < threshold]

    st.metric("Products below threshold", len(products))
    if products:
        df = pd.DataFrame([{
            "DSLD ID": p["dsld_id"],
            "Product": f"{p['brand_name']} - {p['product_name'][:35]}",
            "Type": p["supplement_type"],
            "Section B": f"{p['section_b_score']:.1f}/30",
            "Score 100": f"{p['score_100']:.0f}",
            "Verdict": p["verdict"],
            "Banned": "Y" if p["has_banned"] else "",
            "Harmful": "Y" if p["has_harmful"] else "",
            "Allergens": "Y" if p["has_allergens"] else "",
        } for p in products[:500]])
        st.dataframe(df, width="stretch", height=400)
        csv = df.to_csv(index=False)
        st.download_button("Download CSV", csv, "section_b_low_safety.csv", "text/csv", key="b_csv2")


def _render_detailed_analysis(data):
    st.write("### Detailed Analysis")
    if not data["products"]:
        return

    col1, col2 = st.columns(2)
    with col1:
        st.write("#### Safety Score by Supplement Type")
        type_scores = defaultdict(list)
        for p in data["products"]:
            type_scores[p["supplement_type"]].append(p["section_b_score"])
        rows = [{"Type": t, "Count": len(s), "Avg B": round(sum(s)/len(s), 1),
                 "Min B": round(min(s), 1), "Max B": round(max(s), 1)}
                for t, s in type_scores.items() if s]
        rows.sort(key=lambda r: r["Avg B"])
        data_table(pd.DataFrame(rows), max_rows=20)

    with col2:
        st.write("#### Safety Score by Brand (worst)")
        brand_scores = defaultdict(list)
        for p in data["products"]:
            brand_scores[p["brand_name"]].append(p["section_b_score"])
        rows = [{"Brand": b, "Products": len(s), "Avg B": round(sum(s)/len(s), 1),
                 "Flagged": sum(1 for sc in s if sc < 20)}
                for b, s in brand_scores.items() if len(s) >= 3]
        rows.sort(key=lambda r: r["Avg B"])
        data_table(pd.DataFrame(rows[:30]), max_rows=30)

    st.divider()
    st.write("#### Score Statistics")
    scores = data["scores"]
    if scores:
        sorted_scores = sorted(scores)
        stats = {
            "Mean": f"{sum(scores)/len(scores):.1f}",
            "Median": f"{sorted_scores[len(scores)//2]:.1f}",
            "Min": f"{min(scores):.1f}",
            "Max": f"{max(scores):.1f}",
            "Below 15": sum(1 for s in scores if s < 15),
            "15-20": sum(1 for s in scores if 15 <= s < 20),
            "20-25": sum(1 for s in scores if 20 <= s < 25),
            "25-30": sum(1 for s in scores if 25 <= s <= 30),
        }
        cols = st.columns(len(stats))
        for i, (label, value) in enumerate(stats.items()):
            with cols[i]:
                st.metric(label, value)
