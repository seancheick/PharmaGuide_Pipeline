#!/usr/bin/env python3
"""
Fix iteration safety issues in enhanced_normalizer.py
Ensures we never iterate over None values from .get() calls
"""

import re

def fix_iteration_issues():
    """Fix all instances where we might iterate over None values"""
    
    print("🔧 Fixing Iteration Safety Issues\n")
    
    # Read the current file
    with open("enhanced_normalizer.py", 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find problematic patterns
    patterns_to_fix = [
        {
            'old': r'for ([^)]+) in ([^)]+)\.get\("([^"]+)", \[\]\)',
            'new': r'for \1 in \2.get("\3", []) or []',
            'description': 'Ensure empty list fallback for iterations'
        },
        {
            'old': r'for ([^)]+) in ([^)]+)\.get\("([^"]+)", \{\}\)',
            'new': r'for \1 in (\2.get("\3", {}) or {}).items()',
            'description': 'Ensure empty dict fallback for dict iterations'
        }
    ]
    
    fixes_applied = 0
    
    for pattern in patterns_to_fix:
        matches = re.findall(pattern['old'], content)
        if matches:
            print(f"📋 {pattern['description']}: Found {len(matches)} instances")
            content = re.sub(pattern['old'], pattern['new'], content)
            fixes_applied += len(matches)
    
    # Specific manual fixes for complex cases
    manual_fixes = [
        {
            'old': 'for allergen in self.allergens_db.get("common_allergens", []):',
            'new': 'for allergen in self.allergens_db.get("common_allergens", []) or []:',
            'description': 'Allergen iteration safety'
        },
        {
            'old': 'for additive in self.harmful_additives.get("harmful_additives", []):',
            'new': 'for additive in self.harmful_additives.get("harmful_additives", []) or []:',
            'description': 'Harmful additives iteration safety'
        },
        {
            'old': 'for additive in self.non_harmful_additives.get("non_harmful_additives", []):',
            'new': 'for additive in self.non_harmful_additives.get("non_harmful_additives", []) or []:',
            'description': 'Non-harmful additives iteration safety'
        }
    ]
    
    for fix in manual_fixes:
        if fix['old'] in content:
            content = content.replace(fix['old'], fix['new'])
            fixes_applied += 1
            print(f"✅ {fix['description']}: Applied")
        else:
            print(f"⚠️  {fix['description']}: Pattern not found")
    
    # Write the fixed content back
    with open("enhanced_normalizer.py", 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"\n📊 Total fixes applied: {fixes_applied}")
    
    if fixes_applied > 0:
        print("✅ Iteration safety issues have been fixed!")
        return True
    else:
        print("ℹ️  No fixes were needed")
        return True

def verify_fixes():
    """Verify that the fixes worked correctly"""
    
    print("\n🧪 Verifying Fixes\n")
    
    try:
        # Test import still works
        from enhanced_normalizer import EnhancedDSLDNormalizer
        print("✅ Import test: Success")
        
        # Test basic functionality
        normalizer = EnhancedDSLDNormalizer()
        print("✅ Initialization test: Success")
        
        # Test with minimal data
        test_data = {
            "id": "test",
            "fullName": "Test",
            "brandName": "Test",
            "hasOuterCarton": None,
            "ingredientRows": [],
            "statements": []
        }
        
        result = normalizer.normalize_product(test_data)
        print("✅ Normalization test: Success")
        
        return True
        
    except Exception as e:
        print(f"❌ Verification failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = fix_iteration_issues()
    
    if success:
        verification_success = verify_fixes()
        
        if verification_success:
            print("\n🎉 All iteration safety issues have been successfully fixed and verified!")
        else:
            print("\n⚠️  Fixes applied but verification failed. Please check manually.")
    else:
        print("\n❌ Failed to apply fixes.")