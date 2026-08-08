#!/usr/bin/env python3
"""Capture and diff serving-frequency state across a pipeline run.

Why this exists: the 2026-08-06 serving-frequency incident produced a threshold
flip count that could never be reproduced. Two reasons, both avoidable.

  1. The replay walked stored structures recursively and re-entered the same
     `thresholds_checked` node through several paths, counting one evaluation
     ~6x. This keys every entry instead, so a duplicate is impossible.
  2. `scripts/products/` is gitignored, so re-running the enricher destroyed the
     "before" state. Capture BEFORE you re-run the stage that overwrites it.

Usage:
    python3 scripts/audits/serving_frequency_audit.py capture  before.json
    # ... run: bash batch_run_all_datasets.sh --stages enrich,score
    python3 scripts/audits/serving_frequency_audit.py capture  after.json
    python3 scripts/audits/serving_frequency_audit.py diff     before.json after.json

Write the snapshots OUTSIDE the repo — they are megabytes of derived state.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import Counter
from typing import Any, Dict, Iterator, List, Tuple

SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPTS_DIR)

from serving_frequency import resolve_daily_serving_range  # noqa: E402

ENRICHED_GLOB = os.path.join(
    SCRIPTS_DIR, "products", "output_*_enriched", "enriched", "*.json"
)


def _records() -> Iterator[Tuple[str, Dict[str, Any]]]:
    for path in sorted(glob.glob(ENRICHED_GLOB)):
        try:
            payload = json.load(open(path))
        except (json.JSONDecodeError, OSError):
            continue
        rows = payload if isinstance(payload, list) else payload.get("products") or []
        if isinstance(rows, dict):
            rows = list(rows.values())
        for row in rows:
            if isinstance(row, dict):
                yield path, row


def _threshold_key(
    dsld_id: str,
    rule_id: Any,
    ingredient: Any,
    condition: Any,
    threshold: Dict[str, Any],
    *,
    ingredient_row_id: Any,
) -> str:
    """Stable identity for one evaluated threshold.

    product + rule + ingredient + condition + basis + the threshold's own terms.
    Deliberately NOT positional — a rules-file edit reorders indices, and an
    index-keyed diff would then report spurious changes.
    """
    return "|".join(
        str(part)
        for part in (
            dsld_id,
            rule_id,
            ingredient,
            condition,
            threshold.get("basis"),
            threshold.get("comparator"),
            threshold.get("threshold_value"),
            threshold.get("threshold_unit"),
            ingredient_row_id,
        )
    )


def capture(out_path: str) -> None:
    products: Dict[str, Any] = {}
    thresholds: Dict[str, Any] = {}
    seen_paths: Dict[str, float] = {}

    for path, record in _records():
        dsld_id = str(record.get("dsld_id") or "")
        if not dsld_id:
            continue
        if path not in seen_paths:
            seen_paths[path] = os.path.getmtime(path)

        basis = record.get("serving_basis") or {}
        resolved = resolve_daily_serving_range(record)
        products[dsld_id] = {
            "min": basis.get("min_servings_per_day"),
            "max": basis.get("max_servings_per_day"),
            "basis_reason": basis.get("basis_reason"),
            "source": basis.get("servings_per_day_source"),
            "resolved_min": resolved[0],
            "resolved_max": resolved[1],
            "resolved_defaulted": resolved[2],
            "batch": os.path.relpath(path, SCRIPTS_DIR),
        }

        ingredient_rows = (record.get("ingredient_quality_data") or {}).get(
            "ingredients"
        ) or []
        for ingredient_index, ingredient in enumerate(ingredient_rows):
            if not isinstance(ingredient, dict):
                continue
            name = ingredient.get("canonical_id") or ingredient.get("name")
            row_id = (
                ingredient.get("raw_source_path")
                or ingredient.get("source_label_key")
                or f"ingredient_index:{ingredient_index}"
            )
            for hit in ingredient.get("safety_hits") or []:
                if not isinstance(hit, dict):
                    continue
                for condition_hit in hit.get("condition_hits") or []:
                    if not isinstance(condition_hit, dict):
                        continue
                    evaluation = condition_hit.get("dose_threshold_evaluation") or {}
                    rule = evaluation.get("decision_rule") or {}
                    for threshold in evaluation.get("thresholds_checked") or []:
                        if not isinstance(threshold, dict):
                            continue
                        key = _threshold_key(
                            dsld_id,
                            hit.get("rule_id"),
                            name,
                            condition_hit.get("condition_id"),
                            threshold,
                            ingredient_row_id=row_id,
                        )
                        # An identical duplicate is harmless; a conflicting one
                        # means the identity surface is still incomplete and a
                        # before/after comparison would be unsafe.
                        payload = {
                            "evaluated": threshold.get("evaluated"),
                            "amount": threshold.get("computed_amount"),
                            "unit": threshold.get("computed_unit"),
                            "matched": threshold.get("matched"),
                            "disposition": evaluation.get("consumer_disposition"),
                            "severity": evaluation.get("clinical_severity"),
                            "if_met": rule.get("consumer_disposition_if_met"),
                            "if_not_met": rule.get("consumer_disposition_if_not_met"),
                        }
                        prior = thresholds.get(key)
                        if prior is not None and prior != payload:
                            raise RuntimeError(
                                "serving-frequency audit key collision for "
                                f"{key!r}; distinct evaluations cannot be compared safely"
                            )
                        thresholds[key] = payload

    snapshot = {
        "_meta": {
            "products": len(products),
            "threshold_entries": len(thresholds),
            "batch_files": len(seen_paths),
            "batch_mtimes": {
                os.path.relpath(p, SCRIPTS_DIR): m for p, m in sorted(seen_paths.items())
            },
        },
        "products": products,
        "thresholds": thresholds,
    }
    with open(out_path, "w") as handle:
        json.dump(snapshot, handle)

    print(f"captured {len(products)} products, {len(thresholds)} threshold entries")
    print(f"  -> {out_path}")
    spread = sorted(seen_paths.values())
    if spread and spread[-1] - spread[0] > 3600:
        print(
            "  WARNING: batch mtimes span >1h — this corpus may be MIXED "
            "(some batches written by a different code revision). Check "
            "_meta.batch_mtimes before trusting a before/after diff."
        )


def diff(before_path: str, after_path: str) -> None:
    before = json.load(open(before_path))
    after = json.load(open(after_path))

    moved = []
    for dsld_id, was in before["products"].items():
        now = after["products"].get(dsld_id)
        if not now:
            continue
        if (was["resolved_min"], was["resolved_max"]) != (
            now["resolved_min"],
            now["resolved_max"],
        ):
            moved.append((dsld_id, was, now))

    flips = []
    for key, was in before["thresholds"].items():
        now = after["thresholds"].get(key)
        if not now or not was.get("evaluated") or not now.get("evaluated"):
            continue
        if was.get("matched") != now.get("matched"):
            flips.append((key, was, now))

    print(f"products: {len(before['products'])} -> {len(after['products'])}")
    print(f"threshold entries: {len(before['thresholds'])} -> {len(after['thresholds'])}")
    print(f"\nresolved serving range CHANGED: {len(moved)} products")
    for dsld_id, was, now in moved[:10]:
        print(
            f"   {dsld_id}: ({was['resolved_min']}, {was['resolved_max']}) -> "
            f"({now['resolved_min']}, {now['resolved_max']})  reason={now['basis_reason']}"
        )
    if len(moved) > 10:
        print(f"   ... and {len(moved) - 10} more")

    print(f"\nthreshold decision FLIPS: {len(flips)}")
    directions = Counter()
    for _, was, now in flips:
        directions[
            f"{was.get('disposition')} -> {now.get('disposition')}"
        ] += 1
    for direction, count in directions.most_common():
        print(f"   {direction}: {count}")
    print(f"distinct products with a flip: {len({k.split('|')[0] for k, _, _ in flips})}")
    for key, was, now in flips[:10]:
        parts = key.split("|")
        print(
            f"   {parts[0]} {parts[1]} {parts[3]}: {was['amount']} -> {now['amount']} "
            f"{now['unit']} vs {parts[6]}  [{was.get('disposition')} -> {now.get('disposition')}]"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    capture_parser = sub.add_parser("capture")
    capture_parser.add_argument("out")
    diff_parser = sub.add_parser("diff")
    diff_parser.add_argument("before")
    diff_parser.add_argument("after")
    args = parser.parse_args()

    if args.mode == "capture":
        capture(args.out)
    else:
        diff(args.before, args.after)


if __name__ == "__main__":
    main()
