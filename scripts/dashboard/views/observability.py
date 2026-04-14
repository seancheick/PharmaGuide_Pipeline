from __future__ import annotations

import re
from datetime import datetime, timezone

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from scripts.dashboard.components import _safe_columns, _safe_tabs
from scripts.dashboard.components.metric_cards import metric_card, metric_row
from scripts.dashboard.time_format import format_dashboard_datetime


def render_observability(data):
    _render_alerts(data)
    st.divider()

    tab_integrity, tab_safety, tab_analytics, tab_monitoring, tab_ops = _safe_tabs(
        ["Integrity", "Safety", "Analytics", "Monitoring", "Operations"]
    )
    with tab_integrity:
        _render_integrity(data)
    with tab_safety:
        _render_safety_dashboard(data)
    with tab_analytics:
        _render_analytics(data)
    with tab_monitoring:
        _render_monitoring(data)
    with tab_ops:
        _render_operations(data)


def _render_alerts(data):
    thresholds = data.alert_thresholds
    metrics = data.shared_metrics
    alerts = []
    if metrics.get("pipeline_yield_pct") is not None and metrics["pipeline_yield_pct"] < thresholds["coverage_min_pct"]:
        alerts.append(("error", f"Pipeline yield dropped to {metrics['pipeline_yield_pct']}%"))
    if metrics.get("error_count", 0) > thresholds["max_errors"]:
        alerts.append(("error", f"{metrics['error_count']} export or pipeline errors detected"))
    banned_count = metrics["safety_counts"].get("has_banned_substance", 0)
    if banned_count:
        alerts.append(("warning", f"{banned_count} products contain banned substances"))
    if data.latest_export_at:
        build_age_days = (datetime.now(timezone.utc) - data.latest_export_at).days
        if build_age_days > thresholds["max_build_age_days"]:
            alerts.append(("warning", f"Current build is {build_age_days} days old"))
    if not alerts:
        st.success("No active alerts under the configured thresholds.")
        return
    for level, message in alerts:
        if level == "error":
            st.error(message)
        else:
            st.warning(message)


def _render_integrity(data):
    metrics = data.shared_metrics
    metric_row(
        [
            ("Enriched Inputs", metrics.get("enriched_input_count", 0)),
            ("Scored Inputs", metrics.get("scored_input_count", 0)),
            ("Exported", metrics.get("exported_count", 0)),
            ("Errors", metrics.get("error_count", 0)),
        ]
    )
    metric_row(
        [
            ("Enriched-only", metrics.get("enriched_only_count", 0)),
            ("Scored-only", metrics.get("scored_only_count", 0)),
            ("Yield %", f"{metrics.get('pipeline_yield_pct', 0)}%"),
            ("Strict Mode", "ON" if metrics.get("strict_mode") else "OFF"),
        ]
    )

    st.write("### Product Flow")
    _render_product_flow(data)
    st.write("### Mismatch Tracker")
    _render_mismatch_tracker(data)
    st.write("### Export Errors")
    _render_export_errors(data)


def _render_product_flow(data):
    metrics = data.shared_metrics
    edges = [
        ("Enriched", "Scored", max(metrics.get("scored_input_count", 0) - metrics.get("scored_only_count", 0), 0), metrics.get("enriched_input_count", 0)),
        ("Scored", "Exported", metrics.get("exported_count", 0), metrics.get("scored_input_count", 0)),
        ("Enriched", "Enriched-only", metrics.get("enriched_only_count", 0), metrics.get("enriched_input_count", 0)),
        ("Scored", "Scored-only", metrics.get("scored_only_count", 0), metrics.get("scored_input_count", 0)),
        ("Scored", "Errors", metrics.get("error_count", 0), metrics.get("scored_input_count", 0)),
    ]
    node_order = ["Enriched", "Scored", "Exported", "Enriched-only", "Scored-only", "Errors"]
    node_index = {label: idx for idx, label in enumerate(node_order)}
    summary_rows = []
    for source, target, value, total in edges:
        pct = round((value / total) * 100, 1) if total else 0.0
        summary_rows.append(
            {
                "edge": f"{source} -> {target}",
                "value": value,
                "pct_of_source": pct,
                "source_total": total,
            }
        )

    fig = go.Figure(
        go.Sankey(
            node=dict(label=node_order, pad=18, thickness=18),
            link=dict(
                source=[node_index[source] for source, _, _, _ in edges],
                target=[node_index[target] for _, target, _, _ in edges],
                value=[value for _, _, value, _ in edges],
                label=[
                    f"{row['edge']}: {row['value']} ({row['pct_of_source']}%)"
                    for row in summary_rows
                ],
                hovertemplate="%{label}<extra></extra>",
            ),
        )
    )
    fig.update_layout(height=380, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, width="stretch")

    st.dataframe(pd.DataFrame(summary_rows), width="stretch", hide_index=True)


def _render_mismatch_tracker(data):
    current_rows = [
        {
            "type": "Enriched-only",
            "count": data.shared_metrics.get("enriched_only_count", 0),
            "note": "Products enriched but not exported",
        },
        {
            "type": "Scored-only",
            "count": data.shared_metrics.get("scored_only_count", 0),
            "note": "Products scored without matching enriched record",
        },
    ]
    st.dataframe(pd.DataFrame(current_rows), width="stretch", hide_index=True)

    history_rows = []
    for entry in data.build_history:
        history_rows.append(
            {
                "build": entry["label"],
                "generated_at": entry.get("generated_at"),
                "enriched_only_count": entry.get("enriched_only_count", 0),
                "scored_only_count": entry.get("scored_only_count", 0),
                "error_count": entry.get("error_count", 0),
            }
        )
    if history_rows:
        history_df = pd.DataFrame(history_rows)
        melted = history_df.melt(
            id_vars=["build", "generated_at"],
            value_vars=["enriched_only_count", "scored_only_count", "error_count"],
            var_name="metric",
            value_name="count",
        )
        fig = px.line(
            melted,
            x="generated_at",
            y="count",
            color="metric",
            markers=True,
            title="Mismatch and error trend by build",
        )
        fig.update_layout(height=320)
        st.plotly_chart(fig, width="stretch")

    dataset_rows = []
    if data.batch_history:
        latest = data.batch_history[0]
        for dataset, dataset_state in latest.get("datasets", {}).items():
            dataset_rows.append(
                {
                    "dataset": dataset,
                    "status": dataset_state.get("status"),
                    "last_stage": dataset_state.get("last_stage"),
                    "error_count": len(dataset_state.get("errors", [])),
                }
            )
    if dataset_rows:
        st.write("### Latest Batch Impact")
        st.dataframe(pd.DataFrame(dataset_rows), width="stretch", hide_index=True)


def _render_export_errors(data):
    error_df = pd.DataFrame(_extract_error_records(data))
    if error_df.empty:
        st.success("No export or batch errors recorded in discovered artifacts.")
        return

    top_reasons = (
        error_df.groupby(["classification", "dataset"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
        .head(12)
    )
    col1, col2 = _safe_columns([1.1, 1])
    with col1:
        fig = px.bar(top_reasons, x="count", y="classification", color="dataset", orientation="h", title="Top failure reasons")
        fig.update_layout(height=360, yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, width="stretch")
    with col2:
        st.dataframe(top_reasons, width="stretch", hide_index=True)

    st.write("### Error Drill-Down")
    st.dataframe(
        error_df.sort_values(["batch", "dataset", "classification", "dsld_id"], ascending=[False, True, True, True]),
        width="stretch",
        hide_index=True,
    )


def _render_safety_dashboard(data):
    safety = data.shared_metrics.get("safety_counts", {})
    cols = _safe_columns(6)
    labels = [
        ("Banned", "has_banned_substance"),
        ("Recalled", "has_recalled_ingredient"),
        ("Harmful", "has_harmful_additives"),
        ("Allergens", "has_allergen_risks"),
        ("Watchlist", "has_watchlist_hit"),
        ("High Risk", "has_high_risk_hit"),
    ]
    for col, (label, key) in zip(cols, labels):
        with col:
            metric_card(label, safety.get(key, 0))
    sample = (data.export_audit or {}).get("products_with_warnings_sample", [])
    if sample:
        st.dataframe(pd.DataFrame(sample), width="stretch", hide_index=True)


def _render_analytics(data):
    if data.db_conn is None:
        st.info("Analytics require the current SQLite export.")
        return
    df = pd.read_sql_query(
        """
        SELECT brand_name, supplement_type, verdict, score_100_equivalent AS score, mapped_coverage
        FROM products_core
        WHERE score_100_equivalent IS NOT NULL
        """,
        data.db_conn,
    )
    col1, col2 = _safe_columns(2)
    with col1:
        top_brands = df["brand_name"].value_counts().nlargest(10).index
        fig = px.box(df[df["brand_name"].isin(top_brands)], x="brand_name", y="score", color="brand_name")
        fig.update_layout(showlegend=False, height=360)
        st.plotly_chart(fig, width="stretch")
    with col2:
        fig = px.scatter(df, x="mapped_coverage", y="score", color="verdict", opacity=0.6)
        fig.update_layout(height=360)
        st.plotly_chart(fig, width="stretch")

    st.write("### Ingredient Coverage Health")
    coverage_rows = []
    for dataset, report in data.dataset_reports.items():
        coverage_rows.append(
            {
                "dataset": dataset,
                "cleaned_files": report.get("cleaned_count", 0),
                "error_files": report.get("error_count", 0),
                "unmapped_total": len(report.get("unmapped_active", [])) + len(report.get("unmapped_inactive", [])),
            }
        )
    if coverage_rows:
        coverage_df = pd.DataFrame(coverage_rows)
        left, right = _safe_columns(2)
        with left:
            fig = px.pie(
                coverage_df,
                names="dataset",
                values="unmapped_total",
                title="Unmapped ingredient concentration by dataset",
            )
            fig.update_layout(height=340)
            st.plotly_chart(fig, width="stretch")
        with right:
            st.dataframe(coverage_df.sort_values("unmapped_total", ascending=False), width="stretch", hide_index=True)


def _render_monitoring(data):
    st.write("### Build History")
    history = data.build_history
    if history:
        history_rows = [
            {
                "label": entry["label"],
                "generated_at": entry.get("generated_at"),
                "product_count": entry.get("product_count"),
                "scoring_version": entry.get("scoring_version"),
            }
            for entry in history
        ]
        history_df = pd.DataFrame(history_rows)
        history_df["generated_at"] = history_df["generated_at"].map(
            lambda value: format_dashboard_datetime(value, style="compact", include_timezone=True)
        )
        st.dataframe(history_df, width="stretch", hide_index=True)
        fig = px.scatter(
            history_df,
            x="generated_at",
            y="product_count",
            color="scoring_version",
            size="product_count",
            hover_name="label",
            title="Build timeline",
        )
        fig.update_layout(height=320)
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No build history entries discovered.")

    st.write("### Drift Detection")
    if len(history) < 2:
        st.info("Drift detection requires at least two builds.")
    else:
        current = history[0]
        prior = history[1]
        drift_rows = [
            {
                "metric": "product_count",
                "current": current.get("product_count", 0),
                "prior": prior.get("product_count", 0),
            },
            {
                "metric": "detail_blob_count",
                "current": current.get("detail_blob_count", 0),
                "prior": prior.get("detail_blob_count", 0),
            },
            {
                "metric": "error_count",
                "current": current.get("error_count", 0),
                "prior": prior.get("error_count", 0),
            },
            {
                "metric": "enriched_only_count",
                "current": current.get("enriched_only_count", 0),
                "prior": prior.get("enriched_only_count", 0),
            },
            {
                "metric": "scored_only_count",
                "current": current.get("scored_only_count", 0),
                "prior": prior.get("scored_only_count", 0),
            },
        ]
        drift_df = pd.DataFrame(drift_rows)
        drift_df["delta"] = drift_df["current"].fillna(0) - drift_df["prior"].fillna(0)
        st.dataframe(drift_df, width="stretch", hide_index=True)
        for row in drift_df.to_dict("records"):
            if row["metric"] in {"error_count", "enriched_only_count", "scored_only_count"} and row["delta"] > 0:
                st.warning(f"Drift alert: {row['metric']} increased by {row['delta']} vs prior build.")

    st.write("### Bottleneck Analyzer")
    if not data.batch_history:
        st.info("No batch logs available for bottleneck analysis.")
    else:
        df = pd.DataFrame(
            [
                {"batch": entry["name"], "processing_time": entry.get("summary", {}).get("processing_time", 0.0)}
                for entry in data.batch_history
            ]
        )
        fig = px.bar(df, x="batch", y="processing_time")
        fig.update_layout(height=320)
        st.plotly_chart(fig, width="stretch")

    st.write("### Trend Over Time")
    if len(history) < 2:
        st.info("Trend charts improve when multiple builds are available.")
    else:
        trend_df = pd.DataFrame(
            [
                {
                    "generated_at": entry.get("generated_at"),
                    "product_count": entry.get("product_count", 0),
                    "detail_blob_count": entry.get("detail_blob_count", 0),
                    "error_count": entry.get("error_count", 0),
                }
                for entry in history
            ]
        )
        melted = trend_df.melt(id_vars=["generated_at"], var_name="metric", value_name="value")
        fig = px.line(melted, x="generated_at", y="value", color="metric", markers=True)
        fig.update_layout(height=320)
        st.plotly_chart(fig, width="stretch")

    st.write("### Data Completeness")
    completeness = data.blob_analytics.get("completeness_records", [])
    if completeness:
        df = pd.DataFrame(completeness[:100])
        st.dataframe(df[["dsld_id", "product_name", "brand_name", "completeness_pct", "missing_fields"]], width="stretch", hide_index=True)

    st.write("### Outlier Detector")
    _render_outliers(data)


def _render_outliers(data):
    if data.db_conn is None:
        st.info("No database connection available.")
        return
    columns = {
        row["name"]
        for row in data.db_conn.execute("PRAGMA table_info(products_core)").fetchall()
    }
    queries = [
        (
            "High score, low coverage",
            """
            SELECT dsld_id, product_name, brand_name, score_100_equivalent, mapped_coverage
            FROM products_core
            WHERE score_100_equivalent >= 75 AND mapped_coverage < 0.5
            """,
        ),
        (
            "Unsafe with high score",
            """
            SELECT dsld_id, product_name, brand_name, score_100_equivalent, verdict
            FROM products_core
            WHERE verdict = 'UNSAFE' AND score_100_equivalent >= 60
            """,
        ),
    ]
    if {"has_banned_substance", "has_recalled_ingredient"}.issubset(columns):
        queries.append(
            (
                "Low score with no obvious penalties",
                """
                SELECT dsld_id, product_name, brand_name, score_100_equivalent, verdict
                FROM products_core
                WHERE score_100_equivalent <= 35
                  AND COALESCE(has_banned_substance, 0) = 0
                  AND COALESCE(has_recalled_ingredient, 0) = 0
                """,
            )
        )
    rows = []
    for label, query in queries:
        df = pd.read_sql_query(query, data.db_conn)
        rows.append({"pattern": label, "count": len(df)})
        with st.expander(f"{label} ({len(df)})"):
            if df.empty:
                st.caption("No rows matched.")
            else:
                st.dataframe(df.head(100), width="stretch", hide_index=True)
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def _render_operations(data):
    st.write("### Sync Status")
    if data.remote_manifest:
        status_rows = [
            {
                "scope": "local",
                "db_version": (data.export_manifest or {}).get("db_version"),
                "generated_at": format_dashboard_datetime((data.export_manifest or {}).get("generated_at"), include_timezone=True),
            },
            {
                "scope": "remote",
                "db_version": data.remote_manifest.get("db_version"),
                "generated_at": format_dashboard_datetime(data.remote_manifest.get("generated_at"), include_timezone=True),
            },
        ]
        st.success("Remote manifest loaded.")
        st.dataframe(pd.DataFrame(status_rows), width="stretch", hide_index=True)
    else:
        status_rows = [
            {
                "scope": "local",
                "db_version": (data.export_manifest or {}).get("db_version"),
                "generated_at": format_dashboard_datetime((data.export_manifest or {}).get("generated_at"), include_timezone=True),
                "status": "available",
            },
            {"scope": "remote", "db_version": None, "generated_at": None, "status": "credentials not configured"},
        ]
        st.warning("Credentials not configured; showing local-only status.")
        st.dataframe(pd.DataFrame(status_rows), width="stretch", hide_index=True)

    st.write("### Storage Health")
    if data.build_root.exists():
        size_bytes = sum(path.stat().st_size for path in data.build_root.glob("**/*") if path.is_file())
        st.metric("Build Root Size", f"{size_bytes / (1024 * 1024):.1f} MB")
    if data.detail_index:
        referenced = len(data.detail_index)
        actual = len(list((data.detail_blobs_dir or data.build_root).glob("*.json"))) if data.detail_blobs_dir else 0
        st.write(f"Detail blobs referenced: {referenced} | on disk: {actual}")
        if actual > referenced:
            st.warning(f"{actual - referenced} potential orphaned blobs detected.")

    cleanup_candidates = []
    for entry in data.build_history[1:]:
        build_root = entry.get("build_root")
        if build_root:
            cleanup_candidates.append(
                {
                    "build": entry.get("label"),
                    "path": str(build_root),
                    "generated_at": format_dashboard_datetime(entry.get("generated_at"), style="compact", include_timezone=True),
                    "product_count": entry.get("product_count"),
                }
            )
    st.write("### Safe Cleanup Preview")
    if cleanup_candidates:
        if st.checkbox("Preview cleanup candidates", value=False):
            st.dataframe(pd.DataFrame(cleanup_candidates), width="stretch", hide_index=True)
            st.warning("Preview only. This dashboard does not delete files.")
    else:
        st.info("No older build directories available for cleanup preview.")


def _extract_error_records(data) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    if data.export_manifest:
        for error in data.export_manifest.get("errors", []):
            message = str(error)
            records.append(
                {
                    "batch": "current_release",
                    "dataset": _extract_dataset_name(message),
                    "dsld_id": _extract_dsld_id(message),
                    "classification": _classify_error(message),
                    "message": message,
                }
            )
    for entry in data.batch_history:
        for line in entry.get("error_lines", []):
            records.append(
                {
                    "batch": entry.get("name"),
                    "dataset": _extract_dataset_name(line),
                    "dsld_id": _extract_dsld_id(line),
                    "classification": _classify_error(line),
                    "message": line,
                }
            )
    return records


def _extract_dataset_name(message: str) -> str:
    match = re.search(r"/brands/([^/]+)/", message)
    if match:
        return match.group(1)
    return "Unknown"


def _extract_dsld_id(message: str) -> str | None:
    match = re.search(r"/(\d+)\.json", message)
    return match.group(1) if match else None


def _classify_error(message: str) -> str:
    lowered = message.lower()
    if "source_wrapper_names" in lowered:
        return "Missing wrapper constant"
    if "timeout" in lowered:
        return "Timeout"
    if "json" in lowered and "decode" in lowered:
        return "JSON decode error"
    if "not defined" in lowered or "nameerror" in lowered:
        return "Unhandled code exception"
    if "permission" in lowered:
        return "Permission error"
    return "Other pipeline error"
