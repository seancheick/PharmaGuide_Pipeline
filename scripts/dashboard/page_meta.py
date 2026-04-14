from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.dashboard.time_format import format_dashboard_datetime


PAGE_META: dict[str, dict[str, Any]] = {
    "command-center": {
        "page_title": "Command Center",
        "page_summary": "See release readiness, current pipeline activity, freshness gaps, and the fastest paths to action.",
        "data_planes": ["Release Snapshot", "Pipeline Logs", "Dataset Outputs"],
        "source_paths": ["release_db", "export_manifest", "export_audit", "processing_state", "batch_logs", "dataset_outputs"],
        "freshness_fields": ["latest_export_at", "latest_batch_at", "latest_dataset_activity"],
        "mixed_plane_warning": "This page blends released export data with newer pipeline and dataset activity.",
        "related_views": ["Pipeline Health", "Observability", "Data Quality", "Intelligence"],
        "usage_notes": [
            "Start here for the overall story before drilling into a specific page.",
            "Compare release freshness against pipeline freshness before trusting mixed metrics.",
        ],
    },
    "product-inspector": {
        "page_title": "Product Inspector",
        "page_summary": "Inspect one product, why it scored that way, and where supporting detail data came from.",
        "data_planes": ["Release Snapshot", "Dataset Outputs"],
        "source_paths": ["release_db", "detail_blobs", "detail_index", "dataset_outputs"],
        "freshness_fields": ["latest_export_at", "latest_dataset_activity"],
        "mixed_plane_warning": "Inspector scoring comes from the release snapshot, while source lookup paths may point to newer dataset outputs.",
        "related_views": ["Data Quality", "Intelligence", "Release Diff"],
        "usage_notes": [
            "Search by DSLD ID, product name, brand, or UPC.",
            "Use the detailed score trace to explain bonuses and penalties.",
        ],
    },
    "pipeline-health": {
        "page_title": "Pipeline Health",
        "page_summary": "Answer whether the current release and the latest run are healthy enough to trust and ship.",
        "data_planes": ["Release Snapshot", "Pipeline Logs", "Dataset Outputs"],
        "source_paths": ["export_manifest", "export_audit", "processing_state", "batch_logs", "dataset_outputs"],
        "freshness_fields": ["latest_export_at", "latest_batch_at", "latest_dataset_activity"],
        "mixed_plane_warning": "Release gate status uses the export snapshot, while run status and dataset coverage come from newer pipeline artifacts.",
        "related_views": ["Command Center", "Observability", "Data Quality"],
        "usage_notes": [
            "Read the release gate first, then confirm the latest batch and artifact coverage agree.",
            "Treat stale export dates as a caution, even if the latest batch is fresh.",
        ],
    },
    "data-quality": {
        "page_title": "Data Quality",
        "page_summary": "Find not-scored products, unmapped hotspots, fallback queues, and coverage issues by dataset.",
        "data_planes": ["Release Snapshot", "Dataset Outputs"],
        "source_paths": ["release_db", "dataset_outputs", "scoring_config"],
        "freshness_fields": ["latest_export_at", "latest_dataset_activity"],
        "mixed_plane_warning": "Quality combines release snapshot scoring outcomes with newer dataset-output diagnostics.",
        "related_views": ["Product Inspector", "Pipeline Health", "Observability"],
        "usage_notes": [
            "Use dataset scope to isolate a brand or run family.",
            "Quality diagnostics may be fresher than the currently exported DB.",
        ],
    },
    "observability": {
        "page_title": "Observability",
        "page_summary": "Track integrity, failures, drift, bottlenecks, and operational signals across builds and batch logs.",
        "data_planes": ["Release Snapshot", "Pipeline Logs", "Dataset Outputs"],
        "source_paths": ["export_manifest", "export_audit", "release_db", "batch_logs", "dataset_outputs", "build_history"],
        "freshness_fields": ["latest_export_at", "latest_batch_at", "latest_dataset_activity"],
        "mixed_plane_warning": "Observability intentionally compares older release data with newer pipeline and dataset activity to surface drift and failures.",
        "related_views": ["Pipeline Health", "Batch Diff", "Command Center"],
        "usage_notes": [
            "Use this page to explain losses between enrichment, scoring, and export.",
            "If timelines disagree, trust the source chips and freshness panel before interpreting trends.",
        ],
    },
    "release-diff": {
        "page_title": "Release Diff",
        "page_summary": "Compare two release snapshots to understand score changes, verdict shifts, and build deltas.",
        "data_planes": ["Release Snapshot"],
        "source_paths": ["build_history", "release_db", "export_manifest"],
        "freshness_fields": ["latest_export_at"],
        "mixed_plane_warning": "",
        "related_views": ["Product Inspector", "Intelligence", "Command Center"],
        "usage_notes": [
            "Use this for release-to-release comparison, not live pipeline debugging.",
        ],
    },
    "batch-diff": {
        "page_title": "Batch Diff",
        "page_summary": "Compare recent pipeline runs to see dataset-level status changes and failure movement.",
        "data_planes": ["Pipeline Logs"],
        "source_paths": ["batch_logs", "processing_state"],
        "freshness_fields": ["latest_batch_at"],
        "mixed_plane_warning": "",
        "related_views": ["Observability", "Pipeline Health", "Command Center"],
        "usage_notes": [
            "Use this for run-to-run comparison within the current pipeline activity timeline.",
        ],
    },
    "intelligence": {
        "page_title": "Intelligence",
        "page_summary": "Explore product, ingredient, and brand intelligence derived from the current release snapshot and detail blobs.",
        "data_planes": ["Release Snapshot"],
        "source_paths": ["release_db", "detail_blobs", "detail_index"],
        "freshness_fields": ["latest_export_at"],
        "mixed_plane_warning": "",
        "related_views": ["Product Inspector", "Release Diff", "Command Center"],
        "usage_notes": [
            "Use this page for cross-product insights, not pipeline run diagnosis.",
        ],
    },
    "section-a-audit": {
        "page_title": "Section A Audit",
        "page_summary": "Deep-dive into ingredient quality (Section A) scoring: low-scoring products, probiotic CFU detection, and IQM coverage gaps.",
        "data_planes": ["Release Snapshot", "Dataset Outputs"],
        "source_paths": ["release_db", "dataset_outputs"],
        "freshness_fields": ["latest_export_at", "latest_dataset_activity"],
        "mixed_plane_warning": "Section A audit combines release snapshot scores with dataset-level ingredient detail.",
        "related_views": ["Data Quality", "Section B Audit", "Product Inspector"],
        "usage_notes": [
            "Use audit filters to isolate brands or categories with low Section A scores.",
            "Check probiotic CFU detection rates if supplement type includes probiotics.",
        ],
    },
    "section-b-audit": {
        "page_title": "Section B Audit",
        "page_summary": "Safety and purity audit: banned substances, recalled ingredients, harmful additives, allergen risks, and dose safety analysis.",
        "data_planes": ["Release Snapshot"],
        "source_paths": ["release_db"],
        "freshness_fields": ["latest_export_at"],
        "mixed_plane_warning": "",
        "related_views": ["Section A Audit", "Section C Audit", "Data Quality"],
        "usage_notes": [
            "Use safety flag filters to isolate products with specific risk types.",
            "Check the blocked/unsafe tab for products that failed the safety gate.",
        ],
    },
    "section-c-audit": {
        "page_title": "Section C Audit",
        "page_summary": "Evidence and research audit: clinical backing coverage, zero-evidence products, and evidence strength gaps by brand and type.",
        "data_planes": ["Release Snapshot"],
        "source_paths": ["release_db"],
        "freshness_fields": ["latest_export_at"],
        "mixed_plane_warning": "",
        "related_views": ["Section A Audit", "Section D Audit", "Intelligence"],
        "usage_notes": [
            "Focus on SAFE products with zero evidence — these are the best candidates for clinical study enrichment.",
            "Compare evidence coverage across supplement types to prioritize research investment.",
        ],
    },
    "caers-audit": {
        "page_title": "CAERS Audit",
        "page_summary": "FDA CAERS pharmacovigilance audit: adverse event signals, outcome breakdowns, cross-reference with banned/recalled, and B8 scoring impact.",
        "data_planes": ["Pipeline Data"],
        "source_paths": ["caers_signals"],
        "freshness_fields": [],
        "mixed_plane_warning": "",
        "related_views": ["Section B Audit", "Intelligence"],
        "usage_notes": [
            "Cross-Reference tab shows ingredients with CAERS signals NOT in banned/recalled — review candidates.",
            "B8 Scoring Impact shows how CAERS penalties affect product scores.",
            "Reaction Analysis surfaces the most commonly reported adverse reactions.",
        ],
    },
    "section-d-audit": {
        "page_title": "Section D Audit",
        "page_summary": "Brand trust audit: manufacturer reputation, third-party testing, full disclosure, and certification gap analysis.",
        "data_planes": ["Release Snapshot"],
        "source_paths": ["release_db"],
        "freshness_fields": ["latest_export_at"],
        "mixed_plane_warning": "",
        "related_views": ["Section B Audit", "Section C Audit", "Intelligence"],
        "usage_notes": [
            "Use trust gaps tab to find SAFE products that could score higher with better manufacturer data.",
            "Brand leaderboard shows which manufacturers have the strongest trust signals.",
        ],
    },
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
        "scoring_config": [str(Path("scripts/config/scoring_config.json").resolve())],
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
