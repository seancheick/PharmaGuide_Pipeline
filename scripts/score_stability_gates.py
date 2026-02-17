#!/usr/bin/env python3
"""
Score Stability Gates
=====================
Checks score distribution drift and caution-trigger drift between two scored runs.

Usage:
  python score_stability_gates.py --baseline-dir path/to/baseline --current-dir path/to/current --format lozenge
  python score_stability_gates.py --baseline-dir ... --current-dir ... --expected-change expected_change.json
"""

import argparse
import json
import sys
from pathlib import Path
from statistics import mean
from typing import Dict, List, Tuple


def _load_scored_products(path: Path) -> List[Dict]:
    products: List[Dict] = []
    for file_path in sorted(path.glob("*.json")):
        with open(file_path, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                products.extend(data)
            else:
                products.append(data)
    for file_path in sorted(path.glob("*.jsonl")):
        with open(file_path, "r") as f:
            for line in f:
                if line.strip():
                    products.append(json.loads(line))
    return products


def _percentile(sorted_values: List[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * pct
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def _score_metrics(products: List[Dict]) -> Dict:
    scores = [p.get("score_80") for p in products if p.get("score_80") is not None]
    scores_sorted = sorted(scores)
    metrics = {
        "count": len(scores),
        "mean": round(mean(scores), 2) if scores else 0.0,
        "p10": round(_percentile(scores_sorted, 0.10), 2),
        "p50": round(_percentile(scores_sorted, 0.50), 2),
        "p90": round(_percentile(scores_sorted, 0.90), 2),
    }
    return metrics


def _trigger_rates(products: List[Dict]) -> Tuple[Dict[str, int], Dict[str, float]]:
    trigger_counts: Dict[str, int] = {}
    total = len(products) or 1
    for product in products:
        triggers = product.get("scoring_metadata", {}).get("caution_triggers", []) or []
        for trigger in triggers:
            trigger_counts[trigger] = trigger_counts.get(trigger, 0) + 1
    trigger_rates = {
        trigger: round(count / total * 100.0, 2) for trigger, count in trigger_counts.items()
    }
    return trigger_counts, trigger_rates


def _immediate_fail_metrics(products: List[Dict]) -> Dict[str, float]:
    total = len(products) or 1
    count = 0
    for product in products:
        meta = product.get("scoring_metadata", {}) or {}
        if meta.get("immediate_fail"):
            count += 1
    return {
        "count": count,
        "rate": round(count / total * 100.0, 2)
    }


def _unsafe_metrics(products: List[Dict]) -> Dict[str, float]:
    total = len(products) or 1
    count = 0
    for product in products:
        if product.get("safety_verdict") == "UNSAFE":
            count += 1
    return {
        "count": count,
        "rate": round(count / total * 100.0, 2)
    }


def _top_triggers(trigger_rates: Dict[str, float], limit: int = 20) -> List[str]:
    return [t for t, _ in sorted(trigger_rates.items(), key=lambda x: (-x[1], x[0]))[:limit]]


def main() -> int:
    parser = argparse.ArgumentParser(description="Score stability gate checks")
    parser.add_argument("--baseline-dir", required=True, help="Baseline scored directory")
    parser.add_argument("--current-dir", required=True, help="Current scored directory")
    parser.add_argument("--format", default="unknown", help="Format name (gummy, lozenge, powder, etc.)")
    parser.add_argument("--score-drift-threshold", type=float, default=1.0,
                        help="Max allowed absolute drift for mean/p10/p50/p90 (default: 1.0)")
    parser.add_argument("--trigger-rate-threshold", type=float, default=2.0,
                        help="Max allowed absolute drift in trigger rates (pp) (default: 2.0)")
    parser.add_argument("--trigger-count-threshold", type=int, default=5,
                        help="Max allowed absolute drift in trigger counts (default: 5)")
    parser.add_argument("--immediate-fail-rate-threshold", type=float, default=1.0,
                        help="Max allowed absolute drift in immediate-fail rate (pp) (default: 1.0)")
    parser.add_argument("--immediate-fail-count-threshold", type=int, default=1,
                        help="Max allowed absolute drift in immediate-fail count (default: 1)")
    parser.add_argument("--unsafe-rate-threshold", type=float, default=1.0,
                        help="Max allowed absolute drift in unsafe rate (pp) (default: 1.0)")
    parser.add_argument("--unsafe-count-threshold", type=int, default=1,
                        help="Max allowed absolute drift in unsafe count (default: 1)")
    parser.add_argument("--min-baseline-count-for-rate", type=int, default=5,
                        help="Minimum baseline count to apply rate drift checks (default: 5)")
    parser.add_argument("--expected-change", help="Path to expected-change file to suppress failure")
    parser.add_argument("--output", default="reports", help="Output directory for gate report")

    args = parser.parse_args()

    baseline_path = Path(args.baseline_dir)
    current_path = Path(args.current_dir)

    baseline_products = _load_scored_products(baseline_path)
    current_products = _load_scored_products(current_path)

    if not baseline_products or not current_products:
        print("Missing baseline or current products - cannot compute stability gates.")
        return 1

    baseline_scores = _score_metrics(baseline_products)
    current_scores = _score_metrics(current_products)

    baseline_trigger_counts, baseline_trigger_rates = _trigger_rates(baseline_products)
    current_trigger_counts, current_trigger_rates = _trigger_rates(current_products)
    baseline_immediate_fail = _immediate_fail_metrics(baseline_products)
    current_immediate_fail = _immediate_fail_metrics(current_products)
    baseline_unsafe = _unsafe_metrics(baseline_products)
    current_unsafe = _unsafe_metrics(current_products)
    baseline_unsafe_non_immediate = {
        "count": max(0, baseline_unsafe["count"] - baseline_immediate_fail["count"]),
        "rate": round(
            max(0, baseline_unsafe["count"] - baseline_immediate_fail["count"]) /
            (len(baseline_products) or 1) * 100.0, 2
        )
    }
    current_unsafe_non_immediate = {
        "count": max(0, current_unsafe["count"] - current_immediate_fail["count"]),
        "rate": round(
            max(0, current_unsafe["count"] - current_immediate_fail["count"]) /
            (len(current_products) or 1) * 100.0, 2
        )
    }

    baseline_top = _top_triggers(baseline_trigger_rates)
    current_top = _top_triggers(current_trigger_rates)
    trigger_union = sorted(set(baseline_top + current_top))

    gate_failures = []
    score_drift = {}
    for key in ["mean", "p10", "p50", "p90"]:
        drift = round(current_scores[key] - baseline_scores[key], 2)
        score_drift[key] = drift
        if abs(drift) > args.score_drift_threshold:
            gate_failures.append(
                f"score_distribution_drift:{key}={drift} (threshold {args.score_drift_threshold})"
            )

    trigger_drift = {}
    for trigger in trigger_union:
        base_rate = baseline_trigger_rates.get(trigger, 0.0)
        curr_rate = current_trigger_rates.get(trigger, 0.0)
        base_count = baseline_trigger_counts.get(trigger, 0)
        curr_count = current_trigger_counts.get(trigger, 0)
        drift = round(curr_rate - base_rate, 2)
        count_drift = curr_count - base_count
        trigger_drift[trigger] = {
            "baseline_rate": base_rate,
            "current_rate": curr_rate,
            "drift": drift,
            "baseline_count": base_count,
            "current_count": curr_count,
            "count_drift": count_drift,
            "rate_applicable": rate_applicable,
        }
        rate_applicable = base_count >= args.min_baseline_count_for_rate
        if rate_applicable:
            trigger_gate = (
                abs(drift) > args.trigger_rate_threshold and
                abs(count_drift) > args.trigger_count_threshold
            )
        else:
            trigger_gate = abs(count_drift) > args.trigger_count_threshold
        if trigger_gate:
            gate_failures.append(
                f"trigger_drift:{trigger}={drift}pp/{count_drift} "
                f"(thresholds {args.trigger_rate_threshold}pp/{args.trigger_count_threshold})"
            )

    immediate_fail_drift = round(
        current_immediate_fail["rate"] - baseline_immediate_fail["rate"], 2
    )
    immediate_fail_count_drift = (
        current_immediate_fail["count"] - baseline_immediate_fail["count"]
    )
    immediate_rate_applicable = (
        baseline_immediate_fail["count"] >= args.min_baseline_count_for_rate
    )
    if immediate_rate_applicable:
        immediate_gate = (
            abs(immediate_fail_drift) > args.immediate_fail_rate_threshold and
            abs(immediate_fail_count_drift) > args.immediate_fail_count_threshold
        )
    else:
        immediate_gate = abs(immediate_fail_count_drift) > args.immediate_fail_count_threshold
    if immediate_gate:
        gate_failures.append(
            f"immediate_fail_rate_drift={immediate_fail_drift}pp/"
            f"{immediate_fail_count_drift} "
            f"(thresholds {args.immediate_fail_rate_threshold}pp/"
            f"{args.immediate_fail_count_threshold})"
        )

    unsafe_drift = round(
        current_unsafe["rate"] - baseline_unsafe["rate"], 2
    )
    unsafe_count_drift = current_unsafe["count"] - baseline_unsafe["count"]
    unsafe_rate_applicable = baseline_unsafe["count"] >= args.min_baseline_count_for_rate
    if unsafe_rate_applicable:
        unsafe_gate = (
            abs(unsafe_drift) > args.unsafe_rate_threshold and
            abs(unsafe_count_drift) > args.unsafe_count_threshold
        )
    else:
        unsafe_gate = abs(unsafe_count_drift) > args.unsafe_count_threshold
    if unsafe_gate:
        gate_failures.append(
            f"unsafe_rate_drift={unsafe_drift}pp/{unsafe_count_drift} "
            f"(thresholds {args.unsafe_rate_threshold}pp/{args.unsafe_count_threshold})"
        )

    expected_change = False
    if args.expected_change:
        expected_path = Path(args.expected_change)
        expected_change = expected_path.exists()

    report = {
        "format": args.format,
        "baseline_dir": str(baseline_path),
        "current_dir": str(current_path),
        "baseline_scores": baseline_scores,
        "current_scores": current_scores,
        "score_drift": score_drift,
        "trigger_drift_top20_union": trigger_drift,
        "baseline_immediate_fail": baseline_immediate_fail,
        "current_immediate_fail": current_immediate_fail,
        "immediate_fail_rate_drift": immediate_fail_drift,
        "immediate_fail_count_drift": immediate_fail_count_drift,
        "baseline_unsafe": baseline_unsafe,
        "current_unsafe": current_unsafe,
        "unsafe_rate_drift": unsafe_drift,
        "unsafe_count_drift": unsafe_count_drift,
        "baseline_unsafe_non_immediate": baseline_unsafe_non_immediate,
        "current_unsafe_non_immediate": current_unsafe_non_immediate,
        "unsafe_non_immediate_rate_drift": round(
            current_unsafe_non_immediate["rate"] - baseline_unsafe_non_immediate["rate"], 2
        ),
        "unsafe_non_immediate_count_drift": (
            current_unsafe_non_immediate["count"] - baseline_unsafe_non_immediate["count"]
        ),
        "thresholds": {
            "score_drift_threshold": args.score_drift_threshold,
            "trigger_rate_threshold": args.trigger_rate_threshold,
            "trigger_count_threshold": args.trigger_count_threshold,
            "immediate_fail_rate_threshold": args.immediate_fail_rate_threshold,
            "immediate_fail_count_threshold": args.immediate_fail_count_threshold,
            "unsafe_rate_threshold": args.unsafe_rate_threshold,
            "unsafe_count_threshold": args.unsafe_count_threshold,
            "min_baseline_count_for_rate": args.min_baseline_count_for_rate,
        },
        "expected_change": expected_change,
        "gate_failures": gate_failures,
        "pass_gate": expected_change or len(gate_failures) == 0,
    }

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"score_stability_gate_{args.format}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Score stability gate report written to: {report_path}")
    if report["pass_gate"]:
        print("Gate status: PASS")
        return 0

    print("Gate status: FAIL")
    for failure in gate_failures:
        print(f"  - {failure}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
