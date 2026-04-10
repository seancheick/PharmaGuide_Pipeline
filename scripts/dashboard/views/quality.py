from __future__ import annotations

import json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from scripts.dashboard.components.data_dictionary import field_help
from scripts.dashboard.components.data_table import data_table
from scripts.dashboard.components.metric_cards import metric_row
from scripts.dashboard.data_loader import filter_product_catalog


def render_quality(data):
    dataset_scope = st.session_state.get("dataset_filter", "All Datasets")
    filtered_products = filter_product_catalog(data)
    st.caption(f"Dataset scope: {dataset_scope} | Release rows in scope: {len(filtered_products)}")

    _render_safety_summary(data, filtered_products)
    st.divider()
    _render_harmful_ingredient_trends(data, filtered_products)
    st.divider()
    _render_distribution_row(data, filtered_products)
    st.divider()
    _render_coverage_gate(data, dataset_scope)
    st.divider()

    try:
        tabs = st.tabs(["Not-Scored Queue", "Unmapped Hotspots", "Fallback & Review Queues", "Config Snapshot"])
        if not isinstance(tabs, (list, tuple)) or len(tabs) < 4:
            raise ValueError("tabs unavailable")
        tab_not_scored, tab_unmapped, tab_fallbacks, tab_config = tabs[:4]
    except Exception:
        tab_not_scored = tab_unmapped = tab_fallbacks = tab_config = st
    with tab_not_scored:
        _render_not_scored_queue(data, filtered_products)
    with tab_unmapped:
        _render_unmapped_hotspots(data, dataset_scope)
    with tab_fallbacks:
        _render_fallback_tables(data, dataset_scope)
    with tab_config:
        _render_config_snapshot(data)


def _render_safety_summary(data, filtered_products):
    st.write("### Safety Summary")
    if filtered_products.empty:
        st.info("No release products match the active filters.")
        return
    safety = {
        "has_banned_substance": int(filtered_products["has_banned_substance"].fillna(0).sum()),
        "has_recalled_ingredient": int(filtered_products["has_recalled_ingredient"].fillna(0).sum()),
        "has_harmful_additives": int(filtered_products["has_harmful_additives"].fillna(0).sum()),
        "has_allergen_risks": int(filtered_products["has_allergen_risks"].fillna(0).sum()),
        "has_watchlist_hit": 0,
        "has_high_risk_hit": 0,
    }
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

    rows = build_safety_finding_rows(
        data.db_conn,
        data.detail_blobs_dir,
        selected_flag,
        allowed_ids=set(filtered_products["dsld_id"].astype(str)),
    )
    if not rows:
        st.info(f"No products currently flagged as {selected_category.lower()}.")
        return

    st.write(f"### {selected_category} products")
    data_table(pd.DataFrame(rows), max_rows=200, height=420)


def _render_distribution_row(data, filtered_products):
    st.write("### Distributions")
    try:
        columns = st.columns(2)
        if not isinstance(columns, (list, tuple)) or len(columns) < 2:
            raise ValueError("columns unavailable")
        col_verdict, col_score = columns[0], columns[1]
    except Exception:
        col_verdict, col_score = st, st
    with col_verdict:
        _render_verdict_distribution(filtered_products)
    with col_score:
        _render_score_histogram(filtered_products)


def _render_verdict_distribution(filtered_products):
    verdict_counts = filtered_products["verdict"].fillna("UNKNOWN").value_counts().to_dict()
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


def _render_score_histogram(filtered_products):
    if filtered_products.empty:
        st.info("No database connection available.")
        return
    df = filtered_products[["score"]].dropna().rename(columns={"score": "score"})
    if df.empty:
        st.info("No scored products match the active filters.")
        return
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


def _render_not_scored_queue(data, filtered_products):
    st.write("### Not-Scored Queue")
    df = filtered_products[filtered_products["verdict"] == "NOT_SCORED"].copy()
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
    try:
        columns = st.columns(2)
        if not isinstance(columns, (list, tuple)) or len(columns) < 2:
            raise ValueError("columns unavailable")
        left, right = columns[0], columns[1]
    except Exception:
        left, right = st, st
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
    section_maxima = config.get("section_maximums") or {}
    feature_gates = config.get("feature_gates") or {}
    rows = [
        {"field": "Scoring version", "value": (data.export_manifest or {}).get("scoring_version", "N/A")},
        {"field": "Average coverage", "value": f"{data.shared_metrics.get('average_coverage_pct', 'N/A')}%"},
        {"field": "Ingredient Quality Max", "value": section_maxima.get("A_ingredient_quality", 25)},
        {"field": "Safety & Purity Max", "value": section_maxima.get("B_safety_purity", 30)},
        {"field": "Evidence & Research Max", "value": section_maxima.get("C_evidence_research", 20)},
        {"field": "Brand Trust Max", "value": section_maxima.get("D_brand_trust", 5)},
        {"field": "Non-GMO bonus enabled", "value": bool(feature_gates.get("enable_non_gmo_bonus"))},
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


def build_safety_finding_rows(db_conn, detail_blobs_dir, selected_flag: str, allowed_ids: set[str] | None = None) -> list[dict]:
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
        if allowed_ids is not None and dsld_id not in allowed_ids:
            continue
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
                        "product_b1_penalty": _warning_penalty_score(blob, warning),
                        "warning_title": warning.get("title") or warning.get("type") or "Warning",
                        "severity": warning.get("severity", "info"),
                        "warning_detail": warning.get("detail", ""),
                        "ingredient_name": warning.get("ingredient_name") or _warning_ingredient_name(warning),
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
                    "product_b1_penalty": None,
                    "warning_title": "Flag present in release snapshot",
                    "severity": "unknown",
                    "warning_detail": "Release snapshot indicates this flag, but no matching blob-level warning was found.",
                    "ingredient_name": "",
                }
            )
    return rows


def _warning_ingredient_name(warning: dict) -> str:
    title = str(warning.get("title") or "")
    if ":" in title:
        return title.split(":", 1)[1].strip()
    if title.lower().startswith("contains "):
        return title[9:].strip()
    return str(warning.get("ingredient_name") or "")


def _warning_penalty_score(blob: dict, warning: dict) -> float | None:
    warning_type = str(warning.get("type", "")).lower()
    if warning_type != "harmful_additive":
        return None
    for penalty in blob.get("score_penalties", []):
        if penalty.get("id") == "B1" and penalty.get("score") is not None:
            try:
                return float(penalty["score"])
            except (TypeError, ValueError):
                return None
    return None


def _render_harmful_ingredient_trends(data, filtered_products):
    st.write("### Harmful Ingredient Trends")
    st.caption("Release snapshot detail blobs grouped by flagged ingredient. Points shown are product-level B1 penalty totals, not per-ingredient allocations.")
    rows = build_harmful_ingredient_trend_rows(
        data.detail_blobs_dir,
        allowed_ids=set(filtered_products["dsld_id"].astype(str)),
    )
    if not rows:
        st.info("No harmful additive findings match the active filters.")
        return
    data_table(pd.DataFrame(rows), max_rows=100, height=360)


def build_harmful_ingredient_trend_rows(detail_blobs_dir, allowed_ids: set[str] | None = None) -> list[dict]:
    if detail_blobs_dir is None:
        return []

    grouped: dict[str, dict[str, object]] = {}
    for blob_path in sorted(detail_blobs_dir.glob("*.json")):
        dsld_id = blob_path.stem
        if allowed_ids is not None and dsld_id not in allowed_ids:
            continue
        try:
            blob = json.loads(blob_path.read_text())
        except Exception:
            continue
        product_penalty = None
        for penalty in blob.get("score_penalties", []):
            if penalty.get("id") == "B1" and penalty.get("score") is not None:
                try:
                    product_penalty = float(penalty["score"])
                except (TypeError, ValueError):
                    product_penalty = None
                break
        for warning in blob.get("warnings", []):
            if str(warning.get("type", "")).lower() != "harmful_additive":
                continue
            ingredient_name = _warning_ingredient_name(warning) or "Unknown additive"
            stat = grouped.setdefault(
                ingredient_name,
                {
                    "ingredient_name": ingredient_name,
                    "occurrences": 0,
                    "affected_products": set(),
                    "severity_levels": set(),
                    "penalties": [],
                    "sample_products": [],
                },
            )
            stat["occurrences"] += 1
            stat["affected_products"].add(dsld_id)
            severity = str(warning.get("severity") or "")
            if severity:
                stat["severity_levels"].add(severity)
            if product_penalty is not None:
                stat["penalties"].append(product_penalty)
            sample = f"{blob.get('brand_name', '')} {blob.get('product_name', '')}".strip()
            if sample and sample not in stat["sample_products"] and len(stat["sample_products"]) < 3:
                stat["sample_products"].append(sample)

    rows = []
    for stat in grouped.values():
        penalties = stat["penalties"]
        rows.append(
            {
                "ingredient_name": stat["ingredient_name"],
                "occurrences": stat["occurrences"],
                "affected_products": len(stat["affected_products"]),
                "severity_levels": ", ".join(sorted(stat["severity_levels"])),
                "avg_product_b1_penalty": round(sum(penalties) / len(penalties), 2) if penalties else None,
                "max_product_b1_penalty": round(max(penalties), 2) if penalties else None,
                "sample_products": ", ".join(stat["sample_products"]),
            }
        )
    rows.sort(key=lambda row: (row["affected_products"], row["occurrences"]), reverse=True)
    return rows
