from __future__ import annotations

import json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from scripts.dashboard.components.data_dictionary import field_help
from scripts.dashboard.components.data_table import data_table
from scripts.dashboard.components.metric_cards import metric_row


def render_quality(data):
    dataset_scope = st.session_state.get("dataset_filter", "All Datasets")
    st.caption(f"Dataset scope: {dataset_scope}")

    _render_safety_summary(data)
    st.divider()
    _render_distribution_row(data)
    st.divider()
    _render_coverage_gate(data, dataset_scope)
    st.divider()

    tab_not_scored, tab_unmapped, tab_fallbacks, tab_config = st.tabs(
        ["Not-Scored Queue", "Unmapped Hotspots", "Fallback & Review Queues", "Config Snapshot"]
    )
    with tab_not_scored:
        _render_not_scored_queue(data, dataset_scope)
    with tab_unmapped:
        _render_unmapped_hotspots(data, dataset_scope)
    with tab_fallbacks:
        _render_fallback_tables(data, dataset_scope)
    with tab_config:
        _render_config_snapshot(data)


def _render_safety_summary(data):
    st.write("### Safety Summary")
    safety = data.shared_metrics.get("safety_counts", {})
    metrics = [
        ("Banned", safety.get("has_banned_substance", 0)),
        ("Recalled", safety.get("has_recalled_ingredient", 0)),
        ("Harmful Additives", safety.get("has_harmful_additives", 0)),
        ("Allergen Risks", safety.get("has_allergen_risks", 0)),
        ("Watchlist", safety.get("has_watchlist_hit", 0)),
        ("High Risk", safety.get("has_high_risk_hit", 0)),
    ]
    metric_row(metrics)
    st.caption(field_help("has_harmful_additives"))

    st.write("#### Inspect Safety Findings")
    category_map = {
        "Banned": "has_banned_substance",
        "Recalled": "has_recalled_ingredient",
        "Harmful Additives": "has_harmful_additives",
        "Allergen Risks": "has_allergen_risks",
        "Watchlist": "has_watchlist_hit",
        "High Risk": "has_high_risk_hit",
    }
    selected_category = st.selectbox("Show products for", list(category_map.keys()))
    if selected_category not in category_map:
        selected_category = next(iter(category_map))
    selected_flag = category_map[selected_category]

    if data.db_conn is None:
        st.info("No release export database available for safety drill-down.")
        return

    rows = build_safety_finding_rows(data.db_conn, data.detail_blobs_dir, selected_flag)
    if not rows:
        st.info(f"No products currently flagged as {selected_category.lower()}.")
        return

    st.write(f"### {selected_category} products")
    data_table(pd.DataFrame(rows), max_rows=200, height=420)


def _render_distribution_row(data):
    st.write("### Distributions")
    col_verdict, col_score = st.columns(2)
    with col_verdict:
        _render_verdict_distribution(data)
    with col_score:
        _render_score_histogram(data)


def _render_verdict_distribution(data):
    verdict_counts = data.shared_metrics.get("verdict_counts", {})
    labels = [label for label, count in verdict_counts.items() if count or label in {"BLOCKED", "NOT_SCORED"}]
    colors = {
        "SAFE": "#22c55e",
        "CAUTION": "#eab308",
        "POOR": "#f97316",
        "UNSAFE": "#ef4444",
        "BLOCKED": "#991b1b",
        "NOT_SCORED": "#6b7280",
    }
    fig = go.Figure(
        go.Bar(
            x=labels,
            y=[verdict_counts.get(label, 0) for label in labels],
            marker_color=[colors.get(label, "#3b82f6") for label in labels],
        )
    )
    fig.update_layout(height=340, margin=dict(l=20, r=20, t=40, b=20), title="Verdict Distribution")
    st.plotly_chart(fig, use_container_width=True)


def _render_score_histogram(data):
    if data.db_conn is None:
        st.info("No database connection available.")
        return
    df = pd.read_sql_query(
        "SELECT score_100_equivalent AS score FROM products_core WHERE score_100_equivalent IS NOT NULL",
        data.db_conn,
    )
    fig = go.Figure(go.Histogram(x=df["score"], xbins=dict(start=0, end=100, size=10), marker_color="#0d9488"))
    for value, label in [(90, "A+"), (80, "A"), (70, "B"), (60, "C"), (50, "D"), (32, "F")]:
        fig.add_vline(x=value, line_dash="dash", line_color="gray", annotation_text=label)
    fig.add_annotation(x=95, y=0, text=f"Mean {df['score'].mean():.1f} | Median {df['score'].median():.1f}", showarrow=False)
    fig.update_layout(height=340, margin=dict(l=20, r=20, t=40, b=20), title="Score Distribution")
    st.plotly_chart(fig, use_container_width=True)


def _render_coverage_gate(data, dataset_scope):
    st.write("### Coverage Gate")
    st.caption("Live dataset coverage from current output_* directories and report timestamps.")
    rows = []
    reports = _scoped_dataset_reports(data, dataset_scope)
    for dataset, report in reports.items():
        rows.append(
            {
                "dataset": dataset,
                "cleaned_count": report.get("cleaned_count", 0),
                "error_count": report.get("error_count", 0),
                "unmapped_active": len(report.get("unmapped_active", [])),
                "needs_review_active": len(report.get("needs_review_active", [])),
                "last_updated": report.get("latest_activity_at"),
            }
        )
    if not rows:
        st.info("No dataset output directories are available for coverage diagnostics.")
        return
    df = pd.DataFrame(rows)
    if not df.empty and "last_updated" in df.columns and df["last_updated"].notna().any():
        df["last_updated"] = pd.to_datetime(df["last_updated"]).dt.tz_convert("UTC").dt.strftime("%Y-%m-%d %H:%M UTC")
    fig = go.Figure()
    for column in ["cleaned_count", "error_count", "unmapped_active", "needs_review_active"]:
        fig.add_trace(go.Bar(name=column.replace("_", " ").title(), x=df["dataset"], y=df[column]))
    fig.update_layout(barmode="group", height=320, margin=dict(l=20, r=20, t=30, b=20))
    st.plotly_chart(fig, use_container_width=True)
    st.write("#### Coverage details")
    st.dataframe(df, use_container_width=True, height=260, hide_index=True)


def _render_not_scored_queue(data, dataset_scope):
    st.write("### Not-Scored Queue")
    if data.db_conn is None:
        st.info("No database connection available.")
        return
    df = pd.read_sql_query(
        """
        SELECT dsld_id, product_name, brand_name, mapped_coverage, blocking_reason
        FROM products_core
        WHERE verdict = 'NOT_SCORED'
        """,
        data.db_conn,
    )
    if dataset_scope != "All Datasets" and not df.empty:
        df = df[df["brand_name"].str.contains(dataset_scope, case=False, na=False)]
    if df.empty:
        st.success("No NOT_SCORED products in the current export.")
        return
    df["not_scored_reason"] = df.apply(lambda row: _infer_not_scored_reason(row), axis=1)
    data_table(df[["dsld_id", "product_name", "brand_name", "mapped_coverage", "not_scored_reason"]], max_rows=100)


def _infer_not_scored_reason(row):
    if row.get("blocking_reason"):
        return row["blocking_reason"]
    if row.get("mapped_coverage") is not None and row["mapped_coverage"] < 0.95:
        return f"Coverage below threshold ({row['mapped_coverage'] * 100:.1f}% < 95%)"
    return "Reason unknown; inspect batch logs or source files."


def _render_unmapped_hotspots(data, dataset_scope):
    st.write("### Unmapped Hotspots")
    reports = _scoped_dataset_reports(data, dataset_scope)
    rows = []
    for dataset, report in reports.items():
        for row in report.get("unmapped_active", []):
            rows.append(
                {
                    "ingredient_name": row.get("ingredient_name") or row.get("name"),
                    "occurrences": row.get("occurrence_count") or row.get("count") or 1,
                    "dataset": dataset,
                }
            )
        for row in report.get("unmapped_inactive", []):
            rows.append(
                {
                    "ingredient_name": row.get("ingredient_name") or row.get("name"),
                    "occurrences": row.get("occurrence_count") or row.get("count") or 1,
                    "dataset": dataset,
                }
            )
    if not rows:
        st.info("No unmapped ingredient hotspots found in the discovered outputs.")
        return
    df = pd.DataFrame(rows).groupby("ingredient_name", as_index=False).agg(
        occurrences=("occurrences", "sum"),
        datasets=("dataset", lambda values: ", ".join(sorted(set(values)))),
    )
    df = df.sort_values(["occurrences", "ingredient_name"], ascending=[False, True])
    data_table(df, max_rows=50)


def _render_fallback_tables(data, dataset_scope):
    reports = _scoped_dataset_reports(data, dataset_scope)
    left, right = st.columns(2)
    with left:
        st.write("### Needs Review")
        rows = []
        for dataset, report in reports.items():
            for row in report.get("needs_review_active", []):
                rows.append(
                    {
                        "dataset": dataset,
                        "ingredient_name": row.get("ingredient_name") or row.get("name"),
                        "occurrences": row.get("occurrence_count") or row.get("count") or 1,
                        "type": "active",
                    }
                )
            for row in report.get("needs_review_inactive", []):
                rows.append(
                    {
                        "dataset": dataset,
                        "ingredient_name": row.get("ingredient_name") or row.get("name"),
                        "occurrences": row.get("occurrence_count") or row.get("count") or 1,
                        "type": "inactive",
                    }
                )
        if rows:
            data_table(pd.DataFrame(rows), max_rows=100)
        else:
            st.info("No needs-review ingredient queues found.")
    with right:
        st.write("### Dataset Fallback Signals")
        st.caption("Live fallback and unmapped queues from current dataset output reports.")
        rows = []
        for dataset, report in reports.items():
            rows.append(
                {
                    "dataset": dataset,
                    "cleaned_files": report.get("cleaned_count", 0),
                    "error_files": report.get("error_count", 0),
                    "unmapped_total": len(report.get("unmapped_active", [])) + len(report.get("unmapped_inactive", [])),
                    "last_updated": report.get("latest_activity_at"),
                }
            )
        fallback_df = pd.DataFrame(rows)
        if not fallback_df.empty and "last_updated" in fallback_df.columns and fallback_df["last_updated"].notna().any():
            fallback_df["last_updated"] = pd.to_datetime(fallback_df["last_updated"]).dt.tz_convert("UTC").dt.strftime("%Y-%m-%d %H:%M UTC")
        data_table(fallback_df, max_rows=50)


def _render_config_snapshot(data):
    st.write("### Config Snapshot")
    config = data.scoring_config
    if not config:
        st.info("No scoring config was loaded.")
        return
    section_maxima = (
        config.get("section_maxima")
        or config.get("score_maxima")
        or {"ingredient_quality": 25, "safety_purity": 30, "evidence_research": 20, "brand_trust": 5}
    )
    rows = [
        {"field": "Scoring version", "value": (data.export_manifest or {}).get("scoring_version", "N/A")},
        {"field": "Average coverage", "value": f"{data.shared_metrics.get('average_coverage_pct', 'N/A')}%"},
        {"field": "Ingredient Quality Max", "value": section_maxima.get("ingredient_quality", 25)},
        {"field": "Safety & Purity Max", "value": section_maxima.get("safety_purity", 30)},
        {"field": "Evidence & Research Max", "value": section_maxima.get("evidence_research", 20)},
        {"field": "Brand Trust Max", "value": section_maxima.get("brand_trust", 5)},
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _scoped_dataset_reports(data, dataset_scope):
    if dataset_scope == "All Datasets":
        return data.dataset_reports
    return {dataset_scope: data.dataset_reports.get(dataset_scope, {})} if dataset_scope in data.dataset_reports else {}


def _warning_matches_flag(warning: dict, selected_flag: str) -> bool:
    warning_type = str(warning.get("type", "")).lower()
    title = str(warning.get("title", "")).lower()
    category = str(warning.get("category", "")).lower()

    if selected_flag == "has_harmful_additives":
        return warning_type == "harmful_additive" or "harmful additive" in title or category in {"excipient", "filler"}
    if selected_flag == "has_banned_substance":
        return "banned" in warning_type or "banned" in title
    if selected_flag == "has_recalled_ingredient":
        return "recall" in warning_type or "recall" in title
    if selected_flag == "has_allergen_risks":
        return "allergen" in warning_type or "allergen" in title
    if selected_flag == "has_watchlist_hit":
        return "watchlist" in warning_type or "watchlist" in title
    if selected_flag == "has_high_risk_hit":
        return "high_risk" in warning_type or "high risk" in title
    return False


def build_safety_finding_rows(db_conn, detail_blobs_dir, selected_flag: str) -> list[dict]:
    try:
        columns = {
            row["name"] if isinstance(row, dict) or hasattr(row, "keys") else row[1]
            for row in db_conn.execute("PRAGMA table_info(products_core)").fetchall()
        }
    except Exception:
        return []

    required_columns = {
        "dsld_id",
        "product_name",
        "brand_name",
        "verdict",
        "score_100_equivalent",
    }
    if selected_flag not in columns or not required_columns.issubset(columns):
        return []

    base_df = pd.read_sql_query(
        f"SELECT dsld_id, product_name, brand_name, verdict, score_100_equivalent AS score, mapped_coverage "
        f"FROM products_core WHERE {selected_flag} = 1 ORDER BY score_100_equivalent DESC",
        db_conn,
    )
    if base_df.empty:
        return []

    rows: list[dict] = []
    for _, record in base_df.iterrows():
        dsld_id = str(record["dsld_id"])
        matched_warning = False
        blob_path = detail_blobs_dir / f"{dsld_id}.json" if detail_blobs_dir else None
        if blob_path and blob_path.exists():
            try:
                blob = json.loads(blob_path.read_text())
            except Exception:
                blob = {}
            for warning in blob.get("warnings", []):
                if not _warning_matches_flag(warning, selected_flag):
                    continue
                matched_warning = True
                rows.append(
                    {
                        "dsld_id": dsld_id,
                        "product_name": record["product_name"],
                        "brand_name": record["brand_name"],
                        "verdict": record["verdict"],
                        "score": record["score"],
                        "warning_title": warning.get("title") or warning.get("type") or "Warning",
                        "severity": warning.get("severity", "info"),
                        "warning_detail": warning.get("detail", ""),
                    }
                )
        if not matched_warning:
            rows.append(
                {
                    "dsld_id": dsld_id,
                    "product_name": record["product_name"],
                    "brand_name": record["brand_name"],
                    "verdict": record["verdict"],
                    "score": record["score"],
                    "warning_title": "Flag present in release snapshot",
                    "severity": "unknown",
                    "warning_detail": "Release snapshot indicates this flag, but no matching blob-level warning was found.",
                }
            )
    return rows
