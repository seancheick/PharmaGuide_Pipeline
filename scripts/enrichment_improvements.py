#!/usr/bin/env python3
"""
Enrichment pipeline improvements
Enhanced error handling, fuzzy matching, and performance optimizations
"""

import json
import os
import re
from typing import Dict, List, Any, Optional, Tuple
from fuzzywuzzy import fuzz
import logging

class ImprovedIngredientMatcher:
    """Enhanced ingredient matching with fuzzy logic and better error handling"""
    
    def __init__(self, fuzzy_threshold: int = 80):
        self.fuzzy_threshold = fuzzy_threshold
        self.cache = {}  # Cache for repeated lookups
        
    def enhanced_ingredient_match(self, ingredient_name: str, target_name: str, 
                                aliases: List[str], use_fuzzy: bool = True) -> Tuple[bool, int]:
        """
        Enhanced ingredient matching with exact and fuzzy matching
        Returns (is_match, confidence_score)
        """
        if not ingredient_name or not target_name:
            return False, 0
            
        # Create cache key
        cache_key = f"{ingredient_name.lower()}:{target_name.lower()}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Clean and normalize text
        ingredient_clean = self._normalize_text(ingredient_name)
        target_clean = self._normalize_text(target_name)
        
        # 1. Exact match (highest confidence)
        if ingredient_clean == target_clean:
            result = (True, 100)
            self.cache[cache_key] = result
            return result
        
        # 2. Check aliases for exact matches
        for alias in aliases:
            alias_clean = self._normalize_text(alias)
            if ingredient_clean == alias_clean:
                result = (True, 95)
                self.cache[cache_key] = result
                return result
        
        # 3. Word-level exact matching
        ingredient_words = set(ingredient_clean.split())
        target_words = set(target_clean.split())
        if ingredient_words == target_words:
            result = (True, 90)
            self.cache[cache_key] = result
            return result
        
        # 4. Fuzzy matching (if enabled)
        if use_fuzzy:
            # Check main target
            fuzzy_score = fuzz.ratio(ingredient_clean, target_clean)
            if fuzzy_score >= self.fuzzy_threshold:
                result = (True, fuzzy_score)
                self.cache[cache_key] = result
                return result
            
            # Check aliases with fuzzy matching
            for alias in aliases:
                alias_clean = self._normalize_text(alias)
                fuzzy_score = fuzz.ratio(ingredient_clean, alias_clean)
                if fuzzy_score >= self.fuzzy_threshold:
                    result = (True, fuzzy_score - 5)  # Slightly lower confidence for alias match
                    self.cache[cache_key] = result
                    return result
        
        # No match found
        result = (False, 0)
        self.cache[cache_key] = result
        return result
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for better matching"""
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower().strip()
        
        # Remove special characters but keep spaces and hyphens
        text = re.sub(r'[^\w\s\-]', '', text)
        
        # Normalize common variations
        replacements = {
            'dl-': 'd-',
            'l-': '',
            'vitamin ': 'vitamin',
            'mineral ': 'mineral',
            ' extract': '',
            ' powder': '',
            ' supplement': ''
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text

class EnhancedDatabaseLoader:
    """Enhanced database loading with error recovery"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.databases = {}
        
    def load_databases_safely(self, db_paths: Dict[str, str]) -> Dict[str, Any]:
        """Load databases with comprehensive error handling"""
        
        loaded_count = 0
        failed_count = 0
        
        for db_name, db_path in db_paths.items():
            try:
                if not os.path.exists(db_path):
                    self.logger.warning(f"Database file not found: {db_name} at {db_path}")
                    self.databases[db_name] = self._get_empty_database_structure(db_name)
                    failed_count += 1
                    continue
                
                with open(db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Validate database structure
                if self._validate_database_structure(db_name, data):
                    self.databases[db_name] = data
                    entry_count = self._count_database_entries(data)
                    self.logger.info(f"✅ Loaded {db_name}: {entry_count} entries")
                    loaded_count += 1
                else:
                    self.logger.error(f"Invalid structure in {db_name}, using empty structure")
                    self.databases[db_name] = self._get_empty_database_structure(db_name)
                    failed_count += 1
                    
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON decode error in {db_name}: {e}")
                self.databases[db_name] = self._get_empty_database_structure(db_name)
                failed_count += 1
                
            except Exception as e:
                self.logger.error(f"Unexpected error loading {db_name}: {e}")
                self.databases[db_name] = self._get_empty_database_structure(db_name)
                failed_count += 1
        
        self.logger.info(f"Database loading complete: {loaded_count} loaded, {failed_count} failed")
        
        if failed_count > 0:
            self.logger.warning(f"⚠️  {failed_count} databases failed to load - enrichment quality may be reduced")
        
        return self.databases
    
    def _validate_database_structure(self, db_name: str, data: Any) -> bool:
        """Validate database structure based on expected format"""
        
        if db_name == 'ingredient_quality_map':
            if not isinstance(data, dict):
                return False
            # Check if it has the expected nested structure
            for key, value in data.items():
                if isinstance(value, dict) and 'forms' in value:
                    return True
            return False
            
        elif db_name in ['absorption_enhancers', 'allergens', 'backed_clinical_studies']:
            return isinstance(data, list) or (isinstance(data, dict) and len(data) > 0)
            
        else:
            # Basic validation - should be dict or list
            return isinstance(data, (dict, list))
    
    def _count_database_entries(self, data: Any) -> int:
        """Count entries in database"""
        if isinstance(data, list):
            return len(data)
        elif isinstance(data, dict):
            # For nested structures, count top-level keys
            return len(data)
        else:
            return 1
    
    def _get_empty_database_structure(self, db_name: str) -> Any:
        """Return appropriate empty structure for failed database"""
        
        list_databases = [
            'absorption_enhancers', 'allergens', 'backed_clinical_studies',
            'banned_recalled_ingredients', 'botanical_ingredients',
            'harmful_additives', 'non_harmful_additives', 'passive_inactive_ingredients'
        ]
        
        if db_name in list_databases:
            return []
        else:
            return {}

class EnrichmentErrorHandler:
    """Centralized error handling for enrichment pipeline"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.error_counts = {}
        
    def handle_enrichment_error(self, product_id: str, error: Exception, 
                              context: str = "") -> Tuple[Optional[Dict], List[str]]:
        """Handle enrichment errors gracefully"""
        
        error_type = type(error).__name__
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        
        error_msg = f"Error in {context}: {str(error)}"
        self.logger.error(f"Product {product_id}: {error_msg}")
        
        # Return minimal enriched structure for failed products
        minimal_enriched = {
            "id": product_id,
            "enrichment_version": "2.0.0",
            "enrichment_status": "failed",
            "error_details": {
                "error_type": error_type,
                "error_message": str(error),
                "context": context
            },
            "enriched_date": None,
            "form_quality_mapping": [],
            "ingredient_quality_analysis": {},
            "quality_flags": {"enrichment_failed": True}
        }
        
        issues = [f"Enrichment failed: {error_msg}"]
        
        return minimal_enriched, issues
    
    def get_error_summary(self) -> Dict[str, int]:
        """Get summary of all errors encountered"""
        return self.error_counts.copy()

def create_enhanced_enricher_patch():
    """
    Generate patch code to improve the existing enricher
    This can be applied to the main enrichment script
    """
    
    patch_code = '''
# ENHANCED ERROR HANDLING PATCH
# Add this to your SupplementEnricherV2 class

def _load_all_databases_enhanced(self):
    """Enhanced database loading with better error handling"""
    
    db_loader = EnhancedDatabaseLoader(self.logger)
    self.databases = db_loader.load_databases_safely(self.config['database_paths'])
    
    # Initialize enhanced matcher
    fuzzy_enabled = self.config.get('processing_config', {}).get('enable_fuzzy_matching', True)
    fuzzy_threshold = self.config.get('processing_config', {}).get('fuzzy_threshold', 80)
    
    self.ingredient_matcher = ImprovedIngredientMatcher(fuzzy_threshold)
    self.error_handler = EnrichmentErrorHandler(self.logger)
    
    self.logger.info(f"Enhanced enrichment system initialized")

def _enhanced_ingredient_match(self, ingredient_name: str, target_name: str, aliases: List[str]) -> bool:
    """Use enhanced matching with fuzzy logic"""
    
    if not hasattr(self, 'ingredient_matcher'):
        # Fallback to original method if not initialized
        return self._exact_ingredient_match(ingredient_name, target_name, aliases)
    
    fuzzy_enabled = self.config.get('processing_config', {}).get('enable_fuzzy_matching', True)
    is_match, confidence = self.ingredient_matcher.enhanced_ingredient_match(
        ingredient_name, target_name, aliases, fuzzy_enabled
    )
    
    # Log high-confidence fuzzy matches for validation
    if is_match and confidence < 100 and confidence >= 85:
        self.logger.debug(f"Fuzzy match ({confidence}%): '{ingredient_name}' -> '{target_name}'")
    
    return is_match

def enrich_product_enhanced(self, product_data: Dict) -> Tuple[Dict, List[str]]:
    """Enhanced product enrichment with better error handling"""
    
    product_id = product_data.get("id", "unknown")
    
    try:
        return self.enrich_product_original(product_data)
        
    except KeyError as e:
        return self.error_handler.handle_enrichment_error(
            product_id, e, f"Missing required field: {e}"
        )
        
    except ValueError as e:
        return self.error_handler.handle_enrichment_error(
            product_id, e, "Data validation error"
        )
        
    except Exception as e:
        return self.error_handler.handle_enrichment_error(
            product_id, e, "Unexpected error during enrichment"
        )
'''
    
    return patch_code

if __name__ == "__main__":
    print("🔧 Enrichment Improvements Module")
    print("="*50)
    print("This module provides enhanced error handling and matching capabilities.")
    print("To use these improvements:")
    print("1. Import the classes into your main enrichment script")
    print("2. Replace the database loading method")
    print("3. Use the enhanced ingredient matching")
    print("4. Add comprehensive error handling")
    print("\nRun the validation script first to identify current issues.")