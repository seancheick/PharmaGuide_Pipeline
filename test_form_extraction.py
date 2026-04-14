#!/usr/bin/env python3
"""
Test script to demonstrate form extraction from complex ingredient names
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))

from enhanced_normalizer import EnhancedDSLDNormalizer

# Create normalizer instance
normalizer = EnhancedDSLDNormalizer()

# Test ingredients with forms
test_cases = [
    "Vitamin C (as ascorbic acid and from ferment media)",
    "Vitamin D3 (as cholecalciferol and from ferment media)",
    "Vitamin E (as d-alpha-tocopheryl acetate and from ferment media)",
    "Vitamin B12 (as cyanocobalamin from ferment media)",
    "Folate (as L-5-methylfolate, and as 58 mcg folic acid from ferment media)",
    "Magnesium (as magnesium bisglycinate chelate, from organic algae Lithothamnion spp., and as magnesium oxide from ferment media)",
]

print("=" * 80)
print("FORM EXTRACTION TEST")
print("=" * 80)
print("\nThis test shows how your script extracts the FORM from ingredient names\n")
print("=" * 80)

for ingredient in test_cases:
    # Extract forms using the private method
    forms = normalizer._extract_forms_from_ingredient_name(ingredient)

    # Also show what the preprocessed name looks like
    preprocessed = normalizer.matcher.preprocess_text(ingredient)

    print(f"\nORIGINAL:")
    print(f"  {ingredient}")
    print(f"PREPROCESSED NAME:")
    print(f"  {preprocessed}")
    print(f"EXTRACTED FORMS:")
    if forms:
        for form in forms:
            print(f"  ✓ {form}")
    else:
        print(f"  (none)")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("""
Your script has TWO-STAGE processing:

1. INGREDIENT NAME: The base ingredient (e.g., "vitamin c")
   - Used to match against your ingredient database
   - Preprocessed to remove extra info

2. FORMS: Specific chemical forms (e.g., "ascorbic acid", "cyanocobalamin")
   - Extracted from parenthetical "as ..." patterns
   - Stored separately for detailed tracking
   - Used for quality scoring and bioavailability assessment

This means for:
  "Vitamin C (as ascorbic acid and from ferment media)"

You get:
  • Ingredient: "vitamin c" (matches your database)
  • Form: "ascorbic acid" (tracks the specific chemical form)

This is EXACTLY what you want for supplement analysis!
""")
