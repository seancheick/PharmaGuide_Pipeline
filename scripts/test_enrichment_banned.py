#!/usr/bin/env python3
"""
Test script to verify enhanced banned ingredient detection in enrichment script
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from enrich_supplements_v2 import SupplementEnricherV2
import json

def test_enrichment_banned_detection():
    """Test banned ingredient detection in enrichment script"""

    print("🧪 TESTING ENRICHMENT SCRIPT BANNED DETECTION")
    print("=" * 60)

    # Initialize the enricher
    enricher = SupplementEnricherV2()

    # Test cases with various banned substances
    test_cases = [
        {
            "name": "Test Product with Ephedra",
            "ingredients": [{"name": "Ephedra sinica extract"}],
            "expected_banned": True,
            "expected_severity": "critical"
        },
        {
            "name": "Test Product with DMAA",
            "ingredients": [{"name": "1,3-dimethylamylamine"}],
            "expected_banned": True,
            "expected_severity": "critical"
        },
        {
            "name": "Test Product with Ostarine",
            "ingredients": [{"name": "MK-2866"}],
            "expected_banned": True,
            "expected_severity": "critical"
        },
        {
            "name": "Test Product with Sildenafil",
            "ingredients": [{"name": "Viagra hidden"}],
            "expected_banned": True,
            "expected_severity": "critical"
        },
        {
            "name": "Test Product with Metal Contamination",
            "ingredients": [{"name": "Metal fiber contamination"}],
            "expected_banned": True,
            "expected_severity": "critical"
        },
        {
            "name": "Test Product with Substring Match",
            "ingredients": [{"name": "DMAA Pre-Workout Complex"}],
            "expected_banned": True,
            "expected_severity": "critical"
        },
        {
            "name": "Safe Product",
            "ingredients": [
                {"name": "Creatine Monohydrate"},
                {"name": "Whey Protein Isolate"},
                {"name": "Vitamin D3"}
            ],
            "expected_banned": False,
            "expected_severity": None
        }
    ]

    # Test individual banned detection method
    print("\n1. TESTING _enhanced_banned_ingredient_check METHOD:")

    # Sample banned items for testing
    test_banned_items = [
        {
            "id": "BANNED_EPHEDRA",
            "standard_name": "Ephedra",
            "aliases": ["ma huang", "ephedra sinica"],
            "severity_level": "critical"
        },
        {
            "id": "BANNED_DMAA",
            "standard_name": "DMAA",
            "aliases": ["1,3-dimethylamylamine", "methylhexanamine"],
            "severity_level": "critical"
        }
    ]

    test_ingredients = [
        "Ephedra",  # Exact match
        "ma huang",  # Alias match
        "Ephedra Extract Complex",  # Substring match
        "DMAA Pre-Workout",  # Substring match
        "Creatine"  # Safe ingredient
    ]

    for ingredient in test_ingredients:
        for banned_item in test_banned_items:
            result = enricher._enhanced_banned_ingredient_check(ingredient, banned_item)
            if result:
                print(f"   ✅ DETECTED: '{ingredient}' matches banned '{banned_item['standard_name']}'")
                break
        else:
            print(f"   ❌ SAFE: '{ingredient}' - no banned matches")

    # Test full enrichment process
    print("\n2. TESTING FULL ENRICHMENT PROCESS:")

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n   Test {i}: {test_case['name']}")

        # Create mock product data
        product_data = {
            "id": f"test_{i}",
            "fullName": test_case["name"],
            "ingredientRows": test_case["ingredients"],
            "targetGroups": ["Adults"],
            "servingSize": {"quantity": 1, "unit": "capsule"}
        }

        try:
            # Run enrichment analysis
            result = enricher.analyze_contaminants(product_data, test_case["ingredients"])

            banned_found = result["banned_substances"]["found"]
            banned_substances = result["banned_substances"]["substances"]

            # Check results
            if test_case["expected_banned"]:
                if banned_found:
                    print(f"      ✅ CORRECTLY DETECTED banned substances:")
                    for banned in banned_substances:
                        print(f"         - {banned['name']} -> {banned['standard_name']} (severity: {banned['severity']})")
                else:
                    print(f"      ❌ FAILED - Expected banned substances but none detected")
            else:
                if not banned_found:
                    print(f"      ✅ CORRECTLY IDENTIFIED as safe (no banned substances)")
                else:
                    print(f"      ❌ FALSE POSITIVE - Detected banned substances in safe product:")
                    for banned in banned_substances:
                        print(f"         - {banned['name']} -> {banned['standard_name']}")

        except Exception as e:
            print(f"      ❌ ERROR during analysis: {str(e)}")

    # Test database coverage
    print("\n3. DATABASE COVERAGE IN ENRICHMENT:")
    banned_db = enricher.databases.get('banned_recalled_ingredients', {})
    total_banned = 0

    sections_checked = [
        "permanently_banned", "nootropic_banned", "sarms_prohibited",
        "illegal_spiking_agents", "new_emerging_threats", "pharmaceutical_adulterants",
        "synthetic_cannabinoids", "novel_peptides", "high_risk_ingredients",
        "wada_prohibited_2024", "state_regional_bans", "manufacturing_violations",
        "research_chemicals", "designer_stimulants"
    ]

    for section in sections_checked:
        count = len(banned_db.get(section, []))
        total_banned += count
        print(f"   {section}: {count} entries")

    print(f"\n📊 TOTAL BANNED SUBSTANCES COVERAGE: {total_banned}")

    # Test new critical entries
    print("\n4. TESTING NEW CRITICAL ENTRIES:")
    new_critical_tests = [
        "Contaminated semaglutide",
        "Metal fiber contamination",
        "Pediatric fluoride supplements",
        "NDMA contamination"
    ]

    for ingredient in new_critical_tests:
        banned_item = {"id": "TEST", "standard_name": ingredient, "aliases": [], "severity_level": "critical"}
        result = enricher._enhanced_banned_ingredient_check(ingredient, banned_item)
        status = "✅ DETECTED" if result else "❌ MISSED"
        print(f"   {status}: {ingredient}")

def test_enhanced_vs_exact_matching():
    """Compare enhanced vs exact matching performance"""
    print("\n" + "=" * 60)
    print("🔍 COMPARING ENHANCED VS EXACT MATCHING")
    print("=" * 60)

    enricher = SupplementEnricherV2()

    test_banned_item = {
        "id": "BANNED_DMAA",
        "standard_name": "DMAA",
        "aliases": ["1,3-dimethylamylamine"],
        "severity_level": "critical"
    }

    test_ingredients = [
        "DMAA",  # Exact match
        "1,3-dimethylamylamine",  # Alias exact match
        "DMAA Pre-Workout Blend",  # Substring match
        "Pre-Workout with DMAA",  # Substring match
        "DMAA-Free Formula",  # Contains name but is negative
        "Creatine"  # Safe ingredient
    ]

    for ingredient in test_ingredients:
        exact_result = enricher._exact_ingredient_match(
            ingredient,
            test_banned_item.get('standard_name', ''),
            test_banned_item.get('aliases', [])
        )

        enhanced_result = enricher._enhanced_banned_ingredient_check(ingredient, test_banned_item)

        print(f"\n🧪 Testing: '{ingredient}'")
        print(f"   Exact matching: {'✅ MATCH' if exact_result else '❌ NO MATCH'}")
        print(f"   Enhanced matching: {'✅ MATCH' if enhanced_result else '❌ NO MATCH'}")

        if enhanced_result and not exact_result:
            print(f"   💡 Enhanced detection caught what exact matching missed!")

if __name__ == "__main__":
    test_enrichment_banned_detection()
    test_enhanced_vs_exact_matching()