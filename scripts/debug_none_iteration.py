#!/usr/bin/env python3
"""
Debug the specific None iteration issue
"""

import json
import sys
import traceback
from pathlib import Path

# Add the scripts directory to Python path
sys.path.append(str(Path(__file__).parent))

from enhanced_normalizer import EnhancedDSLDNormalizer

def debug_none_iteration():
    """Debug where the None iteration error occurs"""
    
    print("🔍 Debugging None Iteration Issue\n")
    
    normalizer = EnhancedDSLDNormalizer()
    
    # Test data with None values
    edge_case_data = {
        "id": "edge_test",
        "fullName": "Edge Case Test",
        "brandName": "Test",
        "hasOuterCarton": False,
        "ingredientRows": None,
        "statements": None,
        "contacts": None,
        "claims": None,
        "servingSizes": None,
        "targetGroups": None,
        "events": None,
        "labelRelationships": None,
        "images": None,
        "netContents": None,
        "otheringredients": None
    }
    
    try:
        result = normalizer.normalize_product(edge_case_data)
        print("✅ Success! Edge case handled properly.")
        print(f"Result keys: {list(result.keys())}")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print("\n📍 Full traceback:")
        traceback.print_exc()

if __name__ == "__main__":
    debug_none_iteration()