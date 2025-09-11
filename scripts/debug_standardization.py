#!/usr/bin/env python3
"""
Debug standardization detection for specific failing case
"""

import json
import sys
import re
from pathlib import Path

# Add the scripts directory to Python path
sys.path.append(str(Path(__file__).parent))

from enhanced_normalizer import EnhancedDSLDNormalizer
from constants import STANDARDIZATION_PATTERNS

def debug_standardization():
    """Debug why standardization isn't being detected"""
    
    print("🔍 Debugging Standardization Detection\n")
    
    # Load the failing test case
    file_path = "/Users/seancheick/Documents/DataSetDsld/Tablets-Pills-32882Labels-8-6-25/16640.json"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    
    print(f"Product: {raw_data.get('fullName', 'Unknown')}")
    print(f"Brand: {raw_data.get('brandName', 'Unknown')}\n")
    
    # Examine ingredients for standardization indicators
    print("🧪 Ingredient Analysis:")
    for i, ing in enumerate(raw_data.get('ingredientRows', []), 1):
        name = ing.get('name', '')
        notes = ing.get('notes', '')
        category = ing.get('category', '')
        
        print(f"{i}. {name}")
        print(f"   Notes: {notes}")
        print(f"   Category: {category}")
        
        # Test against patterns
        combined_text = f"{name} {notes}".lower()
        print(f"   Combined text: {combined_text}")
        
        # Check standardization patterns
        print(f"   Pattern matches:")
        for pattern_name, pattern in enumerate(STANDARDIZATION_PATTERNS):
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                print(f"     ✅ Pattern {pattern_name + 1}: {pattern} -> {match.groups()}")
            else:
                print(f"     ❌ Pattern {pattern_name + 1}: {pattern}")
        
        # Check for simple keywords
        keywords = ['extract', 'standardized', '%', 'ratio', 'concentrated', 'potency']
        keyword_matches = [kw for kw in keywords if kw in combined_text]
        print(f"   Keyword matches: {keyword_matches}")
        
        print()
    
    # Test with normalizer
    print("🧹 Normalizer Test:")
    normalizer = EnhancedDSLDNormalizer()
    cleaned_data = normalizer.normalize_product(raw_data)
    
    for i, ing in enumerate(cleaned_data.get('activeIngredients', []), 1):
        print(f"{i}. {ing.get('name', 'Unknown')}")
        print(f"   Standardized: {ing.get('standardized', False)}")
        print(f"   Natural: {ing.get('natural', False)}")
        print(f"   Mapped: {ing.get('mapped', False)}")
        print()

if __name__ == "__main__":
    debug_standardization()