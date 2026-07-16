#!/usr/bin/env python3
"""Stage-3 batch owner for v4-native scored artifacts.

The CLI owns file discovery and atomic writes only. Product scoring and artifact
assembly live in ``scoring_v4.scored_artifact.build_scored_artifact``.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from run_artifacts import atomic_write_json, ensure_run_id, report_run_directory
from scoring_v4.scored_artifact import (
    SCORED_ARTIFACT_SCHEMA_VERSION,
    build_scored_artifact,
)
from stage_manifest import select_stage_input_files


LOGGER = logging.getLogger("pharmaguide.score_products_v4")


def _load_batch(path: Path) -> List[Dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"unreadable enriched batch {path}: {exc}") from exc
    if not isinstance(payload, list) or not payload:
        raise ValueError(f"enriched batch must be a non-empty list: {path}")
    if any(not isinstance(product, dict) for product in payload):
        raise ValueError(f"enriched batch contains a non-object product: {path}")
    ids = [str(product.get("dsld_id") or "").strip() for product in payload]
    if any(not product_id for product_id in ids):
        raise ValueError(f"enriched batch contains a product without dsld_id: {path}")
    duplicates = sorted(product_id for product_id, count in Counter(ids).items() if count > 1)
    if duplicates:
        raise ValueError(f"enriched batch contains duplicate dsld_id values: {duplicates[:5]}")
    return payload


def _output_name(input_path: Path) -> str:
    stem = input_path.stem
    if stem.startswith("enriched_"):
        stem = stem[len("enriched_"):]
    return f"scored_{stem}.json"


def score_file(input_path: Path, scored_dir: Path) -> Dict[str, Any]:
    """Score one complete batch and atomically publish exactly one output."""
    products = _load_batch(input_path)
    artifacts = [build_scored_artifact(product) for product in products]

    scored_dir.mkdir(parents=True, exist_ok=True)
    output_path = scored_dir / _output_name(input_path)
    atomic_write_json(output_path, artifacts)

    statuses = Counter(str(item.get("quality_score_status") or "unknown") for item in artifacts)
    verdicts = Counter(str(item.get("verdict") or "UNKNOWN") for item in artifacts)
    return {
        "input_file": str(input_path),
        "output_file": str(output_path),
        "total_products": len(artifacts),
        "quality_status_distribution": dict(statuses),
        "verdict_distribution": dict(verdicts),
    }


def score_all(input_path: Path, output_dir: Path, *, run_id: str | None = None) -> Dict[str, Any]:
    resolved_input = input_path.resolve()
    if resolved_input.is_file():
        input_files = [resolved_input]
    else:
        input_files = select_stage_input_files(
            resolved_input,
            "enrich",
            patterns=("*.json",),
        )
    if not input_files:
        raise ValueError(f"no enriched JSON files found: {resolved_input}")

    # Validate the complete input set before creating any output. Per-file
    # checks are insufficient because a repeated product in two batches would
    # otherwise become order-dependent last-write-wins data downstream.
    all_ids: Counter[str] = Counter()
    for path in input_files:
        all_ids.update(str(product["dsld_id"]) for product in _load_batch(path))
    cross_batch_duplicates = sorted(
        product_id for product_id, count in all_ids.items() if count > 1
    )
    if cross_batch_duplicates:
        raise ValueError(
            "duplicate dsld_id across enriched batches: "
            f"{cross_batch_duplicates[:5]}"
        )

    effective_run_id = ensure_run_id(run_id)
    scored_dir = output_dir.resolve() / "scored"
    started_at = datetime.now(timezone.utc)
    batches = [score_file(path, scored_dir) for path in input_files]
    summary = {
        "run_id": effective_run_id,
        "scored_artifact_schema_version": SCORED_ARTIFACT_SCHEMA_VERSION,
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "files_processed": len(batches),
        "total_products": sum(batch["total_products"] for batch in batches),
        "batches": batches,
    }
    report_dir = report_run_directory(output_dir.resolve() / "reports", effective_run_id)
    atomic_write_json(report_dir / "scoring_summary.json", summary)
    return summary


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PharmaGuide v4 Stage-3 scorer")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.dry_run:
        LOGGER.info("DRY RUN input=%s output=%s", args.input_dir, args.output_dir)
        return 0
    summary = score_all(Path(args.input_dir), Path(args.output_dir), run_id=args.run_id)
    LOGGER.info("v4 scoring complete: %s products", summary["total_products"])
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        LOGGER.error("v4 scoring failed: %s", exc, exc_info=True)
        raise SystemExit(1)
