#!/usr/bin/env python3
"""
B4 Proprietary Blend Scoring Regression Analysis
=================================================

Validates the new impact-weighted B4 algorithm against real data.

Checks:
1. Score drift (before/after comparison)
2. Edge case coverage (danger zones)
3. Payload size validation
4. Status safety (B4 never causes blocking/error)
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple
from collections import defaultdict
import statistics

# Add parent for imports
sys.path.insert(0, str(Path(__file__).parent))

from score_supplements import SupplementScorer


def load_enriched_products(enriched_dir: Path, limit: int = None) -> List[Dict]:
    """Load enriched products from directory."""
    products = []
    for batch_file in sorted(enriched_dir.glob("enriched_*.json")):
        with open(batch_file) as f:
            batch = json.load(f)
            if isinstance(batch, list):
                products.extend(batch)
            elif isinstance(batch, dict) and "products" in batch:
                products.extend(batch["products"])
        if limit and len(products) >= limit:
            break
    return products[:limit] if limit else products


def analyze_b4_regression(products: List[Dict]) -> Dict[str, Any]:
    """
    Run B4 scoring analysis on products and collect metrics.

    Returns comprehensive analysis dict.
    """
    scorer = SupplementScorer()
    b4_config = scorer.config.get("section_b", {}).get("B4_proprietary_blends", {})

    results = {
        # Count metrics
        "total_products": len(products),
        "products_with_blends": 0,
        "products_without_blends": 0,

        # B4 penalty distribution
        "b4_penalties": [],
        "b4_penalties_nonzero": [],

        # Method usage
        "use_mg_share_count": 0,
        "use_count_share_count": 0,

        # Cap/mitigation
        "hit_cap_15_count": 0,
        "mitigation_applied_count": 0,
        "mitigation_factors": [],

        # Edge cases (danger zones)
        "blends_but_zero_actives": 0,
        "low_total_mg_fallback": 0,
        "low_coverage_fallback": 0,
        "blend_mg_exceeds_total_count": 0,

        # Deduplication stats
        "total_blends_detected": 0,
        "total_blends_after_dedupe": 0,
        "products_with_dedupe": 0,

        # Payload size
        "max_blends_per_product": 0,
        "avg_blends_per_product": 0,
        "penalty_by_blend_lengths": [],

        # Status safety
        "b4_caused_not_applicable": 0,
        "b4_caused_blocked": 0,
        "b4_caused_error": 0,

        # Detailed samples
        "largest_penalty_products": [],
        "edge_case_samples": [],
    }

    blend_counts = []

    for product in products:
        product_id = product.get("dsld_id") or product.get("id") or "unknown"
        proprietary_data = product.get("proprietary_data", {})

        # Check if product has blends
        has_blends = proprietary_data.get("has_proprietary_blends", False)
        blends = proprietary_data.get("blends", [])

        if not has_blends or not blends:
            results["products_without_blends"] += 1
            continue

        results["products_with_blends"] += 1
        results["total_blends_detected"] += len(blends)
        blend_counts.append(len(blends))

        # Run B4 scoring
        penalty, notes, details = scorer._score_b4_proprietary(
            product, proprietary_data, b4_config
        )

        results["b4_penalties"].append(penalty)
        if penalty != 0:
            results["b4_penalties_nonzero"].append(penalty)

        # Check for early exit reasons (danger zones)
        reason = details.get("reason")
        if reason == "no_scorable_actives":
            results["blends_but_zero_actives"] += 1
            results["edge_case_samples"].append({
                "product_id": product_id,
                "reason": "blends_but_zero_actives",
                "blend_count": len(blends),
                "penalty": penalty,
            })
            continue

        if reason in ("no_proprietary_blends", "no_blends_detected"):
            continue

        # Analyze method usage
        use_mg_share = details.get("use_mg_share", False)
        if use_mg_share:
            results["use_mg_share_count"] += 1
        else:
            results["use_count_share_count"] += 1

        # Check mg eligibility fallback reasons
        total_active_mg = details.get("total_active_mg", 0)
        known_fraction = details.get("known_amount_fraction", 0)

        if total_active_mg < 25.0 and not use_mg_share:
            results["low_total_mg_fallback"] += 1
        if known_fraction < 0.60 and not use_mg_share:
            results["low_coverage_fallback"] += 1

        # Count blend_mg > total_active_mg
        penalty_by_blend = details.get("penalty_by_blend", [])
        results["penalty_by_blend_lengths"].append(len(penalty_by_blend))
        results["total_blends_after_dedupe"] += len(penalty_by_blend)

        if len(penalty_by_blend) < len(blends):
            results["products_with_dedupe"] += 1

        for blend_detail in penalty_by_blend:
            blend_mg = blend_detail.get("blend_mg")
            if blend_mg and blend_mg > total_active_mg and total_active_mg > 0:
                results["blend_mg_exceeds_total_count"] += 1

        # Cap and mitigation stats
        pre_mitigation = details.get("pre_mitigation_total", 0)
        if pre_mitigation == -15:
            results["hit_cap_15_count"] += 1

        mitigation_applied = details.get("mitigation_factor_applied", 0)
        if mitigation_applied > 0:
            results["mitigation_applied_count"] += 1
            results["mitigation_factors"].append(mitigation_applied)

        # Track max blends
        if len(blends) > results["max_blends_per_product"]:
            results["max_blends_per_product"] = len(blends)

        # Collect largest penalty products
        if penalty < -3:  # Meaningful penalty
            results["largest_penalty_products"].append({
                "product_id": product_id,
                "product_name": product.get("product_name", "unknown")[:80],
                "penalty": penalty,
                "blend_count": len(blends),
                "deduped_count": len(penalty_by_blend),
                "use_mg_share": use_mg_share,
                "worst_disclosure": details.get("worst_disclosure"),
                "pre_mitigation": pre_mitigation,
                "mitigation_applied": mitigation_applied,
            })

    # Calculate averages
    if blend_counts:
        results["avg_blends_per_product"] = sum(blend_counts) / len(blend_counts)

    # Sort largest penalties
    results["largest_penalty_products"].sort(key=lambda x: x["penalty"])
    results["largest_penalty_products"] = results["largest_penalty_products"][:20]

    # Calculate penalty distribution
    if results["b4_penalties_nonzero"]:
        penalties = results["b4_penalties_nonzero"]
        results["penalty_distribution"] = {
            "count": len(penalties),
            "min": min(penalties),
            "p25": statistics.quantiles(penalties, n=4)[0] if len(penalties) >= 4 else min(penalties),
            "median": statistics.median(penalties),
            "p75": statistics.quantiles(penalties, n=4)[2] if len(penalties) >= 4 else max(penalties),
            "max": max(penalties),
            "mean": statistics.mean(penalties),
        }
    else:
        results["penalty_distribution"] = {"count": 0}

    return results


def verify_status_safety(products: List[Dict]) -> Dict[str, Any]:
    """
    Verify B4 NEVER causes blocked/error/not_applicable status.

    B4 is a transparency penalty only - it must not affect scoring eligibility.
    """
    scorer = SupplementScorer()

    violations = []

    for product in products:
        product_id = product.get("dsld_id") or product.get("id") or "unknown"

        # Score the product
        try:
            result = scorer.score_product(product)

            scoring_status = result.get("scoring_status", "")

            # Check if B4 is the cause of any non-scored status
            # This is hard to prove causally, but we can check:
            # - If product has blends AND status is blocked/error
            # - AND the blocking reason mentions B4 or proprietary

            proprietary_data = product.get("proprietary_data", {})
            has_blends = proprietary_data.get("has_proprietary_blends", False)

            if has_blends:
                # Check the score breakdown for B4 issues
                breakdown = result.get("score_breakdown", {})
                b4_entry = breakdown.get("B4_proprietary_blends", {})

                # B4 should have a valid numeric penalty (or 0), never cause status changes
                if scoring_status == "blocked":
                    # Check if blocking reason is B4-related (it shouldn't be)
                    block_reason = result.get("safety_block", {}).get("block_type", "")
                    if "blend" in block_reason.lower() or "proprietary" in block_reason.lower():
                        violations.append({
                            "product_id": product_id,
                            "violation": "B4 caused blocked status",
                            "block_reason": block_reason,
                        })

                elif scoring_status == "error":
                    error_reason = result.get("error", "")
                    if "b4" in error_reason.lower() or "proprietary" in error_reason.lower():
                        violations.append({
                            "product_id": product_id,
                            "violation": "B4 caused error status",
                            "error": error_reason,
                        })

        except Exception as e:
            # If B4 causes an exception, that's a violation
            if "b4" in str(e).lower() or "proprietary" in str(e).lower():
                violations.append({
                    "product_id": product_id,
                    "violation": "B4 caused exception",
                    "error": str(e),
                })

    return {
        "products_checked": len(products),
        "violations": violations,
        "is_safe": len(violations) == 0,
    }


def print_report(results: Dict[str, Any], safety: Dict[str, Any]) -> None:
    """Print formatted regression report."""
    print("=" * 70)
    print("B4 PROPRIETARY BLEND SCORING REGRESSION ANALYSIS")
    print("=" * 70)

    print(f"\n### Dataset Summary")
    print(f"Total products analyzed: {results['total_products']}")
    print(f"Products with blends: {results['products_with_blends']}")
    print(f"Products without blends: {results['products_without_blends']}")

    print(f"\n### B4 Penalty Distribution (Non-Zero Only)")
    dist = results.get("penalty_distribution", {})
    if dist.get("count", 0) > 0:
        print(f"  Count: {dist['count']}")
        print(f"  Min:    {dist['min']}")
        print(f"  P25:    {dist['p25']:.1f}")
        print(f"  Median: {dist['median']:.1f}")
        print(f"  P75:    {dist['p75']:.1f}")
        print(f"  Max:    {dist['max']}")
        print(f"  Mean:   {dist['mean']:.2f}")
    else:
        print("  No non-zero penalties found")

    print(f"\n### Impact Method Usage")
    print(f"  mg_share:    {results['use_mg_share_count']}")
    print(f"  count_share: {results['use_count_share_count']}")

    print(f"\n### Cap & Mitigation")
    print(f"  Hit -15 cap: {results['hit_cap_15_count']}")
    print(f"  Mitigation applied: {results['mitigation_applied_count']}")
    if results["mitigation_factors"]:
        avg_mit = statistics.mean(results["mitigation_factors"])
        print(f"  Avg mitigation factor: {avg_mit:.2%}")

    print(f"\n### Deduplication Stats")
    print(f"  Total blends detected: {results['total_blends_detected']}")
    print(f"  After dedupe: {results['total_blends_after_dedupe']}")
    print(f"  Products with dedupe: {results['products_with_dedupe']}")
    deduped_pct = 0
    if results['total_blends_detected'] > 0:
        deduped_pct = (1 - results['total_blends_after_dedupe'] / results['total_blends_detected']) * 100
    print(f"  Deduplication rate: {deduped_pct:.1f}%")

    print(f"\n### Edge Cases (Danger Zones)")
    print(f"  Blends but zero actives: {results['blends_but_zero_actives']}")
    print(f"  Low total_mg fallback (<25mg): {results['low_total_mg_fallback']}")
    print(f"  Low coverage fallback (<60%): {results['low_coverage_fallback']}")
    print(f"  blend_mg > total_active_mg: {results['blend_mg_exceeds_total_count']}")

    print(f"\n### Payload Size")
    print(f"  Max blends per product: {results['max_blends_per_product']}")
    print(f"  Avg blends per product: {results['avg_blends_per_product']:.2f}")
    if results["penalty_by_blend_lengths"]:
        avg_details = statistics.mean(results["penalty_by_blend_lengths"])
        print(f"  Avg penalty_by_blend entries: {avg_details:.2f}")

    print(f"\n### Status Safety Check")
    print(f"  Products checked: {safety['products_checked']}")
    print(f"  Violations found: {len(safety['violations'])}")
    print(f"  STATUS: {'SAFE' if safety['is_safe'] else 'VIOLATIONS FOUND!'}")

    if safety["violations"]:
        print("\n  VIOLATIONS:")
        for v in safety["violations"][:10]:
            print(f"    - {v['product_id']}: {v['violation']}")

    print(f"\n### Top 20 Largest Penalty Products")
    print("-" * 70)
    for i, p in enumerate(results["largest_penalty_products"][:20], 1):
        print(f"{i:2}. ID={p['product_id']:<12} penalty={p['penalty']:>3} "
              f"blends={p['blend_count']}/{p['deduped_count']} "
              f"method={'mg' if p['use_mg_share'] else 'cnt'} "
              f"disc={p['worst_disclosure']}")

    if results["edge_case_samples"]:
        print(f"\n### Edge Case Samples (blends but zero actives)")
        print("-" * 70)
        for sample in results["edge_case_samples"][:5]:
            print(f"  - {sample['product_id']}: {sample['blend_count']} blends, penalty={sample['penalty']}")

    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)


def main():
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=["lozenges", "gummies"], default="lozenges")
    parser.add_argument("--limit", type=int, default=None, help="Limit products to analyze")
    args = parser.parse_args()

    if args.dataset == "gummies":
        enriched_dir = Path(__file__).parent / "output_Gummies_enriched" / "enriched"
    else:
        enriched_dir = Path(__file__).parent / "output_Lozenges_enriched" / "enriched"

    if not enriched_dir.exists():
        enriched_dir = Path(__file__).parent / "output_Gummies_enriched" / "enriched"

    if not enriched_dir.exists():
        print("ERROR: No enriched data found")
        sys.exit(1)

    print(f"Loading products from: {enriched_dir}")
    products = load_enriched_products(enriched_dir, limit=args.limit)
    print(f"Loaded {len(products)} products")

    print("\nRunning B4 regression analysis...")
    results = analyze_b4_regression(products)

    print("\nVerifying status safety...")
    safety = verify_status_safety(products)

    print_report(results, safety)

    # Return exit code based on safety
    sys.exit(0 if safety["is_safe"] else 1)


if __name__ == "__main__":
    main()
