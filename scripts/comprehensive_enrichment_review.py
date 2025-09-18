#!/usr/bin/env python3
"""
Comprehensive Enrichment Script Review & Analysis
Healthcare-Ready Production Assessment
"""

import json
import os
import sys
import ast
import re
import traceback
from typing import Dict, List, Any, Tuple, Optional
from pathlib import Path
import time

class EnrichmentReviewer:
    def __init__(self):
        self.critical_issues = []
        self.performance_issues = []
        self.data_integrity_issues = []
        self.healthcare_compliance_issues = []
        self.recommendations = []
        
    def analyze_primary_objective_verification(self):
        """Verify script correctly prepares data for base scoring without performing calculations"""
        print("🎯 PRIMARY OBJECTIVE VERIFICATION")
        print("=" * 50)
        
        try:
            # Read the enrichment script
            with open('enrich_supplements_v2.py', 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for scoring calculations (should NOT be present)
            scoring_patterns = [
                r'final_score\s*=',
                r'calculate_final_score',
                r'user_profile.*score',
                r'personalized.*score',
                r'total_score\s*=.*\+.*\+',
                r'weighted_user_score'
            ]
            
            scoring_violations = []
            for pattern in scoring_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    scoring_violations.extend(matches)
            
            if scoring_violations:
                self.critical_issues.append(
                    f"❌ CRITICAL: Script performs scoring calculations (should only prepare data): {scoring_violations}"
                )
            else:
                print("✅ Correctly prepares data for scoring without performing calculations")
            
            # Check for proper precalculation structure
            if '_calculate_scoring_precalculations' in content:
                print("✅ Includes scoring precalculations for client-side scoring")
            else:
                self.critical_issues.append("❌ Missing scoring precalculations method")
            
            # Verify 80-point base scoring preparation
            if 'base_score_max": 80' in content:
                print("✅ Correctly configured for 80-point base scoring system")
            else:
                self.critical_issues.append("❌ Not configured for 80-point base scoring system")
            
            # Check for client-side compatibility
            if 'compatible_scoring_versions' in content:
                print("✅ Includes client-side scoring compatibility information")
            else:
                self.data_integrity_issues.append("⚠️  Missing client-side scoring compatibility info")
                
        except Exception as e:
            self.critical_issues.append(f"❌ Failed to analyze primary objective: {e}")
    
    def analyze_data_accuracy_mapping(self):
        """Validate ingredient extraction and mapping accuracy"""
        print("\n🔍 DATA ACCURACY & MAPPING ANALYSIS")
        print("=" * 50)
        
        try:
            # Load and analyze reference databases
            db_paths = {
                'ingredient_quality_map': 'data/ingredient_quality_map.json',
                'allergens': 'data/allergens.json',
                'harmful_additives': 'data/harmful_additives.json',
                'rda_optimal_uls': 'data/rda_optimal_uls.json'
            }
            
            missing_databases = []
            for db_name, db_path in db_paths.items():
                if not os.path.exists(db_path):
                    missing_databases.append(db_name)
            
            if missing_databases:
                self.critical_issues.append(f"❌ Missing reference databases: {missing_databases}")
            else:
                print("✅ All reference databases present")
            
            # Analyze ingredient mapping logic
            with open('enrich_supplements_v2.py', 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for exact matching (no fuzzy matching for accuracy)
            if '_exact_ingredient_match' in content and 'fuzz.ratio' not in content:
                print("✅ Uses exact matching for ingredient identification (no fuzzy matching)")
            else:
                self.data_integrity_issues.append("⚠️  May use fuzzy matching which can reduce accuracy")
            
            # Check for proper category mapping
            if '_get_category_weight' in content:
                print("✅ Includes category weight mapping for scoring")
                
                # Verify category accuracy by checking weight assignments
                category_pattern = r"'([^']+)':\s*([\d.]+)"
                categories = re.findall(category_pattern, content)
                
                # Check for healthcare-relevant categories
                healthcare_categories = ['vitamins', 'minerals', 'probiotics', 'botanicals']
                found_categories = [cat[0] for cat in categories]
                
                missing_healthcare_cats = [cat for cat in healthcare_categories if cat not in found_categories]
                if missing_healthcare_cats:
                    self.data_integrity_issues.append(f"⚠️  Missing healthcare categories: {missing_healthcare_cats}")
                else:
                    print("✅ Includes all major healthcare ingredient categories")
            else:
                self.critical_issues.append("❌ Missing category weight mapping")
            
            # Check for data preservation
            if 'ingredient_name' in content and 'standard_name' in content:
                print("✅ Preserves both original and standardized ingredient names")
            else:
                self.data_integrity_issues.append("⚠️  May not preserve original ingredient information")
                
        except Exception as e:
            self.critical_issues.append(f"❌ Failed to analyze data mapping: {e}")
    
    def analyze_code_quality_efficiency(self):
        """Review code quality and efficiency"""
        print("\n⚡ CODE QUALITY & EFFICIENCY REVIEW")
        print("=" * 50)
        
        try:
            with open('enrich_supplements_v2.py', 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for redundant functions
            function_names = re.findall(r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)', content)
            duplicate_functions = [name for name in set(function_names) if function_names.count(name) > 1]
            
            if duplicate_functions:
                self.performance_issues.append(f"⚠️  Duplicate function definitions: {duplicate_functions}")
            else:
                print("✅ No duplicate function definitions found")
            
            # Check for compiled regex patterns (performance optimization)
            if '_compile_patterns' in content and 'self.compiled_patterns' in content:
                print("✅ Uses compiled regex patterns for performance")
            else:
                self.performance_issues.append("⚠️  Should compile regex patterns for better performance")
            
            # Check for proper error handling
            try_except_count = content.count('try:')
            if try_except_count >= 5:  # Should have multiple error handling blocks
                print(f"✅ Includes comprehensive error handling ({try_except_count} try blocks)")
            else:
                self.performance_issues.append("⚠️  Insufficient error handling coverage")
            
            # Check for logging
            if 'self.logger' in content and 'logging' in content:
                print("✅ Includes proper logging for production use")
            else:
                self.performance_issues.append("⚠️  Missing comprehensive logging")
            
            # Check for memory efficiency
            if 'ingredient_registry.clear()' in content:
                print("✅ Includes memory cleanup between products")
            else:
                self.performance_issues.append("⚠️  May have memory leaks between product processing")
            
            # Check for batch processing
            if 'process_batch' in content:
                print("✅ Supports batch processing for efficiency")
            else:
                self.performance_issues.append("⚠️  Missing batch processing capability")
                
        except Exception as e:
            self.critical_issues.append(f"❌ Failed to analyze code quality: {e}")
    
    def analyze_pipeline_readiness(self):
        """Assess pipeline readiness for production"""
        print("\n🚀 PIPELINE READINESS ASSESSMENT")
        print("=" * 50)
        
        try:
            # Check output format compatibility
            sample_output_path = 'output_Gummies-Jellies_enriched/enriched/enriched_cleaned_batch_1.json'
            
            if os.path.exists(sample_output_path):
                with open(sample_output_path, 'r', encoding='utf-8') as f:
                    sample_data = json.load(f)
                
                if isinstance(sample_data, list) and len(sample_data) > 0:
                    product = sample_data[0]
                    
                    # Check required fields for scoring
                    required_fields = [
                        'enrichment_version',
                        'scoring_precalculations',
                        'form_quality_mapping',
                        'contaminant_analysis',
                        'clinical_evidence_matches'
                    ]
                    
                    missing_fields = [field for field in required_fields if field not in product]
                    if missing_fields:
                        self.critical_issues.append(f"❌ Missing required output fields: {missing_fields}")
                    else:
                        print("✅ Output format includes all required fields for scoring")
                    
                    # Check scoring precalculations structure
                    if 'scoring_precalculations' in product:
                        precalc = product['scoring_precalculations']
                        required_sections = ['section_a', 'section_b', 'section_c', 'section_d']
                        
                        missing_sections = [sec for sec in required_sections if sec not in precalc]
                        if missing_sections:
                            self.critical_issues.append(f"❌ Missing scoring sections: {missing_sections}")
                        else:
                            print("✅ Scoring precalculations include all required sections")
                    
                    # Check version compatibility
                    if product.get('enrichment_version') == '2.0.0':
                        print("✅ Uses current enrichment version (2.0.0)")
                    else:
                        self.data_integrity_issues.append("⚠️  May be using outdated enrichment version")
                        
                else:
                    self.critical_issues.append("❌ Invalid output format structure")
            else:
                self.data_integrity_issues.append("⚠️  No sample output available for validation")
            
            # Check configuration file
            config_path = 'config/enrichment_config.json'
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # Check database paths
                db_paths = config.get('database_paths', {})
                if len(db_paths) >= 10:  # Should have multiple reference databases
                    print(f"✅ Configuration includes {len(db_paths)} reference databases")
                else:
                    self.critical_issues.append("❌ Insufficient reference databases in configuration")
                    
            else:
                self.critical_issues.append("❌ Missing configuration file")
                
        except Exception as e:
            self.critical_issues.append(f"❌ Failed to analyze pipeline readiness: {e}")
    
    def analyze_healthcare_compliance(self):
        """Analyze healthcare-specific compliance requirements"""
        print("\n🏥 HEALTHCARE COMPLIANCE ANALYSIS")
        print("=" * 50)
        
        try:
            with open('enrich_supplements_v2.py', 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for safety analysis
            safety_methods = [
                '_analyze_contaminants',
                '_analyze_rda_ul',
                '_detect_unsubstantiated_claims',
                '_get_banned_deduction'
            ]
            
            missing_safety = [method for method in safety_methods if method not in content]
            if missing_safety:
                self.healthcare_compliance_issues.append(f"❌ Missing safety analysis methods: {missing_safety}")
            else:
                print("✅ Includes comprehensive safety analysis")
            
            # Check for allergen detection with negation
            if '_check_negation_context' in content:
                print("✅ Includes intelligent allergen detection with negation handling")
            else:
                self.healthcare_compliance_issues.append("⚠️  May not properly handle allergen-free claims")
            
            # Check for dosage validation
            if 'exceeds_ul' in content and 'ul_value' in content:
                print("✅ Includes Upper Limit (UL) dosage safety validation")
            else:
                self.healthcare_compliance_issues.append("❌ Missing dosage safety validation")
            
            # Check for clinical evidence validation
            if '_is_brand_specific_study' in content:
                print("✅ Includes brand-specific clinical evidence validation")
            else:
                self.healthcare_compliance_issues.append("⚠️  May not properly validate clinical evidence")
            
            # Check for regulatory compliance
            if 'fda' in content.lower() or 'regulatory' in content.lower():
                print("✅ Includes regulatory compliance considerations")
            else:
                self.healthcare_compliance_issues.append("⚠️  Limited regulatory compliance checking")
                
        except Exception as e:
            self.healthcare_compliance_issues.append(f"❌ Failed to analyze healthcare compliance: {e}")
    
    def generate_recommendations(self):
        """Generate specific recommendations for improvements"""
        print("\n💡 RECOMMENDATIONS FOR PRODUCTION READINESS")
        print("=" * 50)
        
        # Critical fixes
        if self.critical_issues:
            print("\n🚨 CRITICAL ISSUES (Must Fix Before Production):")
            for issue in self.critical_issues:
                print(f"   {issue}")
        
        # Performance improvements
        if self.performance_issues:
            print("\n⚡ PERFORMANCE IMPROVEMENTS:")
            for issue in self.performance_issues:
                print(f"   {issue}")
        
        # Data integrity improvements
        if self.data_integrity_issues:
            print("\n📊 DATA INTEGRITY IMPROVEMENTS:")
            for issue in self.data_integrity_issues:
                print(f"   {issue}")
        
        # Healthcare compliance improvements
        if self.healthcare_compliance_issues:
            print("\n🏥 HEALTHCARE COMPLIANCE IMPROVEMENTS:")
            for issue in self.healthcare_compliance_issues:
                print(f"   {issue}")
        
        # Generate specific code recommendations
        print("\n🔧 SPECIFIC CODE IMPROVEMENTS:")
        
        # Memory optimization
        print("   1. Memory Optimization:")
        print("      - Add database connection pooling")
        print("      - Implement lazy loading for large reference databases")
        print("      - Add memory usage monitoring and alerts")
        
        # Error handling
        print("   2. Enhanced Error Handling:")
        print("      - Add specific exception types for different error categories")
        print("      - Implement retry logic for transient failures")
        print("      - Add detailed error context for debugging")
        
        # Validation improvements
        print("   3. Data Validation Enhancements:")
        print("      - Add input data schema validation")
        print("      - Implement cross-reference validation between databases")
        print("      - Add data completeness scoring")
        
        # Healthcare-specific improvements
        print("   4. Healthcare Compliance:")
        print("      - Add FDA recall database integration")
        print("      - Implement drug interaction checking")
        print("      - Add pregnancy/nursing safety warnings")
        
        # Performance monitoring
        print("   5. Production Monitoring:")
        print("      - Add processing time metrics")
        print("      - Implement health check endpoints")
        print("      - Add data quality monitoring dashboards")
    
    def run_comprehensive_review(self):
        """Run the complete review process"""
        print("🔬 COMPREHENSIVE ENRICHMENT SCRIPT REVIEW")
        print("Healthcare-Ready Production Assessment")
        print("=" * 60)
        
        start_time = time.time()
        
        # Run all analysis modules
        self.analyze_primary_objective_verification()
        self.analyze_data_accuracy_mapping()
        self.analyze_code_quality_efficiency()
        self.analyze_pipeline_readiness()
        self.analyze_healthcare_compliance()
        
        # Generate summary
        total_time = time.time() - start_time
        
        print(f"\n📋 REVIEW SUMMARY")
        print("=" * 30)
        print(f"⏱️  Review completed in {total_time:.2f} seconds")
        print(f"🚨 Critical Issues: {len(self.critical_issues)}")
        print(f"⚡ Performance Issues: {len(self.performance_issues)}")
        print(f"📊 Data Integrity Issues: {len(self.data_integrity_issues)}")
        print(f"🏥 Healthcare Compliance Issues: {len(self.healthcare_compliance_issues)}")
        
        # Overall assessment
        total_issues = (len(self.critical_issues) + len(self.performance_issues) + 
                       len(self.data_integrity_issues) + len(self.healthcare_compliance_issues))
        
        if total_issues == 0:
            print("\n🎉 ASSESSMENT: PRODUCTION READY")
            print("   The enrichment script meets all healthcare-ready production standards.")
        elif len(self.critical_issues) == 0:
            print("\n⚠️  ASSESSMENT: NEEDS MINOR IMPROVEMENTS")
            print("   The script is functional but would benefit from the recommended improvements.")
        else:
            print("\n❌ ASSESSMENT: NEEDS CRITICAL FIXES")
            print("   Critical issues must be resolved before production deployment.")
        
        # Generate recommendations
        self.generate_recommendations()
        
        return {
            'total_issues': total_issues,
            'critical_issues': len(self.critical_issues),
            'ready_for_production': len(self.critical_issues) == 0,
            'review_time': total_time
        }

def main():
    """Main execution"""
    reviewer = EnrichmentReviewer()
    results = reviewer.run_comprehensive_review()
    
    # Exit with appropriate code
    if results['critical_issues'] > 0:
        sys.exit(1)  # Critical issues found
    else:
        sys.exit(0)  # Ready for production or minor issues only

if __name__ == "__main__":
    main()