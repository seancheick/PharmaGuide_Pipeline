#!/usr/bin/env python3
"""Shadow Score Comparison — Phase 0 validation harness.

Runs a scoring change in parallel with the current scorer and reports deltas.
Used to validate that architectural changes (e.g., Section E → category bonus)
don't introduce unexpected score shifts.

Usage:
    python3 shadow_score_comparison.py <enriched_dir> [--threshold 3.0]

Outputs:
    - Per-product delta report (old_score, new_score, delta)
    - Aggregate stats: % affected, avg/max delta, verdict changes
    - Category-specific breakdowns
"""

import argparse
import importlib.util
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple, Type


def load_enriched_products(enriched_dir: str) -> List[Dict[str, Any]]:
    """Load all enriched product JSON files from a directory."""
    products = []
    target = Path(enriched_dir)
    if not target.exists():
        print(f"Error: directory {enriched_dir} not found")
        sys.exit(1)

    for fpath in sorted(target.glob("*.json")):
        try:
            with open(fpath) as f:
                data = json.load(f)
            if isinstance(data, list):
                products.extend(data)
            elif isinstance(data, dict):
                if "products" in data:
                    products.extend(data["products"])
                else:
                    products.append(data)
        except (json.JSONDecodeError, IOError) as exc:
            print(f"  Skipping {fpath.name}: {exc}")
    return products


def compare_scores(
    old_results: List[Dict[str, Any]],
    new_results: List[Dict[str, Any]],
    threshold: float = 3.0,
) -> Dict[str, Any]:
    """Compare old vs new scored products and produce a delta report."""
    old_by_id = {r.get("dsld_id"): r for r in old_results if r.get("dsld_id")}
    new_by_id = {r.get("dsld_id"): r for r in new_results if r.get("dsld_id")}

    common_ids = sorted(set(old_by_id) & set(new_by_id))
    deltas = []
    verdict_changes = []
    category_deltas = defaultdict(list)

    for pid in common_ids:
        old = old_by_id[pid]
        new = new_by_id[pid]

        old_score = old.get("score_100_equivalent")
        new_score = new.get("score_100_equivalent")
        old_verdict = old.get("verdict")
        new_verdict = new.get("verdict")

        # Skip unscored products
        if old_score is None and new_score is None:
            continue

        old_s = old_score or 0.0
        new_s = new_score or 0.0
        delta = round(new_s - old_s, 2)

        record = {
            "dsld_id": pid,
            "product_name": old.get("product_name", ""),
            "old_score_100": round(old_s, 2),
            "new_score_100": round(new_s, 2),
            "delta": delta,
            "old_verdict": old_verdict,
            "new_verdict": new_verdict,
            "verdict_changed": old_verdict != new_verdict,
        }
        deltas.append(record)

        if old_verdict != new_verdict:
            verdict_changes.append(record)

        category = old.get("supp_type", "unknown")
        category_deltas[category].append(delta)

    # Aggregate stats
    all_deltas = [d["delta"] for d in deltas]
    nonzero = [d for d in all_deltas if d != 0.0]
    over_threshold = [d for d in all_deltas if abs(d) > threshold]

    total = len(all_deltas)
    report = {
        "summary": {
            "total_products_compared": total,
            "products_affected": len(nonzero),
            "pct_affected": round(len(nonzero) / max(total, 1) * 100, 2),
            "products_over_threshold": len(over_threshold),
            "pct_over_threshold": round(len(over_threshold) / max(total, 1) * 100, 2),
            "threshold_used": threshold,
            "avg_delta": round(sum(all_deltas) / max(total, 1), 4),
            "max_delta": round(max(all_deltas, default=0.0), 2),
            "min_delta": round(min(all_deltas, default=0.0), 2),
            "verdict_changes": len(verdict_changes),
        },
        "category_breakdown": {},
        "verdict_changes": verdict_changes,
        "largest_shifts": sorted(deltas, key=lambda d: abs(d["delta"]), reverse=True)[:20],
    }

    for cat, cat_deltas in sorted(category_deltas.items()):
        nonzero_cat = [d for d in cat_deltas if d != 0.0]
        report["category_breakdown"][cat] = {
            "total": len(cat_deltas),
            "affected": len(nonzero_cat),
            "avg_delta": round(sum(cat_deltas) / max(len(cat_deltas), 1), 4),
            "max_delta": round(max(cat_deltas, default=0.0), 2),
            "min_delta": round(min(cat_deltas, default=0.0), 2),
        }

    return report


def check_rollout_gate(report: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Evaluate whether the shadow comparison passes the rollout gate.

    Gate criteria:
    - Zero unintentional verdict changes
    - < 5% of products shift more than threshold points
    """
    issues = []
    summary = report["summary"]

    if summary["verdict_changes"] > 0:
        issues.append(
            f"FAIL: {summary['verdict_changes']} verdict change(s) detected — "
            "review each before proceeding"
        )

    if summary["pct_over_threshold"] >= 5.0:
        issues.append(
            f"FAIL: {summary['pct_over_threshold']}% of products shifted > "
            f"{summary['threshold_used']} pts (gate requires < 5%)"
        )

    passed = len(issues) == 0
    if passed:
        issues.append(
            f"PASS: {summary['pct_affected']}% affected, "
            f"avg delta {summary['avg_delta']}, "
            f"max delta {summary['max_delta']}, "
            f"0 verdict changes"
        )
    return passed, issues


def _resolve_module_path(module_path: str) -> Path:
    candidate = Path(module_path)
    if not candidate.is_absolute():
        candidate = (Path(__file__).parent / candidate).resolve()
    return candidate


def validate_shadow_pair(
    baseline_module: str,
    candidate_module: str,
    baseline_config: str = "",
    candidate_config: str = "",
) -> Tuple[Path, Path]:
    baseline_path = _resolve_module_path(baseline_module)
    candidate_path = _resolve_module_path(candidate_module)
    same_module = baseline_path == candidate_path
    same_config = (baseline_config or "") == (candidate_config or "")
    if same_module and same_config:
        raise ValueError(
            "Baseline and candidate scorers are identical. "
            "Provide --baseline-module or --baseline-config for a real shadow comparison."
        )
    return baseline_path, candidate_path


def load_scorer_class(module_path: Path, class_name: str) -> Type[Any]:
    spec = importlib.util.spec_from_file_location(f"shadow_{module_path.stem}_{hash(module_path)}", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load scorer module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    scorer_cls = getattr(module, class_name, None)
    if scorer_cls is None:
        raise AttributeError(f"Class {class_name} not found in {module_path}")
    return scorer_cls


def main():
    parser = argparse.ArgumentParser(description="Shadow Score Comparison")
    parser.add_argument("enriched_dir", help="Directory of enriched product JSON files")
    parser.add_argument("--threshold", type=float, default=3.0,
                        help="Point threshold for flagging large shifts (default: 3.0)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output JSON report path (default: stdout summary)")
    parser.add_argument(
        "--baseline-module",
        type=str,
        required=True,
        help="Path to the baseline scorer Python module (for example, a pre-change scorer copy).",
    )
    parser.add_argument(
        "--candidate-module",
        type=str,
        default="score_supplements.py",
        help="Path to the candidate scorer Python module (default: current score_supplements.py).",
    )
    parser.add_argument("--baseline-class", type=str, default="SupplementScorer")
    parser.add_argument("--candidate-class", type=str, default="SupplementScorer")
    parser.add_argument("--baseline-config", type=str, default=None)
    parser.add_argument("--candidate-config", type=str, default=None)
    args = parser.parse_args()

    try:
        baseline_path, candidate_path = validate_shadow_pair(
            args.baseline_module,
            args.candidate_module,
            args.baseline_config or "",
            args.candidate_config or "",
        )
        baseline_cls = load_scorer_class(baseline_path, args.baseline_class)
        candidate_cls = load_scorer_class(candidate_path, args.candidate_class)
    except (ValueError, ImportError, AttributeError) as exc:
        parser.error(str(exc))

    print(f"Loading enriched products from {args.enriched_dir}...")
    products = load_enriched_products(args.enriched_dir)
    print(f"Loaded {len(products)} products")

    if not products:
        print("No products found. Exiting.")
        sys.exit(1)

    print(f"Scoring with baseline scorer: {baseline_path}...")
    scorer_old = baseline_cls(config_path=args.baseline_config) if args.baseline_config else baseline_cls()
    old_results = [scorer_old.score_product(p) for p in products]

    print(f"Scoring with candidate scorer: {candidate_path}...")
    scorer_new = candidate_cls(config_path=args.candidate_config) if args.candidate_config else candidate_cls()
    new_results = [scorer_new.score_product(p) for p in products]

    # Compare
    print(f"\nComparing {len(products)} products (threshold: {args.threshold} pts)...\n")
    report = compare_scores(old_results, new_results, threshold=args.threshold)
    passed, gate_messages = check_rollout_gate(report)

    # Print summary
    s = report["summary"]
    print("=" * 60)
    print("SHADOW COMPARISON REPORT")
    print("=" * 60)
    print(f"Products compared:    {s['total_products_compared']}")
    print(f"Products affected:    {s['products_affected']} ({s['pct_affected']}%)")
    print(f"Over {args.threshold}-pt threshold: {s['products_over_threshold']} ({s['pct_over_threshold']}%)")
    print(f"Avg delta:            {s['avg_delta']}")
    print(f"Max delta:            {s['max_delta']}")
    print(f"Min delta:            {s['min_delta']}")
    print(f"Verdict changes:      {s['verdict_changes']}")
    print()

    if report["category_breakdown"]:
        print("Category breakdown:")
        for cat, stats in report["category_breakdown"].items():
            if stats["affected"] > 0:
                print(f"  {cat}: {stats['affected']}/{stats['total']} affected, "
                      f"avg={stats['avg_delta']}, max={stats['max_delta']}")
        print()

    print("ROLLOUT GATE:")
    for msg in gate_messages:
        print(f"  {msg}")

    if args.output:
        report["rollout_gate"] = {"passed": passed, "messages": gate_messages}
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nFull report saved to {args.output}")


if __name__ == "__main__":
    main()
