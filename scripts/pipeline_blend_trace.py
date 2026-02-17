#!/usr/bin/env python3
"""
Pipeline Blend Trace - End-to-End Verification
===============================================

Traces proprietary blend data from RAW → CLEANED → ENRICHED → SCORED
to verify no data loss, mutation, or misclassification occurs.

Usage:
    python pipeline_blend_trace.py
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent))

from score_supplements import SupplementScorer


@dataclass
class BlendTrace:
    """Trace of blend data through pipeline stages."""
    product_id: str
    product_name: str

    # Stage 1: Cleaned data
    cleaned_blend_count: int
    cleaned_blends: List[Dict]

    # Stage 2: Enriched proprietary_data
    enriched_has_blends: bool
    enriched_blend_count: int
    enriched_blends: List[Dict]

    # Stage 3: Scoring inputs
    scoring_received_blends: int
    scoring_b4_penalty: float
    scoring_b4_details: Dict

    # Validation flags
    blend_count_matches: bool
    disclosure_levels_preserved: bool
    mg_data_preserved: bool
    issues: List[str]


def load_enriched_products(enriched_dir: Path, limit: int = None) -> List[Dict]:
    """Load enriched products."""
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


def extract_cleaned_blends(product: Dict) -> List[Dict]:
    """
    Extract blend data as it appears from the cleaning stage.

    Cleaning sets:
    - proprietaryBlend: bool
    - disclosureLevel: "full" | "partial" | "none"
    - nestedIngredients: list
    """
    blends = []

    for ing in product.get('activeIngredients', []):
        if ing.get('proprietaryBlend', False):
            blends.append({
                "name": ing.get('name', ''),
                "disclosure_level": ing.get('disclosureLevel', 'none'),
                "quantity": ing.get('quantity', 0),
                "unit": ing.get('unit', ''),
                "nested_count": len(ing.get('nestedIngredients', [])),
                "source": "activeIngredients"
            })

    for ing in product.get('inactiveIngredients', []):
        if ing.get('proprietaryBlend', False):
            blends.append({
                "name": ing.get('name', ''),
                "disclosure_level": ing.get('disclosureLevel', 'none'),
                "quantity": ing.get('quantity', 0),
                "unit": ing.get('unit', ''),
                "nested_count": len(ing.get('nestedIngredients', [])),
                "source": "inactiveIngredients"
            })

    return blends


def trace_product(product: Dict, scorer: SupplementScorer) -> BlendTrace:
    """Trace blend data through all pipeline stages for a single product."""
    product_id = product.get('dsld_id', 'unknown')
    product_name = product.get('product_name', 'unknown')

    issues = []

    # Stage 1: Extract cleaned blend data
    cleaned_blends = extract_cleaned_blends(product)

    # Stage 2: Extract enriched proprietary_data
    proprietary_data = product.get('proprietary_data', {})
    enriched_has_blends = proprietary_data.get('has_proprietary_blends', False)
    enriched_blends = proprietary_data.get('blends', [])

    # Stage 3: Run scoring to see what it receives
    b4_config = scorer.config.get('section_b', {}).get('B4_proprietary_blends', {})
    b4_penalty, b4_notes, b4_details = scorer._score_b4_proprietary(
        product, proprietary_data, b4_config
    )

    # Validation checks

    # Check 1: Blend count consistency
    # Note: enrichment may detect additional blends via ProprietaryBlendDetector
    # that weren't marked in cleaning (pattern-based detection)
    blend_count_matches = True
    if cleaned_blends and not enriched_has_blends:
        issues.append(f"LOST_BLENDS: {len(cleaned_blends)} cleaned blends, but enriched says no blends")
        blend_count_matches = False

    # Check 2: Disclosure levels preserved
    disclosure_preserved = True
    for cleaned in cleaned_blends:
        name = cleaned['name'].lower().strip()
        disclosure = cleaned['disclosure_level']

        # Find matching enriched blend
        found = False
        for enriched in enriched_blends:
            enriched_name = (enriched.get('name') or '').lower().strip()
            if enriched_name == name or name in enriched_name or enriched_name in name:
                found = True
                enriched_disclosure = enriched.get('disclosure_level', 'none')
                if enriched_disclosure != disclosure:
                    issues.append(
                        f"DISCLOSURE_MISMATCH: '{name}' cleaned={disclosure}, enriched={enriched_disclosure}"
                    )
                    disclosure_preserved = False
                break

        if not found and enriched_blends:
            # Only flag if we have enriched blends but couldn't match
            issues.append(f"BLEND_NOT_FOUND_IN_ENRICHED: '{name}'")

    # Check 3: mg data preserved
    mg_preserved = True
    for enriched in enriched_blends:
        # Check for mg data in blend or evidence
        blend_mg = enriched.get('total_weight') or enriched.get('blend_total_amount')
        if blend_mg is None:
            evidence = enriched.get('evidence', {})
            if evidence:
                blend_mg = evidence.get('blend_total_amount')

        # Find original cleaned blend
        name = (enriched.get('name') or '').lower().strip()
        for cleaned in cleaned_blends:
            cleaned_name = cleaned['name'].lower().strip()
            if cleaned_name == name or name in cleaned_name:
                cleaned_qty = cleaned.get('quantity', 0)
                if cleaned_qty > 0 and blend_mg is None:
                    issues.append(f"MG_DATA_LOST: '{name}' had {cleaned_qty} in cleaned, None in enriched")
                    mg_preserved = False
                break

    return BlendTrace(
        product_id=product_id,
        product_name=product_name[:60],
        cleaned_blend_count=len(cleaned_blends),
        cleaned_blends=cleaned_blends,
        enriched_has_blends=enriched_has_blends,
        enriched_blend_count=len(enriched_blends),
        enriched_blends=enriched_blends,
        scoring_received_blends=b4_details.get('blends_detected_count', 0),
        scoring_b4_penalty=b4_penalty,
        scoring_b4_details=b4_details,
        blend_count_matches=blend_count_matches,
        disclosure_levels_preserved=disclosure_preserved,
        mg_data_preserved=mg_preserved,
        issues=issues
    )


def find_products_with_blends(products: List[Dict], criteria: str) -> List[Dict]:
    """Find products matching specific blend criteria."""
    results = []

    for product in products:
        cleaned_blends = extract_cleaned_blends(product)
        proprietary_data = product.get('proprietary_data', {})
        enriched_blends = proprietary_data.get('blends', [])

        if criteria == "small_blend":
            # Small blend: total weight < 50mg
            for blend in enriched_blends:
                mg = blend.get('total_weight') or blend.get('blend_total_amount') or 0
                if 0 < mg < 50:
                    results.append(product)
                    break

        elif criteria == "large_blend":
            # Large blend: total weight > 200mg
            for blend in enriched_blends:
                mg = blend.get('total_weight') or blend.get('blend_total_amount') or 0
                if mg > 200:
                    results.append(product)
                    break

        elif criteria == "multiple_blends":
            if len(enriched_blends) >= 2:
                results.append(product)

        elif criteria == "duplicate_blends":
            # Same blend appearing in multiple sections
            if len(enriched_blends) > len(set(b.get('name', '').lower() for b in enriched_blends)):
                results.append(product)

        elif criteria == "cleaned_not_enriched":
            # Blends in cleaned but not in enriched
            if cleaned_blends and not proprietary_data.get('has_proprietary_blends'):
                results.append(product)

    return results


def main():
    """Run end-to-end blend trace verification."""
    print("=" * 70)
    print("PIPELINE BLEND TRACE - END-TO-END VERIFICATION")
    print("=" * 70)

    # Load data
    enriched_dir = Path(__file__).parent / "output_Lozenges_enriched" / "enriched"
    if not enriched_dir.exists():
        enriched_dir = Path(__file__).parent / "output_Gummies_enriched" / "enriched"

    print(f"\nLoading from: {enriched_dir}")
    products = load_enriched_products(enriched_dir, limit=1000)
    print(f"Loaded {len(products)} products")

    scorer = SupplementScorer()

    # Find products by criteria
    print("\n### Finding Products by Criteria")
    print("-" * 50)

    criteria_results = {}
    for criteria in ["small_blend", "large_blend", "multiple_blends", "duplicate_blends", "cleaned_not_enriched"]:
        found = find_products_with_blends(products, criteria)
        criteria_results[criteria] = found
        print(f"  {criteria}: {len(found)} products")

    # Trace sample products from each category
    print("\n### Detailed Traces")
    print("=" * 70)

    all_traces = []
    all_issues = []

    # Trace products with blends
    products_with_blends = [p for p in products if p.get('proprietary_data', {}).get('has_proprietary_blends')]

    for product in products_with_blends[:50]:  # Sample 50 products
        trace = trace_product(product, scorer)
        all_traces.append(trace)
        if trace.issues:
            all_issues.extend([(trace.product_id, issue) for issue in trace.issues])

    # Also trace products from each criteria
    for criteria, found in criteria_results.items():
        for product in found[:5]:  # Sample 5 from each
            trace = trace_product(product, scorer)
            if trace not in all_traces:
                all_traces.append(trace)
                if trace.issues:
                    all_issues.extend([(trace.product_id, issue) for issue in trace.issues])

    # Print detailed traces for products with multiple blends
    print("\n### Sample Traces: Multiple Blends")
    print("-" * 70)

    multi_blend_traces = [t for t in all_traces if t.enriched_blend_count >= 2][:5]
    for trace in multi_blend_traces:
        print(f"\nProduct: {trace.product_id} - {trace.product_name}")
        print(f"  Cleaned blends: {trace.cleaned_blend_count}")
        for b in trace.cleaned_blends:
            print(f"    - {b['name'][:40]}: {b['disclosure_level']}, {b['quantity']}{b['unit']}")
        print(f"  Enriched blends: {trace.enriched_blend_count}")
        for b in trace.enriched_blends:
            mg = b.get('total_weight') or b.get('blend_total_amount') or 0
            print(f"    - {b.get('name', '')[:40]}: {b.get('disclosure_level')}, {mg}mg")
        print(f"  B4 penalty: {trace.scoring_b4_penalty}")
        if trace.issues:
            print(f"  ISSUES: {trace.issues}")

    # Print detailed traces for small vs large blends
    print("\n### Sample Traces: Small Blends (<50mg)")
    print("-" * 70)

    small_traces = [t for t in all_traces if any(
        (b.get('total_weight') or b.get('blend_total_amount') or 0) < 50 and (b.get('total_weight') or b.get('blend_total_amount') or 0) > 0
        for b in t.enriched_blends
    )][:3]
    for trace in small_traces:
        print(f"\nProduct: {trace.product_id}")
        for b in trace.enriched_blends:
            mg = b.get('total_weight') or b.get('blend_total_amount') or 0
            if 0 < mg < 50:
                print(f"  Blend: {b.get('name', '')[:40]}")
                print(f"    mg: {mg}, disclosure: {b.get('disclosure_level')}")
        print(f"  B4 penalty: {trace.scoring_b4_penalty}")
        details = trace.scoring_b4_details
        if details.get('penalty_by_blend'):
            for pd in details['penalty_by_blend']:
                print(f"    - {pd['name'][:30]}: impact={pd['impact']:.2f}, scale={pd['scale']}, penalty={pd['penalty']}")

    print("\n### Sample Traces: Large Blends (>200mg)")
    print("-" * 70)

    large_traces = [t for t in all_traces if any(
        (b.get('total_weight') or b.get('blend_total_amount') or 0) > 200
        for b in t.enriched_blends
    )][:3]
    for trace in large_traces:
        print(f"\nProduct: {trace.product_id}")
        for b in trace.enriched_blends:
            mg = b.get('total_weight') or b.get('blend_total_amount') or 0
            if mg > 200:
                print(f"  Blend: {b.get('name', '')[:40]}")
                print(f"    mg: {mg}, disclosure: {b.get('disclosure_level')}")
        print(f"  B4 penalty: {trace.scoring_b4_penalty}")
        details = trace.scoring_b4_details
        if details.get('penalty_by_blend'):
            for pd in details['penalty_by_blend']:
                print(f"    - {pd['name'][:30]}: impact={pd['impact']:.2f}, scale={pd['scale']}, penalty={pd['penalty']}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    total_traced = len(all_traces)
    issues_found = len(all_issues)
    unique_issue_types = set(issue.split(':')[0] for _, issue in all_issues)

    print(f"\nProducts traced: {total_traced}")
    print(f"Total issues found: {issues_found}")

    if all_issues:
        print(f"\nIssue types: {unique_issue_types}")
        print("\nSample issues:")
        for pid, issue in all_issues[:10]:
            print(f"  - {pid}: {issue}")
    else:
        print("\nNO ISSUES FOUND - Pipeline is clean!")

    # Validation metrics
    blend_count_ok = sum(1 for t in all_traces if t.blend_count_matches)
    disclosure_ok = sum(1 for t in all_traces if t.disclosure_levels_preserved)
    mg_ok = sum(1 for t in all_traces if t.mg_data_preserved)

    print(f"\nValidation metrics:")
    print(f"  Blend count preserved: {blend_count_ok}/{total_traced} ({100*blend_count_ok/total_traced:.1f}%)")
    print(f"  Disclosure preserved:  {disclosure_ok}/{total_traced} ({100*disclosure_ok/total_traced:.1f}%)")
    print(f"  mg data preserved:     {mg_ok}/{total_traced} ({100*mg_ok/total_traced:.1f}%)")

    print("\n" + "=" * 70)
    if issues_found == 0:
        print("VERDICT: PIPELINE IS CLEAN AND STABLE")
    else:
        print(f"VERDICT: {issues_found} ISSUES NEED INVESTIGATION")
    print("=" * 70)

    return 0 if issues_found == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
