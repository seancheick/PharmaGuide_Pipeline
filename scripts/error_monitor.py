#!/usr/bin/env python3
"""
Error Monitor for DSLD Data Cleaning Pipeline
Helps track and identify data quality issues
"""

import os
import json
import glob
import re
from pathlib import Path
from typing import List, Dict, Tuple

def find_unit_conversion_issues(data_directories: List[str]) -> List[Dict]:
    """Find potential unit conversion issues in source data"""
    issues = []

    # Common suspicious unit combinations
    suspicious_combinations = [
        ("ng", ["mg", "mcg"]),  # nanogram to milligram/microgram
        ("ug", ["mg"]),         # microgram (alternate spelling)
        ("g", ["mcg"]),         # gram to microgram (too large jump)
    ]

    for data_dir in data_directories:
        if not os.path.exists(data_dir):
            continue

        json_files = glob.glob(f"{data_dir}/**/*.json", recursive=True)

        for file_path in json_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Check ingredient rows
                if 'ingredientRows' in data:
                    for ingredient in data['ingredientRows']:
                        name = ingredient.get('name', '')

                        if 'quantity' in ingredient and ingredient['quantity']:
                            for qty_info in ingredient['quantity']:
                                unit = qty_info.get('unit', '').lower()
                                quantity = qty_info.get('quantity', 0)

                                # Check for suspicious combinations
                                for sus_from, sus_to_list in suspicious_combinations:
                                    if unit == sus_from:
                                        issues.append({
                                            'file': file_path,
                                            'product_id': data.get('id', 'unknown'),
                                            'product_name': data.get('fullName', 'unknown'),
                                            'ingredient': name,
                                            'quantity': quantity,
                                            'unit': unit,
                                            'issue_type': 'suspicious_unit',
                                            'description': f"Ingredient '{name}' has {unit} units - might be typo"
                                        })

            except (json.JSONDecodeError, KeyError, TypeError) as e:
                issues.append({
                    'file': file_path,
                    'product_id': 'unknown',
                    'product_name': 'unknown',
                    'ingredient': 'unknown',
                    'quantity': 0,
                    'unit': 'unknown',
                    'issue_type': 'file_error',
                    'description': f"Error reading file: {str(e)}"
                })

    return issues

def find_extreme_dosages(data_directories: List[str]) -> List[Dict]:
    """Find ingredients with extremely high or low dosages"""
    issues = []

    # Define normal ranges for common ingredients (in mg)
    normal_ranges = {
        'vitamin c': (10, 2000),
        'zinc': (1, 50),
        'vitamin d': (0.01, 0.1),  # Usually in mcg
        'vitamin b12': (0.001, 1),  # Usually in mcg
        'calcium': (50, 1500),
        'magnesium': (50, 800),
        'iron': (1, 50)
    }

    for data_dir in data_directories:
        if not os.path.exists(data_dir):
            continue

        json_files = glob.glob(f"{data_dir}/**/*.json", recursive=True)

        for file_path in json_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                if 'ingredientRows' in data:
                    for ingredient in data['ingredientRows']:
                        name = ingredient.get('name', '').lower()

                        if 'quantity' in ingredient and ingredient['quantity']:
                            for qty_info in ingredient['quantity']:
                                unit = qty_info.get('unit', '').lower()
                                quantity = qty_info.get('quantity', 0)

                                # Check if ingredient is in our watchlist
                                for ingredient_key, (min_dose, max_dose) in normal_ranges.items():
                                    if ingredient_key in name and unit in ['mg', 'milligram']:
                                        if quantity < min_dose or quantity > max_dose:
                                            issues.append({
                                                'file': file_path,
                                                'product_id': data.get('id', 'unknown'),
                                                'product_name': data.get('fullName', 'unknown'),
                                                'ingredient': ingredient.get('name', ''),
                                                'quantity': quantity,
                                                'unit': unit,
                                                'issue_type': 'extreme_dosage',
                                                'description': f"Dosage {quantity}{unit} outside normal range {min_dose}-{max_dose}mg"
                                            })

            except (json.JSONDecodeError, KeyError, TypeError) as e:
                continue

    return issues

def search_logs_for_errors(log_directory: str) -> List[Dict]:
    """Search log files for WARNING and ERROR messages"""
    issues = []
    log_dir = Path(log_directory)

    if not log_dir.exists():
        return issues

    log_files = list(log_dir.glob("*.log"))

    for log_file in log_files:
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    if 'WARNING' in line or 'ERROR' in line:
                        issues.append({
                            'file': str(log_file),
                            'line_number': line_num,
                            'message': line.strip(),
                            'issue_type': 'log_warning' if 'WARNING' in line else 'log_error',
                            'timestamp': log_file.stem.replace('dsld_cleaning_', '')
                        })
        except Exception as e:
            continue

    return issues

def generate_error_report(output_path: str, data_directories: List[str], log_directory: str):
    """Generate comprehensive error report"""

    print("🔍 Scanning for data quality issues...")

    # Collect all issues
    unit_issues = find_unit_conversion_issues(data_directories)
    dosage_issues = find_extreme_dosages(data_directories)
    log_issues = search_logs_for_errors(log_directory)

    # Generate report
    report = {
        'summary': {
            'unit_conversion_issues': len(unit_issues),
            'extreme_dosage_issues': len(dosage_issues),
            'log_warnings_errors': len(log_issues),
            'total_issues': len(unit_issues) + len(dosage_issues) + len(log_issues)
        },
        'unit_conversion_issues': unit_issues,
        'extreme_dosage_issues': dosage_issues,
        'log_issues': log_issues
    }

    # Save report
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Print summary
    print(f"\n📊 ERROR REPORT SUMMARY:")
    print(f"   Unit conversion issues: {len(unit_issues)}")
    print(f"   Extreme dosage issues: {len(dosage_issues)}")
    print(f"   Log warnings/errors: {len(log_issues)}")
    print(f"   Total issues found: {report['summary']['total_issues']}")
    print(f"\n💾 Detailed report saved to: {output_path}")

    return report

if __name__ == "__main__":
    # Configuration
    DATA_DIRECTORIES = [
        "/Users/seancheick/Documents/DataSetDsld/Lozenges-978labels-11-11-25",
        "/Users/seancheick/Documents/DataSetDsld/Tablets-Pills-32882Labels-8-6-25",
        "/Users/seancheick/Documents/DataSetDsld/Capsules-44920labels-2019-2025-8-6-25",
        "/Users/seancheick/Documents/DataSetDsld/Softgels-19416labels-8-6-25"
    ]

    LOG_DIRECTORY = "/Users/seancheick/Downloads/dsld_clean/logs"
    OUTPUT_PATH = "/Users/seancheick/Downloads/dsld_clean/data_quality_report.json"

    # Generate report
    generate_error_report(OUTPUT_PATH, DATA_DIRECTORIES, LOG_DIRECTORY)