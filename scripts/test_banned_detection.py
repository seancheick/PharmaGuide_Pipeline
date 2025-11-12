#!/usr/bin/env python3
"""
Test script to verify banned ingredient detection capabilities
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from enhanced_normalizer import EnhancedDSLDNormalizer
import json

def test_banned_detection():
    """Test banned ingredient detection with various test cases"""

    # Initialize the normalizer
    normalizer = EnhancedDSLDNormalizer()

    # Test cases - exact matches
    exact_match_tests = [
        "Ephedra",  # permanently_banned
        "DMAA",     # permanently_banned
        "Ostarine", # sarms_prohibited
        "Piracetam", # nootropic_banned
        "Sildenafil", # illegal_spiking_agents
        "Metal Fiber Contamination", # permanently_banned (new)
        "NDMA",     # manufacturing_violations (new)
        "Bromantane" # nootropic_banned (new)
    ]

    # Test cases - alias matches
    alias_match_tests = [
        "ma huang",        # Ephedra alias
        "1,3-dimethylamylamine",  # DMAA alias
        "MK-2866",         # Ostarine alias
        "nootropil",       # Piracetam alias
        "viagra",          # Sildenafil alias
        "metal fibers",    # Metal Fiber alias
        "N-nitrosodimethylamine", # NDMA alias
        "ladasten"         # Bromantane alias
    ]

    # Test cases - substring matches
    substring_match_tests = [
        "Ephedra Extract Complex",  # Contains Ephedra
        "DMAA Pre-Workout Blend",   # Contains DMAA
        "Ostarine MK-2866 Capsules", # Contains Ostarine
        "Natural Sildenafil Complex", # Contains Sildenafil
        "Metal Fiber Contaminated Supplement" # Contains metal fibers
    ]

    # Test cases - should NOT match (safe ingredients)
    safe_ingredient_tests = [
        "Creatine Monohydrate",
        "Whey Protein Isolate",
        "Vitamin D3",
        "Magnesium Citrate",
        "Omega-3 Fish Oil"
    ]

    print("🧪 TESTING BANNED INGREDIENT DETECTION")
    print("=" * 50)

    # Test exact matches
    print("\n1. EXACT MATCH TESTS:")
    for ingredient in exact_match_tests:
        result = normalizer._check_banned_recalled(ingredient)
        status = "✅ DETECTED" if result else "❌ MISSED"
        print(f"   {status}: {ingredient}")

    # Test alias matches
    print("\n2. ALIAS MATCH TESTS:")
    for ingredient in alias_match_tests:
        result = normalizer._check_banned_recalled(ingredient)
        status = "✅ DETECTED" if result else "❌ MISSED"
        print(f"   {status}: {ingredient}")

    # Test substring matches
    print("\n3. SUBSTRING MATCH TESTS:")
    for ingredient in substring_match_tests:
        result = normalizer._check_banned_recalled(ingredient)
        status = "✅ DETECTED" if result else "❌ MISSED"
        print(f"   {status}: {ingredient}")

    # Test safe ingredients (should NOT be detected)
    print("\n4. SAFE INGREDIENT TESTS (should NOT be detected):")
    for ingredient in safe_ingredient_tests:
        result = normalizer._check_banned_recalled(ingredient)
        status = "✅ SAFE" if not result else "❌ FALSE POSITIVE"
        print(f"   {status}: {ingredient}")

    # Test database coverage
    print("\n5. DATABASE COVERAGE:")
    total_banned = 0
    for section in ["permanently_banned", "nootropic_banned", "sarms_prohibited",
                   "illegal_spiking_agents", "manufacturing_violations"]:
        count = len(normalizer.banned_recalled.get(section, []))
        total_banned += count
        print(f"   {section}: {count} entries")

    print(f"\n📊 TOTAL BANNED SUBSTANCES: {total_banned}")
    print(f"📊 TOTAL BANNED VARIATIONS: {len(normalizer.banned_variations)}")

    # Test some new critical entries
    print("\n6. NEW CRITICAL ENTRIES TEST:")
    new_critical_tests = [
        "Contaminated GLP-1",
        "semaglutide contamination",
        "Pediatric Fluoride",
        "fluoride tablets for children"
    ]

    for ingredient in new_critical_tests:
        result = normalizer._check_banned_recalled(ingredient)
        status = "✅ DETECTED" if result else "❌ MISSED"
        print(f"   {status}: {ingredient}")

def test_classification_flow():
    """Test the complete classification flow"""
    print("\n" + "=" * 50)
    print("🔄 TESTING COMPLETE CLASSIFICATION FLOW")
    print("=" * 50)

    normalizer = EnhancedDSLDNormalizer()

    test_ingredients = [
        "Ephedra sinica extract",    # Should be banned
        "Creatine monohydrate",      # Should be safe/beneficial
        "Titanium dioxide",          # Should be harmful
        "Sunflower lecithin"         # Should be allergen + safe
    ]

    for ingredient in test_ingredients:
        print(f"\n🧪 Testing: {ingredient}")

        # Test individual checks
        is_banned = normalizer._check_banned_recalled(ingredient)
        print(f"   Banned check: {'✅ YES' if is_banned else '❌ NO'}")

        # Test other checks
        try:
            is_harmful = normalizer._check_harmful_additives(ingredient)
            print(f"   Harmful check: {'✅ YES' if is_harmful else '❌ NO'}")
        except:
            print(f"   Harmful check: N/A")

        try:
            is_allergen = normalizer._check_allergens(ingredient)
            print(f"   Allergen check: {'✅ YES' if is_allergen else '❌ NO'}")
        except:
            print(f"   Allergen check: N/A")

if __name__ == "__main__":
    test_banned_detection()
    test_classification_flow()