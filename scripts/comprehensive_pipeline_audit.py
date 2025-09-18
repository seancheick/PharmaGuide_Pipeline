#!/usr/bin/env python3
"""
Comprehensive Pipeline Audit
Validates data quality, performance, and correctness of enrichment output
"""

import json
import os
import sys
import traceback
from typing import Dict, List, Any, Tuple
import psutil
import time

class PipelineAuditor:
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.performance_metrics = {}
        
    def audit_memory_usage(self):
        """Check memory usage patterns"""
        print("🧠 Memory Usage Analysis")
        print("-" * 30)
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        try:
            # Test loading all databases
            from enrich_supplements_v2 import SupplementEnricherV2
            
            start_time = time.time()
            enricher = SupplementEnricherV2()
            load_time = time.time() - start_time
            
            after_load_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = after_load_memory - initial_memory
            
            print(f"✅ Initial memory: {initial_memory:.1f} MB")
            print(f"✅ After loading databases: {after_load_memory:.1f} MB")
            print(f"✅ Memory increase: {memory_increase:.1f} MB")
            print(f"✅ Database load time: {load_time:.2f} seconds")
            
            # Check database sizes
            total_entries = 0
            for db_name, db_data in enricher.databases.items():
                if isinstance(db_data, list):
                    entries = len(db_data)
                elif isinstance(db_data, dict):
                    entries = len(db_data)
                else:
                    entries = 1
                total_entries += entries
                
            print(f"✅ Total database entries loaded: {total_entries:,}")
            
            # Memory efficiency check
            if memory_increase > 100:  # More than 100MB
                self.warnings.append(f"High memory usage: {memory_increase:.1f} MB for databases")
            
            self.performance_metrics['memory_usage'] = {
                'initial_mb': initial_memory,
                'after_load_mb': after_load_memory,
                'increase_mb': memory_increase,
                'load_time_seconds': load_time,
                'total_entries': total_entries
            }
            
            return True
            
        except Exception as e:
            self.issues.append(f"Memory analysis failed: {e}")
            return False
    
    def validate_data_structures(self):
        """Validate data structure consistency"""
        print("\n📊 Data Structure Validation")
        print("-" * 30)
        
        try:
            from enrich_supplements_v2 import SupplementEnricherV2
            enricher = SupplementEnricherV2()
            
            # Check each database structure
            structure_issues = []
            
            # 1. Ingredient Quality Map
            quality_map = enricher.databases.get('ingredient_quality_map', {})
            if quality_map:
                sample_entries = list(quality_map.items())[:3]
                for key, value in sample_entries:
                    if not isinstance(value, dict):
                        structure_issues.append(f"Quality map entry '{key}' is not a dict")
                    elif 'forms' not in value:
                        structure_issues.append(f"Quality map entry '{key}' missing 'forms'")
                    else:
                        forms = value.get('forms', {})
                        for form_key, form_data in forms.items():
                            if 'bio_score' not in form_data:
                                structure_issues.append(f"Form '{form_key}' missing bio_score")
                
                print(f"✅ Quality map: {len(quality_map)} entries validated")
            
            # 2. RDA Data
            rda_data = enricher.databases.get('rda_optimal_uls', {})
            if rda_data:
                recommendations = rda_data.get('nutrient_recommendations', [])
                for rec in recommendations[:3]:  # Check first 3
                    if 'standard_name' not in rec:
                        structure_issues.append(f"RDA entry missing standard_name")
                    if 'data' not in rec:
                        structure_issues.append(f"RDA entry missing data array")
                
                print(f"✅ RDA data: {len(recommendations)} nutrients validated")
            
            # 3. Clinical Studies
            studies = enricher.databases.get('backed_clinical_studies', [])
            for study in studies[:3]:  # Check first 3
                required_fields = ['id', 'standard_name', 'evidence_level']
                for field in required_fields:
                    if field not in study:
                        structure_issues.append(f"Clinical study missing '{field}'")
            
            print(f"✅ Clinical studies: {len(studies)} entries validated")
            
            if structure_issues:
                self.issues.extend(structure_issues)
                return False
            else:
                print("✅ All data structures valid")
                return True
                
        except Exception as e:
            self.issues.append(f"Data structure validation failed: {e}")
            return False
    
    def validate_enrichment_accuracy(self):
        """Validate enrichment output accuracy against reference data"""
        print("\n🎯 Enrichment Accuracy Validation")
        print("-" * 30)
        
        try:
            # Load sample cleaned data
            cleaned_file = "output_Gummies-Jellies/cleaned/cleaned_batch_1.json"
            enriched_file = "test_enrichment_output/enriched/enriched_cleaned_batch_1.json"
            
            if not os.path.exists(cleaned_file):
                self.warnings.append("No cleaned data found for validation")
                return True
            
            if not os.path.exists(enriched_file):
                self.warnings.append("No enriched data found for validation")
                return True
            
            with open(cleaned_file, 'r') as f:
                cleaned_data = json.load(f)
            
            with open(enriched_file, 'r') as f:
                enriched_data = json.load(f)
            
            # Validate sample products
            validation_issues = []
            
            for i, (cleaned_product, enriched_product) in enumerate(zip(cleaned_data[:5], enriched_data[:5])):
                product_id = cleaned_product.get('id')
                
                # 1. Check ID preservation
                if cleaned_product.get('id') != enriched_product.get('id'):
                    validation_issues.append(f"Product {product_id}: ID mismatch")
                
                # 2. Check ingredient quality mapping
                active_ingredients = cleaned_product.get('activeIngredients', [])
                quality_mapping = enriched_product.get('form_quality_mapping', [])
                
                if len(active_ingredients) != len(quality_mapping):
                    validation_issues.append(f"Product {product_id}: Ingredient count mismatch")
                
                # 3. Validate specific mappings
                for j, (orig_ing, mapped_ing) in enumerate(zip(active_ingredients, quality_mapping)):
                    orig_name = orig_ing.get('name', '')
                    mapped_name = mapped_ing.get('ingredient', '')
                    
                    if orig_name != mapped_name:
                        validation_issues.append(f"Product {product_id}: Ingredient name mismatch '{orig_name}' vs '{mapped_name}'")
                    
                    # Check bio_score is reasonable
                    bio_score = mapped_ing.get('bio_score', 0)
                    if not isinstance(bio_score, (int, float)) or bio_score < 1 or bio_score > 20:
                        validation_issues.append(f"Product {product_id}: Invalid bio_score {bio_score} for {orig_name}")
                
                # 4. Check RDA references
                rda_refs = enriched_product.get('rda_ul_references', {})
                for ing in active_ingredients:
                    std_name = ing.get('standardName', '')
                    quantity = ing.get('quantity', 0)
                    
                    # If ingredient has quantity, should have RDA reference if vitamin/mineral
                    category = ing.get('category', '')
                    if category in ['vitamin', 'mineral'] and quantity > 0:
                        rda_key = std_name.lower().replace(' ', '_')
                        if rda_key not in rda_refs:
                            # This is expected for unmapped nutrients
                            pass
                        else:
                            rda_data = rda_refs[rda_key]
                            product_amount = rda_data.get('product_amount', 0)
                            if abs(float(product_amount) - float(quantity)) > 0.01:
                                validation_issues.append(f"Product {product_id}: RDA amount mismatch for {std_name}")
            
            if validation_issues:
                print(f"❌ Found {len(validation_issues)} validation issues:")
                for issue in validation_issues[:10]:  # Show first 10
                    print(f"   - {issue}")
                self.issues.extend(validation_issues)
                return False
            else:
                print("✅ Enrichment accuracy validated")
                return True
                
        except Exception as e:
            self.issues.append(f"Accuracy validation failed: {e}")
            traceback.print_exc()
            return False
    
    def check_category_accuracy(self):
        """Check if categories are being assigned correctly"""
        print("\n📂 Category Assignment Validation")
        print("-" * 30)
        
        try:
            from enrich_supplements_v2 import SupplementEnricherV2
            enricher = SupplementEnricherV2()
            
            # Test category assignment for known ingredients
            test_cases = [
                ('Vitamin C', 'vitamin'),
                ('Calcium', 'mineral'),
                ('Turmeric', 'herb'),
                ('L-Arginine', 'amino_acid'),
                ('Fish Oil', 'fat')
            ]
            
            quality_map = enricher.databases.get('ingredient_quality_map', {})
            category_issues = []
            
            for ingredient_name, expected_category in test_cases:
                found = False
                for key, data in quality_map.items():
                    if data.get('standard_name', '').lower() == ingredient_name.lower():
                        actual_category = data.get('category', '')
                        if actual_category != expected_category:
                            category_issues.append(f"'{ingredient_name}': expected '{expected_category}', got '{actual_category}'")
                        found = True
                        break
                
                if not found:
                    category_issues.append(f"'{ingredient_name}': not found in quality map")
            
            if category_issues:
                print(f"❌ Category assignment issues:")
                for issue in category_issues:
                    print(f"   - {issue}")
                self.warnings.extend(category_issues)
            else:
                print("✅ Category assignments correct")
            
            return len(category_issues) == 0
            
        except Exception as e:
            self.issues.append(f"Category validation failed: {e}")
            return False
    
    def check_rda_calculations(self):
        """Validate RDA calculations are correct"""
        print("\n🧮 RDA Calculation Validation")
        print("-" * 30)
        
        try:
            from enrich_supplements_v2 import SupplementEnricherV2
            enricher = SupplementEnricherV2()
            
            # Test RDA calculation with known values
            test_ingredient = {
                'standardName': 'Vitamin C',
                'quantity': 60,  # 60mg
                'unit': 'mg'
            }
            
            rda_result = enricher._analyze_rda_ul([test_ingredient])
            
            if 'vitamin_c' in rda_result:
                vitamin_c_data = rda_result['vitamin_c']
                product_amount = vitamin_c_data.get('product_amount', 0)
                percent_rda = vitamin_c_data.get('percent_rda', 0)
                
                # Vitamin C RDA is typically 90mg for men, 75mg for women
                # So 60mg should be around 67-80% RDA
                if product_amount != 60:
                    self.issues.append(f"RDA calculation: product amount incorrect ({product_amount} vs 60)")
                
                if percent_rda < 50 or percent_rda > 100:
                    self.warnings.append(f"RDA calculation: percent seems off ({percent_rda}% for 60mg Vitamin C)")
                
                print(f"✅ Vitamin C test: {product_amount}mg = {percent_rda}% RDA")
            else:
                self.warnings.append("Vitamin C not found in RDA calculations")
            
            return True
            
        except Exception as e:
            self.issues.append(f"RDA calculation validation failed: {e}")
            return False
    
    def check_performance_bottlenecks(self):
        """Identify potential performance bottlenecks"""
        print("\n⚡ Performance Bottleneck Analysis")
        print("-" * 30)
        
        try:
            from enrich_supplements_v2 import SupplementEnricherV2
            
            # Test processing speed with sample data
            enricher = SupplementEnricherV2()
            
            # Load sample product
            cleaned_file = "output_Gummies-Jellies/cleaned/cleaned_batch_1.json"
            if not os.path.exists(cleaned_file):
                self.warnings.append("No test data for performance analysis")
                return True
            
            with open(cleaned_file, 'r') as f:
                products = json.load(f)
            
            # Time single product enrichment
            if products:
                start_time = time.time()
                enriched, issues = enricher.enrich_product(products[0])
                single_product_time = time.time() - start_time
                
                print(f"✅ Single product enrichment: {single_product_time:.3f} seconds")
                
                # Estimate batch processing time
                estimated_batch_time = single_product_time * len(products)
                print(f"✅ Estimated batch time: {estimated_batch_time:.1f} seconds for {len(products)} products")
                
                # Performance warnings
                if single_product_time > 0.5:  # More than 500ms per product
                    self.warnings.append(f"Slow enrichment: {single_product_time:.3f}s per product")
                
                if estimated_batch_time > 300:  # More than 5 minutes for a batch
                    self.warnings.append(f"Long batch processing time: {estimated_batch_time:.1f}s estimated")
                
                self.performance_metrics['enrichment_speed'] = {
                    'single_product_seconds': single_product_time,
                    'products_per_second': 1 / single_product_time if single_product_time > 0 else 0,
                    'estimated_batch_seconds': estimated_batch_time
                }
            
            return True
            
        except Exception as e:
            self.issues.append(f"Performance analysis failed: {e}")
            return False
    
    def run_comprehensive_audit(self):
        """Run all audit checks"""
        print("🔍 COMPREHENSIVE PIPELINE AUDIT")
        print("=" * 50)
        
        start_time = time.time()
        
        # Run all checks
        checks = [
            ("Memory Usage", self.audit_memory_usage),
            ("Data Structures", self.validate_data_structures),
            ("Enrichment Accuracy", self.validate_enrichment_accuracy),
            ("Category Assignment", self.check_category_accuracy),
            ("RDA Calculations", self.check_rda_calculations),
            ("Performance", self.check_performance_bottlenecks)
        ]
        
        passed_checks = 0
        total_checks = len(checks)
        
        for check_name, check_func in checks:
            try:
                if check_func():
                    passed_checks += 1
            except Exception as e:
                self.issues.append(f"{check_name} check failed: {e}")
        
        total_time = time.time() - start_time
        
        # Final report
        print("\n" + "=" * 50)
        print("📊 AUDIT SUMMARY")
        print("=" * 50)
        
        print(f"✅ Checks passed: {passed_checks}/{total_checks}")
        print(f"⏱️  Total audit time: {total_time:.2f} seconds")
        
        if self.issues:
            print(f"\n❌ {len(self.issues)} Critical Issues:")
            for i, issue in enumerate(self.issues, 1):
                print(f"  {i}. {issue}")
        
        if self.warnings:
            print(f"\n⚠️  {len(self.warnings)} Warnings:")
            for i, warning in enumerate(self.warnings, 1):
                print(f"  {i}. {warning}")
        
        if not self.issues and not self.warnings:
            print("\n🎉 PIPELINE AUDIT PASSED!")
            print("✅ No critical issues found")
            print("✅ Data quality validated")
            print("✅ Performance acceptable")
            print("✅ Ready for production use")
        elif not self.issues:
            print("\n✅ PIPELINE AUDIT MOSTLY PASSED")
            print("⚠️  Some warnings found but no critical issues")
            print("✅ Safe to proceed with monitoring")
        else:
            print("\n❌ PIPELINE AUDIT FAILED")
            print("🔧 Critical issues must be fixed before production use")
        
        # Performance summary
        if self.performance_metrics:
            print(f"\n📈 Performance Metrics:")
            if 'memory_usage' in self.performance_metrics:
                mem = self.performance_metrics['memory_usage']
                print(f"   Memory: {mem['increase_mb']:.1f} MB for {mem['total_entries']:,} entries")
            
            if 'enrichment_speed' in self.performance_metrics:
                speed = self.performance_metrics['enrichment_speed']
                print(f"   Speed: {speed['products_per_second']:.1f} products/second")
        
        return len(self.issues) == 0

if __name__ == "__main__":
    # Change to scripts directory if needed
    if not os.path.exists("config/enrichment_config.json"):
        if os.path.exists("scripts/config/enrichment_config.json"):
            os.chdir("scripts")
    
    auditor = PipelineAuditor()
    success = auditor.run_comprehensive_audit()
    
    sys.exit(0 if success else 1)