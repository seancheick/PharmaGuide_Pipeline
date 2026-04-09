"""
Section A (Ingredient Quality) Audit Dashboard

Monitors ingredient quality scoring, identifies low-scoring products,
and highlights probiotic CFU detection issues.
"""

from __future__ import annotations

import json
from collections import defaultdict

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from scripts.dashboard.components.data_dictionary import field_help
from scripts.dashboard.components.data_table import data_table
from scripts.dashboard.components.metric_cards import metric_row


def render_audit_section_a(data):
    """Main rendering function for Section A audit dashboard."""
    dataset_scope = st.session_state.get("dataset_filter", "All Datasets")
    st.caption(f"Dataset scope: {dataset_scope}")

    # Extract Section A data from database
    section_a_data = _extract_section_a_data(data)
    probiotic_issues = _extract_probiotic_cfu_issues(data)

    # Summary metrics
    _render_section_a_summary(section_a_data, probiotic_issues)
    st.divider()

    # Score distribution
    _render_score_distribution(section_a_data)
    st.divider()

    # Main tabs for different views
    tab_below_threshold, tab_probiotics, tab_details = st.tabs(
        ["Products Below Threshold", "Probiotic CFU Issues", "Detailed Analysis"]
    )

    with tab_below_threshold:
        _render_below_threshold(section_a_data)

    with tab_probiotics:
        _render_probiotic_issues(probiotic_issues, section_a_data)

    with tab_details:
        _render_detailed_analysis(section_a_data, probiotic_issues)


def _extract_section_a_data(data) -> dict:
    """Extract Section A scoring data from database."""
    section_a_data = {
        "products": [],
        "scores": [],
        "verdicts": [],
        "probiotic_flags": [],
    }

    if not data.db_conn:
        st.warning("No database connection available")
        return section_a_data

    try:
        cursor = data.db_conn.cursor()
        # Query products with Section A scores
        cursor.execute("""
            SELECT 
                dsld_id,
                product_name,
                brand_name,
                supplement_type,
                json_extract(score_basis, '$.A.total') as section_a_score,
                verdict,
                json_extract(blob, '$.probiotic_detail.is_probiotic') as is_probiotic,
                json_extract(blob, '$.probiotic_detail.has_cfu') as has_cfu,
                json_extract(blob, '$.probiotic_detail.total_strain_count') as strain_count,
                json_extract(blob, '$.score_100_equivalent') as score_100
            FROM products
            ORDER BY section_a_score ASC
            LIMIT 10000
        """)

        for row in cursor.fetchall():
            try:
                dsld_id, product_name, brand_name, supp_type, sec_a_score, verdict, \
                    is_probiotic, has_cfu, strain_count, score_100 = row

                # Parse scores
                sec_a = float(sec_a_score) if sec_a_score else 0.0
                score_100_eq = float(score_100) if score_100 else 0.0

                section_a_data["products"].append({
                    "dsld_id": dsld_id,
                    "product_name": product_name,
                    "brand_name": brand_name,
                    "supplement_type": supp_type,
                    "section_a_score": sec_a,
                    "score_100": score_100_eq,
                    "verdict": verdict,
                    "is_probiotic": bool(is_probiotic),
                    "has_cfu": bool(has_cfu),
                    "strain_count": int(strain_count) if strain_count else 0,
                })
                section_a_data["scores"].append(sec_a)

            except (TypeError, ValueError):
                continue

    except Exception as e:
        st.error(f"Error querying database: {e}")

    return section_a_data


def _extract_probiotic_cfu_issues(data) -> dict:
    """Extract probiotic products with CFU detection issues."""
    issues = {
        "missing_cfu": [],  # Probiotics without CFU detected
        "low_cfu": [],      # Probiotics with very low CFU
        "multiple_strains": [],  # Multi-strain probiotics
    }

    if not data.db_conn:
        return issues

    try:
        cursor = data.db_conn.cursor()
        cursor.execute("""
            SELECT 
                dsld_id,
                product_name,
                brand_name,
                json_extract(blob, '$.probiotic_detail.is_probiotic') as is_probiotic,
                json_extract(blob, '$.probiotic_detail.has_cfu') as has_cfu,
                json_extract(blob, '$.probiotic_detail.total_cfu') as total_cfu,
                json_extract(blob, '$.probiotic_detail.total_billion_count') as billion_count,
                json_extract(blob, '$.probiotic_detail.total_strain_count') as strain_count,
                json_extract(score_basis, '$.A.total') as section_a_score,
                json_extract(blob, '$.activeIngredients') as active_ings
            FROM products
            WHERE json_extract(blob, '$.probiotic_detail.is_probiotic') = 1
            ORDER BY json_extract(score_basis, '$.A.total') ASC
            LIMIT 5000
        """)

        for row in cursor.fetchall():
            try:
                dsld_id, product_name, brand_name, is_probiotic, has_cfu, total_cfu, \
                    billion_count, strain_count, section_a, active_ings_json = row

                if not is_probiotic:
                    continue

                has_cfu_val = bool(has_cfu)
                cfu_count = float(total_cfu) if total_cfu else 0.0
                sect_a = float(section_a) if section_a else 0.0
                strain_cnt = int(strain_count) if strain_count else 0

                product_info = {
                    "dsld_id": dsld_id,
                    "product_name": product_name,
                    "brand_name": brand_name,
                    "has_cfu": has_cfu_val,
                    "cfu_count": cfu_count,
                    "billion_count": float(billion_count) if billion_count else 0.0,
                    "strain_count": strain_cnt,
                    "section_a_score": sect_a,
                }

                if not has_cfu_val and strain_cnt > 0:
                    # Has probiotic strains but CFU not detected
                    issues["missing_cfu"].append(product_info)
                elif cfu_count > 0 and cfu_count < 1e9:
                    # Very low CFU (< 1 billion)
                    issues["low_cfu"].append(product_info)

                if strain_cnt >= 2:
                    issues["multiple_strains"].append(product_info)

            except (TypeError, ValueError):
                continue

    except Exception as e:
        st.warning(f"Could not extract probiotic issues: {e}")

    return issues


def _render_section_a_summary(section_a_data: dict, probiotic_issues: dict):
    """Render top-level summary metrics."""
    st.write("### Section A Quality Summary")

    if not section_a_data["products"]:
        st.info("No scoring data available")
        return

    total_products = len(section_a_data["products"])
    avg_score = sum(section_a_data["scores"]) / len(section_a_data["scores"]) if section_a_data["scores"] else 0
    probiotic_products = sum(1 for p in section_a_data["products"] if p["is_probiotic"])
    probiotic_with_cfu = sum(1 for p in section_a_data["products"] if p["is_probiotic"] and p["has_cfu"])

    metrics = [
        ("Total Products", total_products),
        ("Avg Section A", f"{avg_score:.1f}/25"),
        ("Probiotic Products", probiotic_products),
        ("With CFU Detected", probiotic_with_cfu),
        ("CFU Detection Rate", f"{(probiotic_with_cfu/probiotic_products*100):.0f}%" if probiotic_products > 0 else "N/A"),
        ("Missing CFU", len(probiotic_issues["missing_cfu"])),
    ]

    metric_row(metrics)


def _render_score_distribution(section_a_data: dict):
    """Render Section A score distribution histogram with threshold slider."""
    st.write("### Section A Score Distribution")

    if not section_a_data["scores"]:
        st.info("No scoring data available")
        return

    # Threshold slider
    col1, col2 = st.columns([3, 1])
    with col2:
        threshold = st.slider(
            "Alert Threshold",
            min_value=0.0,
            max_value=25.0,
            value=10.0,
            step=0.5,
            help="Products below this threshold will be highlighted",
        )

    with col1:
        # Create histogram
        df = pd.DataFrame({"score": section_a_data["scores"]})
        fig = px.histogram(
            df,
            x="score",
            nbins=25,
            title="Score Distribution",
            labels={"score": "Section A Score (out of 25)"},
        )

        # Add threshold line
        fig.add_vline(
            x=threshold,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Alert: {threshold}",
            annotation_position="top right",
        )

        fig.update_xaxes(range=[0, 25])
        st.plotly_chart(fig, use_container_width=True)

    # Show counts
    below_threshold = sum(1 for s in section_a_data["scores"] if s < threshold)
    st.caption(f"**{below_threshold}** products below threshold of {threshold}")


def _render_below_threshold(section_a_data: dict):
    """Render products below threshold with filters."""
    st.write("### Products Below Threshold")

    if not section_a_data["products"]:
        st.info("No data available")
        return

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        threshold = st.number_input("Score Threshold", value=10.0, min_value=0.0, max_value=25.0)
    with col2:
        show_probiotics_only = st.checkbox("Probiotics Only", value=False)
    with col3:
        show_verdicts = st.multiselect(
            "Verdicts",
            ["SAFE", "CAUTION", "POOR", "UNSAFE", "BLOCKED", "NOT_SCORED"],
            default=["SAFE", "CAUTION", "POOR"],
        )

    # Filter products
    filtered_products = [
        p for p in section_a_data["products"]
        if (p["section_a_score"] < threshold
            and (not show_probiotics_only or p["is_probiotic"])
            and p["verdict"] in show_verdicts)
    ]

    st.metric(f"Matching Products", len(filtered_products))

    if filtered_products:
        # Create DataFrame for display
        df = pd.DataFrame([
            {
                "DSLD ID": p["dsld_id"],
                "Product": f"{p['brand_name']} - {p['product_name'][:40]}",
                "Type": p["supplement_type"],
                "Section A": f"{p['section_a_score']:.1f}/25",
                "Score 100": f"{p['score_100']:.0f}",
                "Verdict": p["verdict"],
                "Is Probiotic": "✓" if p["is_probiotic"] else "",
                "Has CFU": "✓" if p["has_cfu"] else "✗" if p["is_probiotic"] else "",
            }
            for p in filtered_products
        ])

        st.dataframe(df, use_container_width=True, height=400)

        # Export option
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name="section_a_audit.csv",
            mime="text/csv",
        )


def _render_probiotic_issues(probiotic_issues: dict, section_a_data: dict):
    """Render probiotic-specific CFU detection issues."""
    st.write("### Probiotic CFU Detection Issues")

    # Tabs for different issue types
    tab_missing, tab_low, tab_multi = st.tabs(
        ["Missing CFU", "Low CFU Count", "Multi-Strain"]
    )

    with tab_missing:
        st.write(f"#### Probiotics Without CFU Detection ({len(probiotic_issues['missing_cfu'])})")
        st.caption(
            "These products have probiotic strains but CFU (Colony Forming Units) "
            "was not detected. This impacts Section A scoring and probiotic bonus eligibility."
        )
        _render_probiotic_table(probiotic_issues["missing_cfu"])

    with tab_low:
        st.write(f"#### Low CFU Count ({len(probiotic_issues['low_cfu'])})")
        st.caption("Probiotic products with CFU < 1 billion (low dosage)")
        _render_probiotic_table(probiotic_issues["low_cfu"])

    with tab_multi:
        st.write(f"#### Multi-Strain Probiotics ({len(probiotic_issues['multiple_strains'])})")
        st.caption("Products with 2+ probiotic strains (often more complex dosing)")
        _render_probiotic_table(probiotic_issues["multiple_strains"])


def _render_probiotic_table(products: list):
    """Render a table of probiotic products."""
    if not products:
        st.info("No products to display")
        return

    df = pd.DataFrame([
        {
            "DSLD ID": p["dsld_id"],
            "Product": f"{p['brand_name']} - {p['product_name'][:35]}",
            "Section A": f"{p['section_a_score']:.1f}/25",
            "Strains": p["strain_count"],
            "CFU": f"{p['billion_count']:.2f}B" if p.get("billion_count") else "Not detected",
            "Has CFU": "✓" if p.get("has_cfu") else "✗",
        }
        for p in products[:500]  # Limit to 500 for performance
    ])

    st.dataframe(df, use_container_width=True, height=300)

    if len(products) > 500:
        st.caption(f"Showing 500 of {len(products)} products")


def _render_detailed_analysis(section_a_data: dict, probiotic_issues: dict):
    """Render detailed analysis and statistics."""
    st.write("### Detailed Analysis")

    col1, col2 = st.columns(2)

    with col1:
        st.write("#### Verdict Distribution")
        verdicts = defaultdict(int)
        for p in section_a_data["products"]:
            verdicts[p["verdict"]] += 1

        if verdicts:
            verdict_df = pd.DataFrame.from_dict(verdicts, orient="index", columns=["count"])
            fig = px.bar(
                verdict_df,
                title="Products by Verdict",
                labels={"index": "Verdict", "count": "Count"},
            )
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.write("#### Supplement Type Distribution")
        types = defaultdict(int)
        for p in section_a_data["products"]:
            types[p["supplement_type"]] += 1

        if types:
            type_df = pd.DataFrame.from_dict(types, orient="index", columns=["count"])
            fig = px.bar(
                type_df,
                title="Products by Type",
                labels={"index": "Type", "count": "Count"},
            )
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Score statistics
    st.write("#### Score Statistics")
    score_stats = {
        "Mean": f"{sum(section_a_data['scores'])/len(section_a_data['scores']):.2f}" if section_a_data["scores"] else 0,
        "Median": f"{sorted(section_a_data['scores'])[len(section_a_data['scores'])//2]:.2f}" if section_a_data["scores"] else 0,
        "Min": f"{min(section_a_data['scores']):.2f}" if section_a_data["scores"] else 0,
        "Max": f"{max(section_a_data['scores']):.2f}" if section_a_data["scores"] else 0,
        "Below 5": sum(1 for s in section_a_data["scores"] if s < 5),
        "5-10": sum(1 for s in section_a_data["scores"] if 5 <= s < 10),
        "10-15": sum(1 for s in section_a_data["scores"] if 10 <= s < 15),
        "15-20": sum(1 for s in section_a_data["scores"] if 15 <= s < 20),
        "20+": sum(1 for s in section_a_data["scores"] if s >= 20),
    }

    cols = st.columns(5)
    for i, (label, value) in enumerate(list(score_stats.items())[:5]):
        with cols[i]:
            st.metric(label, value)
