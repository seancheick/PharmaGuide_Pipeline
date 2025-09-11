#!/usr/bin/env python3
"""
Comprehensive Code Quality Check
Checks for potential issues, lint problems, and runtime errors
"""

import ast
import sys
import os
import traceback
from pathlib import Path

def check_syntax_and_imports():
    """Check syntax and import issues"""
    
    print("🔍 Code Quality Check\n")
    
    files_to_check = [
        "enhanced_normalizer.py",
        "constants.py"
    ]
    
    issues_found = []
    
    for file_name in files_to_check:
        print(f"📄 Checking {file_name}...")
        
        if not os.path.exists(file_name):
            issues_found.append(f"❌ {file_name}: File not found")
            continue
        
        # Check syntax
        try:
            with open(file_name, 'r', encoding='utf-8') as f:
                source = f.read()
            
            ast.parse(source, filename=file_name)
            print(f"   ✅ Syntax: Valid")
            
        except SyntaxError as e:
            issues_found.append(f"❌ {file_name}: Syntax error at line {e.lineno}: {e.msg}")
            print(f"   ❌ Syntax: Error at line {e.lineno}: {e.msg}")
            continue
        
        # Check imports
        try:
            if file_name == "enhanced_normalizer.py":
                from enhanced_normalizer import EnhancedDSLDNormalizer
                print(f"   ✅ Import: Success")
            elif file_name == "constants.py":
                import constants
                print(f"   ✅ Import: Success")
                
        except Exception as e:
            issues_found.append(f"❌ {file_name}: Import error: {str(e)}")
            print(f"   ❌ Import: {str(e)}")
        
        print()
    
    return issues_found

def check_critical_patterns():
    """Check for critical code patterns that might cause issues"""
    
    print("🔧 Critical Pattern Check\n")
    
    issues_found = []
    
    # Check enhanced_normalizer.py for potential issues
    try:
        with open("enhanced_normalizer.py", 'r', encoding='utf-8') as f:
            content = f.read()
        
        critical_checks = [
            {
                'pattern': 'raw_data.get("hasOuterCarton", None)',
                'description': 'hasOuterCarton field extraction',
                'expected': True
            },
            {
                'pattern': 'any(cert.startswith("Third-Party")',
                'description': 'thirdPartyTested fix',
                'expected': True
            },
            {
                'pattern': 'def normalize_product(',
                'description': 'Main normalization method',
                'expected': True
            },
            {
                'pattern': '# CRITICAL FIX',
                'description': 'Critical fix comments preserved',
                'expected': True
            }
        ]
        
        print("📋 Pattern Verification:")
        for check in critical_checks:
            found = check['pattern'] in content
            status = "✅" if found == check['expected'] else "❌"
            print(f"   {status} {check['description']}: {'Found' if found else 'Missing'}")
            
            if found != check['expected']:
                issues_found.append(f"Pattern issue: {check['description']}")
        
        print()
        
    except Exception as e:
        issues_found.append(f"Error reading enhanced_normalizer.py: {str(e)}")
    
    return issues_found

def check_constants_integrity():
    """Check constants.py for integrity"""
    
    print("⚙️ Constants Integrity Check\n")
    
    issues_found = []
    
    try:
        import constants
        
        # Check critical constants exist
        required_constants = [
            'STANDARDIZATION_PATTERNS',
            'CERTIFICATION_PATTERNS', 
            'EXCLUDED_NUTRITION_FACTS',
            'PROPRIETARY_BLEND_INDICATORS'
        ]
        
        print("📋 Required Constants:")
        for const_name in required_constants:
            if hasattr(constants, const_name):
                value = getattr(constants, const_name)
                print(f"   ✅ {const_name}: {type(value).__name__} with {len(value)} items")
            else:
                print(f"   ❌ {const_name}: Missing")
                issues_found.append(f"Missing constant: {const_name}")
        
        # Check STANDARDIZATION_PATTERNS specifically
        if hasattr(constants, 'STANDARDIZATION_PATTERNS'):
            patterns = constants.STANDARDIZATION_PATTERNS
            if len(patterns) >= 11:  # Should have at least 11 patterns now
                print(f"   ✅ STANDARDIZATION_PATTERNS: Enhanced with {len(patterns)} patterns")
            else:
                print(f"   ⚠️  STANDARDIZATION_PATTERNS: Only {len(patterns)} patterns (expected 11+)")
        
        print()
        
    except Exception as e:
        issues_found.append(f"Error checking constants: {str(e)}")
        print(f"   ❌ Constants check failed: {str(e)}\n")
    
    return issues_found

def test_basic_functionality():
    """Test basic functionality to catch runtime issues"""
    
    print("🧪 Basic Functionality Test\n")
    
    issues_found = []
    
    try:
        from enhanced_normalizer import EnhancedDSLDNormalizer
        
        # Initialize normalizer
        normalizer = EnhancedDSLDNormalizer()
        print("   ✅ Normalizer initialization: Success")
        
        # Test with minimal data
        minimal_data = {
            "id": "test123",
            "fullName": "Test Product",
            "brandName": "Test Brand",
            "hasOuterCarton": True,
            "ingredientRows": [],
            "statements": [],
            "contacts": []
        }
        
        result = normalizer.normalize_product(minimal_data)
        print("   ✅ Basic normalization: Success")
        
        # Check critical fields
        if 'hasOuterCarton' in result and result['hasOuterCarton'] == True:
            print("   ✅ hasOuterCarton transfer: Working")
        else:
            issues_found.append("hasOuterCarton not properly transferred")
            print("   ❌ hasOuterCarton transfer: Failed")
        
        if 'id' in result and result['id'] == "test123":
            print("   ✅ Basic field preservation: Working")
        else:
            issues_found.append("Basic field preservation failed")
            print("   ❌ Basic field preservation: Failed")
        
        print()
        
    except Exception as e:
        issues_found.append(f"Basic functionality test failed: {str(e)}")
        print(f"   ❌ Basic functionality test failed: {str(e)}\n")
        traceback.print_exc()
    
    return issues_found

def run_comprehensive_check():
    """Run all checks and provide summary"""
    
    print("🚀 Comprehensive Code Quality Check\n")
    print("="*60 + "\n")
    
    all_issues = []
    
    # Run all checks
    all_issues.extend(check_syntax_and_imports())
    all_issues.extend(check_critical_patterns()) 
    all_issues.extend(check_constants_integrity())
    all_issues.extend(test_basic_functionality())
    
    print("="*60 + "\n")
    print("📊 Final Summary:\n")
    
    if not all_issues:
        print("🎉 ALL CHECKS PASSED!")
        print("✅ No syntax errors")
        print("✅ No import issues") 
        print("✅ All critical patterns present")
        print("✅ Constants integrity verified")
        print("✅ Basic functionality working")
        print("\n🚀 Code is ready for production!")
        return True
    else:
        print(f"⚠️  {len(all_issues)} ISSUES FOUND:")
        for i, issue in enumerate(all_issues, 1):
            print(f"{i}. {issue}")
        print("\n🔧 Please address these issues before proceeding.")
        return False

if __name__ == "__main__":
    success = run_comprehensive_check()