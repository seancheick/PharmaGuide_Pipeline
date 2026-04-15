#!/usr/bin/env python3
"""
Review-only Valyu evidence watchtower for PharmaGuide.

This tool scans selected canonical source domains and emits review reports.
It never mutates production source-of-truth JSON.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_ROOT.parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import env_loader  # noqa: F401
from api_audit.valyu_domain_targets import load_targets
from api_audit.valyu_query_planner import build_search_plan
from api_audit.valyu_report_types import normalize_signal_row
from api_audit.valyu_report_writer import write_reports


VALID_MODES = (
    "clinical-refresh",
    "iqm-gap-scan",
    "harmful-refresh",
    "recall-refresh",
    "all",
)


def _require_valyu_api_key() -> str:
    api_key = os.environ.get("VALYU_API_KEY")
    if not api_key:
        raise SystemExit("VALYU_API_KEY is required for Valyu watchtower runs.")
    return api_key


def _load_valyu_class():
    try:
        from valyu import Valyu
    except ImportError as exc:  # pragma: no cover - exercised via tests
        raise SystemExit("Valyu SDK not found. Install with: pip install valyu") from exc
    return Valyu


def create_valyu_client():
    api_key = _require_valyu_api_key()
    valyu_class = _load_valyu_class()
    return valyu_class(api_key=api_key)


def execute_search(client: Any, plan: dict[str, Any]) -> dict[str, Any]:
    response = client.search(
        query=plan["query_used"],
        included_sources=plan["included_sources"],
        start_date=plan["start_date"],
        end_date=plan["end_date"],
    )
    success = getattr(response, "success", True)
    if isinstance(response, dict):
        success = response.get("success", success)
    if not success:
        error = getattr(response, "error", None)
        if isinstance(response, dict):
            error = response.get("error", error)
        return {"search_results": [], "error": error or "Valyu search failed"}

    results = getattr(response, "results", None)
    if results is None:
        results = getattr(response, "search_results", None)
    if results is None and isinstance(response, dict):
        results = response.get("results")
    if results is None and isinstance(response, dict):
        results = response.get("search_results", [])
    results = results or []

    normalized_results = []
    for item in results:
        if isinstance(item, dict):
            normalized_results.append(item)
            continue
        normalized_results.append(
            {
                "title": getattr(item, "title", ""),
                "url": getattr(item, "url", ""),
                "published_date": getattr(item, "publication_date", ""),
                "source": getattr(item, "source", ""),
            }
        )
    return {"search_results": normalized_results}


def classify_signal(target: dict[str, Any], search_payload: dict[str, Any]) -> dict[str, Any] | None:
    results = search_payload.get("search_results", [])
    if not results:
        return None

    domain_key = str(target["domain"]).replace("-", "_")
    if domain_key == "clinical_refresh":
        signal_type = "possible_upgrade"
    elif domain_key == "iqm_gap_scan":
        signal_type = "missing_evidence"
    elif domain_key == "harmful_refresh":
        signal_type = "possible_safety_change"
    else:
        signal_type = "possible_recall_change"

    references = []
    sources = []
    seen_refs: set[tuple[str, str]] = set()
    for item in results[:5]:
        source = str(item.get("source") or item.get("url") or "")
        if source:
            sources.append(source)
        reference = {
            "title": str(item.get("title") or ""),
            "url": str(item.get("url") or ""),
            "published_date": str(item.get("published_date") or ""),
            "source": str(item.get("source") or ""),
        }
        dedupe_key = (reference["url"], reference["title"])
        if dedupe_key in seen_refs:
            continue
        seen_refs.add(dedupe_key)
        references.append(reference)

    return normalize_signal_row(
        {
            "domain": domain_key,
            "target_file": target.get("target_file"),
            "entity_type": target.get("entity_type"),
            "entity_id": target.get("entity_id"),
            "entity_name": target.get("entity_name"),
            "signal_type": signal_type,
            "signal_strength": "medium",
            "reason": f"Valyu returned {len(results)} result(s) for review.",
            "query_used": target.get("query_used", ""),
            "date_window": {
                "start_date": target.get("start_date"),
                "end_date": target.get("end_date"),
            },
            "candidate_sources": list(dict.fromkeys(sources)),
            "candidate_references": references,
            "suggested_action": "Review citations before deciding whether canonical data should change.",
            "supporting_summary": "",
        }
    )


def run_mode(mode: str, *, limit: int | None = None, client: Any | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    active_client = client or create_valyu_client()
    targets = []
    if mode == "all":
        for submode in VALID_MODES[:-1]:
            targets.extend(load_targets(submode, limit=limit))
    else:
        targets = load_targets(mode, limit=limit)

    raw_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    for target in targets:
        plan = build_search_plan(target["domain"], target["entity_name"])
        target["query_used"] = plan["query_used"]
        target["start_date"] = plan["start_date"]
        target["end_date"] = plan["end_date"]
        payload = execute_search(active_client, plan)
        raw_rows.append({"target": target, "search": payload})
        classified = classify_signal(target, payload)
        if classified:
            review_rows.append(classified)

    metadata = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "targets_scanned": len(targets),
    }
    raw_report = {
        "metadata": metadata,
        "raw_results": raw_rows,
    }
    return raw_report, review_rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Review-only Valyu evidence watchtower for PharmaGuide",
    )
    parser.add_argument("mode", choices=VALID_MODES)
    parser.add_argument("--limit", type=int, default=None, help="Optional target limit per selected mode")
    parser.add_argument("--output-dir", type=str, default=None, help="Optional report output directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    raw_report, review_rows = run_mode(args.mode, limit=args.limit)
    metadata = raw_report["metadata"]
    output_dir = Path(args.output_dir) if args.output_dir else None
    paths = write_reports(metadata, raw_report, review_rows, output_dir=output_dir)
    print(f"Scanned {metadata['targets_scanned']} target(s); queued {len(review_rows)} review row(s).")
    print(f"Summary: {paths['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
