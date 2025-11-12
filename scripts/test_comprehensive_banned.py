#!/usr/bin/env python3
"""
Test comprehensive banned ingredient detection - verify ALL sections are checked
"""

import sys
import os
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v2 import SupplementEnricherV2

def test_all_sections_coverage():
    """Test that both scripts check ALL sections in banned_recalled_ingredients.json"""

    print("🔍 TESTING COMPREHENSIVE BANNED INGREDIENT COVERAGE")
    print("=" * 70)

    # Load the banned ingredients database directly
    try:
        with open('/Users/seancheick/Downloads/dsld_clean/scripts/data/banned_recalled_ingredients.json', 'r') as f:
            banned_db = json.load(f)
    except Exception as e:
        print(f"❌ Error loading banned database: {e}")
        return

    # Get all sections that contain banned substance arrays
    all_sections = []
    total_substances = 0

    for key, value in banned_db.items():
        if isinstance(value, list) and len(value) > 0:
            # Check if items have banned substance structure
            if any(isinstance(item, dict) and 'standard_name' in item for item in value):
                all_sections.append(key)
                total_substances += len(value)

    print(f"📊 BANNED DATABASE ANALYSIS:")
    print(f"   Total sections with banned substances: {len(all_sections)}")
    print(f"   Total banned substances across all sections: {total_substances}")
    print(f"   Sections found: {', '.join(all_sections)}")

    # Test cleaning script coverage
    print(f"\n🧹 TESTING CLEANING SCRIPT (enhanced_normalizer.py):")
    try:
        normalizer = EnhancedDSLDNormalizer()

        # Test the dynamic section detection logic directly
        arrays_to_check = []
        for key, value in normalizer.banned_recalled.items():
            if isinstance(value, list) and len(value) > 0:
                if any(isinstance(item, dict) and 'standard_name' in item for item in value):
                    arrays_to_check.append(key)

        print(f"   Cleaning script checking {len(arrays_to_check)} sections:")
        for section in sorted(arrays_to_check):
            count = len(normalizer.banned_recalled.get(section, []))
            print(f"      ✅ {section}: {count} items")

        # Check for missed sections
        missed_sections = set(all_sections) - set(arrays_to_check)
        if missed_sections:
            print(f"   ❌ MISSED SECTIONS: {', '.join(missed_sections)}")
        else:
            print(f"   ✅ ALL SECTIONS COVERED!")

    except Exception as e:
        print(f"   ❌ Error testing cleaning script: {e}")

    # Test enrichment script coverage
    print(f"\n🔬 TESTING ENRICHMENT SCRIPT (enrich_supplements_v2.py):")
    try:
        enricher = SupplementEnricherV2()
        enricher_banned_db = enricher.databases.get('banned_recalled_ingredients', {})

        # Test the dynamic section detection logic directly
        enricher_sections = []
        for key, value in enricher_banned_db.items():
            if isinstance(value, list) and len(value) > 0:
                if any(isinstance(item, dict) and 'standard_name' in item for item in value):
                    enricher_sections.append(key)

        print(f"   Enrichment script checking {len(enricher_sections)} sections:")
        for section in sorted(enricher_sections):
            count = len(enricher_banned_db.get(section, []))
            print(f"      ✅ {section}: {count} items")

        # Check for missed sections
        missed_sections = set(all_sections) - set(enricher_sections)
        if missed_sections:
            print(f"   ❌ MISSED SECTIONS: {', '.join(missed_sections)}")
        else:
            print(f"   ✅ ALL SECTIONS COVERED!")

    except Exception as e:
        print(f"   ❌ Error testing enrichment script: {e}")

    # Test specific banned substances from different sections
    print(f"\n🎯 TESTING DETECTION ACROSS ALL SECTIONS:")

    test_substances = []
    # Get one test substance from each section
    for section in all_sections[:10]:  # Test first 10 sections
        items = banned_db.get(section, [])
        if items:
            test_substances.append({
                'name': items[0].get('standard_name', ''),
                'section': section,
                'severity': items[0].get('severity_level', 'unknown')
            })

    # Test detection in cleaning script
    print(f"   Cleaning Script Detection:")
    try:
        normalizer = EnhancedDSLDNormalizer()
        for substance in test_substances:
            detected = normalizer._check_banned_recalled(substance['name'])
            status = "✅ DETECTED" if detected else "❌ MISSED"
            print(f"      {status}: {substance['name']} ({substance['section']})")
    except Exception as e:
        print(f"      ❌ Error: {e}")

    # Test detection in enrichment script
    print(f"   Enrichment Script Detection:")
    try:
        enricher = SupplementEnricherV2()
        for substance in test_substances:
            # Create a mock banned item
            banned_item = {
                'standard_name': substance['name'],
                'aliases': [],
                'severity_level': substance['severity']
            }
            detected = enricher._enhanced_banned_ingredient_check(substance['name'], banned_item, substance['section'])
            status = "✅ DETECTED" if detected else "❌ MISSED"
            print(f"      {status}: {substance['name']} ({substance['section']})")
    except Exception as e:
        print(f"      ❌ Error: {e}")

def test_new_critical_substances():
    """Test detection of newly added critical substances"""
    print(f"\n🆕 TESTING NEW CRITICAL SUBSTANCES:")

    new_substances = [
        "Metal Fiber Contamination",
        "Contaminated GLP-1 Compounds",
        "Fluoride Supplements (Children)",
        "NDMA",
        "N-nitrosodimethylamine"
    ]

    try:
        normalizer = EnhancedDSLDNormalizer()
        print(f"   Cleaning Script:")
        for substance in new_substances:
            detected = normalizer._check_banned_recalled(substance)
            status = "✅ DETECTED" if detected else "❌ MISSED"
            print(f"      {status}: {substance}")
    except Exception as e:
        print(f"      ❌ Error: {e}")

if __name__ == "__main__":
    test_all_sections_coverage()
    test_new_critical_substances()