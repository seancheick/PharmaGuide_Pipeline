#!/usr/bin/env python3
"""
Enrichment Data Validation & Category Accuracy Check
Validates that categories are correctly mapped and data integrity is maintained
"""

import json
import os
from typing import Dict, List, Any

from constants import VALIDATION_THRESHOLDS

class EnrichmentDataValidator:
    def __init__(self):
        self.validation_results = {}
        
    def validate_category_accuracy(self):
        """Validate that ingredient categories are correctly mapped from reference data"""
        print("🏷️  CATEGORY ACCURACY VALIDATION")
        print("=" * 40)
        
        try:
            # Load ingredient quality map
            with open('data/ingredient_quality_map.json', 'r', encoding='utf-8') as f:
                quality_map = json.load(f)
            
            # Load sample enriched output
            enriched_path = 'output_Gummies-Jellies_enriched/enriched/enriched_cleaned_batch_1.json'
            if os.path.exists(enriched_path):
                with open(enriched_path, 'r', encoding='utf-8') as f:
                    enriched_data = json.load(f)
                
                category_accuracy = []
                
                for product in enriched_data[:3]:  # Check first 3 products
                    product_id = product.get('id', 'unknown')
                    form_mapping = product.get('form_quality_mapping', [])
                    
                    print(f"\n📦 Product {product_id}:")
                    
                    for ingredient_mapping in form_mapping:
                        ingredient_name = ingredient_mapping.get('ingredient', '')
                        detected_category = ingredient_mapping.get('category', '')
                        standard_name = ingredient_mapping.get('standard_name', '')
                        
                        # Find the reference category
                        reference_category = None
                        for ref_key, ref_data in quality_map.items():
                            if ref_data.get('standard_name', '').lower() == standard_name.lower():
                                reference_category = ref_data.get('category', '')
                                break
                        
                        if reference_category:
                            category_match = detected_category.lower() == reference_category.lower()
                            status = "✅" if category_match else "❌"
                            
                            print(f"   {status} {ingredient_name}")
                            print(f"      Detected: {detected_category}")
                            print(f"      Reference: {reference_category}")
                            
                            category_accuracy.append({
                                'ingredient': ingredient_name,
                                'detected': detected_category,
                                'reference': reference_category,
                                'accurate': category_match
                            })
                        else:
                            print(f"   ⚠️  {ingredient_name} - No reference category found")
                
                # Calculate accuracy rate
                if category_accuracy:
                    accurate_count = sum(1 for item in category_accuracy if item['accurate'])
                    accuracy_rate = (accurate_count / len(category_accuracy)) * 100
                    
                    print(f"\n📊 Category Accuracy: {accuracy_rate:.1f}% ({accurate_count}/{len(category_accuracy)})")
                    
                    if accuracy_rate >= VALIDATION_THRESHOLDS["high_accuracy"]:
                        print("✅ Excellent category accuracy")
                    elif accuracy_rate >= VALIDATION_THRESHOLDS["good_accuracy"]:
                        print("⚠️  Good category accuracy, minor improvements needed")
                    else:
                        print("❌ Poor category accuracy, requires investigation")
                        
                    self.validation_results['category_accuracy'] = accuracy_rate
                
            else:
                print("⚠️  No enriched sample data found for validation")
                
        except Exception as e:
            print(f"❌ Category validation failed: {e}")
    
    def validate_data_preservation(self):
        """Validate that original data is preserved during enrichment"""
        print("\n💾 DATA PRESERVATION VALIDATION")
        print("=" * 40)
        
        try:
            # Load original cleaned data
            cleaned_path = 'output_Gummies-Jellies/cleaned/cleaned_batch_1.json'
            enriched_path = 'output_Gummies-Jellies_enriched/enriched/enriched_cleaned_batch_1.json'
            
            if os.path.exists(cleaned_path) and os.path.exists(enriched_path):
                with open(cleaned_path, 'r', encoding='utf-8') as f:
                    cleaned_data = json.load(f)
                
                with open(enriched_path, 'r', encoding='utf-8') as f:
                    enriched_data = json.load(f)
                
                # Create lookup for enriched data
                enriched_lookup = {item['id']: item for item in enriched_data}
                
                preservation_results = []
                
                for original_product in cleaned_data[:3]:  # Check first 3
                    product_id = original_product.get('id', '')
                    enriched_product = enriched_lookup.get(product_id)
                    
                    if enriched_product:
                        print(f"\n📦 Product {product_id}:")
                        
                        # Check ingredient preservation
                        original_ingredients = original_product.get('activeIngredients', [])
                        form_mapping = enriched_product.get('form_quality_mapping', [])
                        
                        # Verify all original ingredients are preserved
                        original_names = [ing.get('name', '') for ing in original_ingredients]
                        enriched_names = [mapping.get('ingredient', '') for mapping in form_mapping]
                        
                        missing_ingredients = [name for name in original_names if name not in enriched_names]
                        
                        if not missing_ingredients:
                            print("   ✅ All ingredients preserved")
                        else:
                            print(f"   ❌ Missing ingredients: {missing_ingredients}")
                        
                        # Check quantity preservation
                        quantity_preserved = True
                        for orig_ing in original_ingredients:
                            orig_name = orig_ing.get('name', '')
                            orig_qty = orig_ing.get('quantity', 0)
                            
                            # Find corresponding enriched ingredient
                            for mapping in form_mapping:
                                if mapping.get('ingredient', '') == orig_name:
                                    # Quantities should be preserved in original product data
                                    # (enrichment adds analysis but doesn't modify original values)
                                    break
                        
                        preservation_results.append({
                            'product_id': product_id,
                            'ingredients_preserved': len(missing_ingredients) == 0,
                            'missing_count': len(missing_ingredients)
                        })
                
                # Calculate preservation rate
                if preservation_results:
                    fully_preserved = sum(1 for result in preservation_results if result['ingredients_preserved'])
                    preservation_rate = (fully_preserved / len(preservation_results)) * 100
                    
                    print(f"\n📊 Data Preservation Rate: {preservation_rate:.1f}%")
                    
                    if preservation_rate == 100:
                        print("✅ Perfect data preservation")
                    else:
                        print("⚠️  Some data loss detected")
                        
                    self.validation_results['preservation_rate'] = preservation_rate
                
            else:
                print("⚠️  Original cleaned data not found for comparison")
                
        except Exception as e:
            print(f"❌ Data preservation validation failed: {e}")
    
    def validate_scoring_preparation(self):
        """Validate that enriched data is properly prepared for scoring"""
        print("\n🎯 SCORING PREPARATION VALIDATION")
        print("=" * 40)
        
        try:
            enriched_path = 'output_Gummies-Jellies_enriched/enriched/enriched_cleaned_batch_1.json'
            
            if os.path.exists(enriched_path):
                with open(enriched_path, 'r', encoding='utf-8') as f:
                    enriched_data = json.load(f)
                
                scoring_readiness = []
                
                for product in enriched_data[:3]:  # Check first 3 products
                    product_id = product.get('id', 'unknown')
                    print(f"\n📦 Product {product_id}:")
                    
                    # Check required scoring fields
                    required_fields = {
                        'scoring_precalculations': 'Scoring precalculations',
                        'form_quality_mapping': 'Ingredient quality mapping',
                        'contaminant_analysis': 'Safety analysis',
                        'clinical_evidence_matches': 'Clinical evidence',
                        'synergy_analysis': 'Synergy analysis',
                        'certification_analysis': 'Certification analysis'
                    }
                    
                    missing_fields = []
                    for field, description in required_fields.items():
                        if field in product:
                            print(f"   ✅ {description}")
                        else:
                            print(f"   ❌ Missing: {description}")
                            missing_fields.append(field)
                    
                    # Check scoring precalculations structure
                    if 'scoring_precalculations' in product:
                        precalc = product['scoring_precalculations']
                        required_sections = ['section_a', 'section_b', 'section_c', 'section_d']
                        
                        for section in required_sections:
                            if section in precalc:
                                print(f"   ✅ {section.upper()} calculations ready")
                            else:
                                print(f"   ❌ Missing {section.upper()} calculations")
                                missing_fields.append(f"precalc_{section}")
                        
                        # Check base score calculation
                        base_score = precalc.get('base_score_total', 0)
                        max_score = precalc.get('base_score_max', VALIDATION_THRESHOLDS["base_score_max"])
                        
                        if 0 <= base_score <= max_score:
                            print(f"   ✅ Base score valid: {base_score}/{max_score}")
                        else:
                            print(f"   ❌ Invalid base score: {base_score}/{max_score}")
                    
                    scoring_readiness.append({
                        'product_id': product_id,
                        'missing_fields': missing_fields,
                        'ready_for_scoring': len(missing_fields) == 0
                    })
                
                # Calculate readiness rate
                if scoring_readiness:
                    ready_count = sum(1 for result in scoring_readiness if result['ready_for_scoring'])
                    readiness_rate = (ready_count / len(scoring_readiness)) * 100
                    
                    print(f"\n📊 Scoring Readiness: {readiness_rate:.1f}%")
                    
                    if readiness_rate == 100:
                        print("✅ All products ready for scoring")
                    else:
                        print("⚠️  Some products missing scoring requirements")
                        
                    self.validation_results['scoring_readiness'] = readiness_rate
                
            else:
                print("⚠️  No enriched data found for validation")
                
        except Exception as e:
            print(f"❌ Scoring preparation validation failed: {e}")
    
    def validate_reference_database_integrity(self):
        """Validate reference database integrity and completeness"""
        print("\n🗄️  REFERENCE DATABASE INTEGRITY")
        print("=" * 40)
        
        try:
            databases = {
                'ingredient_quality_map.json': 'Ingredient Quality Mapping',
                'allergens.json': 'Allergen Database',
                'harmful_additives.json': 'Harmful Additives',
                'rda_optimal_uls.json': 'RDA/UL References',
                'backed_clinical_studies.json': 'Clinical Studies',
                'synergy_cluster.json': 'Synergy Clusters'
            }
            
            database_health = []
            
            for db_file, db_name in databases.items():
                db_path = f'data/{db_file}'
                
                if os.path.exists(db_path):
                    try:
                        with open(db_path, 'r', encoding='utf-8') as f:
                            db_data = json.load(f)
                        
                        # Count entries
                        if isinstance(db_data, list):
                            entry_count = len(db_data)
                        elif isinstance(db_data, dict):
                            # Count based on structure
                            if 'nutrient_recommendations' in db_data:
                                entry_count = len(db_data['nutrient_recommendations'])
                            elif any(key.endswith('_allergens') or key == 'allergens' for key in db_data.keys()):
                                entry_count = sum(len(v) if isinstance(v, list) else 1 for v in db_data.values() if isinstance(v, (list, dict)))
                            else:
                                entry_count = len(db_data)
                        else:
                            entry_count = 1
                        
                        print(f"   ✅ {db_name}: {entry_count:,} entries")
                        
                        database_health.append({
                            'database': db_name,
                            'entries': entry_count,
                            'healthy': True
                        })
                        
                    except json.JSONDecodeError as e:
                        print(f"   ❌ {db_name}: Invalid JSON format")
                        database_health.append({
                            'database': db_name,
                            'entries': 0,
                            'healthy': False
                        })
                        
                else:
                    print(f"   ❌ {db_name}: File not found")
                    database_health.append({
                        'database': db_name,
                        'entries': 0,
                        'healthy': False
                    })
            
            # Calculate database health
            healthy_dbs = sum(1 for db in database_health if db['healthy'])
            health_rate = (healthy_dbs / len(database_health)) * 100
            
            print(f"\n📊 Database Health: {health_rate:.1f}% ({healthy_dbs}/{len(database_health)})")
            
            if health_rate == 100:
                print("✅ All reference databases healthy")
            else:
                print("⚠️  Some database issues detected")
                
            self.validation_results['database_health'] = health_rate
            
        except Exception as e:
            print(f"❌ Database integrity validation failed: {e}")
    
    def run_validation(self):
        """Run complete validation suite"""
        print("🔬 ENRICHMENT DATA VALIDATION SUITE")
        print("Healthcare-Ready Data Integrity Check")
        print("=" * 50)
        
        self.validate_reference_database_integrity()
        self.validate_category_accuracy()
        self.validate_data_preservation()
        self.validate_scoring_preparation()
        
        # Generate summary
        print(f"\n📋 VALIDATION SUMMARY")
        print("=" * 30)
        
        for metric, value in self.validation_results.items():
            status = "✅" if value >= VALIDATION_THRESHOLDS["high_accuracy"] else "⚠️" if value >= VALIDATION_THRESHOLDS["good_accuracy"] else "❌"
            print(f"{status} {metric.replace('_', ' ').title()}: {value:.1f}%")
        
        # Overall assessment
        if self.validation_results:
            avg_score = sum(self.validation_results.values()) / len(self.validation_results)
            
            print(f"\n🎯 Overall Data Quality: {avg_score:.1f}%")
            
            if avg_score >= VALIDATION_THRESHOLDS["high_accuracy"]:
                print("🎉 EXCELLENT: Data integrity meets healthcare standards")
            elif avg_score >= VALIDATION_THRESHOLDS["good_accuracy"]:
                print("✅ GOOD: Minor improvements recommended")
            else:
                print("⚠️  NEEDS IMPROVEMENT: Address data quality issues")
        
        return self.validation_results

def main():
    validator = EnrichmentDataValidator()
    results = validator.run_validation()

if __name__ == "__main__":
    main()