#!/usr/bin/env python3
"""
Fix Boolean Flags Script
Identifies and fixes issues with boolean flags in the DSLD data cleaning pipeline
"""

import json
import sys
import os
from pathlib import Path

# Add the scripts directory to Python path
sys.path.append(str(Path(__file__).parent))

from enhanced_normalizer import EnhancedDSLDNormalizer

def test_boolean_flag_fixes():
    """Test and demonstrate fixes for boolean flags"""
    
    print("🔍 Testing Boolean Flag Fixes\n")
    
    # Sample test files from different product types
    test_files = [
        "/Users/seancheick/Documents/DataSetDsld/Tablets-Pills-32882Labels-8-6-25/29289.json",  # Nature's Bounty joint supplement
        "/Users/seancheick/Documents/DataSetDsld/Tablets-Pills-32882Labels-8-6-25/16640.json",  # Chinese herbal supplement  
        "/Users/seancheick/Documents/DataSetDsld/Softgels-19416labels-8-6-25/258907.json"       # Country Life astaxanthin
    ]
    
    normalizer = EnhancedDSLDNormalizer()
    
    results = {}
    
    for i, file_path in enumerate(test_files, 1):
        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            continue
            
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        
        print(f"📄 Test {i}: {raw_data.get('fullName', 'Unknown Product')}")
        print(f"   Brand: {raw_data.get('brandName', 'Unknown')}")
        
        # Test raw data
        print(f"\n📊 Raw Data Analysis:")
        print(f"   hasOuterCarton: {raw_data.get('hasOuterCarton', 'MISSING')}")
        
        # Check for standardization patterns in ingredient text
        standardized_ingredients = []
        for ing in raw_data.get('ingredientRows', []):
            name = ing.get('name', '')
            notes = ing.get('notes', '')
            combined_text = f"{name} {notes}".lower()
            
            # Check for standardization markers
            markers = ['standardized', 'extract', '%', 'mg/g', 'ratio']
            if any(marker in combined_text for marker in markers):
                standardized_ingredients.append({
                    'name': name,
                    'text': combined_text[:100] + '...' if len(combined_text) > 100 else combined_text
                })
        
        print(f"   Potential standardized ingredients: {len(standardized_ingredients)}")
        for std_ing in standardized_ingredients[:3]:  # Show first 3
            print(f"     - {std_ing['name']}: {std_ing['text']}")
        
        # Check for third-party testing mentions in statements
        third_party_mentions = []
        for stmt in raw_data.get('statements', []):
            notes = stmt.get('notes', '').lower()
            if any(term in notes for term in ['third party', '3rd party', 'tested', 'verified', 'gmp', 'nsf', 'usp']):
                third_party_mentions.append(notes[:150] + '...' if len(notes) > 150 else notes)
        
        print(f"   Third-party testing mentions: {len(third_party_mentions)}")
        for mention in third_party_mentions[:2]:  # Show first 2
            print(f"     - {mention}")
        
        # Process with normalizer
        cleaned_data = normalizer.normalize_product(raw_data)
        
        print(f"\n🧹 Cleaned Data Analysis:")
        print(f"   hasOuterCarton: {cleaned_data.get('hasOuterCarton', 'STILL MISSING')}")
        print(f"   hasCertifications: {cleaned_data.get('hasCertifications', False)}")
        print(f"   upcValid: {cleaned_data.get('upcValid', False)}")
        
        # Check ingredient-level flags
        standardized_count = 0
        natural_count = 0
        mapped_count = 0
        
        for ing in cleaned_data.get('activeIngredients', []):
            if ing.get('standardized', False):
                standardized_count += 1
            if ing.get('natural', False):
                natural_count += 1
            if ing.get('mapped', False):
                mapped_count += 1
        
        print(f"   Active ingredients with standardized=True: {standardized_count}")
        print(f"   Active ingredients with natural=True: {natural_count}")
        print(f"   Active ingredients with mapped=True: {mapped_count}")
        
        # Check statement-level flags
        gmp_statements = sum(1 for stmt in cleaned_data.get('statements', []) if stmt.get('gmpCertified', False))
        third_party_statements = sum(1 for stmt in cleaned_data.get('statements', []) if stmt.get('thirdPartyTested', False))
        
        print(f"   Statements with gmpCertified=True: {gmp_statements}")
        print(f"   Statements with thirdPartyTested=True: {third_party_statements}")
        
        # Check metadata flags
        metadata = cleaned_data.get('metadata', {})
        enhanced_features = metadata.get('enhancedFeatures', {})
        print(f"   nestedIngredientsFlattened: {enhanced_features.get('nestedIngredientsFlattened', False)}")
        
        quality_flags = metadata.get('qualityFlags', {})
        print(f"   hasStandardized (quality flag): {quality_flags.get('hasStandardized', False)}")
        
        results[file_path] = {
            'raw_hasOuterCarton': raw_data.get('hasOuterCarton'),
            'cleaned_hasOuterCarton': cleaned_data.get('hasOuterCarton'),
            'standardized_ingredients': standardized_count,
            'third_party_mentions': len(third_party_mentions),
            'third_party_statements': third_party_statements
        }
        
        print("\n" + "="*80 + "\n")
    
    print("📋 Summary of Issues Found:")
    print("1. hasOuterCarton field is not being copied from raw to cleaned data")
    print("2. Standardized ingredient detection may have threshold issues")
    print("3. Third-party testing pattern matching needs verification")
    
    return results

def create_fixes():
    """Create fixes for the identified boolean flag issues"""
    
    print("🔧 Creating Fixes for Boolean Flags\n")
    
    fixes = [
        {
            'issue': 'hasOuterCarton always null',
            'location': 'normalize_product method',
            'fix': 'Add hasOuterCarton field extraction from raw data',
            'code': '''
# Add to the cleaned product dictionary around line 1702:
"hasOuterCarton": raw_data.get("hasOuterCarton", None),  # Add this line
"upcValid": self._validate_upc(raw_data.get("upcSku", "")),
'''
        },
        {
            'issue': 'Third-party testing pattern mismatch',
            'location': '_process_statements method',
            'fix': 'Fix certification key matching',
            'code': '''
# Fix the thirdPartyTested logic (around line 2388):
# Change from:
"thirdPartyTested": "Third-Party" in certifications
# To:
"thirdPartyTested": any(cert.startswith("Third-Party") for cert in certifications)
'''
        },
        {
            'issue': 'Standardized ingredient thresholds',
            'location': '_check_standardized_botanicals method',
            'fix': 'Lower detection threshold and improve patterns',
            'code': '''
# In _check_standardized_botanicals method, improve detection:
# Add more standardization markers
standardization_markers = [
    "standardized", "extract", "concentrated", "potency",
    "mg/g", "ratio", "% ", "percent", "guaranteed potency"
]
'''
        }
    ]
    
    for i, fix in enumerate(fixes, 1):
        print(f"🔧 Fix {i}: {fix['issue']}")
        print(f"   Location: {fix['location']}")
        print(f"   Solution: {fix['fix']}")
        print(f"   Code changes:")
        print(fix['code'])
        print()
    
    return fixes

if __name__ == "__main__":
    # Test current state
    results = test_boolean_flag_fixes()
    
    # Show proposed fixes
    fixes = create_fixes()
    
    print("✅ Boolean flag analysis complete!")
    print("📌 Next steps: Apply the fixes above to enhanced_normalizer.py")