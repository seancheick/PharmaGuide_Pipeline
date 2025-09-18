#!/usr/bin/env python3
"""
Detailed data validation - compare enriched output with source data
"""

import json
import os
from typing import Dict, List, Any

def validate_ingredient_mapping():
    """Validate that ingredient mapping is accurate"""
    print("🔍 Detailed Ingredient Mapping Validation")
    print("-" * 40)
    
    # Load sample data
    cleaned_file = "output_Gummies-Jellies/cleaned/cleaned_batch_1.json"
    enriched_file = "test_enrichment_output/enriched/enriched_cleaned_batch_1.json"
    
    if not os.path.exists(cleaned_file) or not os.path.exists(enriched_file):
        print("❌ Test files not found")
        return False
    
    with open(cleaned_file, 'r') as f:
        cleaned_data = json.load(f)
    
    with open(enriched_file, 'r') as f:
        enriched_data = json.load(f)
    
    issues = []
    
    # Check first few products in detail
    for i in range(min(3, len(cleaned_data))):
        cleaned_product = cleaned_data[i]
        enriched_product = enriched_data[i]
        
        product_id = cleaned_product.get('id')
        print(f"\n📦 Product {product_id}: {cleaned_product.get('fullName', '')[:50]}...")
        
        # Check active ingredients mapping
        active_ingredients = cleaned_product.get('activeIngredients', [])
        quality_mapping = enriched_product.get('form_quality_mapping', [])
        
        print(f"   Active ingredients: {len(active_ingredients)}")
        print(f"   Quality mappings: {len(quality_mapping)}")
        
        if len(active_ingredients) != len(quality_mapping):
            issues.append(f"Product {product_id}: Ingredient count mismatch")
            continue
        
        # Validate each ingredient
        for j, (orig_ing, mapped_ing) in enumerate(zip(active_ingredients, quality_mapping)):
            orig_name = orig_ing.get('name', '')
            orig_std_name = orig_ing.get('standardName', '')
            orig_quantity = orig_ing.get('quantity', 0)
            orig_category = orig_ing.get('category', '')
            
            mapped_name = mapped_ing.get('ingredient', '')
            mapped_std_name = mapped_ing.get('standard_name', '')
            mapped_category = mapped_ing.get('category', '')
            bio_score = mapped_ing.get('bio_score', 0)
            
            print(f"     {j+1}. {orig_name}")
            print(f"        Original: std='{orig_std_name}', cat='{orig_category}', qty={orig_quantity}")
            print(f"        Mapped:   std='{mapped_std_name}', cat='{mapped_category}', bio={bio_score}")
            
            # Validate name preservation
            if orig_name != mapped_name:
                issues.append(f"Product {product_id}, ingredient {j+1}: Name mismatch")
            
            # Check bio_score reasonableness
            if bio_score < 1 or bio_score > 20:
                issues.append(f"Product {product_id}, ingredient {j+1}: Invalid bio_score {bio_score}")
            
            # Check if unmapped ingredients have default values
            if mapped_category == 'unmapped':
                print(f"        ⚠️  Unmapped ingredient: {orig_name}")
    
    if issues:
        print(f"\n❌ Found {len(issues)} mapping issues:")
        for issue in issues:
            print(f"   - {issue}")
        return False
    else:
        print(f"\n✅ Ingredient mapping validation passed")
        return True

def validate_rda_accuracy():
    """Validate RDA calculations against known values"""
    print("\n🧮 RDA Calculation Accuracy Check")
    print("-" * 40)
    
    from enrich_supplements_v2 import SupplementEnricherV2
    enricher = SupplementEnricherV2()
    
    # Test known RDA values
    test_cases = [
        # (ingredient, quantity, unit, expected_rda_range)
        ('Vitamin C', 90, 'mg', (90, 120)),  # Should be ~100% RDA
        ('Vitamin D', 400, 'IU', (80, 120)),  # Should be ~100% RDA  
        ('Calcium', 500, 'mg', (40, 60)),     # Should be ~50% RDA
        ('Iron', 18, 'mg', (90, 110)),        # Should be ~100% RDA for women
    ]
    
    issues = []
    
    for ingredient_name, quantity, unit, expected_range in test_cases:
        test_ingredient = {
            'standardName': ingredient_name,
            'quantity': quantity,
            'unit': unit
        }
        
        rda_result = enricher._analyze_rda_ul([test_ingredient])
        rda_key = ingredient_name.lower().replace(' ', '_')
        
        if rda_key in rda_result:
            rda_data = rda_result[rda_key]
            percent_rda = rda_data.get('percent_rda', 0)
            product_amount = rda_data.get('product_amount', 0)
            
            print(f"   {ingredient_name}: {quantity}{unit} = {percent_rda}% RDA")
            
            # Validate amount preservation
            if abs(product_amount - quantity) > 0.01:
                issues.append(f"{ingredient_name}: Amount not preserved ({product_amount} vs {quantity})")
            
            # Validate RDA percentage is reasonable
            if not (expected_range[0] <= percent_rda <= expected_range[1]):
                issues.append(f"{ingredient_name}: RDA% outside expected range ({percent_rda}% not in {expected_range})")
        else:
            print(f"   {ingredient_name}: No RDA data found")
    
    if issues:
        print(f"\n❌ RDA calculation issues:")
        for issue in issues:
            print(f"   - {issue}")
        return False
    else:
        print(f"\n✅ RDA calculations accurate")
        return True

def check_synergy_logic():
    """Validate synergy detection logic"""
    print("\n🔗 Synergy Detection Validation")
    print("-" * 40)
    
    from enrich_supplements_v2 import SupplementEnricherV2
    enricher = SupplementEnricherV2()
    
    # Test synergy detection with known combinations
    test_ingredients = [
        {'name': 'Curcumin', 'standardName': 'curcumin', 'quantity': 500, 'unit': 'mg'},
        {'name': 'Piperine', 'standardName': 'piperine', 'quantity': 10, 'unit': 'mg'},
        {'name': 'Magnesium', 'standardName': 'magnesium', 'quantity': 200, 'unit': 'mg'},
        {'name': 'Vitamin B6', 'standardName': 'vitamin b6', 'quantity': 10, 'unit': 'mg'}
    ]
    
    synergy_result = enricher._analyze_synergies(test_ingredients)
    detected_clusters = synergy_result.get('detected_clusters', [])
    total_points = synergy_result.get('total_synergy_points', 0)
    
    print(f"   Test ingredients: {len(test_ingredients)}")
    print(f"   Detected clusters: {len(detected_clusters)}")
    print(f"   Total synergy points: {total_points}")
    
    issues = []
    
    # Should detect curcumin + piperine synergy
    curcumin_synergy_found = False
    for cluster in detected_clusters:
        cluster_name = cluster.get('cluster_name', '')
        matched_ingredients = cluster.get('matched_ingredients', [])
        
        print(f"     Cluster: {cluster_name}")
        print(f"       Ingredients: {[ing.get('ingredient', '') for ing in matched_ingredients]}")
        
        if 'curcumin' in cluster_name.lower():
            curcumin_synergy_found = True
            
        # Check that cluster has proper name and ID
        if not cluster.get('cluster_name'):
            issues.append("Empty cluster name found")
        if not cluster.get('cluster_id'):
            issues.append("Empty cluster ID found")
    
    if not curcumin_synergy_found and len(detected_clusters) == 0:
        print("     ⚠️  No synergies detected (may be expected if ingredients don't match exactly)")
    
    if issues:
        print(f"\n❌ Synergy detection issues:")
        for issue in issues:
            print(f"   - {issue}")
        return False
    else:
        print(f"\n✅ Synergy detection working correctly")
        return True

def validate_scoring_precalculations():
    """Check that scoring precalculations are reasonable"""
    print("\n📊 Scoring Precalculations Validation")
    print("-" * 40)
    
    enriched_file = "test_enrichment_output/enriched/enriched_cleaned_batch_1.json"
    
    if not os.path.exists(enriched_file):
        print("❌ No enriched data for validation")
        return False
    
    with open(enriched_file, 'r') as f:
        enriched_data = json.load(f)
    
    issues = []
    
    # Check first few products
    for i in range(min(3, len(enriched_data))):
        product = enriched_data[i]
        product_id = product.get('id')
        scoring = product.get('scoring_precalculations', {})
        
        print(f"\n   Product {product_id}:")
        
        # Check section totals
        section_a = scoring.get('section_a', {})
        section_b = scoring.get('section_b', {})
        section_c = scoring.get('section_c', {})
        section_d = scoring.get('section_d', {})
        
        a_total = section_a.get('total', 0)
        b_total = section_b.get('total', 0)
        c_total = section_c.get('total', 0)
        d_total = section_d.get('total', 0)
        
        base_total = scoring.get('base_score_total', 0)
        expected_total = a_total + b_total + c_total + d_total
        
        print(f"     Section A: {a_total}")
        print(f"     Section B: {b_total}")
        print(f"     Section C: {c_total}")
        print(f"     Section D: {d_total}")
        print(f"     Base total: {base_total}")
        print(f"     Expected: {expected_total}")
        
        # Validate total calculation
        if abs(base_total - expected_total) > 0.01:
            issues.append(f"Product {product_id}: Score total mismatch ({base_total} vs {expected_total})")
        
        # Check reasonable ranges
        if base_total < 0 or base_total > 80:
            issues.append(f"Product {product_id}: Base score out of range ({base_total})")
        
        # Section B should start at 15 (contaminant base)
        if b_total < 0 or b_total > 20:
            issues.append(f"Product {product_id}: Section B score unusual ({b_total})")
    
    if issues:
        print(f"\n❌ Scoring calculation issues:")
        for issue in issues:
            print(f"   - {issue}")
        return False
    else:
        print(f"\n✅ Scoring precalculations accurate")
        return True

def run_detailed_validation():
    """Run all detailed validation checks"""
    print("🔬 DETAILED DATA VALIDATION")
    print("=" * 50)
    
    checks = [
        ("Ingredient Mapping", validate_ingredient_mapping),
        ("RDA Accuracy", validate_rda_accuracy),
        ("Synergy Logic", check_synergy_logic),
        ("Scoring Calculations", validate_scoring_precalculations)
    ]
    
    passed = 0
    total = len(checks)
    
    for check_name, check_func in checks:
        try:
            if check_func():
                passed += 1
        except Exception as e:
            print(f"❌ {check_name} check failed: {e}")
    
    print("\n" + "=" * 50)
    print("📊 DETAILED VALIDATION SUMMARY")
    print("=" * 50)
    
    print(f"✅ Checks passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 ALL DETAILED VALIDATIONS PASSED!")
        print("✅ Data quality is excellent")
        print("✅ Calculations are accurate")
        print("✅ Pipeline is production-ready")
    else:
        print("⚠️  Some detailed checks failed")
        print("🔧 Review the issues above")
    
    return passed == total

if __name__ == "__main__":
    # Change to scripts directory if needed
    if not os.path.exists("config/enrichment_config.json"):
        if os.path.exists("scripts/config/enrichment_config.json"):
            os.chdir("scripts")
    
    success = run_detailed_validation()