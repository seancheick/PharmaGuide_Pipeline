#!/usr/bin/env python3
"""
Enhanced Enrichment Reporting System
Provides comprehensive reporting for supplement data processing failures and successes
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import traceback

class EnrichmentReporter:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.reports_dir = os.path.join(output_dir, "reports")
        self.detailed_failures = []
        self.summary_stats = {
            "total_processed": 0,
            "successful": 0,
            "failed": 0,
            "failure_categories": {},
            "processing_start": None,
            "processing_end": None
        }
        
        # Ensure reports directory exists
        os.makedirs(self.reports_dir, exist_ok=True)
        
    def start_processing(self):
        """Mark the start of processing"""
        self.summary_stats["processing_start"] = datetime.utcnow().isoformat() + "Z"
        
    def end_processing(self):
        """Mark the end of processing"""
        self.summary_stats["processing_end"] = datetime.utcnow().isoformat() + "Z"
        
    def analyze_enrichment_failure(self, product_data: Dict, error_message: str, enriched_data: Optional[Dict] = None) -> Dict:
        """Analyze why enrichment failed and categorize the failure"""
        
        product_id = product_data.get('id', 'unknown')
        product_name = product_data.get('fullName', 'Unknown Product')
        
        failure_analysis = {
            "product_id": product_id,
            "product_name": product_name,
            "brand_name": product_data.get('brandName', ''),
            "failure_timestamp": datetime.utcnow().isoformat() + "Z",
            "error_message": error_message,
            "failure_category": "unknown",
            "failure_subcategory": "unknown",
            "missing_data_fields": [],
            "data_quality_issues": [],
            "actionable_steps": [],
            "source_file_reference": "",
            "enrichment_completeness": 0.0,
            "specific_issues": {}
        }
        
        # Analyze different failure types
        if "Enrichment failed:" in error_message:
            failure_analysis["failure_category"] = "processing_error"
            failure_analysis["failure_subcategory"] = "exception_during_enrichment"
            
            # Extract specific error details
            if "KeyError" in error_message:
                failure_analysis["failure_subcategory"] = "missing_required_field"
                failure_analysis["actionable_steps"].append("Check input data structure for missing required fields")
            elif "TypeError" in error_message:
                failure_analysis["failure_subcategory"] = "data_type_mismatch"
                failure_analysis["actionable_steps"].append("Validate data types in input file")
            elif "ValueError" in error_message:
                failure_analysis["failure_subcategory"] = "invalid_data_value"
                failure_analysis["actionable_steps"].append("Check for invalid or malformed data values")
        
        # Analyze data completeness issues
        active_ingredients = product_data.get('activeIngredients', [])
        inactive_ingredients = product_data.get('inactiveIngredients', [])
        
        if not active_ingredients:
            failure_analysis["missing_data_fields"].append("activeIngredients")
            failure_analysis["failure_category"] = "data_completeness"
            failure_analysis["failure_subcategory"] = "missing_active_ingredients"
            failure_analysis["actionable_steps"].append("Add active ingredients data to source file")
        
        # Check for ingredient mapping issues
        if active_ingredients:
            unmapped_ingredients = []
            for ingredient in active_ingredients:
                if not ingredient.get('mapped', True):  # Assume mapped=True if not specified
                    unmapped_ingredients.append(ingredient.get('name', 'unknown'))
            
            if unmapped_ingredients:
                failure_analysis["failure_category"] = "ingredient_mapping"
                failure_analysis["failure_subcategory"] = "unmapped_ingredients"
                failure_analysis["specific_issues"]["unmapped_ingredients"] = unmapped_ingredients
                failure_analysis["actionable_steps"].append(f"Add mappings for ingredients: {', '.join(unmapped_ingredients)}")
        
        # Check for missing essential product data
        essential_fields = ['id', 'fullName', 'brandName', 'activeIngredients']
        missing_essential = [field for field in essential_fields if not product_data.get(field)]
        
        if missing_essential:
            failure_analysis["missing_data_fields"].extend(missing_essential)
            failure_analysis["failure_category"] = "data_completeness"
            failure_analysis["failure_subcategory"] = "missing_essential_fields"
            failure_analysis["actionable_steps"].append(f"Add missing essential fields: {', '.join(missing_essential)}")
        
        # Analyze partial enrichment if enriched_data is available
        if enriched_data:
            completeness = self._calculate_enrichment_completeness(enriched_data)
            failure_analysis["enrichment_completeness"] = completeness
            
            if completeness > 0:
                failure_analysis["failure_category"] = "partial_enrichment"
                failure_analysis["failure_subcategory"] = "incomplete_analysis"
                failure_analysis["actionable_steps"].append("Review partial enrichment data for missing analysis sections")
        
        # Data quality checks
        quality_issues = self._identify_data_quality_issues(product_data)
        failure_analysis["data_quality_issues"] = quality_issues
        
        if quality_issues:
            if failure_analysis["failure_category"] == "unknown":
                failure_analysis["failure_category"] = "data_quality"
                failure_analysis["failure_subcategory"] = "quality_issues_detected"
            
            for issue in quality_issues:
                failure_analysis["actionable_steps"].append(f"Fix data quality issue: {issue}")
        
        # Set default actionable steps if none identified
        if not failure_analysis["actionable_steps"]:
            failure_analysis["actionable_steps"] = [
                "Review error message for specific details",
                "Validate input data structure and completeness",
                "Check enrichment script logs for additional context"
            ]
        
        return failure_analysis
    
    def _calculate_enrichment_completeness(self, enriched_data: Dict) -> float:
        """Calculate how complete the enrichment is (0-100%)"""
        required_sections = [
            'form_quality_mapping',
            'ingredient_quality_analysis', 
            'contaminant_analysis',
            'clinical_evidence_matches',
            'scoring_precalculations'
        ]
        
        completed_sections = 0
        for section in required_sections:
            if section in enriched_data and enriched_data[section]:
                completed_sections += 1
        
        return (completed_sections / len(required_sections)) * 100
    
    def _identify_data_quality_issues(self, product_data: Dict) -> List[str]:
        """Identify specific data quality issues"""
        issues = []
        
        # Check for empty or invalid IDs
        product_id = product_data.get('id', '')
        if not product_id or product_id == 'unknown':
            issues.append("Missing or invalid product ID")
        
        # Check for missing product name
        if not product_data.get('fullName', '').strip():
            issues.append("Missing product name")
        
        # Check for missing brand
        if not product_data.get('brandName', '').strip():
            issues.append("Missing brand name")
        
        # Check ingredient data quality
        active_ingredients = product_data.get('activeIngredients', [])
        for i, ingredient in enumerate(active_ingredients):
            if not ingredient.get('name', '').strip():
                issues.append(f"Active ingredient {i+1} missing name")
            
            if not ingredient.get('quantity') and ingredient.get('quantity') != 0:
                issues.append(f"Active ingredient '{ingredient.get('name', 'unknown')}' missing quantity")
            
            if not ingredient.get('unit', '').strip():
                issues.append(f"Active ingredient '{ingredient.get('name', 'unknown')}' missing unit")
        
        # Check for suspicious data patterns
        if len(active_ingredients) == 0:
            issues.append("No active ingredients listed")
        elif len(active_ingredients) > 50:
            issues.append("Unusually high number of active ingredients (>50) - may indicate data parsing issues")
        
        return issues
    
    def record_failure(self, product_data: Dict, error_message: str, enriched_data: Optional[Dict] = None, source_file: str = ""):
        """Record a detailed failure analysis"""
        failure_analysis = self.analyze_enrichment_failure(product_data, error_message, enriched_data)
        failure_analysis["source_file_reference"] = source_file
        
        self.detailed_failures.append(failure_analysis)
        
        # Update summary stats
        self.summary_stats["failed"] += 1
        
        # Update failure category counts
        category = failure_analysis["failure_category"]
        if category not in self.summary_stats["failure_categories"]:
            self.summary_stats["failure_categories"][category] = 0
        self.summary_stats["failure_categories"][category] += 1
    
    def record_success(self, product_data: Dict, enriched_data: Dict):
        """Record a successful enrichment"""
        self.summary_stats["successful"] += 1
        
        # Could add success analysis here if needed
        # e.g., track enrichment quality scores, completeness, etc.
    
    def update_total_processed(self, count: int):
        """Update total processed count"""
        self.summary_stats["total_processed"] += count
    
    def generate_detailed_failure_report(self) -> str:
        """Generate detailed failure report in JSON format"""
        
        # Categorize failures for better organization
        categorized_failures = {}
        for failure in self.detailed_failures:
            category = failure["failure_category"]
            if category not in categorized_failures:
                categorized_failures[category] = []
            categorized_failures[category].append(failure)
        
        detailed_report = {
            "report_metadata": {
                "report_type": "detailed_failure_analysis",
                "generated_timestamp": datetime.utcnow().isoformat() + "Z",
                "enrichment_version": "2.0.0",
                "total_failures_analyzed": len(self.detailed_failures)
            },
            "failure_summary": {
                "total_failures": len(self.detailed_failures),
                "failure_categories": dict(self.summary_stats["failure_categories"]),
                "most_common_failure": max(self.summary_stats["failure_categories"].items(), key=lambda x: x[1])[0] if self.summary_stats["failure_categories"] else "none"
            },
            "categorized_failures": categorized_failures,
            "actionable_insights": self._generate_actionable_insights(),
            "recommended_fixes": self._generate_recommended_fixes()
        }
        
        # Save detailed report
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        report_file = os.path.join(self.reports_dir, f"detailed_failure_report_{timestamp}.json")
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(detailed_report, f, indent=2, ensure_ascii=False)
        
        return report_file
    
    def generate_human_readable_report(self) -> str:
        """Generate human-readable failure report"""
        
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        report_file = os.path.join(self.reports_dir, f"failure_analysis_report_{timestamp}.md")
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("# Enrichment Failure Analysis Report\n\n")
            f.write(f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
            f.write(f"**Total Failures Analyzed:** {len(self.detailed_failures)}\n\n")
            
            # Summary section
            f.write("## Summary\n\n")
            f.write(f"- **Total Products Processed:** {self.summary_stats['total_processed']}\n")
            f.write(f"- **Successful Enrichments:** {self.summary_stats['successful']}\n")
            f.write(f"- **Failed Enrichments:** {self.summary_stats['failed']}\n")
            
            if self.summary_stats['total_processed'] > 0:
                success_rate = (self.summary_stats['successful'] / self.summary_stats['total_processed']) * 100
                f.write(f"- **Success Rate:** {success_rate:.1f}%\n")
            
            f.write("\n## Failure Categories\n\n")
            for category, count in self.summary_stats["failure_categories"].items():
                percentage = (count / len(self.detailed_failures)) * 100 if self.detailed_failures else 0
                f.write(f"- **{category.replace('_', ' ').title()}:** {count} failures ({percentage:.1f}%)\n")
            
            # Detailed failures by category
            categorized_failures = {}
            for failure in self.detailed_failures:
                category = failure["failure_category"]
                if category not in categorized_failures:
                    categorized_failures[category] = []
                categorized_failures[category].append(failure)
            
            f.write("\n## Detailed Failure Analysis\n\n")
            
            for category, failures in categorized_failures.items():
                f.write(f"### {category.replace('_', ' ').title()} ({len(failures)} failures)\n\n")
                
                for i, failure in enumerate(failures[:10], 1):  # Limit to first 10 per category
                    f.write(f"#### {i}. {failure['product_name']} (ID: {failure['product_id']})\n\n")
                    f.write(f"**Brand:** {failure['brand_name']}\n")
                    f.write(f"**Error:** {failure['error_message']}\n")
                    
                    if failure['missing_data_fields']:
                        f.write(f"**Missing Fields:** {', '.join(failure['missing_data_fields'])}\n")
                    
                    if failure['data_quality_issues']:
                        f.write("**Data Quality Issues:**\n")
                        for issue in failure['data_quality_issues']:
                            f.write(f"- {issue}\n")
                    
                    f.write("**Recommended Actions:**\n")
                    for action in failure['actionable_steps']:
                        f.write(f"- {action}\n")
                    
                    f.write("\n---\n\n")
                
                if len(failures) > 10:
                    f.write(f"*... and {len(failures) - 10} more failures in this category*\n\n")
            
            # Actionable insights
            insights = self._generate_actionable_insights()
            f.write("## Key Insights & Recommendations\n\n")
            
            for insight in insights:
                f.write(f"### {insight['title']}\n\n")
                f.write(f"{insight['description']}\n\n")
                f.write("**Recommended Actions:**\n")
                for action in insight['actions']:
                    f.write(f"- {action}\n")
                f.write("\n")
        
        return report_file
    
    def generate_summary_report(self) -> str:
        """Generate executive summary report"""
        
        processing_time = None
        if self.summary_stats["processing_start"] and self.summary_stats["processing_end"]:
            start = datetime.fromisoformat(self.summary_stats["processing_start"].replace('Z', '+00:00'))
            end = datetime.fromisoformat(self.summary_stats["processing_end"].replace('Z', '+00:00'))
            processing_time = (end - start).total_seconds()
        
        summary_report = {
            "report_metadata": {
                "report_type": "enrichment_summary",
                "generated_timestamp": datetime.utcnow().isoformat() + "Z",
                "enrichment_version": "2.0.0"
            },
            "processing_summary": {
                "total_products_processed": self.summary_stats["total_processed"],
                "successful_enrichments": self.summary_stats["successful"],
                "failed_enrichments": self.summary_stats["failed"],
                "success_rate_percentage": round((self.summary_stats["successful"] / self.summary_stats["total_processed"]) * 100, 1) if self.summary_stats["total_processed"] > 0 else 0,
                "processing_start_time": self.summary_stats["processing_start"],
                "processing_end_time": self.summary_stats["processing_end"],
                "total_processing_time_seconds": round(processing_time, 2) if processing_time else None
            },
            "failure_breakdown": {
                "failure_categories": dict(self.summary_stats["failure_categories"]),
                "top_failure_reasons": self._get_top_failure_reasons(),
                "data_quality_issues_count": self._count_data_quality_issues(),
                "actionable_items_count": len(self.detailed_failures)
            },
            "recommendations": {
                "immediate_actions": self._get_immediate_actions(),
                "data_improvement_priorities": self._get_data_improvement_priorities(),
                "system_improvements": self._get_system_improvements()
            }
        }
        
        # Save summary report
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        report_file = os.path.join(self.reports_dir, f"enrichment_summary_{timestamp}.json")
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(summary_report, f, indent=2, ensure_ascii=False)
        
        return report_file
    
    def _generate_actionable_insights(self) -> List[Dict]:
        """Generate actionable insights from failure patterns"""
        insights = []
        
        # Analyze failure patterns
        category_counts = self.summary_stats["failure_categories"]
        
        if category_counts.get("data_completeness", 0) > 0:
            insights.append({
                "title": "Data Completeness Issues",
                "description": f"Found {category_counts['data_completeness']} products with missing essential data fields.",
                "actions": [
                    "Review data extraction process for completeness",
                    "Implement validation checks before enrichment",
                    "Identify and fix data source issues"
                ]
            })
        
        if category_counts.get("ingredient_mapping", 0) > 0:
            insights.append({
                "title": "Ingredient Mapping Failures",
                "description": f"Found {category_counts['ingredient_mapping']} products with unmapped ingredients.",
                "actions": [
                    "Expand ingredient quality mapping database",
                    "Review unmapped ingredients for common patterns",
                    "Add aliases for commonly missed ingredient names"
                ]
            })
        
        if category_counts.get("processing_error", 0) > 0:
            insights.append({
                "title": "Processing Errors",
                "description": f"Found {category_counts['processing_error']} products that failed during enrichment processing.",
                "actions": [
                    "Review error logs for common exception patterns",
                    "Improve error handling in enrichment script",
                    "Add input validation before processing"
                ]
            })
        
        return insights
    
    def _generate_recommended_fixes(self) -> List[Dict]:
        """Generate specific recommended fixes"""
        fixes = []
        
        # Analyze common issues across failures
        common_missing_fields = {}
        common_quality_issues = {}
        
        for failure in self.detailed_failures:
            for field in failure["missing_data_fields"]:
                common_missing_fields[field] = common_missing_fields.get(field, 0) + 1
            
            for issue in failure["data_quality_issues"]:
                common_quality_issues[issue] = common_quality_issues.get(issue, 0) + 1
        
        # Generate fixes for most common issues
        if common_missing_fields:
            most_common_field = max(common_missing_fields.items(), key=lambda x: x[1])
            fixes.append({
                "issue": f"Missing field: {most_common_field[0]}",
                "frequency": most_common_field[1],
                "fix_type": "data_source",
                "recommended_action": f"Ensure {most_common_field[0]} is populated in source data",
                "priority": "high" if most_common_field[1] > len(self.detailed_failures) * 0.5 else "medium"
            })
        
        if common_quality_issues:
            most_common_issue = max(common_quality_issues.items(), key=lambda x: x[1])
            fixes.append({
                "issue": most_common_issue[0],
                "frequency": most_common_issue[1],
                "fix_type": "data_quality",
                "recommended_action": f"Implement validation to prevent: {most_common_issue[0]}",
                "priority": "high" if most_common_issue[1] > len(self.detailed_failures) * 0.3 else "medium"
            })
        
        return fixes
    
    def _get_top_failure_reasons(self) -> List[Dict]:
        """Get top failure reasons with counts"""
        subcategory_counts = {}
        
        for failure in self.detailed_failures:
            subcategory = failure["failure_subcategory"]
            subcategory_counts[subcategory] = subcategory_counts.get(subcategory, 0) + 1
        
        # Sort by frequency and return top 5
        sorted_reasons = sorted(subcategory_counts.items(), key=lambda x: x[1], reverse=True)
        
        return [
            {"reason": reason, "count": count, "percentage": round((count / len(self.detailed_failures)) * 100, 1)}
            for reason, count in sorted_reasons[:5]
        ]
    
    def _count_data_quality_issues(self) -> int:
        """Count total data quality issues across all failures"""
        total_issues = 0
        for failure in self.detailed_failures:
            total_issues += len(failure["data_quality_issues"])
        return total_issues
    
    def _get_immediate_actions(self) -> List[str]:
        """Get immediate actions needed"""
        actions = []
        
        if self.summary_stats["failed"] > 0:
            actions.append(f"Review {self.summary_stats['failed']} failed enrichments")
        
        if self.summary_stats["failure_categories"].get("data_completeness", 0) > 0:
            actions.append("Fix missing data fields in source files")
        
        if self.summary_stats["failure_categories"].get("processing_error", 0) > 0:
            actions.append("Investigate processing errors and improve error handling")
        
        return actions
    
    def _get_data_improvement_priorities(self) -> List[str]:
        """Get data improvement priorities"""
        priorities = []
        
        # Analyze failure patterns to determine priorities
        category_counts = self.summary_stats["failure_categories"]
        total_failures = sum(category_counts.values())
        
        if total_failures > 0:
            for category, count in category_counts.items():
                percentage = (count / total_failures) * 100
                if percentage > 20:  # If category represents >20% of failures
                    priorities.append(f"Address {category.replace('_', ' ')} issues ({percentage:.1f}% of failures)")
        
        return priorities
    
    def _get_system_improvements(self) -> List[str]:
        """Get system improvement recommendations"""
        improvements = []
        
        if len(self.detailed_failures) > 0:
            improvements.append("Implement pre-processing validation to catch issues early")
            improvements.append("Add more detailed error logging for better debugging")
            improvements.append("Create automated data quality checks")
        
        if self.summary_stats["failure_categories"].get("ingredient_mapping", 0) > 0:
            improvements.append("Expand ingredient mapping database coverage")
        
        return improvements
    
    def generate_all_reports(self) -> Dict[str, str]:
        """Generate all report types and return file paths"""
        self.end_processing()
        
        report_files = {
            "summary_report": self.generate_summary_report(),
            "detailed_failure_report": self.generate_detailed_failure_report(),
            "human_readable_report": self.generate_human_readable_report()
        }
        
        return report_files

def main():
    """Test the reporting system"""
    reporter = EnrichmentReporter("test_output")
    reporter.start_processing()
    
    # Simulate some failures for testing
    test_product = {
        "id": "12345",
        "fullName": "Test Product",
        "brandName": "Test Brand",
        "activeIngredients": []
    }
    
    reporter.record_failure(test_product, "Enrichment failed: Missing active ingredients", source_file="test.json")
    reporter.update_total_processed(1)
    
    # Generate reports
    report_files = reporter.generate_all_reports()
    
    print("Generated reports:")
    for report_type, file_path in report_files.items():
        print(f"- {report_type}: {file_path}")

if __name__ == "__main__":
    main()