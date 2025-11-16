#!/usr/bin/env python3
"""
Complete all remaining database standardization
Adds IDs, metadata, and fixes schema issues for all 15 remaining databases
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import shutil

def create_backup(filepath: Path):
    """Create timestamped backup"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = filepath.parent / f"{filepath.stem}_backup_{timestamp}{filepath.suffix}"
    shutil.copy2(filepath, backup_path)
    print(f"  ✅ Backup: {backup_path.name}")
    return backup_path

def generate_id(name: str) -> str:
    """Generate ID from name"""
    id_str = name.lower()
    id_str = re.sub(r'[^a-z0-9]+', '_', id_str)
    id_str = id_str.strip('_')
    return id_str

def add_metadata_to_simple_array(filepath: Path, description: str, purpose: str):
    """Add metadata to databases with simple array structure"""
    print(f"\n🔧 Processing: {filepath.name}")

    create_backup(filepath)

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Find main array key
    main_key = None
    for key, value in data.items():
        if isinstance(value, list) and not key.startswith('_'):
            main_key = key
            break

    if not main_key:
        print(f"  ⚠️  No main array found")
        return

    entries = data[main_key]

    # Check if metadata exists
    if '_metadata' not in data:
        data['_metadata'] = {
            "description": description,
            "purpose": purpose,
            "total_entries": len(entries),
            "schema_version": "1.0",
            "last_updated": "2025-11-14"
        }
        print(f"  ✅ Added metadata")
    else:
        print(f"  ℹ️  Metadata already exists")

    # Save
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"  ✅ Complete: {len(entries)} entries")

def add_ids_and_metadata(filepath: Path, main_key: str, description: str, purpose: str, id_field: str = "standard_name"):
    """Add IDs and metadata to databases"""
    print(f"\n🔧 Processing: {filepath.name}")

    create_backup(filepath)

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    entries = data.get(main_key, [])

    # Add IDs
    used_ids = set()
    ids_added = 0

    for entry in entries:
        if 'id' not in entry:
            # Generate ID from specified field
            name = entry.get(id_field, entry.get('name', ''))
            base_id = generate_id(name)

            # Handle collisions
            entry_id = base_id
            counter = 2
            while entry_id in used_ids:
                entry_id = f"{base_id}_{counter}"
                counter += 1

            entry['id'] = entry_id
            used_ids.add(entry_id)
            ids_added += 1
        else:
            used_ids.add(entry['id'])

    print(f"  ✅ Added {ids_added} IDs")

    # Add metadata
    if '_metadata' not in data:
        data['_metadata'] = {
            "description": description,
            "purpose": purpose,
            "total_entries": len(entries),
            "schema_version": "1.0",
            "last_updated": "2025-11-14"
        }
        print(f"  ✅ Added metadata")
    else:
        data['_metadata']['total_entries'] = len(entries)
        data['_metadata']['last_updated'] = "2025-11-14"
        print(f"  ✅ Updated metadata")

    # Save
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"  ✅ Complete: {len(entries)} entries, all have IDs")

def main():
    print("=" * 80)
    print("COMPLETING ALL DATABASE STANDARDIZATION")
    print("=" * 80)

    data_dir = Path('data')

    # Group 1: Just need metadata (4 databases)
    print("\n" + "=" * 80)
    print("GROUP 1: Adding Metadata (4 databases)")
    print("=" * 80)

    add_metadata_to_simple_array(
        data_dir / 'allergens.json',
        "Allergen database for supplement safety flagging and warnings",
        "safety_warnings"
    )

    add_metadata_to_simple_array(
        data_dir / 'banned_recalled_ingredients.json',
        "Banned and recalled ingredients database including FDA warnings, prohibited substances, and emerging threats",
        "safety_disqualification"
    )

    add_metadata_to_simple_array(
        data_dir / 'harmful_additives.json',
        "Harmful additives database with risk levels and scoring penalties",
        "quality_penalties"
    )

    add_metadata_to_simple_array(
        data_dir / 'synergy_cluster.json',
        "Ingredient synergy clusters for bonus scoring when complementary ingredients are combined",
        "synergy_bonuses"
    )

    # Group 2: Need IDs + metadata (4 databases)
    print("\n" + "=" * 80)
    print("GROUP 2: Adding IDs + Metadata (4 databases)")
    print("=" * 80)

    add_ids_and_metadata(
        data_dir / 'proprietary_blends_penalty.json',
        'proprietary_blends',
        "Proprietary blend penalties for undisclosed ingredient amounts",
        "transparency_penalties",
        "blend_type"
    )

    add_ids_and_metadata(
        data_dir / 'rda_optimal_uls.json',
        'ingredients',
        "RDA (Recommended Dietary Allowance), optimal dosing, and UL (Upper Limit) reference values for nutrient dosing validation",
        "dosing_validation",
        "name"
    )

    add_ids_and_metadata(
        data_dir / 'rda_therapeutic_dosing.json',
        'ingredients',
        "Therapeutic dosing ranges for clinical efficacy validation",
        "therapeutic_validation",
        "name"
    )

    add_ids_and_metadata(
        data_dir / 'user_goals_to_clusters.json',
        'user_goals',
        "Mapping of user health goals to ingredient synergy clusters for personalized recommendations",
        "goal_mapping",
        "goal"
    )

    # Group 3: Review structure (7 databases)
    print("\n" + "=" * 80)
    print("GROUP 3: Reviewing Structure (7 databases)")
    print("=" * 80)

    # These may have different structures - need to check each
    structure_review = [
        'absorption_enhancers.json',
        'backed_clinical_studies.json',
        'enhanced_delivery.json',
        'ingredient_quality_map.json',
        'ingredient_weights.json',
        'manufacturer_violations.json',
        'top_manufacturers_data.json'
    ]

    for db_name in structure_review:
        filepath = data_dir / db_name
        if not filepath.exists():
            print(f"\n⚠️  {db_name}: File not found")
            continue

        print(f"\n🔍 Reviewing: {db_name}")

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if isinstance(data, list):
            print(f"  📋 Structure: Direct array ({len(data)} entries)")
            print(f"  💡 Recommendation: Wrap in object with metadata")

            # Check if entries have IDs
            has_ids = sum(1 for e in data if isinstance(e, dict) and 'id' in e)
            print(f"  📊 Entries with IDs: {has_ids}/{len(data)}")

        elif isinstance(data, dict):
            # Check structure type
            has_metadata = '_metadata' in data
            arrays = [k for k, v in data.items() if isinstance(v, list) and not k.startswith('_')]
            nested = [k for k, v in data.items() if isinstance(v, dict) and not k.startswith('_')]

            print(f"  📋 Structure: Nested dict")
            print(f"  📊 Arrays: {len(arrays)}, Nested dicts: {len(nested)}")
            print(f"  📊 Has metadata: {has_metadata}")

            if not has_metadata:
                print(f"  💡 Recommendation: Add metadata")

    print("\n" + "=" * 80)
    print("PHASE 1 & 2 COMPLETE")
    print("=" * 80)
    print("\n✅ Groups 1 & 2 complete (8 databases standardized)")
    print("⚠️  Group 3 needs manual review (7 databases)")
    print("\nNext: Run fix_structure_databases.py to complete Group 3")

if __name__ == '__main__':
    main()
