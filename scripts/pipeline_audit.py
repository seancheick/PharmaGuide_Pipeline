#!/usr/bin/env python3
"""
Pipeline Audit Script
=====================
Runs a full pipeline validation (raw → clean → enrich) and generates
comprehensive audit metrics.

Metrics collected:
- Sugar extraction correctness rates
- Allergen presence_type distribution + dedupe validation
- Colors classification breakdown (natural/artificial/unspecified)
- Probiotic CFU extraction rates for viable cells
- Contract validation summary
- Reference versions verification

Usage:
    python pipeline_audit.py --raw-dir /path/to/raw --sample-size 50
    python pipeline_audit.py --cleaned-dir output_Gummies/cleaned --sample-size 100
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import Counter, defaultdict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3
from enrichment_contract_validator import EnrichmentContractValidator, ContractViolation

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PipelineAuditor:
    """Comprehensive pipeline auditor for validation metrics."""

    def __init__(self):
        self.normalizer = None
        self.enricher = None
        self.validator = EnrichmentContractValidator()
        self.metrics = {
            "sugar": defaultdict(int),
            "allergens": defaultdict(int),
            "colors": defaultdict(int),
            "probiotic_cfu": defaultdict(int),
            "contract_violations": {
                "errors": [],
                "warnings": [],
                "by_rule": Counter()
            },
            "reference_versions": {
                "cleaning": None,
                "enrichment": None
            },
            "products_processed": 0,
            "products_with_issues": []
        }

    def initialize_pipelines(self):
        """Initialize cleaning and enrichment pipelines."""
        logger.info("Initializing pipelines...")

        # Initialize normalizer (cleaning)
        self.normalizer = EnhancedDSLDNormalizer()
        logger.info(f"Normalizer reference_versions: {self.normalizer.reference_versions}")
        self.metrics["reference_versions"]["cleaning"] = self.normalizer.reference_versions

        # Initialize enricher
        self.enricher = SupplementEnricherV3()
        logger.info(f"Enricher reference_versions: {self.enricher.reference_versions}")
        self.metrics["reference_versions"]["enrichment"] = self.enricher.reference_versions

        logger.info("Pipelines initialized successfully")

    def load_raw_products(self, raw_dir: str, sample_size: int = 50) -> List[Dict]:
        """Load raw products from directory."""
        raw_path = Path(raw_dir)
        if not raw_path.exists():
            logger.error(f"Raw directory not found: {raw_dir}")
            return []

        products = []
        json_files = list(raw_path.glob("*.json"))[:sample_size]

        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    product = json.load(f)
                    products.append(product)
            except Exception as e:
                logger.warning(f"Failed to load {json_file}: {e}")

        logger.info(f"Loaded {len(products)} raw products from {raw_dir}")
        return products

    def load_cleaned_products(self, cleaned_dir: str, sample_size: int = 50) -> List[Dict]:
        """Load cleaned products from directory."""
        cleaned_path = Path(cleaned_dir)
        if not cleaned_path.exists():
            logger.error(f"Cleaned directory not found: {cleaned_dir}")
            return []

        products = []
        json_files = list(cleaned_path.glob("*.json"))

        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    batch = json.load(f)
                    if isinstance(batch, list):
                        products.extend(batch[:sample_size - len(products)])
                    elif isinstance(batch, dict) and 'products' in batch:
                        products.extend(batch['products'][:sample_size - len(products)])
                    else:
                        products.append(batch)

                    if len(products) >= sample_size:
                        break
            except Exception as e:
                logger.warning(f"Failed to load {json_file}: {e}")

        logger.info(f"Loaded {len(products)} cleaned products from {cleaned_dir}")
        return products[:sample_size]

    def run_cleaning(self, raw_products: List[Dict]) -> List[Dict]:
        """Run cleaning stage on raw products."""
        cleaned = []
        for product in raw_products:
            try:
                cleaned_product = self.normalizer.normalize(product)
                cleaned.append(cleaned_product)
            except Exception as e:
                logger.warning(f"Cleaning failed for product {product.get('id', 'unknown')}: {e}")

        logger.info(f"Cleaned {len(cleaned)}/{len(raw_products)} products")
        return cleaned

    def run_enrichment(self, cleaned_products: List[Dict]) -> List[Dict]:
        """Run enrichment stage on cleaned products."""
        enriched = []
        for product in cleaned_products:
            try:
                enriched_product, warnings = self.enricher.enrich_product(product)
                enriched.append(enriched_product)
            except Exception as e:
                logger.warning(f"Enrichment failed for product {product.get('id', 'unknown')}: {e}")

        logger.info(f"Enriched {len(enriched)}/{len(cleaned_products)} products")
        return enriched

    def audit_sugar_extraction(self, enriched_products: List[Dict]):
        """Audit sugar extraction metrics."""
        for product in enriched_products:
            product_id = product.get('id', product.get('dsld_id', 'unknown'))
            dietary = product.get('dietary_sensitivity_data', {})
            sugar_data = dietary.get('sugar', {})
            nutritional = product.get('nutritionalInfo', {})

            # Check sugar extraction
            sugar_amount = sugar_data.get('amount_g', 0) or 0
            has_sugar_sources = bool(sugar_data.get('sugar_sources', []))
            contains_sugar = sugar_data.get('contains_sugar', False)
            level = sugar_data.get('level', 'unknown')

            # Count sugar levels
            self.metrics["sugar"]["level_" + level] += 1

            # Check for sugar in nutritionalInfo
            nutritional_sugar = nutritional.get('sugars', {})
            if nutritional_sugar:
                self.metrics["sugar"]["has_nutritional_sugar"] += 1
                if nutritional_sugar.get('amount', 0) > 0:
                    self.metrics["sugar"]["nutritional_sugar_positive"] += 1

            # Check consistency
            if sugar_amount > 0:
                self.metrics["sugar"]["amount_positive"] += 1
                if contains_sugar:
                    self.metrics["sugar"]["amount_positive_contains_sugar_true"] += 1
                else:
                    self.metrics["sugar"]["amount_positive_contains_sugar_false_ERROR"] += 1

            if has_sugar_sources:
                self.metrics["sugar"]["has_sugar_sources"] += 1

            if contains_sugar:
                self.metrics["sugar"]["contains_sugar_true"] += 1
            else:
                self.metrics["sugar"]["contains_sugar_false"] += 1

    def audit_allergen_extraction(self, enriched_products: List[Dict]):
        """Audit allergen extraction and dedupe."""
        for product in enriched_products:
            product_id = product.get('id', product.get('dsld_id', 'unknown'))
            dietary = product.get('dietary_sensitivity_data', {})
            allergens = dietary.get('allergens', []) or []

            if not allergens:
                self.metrics["allergens"]["products_with_no_allergens"] += 1
                continue

            self.metrics["allergens"]["products_with_allergens"] += 1

            # Count presence types
            allergen_ids_seen = defaultdict(list)
            for allergen in allergens:
                allergen_id = allergen.get('allergen_id', allergen.get('allergen_name', 'unknown'))
                presence_type = allergen.get('presence_type', 'unknown')

                self.metrics["allergens"]["presence_" + presence_type] += 1
                allergen_ids_seen[allergen_id].append(presence_type)

            # Check for duplicates
            for allergen_id, types in allergen_ids_seen.items():
                if len(types) > 1:
                    self.metrics["allergens"]["duplicate_allergen_records"] += 1
                    # Check if there's a dedupe issue (contains + weaker)
                    if "contains" in types and len(set(types)) > 1:
                        self.metrics["allergens"]["dedupe_violation_contains_with_weaker"] += 1

            # Check has_may_contain_warning consistency
            has_warning = dietary.get('has_may_contain_warning', False)
            has_may_contain_allergen = any(
                a.get('presence_type') in ('may_contain', 'facility_warning')
                for a in allergens
            )

            if has_warning:
                self.metrics["allergens"]["has_may_contain_warning_true"] += 1
                if has_may_contain_allergen:
                    self.metrics["allergens"]["warning_with_allergen_CORRECT"] += 1
                else:
                    self.metrics["allergens"]["warning_without_allergen_ERROR"] += 1

    def audit_colors_classification(self, cleaned_products: List[Dict], enriched_products: List[Dict]):
        """Audit colors classification (natural/artificial/unspecified)."""
        # Build enriched lookup
        enriched_by_id = {
            p.get('id', p.get('dsld_id')): p for p in enriched_products
        }

        for cleaned in cleaned_products:
            product_id = cleaned.get('id', cleaned.get('dsld_id', 'unknown'))

            # Check all ingredients for color-related standardNames
            all_ingredients = (
                cleaned.get('activeIngredients', []) or []
            ) + (
                cleaned.get('inactiveIngredients', []) or []
            )

            for ing in all_ingredients:
                std_name = (ing.get('standardName', '') or '').lower()
                ing_name = (ing.get('name', '') or '').lower()

                if 'color' in std_name or 'color' in ing_name:
                    if std_name == 'natural colors':
                        self.metrics["colors"]["natural_colors"] += 1
                    elif std_name == 'artificial colors':
                        self.metrics["colors"]["artificial_colors"] += 1
                    elif std_name == 'colors (unspecified)':
                        self.metrics["colors"]["unspecified_colors"] += 1
                    elif 'color' in std_name:
                        self.metrics["colors"]["other_color_standardNames"] += 1

                    # Check if flagged as harmful additive in enriched
                    enriched = enriched_by_id.get(product_id, {})
                    contaminant = enriched.get('contaminant_data', {})
                    harmful = contaminant.get('harmful_additives', {})
                    additives = harmful.get('additives', []) or []

                    for additive in additives:
                        if additive.get('ingredient', '').lower() == ing_name:
                            if 'ARTIFICIAL_COLORS' in additive.get('additive_id', ''):
                                if std_name == 'natural colors':
                                    self.metrics["colors"]["natural_flagged_as_artificial_ERROR"] += 1
                                else:
                                    self.metrics["colors"]["artificial_flagged_correctly"] += 1

    def audit_probiotic_cfu(self, enriched_products: List[Dict]):
        """Audit probiotic CFU extraction for viable cells."""
        for product in enriched_products:
            product_id = product.get('id', product.get('dsld_id', 'unknown'))
            probiotic_data = product.get('probiotic_data', {})

            if not probiotic_data:
                continue

            self.metrics["probiotic_cfu"]["products_with_probiotic_data"] += 1

            is_probiotic = probiotic_data.get('is_probiotic', False)
            if is_probiotic:
                self.metrics["probiotic_cfu"]["is_probiotic_true"] += 1

            # Check blends for CFU
            blends = probiotic_data.get('probiotic_blends', []) or []
            for blend in blends:
                cfu_data = blend.get('cfu_data', {})
                if cfu_data:
                    self.metrics["probiotic_cfu"]["blends_with_cfu_data"] += 1
                    if cfu_data.get('has_cfu', False):
                        self.metrics["probiotic_cfu"]["blends_has_cfu_true"] += 1

                    if cfu_data.get('billion_count', 0) > 0:
                        self.metrics["probiotic_cfu"]["blends_with_billion_count"] += 1

                    guarantee_type = cfu_data.get('guarantee_type')
                    if guarantee_type:
                        self.metrics["probiotic_cfu"]["guarantee_" + guarantee_type] += 1

            # Check for viable cells unit in ingredients
            all_ingredients = (
                product.get('activeIngredients', []) or []
            ) + (
                product.get('inactiveIngredients', []) or []
            )

            for ing in all_ingredients:
                unit = (ing.get('unit', '') or '').lower()
                if 'viable' in unit or 'cell' in unit:
                    self.metrics["probiotic_cfu"]["ingredients_with_viable_cell_unit"] += 1
                    quantity = ing.get('quantity', 0)
                    if quantity and quantity > 0:
                        self.metrics["probiotic_cfu"]["viable_cell_with_quantity"] += 1

    def run_contract_validation(self, enriched_products: List[Dict]):
        """Run contract validator on all enriched products."""
        for product in enriched_products:
            product_id = product.get('id', product.get('dsld_id', 'unknown'))
            violations = self.validator.validate(product)

            for violation in violations:
                self.metrics["contract_violations"]["by_rule"][violation.rule] += 1

                violation_record = {
                    "product_id": product_id,
                    "rule": violation.rule,
                    "rule_name": violation.rule_name,
                    "message": violation.message,
                    "severity": violation.severity
                }

                if violation.severity == "error":
                    self.metrics["contract_violations"]["errors"].append(violation_record)
                else:
                    self.metrics["contract_violations"]["warnings"].append(violation_record)

    def verify_reference_versions(self, cleaned_products: List[Dict], enriched_products: List[Dict]):
        """Verify reference_versions is present in outputs."""
        # Check cleaned
        for product in cleaned_products[:5]:  # Sample
            metadata = product.get('metadata', {})
            ref_vers = metadata.get('reference_versions', {})
            if ref_vers:
                self.metrics["reference_versions"]["cleaning_in_output"] = True
                self.metrics["reference_versions"]["cleaning_sample"] = ref_vers
                break

        # Check enriched
        for product in enriched_products[:5]:  # Sample
            ref_vers = product.get('reference_versions', {})
            if ref_vers:
                self.metrics["reference_versions"]["enrichment_in_output"] = True
                self.metrics["reference_versions"]["enrichment_sample"] = ref_vers
                break

    def run_full_audit(
        self,
        raw_dir: str = None,
        cleaned_dir: str = None,
        sample_size: int = 50
    ) -> Dict:
        """Run full pipeline audit."""
        start_time = datetime.utcnow()

        # Initialize pipelines
        self.initialize_pipelines()

        # Load or generate cleaned products
        if raw_dir:
            raw_products = self.load_raw_products(raw_dir, sample_size)
            cleaned_products = self.run_cleaning(raw_products)
        elif cleaned_dir:
            cleaned_products = self.load_cleaned_products(cleaned_dir, sample_size)
        else:
            logger.error("Must provide either --raw-dir or --cleaned-dir")
            return {}

        if not cleaned_products:
            logger.error("No products to process")
            return {}

        # Run enrichment
        enriched_products = self.run_enrichment(cleaned_products)

        self.metrics["products_processed"] = len(enriched_products)

        # Run all audits
        logger.info("Running sugar extraction audit...")
        self.audit_sugar_extraction(enriched_products)

        logger.info("Running allergen extraction audit...")
        self.audit_allergen_extraction(enriched_products)

        logger.info("Running colors classification audit...")
        self.audit_colors_classification(cleaned_products, enriched_products)

        logger.info("Running probiotic CFU audit...")
        self.audit_probiotic_cfu(enriched_products)

        logger.info("Running contract validation...")
        self.run_contract_validation(enriched_products)

        logger.info("Verifying reference versions...")
        self.verify_reference_versions(cleaned_products, enriched_products)

        # Calculate duration
        end_time = datetime.utcnow()
        self.metrics["duration_seconds"] = (end_time - start_time).total_seconds()
        self.metrics["timestamp"] = end_time.isoformat() + "Z"

        return self.metrics

    def print_report(self):
        """Print formatted audit report."""
        print("\n" + "=" * 80)
        print("PIPELINE AUDIT REPORT")
        print("=" * 80)
        print(f"Products Processed: {self.metrics['products_processed']}")
        print(f"Duration: {self.metrics.get('duration_seconds', 0):.2f}s")
        print(f"Timestamp: {self.metrics.get('timestamp', 'N/A')}")

        # Reference Versions
        print("\n" + "-" * 80)
        print("REFERENCE VERSIONS")
        print("-" * 80)
        ref = self.metrics["reference_versions"]
        print(f"Cleaning Pipeline:")
        print(f"  color_indicators: {ref.get('cleaning', {}).get('color_indicators', {})}")
        print(f"Enrichment Pipeline:")
        print(f"  color_indicators: {ref.get('enrichment', {}).get('color_indicators', {})}")
        print(f"In Cleaned Output: {ref.get('cleaning_in_output', False)}")
        print(f"In Enriched Output: {ref.get('enrichment_in_output', False)}")

        # Sugar Metrics
        print("\n" + "-" * 80)
        print("SUGAR EXTRACTION METRICS")
        print("-" * 80)
        sugar = self.metrics["sugar"]
        for key, value in sorted(sugar.items()):
            status = "ERROR" if "ERROR" in key else ""
            print(f"  {key}: {value} {status}")

        # Allergen Metrics
        print("\n" + "-" * 80)
        print("ALLERGEN PRESENCE_TYPE DISTRIBUTION")
        print("-" * 80)
        allergens = self.metrics["allergens"]
        for key, value in sorted(allergens.items()):
            status = "ERROR" if "ERROR" in key or "violation" in key else ""
            print(f"  {key}: {value} {status}")

        # Colors Metrics
        print("\n" + "-" * 80)
        print("COLORS CLASSIFICATION BREAKDOWN")
        print("-" * 80)
        colors = self.metrics["colors"]
        for key, value in sorted(colors.items()):
            status = "ERROR" if "ERROR" in key else ""
            print(f"  {key}: {value} {status}")

        # Probiotic CFU Metrics
        print("\n" + "-" * 80)
        print("PROBIOTIC CFU EXTRACTION RATES")
        print("-" * 80)
        cfu = self.metrics["probiotic_cfu"]
        for key, value in sorted(cfu.items()):
            print(f"  {key}: {value}")

        # Contract Validation Summary
        print("\n" + "-" * 80)
        print("CONTRACT VALIDATION SUMMARY")
        print("-" * 80)
        cv = self.metrics["contract_violations"]
        print(f"Total ERRORS: {len(cv['errors'])}")
        print(f"Total WARNINGS: {len(cv['warnings'])}")
        print("\nViolations by Rule:")
        for rule, count in sorted(cv["by_rule"].items()):
            print(f"  {rule}: {count}")

        if cv["errors"]:
            print("\nERROR Violations (product IDs):")
            for error in cv["errors"][:10]:  # Limit output
                print(f"  [{error['rule']}] {error['product_id']}: {error['message'][:60]}...")
            if len(cv["errors"]) > 10:
                print(f"  ... and {len(cv['errors']) - 10} more")

        print("\n" + "=" * 80)
        print("END OF REPORT")
        print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description='Pipeline Audit Tool')
    parser.add_argument('--raw-dir', help='Directory containing raw DSLD data')
    parser.add_argument('--cleaned-dir', help='Directory containing cleaned data')
    parser.add_argument('--sample-size', type=int, default=50, help='Number of products to audit')
    parser.add_argument('--output', help='Output file for JSON report')

    args = parser.parse_args()

    if not args.raw_dir and not args.cleaned_dir:
        # Default to existing cleaned data
        args.cleaned_dir = "output_Gummies/cleaned"

    auditor = PipelineAuditor()
    metrics = auditor.run_full_audit(
        raw_dir=args.raw_dir,
        cleaned_dir=args.cleaned_dir,
        sample_size=args.sample_size
    )

    auditor.print_report()

    if args.output:
        # Convert defaultdicts to regular dicts for JSON serialization
        def convert_defaultdict(d):
            if isinstance(d, defaultdict):
                d = dict(d)
            if isinstance(d, dict):
                return {k: convert_defaultdict(v) for k, v in d.items()}
            if isinstance(d, Counter):
                return dict(d)
            return d

        metrics_json = convert_defaultdict(metrics)
        with open(args.output, 'w') as f:
            json.dump(metrics_json, f, indent=2, default=str)
        print(f"\nJSON report saved to: {args.output}")


if __name__ == "__main__":
    main()
