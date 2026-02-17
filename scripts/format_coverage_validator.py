#!/usr/bin/env python3
"""
Format Coverage Validator
=========================
Validates enrichment + scoring coverage across product formats.

Captures metrics per format:
- % scorable vs skipped ingredients
- Frequency of each skip reason
- Proprietary blend trigger counts (with dedupe check)
- "Inactive promoted" counts and reasons
- "Unknown scorable" (scorable but not in DB) counts

Usage:
    python format_coverage_validator.py --input output_Gummies_enriched/enriched/
    python format_coverage_validator.py --input output_Powders_enriched/enriched/ --format powder
    python format_coverage_validator.py --input output_Lozenges_enriched/enriched/ --output reports/

Author: PharmaGuide Team
"""

import json
import os
import sys
import argparse
from collections import Counter, defaultdict
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))


class FormatCoverageValidator:
    """Validates enrichment coverage and captures metrics."""

    def __init__(self, format_name: str = "unknown"):
        self.format_name = format_name
        self.products_analyzed = 0
        self.metrics = self._init_metrics()

    def _init_metrics(self) -> Dict:
        """Initialize metrics structure."""
        return {
            # Ingredient classification metrics (record-level primitives)
            "total_records_seen": 0,           # input records before classification
            "total_ingredients_evaluated": 0,  # scorable + skipped (invariant denominator)
            "unevaluated_records": 0,          # leak detection: should be 0
            "total_active_ingredients": 0,     # legacy: original active ingredients only
            "total_scorable_ingredients": 0,
            "total_skipped_ingredients": 0,
            "total_inactive_ingredients": 0,
            "total_promoted_from_inactive": 0,

            # Detailed breakdowns
            "skip_reasons": Counter(),
            "promotion_reasons": Counter(),
            "promotion_confidence": Counter(),

            # DB coverage metrics
            "scorable_mapped": 0,
            "scorable_unmapped": 0,
            "unknown_scorable_ingredients": Counter(),  # name -> count

            # Normalized-name metrics (unique normalized ingredients)
            "normalized_name_counts": {
                "evaluated": Counter(),
                "scorable": Counter(),
                "skipped": Counter(),
            },

            # Blend metrics
            "products_with_blend_triggers": 0,
            "total_blend_triggers": 0,
            "blend_trigger_types": Counter(),
            "blend_only_products": 0,

            # Serving basis metrics
            "serving_units": Counter(),
            "products_missing_serving_basis": 0,

            # Scoring trigger metrics
            "caution_triggers": Counter(),
            "products_with_cautions": 0,

            # Per-product details for analysis
            "products": []
        }

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize ingredient names for stable, unique-name metrics."""
        return (name or "").lower().strip()

    def analyze_product(self, product: Dict) -> Dict:
        """Analyze a single enriched product and capture metrics."""
        self.products_analyzed += 1

        product_id = product.get('dsld_id', 'unknown')
        product_name = product.get('product_name', 'Unknown')

        # Extract quality data
        quality_data = product.get('ingredient_quality_data', {})
        scoring_result = product.get('scoring_result', {})

        # Ingredient classification metrics
        total_active = quality_data.get('total_active', 0)
        total_scorable = quality_data.get('total_scorable_active_count', 0)
        skipped_count = quality_data.get('skipped_non_scorable_count', 0)
        unmapped_scorable = quality_data.get('unmapped_scorable_count', 0)

        # Leak detection metrics
        total_records_seen = quality_data.get('total_records_seen', 0)
        unevaluated = quality_data.get('unevaluated_records', 0)

        # Use new record-level primitive if available, otherwise fallback
        total_evaluated = quality_data.get('total_ingredients_evaluated', 0)
        if total_evaluated == 0:
            # Fallback for older enriched data without the new field
            total_evaluated = total_scorable + skipped_count
        if total_records_seen == 0:
            # Fallback for older enriched data
            total_records_seen = total_active

        self.metrics['total_records_seen'] += total_records_seen
        self.metrics['total_ingredients_evaluated'] += total_evaluated
        self.metrics['unevaluated_records'] += unevaluated
        self.metrics['total_active_ingredients'] += total_active
        self.metrics['total_scorable_ingredients'] += total_scorable
        self.metrics['total_skipped_ingredients'] += skipped_count
        self.metrics['scorable_unmapped'] += unmapped_scorable
        self.metrics['scorable_mapped'] += (total_scorable - unmapped_scorable)

        # Skip reasons breakdown
        skip_reasons = quality_data.get('skipped_reasons_breakdown', {})
        for reason, count in skip_reasons.items():
            self.metrics['skip_reasons'][reason] += count

        # Promoted from inactive
        promoted = quality_data.get('promoted_from_inactive', [])
        self.metrics['total_promoted_from_inactive'] += len(promoted)
        for promo in promoted:
            reason = promo.get('promotion_reason', 'unknown')
            confidence = promo.get('promotion_confidence', 'unknown')
            self.metrics['promotion_reasons'][reason] += 1
            self.metrics['promotion_confidence'][confidence] += 1

        # Collect unknown scorable ingredients (unmapped but scorable)
        scorable_ingredients = quality_data.get('ingredients_scorable', [])
        for ing in scorable_ingredients:
            if not ing.get('mapped', False):
                name = ing.get('name', '')
                std_name = ing.get('standard_name', name)
                normalized = self._normalize_name(std_name)
                self.metrics['unknown_scorable_ingredients'][normalized] += 1

        # Normalized-name metrics for scorable + skipped
        for ing in scorable_ingredients:
            std_name = ing.get('standard_name', ing.get('name', ''))
            normalized = self._normalize_name(std_name)
            if normalized:
                self.metrics['normalized_name_counts']['scorable'][normalized] += 1
                self.metrics['normalized_name_counts']['evaluated'][normalized] += 1

        skipped_ingredients = quality_data.get('ingredients_skipped', [])
        for ing in skipped_ingredients:
            std_name = ing.get('standard_name', ing.get('name', ''))
            normalized = self._normalize_name(std_name)
            if normalized:
                self.metrics['normalized_name_counts']['skipped'][normalized] += 1
                self.metrics['normalized_name_counts']['evaluated'][normalized] += 1

        # Blend metrics
        blend_only = quality_data.get('blend_only_product', False)
        if blend_only:
            self.metrics['blend_only_products'] += 1

        blend_headers = quality_data.get('blend_header_rows', [])

        # Check scoring triggers for blend-related
        triggers = []
        if scoring_result:
            triggers = scoring_result.get('caution_triggers', [])
            if triggers:
                self.metrics['products_with_cautions'] += 1

            for trigger in triggers:
                self.metrics['caution_triggers'][trigger] += 1
                if 'blend' in trigger.lower() or 'proprietary' in trigger.lower():
                    self.metrics['total_blend_triggers'] += 1
                    self.metrics['blend_trigger_types'][trigger] += 1

        # Check if product has any blend triggers
        blend_triggers_in_product = [t for t in triggers
                                      if 'blend' in t.lower() or 'proprietary' in t.lower()]
        if blend_triggers_in_product:
            self.metrics['products_with_blend_triggers'] += 1

        # Serving basis metrics
        serving_basis = product.get('serving_basis', {})
        serving_unit = serving_basis.get('basis_unit', '')
        if serving_unit:
            self.metrics['serving_units'][serving_unit] += 1
        else:
            self.metrics['products_missing_serving_basis'] += 1

        # Inactive ingredients
        inactive = product.get('inactiveIngredients', [])
        self.metrics['total_inactive_ingredients'] += len(inactive)

        # Store per-product summary
        product_summary = {
            "id": product_id,
            "name": product_name[:50],
            "total_active": total_active,
            "scorable": total_scorable,
            "skipped": skipped_count,
            "unmapped_scorable": unmapped_scorable,
            "promoted": len(promoted),
            "blend_only": blend_only,
            "caution_triggers": triggers,
            "serving_unit": serving_unit
        }
        self.metrics['products'].append(product_summary)

        return product_summary

    def analyze_batch(self, products: List[Dict]) -> Dict:
        """Analyze a batch of products."""
        for product in products:
            self.analyze_product(product)
        return self.generate_report()

    def generate_report(self) -> Dict:
        """Generate summary report."""
        m = self.metrics

        # Calculate percentages using record-level primitive as denominator
        # INVARIANT: scorable + skipped = total_evaluated (always <= 100%)
        total_evaluated = m['total_ingredients_evaluated'] or 1  # Avoid division by zero
        total_records_seen = m['total_records_seen'] or 1
        total_scorable = m['total_scorable_ingredients'] or 1

        scorable_pct = (m['total_scorable_ingredients'] / total_evaluated * 100)
        skipped_pct = (m['total_skipped_ingredients'] / total_evaluated * 100)
        unmapped_pct = (m['scorable_unmapped'] / total_scorable * 100) if total_scorable else 0

        # Leak detection: what % of records seen were actually evaluated
        evaluated_pct = (m['total_ingredients_evaluated'] / total_records_seen * 100)
        leak_count = m['unevaluated_records']

        # Check for blend trigger deduplication
        avg_blend_triggers = (m['total_blend_triggers'] / m['products_with_blend_triggers']
                              if m['products_with_blend_triggers'] else 0)

        # Get top unknown scorable ingredients
        top_unknown = m['unknown_scorable_ingredients'].most_common(50)
        top_scorable_names = m['normalized_name_counts']['scorable'].most_common(50)
        top_skipped_names = m['normalized_name_counts']['skipped'].most_common(50)

        report = {
            "format": self.format_name,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "products_analyzed": self.products_analyzed,

            "summary": {
                "scorable_percentage": round(scorable_pct, 1),
                "skipped_percentage": round(skipped_pct, 1),
                "unmapped_scorable_percentage": round(unmapped_pct, 1),
                "promoted_from_inactive_total": m['total_promoted_from_inactive'],
                "blend_only_products": m['blend_only_products'],
                "products_with_cautions": m['products_with_cautions'],
            },

            "coverage_integrity": {
                "total_records_seen": m['total_records_seen'],
                "total_evaluated": m['total_ingredients_evaluated'],
                "evaluated_percentage": round(evaluated_pct, 1),
                "unevaluated_records": leak_count,
                "leak_check": "PASS" if leak_count == 0 else f"FAIL: {leak_count} leaked",
            },

            "ingredient_classification": {
                "total_evaluated": m['total_ingredients_evaluated'],  # denominator
                "total_scorable": m['total_scorable_ingredients'],
                "total_skipped": m['total_skipped_ingredients'],
                "scorable_mapped": m['scorable_mapped'],
                "scorable_unmapped": m['scorable_unmapped'],
                "total_active_legacy": m['total_active_ingredients'],  # for reference
            },

            "skip_reasons_breakdown": dict(m['skip_reasons'].most_common()),

            "promotion_breakdown": {
                "by_reason": dict(m['promotion_reasons'].most_common()),
                "by_confidence": dict(m['promotion_confidence'].most_common()),
            },

            "blend_analysis": {
                "products_with_blend_triggers": m['products_with_blend_triggers'],
                "total_blend_triggers": m['total_blend_triggers'],
                "avg_blend_triggers_per_product": round(avg_blend_triggers, 2),
                "trigger_types": dict(m['blend_trigger_types'].most_common()),
                "blend_only_products": m['blend_only_products'],
                "dedupe_check": "PASS" if avg_blend_triggers <= 1.5 else "WARN: possible duplicates"
            },

            "serving_basis": {
                "unit_distribution": dict(m['serving_units'].most_common(15)),
                "missing_count": m['products_missing_serving_basis'],
            },

            "caution_triggers": {
                "distribution": dict(m['caution_triggers'].most_common(20)),
                "products_affected": m['products_with_cautions'],
            },

            "unknown_scorable_ingredients": {
                "total_unique": len(m['unknown_scorable_ingredients']),
                "total_occurrences": sum(m['unknown_scorable_ingredients'].values()),
                "top_50": [{"name": name, "count": count}
                          for name, count in top_unknown],
            },

            "normalized_name_metrics": {
                "total_unique_evaluated": len(m['normalized_name_counts']['evaluated']),
                "total_unique_scorable": len(m['normalized_name_counts']['scorable']),
                "total_unique_skipped": len(m['normalized_name_counts']['skipped']),
                "top_50_scorable": [{"name": name, "count": count}
                                   for name, count in top_scorable_names],
                "top_50_skipped": [{"name": name, "count": count}
                                  for name, count in top_skipped_names],
            },

            # Don't include full product details in main report (too large)
            "products_sample": m['products'][:10] if m['products'] else []
        }

        return report

    def save_report(self, output_path: str):
        """Save report to file."""
        report = self.generate_report()
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        return report

    def save_unknown_scorable_report(self, output_path: str):
        """Save detailed unknown scorable ingredients report."""
        top_200 = self.metrics['unknown_scorable_ingredients'].most_common(200)

        report = {
            "format": self.format_name,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "description": "Top 200 scorable ingredients not found in therapeutic DBs",
            "action_needed": [
                "Bucket into: true actives to add, excipients to denylist, ambiguous terms",
            ],
            "ingredients": [
                {"rank": i + 1, "name": name, "occurrences": count}
                for i, (name, count) in enumerate(top_200)
            ]
        }

        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)

        return report


def load_enriched_products(input_path: str) -> List[Dict]:
    """
    Load enriched products from file or directory.

    Handles both directory layouts:
    - output_Lozenges_enriched/enriched/*.json
    - output_Lozenges/enriched/enriched/*.json

    Falls back to glob search if initial path yields no products.
    """
    products = []
    path = Path(input_path)

    if path.is_file():
        with open(path, 'r') as f:
            if path.suffix == '.jsonl':
                for line in f:
                    if line.strip():
                        products.append(json.loads(line))
            else:
                data = json.load(f)
                if isinstance(data, list):
                    products = data
                else:
                    products = [data]

    elif path.is_dir():
        # Try direct path first
        products = _load_from_directory(path)

        # If no products found, try common alternative layouts
        if not products:
            alternatives = [
                path / 'enriched',           # path/enriched/
                path.parent / 'enriched',    # ../enriched/
                path / '*.json',             # glob in current
            ]

            for alt in alternatives:
                if alt.exists() if hasattr(alt, 'exists') else False:
                    products = _load_from_directory(alt)
                    if products:
                        print(f"Found products at fallback path: {alt}")
                        break

            # Last resort: recursive glob search
            if not products:
                json_files = list(path.rglob('enriched*.json'))
                if json_files:
                    print(f"Found {len(json_files)} enriched files via recursive search")
                    for file_path in sorted(json_files):
                        try:
                            with open(file_path, 'r') as f:
                                data = json.load(f)
                                if isinstance(data, list):
                                    products.extend(data)
                                else:
                                    products.append(data)
                        except (json.JSONDecodeError, IOError) as e:
                            print(f"Warning: Could not load {file_path}: {e}")

    return products


def _load_from_directory(path: Path) -> List[Dict]:
    """Load products from a directory of JSON/JSONL files."""
    products = []

    for file_path in sorted(path.glob('*.json')):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    products.extend(data)
                else:
                    products.append(data)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load {file_path}: {e}")

    for file_path in sorted(path.glob('*.jsonl')):
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    if line.strip():
                        products.append(json.loads(line))
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load {file_path}: {e}")

    return products


def main():
    parser = argparse.ArgumentParser(
        description="Validate format coverage for enriched products"
    )
    parser.add_argument(
        '--input', '-i',
        required=True,
        help='Input file or directory with enriched products'
    )
    parser.add_argument(
        '--format', '-f',
        default='unknown',
        help='Format name (gummy, powder, protein, greens, beverage, lozenge)'
    )
    parser.add_argument(
        '--output', '-o',
        default='reports/',
        help='Output directory for reports'
    )

    args = parser.parse_args()

    # Load products
    print(f"Loading products from: {args.input}")
    products = load_enriched_products(args.input)
    print(f"Loaded {len(products)} products")

    if not products:
        print("No products found!")
        return 1

    # Validate
    validator = FormatCoverageValidator(format_name=args.format)
    report = validator.analyze_batch(products)

    # Save reports
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"coverage_report_{args.format}_{timestamp}.json"
    unknown_path = output_dir / f"unknown_scorable_{args.format}_{timestamp}.json"

    validator.save_report(str(report_path))
    validator.save_unknown_scorable_report(str(unknown_path))

    # Print summary
    print("\n" + "=" * 60)
    print(f"FORMAT COVERAGE REPORT: {args.format.upper()}")
    print("=" * 60)
    print(f"Products analyzed: {report['products_analyzed']}")
    print()
    print("INGREDIENT CLASSIFICATION:")
    print(f"  Scorable: {report['summary']['scorable_percentage']:.1f}%")
    print(f"  Skipped:  {report['summary']['skipped_percentage']:.1f}%")
    print(f"  Unmapped scorable: {report['summary']['unmapped_scorable_percentage']:.1f}%")
    print()
    print("SKIP REASONS:")
    for reason, count in list(report['skip_reasons_breakdown'].items())[:5]:
        print(f"  {reason}: {count}")
    print()
    print("BLEND ANALYSIS:")
    print(f"  Products with blend triggers: {report['blend_analysis']['products_with_blend_triggers']}")
    print(f"  Avg triggers per product: {report['blend_analysis']['avg_blend_triggers_per_product']}")
    print(f"  Dedupe check: {report['blend_analysis']['dedupe_check']}")
    print()
    print("CAUTION TRIGGERS (top 5):")
    for trigger, count in list(report['caution_triggers']['distribution'].items())[:5]:
        print(f"  {trigger}: {count}")
    print()
    print("UNKNOWN SCORABLE INGREDIENTS (top 10):")
    for item in report['unknown_scorable_ingredients']['top_50'][:10]:
        print(f"  {item['name']}: {item['count']}x")
    print()
    print(f"Reports saved to: {output_dir}")
    print(f"  - {report_path.name}")
    print(f"  - {unknown_path.name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
