#!/usr/bin/env python3
"""
Fix specific database structure issues identified in validation
"""

import json
import os
from typing import Dict, Any

def fix_allergens_database():
    """Fix allergens database structure - extract list from nested structure"""
    
    allergens_file = "data/allergens.json"
    
    if not os.path.exists(allergens_file):
        print(f"❌ Allergens file not found: {allergens_file}")
        return False
    
    try:
        with open(allergens_file, 'r') as f:
            data = json.load(f)
        
        # The enrichment script expects a list under 'allergens' key
        if isinstance(data, dict) and 'common_allergens' in data:
            # Extract the allergens list and restructure
            allergens_list = data['common_allergens']
            
            # Create the expected structure
            fixed_structure = {
                "allergens": allergens_list
            }
            
            # Backup original
            backup_file = allergens_file + ".backup"
            with open(backup_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Write fixed structure
            with open(allergens_file, 'w') as f:
                json.dump(fixed_structure, f, indent=2)
            
            print(f"✅ Fixed allergens database structure")
            print(f"   - Backup saved to: {backup_file}")
            print(f"   - Extracted {len(allergens_list)} allergens")
            return True
        else:
            print("❌ Unexpected allergens database structure")
            return False
            
    except Exception as e:
        print(f"❌ Error fixing allergens database: {e}")
        return False

def fix_synergy_cluster_ids():
    """Add missing IDs to synergy clusters"""
    
    synergy_file = "data/synergy_cluster.json"
    
    if not os.path.exists(synergy_file):
        print(f"❌ Synergy file not found: {synergy_file}")
        return False
    
    try:
        with open(synergy_file, 'r') as f:
            data = json.load(f)
        
        if isinstance(data, dict) and 'synergy_clusters' in data:
            clusters = data['synergy_clusters']
            
            # Add IDs to clusters that don't have them
            for i, cluster in enumerate(clusters):
                if not cluster.get('id'):
                    # Generate ID from name
                    name = cluster.get('name', f'cluster_{i+1}')
                    cluster_id = name.lower().replace(' ', '_').replace('-', '_')
                    cluster['id'] = f"SYNERGY_{cluster_id.upper()}"
            
            # Backup original
            backup_file = synergy_file + ".backup"
            with open(backup_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Write fixed structure
            with open(synergy_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f"✅ Fixed synergy cluster IDs")
            print(f"   - Backup saved to: {backup_file}")
            print(f"   - Added IDs to {len(clusters)} clusters")
            return True
        else:
            print("❌ Unexpected synergy database structure")
            return False
            
    except Exception as e:
        print(f"❌ Error fixing synergy database: {e}")
        return False

def fix_config_paths():
    """Fix hardcoded paths in configuration"""
    
    config_file = "config/enrichment_config.json"
    
    if not os.path.exists(config_file):
        print(f"❌ Config file not found: {config_file}")
        return False
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        # Fix hardcoded paths
        paths = config.get('paths', {})
        
        # Replace hardcoded input directory
        input_dir = paths.get('input_directory', '')
        if '/Users/' in input_dir:
            # Extract the relative part
            if 'output_' in input_dir:
                relative_part = input_dir.split('scripts/')[-1]
                paths['input_directory'] = relative_part
                print(f"✅ Fixed input directory path: {relative_part}")
        
        # Backup original
        backup_file = config_file + ".backup"
        with open(backup_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        # Write fixed config
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"✅ Fixed configuration paths")
        print(f"   - Backup saved to: {backup_file}")
        return True
        
    except Exception as e:
        print(f"❌ Error fixing config: {e}")
        return False

def apply_enrichment_script_patches():
    """Apply patches to the enrichment script for better error handling"""
    
    script_file = "enrich_supplements_v2.py"
    
    if not os.path.exists(script_file):
        print(f"❌ Enrichment script not found: {script_file}")
        return False
    
    try:
        with open(script_file, 'r') as f:
            content = f.read()
        
        # Check if patches are already applied
        if '_validate_synergy_data' in content:
            print("✅ Patches already applied to enrichment script")
            return True
        
        # Find the _load_all_databases method and add validation
        validation_methods = '''
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

'''
        
        # Insert validation methods before the _load_all_databases method
        load_db_pos = content.find('def _load_all_databases(self):')
        if load_db_pos != -1:
            content = content[:load_db_pos] + validation_methods + content[load_db_pos:]
            
            # Backup original
            backup_file = script_file + ".backup"
            with open(backup_file, 'w') as f:
                with open(script_file, 'r') as orig:
                    f.write(orig.read())
            
            # Write patched version
            with open(script_file, 'w') as f:
                f.write(content)
            
            print(f"✅ Applied patches to enrichment script")
            print(f"   - Backup saved to: {backup_file}")
            print(f"   - Added database validation methods")
            return True
        else:
            print("❌ Could not find insertion point in enrichment script")
            return False
        
    except Exception as e:
        print(f"❌ Error patching enrichment script: {e}")
        return False

def run_all_fixes():
    """Run all fixes in sequence"""
    
    print("🔧 Applying Database and Configuration Fixes")
    print("=" * 50)
    
    fixes_applied = 0
    total_fixes = 4
    
    # 1. Fix allergens database
    print("\n1️⃣ Fixing allergens database structure...")
    if fix_allergens_database():
        fixes_applied += 1
    
    # 2. Fix synergy cluster IDs
    print("\n2️⃣ Adding missing synergy cluster IDs...")
    if fix_synergy_cluster_ids():
        fixes_applied += 1
    
    # 3. Fix config paths
    print("\n3️⃣ Fixing configuration paths...")
    if fix_config_paths():
        fixes_applied += 1
    
    # 4. Apply script patches
    print("\n4️⃣ Applying enrichment script patches...")
    if apply_enrichment_script_patches():
        fixes_applied += 1
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 FIX SUMMARY")
    print("=" * 50)
    
    if fixes_applied == total_fixes:
        print("🎉 All fixes applied successfully!")
        print("✅ Database structures corrected")
        print("✅ Configuration paths fixed")
        print("✅ Error handling improved")
        print("\n🚀 Ready to run enrichment pipeline!")
        print("\n💡 Next steps:")
        print("  1. Test with a small batch first")
        print("  2. Monitor logs for any remaining issues")
        print("  3. Validate output quality")
    else:
        print(f"⚠️  {fixes_applied}/{total_fixes} fixes applied successfully")
        print("Some issues may need manual attention")
    
    return fixes_applied == total_fixes

if __name__ == "__main__":
    success = run_all_fixes()
    
    if success:
        print("\n🔍 Running validation again to confirm fixes...")
        # Re-run validation
        from enrichment_targeted_fixes import run_comprehensive_validation
        run_comprehensive_validation()