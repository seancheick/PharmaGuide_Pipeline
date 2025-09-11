#!/usr/bin/env python3
"""
Test Form Detection Issues
Identify specific form detection problems using real DSLD data
"""

import json
import sys
from pathlib import Path

# Add the scripts directory to Python path
sys.path.append(str(Path(__file__).parent))

from enhanced_normalizer import EnhancedDSLDNormalizer

def test_form_detection_with_real_data():
    """Test form detection using real DSLD data"""
    
    print("🔍 Testing Form Detection with Real DSLD Data\n")
    
    normalizer = EnhancedDSLDNormalizer()
    
    # Test with the Nature's Bounty product
    test_file = "/Users/seancheick/Documents/DataSetDsld/Tablets-Pills-32882Labels-8-6-25/29289.json"
    
    try:
        with open(test_file, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        
        print(f"📋 Testing with: {raw_data.get('fullName', 'Unknown Product')}")
        print(f"🏭 Brand: {raw_data.get('brandName', 'Unknown Brand')}")
        print()
        
        # Process with normalizer
        result = normalizer.normalize_product(raw_data)
        
        # Analyze each ingredient's form detection
        print("🔬 Raw vs Cleaned Form Detection Analysis:\n")
        
        raw_ingredients = raw_data.get('ingredientRows', [])
        cleaned_ingredients = result.get('activeIngredients', []) + result.get('inactiveIngredients', [])
        
        for i, raw_ing in enumerate(raw_ingredients):
            raw_name = raw_ing.get('name', '')
            raw_notes = raw_ing.get('notes', '')
            raw_forms = [f.get('name', '') for f in raw_ing.get('forms', [])]
            raw_category = raw_ing.get('category', '')
            
            print(f"🔍 Raw Ingredient #{i+1}: {raw_name}")
            print(f"   📝 Notes: {raw_notes}")
            print(f"   📋 Raw Forms: {raw_forms}")
            print(f"   🏷️  Category: {raw_category}")
            
            # Find corresponding cleaned ingredient
            cleaned_match = None
            for clean_ing in cleaned_ingredients:
                if clean_ing.get('name', '').lower() in raw_name.lower() or raw_name.lower() in clean_ing.get('name', '').lower():
                    cleaned_match = clean_ing
                    break
            
            if cleaned_match:
                cleaned_forms = cleaned_match.get('forms', [])
                print(f"   ✅ Cleaned Forms: {cleaned_forms}")
                
                # Identify issues
                issues = []
                
                # Check if parenthetical forms were extracted
                if "(" in raw_name and ")" in raw_name:
                    paren_content = raw_name[raw_name.find("(")+1:raw_name.find(")")]
                    if "as " in paren_content.lower() or "form:" in paren_content.lower():
                        if not any(paren_content.lower().replace('as ', '').strip() in form.lower() for form in cleaned_forms):
                            issues.append(f"Parenthetical form not extracted: '{paren_content}'")
                
                # Check if notes forms were extracted  
                if raw_notes and ("Form:" in raw_notes or "as " in raw_notes):
                    if not cleaned_forms or cleaned_forms == ['unspecified']:
                        issues.append(f"Notes form not extracted from: '{raw_notes}'")
                
                # Check sulfate forms
                if "sulfate" in raw_name.lower():
                    if not any("sulfate" in form.lower() for form in cleaned_forms):
                        issues.append("Sulfate form not detected")
                
                # Check extract forms
                if "extract" in raw_name.lower():
                    if not any("extract" in form.lower() for form in cleaned_forms):
                        issues.append("Extract form not detected")
                
                # Check HCl forms
                if "hcl" in raw_name.lower():
                    if not any("hcl" in form.lower() or "hydrochloride" in form.lower() for form in cleaned_forms):
                        issues.append("HCl/Hydrochloride form not detected")
                
                if issues:
                    print(f"   ❌ Issues Found:")
                    for issue in issues:
                        print(f"      - {issue}")
                else:
                    print(f"   ✅ Form detection looks good")
                    
            else:
                print(f"   ⚠️  No matching cleaned ingredient found")
            
            print()
        
        return True
        
    except FileNotFoundError:
        print(f"❌ Test file not found: {test_file}")
        return False
    except Exception as e:
        print(f"❌ Error during testing: {str(e)}")
        return False

def analyze_common_form_patterns():
    """Analyze common form patterns that should be detected"""
    
    print("📊 Common Form Patterns Analysis\n")
    
    # Patterns commonly found in DSLD data that should be detected
    test_patterns = [
        # Vitamin forms with parentheses
        "Vitamin D (as cholecalciferol)",
        "Vitamin D (Form: as D3 (Alt. Name: Cholecalciferol))",
        "Vitamin C (as ascorbic acid)",
        "Vitamin A (as retinyl palmitate)",
        "Vitamin E (as d-alpha tocopheryl acetate)",
        
        # Mineral forms with sulfate
        "Ferrous sulfate", 
        "Zinc sulfate",
        "Copper sulfate",
        "Magnesium sulfate",
        "Chondroitin sulfate",
        
        # HCl forms
        "Glucosamine HCl",
        "Betaine HCl",
        "L-Lysine HCl",
        
        # Extract forms
        "Green tea extract",
        "Turmeric extract", 
        "Ginkgo biloba extract",
        "Boswellia serrata extract",
        "Milk thistle extract",
        
        # Complex botanical forms
        "Ginkgo biloba leaf extract standardized to 24% flavonoids",
        "Turmeric root extract (standardized to 95% curcuminoids)",
        "Green tea leaf extract (standardized to 50% EGCG)",
    ]
    
    normalizer = EnhancedDSLDNormalizer()
    
    print("Testing form extraction patterns:")
    
    for pattern in test_patterns:
        # Extract forms using current method
        extracted_forms = normalizer._extract_forms_from_ingredient_name(pattern)
        
        print(f"📋 '{pattern}'")
        print(f"   → Extracted: {extracted_forms if extracted_forms else ['unspecified']}")
        
        # Analyze what should be detected
        expected_forms = []
        pattern_lower = pattern.lower()
        
        # Check for common patterns that should be detected
        if "(" in pattern and ")" in pattern:
            paren_content = pattern[pattern.find("(")+1:pattern.find(")")].strip()
            if "as " in paren_content.lower():
                expected_forms.append(paren_content.replace("as ", "").strip())
        
        if "sulfate" in pattern_lower:
            expected_forms.append("sulfate")
        if "hcl" in pattern_lower:
            expected_forms.append("hydrochloride")
        if "extract" in pattern_lower:
            expected_forms.append("extract")
        if "standardized" in pattern_lower:
            expected_forms.append("standardized")
            
        if expected_forms:
            missing = [form for form in expected_forms if not any(form.lower() in ext.lower() for ext in extracted_forms)]
            if missing:
                print(f"   ❌ Missing: {missing}")
            else:
                print(f"   ✅ Good coverage")
        else:
            if not extracted_forms:
                print(f"   ✅ Correctly unspecified")
        
        print()

if __name__ == "__main__":
    print("🔍 FORM DETECTION ISSUE ANALYSIS\n")
    
    # Test with real DSLD data
    test_form_detection_with_real_data()
    
    print("="*60)
    print()
    
    # Analyze common patterns
    analyze_common_form_patterns()