#!/usr/bin/env python3
"""
Targeted fixes for the enrichment pipeline
Addresses specific issues without changing the core architecture
"""

import json
import os
import logging
from typing import Dict, List, Any, Optional

def fix_synergy_analysis_data_structure():
    """
    Fix the synergy cluster data structure issue
    The enriched output shows empty cluster names, suggesting a data mismatch
    """
    
    synergy_file = "data/synergy_cluster.json"
    
    if not os.path.exists(synergy_file):
        print(f"❌ Synergy cluster file not found: {synergy_file}")
        return False
    
    try:
        with open(synergy_file, 'r') as f:
            synergy_data = json.load(f)
        
        print("🔍 Analyzing synergy cluster data structure...")
        
        # Check the structure
        if isinstance(synergy_data, dict):
            if 'synergy_clusters' in synergy_data:
                clusters = synergy_data['synergy_clusters']
                print(f"✅ Found {len(clusters)} synergy clusters")
                
                # Check first few clusters for structure
                for i, cluster in enumerate(clusters[:3]):
                    print(f"  Cluster {i+1}:")
                    print(f"    - ID: {cluster.get('id', 'MISSING')}")
                    print(f"    - Name: {cluster.get('name', 'MISSING')}")
                    print(f"    - Ingredients: {len(cluster.get('ingredients', []))}")
                    
                    if not cluster.get('name'):
                        print(f"    ⚠️  Missing name for cluster {cluster.get('id', 'unknown')}")
                    
                    if not cluster.get('id'):
                        print(f"    ⚠️  Missing ID for cluster")
                
                return True
            else:
                print("❌ Missing 'synergy_clusters' key in data")
                return False
        else:
            print("❌ Synergy data is not a dictionary")
            return False
            
    except Exception as e:
        print(f"❌ Error analyzing synergy data: {e}")
        return False

def validate_database_integrity():
    """
    Validate all database files for common issues
    """
    
    config_file = "config/enrichment_config.json"
    
    if not os.path.exists(config_file):
        print(f"❌ Config file not found: {config_file}")
        return False
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        db_paths = config.get('database_paths', {})
        issues = []
        
        print("🔍 Validating database integrity...")
        
        for db_name, db_path in db_paths.items():
            print(f"\n📄 Checking {db_name}...")
            
            if not os.path.exists(db_path):
                issues.append(f"Missing file: {db_name} at {db_path}")
                print(f"  ❌ File not found")
                continue
            
            try:
                with open(db_path, 'r') as f:
                    data = json.load(f)
                
                # Basic structure validation
                if db_name == 'ingredient_quality_map':
                    if not isinstance(data, dict):
                        issues.append(f"Invalid structure: {db_name} should be dict")
                    else:
                        # Check for proper nested structure
                        valid_entries = 0
                        for key, value in data.items():
                            if isinstance(value, dict) and 'forms' in value:
                                valid_entries += 1
                        print(f"  ✅ {valid_entries} valid entries")
                
                elif db_name == 'synergy_cluster':
                    if isinstance(data, dict) and 'synergy_clusters' in data:
                        clusters = data['synergy_clusters']
                        missing_names = sum(1 for c in clusters if not c.get('name'))
                        missing_ids = sum(1 for c in clusters if not c.get('id'))
                        
                        if missing_names > 0:
                            issues.append(f"Synergy clusters missing names: {missing_names}")
                        if missing_ids > 0:
                            issues.append(f"Synergy clusters missing IDs: {missing_ids}")
                        
                        print(f"  ✅ {len(clusters)} clusters, {missing_names} missing names, {missing_ids} missing IDs")
                    else:
                        issues.append(f"Invalid synergy cluster structure")
                
                elif db_name in ['absorption_enhancers', 'allergens', 'backed_clinical_studies']:
                    if isinstance(data, list):
                        print(f"  ✅ {len(data)} entries")
                    else:
                        issues.append(f"Invalid structure: {db_name} should be list")
                
                else:
                    # Generic validation
                    if isinstance(data, (dict, list)):
                        count = len(data)
                        print(f"  ✅ {count} entries")
                    else:
                        issues.append(f"Invalid structure: {db_name}")
                        
            except json.JSONDecodeError as e:
                issues.append(f"JSON decode error in {db_name}: {e}")
                print(f"  ❌ JSON decode error")
            except Exception as e:
                issues.append(f"Error reading {db_name}: {e}")
                print(f"  ❌ Read error: {e}")
        
        print(f"\n📊 Validation Summary:")
        if issues:
            print(f"❌ {len(issues)} issues found:")
            for issue in issues:
                print(f"  - {issue}")
            return False
        else:
            print("✅ All databases valid")
            return True
            
    except Exception as e:
        print(f"❌ Error validating databases: {e}")
        return False

def create_enhanced_error_handling_patch():
    """
    Generate code patches for better error handling in the enrichment script
    """
    
    patches = {
        "database_loading": '''
# PATCH 1: Enhanced database loading with validation
def _load_all_databases_with_validation(self):
    """Load databases with comprehensive validation"""
    db_paths = self.config['database_paths']
    
    for db_name, db_path in db_paths.items():
        try:
            if os.path.exists(db_path):
                with open(db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Validate critical databases
                if db_name == 'ingredient_quality_map' and not self._validate_quality_map(data):
                    self.logger.warning(f"Invalid structure in {db_name}, using fallback")
                    data = {}
                elif db_name == 'synergy_cluster' and not self._validate_synergy_data(data):
                    self.logger.warning(f"Invalid structure in {db_name}, using fallback")
                    data = {"synergy_clusters": []}
                
                self.databases[db_name] = data
                entry_count = len(data) if isinstance(data, (list, dict)) else 1
                self.logger.info(f"✅ Loaded {db_name}: {entry_count} entries")
            else:
                self.logger.error(f"❌ Database file not found: {db_name} at {db_path}")
                self.databases[db_name] = [] if db_name.endswith('s') else {}
        except Exception as e:
            self.logger.error(f"❌ Failed to load {db_name}: {e}")
            self.databases[db_name] = [] if db_name.endswith('s') else {}
    
    # Validate critical databases are loaded
    critical_dbs = ['ingredient_quality_map', 'synergy_cluster']
    for db_name in critical_dbs:
        if not self.databases.get(db_name):
            self.logger.warning(f"⚠️  Critical database {db_name} is empty - enrichment quality will be reduced")

def _validate_quality_map(self, data):
    """Validate ingredient quality map structure"""
    if not isinstance(data, dict):
        return False
    
    # Check if at least some entries have the expected structure
    valid_entries = 0
    for key, value in data.items():
        if isinstance(value, dict) and 'forms' in value:
            valid_entries += 1
    
    return valid_entries > 0

def _validate_synergy_data(self, data):
    """Validate synergy cluster data structure"""
    if not isinstance(data, dict) or 'synergy_clusters' not in data:
        return False
    
    clusters = data['synergy_clusters']
    if not isinstance(clusters, list):
        return False
    
    # Check if clusters have required fields
    valid_clusters = 0
    for cluster in clusters:
        if isinstance(cluster, dict) and cluster.get('ingredients'):
            valid_clusters += 1
    
    return valid_clusters > 0
''',
        
        "synergy_analysis_fix": '''
# PATCH 2: Fix synergy analysis to handle missing names/IDs
def _analyze_synergies_fixed(self, ingredients: List[Dict]) -> Dict:
    """Fixed synergy analysis with better error handling"""
    synergy_db = self.databases.get('synergy_cluster', {})
    synergy_clusters = synergy_db.get('synergy_clusters', [])
    detected_clusters = []
    
    for cluster in synergy_clusters:
        # Handle missing cluster names/IDs gracefully
        cluster_name = cluster.get('name', f"Cluster_{cluster.get('id', 'unknown')}")
        cluster_id = cluster.get('id', f"cluster_{len(detected_clusters) + 1}")
        cluster_ingredients = cluster.get('ingredients', [])
        
        if not cluster_ingredients:
            continue  # Skip empty clusters
        
        matched_ingredients = []
        
        # Check if at least 2 ingredients from the cluster are present
        for cluster_ing_name in cluster_ingredients:
            for product_ing in ingredients:
                if self._exact_ingredient_match(
                    product_ing.get('standardName', ''), 
                    cluster_ing_name, 
                    []
                ):
                    # Get product dose and check against minimum effective dose
                    product_dose = product_ing.get('quantity', 0)
                    
                    # Check minimum effective dose from cluster data
                    min_effective_doses = cluster.get('min_effective_doses', {})
                    cluster_ing_lower = cluster_ing_name.lower().strip()
                    min_dose = min_effective_doses.get(cluster_ing_lower, 0)
                    
                    # Determine if dose meets minimum requirement
                    meets_min_dose = product_dose >= min_dose if min_dose > 0 else True
                    
                    matched_ingredients.append({
                        "ingredient": product_ing.get('name', ''),
                        "amount": product_dose,
                        "unit": product_ing.get('unit', ''),
                        "min_required": min_dose,
                        "meets_min_dose": meets_min_dose
                    })
        
        # Need at least 2 ingredients for synergy
        if len(matched_ingredients) >= 2:
            # All ingredients must meet minimum dose for full synergy points
            all_meet_dose = all(ing.get('meets_min_dose', False) for ing in matched_ingredients)
            # Use evidence tier for more accurate scoring
            evidence_tier = cluster.get('evidence_tier', 3)
            base_points = {1: 3, 2: 2, 3: 1}.get(evidence_tier, 1)
            points = base_points if all_meet_dose else base_points // 2
            
            detected_clusters.append({
                "cluster_name": cluster_name,  # Fixed: ensure name is always present
                "cluster_id": cluster_id,      # Fixed: ensure ID is always present
                "matched_ingredients": matched_ingredients,
                "synergy_points": points,
                "all_doses_adequate": all_meet_dose
            })
    
    total_points = sum(cluster.get('synergy_points', 0) for cluster in detected_clusters)
    
    return {
        "detected_clusters": detected_clusters,
        "total_synergy_points": total_points
    }
'''
    }
    
    return patches

def run_comprehensive_validation():
    """
    Run all validation checks and provide actionable recommendations
    """
    
    print("🚀 Comprehensive Enrichment Pipeline Validation")
    print("=" * 60)
    
    all_passed = True
    
    # 1. Database integrity check
    print("\n1️⃣ Database Integrity Check")
    db_valid = validate_database_integrity()
    if not db_valid:
        all_passed = False
    
    # 2. Synergy data structure check
    print("\n2️⃣ Synergy Data Structure Check")
    synergy_valid = fix_synergy_analysis_data_structure()
    if not synergy_valid:
        all_passed = False
    
    # 3. Configuration validation
    print("\n3️⃣ Configuration Validation")
    config_file = "config/enrichment_config.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Check for hardcoded paths
            input_dir = config.get('paths', {}).get('input_directory', '')
            if '/Users/' in input_dir:
                print("  ⚠️  Hardcoded user path detected in config")
                print(f"     Current: {input_dir}")
                print("     Recommendation: Use relative paths like 'output_cleaned/cleaned'")
                all_passed = False
            else:
                print("  ✅ Configuration paths look good")
                
        except Exception as e:
            print(f"  ❌ Error reading config: {e}")
            all_passed = False
    else:
        print(f"  ❌ Config file not found: {config_file}")
        all_passed = False
    
    # Final summary
    print("\n" + "=" * 60)
    print("📊 VALIDATION SUMMARY")
    print("=" * 60)
    
    if all_passed:
        print("🎉 All validations passed!")
        print("✅ Pipeline is ready for enrichment")
        print("\n💡 Recommendations:")
        print("  - Run a small test batch first")
        print("  - Monitor logs for any warnings")
        print("  - Check output quality on first few products")
    else:
        print("⚠️  Some issues found that should be addressed")
        print("\n🔧 Next Steps:")
        print("  1. Fix database structure issues")
        print("  2. Update configuration paths")
        print("  3. Apply the provided code patches")
        print("  4. Re-run validation")
    
    return all_passed

if __name__ == "__main__":
    # Change to scripts directory if needed
    if not os.path.exists("config/enrichment_config.json"):
        if os.path.exists("scripts/config/enrichment_config.json"):
            os.chdir("scripts")
            print("📁 Changed to scripts directory")
    
    success = run_comprehensive_validation()
    
    if not success:
        print("\n💡 Would you like to see the code patches to fix these issues?")
        patches = create_enhanced_error_handling_patch()
        print("\nCode patches available for:")
        for patch_name in patches.keys():
            print(f"  - {patch_name}")