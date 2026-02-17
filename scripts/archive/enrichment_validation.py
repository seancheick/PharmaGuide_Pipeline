#!/usr/bin/env python3
"""
Post-Enrichment Validation Pipeline
Validates enriched data quality and mapping completeness
"""

import json
import os
import sys
import logging
from datetime import datetime
from typing import Dict, List, Any, Tuple
from pathlib import Path
import argparse

from constants import VALIDATION_THRESHOLDS

class EnrichmentValidator:
    def __init__(self):
        """Initialize validation system"""
        self._setup_logging()
        self.validation_results = {
            "total_products": 0,
            "valid_products": 0,
            "issues_found": [],
            "mapping_stats": {},
            "quality_stats": {}
        }

    def _setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        self.logger = logging.getLogger(__name__)

    def validate_enrichment_directory(self, enrichment_dir: str, cleaned_dir: str) -> Dict:
        """Validate an entire enrichment directory against cleaned input"""
        self.logger.info(f"Starting validation of {enrichment_dir}")

        # Find enriched files
        enriched_files = []
        if os.path.exists(os.path.join(enrichment_dir, "enriched")):
            enriched_path = os.path.join(enrichment_dir, "enriched")
            enriched_files = [f for f in os.listdir(enriched_path) if f.endswith('.json')]

        if not enriched_files:
            self.logger.error(f"No enriched files found in {enrichment_dir}")
            return self.validation_results

        # Find corresponding cleaned files
        cleaned_files = []
        if os.path.exists(cleaned_dir):
            cleaned_files = [f for f in os.listdir(cleaned_dir) if f.endswith('.json')]

        self.logger.info(f"Found {len(enriched_files)} enriched files and {len(cleaned_files)} cleaned files")

        # Validate each enriched file
        for enriched_file in enriched_files:
            enriched_path = os.path.join(enrichment_dir, "enriched", enriched_file)

            # Try to find corresponding cleaned file
            cleaned_file_name = enriched_file.replace("enriched_", "")
            cleaned_path = os.path.join(cleaned_dir, cleaned_file_name)

            if os.path.exists(cleaned_path):
                self._validate_file_pair(enriched_path, cleaned_path)
            else:
                self.logger.warning(f"No corresponding cleaned file found for {enriched_file}")

        # Generate validation report
        return self._generate_validation_report(enrichment_dir)

    def _validate_file_pair(self, enriched_file: str, cleaned_file: str):
        """Validate an enriched file against its cleaned counterpart"""
        try:
            # Load enriched data
            with open(enriched_file, 'r', encoding='utf-8') as f:
                enriched_data = json.load(f)

            # Load cleaned data
            with open(cleaned_file, 'r', encoding='utf-8') as f:
                cleaned_data = json.load(f)

            self.logger.info(f"Validating {os.path.basename(enriched_file)} ({len(enriched_data)} products)")

            # Validate each product
            for i, (enriched_product, cleaned_product) in enumerate(zip(enriched_data, cleaned_data)):
                self._validate_product_pair(enriched_product, cleaned_product, i)

            self.validation_results["total_products"] += len(enriched_data)

        except Exception as e:
            self.logger.error(f"Error validating file pair {enriched_file}: {e}")
            self.validation_results["issues_found"].append({
                "type": "file_validation_error",
                "file": os.path.basename(enriched_file),
                "error": str(e)
            })

    def _validate_product_pair(self, enriched: Dict, cleaned: Dict, index: int):
        """Validate a single product enrichment"""
        product_id = enriched.get('id', f'unknown_{index}')
        issues = []

        # 1. Validate ID consistency
        if enriched.get('id') != cleaned.get('id'):
            issues.append(f"ID mismatch: enriched={enriched.get('id')}, cleaned={cleaned.get('id')}")

        # 2. Validate enrichment completeness
        required_sections = [
            'ingredient_quality_analysis',
            'contaminant_analysis',
            'allergen_compliance',
            'scoring_precalculations'
        ]

        for section in required_sections:
            if section not in enriched:
                issues.append(f"Missing required section: {section}")

        # 3. Validate ingredient mapping completeness
        cleaned_ingredients = []
        if cleaned.get('activeIngredients'):
            cleaned_ingredients.extend([ing.get('name', '') for ing in cleaned['activeIngredients']])
        if cleaned.get('inactiveIngredients'):
            cleaned_ingredients.extend([ing.get('name', '') for ing in cleaned['inactiveIngredients']])

        # Check if all ingredients were processed in quality analysis
        quality_analysis = enriched.get('ingredient_quality_analysis', {})
        form_mapping = quality_analysis.get('form_mapping', [])

        mapped_ingredients = [item.get('ingredient', '') for item in form_mapping]
        unmapped_count = sum(1 for item in form_mapping if item.get('category') == 'unmapped')

        if unmapped_count > 0:
            issues.append(f"Found {unmapped_count} unmapped ingredients")

        # 4. Validate scoring completeness
        scoring = enriched.get('scoring_precalculations', {})
        if not scoring:
            issues.append("Missing scoring precalculations")
        else:
            # Check for required scoring sections
            required_scoring = ['section_a', 'section_b', 'section_c']
            for section in required_scoring:
                if section not in scoring:
                    issues.append(f"Missing scoring section: {section}")

        # 5. Validate contaminant analysis
        contaminant = enriched.get('contaminant_analysis', {})
        if not contaminant:
            issues.append("Missing contaminant analysis")

        # Record results
        if issues:
            self.validation_results["issues_found"].append({
                "type": "product_validation",
                "product_id": product_id,
                "issues": issues
            })
        else:
            self.validation_results["valid_products"] += 1

        # Update mapping stats
        if 'mapping_stats' not in self.validation_results:
            self.validation_results['mapping_stats'] = {"total_ingredients": 0, "mapped": 0, "unmapped": 0}

        self.validation_results['mapping_stats']['total_ingredients'] += len(cleaned_ingredients)
        self.validation_results['mapping_stats']['mapped'] += len(mapped_ingredients) - unmapped_count
        self.validation_results['mapping_stats']['unmapped'] += unmapped_count

    def _generate_validation_report(self, output_dir: str) -> Dict:
        """Generate comprehensive validation report"""
        reports_dir = os.path.join(output_dir, "reports")
        os.makedirs(reports_dir, exist_ok=True)

        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')

        # Calculate success rate
        success_rate = 0
        if self.validation_results["total_products"] > 0:
            success_rate = (self.validation_results["valid_products"] / self.validation_results["total_products"]) * 100

        # Generate JSON report
        detailed_report = {
            "validation_summary": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "total_products_validated": self.validation_results["total_products"],
                "valid_products": self.validation_results["valid_products"],
                "products_with_issues": len([issue for issue in self.validation_results["issues_found"]
                                           if issue["type"] == "product_validation"]),
                "validation_success_rate": round(success_rate, 2)
            },
            "mapping_statistics": self.validation_results.get("mapping_stats", {}),
            "issues_summary": {
                "total_issues": len(self.validation_results["issues_found"]),
                "by_type": {}
            },
            "detailed_issues": self.validation_results["issues_found"]
        }

        # Count issues by type
        for issue in self.validation_results["issues_found"]:
            issue_type = issue["type"]
            if issue_type not in detailed_report["issues_summary"]["by_type"]:
                detailed_report["issues_summary"]["by_type"][issue_type] = 0
            detailed_report["issues_summary"]["by_type"][issue_type] += 1

        # Save JSON report
        json_report_file = os.path.join(reports_dir, f"validation_report_{timestamp}.json")
        with open(json_report_file, 'w', encoding='utf-8') as f:
            json.dump(detailed_report, f, indent=2, ensure_ascii=False)

        # Generate Markdown report
        md_report_file = os.path.join(reports_dir, f"validation_summary_{timestamp}.md")
        with open(md_report_file, 'w', encoding='utf-8') as f:
            f.write("# Enrichment Validation Report\n\n")
            f.write(f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n")

            f.write("## Summary\n\n")
            f.write(f"- **Total Products Validated:** {self.validation_results['total_products']}\n")
            f.write(f"- **Valid Products:** {self.validation_results['valid_products']}\n")
            f.write(f"- **Products with Issues:** {len([issue for issue in self.validation_results['issues_found'] if issue['type'] == 'product_validation'])}\n")
            f.write(f"- **Validation Success Rate:** {success_rate:.2f}%\n\n")

            # Mapping statistics
            mapping_stats = self.validation_results.get("mapping_stats", {})
            if mapping_stats:
                total_ingredients = mapping_stats.get("total_ingredients", 0)
                mapped = mapping_stats.get("mapped", 0)
                unmapped = mapping_stats.get("unmapped", 0)
                mapping_rate = (mapped / total_ingredients * 100) if total_ingredients > 0 else 0

                f.write("## Ingredient Mapping Statistics\n\n")
                f.write(f"- **Total Ingredients:** {total_ingredients}\n")
                f.write(f"- **Successfully Mapped:** {mapped}\n")
                f.write(f"- **Unmapped:** {unmapped}\n")
                f.write(f"- **Mapping Success Rate:** {mapping_rate:.2f}%\n\n")

            # Issues breakdown
            if self.validation_results["issues_found"]:
                f.write("## Issues Found\n\n")
                issue_types = {}
                for issue in self.validation_results["issues_found"]:
                    issue_type = issue["type"]
                    if issue_type not in issue_types:
                        issue_types[issue_type] = []
                    issue_types[issue_type].append(issue)

                for issue_type, issues in issue_types.items():
                    f.write(f"### {issue_type.replace('_', ' ').title()}\n")
                    f.write(f"Count: {len(issues)}\n\n")

                    for issue in issues[:10]:  # Show first 10
                        if issue_type == "product_validation":
                            f.write(f"- **Product {issue['product_id']}:**\n")
                            for sub_issue in issue['issues']:
                                f.write(f"  - {sub_issue}\n")
                        else:
                            f.write(f"- {issue.get('error', 'Unknown error')}\n")

                    if len(issues) > 10:
                        f.write(f"... and {len(issues) - 10} more issues\n")
                    f.write("\n")

            f.write("## Recommendations\n\n")
            if success_rate >= VALIDATION_THRESHOLDS["excellent_success_rate"]:
                f.write("✅ **Excellent**: Validation passed with high success rate\n")
            elif success_rate >= VALIDATION_THRESHOLDS["good_success_rate"]:
                f.write("⚠️ **Good**: Minor issues found, review recommended\n")
            else:
                f.write("❌ **Needs Attention**: Significant issues found, immediate review required\n")

        self.logger.info(f"Validation complete: {success_rate:.2f}% success rate")
        self.logger.info(f"Detailed report: {json_report_file}")
        self.logger.info(f"Summary report: {md_report_file}")

        return detailed_report

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Post-Enrichment Validation Pipeline')
    parser.add_argument('enriched_dir', help='Directory containing enriched data')
    parser.add_argument('cleaned_dir', help='Directory containing cleaned data (for comparison)')
    parser.add_argument('--output', help='Output directory (defaults to enriched_dir)')

    args = parser.parse_args()

    output_dir = args.output or args.enriched_dir

    validator = EnrichmentValidator()
    results = validator.validate_enrichment_directory(args.enriched_dir, args.cleaned_dir)

    # Print summary
    print("\n" + "="*50)
    print("VALIDATION SUMMARY")
    print("="*50)
    print(f"Total Products: {results['validation_summary']['total_products_validated']}")
    print(f"Valid Products: {results['validation_summary']['valid_products']}")
    print(f"Success Rate: {results['validation_summary']['validation_success_rate']:.2f}%")
    print("="*50)

    return 0 if results['validation_summary']['validation_success_rate'] >= VALIDATION_THRESHOLDS["good_success_rate"] else 1

if __name__ == "__main__":
    sys.exit(main())