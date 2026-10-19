from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.dashboard.time_format import format_dashboard_datetime


def _meta(title, summary, planes, sources, freshness, notes=(), warning=""):
    return {
        "page_title": title,
        "page_summary": summary,
        "data_planes": list(planes),
        "source_paths": list(sources),
        "freshness_fields": list(freshness),
        "mixed_plane_warning": warning,
        "usage_notes": list(notes),
    }


_INDEX_PLANES = ("Candidate (scored outputs)", "Release (catalog)", "History")
PAGE_META: dict[str, dict[str, Any]] = {
    "overview": _meta(
        "Overview",
        "Is the newest scoring run healthy, how does it differ from what ships, and what needs attention first.",
        _INDEX_PLANES, ["dashboard_index", "scored_outputs", "release_db", "export_manifest", "processing_state"],
        ["latest_export_at", "latest_batch_at", "latest_dataset_activity"],
        ["Readiness here is informational; it is never a release gate."],
        "Candidate results are pipeline outputs that are not yet published; release figures are what ships.",
    ),
    "audit-queue": _meta(
        "Audit Queue",
        "Contradictions, integrity defects and unexplained changes found by versioned rules — with triage.",
        _INDEX_PLANES, ["dashboard_index", "scoring_config"], ["latest_dataset_activity"],
        ["Audit states such as Evidence 0 or a neutral Dose are not findings; find them in Product Explorer."],
    ),
    "run-compare": _meta(
        "Run Compare & Trends",
        "Review a candidate against a baseline run: score and tier movement, status changes and their causes.",
        _INDEX_PLANES, ["dashboard_index", "scored_outputs", "release_db"], ["latest_export_at", "latest_dataset_activity"],
        ["Older catalogs are pillar totals only: their movements show deltas, never invented causes."],
    ),
    "product-explorer": _meta(
        "Product Explorer",
        "Every product with its six pillars. Filter by any score, state or receipt line and open the trace.",
        _INDEX_PLANES, ["dashboard_index", "scored_outputs", "release_db"], ["latest_dataset_activity"],
        ["Saved views list audit states, not defects."],
    ),
    "product-trace": _meta(
        "Product Trace",
        "Where every point of one product's score came from, and every point it did not earn.",
        _INDEX_PLANES, ["dashboard_index", "scored_outputs", "detail_blobs"], ["latest_dataset_activity"],
        ["Values are the scorer's own receipts; the dashboard never recomputes a score."],
    ),
    "score-lab": _meta(
        "Score Lab",
        "How the scoring behaves across the catalog: distributions, rule impact, neutral usage, caps and floors.",
        _INDEX_PLANES, ["dashboard_index", "scoring_config"], ["latest_dataset_activity"],
        ["Peer percentiles are context for one run and config, never a second score."],
    ),
    "coverage-calibration": _meta(
        "Coverage & Calibration",
        "Calibration records behind the numbers, what the scorer could and could not assess, and the golden set.",
        _INDEX_PLANES, ["scoring_config", "dashboard_index", "canaries"], ["latest_dataset_activity"],
    ),
    "market-intelligence": _meta(
        "Market Intelligence",
        "Brands, categories, ingredients and forms across the catalog.",
        _INDEX_PLANES, ["dashboard_index", "release_db"], ["latest_dataset_activity"],
        ["Rankings include complete, scored products only, with minimum sample sizes."],
    ),
    "safety-regulatory": _meta(
        "Safety & Regulatory",
        "Blocked and suppressed products with their reasons, upper-limit findings, CAERS signals and safety copy. "
        "v4 applies no CAERS penalty.",
        _INDEX_PLANES, ["dashboard_index", "release_db", "caers"], ["latest_export_at"],
        ["v4 applies no CAERS penalty; CAERS signals are context for review, not points."],
    ),
    "data-quality": _meta(
        "Data Quality, Release & Ops",
        "Pipeline and batch health, coverage and fallbacks, config snapshot, release diff and index status.",
        ("Release Snapshot", "Pipeline Logs", "Dataset Outputs"),
        ["release_db", "export_manifest", "export_audit", "processing_state", "batch_logs", "dataset_outputs",
         "scoring_config", "dashboard_index"],
        ["latest_export_at", "latest_batch_at", "latest_dataset_activity"],
        warning="Release figures come from the export snapshot; batch and coverage figures from newer pipeline artifacts.",
    ),
}


def _resolve_source_key(key: str, data: Any) -> list[str]:
    build_root = getattr(data, "build_root", Path("."))
    scan_dir = getattr(data, "scan_dir", Path("."))
    source_map: dict[str, list[str]] = {
        "release_db": [str(getattr(data, "db_path", build_root / "pharmaguide_core.db"))],
        "export_manifest": [str(build_root / "export_manifest.json")],
        "export_audit": [str(build_root / "export_audit_report.json")],
        "detail_index": [str(build_root / "detail_index.json")],
        "detail_blobs": [str(getattr(data, "detail_blobs_dir", build_root / "detail_blobs"))],
        "processing_state": [str(scan_dir / "logs" / "processing_state.json")],
        "batch_logs": [str(scan_dir / "logs")],
        "dataset_outputs": [str(scan_dir / "output_*")],
        "build_history": [str(build_root.parent)],
        "dashboard_index": [str(Path("scripts/.cache/dashboard").resolve())],
        "scored_outputs": [str(scan_dir / "output_*_scored" / "scored")],
        "canaries": [str(Path("scripts/data/canary_products.json").resolve())],
        "caers": [str(Path("scripts/data/caers_adverse_event_signals.json").resolve())],
        # The production v4 configs that config_registry fingerprints.
        "scoring_config": [
            str(Path("scripts/scoring_v4/config/quality_score.json").resolve()),
            str(Path("scripts/data/omega_rubric.json").resolve()),
        ],
    }
    return source_map.get(key, [key])


def _latest_dataset_activity(data: Any) -> datetime | None:
    candidates = [
        getattr(data, "latest_enriched_at", None),
        getattr(data, "latest_scored_at", None),
    ]
    real = [value for value in candidates if value is not None]
    return max(real) if real else None


def _resolve_freshness_value(field: str, data: Any) -> datetime | None:
    if field == "latest_dataset_activity":
        return _latest_dataset_activity(data)
    return getattr(data, field, None)


def _freshness_label(field: str) -> str:
    labels = {
        "latest_export_at": "Last export",
        "latest_batch_at": "Last batch activity",
        "latest_dataset_activity": "Latest dataset activity",
        "latest_enriched_at": "Latest enriched",
        "latest_scored_at": "Latest scored",
    }
    return labels.get(field, field.replace("_", " ").title())


def _should_warn_about_mixed_planes(meta: dict[str, Any], data: Any) -> bool:
    if not meta.get("mixed_plane_warning"):
        return False
    if len(meta.get("data_planes", [])) <= 1:
        return False

    timestamps = [
        _resolve_freshness_value(field, data)
        for field in meta.get("freshness_fields", [])
    ]
    real_timestamps = [value for value in timestamps if value is not None]
    if len(real_timestamps) < 2:
        return True

    return len(set(real_timestamps)) > 1


def get_page_meta(page_slug: str, data: Any) -> dict[str, Any]:
    base = deepcopy(PAGE_META[page_slug])
    resolved_sources: list[str] = []
    for source_key in base["source_paths"]:
        for path in _resolve_source_key(source_key, data):
            if path not in resolved_sources:
                resolved_sources.append(path)
    freshness_display = []
    for field in base["freshness_fields"]:
        value = _resolve_freshness_value(field, data)
        freshness_display.append(
            {
                "label": _freshness_label(field),
                "value": format_dashboard_datetime(value, style="full"),
            }
        )
    base["source_paths"] = resolved_sources
    base["freshness_display"] = freshness_display
    base["show_mixed_plane_warning"] = _should_warn_about_mixed_planes(base, data)
    return base
