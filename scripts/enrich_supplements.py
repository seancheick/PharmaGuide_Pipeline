#!/usr/bin/env python3
"""
DSLD Supplement Data Enrichment System
=====================================

Comprehensive enrichment pipeline that processes cleaned supplement data
and enriches it with information from 17+ reference databases for scoring.

Author: Claude Code
Version: 1.0.0
Created: 2025-09-11
"""

import json
import os
import sys
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/enrichment.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class EnrichmentResult:
    """Results from enrichment processing"""
    success: bool
    product_id: str
    enriched_data: Optional[Dict] = None
    errors: Optional[List[str]] = None
    warnings: Optional[List[str]] = None
    processing_time: float = 0.0

class SupplementEnricher:
    """Comprehensive supplement data enrichment system"""
    
    def __init__(self, config_path: str = "config/enrichment_config.json"):
        """Initialize enricher with configuration"""
        self.config = self._load_config(config_path)
        self.databases = {}
        self.text_patterns = {}
        self.stats = {
            'total_processed': 0,
            'successful_enrichments': 0,
            'failed_enrichments': 0,
            'total_databases_loaded': 0,
            'processing_start_time': None
        }
        
        # Deduplication registry for current product
        self.ingredient_registry = {}
        
        # Load all reference databases
        self._load_databases()
        self._compile_patterns()
        
        logger.info(f"Enrichment system initialized with {len(self.databases)} databases")
    
    def _load_config(self, config_path: str) -> Dict:
        """Load enrichment configuration"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"Configuration loaded from {config_path}")
            return config
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            raise
    
    def _load_databases(self):
        """Load all reference databases"""
        for db_name, db_path in self.config['database_paths'].items():
            try:
                full_path = Path(db_path)
                if not full_path.exists():
                    logger.warning(f"Database file not found: {full_path}")
                    continue
                    
                with open(full_path, 'r', encoding='utf-8') as f:
                    self.databases[db_name] = json.load(f)
                
                # Log database size
                if isinstance(self.databases[db_name], dict):
                    size = len(self.databases[db_name].get('common_allergens', 
                              self.databases[db_name].get('harmful_additives',
                              self.databases[db_name].get('therapeutic_dosing', []))))
                else:
                    size = len(self.databases[db_name])
                
                logger.info(f"Loaded {db_name}: {size} entries")
                self.stats['total_databases_loaded'] += 1
                
            except Exception as e:
                logger.error(f"Failed to load database {db_name} from {db_path}: {e}")
    
    def _compile_patterns(self):
        """Compile regex patterns for text analysis"""
        self.text_patterns = {
            'percentage': re.compile(r'(\d+(?:\.\d+)?)\s*%\s*([a-zA-Z\s\-]+)', re.IGNORECASE),
            'standardized': re.compile(r'standardized\s+to\s+(\d+(?:\.\d+)?)\s*%\s*([a-zA-Z\s\-]+)', re.IGNORECASE),
            'extract_ratio': re.compile(r'(\d+(?:\.\d+)?)\s*:\s*1\s+extract', re.IGNORECASE),
            'delivery_methods': re.compile(r'(liposomal|phytosome|nanoemulsion|sublingual|enteric[- ]coated|time[- ]release)', re.IGNORECASE),
            'proprietary_terms': re.compile(r'(proprietary|blend|matrix|complex|formula)', re.IGNORECASE)
        }
    
    def normalize_text(self, text: str) -> str:
        """Normalize text for matching"""
        if not text:
            return ""
        
        # Convert to lowercase, remove special characters, normalize spaces
        normalized = re.sub(r'[^\w\s\-]', ' ', text.lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized
    
    def fuzzy_match(self, text1: str, text2: str, threshold: float = 0.85) -> bool:
        """Simple fuzzy matching implementation"""
        if not text1 or not text2:
            return False
        
        # Normalize both texts
        norm1 = self.normalize_text(text1)
        norm2 = self.normalize_text(text2)
        
        # Exact match
        if norm1 == norm2:
            return True
        
        # Contains match
        if norm1 in norm2 or norm2 in norm1:
            return True
        
        # Simple similarity check (Jaccard similarity)
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        
        if not words1 or not words2:
            return False
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        similarity = intersection / union if union > 0 else 0
        return similarity >= threshold
    
    def check_ingredient_match(self, ingredient_name: str, standard_name: str, aliases: List[str]) -> bool:
        """Check if ingredient matches standard name or aliases"""
        if not ingredient_name:
            return False
        
        # Check standard name
        if self.fuzzy_match(ingredient_name, standard_name):
            return True
        
        # Check aliases
        for alias in aliases:
            if self.fuzzy_match(ingredient_name, alias):
                return True
        
        return False
    
    def enrich_absorption_enhancers(self, product_data: Dict) -> Dict:
        """Analyze absorption enhancers"""
        enhancers_data = self.databases.get('absorption_enhancers', [])
        if not enhancers_data:
            return {"detected": False, "enhancer_pairs": []}
        
        detected_pairs = []
        all_ingredients = []
        
        # Collect all ingredient names
        for ingredient in product_data.get('activeIngredients', []):
            all_ingredients.append(ingredient.get('name', ''))
            all_ingredients.append(ingredient.get('standardName', ''))
        
        for ingredient in product_data.get('inactiveIngredients', []):
            all_ingredients.append(ingredient.get('name', ''))
            all_ingredients.append(ingredient.get('standardName', ''))
        
        # Check for enhancers
        for enhancer_data in enhancers_data:
            enhancer_name = enhancer_data.get('name', '')
            enhancer_aliases = enhancer_data.get('aliases', [])
            
            # Check if enhancer is present
            enhancer_found = False
            enhancer_ingredient = None
            
            for ingredient_name in all_ingredients:
                if self.check_ingredient_match(ingredient_name, enhancer_name, enhancer_aliases):
                    enhancer_found = True
                    enhancer_ingredient = ingredient_name
                    break
            
            if enhancer_found:
                # Check what it enhances
                enhanced_ingredients = []
                enhances_list = enhancer_data.get('enhances', [])
                
                for ingredient_name in all_ingredients:
                    for enhanced_name in enhances_list:
                        if self.fuzzy_match(ingredient_name, enhanced_name):
                            enhanced_ingredients.append(ingredient_name)
                
                if enhanced_ingredients:
                    detected_pairs.append({
                        "enhancer_ingredient": enhancer_ingredient,
                        "enhancer_name": enhancer_name,
                        "enhancer_aliases": enhancer_aliases,
                        "enhances_ingredients": enhanced_ingredients,
                        "mechanism": enhancer_data.get('mechanism', ''),
                        "boost_factor": enhancer_data.get('boost_factor', ''),
                        "score_contribution": enhancer_data.get('score_contribution', 0)
                    })
        
        return {
            "detected": len(detected_pairs) > 0,
            "enhancer_pairs": detected_pairs,
            "total_enhancers_found": len(detected_pairs)
        }
    
    def enrich_allergen_analysis(self, product_data: Dict) -> Dict:
        """Analyze allergens from multiple sources"""
        allergens_data = self.databases.get('allergens', {})
        if not allergens_data:
            return {"detected": False, "detected_allergens": []}
        
        detected_allergens = []
        all_ingredients = []
        all_text = []
        
        # Collect ingredient names
        for ingredient in product_data.get('activeIngredients', []) + product_data.get('inactiveIngredients', []):
            all_ingredients.append(ingredient.get('name', ''))
            all_ingredients.append(ingredient.get('standardName', ''))
        
        # Collect text from statements and claims
        for statement in product_data.get('statements', []):
            all_text.append(statement.get('notes', ''))
        
        all_text.append(product_data.get('labelText', ''))
        
        # Check against allergen database
        for allergen in allergens_data.get('common_allergens', []):
            allergen_name = allergen.get('standard_name', '')
            allergen_aliases = allergen.get('aliases', [])
            
            # Check ingredients with exact matching
            matched_ingredient = None
            for ingredient_name in all_ingredients:
                if self._exact_ingredient_match(ingredient_name, allergen_name, allergen_aliases):
                    matched_ingredient = ingredient_name
                    break
            
            # Check text content with negation awareness and exact matching
            if not matched_ingredient:
                for text in all_text:
                    if self._exact_ingredient_match(text, allergen_name, allergen_aliases):
                        # Check if this is in a negation context
                        if self._check_negation_context(text, allergen_name, allergen_aliases):
                            continue  # Skip if negated (e.g., "contains NO soy")
                        
                        matched_ingredient = f"Found in label text: {allergen_name}"
                        break
            
            if matched_ingredient:
                severity = allergen.get('severity_level', 'low')
                penalty_map = {'low': -1, 'moderate': -1.5, 'high': -2}
                
                detected_allergens.append({
                    "ingredient_name": matched_ingredient,
                    "allergen_id": allergen.get('id', ''),
                    "standard_name": allergen_name,
                    "severity_level": severity,
                    "penalty_score": penalty_map.get(severity, -1),
                    "notes": allergen.get('notes', ''),
                    "category": allergen.get('category', ''),
                    "regulatory_status": allergen.get('regulatory_status', ''),
                    "supplement_context": allergen.get('supplement_context', '')
                })
        
        # Deduplicate allergens
        detected_allergens = self._deduplicate_results(detected_allergens, 'allergens')
        
        return {
            "detected": len(detected_allergens) > 0,
            "detected_allergens": detected_allergens,
            "total_allergens": len(detected_allergens),
            "severity_breakdown": self._count_by_severity(detected_allergens)
        }
    
    def _check_negation_context(self, text: str, allergen_name: str, aliases: List[str]) -> bool:
        """Check if allergen mention is in a negation context (NO X, free from X, etc.)"""
        if not text:
            return False
            
        text_lower = text.lower()
        
        # Create list of all possible allergen terms
        allergen_terms = [allergen_name.lower()] + [alias.lower() for alias in aliases]
        
        # Negation patterns to look for
        negation_patterns = [
            r'\bno\s+',
            r'\bfree\s+from\s+',
            r'\bfree\s+of\s+',
            r'\bwithout\s+',
            r'\bdoes\s+not\s+contain\s+',
            r'\bcontains\s+no\s+',
            r'\b(?:gluten|dairy|soy|wheat|milk|egg|nut)\s*[-\s]*free\b',
        ]
        
        import re
        
        # Check each allergen term
        for term in allergen_terms:
            if term in text_lower:
                # Find position of allergen term
                term_positions = []
                start = 0
                while True:
                    pos = text_lower.find(term, start)
                    if pos == -1:
                        break
                    term_positions.append(pos)
                    start = pos + 1
                
                # Check if any occurrence is preceded by negation
                for pos in term_positions:
                    # Look 50 characters before the allergen term
                    context_start = max(0, pos - 50)
                    context = text_lower[context_start:pos + len(term)]
                    
                    # Check for negation patterns
                    for pattern in negation_patterns:
                        if re.search(pattern + r'.*' + re.escape(term), context):
                            return True
                    
                    # Also check for compound terms like "gluten-free", "dairy-free"
                    free_pattern = rf'\b{re.escape(term)}\s*[-\s]*free\b'
                    if re.search(free_pattern, text_lower):
                        return True
        
        return False
    
    def _exact_ingredient_match(self, ingredient_name: str, target_name: str, aliases: List[str]) -> bool:
        """Perform exact matching for ingredients - no fuzzy matching for accuracy"""
        if not ingredient_name or not target_name:
            return False
            
        ingredient_lower = ingredient_name.lower().strip()
        target_lower = target_name.lower().strip()
        
        # 1. Exact match
        if ingredient_lower == target_lower:
            return True
        
        # 2. Check aliases for exact matches only
        for alias in aliases:
            if ingredient_lower == alias.lower().strip():
                return True
        
        # 3. Check if ingredient contains target as whole word (but not partial)
        import re
        pattern = rf'\b{re.escape(target_lower)}\b'
        if re.search(pattern, ingredient_lower):
            return True
        
        # 4. Check aliases as whole words
        for alias in aliases:
            alias_lower = alias.lower().strip()
            if alias_lower and re.search(rf'\b{re.escape(alias_lower)}\b', ingredient_lower):
                return True
        
        return False
    
    def _is_brand_specific_study(self, study_id: str, study_name: str) -> bool:
        """Check if a study is for a specific brand/proprietary ingredient - fully data-driven"""
        # Only use data-driven indicators from study ID prefixes
        study_id_indicators = ['BRAND_', 'PROP_', 'TRADE_']
        
        study_text = f"{study_id} {study_name}".lower()
        
        # Check study ID prefix patterns
        if any(indicator.lower() in study_text for indicator in study_id_indicators):
            return True
        
        # Additional data-driven heuristics:
        # 1. Study names with trademark symbols or proprietary terms
        proprietary_terms = ['™', '®', 'proprietary', 'patented', 'branded']
        if any(term in study_text for term in proprietary_terms):
            return True
        
        # 2. Study names that contain multiple capital letters (likely brand names)
        # This catches brands like "KSM-66", "BCM-95", etc. without hard-coding them
        import re
        if re.search(r'[A-Z]{2,}[-\d]*', study_name):
            return True
        
        # 3. Study names with numbers (often indicate proprietary formulations)
        if re.search(r'[A-Za-z]+[-\s]*\d+', study_name):
            return True
        
        return False
    
    def _check_brand_match(self, ingredient_text: str, study_name: str, study_aliases: List[str]) -> bool:
        """Check if ingredient text explicitly mentions the brand - fully data-driven"""
        if not ingredient_text:
            return False
            
        ingredient_lower = ingredient_text.lower()
        
        # Extract brand identifiers from study name (data-driven)
        study_name_lower = study_name.lower()
        brand_names = []
        
        # Add the study name itself as a potential brand identifier
        brand_names.append(study_name_lower)
        
        # Add all aliases as potential brand identifiers
        for alias in study_aliases:
            if alias and len(alias.strip()) > 1:  # Only meaningful aliases
                brand_names.append(alias.lower().strip())
        
        # For brand-specific studies, extract individual words as potential brand terms
        # This is completely data-driven based on what's in the JSON
        if self._is_brand_specific_study("", study_name):  # Check if it's a brand study
            # Split study name into components to extract brand terms
            study_words = study_name_lower.replace('-', ' ').split()
            for word in study_words:
                if len(word) > 2 and word not in ['the', 'and', 'for', 'with']:
                    brand_names.append(word)
        
        # Check if ingredient explicitly mentions any brand identifier
        return any(brand_term in ingredient_lower for brand_term in brand_names if brand_term)
    
    def _reset_ingredient_registry(self):
        """Reset ingredient registry for new product"""
        self.ingredient_registry = {}
    
    def _register_ingredient(self, ingredient_name: str, analysis_type: str, data: Dict):
        """Register an ingredient to prevent duplication"""
        if not ingredient_name:
            return
            
        normalized_name = ingredient_name.lower().strip()
        
        if normalized_name not in self.ingredient_registry:
            self.ingredient_registry[normalized_name] = {}
        
        self.ingredient_registry[normalized_name][analysis_type] = data
    
    def _is_ingredient_processed(self, ingredient_name: str, analysis_type: str) -> bool:
        """Check if ingredient was already processed in this analysis type"""
        if not ingredient_name:
            return False
            
        normalized_name = ingredient_name.lower().strip()
        return (normalized_name in self.ingredient_registry and 
                analysis_type in self.ingredient_registry[normalized_name])
    
    def _deduplicate_results(self, results: List[Dict], analysis_type: str) -> List[Dict]:
        """Remove duplicate ingredients from results"""
        if not results:
            return results
            
        seen_ingredients = set()
        deduplicated = []
        
        for result in results:
            # Try different keys that might contain ingredient name
            ingredient_name = (
                result.get('ingredient_name', '') or
                result.get('standard_name', '') or
                result.get('label_ingredient', '') or
                result.get('additive_name', '') or
                str(result.get('allergen_id', ''))
            )
            
            if ingredient_name:
                normalized = ingredient_name.lower().strip()
                
                # Clean up "Found in label text:" prefix for comparison
                if normalized.startswith('found in label text:'):
                    normalized = normalized.replace('found in label text:', '').strip()
                
                if normalized not in seen_ingredients:
                    seen_ingredients.add(normalized)
                    deduplicated.append(result)
                    
                    # Register this ingredient
                    self._register_ingredient(ingredient_name, analysis_type, result)
            else:
                # If no ingredient name found, include it (might be summary data)
                deduplicated.append(result)
        
        return deduplicated

    def enrich_clinical_evidence(self, product_data: Dict) -> Dict:
        """Analyze clinical evidence for ingredients with brand-specific validation"""
        clinical_data = self.databases.get('backed_clinical_studies', [])
        if not clinical_data:
            return {"evidence_found": []}
        
        evidence_found = []
        all_ingredients = []
        
        # Collect all ingredient information including forms and notes
        for ingredient in product_data.get('activeIngredients', []):
            all_ingredients.extend([
                ingredient.get('name', ''),
                ingredient.get('standardName', ''),
                ingredient.get('formDetails', ''),
                ingredient.get('notes', ''),
            ])
            all_ingredients.extend(ingredient.get('forms', []))
        
        # Also check label text for brand mentions
        label_text = product_data.get('labelText', '')
        
        # Check against clinical studies database
        for study in clinical_data:
            study_name = study.get('standard_name', '')
            study_aliases = study.get('aliases', [])
            study_id = study.get('id', '')
            
            # Check if this is a brand-specific study
            is_brand_study = self._is_brand_specific_study(study_id, study_name)
            
            matched_ingredient = None
            for ingredient_info in all_ingredients:
                if self._exact_ingredient_match(ingredient_info, study_name, study_aliases):
                    # For brand studies, require explicit brand mention
                    if is_brand_study:
                        # Check ingredient, label text, and product name for brand mention
                        brand_contexts = [ingredient_info, label_text, product_data.get('fullName', '')]
                        brand_found = any(self._check_brand_match(context, study_name, study_aliases) 
                                        for context in brand_contexts)
                        if not brand_found:
                            continue  # Skip if brand not explicitly mentioned
                    
                    matched_ingredient = ingredient_info
                    break
            
            if matched_ingredient:
                evidence_found.append({
                    "ingredient_matched": matched_ingredient,
                    "study_id": study_id,
                    "standard_name": study_name,
                    "evidence_level": study.get('evidence_level', ''),
                    "score_contribution": study.get('score_contribution', ''),
                    "health_goals_supported": study.get('health_goals_supported', []),
                    "key_endpoints": study.get('key_endpoints', []),
                    "published_studies": study.get('published_studies', []),
                    "notes": study.get('notes', ''),
                    "is_brand_specific": is_brand_study
                })
        
        return {
            "evidence_found": evidence_found,
            "total_evidence_items": len(evidence_found),
            "evidence_tiers": self._count_evidence_tiers(evidence_found)
        }
    
    def enrich_banned_substances(self, product_data: Dict) -> Dict:
        """Check for banned or recalled substances"""
        banned_data = self.databases.get('banned_recalled_ingredients', {})
        if not banned_data:
            return {"detected": False, "flagged_substances": []}
        
        flagged_substances = []
        all_ingredients = []
        
        # Collect all ingredient names and text
        for ingredient in product_data.get('activeIngredients', []) + product_data.get('inactiveIngredients', []):
            all_ingredients.extend([
                ingredient.get('name', ''),
                ingredient.get('standardName', ''),
                ingredient.get('notes', ''),
            ])
        
        all_ingredients.append(product_data.get('labelText', ''))
        
        # Check permanently banned
        for banned in banned_data.get('permanently_banned', []):
            banned_name = banned.get('standard_name', '')
            banned_aliases = banned.get('aliases', [])
            
            for ingredient_info in all_ingredients:
                if self.check_ingredient_match(ingredient_info, banned_name, banned_aliases):
                    flagged_substances.append({
                        "ingredient_name": ingredient_info,
                        "banned_id": banned.get('id', ''),
                        "standard_name": banned_name,
                        "status": "permanently_banned",
                        "severity_level": banned.get('severity_level', 'critical'),
                        "banned_date": banned.get('banned_date', ''),
                        "banned_by": banned.get('banned_by', ''),
                        "reason": banned.get('reason', ''),
                        "notes": banned.get('notes', '')
                    })
                    break
        
        # Check recalled items
        for recalled in banned_data.get('recalled_products', []):
            recalled_name = recalled.get('standard_name', '')
            recalled_aliases = recalled.get('aliases', [])
            
            for ingredient_info in all_ingredients:
                if self.check_ingredient_match(ingredient_info, recalled_name, recalled_aliases):
                    flagged_substances.append({
                        "ingredient_name": ingredient_info,
                        "recalled_id": recalled.get('id', ''),
                        "standard_name": recalled_name,
                        "status": "recalled",
                        "severity_level": recalled.get('severity_level', 'high'),
                        "recall_date": recalled.get('recall_date', ''),
                        "recall_reason": recalled.get('recall_reason', ''),
                        "notes": recalled.get('notes', '')
                    })
                    break
        
        return {
            "detected": len(flagged_substances) > 0,
            "flagged_substances": flagged_substances,
            "total_violations": len(flagged_substances),
            "has_critical_violations": any(s.get('severity_level') == 'critical' for s in flagged_substances)
        }
    
    def enrich_enhanced_delivery(self, product_data: Dict) -> Dict:
        """Detect enhanced delivery methods"""
        delivery_data = self.databases.get('enhanced_delivery', {})
        if not delivery_data:
            return {"detected": False, "delivery_methods": []}
        
        detected_methods = []
        
        # Collect all text for analysis
        all_text = []
        for ingredient in product_data.get('activeIngredients', []) + product_data.get('inactiveIngredients', []):
            all_text.extend([
                ingredient.get('name', ''),
                ingredient.get('standardName', ''),
                ingredient.get('formDetails', ''),
                ingredient.get('notes', ''),
            ])
        
        for statement in product_data.get('statements', []):
            all_text.append(statement.get('notes', ''))
        
        all_text.append(product_data.get('labelText', ''))
        all_text.append(product_data.get('fullName', ''))
        
        # Check for delivery methods
        combined_text = ' '.join(filter(None, [text or '' for text in all_text])).lower()
        
        for method_key, method_data in delivery_data.items():
            if isinstance(method_data, dict):
                # Check if method keyword appears in text
                method_patterns = [
                    method_key,
                    method_key.replace('_', ' '),
                    method_key.replace('_', '-')
                ]
                
                for pattern in method_patterns:
                    if pattern.lower() in combined_text:
                        detected_methods.append({
                            "method": method_key,
                            "points": method_data.get('points', 0),
                            "description": method_data.get('description', ''),
                            "category": method_data.get('category', 'delivery')
                        })
                        break
        
        return {
            "detected": len(detected_methods) > 0,
            "delivery_methods": detected_methods,
            "total_methods": len(detected_methods),
            "total_points": sum(m.get('points', 0) for m in detected_methods)
        }
    
    def enrich_harmful_additives(self, product_data: Dict) -> Dict:
        """Analyze harmful additives"""
        harmful_data = self.databases.get('harmful_additives', {})
        if not harmful_data:
            return {"detected": False, "flagged_additives": []}
        
        flagged_additives = []
        inactive_ingredients = []
        
        # Collect inactive ingredients
        for ingredient in product_data.get('inactiveIngredients', []):
            inactive_ingredients.extend([
                ingredient.get('name', ''),
                ingredient.get('standardName', ''),
            ])
        
        # Check against harmful additives database
        for additive in harmful_data.get('harmful_additives', []):
            additive_name = additive.get('standard_name', '')
            additive_aliases = additive.get('aliases', [])
            
            matched_ingredient = None
            for ingredient_name in inactive_ingredients:
                if self.check_ingredient_match(ingredient_name, additive_name, additive_aliases):
                    matched_ingredient = ingredient_name
                    break
            
            if matched_ingredient:
                flagged_additives.append({
                    "ingredient_name": matched_ingredient,
                    "additive_id": additive.get('id', ''),
                    "standard_name": additive_name,
                    "risk_level": additive.get('risk_level', 'low'),
                    "category": additive.get('category', ''),
                    "notes": additive.get('notes', ''),
                    "population_warnings": additive.get('population_warnings', []),
                    "regulatory_status": additive.get('regulatory_status', '')
                })
        
        # Deduplicate harmful additives
        flagged_additives = self._deduplicate_results(flagged_additives, 'harmful_additives')
        
        return {
            "detected": len(flagged_additives) > 0,
            "flagged_additives": flagged_additives,
            "total_harmful": len(flagged_additives),
            "risk_breakdown": self._count_by_risk_level(flagged_additives)
        }
    
    def enrich_ingredient_quality(self, product_data: Dict) -> List[Dict]:
        """Analyze ingredient quality from quality map"""
        quality_data = self.databases.get('ingredient_quality_map', {})
        if not quality_data:
            return []
        
        quality_analysis = []
        
        # Analyze active ingredients
        for ingredient in product_data.get('activeIngredients', []):
            ingredient_name = ingredient.get('name', '')
            standard_name = ingredient.get('standardName', '')
            forms = ingredient.get('forms', [])
            form_details = ingredient.get('formDetails', '')
            
            # Search in quality map
            for category_key, category_data in quality_data.items():
                if 'forms' not in category_data:
                    continue
                
                # Check if ingredient matches this category
                category_standard = category_data.get('standard_name', '')
                if not self.fuzzy_match(standard_name, category_standard):
                    continue
                
                # Find matching form with priority-based matching
                best_match = None
                best_form_key = None
                best_score = 0
                match_priority = 0  # Higher = better match type
                
                for form_key, form_data in category_data['forms'].items():
                    form_aliases = form_data.get('aliases', [])
                    
                    # Check against ingredient name, forms, and form details with priority
                    search_terms = [
                        (ingredient_name, 3),      # Highest priority: exact ingredient name
                        (form_details, 2),         # Medium priority: form details  
                    ] + [(form, 1) for form in forms]  # Lower priority: generic forms
                    
                    for term, priority in search_terms:
                        if not term:
                            continue
                            
                        # Use exact matching for better accuracy
                        if self._exact_ingredient_match(term, form_key, form_aliases):
                            current_score = form_data.get('score', 0)
                            
                            # Select based on priority first, then score
                            if (priority > match_priority or 
                                (priority == match_priority and current_score > best_score)):
                                best_match = form_data
                                best_form_key = form_key
                                best_score = current_score
                                match_priority = priority
                            break
                
                if best_match:
                    quality_analysis.append({
                        "label_ingredient": ingredient_name,
                        "matched_standard": category_key,
                        "matched_form": best_form_key,
                        "bio_score": best_match.get('bio_score', 0),
                        "natural": best_match.get('natural', False),
                        "score": best_match.get('score', 0),
                        "absorption": best_match.get('absorption', ''),
                        "dosage_importance": best_match.get('dosage_importance', 1.0),
                        "cui": category_data.get('cui', ''),
                        "rxcui": category_data.get('rxcui', ''),
                        "notes": best_match.get('notes', ''),
                        "quantity": ingredient.get('quantity', 0),
                        "unit": ingredient.get('unit', ''),
                        "daily_value": ingredient.get('dailyValue', 0)
                    })
                    break
        
        return quality_analysis
    
    def enrich_non_harmful_additives(self, product_data: Dict) -> List[Dict]:
        """Identify non-harmful additives"""
        nha_data = self.databases.get('non_harmful_additives', {})
        if not nha_data:
            return []
        
        non_harmful_found = []
        inactive_ingredients = []
        
        # Collect inactive ingredients
        for ingredient in product_data.get('inactiveIngredients', []):
            inactive_ingredients.append({
                'name': ingredient.get('name', ''),
                'standard_name': ingredient.get('standardName', '')
            })
        
        # Check against non-harmful additives
        for additive in nha_data.get('non_harmful_additives', []):
            additive_name = additive.get('standard_name', '')
            additive_aliases = additive.get('aliases', [])
            
            for ingredient in inactive_ingredients:
                ingredient_name = ingredient['name']
                ingredient_standard = ingredient['standard_name']
                
                if (self.check_ingredient_match(ingredient_name, additive_name, additive_aliases) or
                    self.check_ingredient_match(ingredient_standard, additive_name, additive_aliases)):
                    
                    non_harmful_found.append({
                        "ingredient_name": ingredient_name,
                        "is_non_harmful_additive": True,
                        "nha_id": additive.get('id', ''),
                        "standard_name": additive_name,
                        "additive_type": additive.get('additive_type', ''),
                        "category": additive.get('category', ''),
                        "clean_label_score": additive.get('clean_label_score', 0),
                        "regulatory_status": additive.get('regulatory_status', ''),
                        "notes": additive.get('notes', '')
                    })
                    break
        
        return non_harmful_found
    
    def enrich_passive_ingredients(self, product_data: Dict) -> List[Dict]:
        """Identify passive inactive ingredients"""
        passive_data = self.databases.get('passive_inactive_ingredients', {})
        if not passive_data:
            return []
        
        passive_found = []
        inactive_ingredients = []
        
        # Collect inactive ingredients
        for ingredient in product_data.get('inactiveIngredients', []):
            inactive_ingredients.append(ingredient.get('name', ''))
            inactive_ingredients.append(ingredient.get('standardName', ''))
        
        # Check against passive ingredients
        for passive in passive_data.get('passive_inactive_ingredients', []):
            passive_name = passive.get('standard_name', '')
            passive_aliases = passive.get('aliases', [])
            
            for ingredient_name in inactive_ingredients:
                if self.check_ingredient_match(ingredient_name, passive_name, passive_aliases):
                    passive_found.append({
                        "ingredient_name": ingredient_name,
                        "pii_id": passive.get('id', ''),
                        "standard_name": passive_name,
                        "category": passive.get('category', ''),
                        "notes": passive.get('notes', '')
                    })
                    break
        
        return passive_found
    
    def enrich_proprietary_blends(self, product_data: Dict) -> Dict:
        """Analyze proprietary blend penalties"""
        blend_data = self.databases.get('proprietary_blends_penalty', {})
        if not blend_data:
            return {"violations_detected": False, "flagged_blends": []}
        
        flagged_blends = []
        
        # Collect all text for analysis
        all_text = []
        for ingredient in product_data.get('activeIngredients', []) + product_data.get('inactiveIngredients', []):
            all_text.extend([
                ingredient.get('name', ''),
                ingredient.get('notes', ''),
            ])
        
        for statement in product_data.get('statements', []):
            all_text.append(statement.get('notes', ''))
        
        all_text.extend([
            product_data.get('fullName', ''),
            product_data.get('labelText', '')
        ])
        
        combined_text = ' '.join(filter(None, [text or '' for text in all_text])).lower()
        
        # Check for proprietary blend concerns
        for concern in blend_data.get('proprietary_blend_concerns', []):
            red_flags = concern.get('red_flag_terms', [])
            
            matched_term = None
            for flag_term in red_flags:
                if flag_term.lower() in combined_text:
                    matched_term = flag_term
                    break
            
            if matched_term:
                # Determine penalty based on disclosure level
                has_disclosure = self._check_blend_disclosure(product_data)
                penalties = concern.get('penalties', [])
                
                penalty_info = None
                if not has_disclosure:
                    penalty_info = next((p for p in penalties if p.get('type') == 'no_disclosure'), None)
                else:
                    penalty_info = next((p for p in penalties if p.get('type') == 'partial_disclosure'), None)
                
                if penalty_info:
                    flagged_blends.append({
                        "red_flag_term": matched_term,
                        "blend_id": concern.get('id', ''),
                        "standard_name": concern.get('standard_name', ''),
                        "risk_factors": concern.get('risk_factors', []),
                        "severity_level": concern.get('severity_level', ''),
                        "penalty_applied": penalty_info.get('penalty', 0),
                        "penalty_reason": penalty_info.get('penalty_reason', ''),
                        "notes": concern.get('notes', '')
                    })
        
        return {
            "violations_detected": len(flagged_blends) > 0,
            "flagged_blends": flagged_blends,
            "total_violations": len(flagged_blends),
            "total_penalty": sum(b.get('penalty_applied', 0) for b in flagged_blends)
        }
    
    def enrich_standardized_botanicals(self, product_data: Dict) -> List[Dict]:
        """Analyze standardized botanical ingredients"""
        botanical_data = self.databases.get('standardized_botanicals', {})
        if not botanical_data:
            return []
        
        standardized_found = []
        
        # Collect ingredient information
        for ingredient in product_data.get('activeIngredients', []):
            ingredient_name = ingredient.get('name', '')
            standard_name = ingredient.get('standardName', '')
            form_details = ingredient.get('formDetails', '')
            notes = ingredient.get('notes', '')
            
            # Search for botanical matches
            for botanical in botanical_data.get('standardized_botanicals', []):
                botanical_name = botanical.get('standard_name', '')
                botanical_aliases = botanical.get('aliases', [])
                markers = botanical.get('markers', [])
                
                # Check if ingredient matches botanical
                if (self.check_ingredient_match(ingredient_name, botanical_name, botanical_aliases) or
                    self.check_ingredient_match(standard_name, botanical_name, botanical_aliases)):
                    
                    # Look for standardization information
                    search_text = f"{ingredient_name} {standard_name} {form_details} {notes}"
                    
                    # Extract percentage information
                    percentages = self.text_patterns['percentage'].findall(search_text)
                    standardized_info = self.text_patterns['standardized'].findall(search_text)
                    
                    standardization_found = False
                    extracted_percentage = None
                    marker_mentioned = False
                    
                    # Check for specific markers
                    for marker in markers:
                        if marker.lower() in search_text.lower():
                            marker_mentioned = True
                            
                            # Look for percentage with this marker
                            for perc_match in percentages + standardized_info:
                                percentage, compound = perc_match
                                if marker.lower() in compound.lower():
                                    standardization_found = True
                                    extracted_percentage = f"{percentage}% {compound.strip()}"
                                    break
                    
                    # Check minimum threshold if exists
                    min_threshold = botanical.get('min_threshold')
                    meets_min_threshold = None
                    
                    if min_threshold and extracted_percentage:
                        try:
                            perc_value = float(percentages[0][0]) if percentages else 0
                            meets_min_threshold = perc_value >= min_threshold
                        except (ValueError, IndexError):
                            meets_min_threshold = False
                    
                    standardized_found.append({
                        "botanical_name": ingredient_name,
                        "standard_name": botanical_name,
                        "markers": markers,
                        "standardization_found": standardization_found,
                        "extracted_percentage": extracted_percentage,
                        "meets_min_threshold": meets_min_threshold,
                        "marker_mentioned": marker_mentioned,
                        "min_threshold": min_threshold,
                        "priority": botanical.get('priority', 'medium')
                    })
                    break
        
        return standardized_found
    
    def enrich_dosage_analysis(self, product_data: Dict) -> Dict:
        """Analyze dosages against RDA and therapeutic ranges"""
        rda_data = self.databases.get('rda_optimal_uls', {})
        therapeutic_data = self.databases.get('rda_therapeutic_dosing', {})
        
        dosage_analysis = {}
        ingredient_assessments = []
        
        for ingredient in product_data.get('activeIngredients', []):
            ingredient_name = ingredient.get('standardName', ingredient.get('name', ''))
            amount = ingredient.get('quantity', 0)
            unit = ingredient.get('unit', '')
            
            if not ingredient_name or amount == 0:
                continue
                
            # Find RDA/UL info
            rda_info = self._find_rda_info(ingredient_name, rda_data)
            
            # Find therapeutic info
            therapeutic_info = self._find_therapeutic_info(ingredient_name, therapeutic_data)
            
            # Calculate assessments
            assessment = {
                "ingredient_name": ingredient_name,
                "amount": amount,
                "unit": unit,
                "rda_analysis": rda_info,
                "therapeutic_analysis": therapeutic_info,
                "dosage_category": self._determine_dosage_category(amount, unit, rda_info, therapeutic_info),
                "safety_assessment": self._assess_dosage_safety(amount, unit, rda_info, therapeutic_info)
            }
            
            ingredient_assessments.append(assessment)
        
        return {
            "total_ingredients_analyzed": len(ingredient_assessments),
            "ingredient_assessments": ingredient_assessments,
            "summary": self._create_dosage_summary(ingredient_assessments)
        }
    
    def _find_rda_info(self, ingredient_name: str, rda_data: Dict) -> Dict:
        """Find RDA/UL information for an ingredient"""
        nutrient_recommendations = rda_data.get('nutrient_recommendations', [])
        
        for nutrient in nutrient_recommendations:
            standard_name = nutrient.get('standard_name', '')
            aliases = nutrient.get('aliases', [])
            
            if self.check_ingredient_match(ingredient_name, standard_name, aliases):
                # Get UL information with proper handling
                highest_ul = nutrient.get('highest_ul', 0)
                ul_note = nutrient.get('ul_note', '')
                
                # Format UL display value
                if highest_ul == 0 or highest_ul is None:
                    ul_display = "ND" if not ul_note else "none"
                else:
                    ul_display = f"{highest_ul} {nutrient.get('unit', '')}"
                
                # Get age-specific UL data if available
                age_specific_uls = []
                data_points = nutrient.get('data', [])
                for point in data_points:
                    if 'ul' in point:
                        ul_val = point.get('ul')
                        if ul_val and ul_val != 'ND':
                            age_specific_uls.append({
                                "group": point.get('group', ''),
                                "age_range": point.get('age_range', ''),
                                "ul": ul_val,
                                "unit": nutrient.get('unit', '')
                            })
                
                return {
                    "found": True,
                    "standard_name": standard_name,
                    "unit": nutrient.get('unit', ''),
                    "optimal_range": nutrient.get('optimal_range', ''),
                    "ul_value": highest_ul if highest_ul else 0,
                    "ul_display": ul_display,
                    "ul_note": ul_note,
                    "age_specific_uls": age_specific_uls,
                    "warnings": nutrient.get('warnings', [])
                }
        
        return {"found": False}
    
    def _find_therapeutic_info(self, ingredient_name: str, therapeutic_data: Dict) -> Dict:
        """Find therapeutic dosing information for an ingredient"""
        therapeutic_dosing = therapeutic_data.get('therapeutic_dosing', [])
        
        for therapeutic in therapeutic_dosing:
            standard_name = therapeutic.get('standard_name', '')
            aliases = therapeutic.get('aliases', [])
            
            if self.check_ingredient_match(ingredient_name, standard_name, aliases):
                return {
                    "found": True,
                    "standard_name": standard_name,
                    "unit": therapeutic.get('unit', ''),
                    "typical_range": therapeutic.get('typical_dosing_range', ''),
                    "common_serving": therapeutic.get('common_serving_size', ''),
                    "upper_limit": therapeutic.get('upper_limit', ''),
                    "upper_limit_notes": therapeutic.get('upper_limit_notes', ''),
                    "evidence_tier": therapeutic.get('evidence_tier', 0),
                    "common_use": therapeutic.get('common_use', '')
                }
        
        return {"found": False}
    
    def _determine_dosage_category(self, amount: float, unit: str, rda_info: Dict, therapeutic_info: Dict) -> str:
        """Determine dosage category based on RDA and therapeutic ranges"""
        if not rda_info.get('found') and not therapeutic_info.get('found'):
            return "unknown"
        
        # For RDA-based nutrients
        if rda_info.get('found'):
            optimal_range = rda_info.get('optimal_range', '')
            ul_value = rda_info.get('ul_value', 0)
            
            if optimal_range and '-' in optimal_range:
                try:
                    min_opt, max_opt = map(float, optimal_range.split('-'))
                    ul_val = float(ul_value) if ul_value else 0
                    
                    if amount <= min_opt * 0.5:
                        return "trace"
                    elif amount <= min_opt:
                        return "maintenance" 
                    elif amount <= max_opt:
                        return "optimal"
                    elif ul_val > 0 and amount <= ul_val:
                        return "therapeutic"
                    elif ul_val > 0 and amount > ul_val:
                        return "excessive"
                    else:
                        return "high_therapeutic"
                except (ValueError, TypeError):
                    pass
        
        # For therapeutic-based nutrients
        if therapeutic_info.get('found'):
            typical_range = therapeutic_info.get('typical_range', '')
            upper_limit = therapeutic_info.get('upper_limit', '')
            
            if typical_range and '-' in typical_range:
                try:
                    min_ther, max_ther = map(float, typical_range.split('-'))
                    if amount < min_ther * 0.5:
                        return "trace"
                    elif amount <= max_ther:
                        return "therapeutic"
                    elif upper_limit:
                        upper_val = float(upper_limit)
                        if amount <= upper_val:
                            return "high_therapeutic"
                        else:
                            return "excessive"
                    else:
                        return "high_therapeutic"
                except ValueError:
                    pass
        
        return "moderate"
    
    def _assess_dosage_safety(self, amount: float, unit: str, rda_info: Dict, therapeutic_info: Dict) -> Dict:
        """Assess safety of the dosage"""
        safety = {
            "safety_level": "safe",
            "warnings": [],
            "considerations": [],
            "ul_comparison": "not_applicable"
        }
        
        # Check RDA UL warnings
        if rda_info.get('found'):
            ul_value = rda_info.get('ul_value', 0)
            ul_display = rda_info.get('ul_display', 'ND')
            
            try:
                ul_val = float(ul_value) if ul_value else 0
                if ul_val > 0:
                    if amount > ul_val:
                        safety["safety_level"] = "caution"
                        safety["warnings"].append(f"⚠️ EXCEEDS Upper Limit: {amount} {unit} > {ul_display}")
                        safety["ul_comparison"] = "exceeds"
                    elif amount > ul_val * 0.8:  # Within 80% of UL
                        safety["safety_level"] = "moderate"
                        safety["considerations"].append(f"Approaching Upper Limit: {amount} {unit} (UL: {ul_display})")
                        safety["ul_comparison"] = "approaching"
                    else:
                        safety["considerations"].append(f"Below Upper Limit: {amount} {unit} (UL: {ul_display})")
                        safety["ul_comparison"] = "below"
                else:
                    # No UL established
                    safety["considerations"].append(f"Upper Limit: {ul_display}")
                    safety["ul_comparison"] = "no_ul_established"
            except (ValueError, TypeError):
                safety["considerations"].append(f"Upper Limit: {ul_display}")
                safety["ul_comparison"] = "no_ul_established"
            
            safety["warnings"].extend(rda_info.get('warnings', []))
        
        # Check therapeutic warnings
        if therapeutic_info.get('found'):
            upper_limit = therapeutic_info.get('upper_limit', '')
            upper_notes = therapeutic_info.get('upper_limit_notes', '')
            
            if upper_limit:
                try:
                    upper_val = float(upper_limit)
                    if amount > upper_val:
                        safety["safety_level"] = "caution"
                        safety["warnings"].append(f"⚠️ Exceeds therapeutic upper limit: {amount} {unit} > {upper_val} {unit}")
                        if upper_notes:
                            safety["considerations"].append(upper_notes)
                except ValueError:
                    pass
        
        return safety
    
    def _create_dosage_summary(self, assessments: List[Dict]) -> Dict:
        """Create summary of dosage analysis"""
        if not assessments:
            return {"categories": {}, "safety_flags": 0}
        
        categories = {}
        safety_flags = 0
        
        for assessment in assessments:
            category = assessment.get('dosage_category', 'unknown')
            categories[category] = categories.get(category, 0) + 1
            
            if assessment.get('safety_assessment', {}).get('safety_level') == 'caution':
                safety_flags += 1
        
        return {
            "categories": categories,
            "safety_flags": safety_flags,
            "total_analyzed": len(assessments)
        }

    def enrich_synergy_clusters(self, product_data: Dict) -> List[Dict]:
        """Analyze ingredient synergy clusters"""
        synergy_data = self.databases.get('synergy_cluster', {})
        if not synergy_data:
            return []
        
        detected_clusters = []
        product_ingredients = {}
        
        # Build ingredient map with quantities
        for ingredient in product_data.get('activeIngredients', []):
            name = ingredient.get('name', '').lower()
            standard_name = ingredient.get('standardName', '').lower()
            quantity = ingredient.get('quantity', 0)
            unit = ingredient.get('unit', '')
            
            product_ingredients[name] = {'quantity': quantity, 'unit': unit}
            product_ingredients[standard_name] = {'quantity': quantity, 'unit': unit}
        
        # Check each synergy cluster
        for cluster in synergy_data.get('synergy_clusters', []):
            cluster_name = cluster.get('name', '')
            cluster_ingredients = cluster.get('ingredients', [])
            min_doses = cluster.get('min_effective_doses', {})
            evidence_tier = cluster.get('evidence_tier', 3)
            
            # Find matching ingredients
            matching_ingredients = []
            for cluster_ingredient in cluster_ingredients:
                cluster_ingredient_lower = cluster_ingredient.lower()
                if cluster_ingredient_lower in product_ingredients:
                    matching_ingredients.append(cluster_ingredient)
            
            # If we have matches, analyze the cluster
            if len(matching_ingredients) >= 2:  # Need at least 2 ingredients for synergy
                dose_adequacy = {}
                
                for ingredient in matching_ingredients:
                    ingredient_lower = ingredient.lower()
                    if ingredient_lower in product_ingredients and ingredient.lower() in min_doses:
                        current_dose = product_ingredients[ingredient_lower]['quantity']
                        min_dose = min_doses[ingredient.lower()]
                        
                        dose_adequacy[ingredient] = {
                            "current": current_dose,
                            "minimum": min_dose,
                            "meets_minimum": current_dose >= min_dose,
                            "percentage_of_minimum": (current_dose / min_dose * 100) if min_dose > 0 else 0,
                            "unit": product_ingredients[ingredient_lower]['unit']
                        }
                
                detected_clusters.append({
                    "cluster_name": cluster_name,
                    "matching_ingredients": matching_ingredients,
                    "total_matches": len(matching_ingredients),
                    "min_effective_doses": min_doses,
                    "dose_adequacy": dose_adequacy,
                    "evidence_tier": evidence_tier,
                    "cluster_effectiveness": self._assess_cluster_effectiveness(dose_adequacy)
                })
        
        return detected_clusters
    
    def validate_enrichment(self, enriched_data: Dict) -> Tuple[bool, List[str]]:
        """Validate that critical enrichments were performed with quality data"""
        issues = []
        
        # Check required top-level fields
        required_fields = ['dsld_id', 'enrichment_version', 'ingredient_analysis', 'manufacturer_analysis']
        for field in required_fields:
            if field not in enriched_data:
                issues.append(f"Missing required field: {field}")
        
        # Check critical analyses are present
        critical_analyses = [
            'allergen_analysis',
            'banned_substances', 
            'dosage_analysis',
            'harmful_additives',
            'enhanced_delivery',
            'clinical_evidence',
            'ingredient_summary'
        ]
        
        ingredient_analysis = enriched_data.get('ingredient_analysis', {})
        for analysis in critical_analyses:
            if analysis not in ingredient_analysis:
                issues.append(f"Missing critical analysis: {analysis}")
            elif not ingredient_analysis[analysis]:  # Check if empty
                issues.append(f"Empty analysis detected: {analysis}")
        
        # Validate data quality
        if ingredient_analysis.get('ingredient_summary', {}).get('total_active_ingredients', 0) == 0:
            issues.append("No active ingredients found - possible processing error")
        
        # Check for reasonable processing
        allergen_data = ingredient_analysis.get('allergen_analysis', {})
        if isinstance(allergen_data, dict) and not allergen_data.get('detected_allergens') and not allergen_data.get('detected', False):
            # This might be normal, so just log info level
            pass
        
        # Validate manufacturer analysis
        manufacturer_data = enriched_data.get('manufacturer_analysis', {})
        if not manufacturer_data.get('manufacturer_found', False):
            issues.append("Manufacturer not found in database - may affect scoring")
        
        # Check dosage analysis quality (new feature validation)
        dosage_data = ingredient_analysis.get('dosage_analysis', {})
        if dosage_data.get('total_ingredients_analyzed', 0) == 0:
            issues.append("Dosage analysis failed - no ingredients analyzed")
        
        # Log issues
        if issues:
            logger.warning(f"Validation issues found: {len(issues)} problems")
            for issue in issues:
                logger.warning(f"  - {issue}")
        else:
            logger.debug("Enrichment validation passed")
        
        return len(issues) == 0, issues
    
    def enrich_manufacturer_analysis(self, product_data: Dict) -> Dict:
        """Analyze manufacturer reputation"""
        manufacturer_data = self.databases.get('top_manufacturers_data', {})
        if not manufacturer_data:
            return {"manufacturer_found": False}
        
        # Extract manufacturer information
        manufacturer_name = ""
        contacts = product_data.get('contacts', [])
        
        if isinstance(contacts, list) and contacts:
            manufacturer_name = contacts[0].get('name', '')
        elif isinstance(contacts, dict):
            manufacturer_name = contacts.get('name', '')
        
        if not manufacturer_name:
            return {"manufacturer_found": False}
        
        # Search in top manufacturers
        for manufacturer in manufacturer_data:
            standard_name = manufacturer.get('standard_name', '')
            aka_names = manufacturer.get('aka', [])
            
            if (self.fuzzy_match(manufacturer_name, standard_name) or
                any(self.fuzzy_match(manufacturer_name, aka) for aka in aka_names)):
                
                return {
                    "manufacturer_found": True,
                    "manufacturer_name": manufacturer_name,
                    "manufacturer_id": manufacturer.get('id', ''),
                    "standard_name": standard_name,
                    "score_contribution": manufacturer.get('score_contribution', 0),
                    "reputation_evidence": manufacturer.get('evidence', []),
                    "notes": manufacturer.get('notes', '')
                }
        
        return {
            "manufacturer_found": False,
            "manufacturer_name": manufacturer_name
        }
    
    def _check_blend_disclosure(self, product_data: Dict) -> bool:
        """Check if product has proper ingredient disclosure"""
        # Simple check - if all active ingredients have quantities, assume good disclosure
        for ingredient in product_data.get('activeIngredients', []):
            if not ingredient.get('quantity') or ingredient.get('proprietaryBlend', False):
                return False
        return True
    
    def _count_by_severity(self, items: List[Dict]) -> Dict:
        """Count items by severity level"""
        counts = {'low': 0, 'moderate': 0, 'high': 0, 'critical': 0}
        for item in items:
            severity = item.get('severity_level', 'low')
            counts[severity] = counts.get(severity, 0) + 1
        return counts
    
    def _count_by_risk_level(self, items: List[Dict]) -> Dict:
        """Count items by risk level"""
        counts = {'low': 0, 'moderate': 0, 'high': 0, 'critical': 0}
        for item in items:
            risk = item.get('risk_level', 'low')
            counts[risk] = counts.get(risk, 0) + 1
        return counts
    
    def _count_evidence_tiers(self, items: List[Dict]) -> Dict:
        """Count evidence by tiers"""
        counts = {'tier_1': 0, 'tier_2': 0, 'tier_3': 0}
        for item in items:
            tier = item.get('score_contribution', 'tier_3')
            counts[tier] = counts.get(tier, 0) + 1
        return counts
    
    def _assess_cluster_effectiveness(self, dose_adequacy: Dict) -> str:
        """Assess overall cluster effectiveness"""
        if not dose_adequacy:
            return "no_dosage_info"
        
        meets_minimum_count = sum(1 for d in dose_adequacy.values() if d.get('meets_minimum', False))
        total_ingredients = len(dose_adequacy)
        
        if meets_minimum_count == total_ingredients:
            return "fully_effective"
        elif meets_minimum_count >= total_ingredients * 0.5:
            return "partially_effective"
        else:
            return "insufficient_dosing"
    
    def enrich_product(self, product_data: Dict) -> EnrichmentResult:
        """Enrich a single product with all database information"""
        start_time = time.time()
        product_id = product_data.get('id', 'unknown')
        
        # Reset ingredient registry for new product to prevent cross-contamination
        self._reset_ingredient_registry()
        
        try:
            logger.info(f"Enriching product {product_id}: {product_data.get('fullName', 'Unknown')}")
            
            # Create comprehensive enriched data structure
            enriched_data = {
                "dsld_id": product_id,
                "enrichment_version": self.config['enrichment_info']['version'],
                "enriched_timestamp": datetime.now().isoformat(),
                "source_product": {
                    "fullName": product_data.get('fullName', ''),
                    "brandName": product_data.get('brandName', ''),
                    "productType": product_data.get('productType', ''),
                    "physicalState": product_data.get('physicalState', ''),
                    "targetGroups": product_data.get('targetGroups', [])
                },
                
                # Basic product information
                "basic_product_info": {
                    "product_name": product_data.get('fullName', ''),
                    "brand_name": product_data.get('brandName', ''),
                    "upc_code": product_data.get('upcSku', '').replace(' ', ''),
                    "upc_valid": product_data.get('upcValid', False),
                    "serving_size": self._extract_serving_info(product_data),
                    "servings_per_container": product_data.get('servingsPerContainer', 0),
                    "net_quantity": product_data.get('netContents', ''),
                    "images": [product_data.get('imageUrl', '')] if product_data.get('imageUrl') else [],
                    "target_demographics": product_data.get('targetGroups', []),
                    "product_status": product_data.get('status', 'unknown')
                },
                
                # Comprehensive ingredient analysis
                "ingredient_analysis": {
                    "absorption_enhancers": self.enrich_absorption_enhancers(product_data),
                    "allergen_analysis": self.enrich_allergen_analysis(product_data),
                    "clinical_evidence": self.enrich_clinical_evidence(product_data),
                    "banned_substances": self.enrich_banned_substances(product_data),
                    "enhanced_delivery": self.enrich_enhanced_delivery(product_data),
                    "harmful_additives": self.enrich_harmful_additives(product_data),
                    "ingredient_quality": self.enrich_ingredient_quality(product_data),
                    "non_harmful_additives": self.enrich_non_harmful_additives(product_data),
                    "passive_ingredients": self.enrich_passive_ingredients(product_data),
                    "proprietary_blend_penalties": self.enrich_proprietary_blends(product_data),
                    "standardized_botanicals": self.enrich_standardized_botanicals(product_data),
                    "synergy_clusters": self.enrich_synergy_clusters(product_data),
                    "dosage_analysis": self.enrich_dosage_analysis(product_data),
                    
                    # Ingredient counts and summaries
                    "ingredient_summary": {
                        "total_active_ingredients": len(product_data.get('activeIngredients', [])),
                        "total_inactive_ingredients": len(product_data.get('inactiveIngredients', [])),
                        "proprietary_blends": product_data.get('metadata', {}).get('proprietaryBlendStats', {}).get('hasProprietaryBlends', False),
                        "mapping_rate": product_data.get('metadata', {}).get('mappingStats', {}).get('mappingRate', 0)
                    }
                },
                
                # Manufacturer analysis
                "manufacturer_analysis": self.enrich_manufacturer_analysis(product_data),
                
                # Claims and statements analysis
                "claims_analysis": self._analyze_claims(product_data),
                "certification_analysis": self.extract_certifications(product_data),
                
                # Safety and compliance
                "safety_analysis": self._analyze_safety(product_data),
                
                # Mobile app preparation
                "mobile_app_data": self._prepare_mobile_data(product_data),
                
                # Scoring system preparation
                "scoring_preparation": self._prepare_scoring_data(product_data),
                
                # Processing metadata
                "enrichment_metadata": {
                    "databases_processed": len(self.databases),
                    "processing_time_seconds": 0,  # Will be updated
                    "enrichment_flags": self._generate_flags(product_data),
                    "data_completeness": self._assess_completeness(product_data)
                }
            }
            
            processing_time = time.time() - start_time
            enriched_data["enrichment_metadata"]["processing_time_seconds"] = round(processing_time, 3)
            
            # Cross-validate certifications against detected allergens
            certification_data = enriched_data.get('certification_analysis', {})
            allergen_data = enriched_data.get('ingredient_analysis', {}).get('allergen_analysis', {})
            detected_allergens = allergen_data.get('detected_allergens', [])
            
            cross_validation = self._cross_validate_certifications(certification_data, detected_allergens)
            enriched_data['cross_validation'] = cross_validation
            
            # Validate enrichment quality
            is_valid, validation_issues = self.validate_enrichment(enriched_data)
            
            # Add cross-validation issues to validation
            if cross_validation.get('has_contradictions', False):
                validation_issues.extend(cross_validation.get('contradictions', []))
                is_valid = False
            
            # Add validation metadata
            enriched_data["enrichment_metadata"]["validation"] = {
                "passed": is_valid,
                "issues_count": len(validation_issues),
                "issues": validation_issues,
                "validated_at": datetime.now().isoformat()
            }
            
            return EnrichmentResult(
                success=True,
                product_id=product_id,
                enriched_data=enriched_data,
                warnings=validation_issues if not is_valid else None,
                processing_time=processing_time
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Failed to enrich product {product_id}: {e}")
            return EnrichmentResult(
                success=False,
                product_id=product_id,
                errors=[str(e)],
                processing_time=processing_time
            )
    
    def _extract_serving_info(self, product_data: Dict) -> str:
        """Extract serving size information"""
        serving_sizes = product_data.get('servingSizes', [])
        if serving_sizes:
            serving = serving_sizes[0]
            min_qty = serving.get('minQuantity', 1)
            max_qty = serving.get('maxQuantity', 1)
            unit = serving.get('unit', 'serving')
            
            if min_qty == max_qty:
                return f"{min_qty} {unit}"
            else:
                return f"{min_qty}-{max_qty} {unit}"
        return "1 serving"
    
    def extract_certifications(self, product_data: Dict) -> Dict:
        """Extract certification claims from text"""
        certification_patterns = {
            'nsf': r'\bNSF\b.*?(certified|sport|contents)',
            'usp': r'\bUSP\b.*?(verified|mark)',
            'gmp': r'\b(c?GMP|good\s+manufacturing)',
            'organic': r'\b(USDA\s+organic|certified\s+organic)',
            'third_party': r'(third[- ]party|independently)\s+(tested|verified)',
            'non_gmo': r'(non[- ]?GMO|GMO[- ]?free)',
            'kosher': r'\b(kosher|OU|OK)\b',
            'halal': r'\bhalal\b',
            'vegan': r'\b(vegan|plant[- ]based)\b',
            'gluten_free': r'(gluten[- ]?free|no\s+gluten)',
            'soy_free': r'(soy[- ]?free|no\s+soy)',
            'dairy_free': r'(dairy[- ]?free|lactose[- ]?free|no\s+(dairy|lactose))'
        }
        
        text_to_search = self._combine_all_text(product_data)
        found_certifications = {}
        
        for cert_type, pattern in certification_patterns.items():
            if re.search(pattern, text_to_search, re.IGNORECASE):
                found_certifications[cert_type] = True
                
        # Also check structured data
        target_groups = product_data.get('targetGroups', [])
        for group in target_groups:
            group_lower = group.lower()
            if 'gluten free' in group_lower:
                found_certifications['gluten_free'] = True
            elif 'dairy free' in group_lower:
                found_certifications['dairy_free'] = True
            elif 'soy free' in group_lower:
                found_certifications['soy_free'] = True
            elif 'vegan' in group_lower:
                found_certifications['vegan'] = True
        
        return {
            "certifications_found": found_certifications,
            "total_certifications": len(found_certifications),
            "certification_score": self._calculate_certification_score(found_certifications)
        }
    
    def _cross_validate_certifications(self, certifications: Dict, allergens: List[Dict]) -> Dict:
        """Cross-validate certifications against detected allergens for contradictions"""
        contradictions = []
        warnings = []
        
        cert_found = certifications.get('certifications_found', {})
        
        # Check for allergen vs certification contradictions
        allergen_types = set()
        for allergen in allergens:
            allergen_name = allergen.get('standard_name', '').lower()
            if allergen_name:
                allergen_types.add(allergen_name)
        
        # Check specific contradictions
        if cert_found.get('gluten_free') and any('gluten' in allergen or 'wheat' in allergen for allergen in allergen_types):
            contradictions.append("Product claims 'Gluten Free' but contains gluten/wheat allergens")
        
        if cert_found.get('dairy_free') and any('milk' in allergen or 'dairy' in allergen for allergen in allergen_types):
            contradictions.append("Product claims 'Dairy Free' but contains milk/dairy allergens")
        
        if cert_found.get('soy_free') and 'soy' in allergen_types:
            contradictions.append("Product claims 'Soy Free' but contains soy allergens")
        
        if cert_found.get('vegan'):
            non_vegan_indicators = ['milk', 'dairy', 'gelatin', 'collagen', 'whey', 'casein']
            found_non_vegan = [indicator for indicator in non_vegan_indicators if indicator in allergen_types]
            if found_non_vegan:
                contradictions.append(f"Product claims 'Vegan' but contains animal-derived ingredients: {', '.join(found_non_vegan)}")
        
        # Check for missing certifications (warnings)
        if allergen_types:
            if not cert_found.get('gluten_free') and not any('gluten' in a or 'wheat' in a for a in allergen_types):
                warnings.append("Product appears gluten-free but lacks certification")
            
            if not cert_found.get('dairy_free') and not any('milk' in a or 'dairy' in a for a in allergen_types):
                warnings.append("Product appears dairy-free but lacks certification")
        
        return {
            "has_contradictions": len(contradictions) > 0,
            "contradictions": contradictions,
            "warnings": warnings,
            "validation_status": "failed" if contradictions else ("warning" if warnings else "passed")
        }
    
    def _combine_all_text(self, product_data: Dict) -> str:
        """Combine all text fields for pattern matching"""
        all_text = []
        
        # Product info
        all_text.extend([
            product_data.get('fullName', ''),
            product_data.get('labelText', ''),
            product_data.get('brandName', '')
        ])
        
        # Statements
        for statement in product_data.get('statements', []):
            all_text.append(statement.get('notes', ''))
        
        # Ingredient notes
        for ingredient in product_data.get('activeIngredients', []) + product_data.get('inactiveIngredients', []):
            all_text.extend([
                ingredient.get('notes', ''),
                ingredient.get('formDetails', '')
            ])
        
        return ' '.join(filter(None, [text or '' for text in all_text]))
    
    def _calculate_certification_score(self, certifications: Dict) -> int:
        """Calculate certification score based on value hierarchy"""
        scores = {
            'nsf': 5, 'usp': 5, 'third_party': 4, 'gmp': 3,
            'organic': 2, 'non_gmo': 2, 'kosher': 1, 'halal': 1,
            'vegan': 1, 'gluten_free': 1, 'soy_free': 1, 'dairy_free': 1
        }
        
        return sum(scores.get(cert, 1) for cert in certifications.keys())

    def _analyze_claims(self, product_data: Dict) -> Dict:
        """Analyze product claims and statements"""
        claims = product_data.get('claims', [])
        statements = product_data.get('statements', [])
        
        structure_function_claims = []
        health_claims = []
        marketing_claims = []
        
        # Process claims
        for claim in claims:
            if claim.get('description') == 'Structure/Function':
                structure_function_claims.append(claim)
            else:
                health_claims.append(claim)
        
        # Process statements for marketing claims
        for statement in statements:
            statement_type = statement.get('type', '')
            notes = statement.get('notes', '')
            
            if 'General Statements' in statement_type:
                marketing_claims.append({
                    "claim": notes,
                    "type": "marketing",
                    "source": statement_type
                })
        
        return {
            "structure_function_claims": structure_function_claims,
            "health_claims": health_claims,
            "marketing_claims": marketing_claims,
            "total_claims": len(claims),
            "fda_compliant": not any(c.get('hasUnsubstantiated', False) for c in claims)
        }
    
    def _analyze_safety(self, product_data: Dict) -> Dict:
        """Analyze overall safety profile"""
        # This will be enhanced with data from enrichment analyses
        return {
            "overall_safety_rating": "pending_analysis",
            "age_restrictions": self._extract_age_restrictions(product_data),
            "warnings": self._extract_warnings(product_data),
            "contraindications": self._extract_contraindications(product_data)
        }
    
    def _extract_age_restrictions(self, product_data: Dict) -> List[str]:
        """Extract age restrictions from statements"""
        age_restrictions = []
        statements = product_data.get('statements', [])
        
        for statement in statements:
            notes = statement.get('notes', '').lower()
            if 'not for children' in notes or 'under' in notes and 'age' in notes:
                age_restrictions.append(statement.get('notes', ''))
        
        return age_restrictions
    
    def _extract_warnings(self, product_data: Dict) -> List[str]:
        """Extract warnings from statements"""
        warnings = []
        statements = product_data.get('statements', [])
        
        for statement in statements:
            statement_type = statement.get('type', '')
            if 'Precautions' in statement_type or 'Warning' in statement_type:
                warnings.append(statement.get('notes', ''))
        
        return warnings
    
    def _extract_contraindications(self, product_data: Dict) -> List[str]:
        """Extract contraindications"""
        contraindications = []
        statements = product_data.get('statements', [])
        
        for statement in statements:
            notes = statement.get('notes', '').lower()
            if ('pregnant' in notes or 'nursing' in notes or 
                'medication' in notes or 'doctor' in notes):
                contraindications.append(statement.get('notes', ''))
        
        return contraindications
    
    def _prepare_mobile_data(self, product_data: Dict) -> Dict:
        """Prepare data optimized for mobile app"""
        return {
            "barcode_scannable": bool(product_data.get('upcValid', False)),
            "upc_verified": product_data.get('upcValid', False),
            "ui_display_ready": {
                "short_name": product_data.get('fullName', '')[:30] + "..." if len(product_data.get('fullName', '')) > 30 else product_data.get('fullName', ''),
                "brand": product_data.get('brandName', ''),
                "form": product_data.get('physicalState', ''),
                "target_group": product_data.get('targetGroups', []),
                "key_ingredients": [ing.get('name', '') for ing in product_data.get('activeIngredients', [])[:3]]
            }
        }
    
    def _prepare_scoring_data(self, product_data: Dict) -> Dict:
        """Prepare data for scoring system"""
        return {
            "ready_for_scoring": True,
            "scoring_timestamp": datetime.now().isoformat(),
            "ingredient_count": len(product_data.get('activeIngredients', [])),
            "has_proprietary_blends": product_data.get('metadata', {}).get('proprietaryBlendStats', {}).get('hasProprietaryBlends', False),
            "mapping_completeness": product_data.get('metadata', {}).get('mappingStats', {}).get('mappingRate', 0)
        }
    
    def _generate_flags(self, product_data: Dict) -> List[str]:
        """Generate processing flags"""
        flags = []
        
        if product_data.get('status') == 'discontinued':
            flags.append('discontinued_product')
        
        if product_data.get('metadata', {}).get('proprietaryBlendStats', {}).get('hasProprietaryBlends', False):
            flags.append('has_proprietary_blends')
        
        if product_data.get('metadata', {}).get('qualityFlags', {}).get('hasHarmfulAdditives', False):
            flags.append('has_harmful_additives')
        
        if product_data.get('metadata', {}).get('qualityFlags', {}).get('hasAllergens', False):
            flags.append('has_allergens')
        
        return flags
    
    def _assess_completeness(self, product_data: Dict) -> Dict:
        """Assess data completeness"""
        completeness = product_data.get('metadata', {}).get('completeness', {})
        return {
            "score": completeness.get('score', 0),
            "missing_fields": completeness.get('missingFields', []),
            "critical_complete": completeness.get('criticalFieldsComplete', False)
        }
    
    def _get_review_priority(self, warnings: List[str]) -> str:
        """Determine review priority based on warning types"""
        high_priority_keywords = [
            'banned', 'harmful', 'allergen', 'safety', 'recalled', 
            'contaminated', 'undisclosed', 'proprietary_stimulants'
        ]
        moderate_priority_keywords = [
            'proprietary_blend', 'missing_dose', 'incomplete_data',
            'standardization', 'therapeutic_range'
        ]
        
        warning_text = ' '.join(warnings).lower()
        
        if any(keyword in warning_text for keyword in high_priority_keywords):
            return 'high'
        elif any(keyword in warning_text for keyword in moderate_priority_keywords):
            return 'moderate'
        else:
            return 'low'
    
    def _generate_action_items(self, warnings: List[str]) -> List[str]:
        """Generate specific action items based on warnings"""
        actions = []
        warning_text = ' '.join(warnings).lower()
        
        if 'banned' in warning_text or 'recalled' in warning_text:
            actions.append("URGENT: Verify ingredient safety status with regulatory databases")
        if 'harmful' in warning_text or 'safety' in warning_text:
            actions.append("Review safety profile and consider removal from consideration")
        if 'allergen' in warning_text:
            actions.append("Verify allergen labeling and cross-contamination risks")
        if 'proprietary_blend' in warning_text:
            actions.append("Request detailed ingredient breakdown from manufacturer")
        if 'missing_dose' in warning_text or 'incomplete_data' in warning_text:
            actions.append("Gather additional product information and dosage data")
        if 'standardization' in warning_text:
            actions.append("Verify ingredient standardization and potency claims")
        if 'therapeutic_range' in warning_text:
            actions.append("Review dosage adequacy against therapeutic guidelines")
        
        if not actions:
            actions.append("Review product details for data quality issues")
        
        return actions
    
    def _create_review_report(self, needs_review: List[Dict], report_path: str) -> None:
        """Create actionable review report"""
        priority_stats = {'high': 0, 'moderate': 0, 'low': 0}
        action_summary = {}
        
        for product in needs_review:
            priority = product.get('review_priority', 'low')
            priority_stats[priority] += 1
            
            for action in product.get('action_items', []):
                if action not in action_summary:
                    action_summary[action] = 0
                action_summary[action] += 1
        
        report = {
            "review_summary": {
                "total_products_needing_review": len(needs_review),
                "priority_breakdown": priority_stats,
                "report_timestamp": datetime.now().isoformat()
            },
            "action_items_summary": {
                "unique_actions_needed": len(action_summary),
                "action_frequency": sorted(action_summary.items(), key=lambda x: x[1], reverse=True)
            },
            "detailed_products": needs_review
        }
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
    
    def process_batch(self, input_file: str, output_dir: str) -> Dict:
        """Process a batch of products with quality separation"""
        batch_start_time = time.time()
        
        try:
            # Load input data
            with open(input_file, 'r', encoding='utf-8') as f:
                products = json.load(f)
            
            logger.info(f"Processing batch: {len(products)} products from {input_file}")
            
            # Process each product with quality tracking
            enriched_products = []  # Clean, validated products
            needs_review = []       # Products with validation issues
            errors = []            # Failed processing
            
            for i, product in enumerate(products):
                result = self.enrich_product(product)
                
                if result.success:
                    # Check if product has validation warnings
                    if result.warnings and len(result.warnings) > 0:
                        needs_review.append({
                            "product": result.enriched_data,
                            "issues": result.warnings,
                            "review_priority": self._get_review_priority(result.warnings),
                            "action_items": self._generate_action_items(result.warnings),
                            "processing_timestamp": datetime.now().isoformat()
                        })
                        logger.info(f"Product {result.product_id} needs review: {len(result.warnings)} issues")
                    else:
                        enriched_products.append(result.enriched_data)
                    
                    self.stats['successful_enrichments'] += 1
                else:
                    errors.append({
                        "product_id": result.product_id,
                        "errors": result.errors,
                        "action_items": ["Fix data processing errors", "Check data integrity"],
                        "review_priority": "high"
                    })
                    self.stats['failed_enrichments'] += 1
                
                self.stats['total_processed'] += 1
                
                # Progress logging
                if (i + 1) % 10 == 0:
                    logger.info(f"Processed {i + 1}/{len(products)} products")
            
            # Create output directories
            base_output = Path(output_dir)
            enriched_dir = base_output / "enriched"
            review_dir = base_output / "needs_review"
            reports_dir = base_output / "reports"
            
            enriched_dir.mkdir(parents=True, exist_ok=True)
            review_dir.mkdir(parents=True, exist_ok=True)
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            batch_name = Path(input_file).stem
            
            # Define output file paths
            enriched_file = enriched_dir / f"enriched_{batch_name}.json"
            review_file = review_dir / f"review_{batch_name}.json"
            
            # Save clean enriched data
            if enriched_products:
                with open(enriched_file, 'w', encoding='utf-8') as f:
                    json.dump(enriched_products, f, indent=2, ensure_ascii=False)
            
            # Save products that need review
            if needs_review:
                with open(review_file, 'w', encoding='utf-8') as f:
                    json.dump(needs_review, f, indent=2, ensure_ascii=False)
                    
                # Create actionable review report
                self._create_review_report(needs_review, review_dir / f"review_actions_{batch_name}.json")
            
            # Create summary report
            processing_time = time.time() - batch_start_time
            summary = {
                "batch_info": {
                    "input_file": input_file,
                    "output_file": str(enriched_file),
                    "processing_timestamp": datetime.now().isoformat(),
                    "processing_time_seconds": round(processing_time, 2)
                },
                "processing_stats": {
                    "total_products": len(products),
                    "successful_enrichments": len(enriched_products),
                    "products_needing_review": len(needs_review),
                    "failed_enrichments": len(errors),
                    "success_rate": round(len(enriched_products) / len(products) * 100, 2),
                    "review_rate": round(len(needs_review) / len(products) * 100, 2)
                },
                "enrichment_summary": {
                    "databases_used": len(self.databases),
                    "average_processing_time": round(processing_time / len(products), 3)
                },
                "output_files": {
                    "enriched_data": str(enriched_file) if enriched_products else None,
                    "review_data": str(review_file) if needs_review else None,
                    "review_actions": str(review_dir / f"review_actions_{batch_name}.json") if needs_review else None
                },
                "errors": errors
            }
            
            # Save summary
            summary_file = Path(output_dir).parent / "reports" / f"enrichment_summary_{batch_name}.json"
            summary_file.parent.mkdir(exist_ok=True)
            
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Batch processing complete: {summary['processing_stats']['success_rate']}% success rate")
            return summary
            
        except Exception as e:
            logger.error(f"Failed to process batch {input_file}: {e}")
            raise

def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="DSLD Supplement Data Enrichment System")
    parser.add_argument('input_path', help='Path to cleaned JSON file or directory')
    parser.add_argument('output_base', help='Base output directory')
    parser.add_argument('--config', default='config/enrichment_config.json', help='Config file path')
    parser.add_argument('--workers', type=int, default=4, help='Number of worker threads')
    
    args = parser.parse_args()
    
    # Initialize enricher
    enricher = SupplementEnricher(args.config)
    enricher.stats['processing_start_time'] = time.time()
    
    # Determine input files
    input_path = Path(args.input_path)
    if input_path.is_file():
        input_files = [input_path]
    elif input_path.is_dir():
        input_files = list(input_path.glob('cleaned_batch_*.json'))
    else:
        logger.error(f"Input path not found: {input_path}")
        return
    
    logger.info(f"Found {len(input_files)} files to process")
    
    # Create base output directory
    base_output = Path(args.output_base)
    base_output.mkdir(parents=True, exist_ok=True)
    
    # Process files
    summaries = []
    total_start_time = time.time()
    
    for input_file in sorted(input_files):
        logger.info(f"Processing file: {input_file}")
        try:
            summary = enricher.process_batch(str(input_file), str(base_output))
            summaries.append(summary)
        except Exception as e:
            logger.error(f"Failed to process {input_file}: {e}")
    
    # Create final summary
    total_time = time.time() - total_start_time
    final_summary = {
        "overall_processing": {
            "total_files_processed": len(summaries),
            "total_processing_time_seconds": round(total_time, 2),
            "processing_timestamp": datetime.now().isoformat(),
            "enrichment_version": enricher.config['enrichment_info']['version']
        },
        "aggregate_stats": {
            "total_products_processed": enricher.stats['total_processed'],
            "successful_enrichments": enricher.stats['successful_enrichments'],
            "failed_enrichments": enricher.stats['failed_enrichments'],
            "overall_success_rate": round(enricher.stats['successful_enrichments'] / enricher.stats['total_processed'] * 100, 2) if enricher.stats['total_processed'] > 0 else 0
        },
        "database_info": {
            "databases_loaded": enricher.stats['total_databases_loaded'],
            "database_list": list(enricher.databases.keys())
        },
        "batch_summaries": summaries
    }
    
    # Save final summary
    reports_dir = base_output / "reports"
    reports_dir.mkdir(exist_ok=True)
    final_summary_file = reports_dir / f"enrichment_final_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(final_summary_file, 'w', encoding='utf-8') as f:
        json.dump(final_summary, f, indent=2, ensure_ascii=False)
    
    logger.info("="*50)
    logger.info("ENRICHMENT PROCESSING COMPLETE")
    logger.info(f"Total products processed: {enricher.stats['total_processed']}")
    logger.info(f"Success rate: {final_summary['aggregate_stats']['overall_success_rate']}%")
    logger.info(f"Total processing time: {total_time:.2f} seconds")
    logger.info(f"Final summary saved: {final_summary_file}")
    logger.info("="*50)

if __name__ == "__main__":
    main()