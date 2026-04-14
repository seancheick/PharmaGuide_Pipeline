from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import re

import pandas as pd
import streamlit as st

from scripts.dashboard.components.metric_cards import metric_row
from scripts.dashboard.components.status_badge import status_badge
from scripts.dashboard.time_format import format_dashboard_datetime


def render_health(data):
    _render_release_card(data)
    st.divider()
    _render_release_gate(data)
    st.divider()
    _render_latest_batch(data)
    st.divider()
    _render_processing_state(data)
    st.divider()
    _render_missing_artifacts(data)
    st.divider()
    _render_batch_history(data)


def _render_release_card(data):
    manifest = data.export_manifest or {}
    st.markdown("#### Release Snapshot")
    metrics = [
        ("DB Version", manifest.get("db_version", "N/A")),
        ("Scoring Version", manifest.get("scoring_version", "N/A")),
        ("Products", f"{data.shared_metrics.get('product_count', 0):,}"),
        ("Generated", format_dashboard_datetime(manifest.get("generated_at"), style="compact")),
    ]
    metric_row(metrics)

    st.write("### Artifact Status")
    artifact_rows = []
    for key, present in data.release_artifact_status.items():
        artifact_rows.append({"artifact": key.replace("_", " ").title(), "status": "Present" if present else "Missing"})
    st.dataframe(pd.DataFrame(artifact_rows), width="stretch", hide_index=True, height=240)


def _render_release_gate(data):
    st.write("### Release Gate")
    metrics = data.shared_metrics
    thresholds = data.alert_thresholds
    reasons = []
    warnings = []

    if metrics.get("error_count", 0) > thresholds["max_errors"]:
        reasons.append(f"Error count {metrics['error_count']} exceeds max {thresholds['max_errors']}")
    if metrics.get("pipeline_yield_pct") is not None and metrics["pipeline_yield_pct"] < thresholds["coverage_min_pct"]:
        reasons.append(
            f"Pipeline yield {metrics['pipeline_yield_pct']}% is below threshold {thresholds['coverage_min_pct']}%"
        )
    if metrics.get("enriched_only_count", 0) > 0:
        reasons.append(f"{metrics['enriched_only_count']} enriched-only products detected")
    if metrics.get("blocked_count", 0) > 0:
        warnings.append(f"{metrics['blocked_count']} BLOCKED products in current export")
    if metrics["safety_counts"].get("has_banned_substance", 0) > 0:
        warnings.append(f"{metrics['safety_counts']['has_banned_substance']} products contain banned substances")

    build_age_days = None
    if data.latest_export_at:
        build_age_days = (datetime.now(timezone.utc) - data.latest_export_at).days
        if build_age_days > thresholds["max_build_age_days"]:
            warnings.append(f"Build is {build_age_days} days old")

    if reasons:
        status_badge("BLOCKED", "blocked")
        for reason in reasons:
            st.error(reason)
    elif warnings:
        status_badge("REVIEW", "warning")
        for warning in warnings:
            st.warning(warning)
    else:
        status_badge("GO", "pass")
        st.success("All current gate checks are within configured thresholds.")


def _render_latest_batch(data):
    st.write("### Latest Batch Run")
    snapshot = _build_live_pipeline_snapshot(data)
    latest_log = data.batch_history[0] if data.batch_history else None

    if snapshot and (
        latest_log is None
        or (snapshot.get("timestamp") and snapshot["timestamp"] >= latest_log.get("timestamp"))
    ):
        st.caption(
            f"Live pipeline snapshot | {format_dashboard_datetime(snapshot.get('timestamp'), include_timezone=True)}"
        )
        st.caption("Source: processing_state.json + output_* reports")
        batch_metrics = [
            ("Processed", snapshot.get("processed", 0)),
            ("Errors", snapshot.get("errors", 0)),
            ("Cleaned", snapshot.get("cleaned", 0)),
            ("Time (s)", round(snapshot.get("processing_time", 0.0), 2)),
        ]
        metric_row(batch_metrics)
        st.dataframe(
            pd.DataFrame(snapshot.get("datasets", [])),
            width="stretch",
            hide_index=True,
            height=260,
        )
        with st.expander("Latest batch errors"):
            if snapshot.get("error_lines"):
                _render_scroll_code(snapshot["error_lines"])
            else:
                st.caption("No errors recorded in the latest pipeline snapshot.")
        if latest_log and snapshot.get("timestamp") and latest_log.get("timestamp") and latest_log["timestamp"] < snapshot["timestamp"]:
            st.caption(
                f"Most recent batch log on disk is older: {latest_log['name']} at "
                f"{format_dashboard_datetime(latest_log.get('timestamp'), include_timezone=True)}"
            )
        return

    if not latest_log:
        st.info("No batch logs were discovered.")
        return

    latest = latest_log
    summary = latest.get("summary", {})
    st.caption(f"{latest['name']} | {format_dashboard_datetime(latest.get('timestamp'), include_timezone=True)}")

    batch_metrics = [
        ("Processed", summary.get("processed", 0)),
        ("Errors", summary.get("errors", 0)),
        ("Cleaned", summary.get("cleaned", 0)),
        ("Time (s)", round(summary.get("processing_time", 0.0), 2)),
    ]
    metric_row(batch_metrics)

    rows = []
    for dataset, details in latest.get("datasets", {}).items():
        rows.append(
            {
                "dataset": dataset,
                "status": details.get("status", "UNKNOWN"),
                "last_stage": details.get("last_stage", "UNKNOWN"),
                "error_count": len(details.get("errors", [])),
                "stage_rail": _format_stage_rail(details.get("stage_marks", {})),
            }
        )
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True, height=260)

    with st.expander("Latest batch errors"):
        if latest.get("error_lines"):
            _render_scroll_code(latest["error_lines"])
        else:
            st.caption("No errors recorded in the latest batch log.")


def _render_scroll_code(lines, height_px: int = 280):
    body = escape("\n".join(lines))
    st.markdown(
        f"""
        <div style="max-height:{height_px}px; overflow-y:auto; border:1px solid rgba(15,23,42,0.12);
                    border-radius:12px; background:#0f172a; color:#e2e8f0; padding:0.85rem;">
          <pre style="margin:0; white-space:pre-wrap; font-size:0.82rem;">{body}</pre>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _build_live_pipeline_snapshot(data):
    timestamps = [
        value for value in [data.latest_scored_at, data.latest_enriched_at, data.latest_batch_at]
        if value is not None
    ]
    if not timestamps:
        return None

    state = data.processing_state or {}
    processed = state.get("processed_files")
    errors = len(state.get("errors", []))
    cleaned = sum(report.get("cleaned_count", 0) for report in data.dataset_reports.values())
    processing_time = 0.0
    summary_generated = None

    dataset_rows = []
    for dataset, report in data.dataset_reports.items():
        parsed = _parse_processing_summary_text(report.get("processing_summary_text"))
        processing_time += parsed.get("processing_time", 0.0) or 0.0
        if parsed.get("generated_at") and (summary_generated is None or parsed["generated_at"] > summary_generated):
            summary_generated = parsed["generated_at"]
        dataset_rows.append(
            {
                "dataset": dataset,
                "status": "SUCCESS" if report.get("error_count", 0) == 0 else "FAILED",
                "last_stage": (
                    "SCORE"
                    if dataset in data.scoring_summaries
                    else "ENRICH"
                    if dataset in data.enrichment_summaries
                    else "CLEAN"
                ),
                "error_count": report.get("error_count", 0),
                "stage_rail": _format_stage_rail(
                    {
                        "CLEAN": report.get("cleaned_count", 0) > 0 or parsed.get("cleaned", 0) > 0,
                        "ENRICH": dataset in data.enrichment_summaries,
                        "SCORE": dataset in data.scoring_summaries,
                        "EXPORT": bool(data.latest_export_at and data.latest_scored_at and data.latest_export_at >= data.latest_scored_at),
                    }
                ),
            }
        )

    return {
        "timestamp": max(timestamps + ([summary_generated] if summary_generated is not None else [])),
        "processed": processed if processed is not None else cleaned + errors,
        "errors": errors,
        "cleaned": cleaned,
        "processing_time": processing_time,
        "datasets": dataset_rows,
        "error_lines": state.get("errors", []),
    }


def _parse_processing_summary_text(text: str | None) -> dict:
    if not text:
        return {}

    generated_at = None
    match = re.search(r"Generated:\s+([0-9:\-\s]+)", text)
    if match:
        generated_at = format_dashboard_datetime(match.group(1).strip().replace(" ", "T") + "+00:00")

    time_match = re.search(r"Processing Time:\s+([0-9.]+)\s+minutes", text)
    processing_time = round(float(time_match.group(1)) * 60, 2) if time_match else None

    cleaned_match = re.search(r"Successfully cleaned:\s+(\d+)", text)
    cleaned = int(cleaned_match.group(1)) if cleaned_match else 0

    generated_dt = None
    if match:
        raw = match.group(1).strip()
        generated_dt = datetime.fromisoformat(raw.replace(" ", "T")).replace(tzinfo=timezone.utc)

    return {
        "generated_at": generated_dt,
        "processing_time": processing_time,
        "cleaned": cleaned,
    }


def _format_stage_rail(stage_marks):
    stages = ["CLEAN", "ENRICH", "SCORE", "EXPORT"]
    rendered = []
    for stage in stages:
        rendered.append(f"{stage}:{'✓' if stage_marks.get(stage) else '·'}")
    return "  ".join(rendered)


def _render_processing_state(data):
    st.write("### Processing State")
    state = data.processing_state
    if not state:
        st.info("No processing_state.json found.")
        return

    rows = [
        {"field": "Started", "value": str(format_dashboard_datetime(state.get("started"), include_timezone=True))},
        {"field": "Last updated", "value": str(format_dashboard_datetime(state.get("last_updated"), include_timezone=True))},
        {"field": "Progress", "value": f"{state.get('processed_files', 0)} / {state.get('total_files', 0)} files"},
        {"field": "Can resume", "value": str(state.get("can_resume"))},
        {"field": "Errors", "value": str(len(state.get("errors", [])))},
    ]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True, height=240)


def _render_missing_artifacts(data):
    st.write("### Dataset Artifact Coverage")
    st.caption("Live output_* artifact state from current dataset folders and report files.")
    if not data.dataset_reports:
        st.info("No output_* dataset directories were found.")
        return

    rows = []
    for dataset, report in data.dataset_reports.items():
        rows.append(
            {
                "dataset": dataset,
                "cleaned_files": report.get("cleaned_count", 0),
                "error_files": report.get("error_count", 0),
                "has_unmapped_dir": report["artifacts"].get("unmapped_dir", False),
                "has_reports_dir": report["artifacts"].get("reports_dir", False),
                "last_updated": format_dashboard_datetime(report.get("latest_activity_at"), style="compact", include_timezone=True),
                "missing_expected": ", ".join(report.get("missing_expected", [])) or "None",
            }
        )
    df = pd.DataFrame(rows).sort_values(["error_files", "cleaned_files"], ascending=[False, False])
    st.dataframe(df, width="stretch", hide_index=True, height=300)


def _render_batch_history(data):
    st.write("### Batch History")
    if not data.batch_history:
        st.info("No batch history available.")
        return

    rows = []
    for entry in data.batch_history:
        summary = entry.get("summary", {})
        rows.append(
            {
                "name": entry["name"],
                "timestamp": format_dashboard_datetime(entry.get("timestamp"), style="compact", include_timezone=True),
                "processed": summary.get("processed", 0),
                "errors": summary.get("errors", 0),
                "datasets": ", ".join(entry.get("datasets", {}).keys()),
            }
        )
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True, height=320)
