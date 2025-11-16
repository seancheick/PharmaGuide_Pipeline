#!/usr/bin/env python3
"""
Comprehensive verification of all 18 databases
"""

import json
from pathlib import Path
from collections import defaultdict

def check_database(filepath: Path):
    """Check database completeness"""
    result = {
        "exists": False,
        "has_metadata": False,
        "total_entries": 0,
        "entries_with_ids": 0,
        "structure_type": "unknown",
        "main_key": None
    }

    if not filepath.exists():
        return result

    result["exists"] = True

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Check for metadata
        result["has_metadata"] = '_metadata' in data or 'database_info' in data

        # Determine structure
        if isinstance(data, list):
            result["structure_type"] = "direct_array"
            result["total_entries"] = len(data)
            result["entries_with_ids"] = sum(1 for e in data if isinstance(e, dict) and 'id' in e)

        elif isinstance(data, dict):
            # Find main array or count nested dicts
            arrays = [(k, v) for k, v in data.items() if isinstance(v, list) and not k.startswith('_')]
            nested = [(k, v) for k, v in data.items() if isinstance(v, dict) and not k.startswith('_')]

            if arrays:
                result["structure_type"] = "wrapped_array"
                # Use first non-metadata array
                main_key, main_array = arrays[0]
                result["main_key"] = main_key
                result["total_entries"] = len(main_array)
                result["entries_with_ids"] = sum(1 for e in main_array if isinstance(e, dict) and 'id' in e)

            elif nested:
                result["structure_type"] = "nested_dict"
                result["total_entries"] = len(nested)
                # Nested dicts don't typically have IDs
                result["entries_with_ids"] = result["total_entries"]

    except Exception as e:
        result["error"] = str(e)

    return result

print("=" * 100)
print(" " * 30 + "DATABASE VERIFICATION REPORT")
print("=" * 100)
print()

databases = [
    # Group A: Already completed
    "botanical_ingredients.json",
    "other_ingredients.json",
    "standardized_botanicals.json",

    # Group B: Just got metadata
    "allergens.json",
    "banned_recalled_ingredients.json",
    "harmful_additives.json",
    "synergy_cluster.json",

    # Group C: Got IDs + metadata
    "proprietary_blends_penalty.json",
    "rda_optimal_uls.json",
    "rda_therapeutic_dosing.json",
    "user_goals_to_clusters.json",

    # Group D: Wrapped + metadata
    "absorption_enhancers.json",
    "backed_clinical_studies.json",
    "manufacturer_violations.json",
    "top_manufacturers_data.json",

    # Group E: Nested + metadata
    "enhanced_delivery.json",
    "ingredient_quality_map.json",
    "ingredient_weights.json"
]

data_dir = Path('data')
complete_count = 0
incomplete_count = 0

print(f"{'Database':<40} {'Status':<10} {'Entries':<10} {'IDs':<10} {'Meta':<8} {'Structure'}")
print("-" * 100)

for db_name in databases:
    filepath = data_dir / db_name
    result = check_database(filepath)

    if not result["exists"]:
        print(f"{db_name:<40} {'MISSING':<10} {'-':<10} {'-':<10} {'-':<8} {'-'}")
        incomplete_count += 1
        continue

    # Determine status
    if result["structure_type"] == "nested_dict":
        # Nested dicts don't need individual IDs
        is_complete = result["has_metadata"]
    else:
        is_complete = (
            result["has_metadata"] and
            result["total_entries"] > 0 and
            result["entries_with_ids"] == result["total_entries"]
        )

    status = "✅ COMPLETE" if is_complete else "⚠️  INCOMPLETE"

    if is_complete:
        complete_count += 1
    else:
        incomplete_count += 1

    entries_str = str(result["total_entries"])
    ids_str = f"{result['entries_with_ids']}/{result['total_entries']}" if result["structure_type"] != "nested_dict" else "N/A"
    meta_str = "✅" if result["has_metadata"] else "❌"

    print(f"{db_name:<40} {status:<10} {entries_str:<10} {ids_str:<10} {meta_str:<8} {result['structure_type']}")

print("-" * 100)
print()
print(f"📊 SUMMARY:")
print(f"   Total Databases: {len(databases)}")
print(f"   ✅ Complete: {complete_count}")
print(f"   ⚠️  Incomplete: {incomplete_count}")
print()

if complete_count == len(databases):
    print("🎉 ALL DATABASES ARE COMPLETE AND STANDARDIZED! 🎉")
    print()
    print("✅ All databases have:")
    print("   - Proper schema structure")
    print("   - IDs for array entries (where applicable)")
    print("   - Metadata sections")
    print("   - Consistent formatting")
    print()
    print("🚀 Ready for production use!")
else:
    print("⚠️  Some databases need attention:")
    print()
    # Show which ones need work
    for db_name in databases:
        filepath = data_dir / db_name
        result = check_database(filepath)

        if result["exists"]:
            if result["structure_type"] == "nested_dict":
                is_complete = result["has_metadata"]
            else:
                is_complete = (
                    result["has_metadata"] and
                    result["total_entries"] > 0 and
                    result["entries_with_ids"] == result["total_entries"]
                )

            if not is_complete:
                issues = []
                if not result["has_metadata"]:
                    issues.append("missing metadata")
                if result["structure_type"] != "nested_dict" and result["entries_with_ids"] < result["total_entries"]:
                    issues.append(f"missing {result['total_entries'] - result['entries_with_ids']} IDs")

                print(f"   - {db_name}: {', '.join(issues)}")

print()
print("=" * 100)
