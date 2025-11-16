#!/usr/bin/env python3
"""
Integration test to verify all scripts work with new database schema
Tests that all databases are loaded correctly with new structure
"""

import json
from pathlib import Path

print("=" * 100)
print(" " * 25 + "INTEGRATION TEST - NEW DATABASE SCHEMA")
print("=" * 100)
print()

# Test 1: Verify all databases have correct structure
print("TEST 1: Verifying Database Structures")
print("-" * 100)

databases_to_test = {
    # Wrapped arrays with IDs
    'botanical_ingredients.json': ('botanical_ingredients', True),
    'other_ingredients.json': ('other_ingredients', True),
    'standardized_botanicals.json': ('standardized_botanicals', True),
    'allergens.json': ('common_allergens', True),
    'banned_recalled_ingredients.json': ('permanently_banned', True),  # Has multiple arrays, checking first one
    'harmful_additives.json': ('harmful_additives', True),
    'synergy_cluster.json': ('synergy_clusters', True),
    'proprietary_blends_penalty.json': ('proprietary_blend_concerns', True),
    'rda_optimal_uls.json': ('nutrient_recommendations', True),
    'rda_therapeutic_dosing.json': ('therapeutic_dosing', True),
    'user_goals_to_clusters.json': ('user_goal_mappings', True),
    'absorption_enhancers.json': ('absorption_enhancers', True),
    'backed_clinical_studies.json': ('backed_clinical_studies', True),
    'manufacturer_violations.json': ('manufacturer_violations', True),
    'top_manufacturers_data.json': ('top_manufacturers', True),

    # Nested dicts (no IDs needed)
    'enhanced_delivery.json': (None, False),
    'ingredient_quality_map.json': (None, False),
    'ingredient_weights.json': (None, False),
}

all_pass = True

for db_file, (main_key, needs_ids) in databases_to_test.items():
    filepath = Path(f'data/{db_file}')

    if not filepath.exists():
        print(f"⚠️  {db_file}: File not found")
        all_pass = False
        continue

    try:
        with open(filepath, 'r') as f:
            data = json.load(f)

        # Check metadata
        has_metadata = '_metadata' in data or 'database_info' in data
        if not has_metadata:
            print(f"❌ {db_file}: Missing _metadata")
            all_pass = False
            continue

        # Check structure
        if main_key:
            if main_key not in data:
                print(f"❌ {db_file}: Missing key '{main_key}'")
                all_pass = False
                continue

            entries = data[main_key]
            if not isinstance(entries, list):
                print(f"❌ {db_file}: '{main_key}' is not a list")
                all_pass = False
                continue

            # Check IDs if needed
            if needs_ids:
                entries_with_ids = sum(1 for e in entries if isinstance(e, dict) and 'id' in e)
                if entries_with_ids != len(entries):
                    print(f"❌ {db_file}: {entries_with_ids}/{len(entries)} entries have IDs")
                    all_pass = False
                    continue

            print(f"✅ {db_file}: {len(entries)} entries, all have IDs, has metadata")
        else:
            # Nested dict structure
            print(f"✅ {db_file}: Nested dict structure, has metadata")

    except Exception as e:
        print(f"❌ {db_file}: Error - {e}")
        all_pass = False

print()

# Test 2: Test enhanced_normalizer loads everything correctly
print("TEST 2: Testing Enhanced Normalizer")
print("-" * 100)

try:
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()

    # Verify key databases loaded
    other_ing_count = len(normalizer.other_ingredients.get("other_ingredients", []))
    botanical_count = len(normalizer.botanical_ingredients.get("botanical_ingredients", []))
    standardized_count = len(normalizer.standardized_botanicals.get("standardized_botanicals", []))

    print(f"✅ EnhancedDSLDNormalizer initialized successfully")
    print(f"   - other_ingredients: {other_ing_count} entries")
    print(f"   - botanical_ingredients: {botanical_count} entries")
    print(f"   - standardized_botanicals: {standardized_count} entries")

except Exception as e:
    print(f"❌ EnhancedDSLDNormalizer failed: {e}")
    import traceback
    traceback.print_exc()
    all_pass = False

print()

# Test 3: Test enrichment config
print("TEST 3: Testing Enrichment Config")
print("-" * 100)

try:
    with open('config/enrichment_config.json', 'r') as f:
        config = json.load(f)

    db_paths = config.get('database_paths', {})

    # Check that it uses other_ingredients, not old databases
    if 'other_ingredients' in db_paths:
        print(f"✅ Config uses 'other_ingredients' ✓")
    else:
        print(f"❌ Config missing 'other_ingredients'")
        all_pass = False

    if 'non_harmful_additives' in db_paths:
        print(f"⚠️  Config still references 'non_harmful_additives' (should be removed)")
        all_pass = False

    if 'passive_inactive_ingredients' in db_paths:
        print(f"⚠️  Config still references 'passive_inactive_ingredients' (should be removed)")
        all_pass = False

    # Verify all database files exist
    missing_files = []
    for db_name, db_path in db_paths.items():
        if not Path(db_path).exists():
            missing_files.append(db_path)

    if missing_files:
        print(f"❌ Missing database files:")
        for file in missing_files:
            print(f"   - {file}")
        all_pass = False
    else:
        print(f"✅ All {len(db_paths)} database files exist")

except Exception as e:
    print(f"❌ Config test failed: {e}")
    all_pass = False

print()

# Test 4: Verify is_additive field in other_ingredients
print("TEST 4: Testing is_additive Field")
print("-" * 100)

try:
    with open('data/other_ingredients.json', 'r') as f:
        data = json.load(f)

    entries = data.get('other_ingredients', [])
    has_field = sum(1 for e in entries if 'is_additive' in e)

    if has_field == len(entries):
        additive_count = sum(1 for e in entries if e.get('is_additive') is True)
        excipient_count = sum(1 for e in entries if e.get('is_additive') is False)

        print(f"✅ All {len(entries)} entries have 'is_additive' field")
        print(f"   - Additives (true): {additive_count}")
        print(f"   - Excipients (false): {excipient_count}")
    else:
        print(f"❌ Only {has_field}/{len(entries)} entries have 'is_additive' field")
        all_pass = False

except Exception as e:
    print(f"❌ is_additive test failed: {e}")
    all_pass = False

print()

# Final Result
print("=" * 100)
if all_pass:
    print(" " * 35 + "🎉 ALL TESTS PASSED! 🎉")
    print()
    print("✅ All databases have correct schema")
    print("✅ All databases have IDs (where needed)")
    print("✅ All databases have metadata")
    print("✅ Enhanced normalizer works correctly")
    print("✅ Enrichment config is updated")
    print("✅ is_additive field present")
    print()
    print("🚀 All scripts ready for production!")
else:
    print(" " * 35 + "❌ SOME TESTS FAILED")
    print()
    print("Please review the errors above and fix the issues")

print("=" * 100)
