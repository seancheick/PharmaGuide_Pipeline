from __future__ import annotations

import ast
import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from scripts.scoring_v4.config_registry import all_config_provenance
from scripts.scoring_v4.quality_score_config import config as quality_score_config
from scripts.dashboard.score_index import IndexReader, default_paths


DEFAULT_ALERT_THRESHOLDS = {
    "coverage_min_pct": 95,
    "max_errors": 0,
    "ban_increase_alert": True,
    "max_unmapped": 100,
    "max_build_age_days": 7,
    "max_sync_lag_hours": 24,
    # V4 scoring-anomaly thresholds (surfaced in Command Center → Scoring Integrity).
    "max_recon_mismatches": 0,    # pillars must always sum to quality_score_v4_100
    "max_out_of_range": 0,        # impossible values are always bugs
    "max_zero_pillar_pct": 5.0,   # % of scored products carrying any 0-valued pillar
}

SAFETY_COUNT_KEYS = [
    "has_banned_substance",
    "has_recalled_ingredient",
    "has_harmful_additives",
    "has_allergen_risks",
    "has_watchlist_hit",
    "has_high_risk_hit",
]


@dataclass
class DashboardData:
    db_path: Path | None = None
    db_conn: sqlite3.Connection | None = None
    export_manifest: dict[str, Any] | None = None
    export_audit: dict[str, Any] | None = None
    detail_index: dict[str, Any] | None = None
    detail_blobs_dir: Path | None = None

    enrichment_summaries: dict[str, dict[str, Any]] = field(default_factory=dict)
    scoring_summaries: dict[str, dict[str, Any]] = field(default_factory=dict)
    coverage_reports: dict[str, dict[str, Any]] = field(default_factory=dict)
    form_fallback_reports: dict[str, dict[str, Any]] = field(default_factory=dict)
    parent_fallback_reports: dict[str, dict[str, Any]] = field(default_factory=dict)
    report_dirs: dict[str, Path] = field(default_factory=dict)
    dataset_reports: dict[str, dict[str, Any]] = field(default_factory=dict)

    processing_state: dict[str, Any] | None = None
    scoring_config_snapshot: dict[str, Any] = field(default_factory=dict)
    batch_run_files: list[Path] = field(default_factory=list)
    batch_history: list[dict[str, Any]] = field(default_factory=list)
    latest_batch_summary: dict[str, Any] | None = None

    latest_enriched_at: datetime | None = None
    latest_scored_at: datetime | None = None
    latest_export_at: datetime | None = None
    latest_batch_at: datetime | None = None

    scan_dir: Path = Path(".")
    build_root: Path = Path(".")
    dataset_root: Path | None = None
    flutter_repo: Path | None = None
    discovered_datasets: list[str] = field(default_factory=list)
    missing_artifacts: dict[str, list[str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    release_artifact_status: dict[str, Any] = field(default_factory=dict)

    integrity_data: dict[str, Any] | None = None
    remote_manifest: dict[str, Any] | None = None
    sync_failures: list[dict[str, Any]] = field(default_factory=list)
    storage_health: dict[str, Any] | None = None

    build_history: list[dict[str, Any]] = field(default_factory=list)
    alert_thresholds: dict[str, Any] = field(default_factory=dict)
    shared_metrics: dict[str, Any] = field(default_factory=dict)
    label_trust: dict[str, Any] = field(default_factory=dict)
    index: Any = None  # score_index.IndexReader over the current dashboard index build

    caers_signals: dict[str, Any] = field(default_factory=dict)
    caers_metadata: dict[str, Any] = field(default_factory=dict)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _mtime(path: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def _parse_report_filename_timestamp(path: Path) -> datetime | None:
    match = re.search(r"(\d{8}_\d{6})", path.name)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_processing_summary_generated_at(text: str | None) -> datetime | None:
    if not text:
        return None
    for line in text.splitlines():
        if line.startswith("Generated:"):
            generated = line.split("Generated:", 1)[1].strip().replace(" ", "T")
            try:
                parsed = datetime.fromisoformat(generated)
            except ValueError:
                return None
            if parsed.tzinfo is None:
                local_tz = datetime.now().astimezone().tzinfo or timezone.utc
                parsed = parsed.replace(tzinfo=local_tz)
            return parsed.astimezone(timezone.utc)
    return None


def _report_timestamp(path: Path, content: dict[str, Any] | None = None, text: str | None = None) -> datetime | None:
    candidates = []
    if content:
        for key in ("generated_at", "completed_at", "last_updated", "timestamp", "created_at"):
            parsed = _parse_datetime(content.get(key))
            if parsed:
                candidates.append(parsed)
    summary_generated = _parse_processing_summary_generated_at(text)
    if summary_generated:
        candidates.append(summary_generated)
    filename_timestamp = _parse_report_filename_timestamp(path)
    if filename_timestamp:
        candidates.append(filename_timestamp)
    if candidates:
        return max(candidates)
    return _mtime(path)


@st.cache_resource
def get_sqlite_connection(db_path: Path) -> sqlite3.Connection | None:
    if not db_path.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error:
        return None


def safe_load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _dashboard_root() -> Path:
    return Path(__file__).resolve().parent


def _load_alert_thresholds() -> dict[str, Any]:
    alert_path = _dashboard_root() / "dashboard_alerts.json"
    data = safe_load_json(alert_path)
    if not data:
        return dict(DEFAULT_ALERT_THRESHOLDS)
    merged = dict(DEFAULT_ALERT_THRESHOLDS)
    merged.update(data)
    return merged


def _discover_build_history(build_root: Path, dataset_root: Path | None) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}

    def add_candidate(root: Path) -> None:
        manifest_path = root / "export_manifest.json"
        db_path = root / "pharmaguide_core.db"
        audit_path = root / "export_audit_report.json"
        if not manifest_path.exists() and not db_path.exists():
            return
        manifest = safe_load_json(manifest_path) or {}
        audit = safe_load_json(audit_path) or {}
        counts = audit.get("counts", {})
        generated_at = _parse_datetime(manifest.get("generated_at")) or _mtime(manifest_path) or _mtime(db_path)
        label = manifest.get("db_version") or root.name
        candidates[str(root.resolve())] = {
            "label": label,
            "build_root": root.resolve(),
            "manifest_path": manifest_path.resolve() if manifest_path.exists() else None,
            "db_path": db_path.resolve() if db_path.exists() else None,
            "audit_path": audit_path.resolve() if audit_path.exists() else None,
            "generated_at": generated_at,
            "product_count": manifest.get("product_count"),
            "scoring_version": manifest.get("scoring_version"),
            "pipeline_version": manifest.get("pipeline_version"),
            "detail_blob_count": manifest.get("detail_blob_count"),
            "error_count": counts.get("total_errors", 0),
            "enriched_only_count": counts.get("enriched_only", 0),
            "scored_only_count": counts.get("scored_only", 0),
            "manifest": manifest,
            "audit": audit,
        }

    add_candidate(build_root)
    parent = build_root.parent
    if parent.exists():
        for child in parent.iterdir():
            if child.is_dir():
                add_candidate(child)
    if dataset_root:
        builds_dir = dataset_root / "builds"
        if builds_dir.exists():
            for child in builds_dir.iterdir():
                if child.is_dir():
                    add_candidate(child)

    history = list(candidates.values())
    history.sort(key=lambda item: item.get("generated_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return history


def _discover_output_dirs(scan_dir: Path) -> list[Path]:
    return sorted([path for path in scan_dir.glob("output_*") if path.is_dir()])


def _dataset_name(output_dir: Path) -> str:
    return output_dir.name.replace("output_", "").replace("_", " ").strip() or output_dir.name


def _load_unmapped_report(path: Path, key: str) -> list[dict[str, Any]]:
    payload = safe_load_json(path) or {}
    rows = payload.get(key, [])
    if not isinstance(rows, list):
        return []
    return rows


def _latest_report_dir(report_root: Path) -> Path:
    """The directory holding a dataset's newest reports. Enrich and score
    write ``reports/runs/<run_id>/``; older outputs wrote flat
    ``reports/*.json``. All reports are read from one run so the dashboard
    never pairs one run's queue with another run's summary."""
    runs = report_root / "runs"
    candidates = [path for path in runs.iterdir() if path.is_dir()] if runs.is_dir() else []
    candidates.append(report_root)
    dated = []
    for directory in candidates:
        times = [path.stat().st_mtime for path in directory.glob("*.json")]
        if times:
            dated.append((max(times), str(directory), directory))
    return max(dated)[2] if dated else report_root


def _parse_dataset_report(output_dir: Path) -> dict[str, Any]:
    report_dir = output_dir / "reports"
    unmapped_dir = output_dir / "unmapped"
    cleaned_dir = output_dir / "cleaned"
    errors_dir = output_dir / "errors"

    artifacts = {
        "reports_dir": report_dir.exists(),
        "cleaned_dir": cleaned_dir.exists(),
        "errors_dir": errors_dir.exists(),
        "unmapped_dir": unmapped_dir.exists(),
    }

    processing_summary_path = report_dir / "processing_summary.txt"
    processing_summary_text = processing_summary_path.read_text() if processing_summary_path.exists() else None

    report = {
        "output_dir": output_dir,
        "artifacts": artifacts,
        "cleaned_files": sorted(cleaned_dir.glob("*.json")) if cleaned_dir.exists() else [],
        "error_files": sorted(errors_dir.glob("*_error.json")) if errors_dir.exists() else [],
        "processing_summary_path": processing_summary_path,
        "processing_summary_text": processing_summary_text,
        "unmapped_active": _load_unmapped_report(unmapped_dir / "unmapped_active_ingredients.json", "unmapped_ingredients"),
        "unmapped_inactive": _load_unmapped_report(unmapped_dir / "unmapped_inactive_ingredients.json", "unmapped_ingredients"),
        "needs_review_active": _load_unmapped_report(unmapped_dir / "needs_verification_active_ingredients.json", "ingredients"),
        "needs_review_inactive": _load_unmapped_report(unmapped_dir / "needs_verification_inactive_ingredients.json", "ingredients"),
    }
    report["cleaned_count"] = len(report["cleaned_files"])
    report["error_count"] = len(report["error_files"])
    report_file_times = []
    pipeline_report_times = []
    for path in report_dir.glob("*"):
        text = None
        content = None
        if path.suffix == ".json":
            content = safe_load_json(path)
            if not content:
                content = None
        elif path.name == "processing_summary.txt":
            text = processing_summary_text
        timestamp = _report_timestamp(path, content=content, text=text)
        if timestamp:
            report_file_times.append(timestamp)
            if content is not None or text is not None:
                pipeline_report_times.append(timestamp)
    report["latest_activity_at"] = max(
        [_mtime(output_dir)]
        + [_mtime(path) for path in report["cleaned_files"] + report["error_files"] if _mtime(path)]
        + report_file_times,
        default=None,
    )
    report["latest_pipeline_at"] = max(pipeline_report_times, default=None)
    report["missing_expected"] = [
        name for name, present in artifacts.items() if not present and name != "reports_dir"
    ]
    return report


def _extract_dataset_from_path(text: str) -> str | None:
    patterns = [
        r"/brands/([^/]+)/",
        r"/output_([^/]+)/",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).replace("_", " ")
    return None


BATCH_HISTORY_LIMIT = 40  # newest logs only; 399 full logs took ~14 s to parse on every load


def _parse_batch_summary_text(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return _parse_batch_summary_cached(str(path), stat.st_size, stat.st_mtime_ns)


@st.cache_data(show_spinner=False, max_entries=256)
def _parse_batch_summary_cached(path_text: str, size: int, mtime_ns: int) -> dict[str, Any]:
    """Parse one batch log; cached per (path, size, mtime) so unchanged logs are read once."""
    path = Path(path_text)
    text = path.read_text(errors="replace")
    lines = text.splitlines()
    info: dict[str, Any] = {
        "path": path,
        "name": path.name,
        "kind": "batch_log",
        "summary": {},
        "datasets": {},
        "error_lines": [],
        "started": None,
        "ended": None,
    }
    for line in lines:
        if "Started:" in line:
            info["started"] = _parse_datetime(line.split("Started:", 1)[1].strip().replace(" ", "T") + "+00:00")
        elif "Ended:" in line:
            info["ended"] = _parse_datetime(line.split("Ended:", 1)[1].strip().replace(" ", "T") + "+00:00")
        elif "Summary:" in line:
            raw = line.split("Summary:", 1)[1].strip()
            try:
                info["summary"] = ast.literal_eval(raw)
            except (SyntaxError, ValueError):
                info["summary"] = {}
        elif "ERROR -" in line:
            message = line.split("ERROR -", 1)[1].strip()
            info["error_lines"].append(message)
            dataset = _extract_dataset_from_path(message) or "Unknown"
            dataset_state = info["datasets"].setdefault(
                dataset,
                {"status": "FAILED", "last_stage": "CLEAN", "errors": []},
            )
            dataset_state["errors"].append(message)

    if not info["datasets"]:
        dataset = _extract_dataset_from_path(text) or "Unknown"
        errors = info["summary"].get("errors", 0)
        info["datasets"][dataset] = {
            "status": "FAILED" if errors else "SUCCESS",
            "last_stage": "CLEAN",
            "errors": info["error_lines"],
        }

    for dataset_state in info["datasets"].values():
        dataset_state["stage_marks"] = {
            "CLEAN": dataset_state["status"] == "SUCCESS" or dataset_state["status"] == "FAILED",
            "ENRICH": False,
            "SCORE": False,
            "EXPORT": False,
        }

    timestamp = info.get("started") or info.get("ended") or _mtime(path)
    info["timestamp"] = timestamp
    return info


def _discover_batch_history(scan_dir: Path) -> tuple[list[Path], list[dict[str, Any]]]:
    batch_files = sorted(scan_dir.glob("batch_run_summary_*.txt"))
    report_files = sorted((scan_dir / "reports").glob("batch_run_summary_*.txt")) if (scan_dir / "reports").exists() else []
    batch_logs = sorted((scan_dir / "logs").glob("batch_*_log.txt")) if (scan_dir / "logs").exists() else []
    legacy_logs = []
    parent_logs_dir = scan_dir.parent / "logs"
    if parent_logs_dir.exists() and parent_logs_dir != scan_dir / "logs":
        legacy_logs = sorted(parent_logs_dir.glob("batch_*_log.txt"))
    all_files = batch_files + report_files + batch_logs + legacy_logs
    newest = sorted(all_files, key=lambda path: path.stat().st_mtime_ns, reverse=True)[:BATCH_HISTORY_LIMIT]
    history = [_parse_batch_summary_text(path) for path in newest]
    history.sort(key=lambda item: item.get("timestamp") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    sorted_files = [item["path"] for item in history]
    return sorted_files, history




_LABEL_TRUST_FORM_STATES = frozenset({
    "assessed",
    "not_disclosed",
    "listed_not_assessed",
    "not_applicable",
    "needs_review",
})
_LABEL_TRUST_IDENTITY_STATES = frozenset({
    "clean",
    "repaired",
    "taxonomy_only",
    "identity_conflict",
    "missing_display_label",
})
_LABEL_TRUST_DISPOSITIONS = frozenset({
    "scored",
    "label_context",
    "other_ingredient",
    "needs_review",
})
_LABEL_MISMATCH_STATUSES = frozenset({
    "submitted",
    "under_review",
    "resolved",
    "dismissed",
})
_LABEL_MISMATCH_CATEGORIES = frozenset({
    "product_identity",
    "ingredient_missing",
    "ingredient_extra",
    "amount_or_unit",
    "form_or_parenthetical",
    "serving_size_or_directions",
    "other_ingredients",
    "catalog_version_or_status",
})


def _empty_label_trust_metrics() -> dict[str, Any]:
    return {
        "total_products": 0,
        "supported_products": 0,
        "unsupported_products": 0,
        "complete_products": 0,
        "incomplete_products": 0,
        "unavailable_products": 0,
        "invalid_audit_products": 0,
        "average_completeness_pct": None,
        "display_dispositions": {},
        "form_states": {},
        "identity_states": {},
        "integrity_failures": 0,
        "identity_failure_products": 0,
        "total_display_rows": 0,
        "unrecognized_display_dispositions": 0,
        "unrecognized_form_states": 0,
        "unrecognized_identity_states": 0,
        "formula_history_products": 0,
        "formula_history_coverage_pct": None,
        "mismatch_outcomes": {},
        "mismatch_categories": {},
        "rejected_mismatch_outcomes": 0,
        "rejected_mismatch_categories": 0,
        "invalid_mismatch_summary": 0,
        "by_brand": [],
        "by_category": [],
    }


def _safe_aggregate_counts(
    rows: Any,
    *,
    key: str,
    allowed: frozenset[str],
) -> tuple[dict[str, int], int]:
    counts: Counter[str] = Counter()
    rejected = 0
    if not isinstance(rows, list):
        return {}, 0
    for row in rows:
        if not isinstance(row, dict):
            rejected += 1
            continue
        name = row.get(key)
        count = row.get("count")
        if (
            set(row) != {key, "count"}
            or not isinstance(name, str)
            or name not in allowed
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
        ):
            rejected += 1
            continue
        counts[name] += count
    return dict(sorted(counts.items())), rejected


def _load_label_mismatch_summary(
    path: Path | None,
) -> tuple[dict[str, int], dict[str, int], int, int, int]:
    if path is None or not path.exists():
        return {}, {}, 0, 0, 0
    summary = safe_load_json(path)
    if (
        not isinstance(summary, dict)
        or set(summary) != {"schema_version", "outcomes", "categories"}
        or type(summary.get("schema_version")) is not int
        or summary.get("schema_version") != 1
        or not isinstance(summary.get("outcomes"), list)
        or not isinstance(summary.get("categories"), list)
    ):
        return {}, {}, 0, 0, 1
    outcomes, rejected_outcomes = _safe_aggregate_counts(
        summary.get("outcomes"),
        key="status",
        allowed=_LABEL_MISMATCH_STATUSES,
    )
    categories, rejected_categories = _safe_aggregate_counts(
        summary.get("categories"),
        key="category",
        allowed=_LABEL_MISMATCH_CATEGORIES,
    )
    return outcomes, categories, rejected_outcomes, rejected_categories, 0


def _label_trust_breakdown_rows(
    stats: dict[str, dict[str, Any]],
    *,
    dimension: str,
) -> list[dict[str, Any]]:
    rows = []
    for name, values in sorted(stats.items()):
        percentages = values["percentages"]
        rows.append({
            dimension: name,
            "total_products": values["total_products"],
            "supported_products": values["supported_products"],
            "unsupported_products": values["unsupported_products"],
            "complete_products": values["complete_products"],
            "incomplete_products": values["incomplete_products"],
            "unavailable_products": values["unavailable_products"],
            "invalid_audit_products": values["invalid_audit_products"],
            "average_completeness_pct": (
                round(sum(percentages) / len(percentages), 2)
                if percentages
                else None
            ),
        })
    return rows


def compute_label_trust(
    records: Any,
    mismatch_summary_path: Path | None = None,
) -> dict[str, Any]:
    """Release label-trust metrics from per-product records (``score_index.label_trust_record``).

    Records come from the dashboard index, so a page load never scans detail blobs.
    """
    (
        mismatch_outcomes,
        mismatch_categories,
        rejected_mismatch_outcomes,
        rejected_mismatch_categories,
        invalid_mismatch_summary,
    ) = _load_label_mismatch_summary(mismatch_summary_path)
    label_trust = _empty_label_trust_metrics()
    label_trust_percentages: list[float] = []
    label_trust_dispositions: Counter[str] = Counter()
    label_trust_form_states: Counter[str] = Counter()
    label_trust_identity_states: Counter[str] = Counter()
    label_trust_identity_failure_products: set[str] = set()

    def _dimension() -> dict[str, Any]:
        return {
            "total_products": 0,
            "supported_products": 0,
            "unsupported_products": 0,
            "complete_products": 0,
            "incomplete_products": 0,
            "unavailable_products": 0,
            "invalid_audit_products": 0,
            "percentages": [],
        }

    label_trust_by_brand: defaultdict[str, dict[str, Any]] = defaultdict(_dimension)
    label_trust_by_category: defaultdict[str, dict[str, Any]] = defaultdict(_dimension)

    for blob in records or []:
        if not isinstance(blob, dict) or not blob:
            continue
        dsld_id = str(blob.get("dsld_id"))
        label_trust["total_products"] += 1
        audit = blob.get("label_ledger_audit")
        audit = audit if isinstance(audit, dict) else {}
        support_status = audit.get("support_status")
        completeness_status = audit.get("completeness_status")
        completeness_percentage = audit.get("completeness_percentage")
        percentage_is_valid_number = (
            not isinstance(completeness_percentage, bool)
            and isinstance(completeness_percentage, (int, float))
            and 0 <= completeness_percentage <= 100
        )
        audit_tuple_is_valid = (
            support_status == "supported"
            and (
                (
                    completeness_status == "complete"
                    and completeness_percentage == 100
                )
                or (
                    completeness_status == "incomplete"
                    and percentage_is_valid_number
                    and completeness_percentage < 100
                )
            )
        ) or (
            support_status == "unsupported"
            and completeness_status == "unavailable"
            and completeness_percentage is None
        )
        audit_completeness_bucket: str | None = None
        if not audit_tuple_is_valid:
            label_trust["invalid_audit_products"] += 1
        elif support_status == "supported":
            label_trust["supported_products"] += 1
            audit_completeness_bucket = completeness_status
            label_trust[f"{audit_completeness_bucket}_products"] += 1
        else:
            label_trust["unsupported_products"] += 1
            audit_completeness_bucket = "unavailable"
            label_trust["unavailable_products"] += 1
        if audit_tuple_is_valid and percentage_is_valid_number:
            label_trust_percentages.append(float(completeness_percentage))

        brand_name = str(blob.get("brand_name") or "Unspecified").strip() or "Unspecified"
        primary_type = str(blob.get("primary_type") or "Unspecified").strip() or "Unspecified"
        for dimension_stats, name in (
            (label_trust_by_brand, brand_name),
            (label_trust_by_category, primary_type),
        ):
            dimension_stats[name]["total_products"] += 1
            if not audit_tuple_is_valid:
                dimension_stats[name]["invalid_audit_products"] += 1
            else:
                dimension_stats[name][f"{support_status}_products"] += 1
                dimension_stats[name][
                    f"{audit_completeness_bucket}_products"
                ] += 1
            if audit_tuple_is_valid and percentage_is_valid_number:
                dimension_stats[name]["percentages"].append(
                    float(completeness_percentage)
                )

        display_rows = blob.get("display_ingredients")
        if isinstance(display_rows, list):
            for row in display_rows:
                if not isinstance(row, dict):
                    continue
                label_trust["total_display_rows"] += 1
                disposition = row.get("display_disposition")
                if (
                    isinstance(disposition, str)
                    and disposition in _LABEL_TRUST_DISPOSITIONS
                ):
                    label_trust_dispositions[disposition] += 1
                else:
                    label_trust["unrecognized_display_dispositions"] += 1
                form_state = row.get("form_display_state")
                if isinstance(form_state, str) and form_state in _LABEL_TRUST_FORM_STATES:
                    label_trust_form_states[form_state] += 1
                else:
                    label_trust["unrecognized_form_states"] += 1
                identity_state = row.get("identity_integrity_state")
                identity_state_is_known = (
                    isinstance(identity_state, str)
                    and identity_state in _LABEL_TRUST_IDENTITY_STATES
                )
                if identity_state_is_known:
                    label_trust_identity_states[identity_state] += 1
                else:
                    label_trust["unrecognized_identity_states"] += 1
                if not identity_state_is_known or identity_state in {
                    "identity_conflict",
                    "missing_display_label",
                }:
                    label_trust["integrity_failures"] += 1
                    label_trust_identity_failure_products.add(dsld_id)

        label_record = blob.get("label_record")
        if isinstance(label_record, dict):
            formula_history = label_record.get("formula_history")
            if (
                label_record.get("history_status") == "available"
                and isinstance(formula_history, list)
                and bool(formula_history)
            ):
                label_trust["formula_history_products"] += 1

    label_trust["average_completeness_pct"] = (
        round(sum(label_trust_percentages) / len(label_trust_percentages), 2)
        if label_trust_percentages
        else None
    )
    label_trust["display_dispositions"] = dict(
        sorted(label_trust_dispositions.items())
    )
    label_trust["form_states"] = dict(sorted(label_trust_form_states.items()))
    label_trust["identity_states"] = dict(
        sorted(label_trust_identity_states.items())
    )
    label_trust["identity_failure_products"] = len(
        label_trust_identity_failure_products
    )
    label_trust["formula_history_coverage_pct"] = (
        round(
            label_trust["formula_history_products"]
            / label_trust["total_products"]
            * 100,
            2,
        )
        if label_trust["total_products"]
        else None
    )
    label_trust["mismatch_outcomes"] = mismatch_outcomes
    label_trust["mismatch_categories"] = mismatch_categories
    label_trust["rejected_mismatch_outcomes"] = rejected_mismatch_outcomes
    label_trust["rejected_mismatch_categories"] = rejected_mismatch_categories
    label_trust["invalid_mismatch_summary"] = invalid_mismatch_summary
    label_trust["by_brand"] = _label_trust_breakdown_rows(
        label_trust_by_brand,
        dimension="brand_name",
    )
    label_trust["by_category"] = _label_trust_breakdown_rows(
        label_trust_by_category,
        dimension="primary_type",
    )

    return label_trust


def _compute_shared_metrics(
    db_conn: sqlite3.Connection | None,
    export_manifest: dict[str, Any] | None,
    export_audit: dict[str, Any] | None,
    integrity_data: dict[str, Any] | None,
) -> dict[str, Any]:
    counts = (export_audit or {}).get("counts", {})
    status_counts: dict[str, int] = {}
    safety_status_counts: dict[str, int] = {}
    safety_counts = {key: int(counts.get(key, 0)) for key in SAFETY_COUNT_KEYS}
    product_count = int((export_manifest or {}).get("product_count") or counts.get("total_exported", 0))
    average_score = None
    average_coverage_pct = None
    blocked_count = 0

    if db_conn is not None:
        for row in db_conn.execute(
            "SELECT quality_score_status AS status, COUNT(*) AS count FROM products_core GROUP BY quality_score_status"
        ).fetchall():
            status_counts[str(row["status"])] = int(row["count"])
        for row in db_conn.execute(
            "SELECT product_safety_status AS status, COUNT(*) AS count FROM products_core GROUP BY product_safety_status"
        ).fetchall():
            safety_status_counts[str(row["status"])] = int(row["count"])
        avg_row = db_conn.execute(
            "SELECT AVG(CASE WHEN quality_score_status = 'scored' THEN quality_score_v4_100 END) AS avg_score, "
            "AVG(mapped_coverage) AS avg_coverage FROM products_core"
        ).fetchone()
        average_score = round(float(avg_row["avg_score"] or 0.0), 1)
        average_coverage_pct = round(float(avg_row["avg_coverage"] or 0.0) * 100, 1)
        blocked_count = safety_status_counts.get("blocked", 0)
        product_count = int(
            db_conn.execute("SELECT COUNT(*) AS count FROM products_core").fetchone()["count"]
        )

    enriched_input_count = None
    scored_input_count = None
    error_count = int(counts.get("total_errors", 0))
    enriched_only_count = int(counts.get("enriched_only", 0))
    scored_only_count = int(counts.get("scored_only", 0))
    strict_mode = False
    if integrity_data:
        enriched_input_count = integrity_data.get("enriched_input_count")
        scored_input_count = integrity_data.get("scored_input_count")
        error_count = len(integrity_data.get("errors", [])) or error_count
        enriched_only_count = integrity_data.get("enriched_only_count", enriched_only_count)
        scored_only_count = integrity_data.get("scored_only_count", scored_only_count)
        strict_mode = bool(integrity_data.get("strict_mode", False))

    if enriched_input_count is None:
        enriched_input_count = product_count + enriched_only_count + error_count
    if scored_input_count is None:
        scored_input_count = product_count + scored_only_count + error_count

    pipeline_yield_pct = round((product_count / enriched_input_count) * 100, 1) if enriched_input_count else None

    return {
        "product_count": product_count,
        "status_counts": status_counts,
        "safety_status_counts": safety_status_counts,
        "safety_counts": safety_counts,
        "average_score": average_score,
        "average_coverage_pct": average_coverage_pct,
        "enriched_input_count": enriched_input_count,
        "scored_input_count": scored_input_count,
        "exported_count": product_count,
        "error_count": error_count,
        "enriched_only_count": enriched_only_count,
        "scored_only_count": scored_only_count,
        "pipeline_yield_pct": pipeline_yield_pct,
        "strict_mode": strict_mode,
        "blocked_count": blocked_count,
    }




def _load_release_config_provenance(db_conn: sqlite3.Connection | None) -> list[dict[str, Any]]:
    """Scoring-config provenance stamped on released products, with product counts.

    Reads products_core.v4_config_fingerprint, the scored artifact's
    config_registry.all_config_provenance() stamp. An older DB without the
    column, or no DB, yields an empty list (comparison unknown).
    """
    if db_conn is None:
        return []
    try:
        rows = db_conn.execute(
            "SELECT v4_config_fingerprint AS stamp, COUNT(*) AS products "
            "FROM products_core GROUP BY v4_config_fingerprint"
        ).fetchall()
    except sqlite3.Error:
        return []
    release = []
    for stamp, products in rows:
        try:
            provenance = json.loads(stamp) if stamp else None
            if not isinstance(provenance, dict):
                provenance = None
        except (TypeError, json.JSONDecodeError):
            provenance = None
        release.append({"provenance": provenance, "products": int(products)})
    return release


def _load_scoring_config_snapshot(db_conn: sqlite3.Connection | None, warnings: list[str]) -> dict[str, Any]:
    """Production v4 scoring config as the scorer stamps it, plus the release's stamp."""
    try:
        # The Streamlit resource cache owns dashboard freshness (Refresh + TTL).
        # Process-long scorer caches must neither mask edits nor be invalidated.
        provenance = all_config_provenance(fresh=True)
        pillars = quality_score_config(fresh=True)["pillars"]
        if not isinstance(pillars, dict) or not pillars:
            raise ValueError("quality_score pillars must be a nonempty object")
        pillar_weights = {name: spec["weight"] for name, spec in pillars.items()}
        if any(type(weight) not in (int, float) or not math.isfinite(weight)
               for weight in pillar_weights.values()):
            raise ValueError("quality_score pillar weights must be finite numbers")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        warnings.append(f"v4 scoring config could not be read: {exc}")
        return {}
    return {
        "provenance": provenance,
        "pillar_weights": pillar_weights,
        "release": _load_release_config_provenance(db_conn),
    }


@st.cache_resource(ttl=300)
def load_dashboard_data(config: Any) -> DashboardData:
    data = DashboardData(
        scan_dir=config.scan_dir,
        build_root=config.build_root,
        dataset_root=config.dataset_root,
        flutter_repo=config.flutter_repo,
    )

    data.db_path = config.build_root / "pharmaguide_core.db"
    data.db_conn = get_sqlite_connection(data.db_path)
    data.export_manifest = safe_load_json(config.build_root / "export_manifest.json")
    data.export_audit = safe_load_json(config.build_root / "export_audit_report.json")
    data.detail_index = safe_load_json(config.build_root / "detail_index.json")
    data.detail_blobs_dir = config.build_root / "detail_blobs"
    data.processing_state = safe_load_json(config.scan_dir / "logs" / "processing_state.json")
    data.scoring_config_snapshot = _load_scoring_config_snapshot(data.db_conn, data.warnings)

    data.integrity_data = (data.export_manifest or {}).get("integrity", {}) or None
    data.alert_thresholds = _load_alert_thresholds()
    data.build_history = _discover_build_history(config.build_root, config.dataset_root)

    if data.export_manifest:
        data.latest_export_at = _parse_datetime(data.export_manifest.get("generated_at"))
    if data.processing_state:
        data.latest_batch_at = _parse_datetime(data.processing_state.get("last_updated"))

    data.release_artifact_status = {
        "db": data.db_path.exists(),
        "manifest": (config.build_root / "export_manifest.json").exists(),
        "audit": (config.build_root / "export_audit_report.json").exists(),
        "detail_index": (config.build_root / "detail_index.json").exists(),
        "blobs": bool(data.detail_blobs_dir and data.detail_blobs_dir.exists()),
    }

    if not data.release_artifact_status["db"]:
        data.warnings.append(f"Database not found at {data.db_path}")
    if not data.release_artifact_status["manifest"]:
        data.warnings.append(f"Manifest not found at {config.build_root / 'export_manifest.json'}")
    if not data.release_artifact_status["detail_index"]:
        data.warnings.append(f"Detail index not found at {config.build_root / 'detail_index.json'}")

    for output_dir in _discover_output_dirs(config.scan_dir):
        dataset_name = _dataset_name(output_dir)
        dataset_report = _parse_dataset_report(output_dir)
        data.dataset_reports[dataset_name] = dataset_report
        data.discovered_datasets.append(dataset_name)
        if dataset_report["latest_pipeline_at"]:
            if data.latest_enriched_at is None or dataset_report["latest_pipeline_at"] > data.latest_enriched_at:
                data.latest_enriched_at = dataset_report["latest_pipeline_at"]
        data.missing_artifacts[dataset_name] = dataset_report["missing_expected"]

        report_dir = _latest_report_dir(output_dir / "reports")
        data.report_dirs[dataset_name] = report_dir
        for report_path in report_dir.glob("*.json"):
            content = safe_load_json(report_path)
            if not content:
                continue
            if "enrichment_summary" in report_path.name:
                data.enrichment_summaries[dataset_name] = content
                timestamp = _report_timestamp(report_path, content=content)
                if timestamp and (data.latest_enriched_at is None or timestamp > data.latest_enriched_at):
                    data.latest_enriched_at = timestamp
            elif "scoring_summary" in report_path.name:
                data.scoring_summaries[dataset_name] = content
                timestamp = _report_timestamp(report_path, content=content)
                if timestamp and (data.latest_scored_at is None or timestamp > data.latest_scored_at):
                    data.latest_scored_at = timestamp
            elif "coverage_report" in report_path.name:
                data.coverage_reports[dataset_name] = content
            elif "form_fallback" in report_path.name:
                data.form_fallback_reports[dataset_name] = content
            elif "parent_fallback" in report_path.name:
                data.parent_fallback_reports[dataset_name] = content

    data.discovered_datasets = sorted(set(data.discovered_datasets))

    data.batch_run_files, data.batch_history = _discover_batch_history(config.scan_dir)
    if data.batch_history:
        data.latest_batch_summary = data.batch_history[0]
        latest_log_at = data.batch_history[0].get("timestamp")
        if latest_log_at and (data.latest_batch_at is None or latest_log_at > data.latest_batch_at):
            data.latest_batch_at = latest_log_at

    live_pipeline_candidates = [
        timestamp for timestamp in [
            data.latest_batch_at,
            data.latest_enriched_at,
            data.latest_scored_at,
        ] if timestamp is not None
    ]
    if live_pipeline_candidates:
        data.latest_batch_at = max(live_pipeline_candidates)

    data.shared_metrics = _compute_shared_metrics(data.db_conn, data.export_manifest, data.export_audit, data.integrity_data)
    data.index = IndexReader(default_paths(config.scan_dir, config.build_root))
    data.label_trust = compute_label_trust(
        data.index.label_records(),
        config.build_root / "label_mismatch_summary.json",
    )

    # Load CAERS adverse event signals
    caers_path = Path("scripts/data/caers_adverse_event_signals.json")
    caers_raw = safe_load_json(caers_path)
    if caers_raw:
        data.caers_signals = caers_raw.get("signals", {})
        data.caers_metadata = caers_raw.get("_metadata", {})

    return data
