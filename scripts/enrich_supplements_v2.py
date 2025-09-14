#!/usr/bin/env python3
"""
DSLD Supplement Enrichment System v2.0.0
Streamlined enrichment focused on scoring preparation
"""

import json
import os
import sys
import logging
import argparse
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import traceback
from fuzzywuzzy import fuzz

class SupplementEnricherV2:
    def __init__(self, config_path: str = "config/enrichment_config.json"):
        """Initialize enrichment system with configuration"""
        self.databases = {}
        self.ingredient_registry = set()  # For deduplication
        self._setup_logging()
        self.config = self._load_config(config_path)
        self._compile_patterns()
        self._load_all_databases()
        
    def _setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)

    def _load_config(self, config_path: str) -> Dict:
        """Load enrichment configuration"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            self.logger.info(f"Configuration loaded from {config_path}")
            return config
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            raise

    def _load_all_databases(self):
        """Load all reference databases"""
        db_paths = self.config['database_paths']
        
        for db_name, db_path in db_paths.items():
            try:
                if os.path.exists(db_path):
                    with open(db_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.databases[db_name] = data
                        self.logger.info(f"Loaded {db_name}: {len(data)} entries")
                else:
                    self.databases[db_name] = []
                    self.logger.info(f"Loaded {db_name}: 0 entries")
            except Exception as e:
                self.logger.warning(f"Failed to load {db_name}: {e}")
                self.databases[db_name] = []
        
        self.logger.info(f"Enrichment system initialized with {len(self.databases)} databases")
        
    def _compile_patterns(self):
        """Compile regex patterns for performance"""
        self.compiled_patterns = {
            'physician': re.compile(r'\b(doctor|physician|md)[-\s]?formulated\b', re.I),
            'usa_made': re.compile(r'\b(made|manufactured)\s+in\s+(the\s+)?usa\b', re.I),
            'eu_made': re.compile(r'\b(made|manufactured)\s+in\s+(the\s+)?(eu|europe|european\s+union)\b', re.I),
            'organic': re.compile(r'\b(certified\s+)?organic\b', re.I),
            'non_gmo': re.compile(r'\b(non[-\s]?gmo|gmo[-\s]?free)\b', re.I),
            'third_party': re.compile(r'\bthird[-\s]?party\s+tested\b', re.I),
            'sustainability': re.compile(r'\b(sustainable|eco[-\s]?friendly|carbon[-\s]?neutral)\b', re.I),
            'negation': re.compile(r'\b(no|zero|free\s+of|does\s+not\s+contain|without)\s+', re.I),
            'proprietary': re.compile(r'\bproprietary\s+(blend|formula|complex)\b', re.I),
            'unsubstantiated': re.compile(r'\b(cure|treat|prevent|heal|miracle|magical|instant)\b', re.I)
        }

    def _check_negation_context(self, text: str, allergen_name: str, aliases: List[str]) -> bool:
        """Check if allergen mention is in a negation context (NO X, free from X, etc.)"""
        if not text:
            return False
            
        text_lower = text.lower()
        allergen_lower = allergen_name.lower()
        
        # Build search terms including aliases
        search_terms = [allergen_lower] + [alias.lower() for alias in aliases]
        
        # Negation patterns
        negation_patterns = [
            r'\bno\s+', r'\bfree\s+from\s+', r'\bfree\s+of\s+', 
            r'\bwithout\s+', r'\bdoes\s+not\s+contain\s+', r'\bcontains\s+no\s+',
            r'\b0\s*%\s+', r'\bzero\s+', r'\bnon[- ]?'
        ]
        
        for term in search_terms:
            for pattern in negation_patterns:
                negation_regex = pattern + r'.*?' + re.escape(term)
                if re.search(negation_regex, text_lower):
                    return True
        
        return False

    def _exact_ingredient_match(self, ingredient_name: str, target_name: str, aliases: List[str]) -> bool:
        """Perform exact matching for ingredients - no fuzzy matching for accuracy"""
        if not ingredient_name or not target_name:
            return False
            
        ingredient_clean = re.sub(r'[^a-zA-Z0-9\s]', '', ingredient_name.lower()).strip()
        target_clean = re.sub(r'[^a-zA-Z0-9\s]', '', target_name.lower()).strip()
        
        # 1. Exact match
        if ingredient_clean == target_clean:
            return True
            
        # 2. Check aliases
        for alias in aliases:
            alias_clean = re.sub(r'[^a-zA-Z0-9\s]', '', alias.lower()).strip()
            if ingredient_clean == alias_clean:
                return True
                
        # 3. Whole word matching
        ingredient_words = set(ingredient_clean.split())
        target_words = set(target_clean.split())
        if ingredient_words == target_words:
            return True
            
        return False

    def _is_brand_specific_study(self, study_name: str) -> bool:
        """Check if study is brand-specific using data-driven approach"""
        if not study_name:
            return False
            
        # 1. Check if ID starts with "BRAND_"
        if "BRAND_" in study_name.upper():
            return True
            
        # 2. Study names that contain multiple capital letters (likely brand names)
        # This catches brands like "KSM-66", "BCM-95", etc. without hard-coding them
        import re
        if re.search(r'[A-Z]{2,}[-\d]*', study_name):
            return True
            
        # 3. Check for proprietary naming patterns
        proprietary_patterns = [
            r'\b[A-Z][a-z]*-\d+\b',  # Like "KSM-66", "BCM-95"
            r'\b[A-Z]{3,}\b',        # Like "MERIVA", "SETRIA"
            r'\®|\™',                # Trademark symbols
        ]
        
        for pattern in proprietary_patterns:
            if re.search(pattern, study_name):
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
        
        # Extract brand from study name
        if "brand_" in study_name_lower:
            brand_part = study_name_lower.replace("brand_", "")
            brand_names.append(brand_part)
            
        # Add aliases as potential brand names
        brand_names.extend([alias.lower() for alias in study_aliases])
        
        # Check if any brand name appears in ingredient text
        for brand in brand_names:
            if brand in ingredient_lower:
                return True
                
        return False

    def enrich_product(self, product_data: Dict) -> Tuple[Dict, List[str]]:
        """Enrich a single product with v2.0.0 format"""
        try:
            self.ingredient_registry.clear()  # Reset for each product
            
            # Initialize enriched structure
            enriched = {
                "id": product_data.get("id", ""),
                "enrichment_version": "2.0.0",
                "compatible_scoring_versions": ["2.1.0", "2.1.1"],
                "enriched_date": datetime.utcnow().isoformat() + "Z",
                "form_quality_mapping": [],
                "ingredient_quality_analysis": {},
                "absorption_enhancers": {"present": False, "enhancers": [], "enhanced_nutrients": [], "enhancement_points": 0},
                "organic_certification": {"claimed": False, "claim_text": "", "usda_verified": False, "certification_points": 0},
                "standardized_botanicals": {"present": False, "botanicals": [], "standardization_points": 0},
                "enhanced_delivery": {"present": False, "delivery_systems": [], "delivery_points": 0},
                "synergy_analysis": {"detected_clusters": [], "total_synergy_points": 0},
                "contaminant_analysis": {
                    "banned_substances": {"found": False, "substances": [], "severity_deductions": 0},
                    "harmful_additives": {"found": False, "additives": [], "total_deduction": 0, "capped_deduction": 0},
                    "allergen_analysis": {"found": False, "allergens": [], "total_deduction": 0, "capped_deduction": 0},
                    "final_contaminant_score": 15.0
                },
                "allergen_compliance": {
                    "claims": {},
                    "verified": False,
                    "compliance_points": 0,
                    "gluten_free_points": 0,
                    "vegan_vegetarian_points": 0
                },
                "certification_analysis": {
                    "third_party": {"certifications": [], "certification_count": 0, "certification_points": 0},
                    "gmp": {"claimed": False, "text_found": "", "verified": False, "gmp_points": 0},
                    "batch_traceability": {"has_coa": False, "has_qr_code": False, "has_batch_lookup": False, "code_found": "", "traceability_points": 0}
                },
                "proprietary_blend_analysis": {"has_proprietary": False, "blends": [], "disclosure_level": "full", "transparency_penalty": 0},
                "clinical_evidence_matches": [],
                "unsubstantiated_claims": {"found": False, "claims": [], "flagged_terms": [], "penalty": 0},
                "manufacturer_analysis": {
                    "company": product_data.get("brandName", ""),
                    "parent_company": "",
                    "in_top_manufacturers": False,
                    "reputation_points": 0,
                    "fda_violations": {"recalls": [], "warning_letters": [], "adverse_events": [], "total_penalty": 0, "last_checked": None}
                },
                "disclosure_quality": {"all_ingredients_listed": True, "no_vague_terms": True, "vague_terms_found": [], "disclosure_points": 2},
                "bonus_features": {"physician_formulated": False, "made_in_usa_eu": False, "made_in_text": "", "sustainability": False, "sustainability_text": "", "bonus_points": 0},
                "scoring_precalculations": {
                    "section_a": {"a1_bioavailability": 0, "a2_absorption": 0, "a3_organic": 0, "a3_standardized": 0, "a3_premium_forms": 0, "a3_enhanced_delivery": 0, "a3_synergy": 0, "a3_subtotal": 0, "total": 0, "capped": 0},
                    "section_b": {"b1_contaminant_base": 15, "b1_banned_deduction": 0, "b1_harmful_deduction": 0, "b1_allergen_deduction": 0, "b1_subtotal": 15, "b2_allergen_compliance": 0, "b3_third_party": 0, "b3_gmp": 0, "b3_traceability": 0, "b3_subtotal": 0, "b4_transparency": 0, "total": 15},
                    "section_c": {"evidence": 0, "claims_penalty": 0, "total": 0},
                    "section_d": {"manufacturer": 0, "disclosure": 2, "physician_formulated": 0, "made_usa_eu": 0, "sustainability": 0, "bonuses_subtotal": 0, "total": 2},
                    "base_score_total": 17, "base_score_max": 80
                },
                "rda_ul_references": {},
                "quality_flags": {
                    "has_premium_forms": False, "has_natural_sources": False, "has_organic": False,
                    "has_clinical_evidence": False, "has_synergies": False, "has_harmful_additives": False,
                    "has_allergens": False, "has_certifications": False, "has_gmp": False,
                    "has_third_party": False, "is_vegan": False, "is_discontinued": False, "made_in_usa": False
                },
                "metadata": {
                    "requires_user_profile_scoring": False,
                    "max_possible_score": 80,
                    "current_base_score": 17,
                    "scoring_algorithm_version": "2.1.0",
                    "data_completeness": 100.0,
                    "missing_data": [],
                    "single_ingredient_product": False
                }
            }
            
            issues = []
            
            # Check discontinuation status
            status = product_data.get("status", "").lower()
            enriched["quality_flags"]["is_discontinued"] = status == "discontinued"
            
            # Process active ingredients
            active_ingredients = product_data.get("activeIngredients", [])
            inactive_ingredients = product_data.get("inactiveIngredients", [])
            
            if active_ingredients:
                enriched["form_quality_mapping"] = self._analyze_ingredient_quality(active_ingredients)
                enriched["ingredient_quality_analysis"] = self._calculate_quality_analysis(enriched["form_quality_mapping"])
                enriched["clinical_evidence_matches"] = self._find_clinical_evidence(active_ingredients, product_data)
                enriched["rda_ul_references"] = self._analyze_rda_ul(active_ingredients)
                enriched["absorption_enhancers"] = self._analyze_absorption_enhancers(active_ingredients + inactive_ingredients)
                enriched["enhanced_delivery"] = self._analyze_enhanced_delivery(active_ingredients, product_data)
                enriched["synergy_analysis"] = self._analyze_synergies(active_ingredients)
                enriched["standardized_botanicals"] = self._analyze_standardized_botanicals(active_ingredients, product_data)
                enriched["organic_certification"] = self._analyze_organic_certification(product_data)
                enriched["proprietary_blend_analysis"] = self._analyze_proprietary_blends(active_ingredients, product_data)
                enriched["unsubstantiated_claims"] = self._detect_unsubstantiated_claims(product_data)
                enriched["bonus_features"] = self._detect_bonus_features(product_data)
                
            # Process inactive ingredients for contaminants
            inactive_ingredients = product_data.get("inactiveIngredients", [])
            enriched["contaminant_analysis"] = self._analyze_contaminants(active_ingredients + inactive_ingredients, product_data)
            
            # Analyze certifications and compliance
            enriched["allergen_compliance"] = self._analyze_allergen_compliance(product_data, enriched["contaminant_analysis"])
            enriched["certification_analysis"] = self._analyze_certifications(product_data)
            
            # Analyze manufacturer
            enriched["manufacturer_analysis"] = self._analyze_manufacturer(product_data)
            
            # Set quality flags
            enriched["quality_flags"] = self._set_quality_flags(enriched, product_data)
            
            # Set metadata
            enriched["metadata"] = self._calculate_metadata(enriched, product_data)
            
            # Calculate precalculations for scoring
            enriched["scoring_precalculations"] = self._calculate_scoring_precalculations(enriched)
            
            return enriched, issues
            
        except Exception as e:
            self.logger.error(f"Error enriching product {product_data.get('id', 'unknown')}: {e}")
            self.logger.error(traceback.format_exc())
            return None, [f"Enrichment failed: {str(e)}"]

    def _analyze_ingredient_quality(self, ingredients: List[Dict]) -> List[Dict]:
        """Analyze ingredient quality and forms with exact matching - Fixed to use reference data correctly"""
        quality_mapping = []
        quality_map = self.databases.get('ingredient_quality_map', {})
        
        for ingredient in ingredients:
            ingredient_name = ingredient.get('name', '')  # Keep exact name from label
            quantity = ingredient.get('quantity', 0)
            unit = ingredient.get('unit', '')
            
            # Find quality match with proper hierarchy handling
            matched_parent = None
            matched_form = None  
            detected_form = "standard"
            parent_key = ""
            
            # PHASE 1: Search all forms across all parent entries first (more specific)
            form_found = False
            for parent_key, parent_data in quality_map.items():
                forms_dict = parent_data.get('forms', {})
                for form_key, form_data in forms_dict.items():
                    # Check if ingredient matches this specific form
                    form_aliases = form_data.get('aliases', [])
                    if self._exact_ingredient_match(ingredient_name, form_key, form_aliases):
                        matched_parent = parent_data
                        matched_form = form_data  
                        detected_form = form_key
                        form_found = True
                        break
                if form_found:
                    break
            
            # PHASE 2: If no form match, try parent-level matches
            if not form_found:
                for parent_key, parent_data in quality_map.items():
                    parent_aliases = parent_data.get('aliases', [])
                    parent_standard_name = parent_data.get('standard_name', '')
                    if self._exact_ingredient_match(ingredient_name, parent_standard_name, parent_aliases):
                        matched_parent = parent_data
                        # Use a default/standard form if available
                        forms_dict = parent_data.get('forms', {})
                        if forms_dict:
                            # Look for a "standard" form or use first form
                            for form_key in forms_dict.keys():
                                if 'standard' in form_key.lower():
                                    matched_form = forms_dict[form_key]
                                    detected_form = form_key
                                    break
                            if not matched_form:  # Use first form if no standard found
                                detected_form = list(forms_dict.keys())[0]
                                matched_form = forms_dict[detected_form]
                        break
            
            if matched_parent and matched_form:
                # Extract data from matched form
                bio_score = matched_form.get('bio_score', 5)
                is_natural = matched_form.get('natural', False)
                natural_bonus = 3 if is_natural else 0
                total_form_score = bio_score + natural_bonus
                
                # Use parent category and standard_name (from reference data, not cleaned data)
                reference_category = matched_parent.get('category', 'other')
                reference_standard_name = matched_parent.get('standard_name', ingredient_name)
                category_weight = self._get_category_weight(reference_category)
                dosage_importance = matched_form.get('dosage_importance', 1.0)
                
                weighted_score = total_form_score * dosage_importance
                
                # Log successful mapping for validation
                self.logger.debug(f"Mapped '{ingredient_name}' -> '{detected_form}' (parent: {parent_key})")
                
                quality_mapping.append({
                    "ingredient": ingredient_name,  # Preserve exact name from label
                    "standard_name": reference_standard_name,  # From reference data
                    "detected_form": detected_form,  # Exact form key that matched
                    "bio_score": bio_score,
                    "natural": is_natural,
                    "natural_bonus": natural_bonus,
                    "total_form_score": total_form_score,
                    "category": reference_category,  # From reference data
                    "category_weight": category_weight,
                    "dosage_importance": dosage_importance,
                    "weighted_score": weighted_score,
                    "absorption": matched_form.get('absorption', 'moderate'),
                    "notes": matched_form.get('notes', '')
                })
            else:
                # Log unmapped ingredient for validation
                self.logger.warning(f"No mapping found for ingredient: '{ingredient_name}'")
                
                # Default values for unmapped ingredients
                quality_mapping.append({
                    "ingredient": ingredient_name,  # Preserve exact name from label
                    "standard_name": ingredient_name,  # Use ingredient name as fallback
                    "detected_form": "standard",
                    "bio_score": 5,
                    "natural": False,
                    "natural_bonus": 0,
                    "total_form_score": 5,
                    "category": "unmapped",  # Flag as unmapped, not using cleaned data category
                    "category_weight": 1.0,
                    "dosage_importance": 1.0,
                    "weighted_score": 5.0,
                    "absorption": "moderate",
                    "notes": "No reference data found - using default values"
                })
        
        return quality_mapping

    def _get_category_weight(self, category: str) -> float:
        """Get category weight for ingredient"""
        weights = {
            'vitamin': 1.0,
            'mineral': 1.0,
            'herb': 0.8,
            'amino_acid': 0.9,
            'other': 0.7
        }
        return weights.get(category.lower(), 1.0)

    def _calculate_quality_analysis(self, quality_mapping: List[Dict]) -> Dict:
        """Calculate ingredient quality analysis summary"""
        if not quality_mapping:
            return {
                "total_weighted_score": 0,
                "total_weight": 0,
                "average_score": 0,
                "premium_forms_count": 0,
                "has_super_combo_bonus": False,
                "final_a1_score": 0,
                "capped_score": 0
            }
        
        total_weighted = sum(item["weighted_score"] for item in quality_mapping)
        total_weight = sum(item["dosage_importance"] for item in quality_mapping)
        average_score = total_weighted / total_weight if total_weight > 0 else 0
        premium_forms = sum(1 for item in quality_mapping if item["bio_score"] > 11)
        
        # Cap the score at 20
        capped_score = min(average_score, 20)
        
        return {
            "total_weighted_score": round(total_weighted, 2),
            "total_weight": round(total_weight, 2),
            "average_score": round(average_score, 2),
            "premium_forms_count": premium_forms,
            "has_super_combo_bonus": premium_forms >= 3,
            "final_a1_score": round(average_score, 2),
            "capped_score": round(capped_score, 2)
        }

    def _find_clinical_evidence(self, ingredients: List[Dict], product_data: Dict) -> List[Dict]:
        """Find clinical evidence matches with brand-specific validation"""
        evidence_matches = []
        clinical_studies = self.databases.get('backed_clinical_studies', [])
        
        # Get product text for brand context
        product_text = ' '.join([
            product_data.get('fullName', ''),
            product_data.get('brandName', ''),
            str(product_data.get('targetGroups', [])),
            str([ing.get('notes', '') for ing in ingredients])
        ])
        
        for ingredient in ingredients:
            ingredient_name = ingredient.get('name', '')
            standard_name = ingredient.get('standardName', '')
            
            for study in clinical_studies:
                study_name = study.get('standard_name', '')
                study_aliases = study.get('aliases', [])
                study_id = study.get('id', '')
                
                # Check if ingredient matches study
                if self._exact_ingredient_match(standard_name, study_name, study_aliases):
                    
                    # For brand-specific studies, require explicit brand mention
                    if self._is_brand_specific_study(study_id):
                        brand_contexts = [
                            product_data.get('fullName', ''),
                            product_data.get('brandName', ''),
                            ingredient.get('notes', ''),
                            ingredient.get('formDetails', '')
                        ]
                        
                        brand_found = any(self._check_brand_match(context, study_name, study_aliases) 
                                        for context in brand_contexts)
                        if not brand_found:
                            continue  # Skip if brand not explicitly mentioned
                    
                    evidence_matches.append({
                        "ingredient": f"{ingredient_name} ({ingredient.get('formDetails', 'standard')})",
                        "evidence_id": study_id,
                        "evidence_level": study.get('evidence_level', 'ingredient-human'),
                        "score_contribution": self._get_evidence_score(study.get('score_contribution', 'tier_3')),
                        "key_endpoints": study.get('key_endpoints', [])
                    })
                    break  # Only match one study per ingredient
        
        return evidence_matches

    def _get_evidence_score(self, tier: str) -> int:
        """Convert evidence tier to score"""
        scores = {
            'tier_1': 10,
            'tier_2': 7,
            'tier_3': 5
        }
        return scores.get(tier, 3)

    def _analyze_absorption_enhancers(self, all_ingredients: List[Dict]) -> Dict:
        """Check for absorption enhancers"""
        enhancers_db = self.databases.get('absorption_enhancers', [])
        found_enhancers = []
        enhanced_nutrients = []
        
        for ingredient in all_ingredients:
            ingredient_name = ingredient.get('name', '')
            
            for enhancer in enhancers_db:
                if self._exact_ingredient_match(ingredient_name, enhancer.get('standard_name', ''), enhancer.get('aliases', [])):
                    # Find what nutrients this enhancer affects
                    enhanced_list = enhancer.get('enhanced_nutrients', [])
                    
                    # Check if any of the enhanced nutrients are present in the product
                    for enhanced_nutrient in enhanced_list:
                        for product_ingredient in all_ingredients:
                            # Check both standard name and ingredient name with partial matching
                            ingredient_std_name = product_ingredient.get('standardName', '').lower()
                            ingredient_name_lower = product_ingredient.get('name', '').lower()
                            enhanced_nutrient_lower = enhanced_nutrient.lower()
                            
                            # More flexible matching for enhanced nutrients
                            if (enhanced_nutrient_lower in ingredient_std_name or 
                                enhanced_nutrient_lower in ingredient_name_lower or
                                ingredient_std_name in enhanced_nutrient_lower or
                                self._exact_ingredient_match(ingredient_std_name, enhanced_nutrient, [])):
                                if enhanced_nutrient not in enhanced_nutrients:
                                    enhanced_nutrients.append(enhanced_nutrient)
                    
                    found_enhancers.append({
                        "name": ingredient_name,
                        "enhancer_id": enhancer.get('id', ''),
                        "enhanced_nutrients": enhancer.get('enhanced_nutrients', []),
                        "enhancement_factor": enhancer.get('enhancement_factor', 1.0)
                    })
        
        enhancement_points = 3 if found_enhancers and enhanced_nutrients else 0
        
        return {
            "present": len(found_enhancers) > 0,
            "enhancers": found_enhancers,
            "enhanced_nutrients": enhanced_nutrients,
            "enhancement_points": enhancement_points
        }

    def _analyze_enhanced_delivery(self, ingredients: List[Dict], product_data: Dict) -> Dict:
        """Check for enhanced delivery systems"""
        delivery_db = self.databases.get('enhanced_delivery', {})
        delivery_systems = []
        
        # Check both ingredients and product text
        product_text = ' '.join([
            product_data.get('fullName', ''),
            product_data.get('labelText', ''),
            ' '.join([ing.get('notes', '') or '' for ing in ingredients])
        ]).lower()
        
        for delivery_name, delivery_data in delivery_db.items():
            if isinstance(delivery_data, dict):
                delivery_name_lower = delivery_name.lower()
                
                # Check if delivery system is mentioned in product text
                if delivery_name_lower in product_text:
                    delivery_systems.append({
                        "name": delivery_name,
                        "delivery_id": delivery_name.upper(),
                        "delivery_type": delivery_data.get('category', 'delivery'),
                        "points": delivery_data.get('points', 4)
                    })
        
        total_points = sum(system.get('points', 4) for system in delivery_systems)
        
        return {
            "present": len(delivery_systems) > 0,
            "delivery_systems": delivery_systems,
            "delivery_points": total_points
        }

    def _analyze_synergies(self, ingredients: List[Dict]) -> Dict:
        """Detect synergy clusters with dosage validation"""
        synergy_db = self.databases.get('synergy_cluster', {})
        synergy_clusters = synergy_db.get('synergy_clusters', [])
        detected_clusters = []
        
        for cluster in synergy_clusters:
            cluster_ingredients = cluster.get('ingredients', [])
            matched_ingredients = []
            
            # Check if at least 2 ingredients from the cluster are present
            # cluster_ingredients is a list of strings, not objects
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
                    "cluster_name": cluster.get('name', ''),
                    "cluster_id": cluster.get('id', ''),
                    "matched_ingredients": matched_ingredients,
                    "synergy_points": points,
                    "all_doses_adequate": all_meet_dose
                })
        
        total_points = sum(cluster.get('synergy_points', 0) for cluster in detected_clusters)
        
        return {
            "detected_clusters": detected_clusters,
            "total_synergy_points": total_points
        }

    def _analyze_standardized_botanicals(self, ingredients: List[Dict], product_data: Dict) -> Dict:
        """Check for standardized botanicals with percentage extraction"""
        botanicals_db = self.databases.get('standardized_botanicals', {})
        botanicals_list = botanicals_db.get('standardized_botanicals', [])
        standardized_botanicals = []
        
        # Get label text for percentage extraction
        label_text = product_data.get('labelText', '')
        
        for ingredient in ingredients:
            ingredient_name = ingredient.get('name', '')
            notes = ingredient.get('notes', '') or ''
            
            for botanical in botanicals_list:
                if self._exact_ingredient_match(ingredient_name, botanical.get('standard_name', ''), botanical.get('aliases', [])):
                    # Extract standardization percentage from notes or label text
                    percentage = self._extract_standardization_percentage(notes + ' ' + label_text, botanical.get('markers', []))
                    
                    points = 0
                    # Handle different min_standardization formats (0.97 vs 97)
                    min_threshold = botanical.get('min_standardization', 1.0)
                    if min_threshold > 1:  # If stored as 97 instead of 0.97
                        min_threshold = min_threshold / 100
                    
                    if percentage >= min_threshold:
                        points = 2  # Standardized to +2 per scoring doc
                    
                    standardized_botanicals.append({
                        "ingredient": ingredient_name,
                        "botanical_id": botanical.get('id', ''),
                        "standardization_percentage": percentage,
                        "marker_compounds": botanical.get('markers', []),
                        "points": points
                    })
        
        total_points = sum(bot.get('points', 0) for bot in standardized_botanicals)
        
        return {
            "present": len(standardized_botanicals) > 0,
            "botanicals": standardized_botanicals,
            "standardization_points": total_points
        }

    def _extract_standardization_percentage(self, text: str, marker_compounds: List[str]) -> float:
        """Extract standardization percentage from text"""
        if not text:
            return 0.0
        
        text_lower = text.lower()
        
        # Look for patterns like "standardized to 20%" or "20% saponins"
        for compound in marker_compounds:
            compound_lower = compound.lower()
            
            # Pattern: "standardized to X% compound" or "X% compound"
            patterns = [
                rf'standardized\s+to\s+(\d+(?:\.\d+)?)\s*%\s*{re.escape(compound_lower)}',
                rf'(\d+(?:\.\d+)?)\s*%\s*{re.escape(compound_lower)}',
                rf'{re.escape(compound_lower)}\s*(\d+(?:\.\d+)?)\s*%',
                rf'contains?\s+(\d+(?:\.\d+)?)\s*%\s*{re.escape(compound_lower)}'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    return float(match.group(1))
        
        # General standardization patterns
        general_patterns = [
            r'standardized\s+to\s+(\d+(?:\.\d+)?)\s*%',
            r'(\d+(?:\.\d+)?)\s*%\s*standardized',
            r'extract\s+(\d+(?:\.\d+)?)\s*%'
        ]
        
        for pattern in general_patterns:
            match = re.search(pattern, text_lower)
            if match:
                return float(match.group(1))
        
        return 0.0

    def _analyze_organic_certification(self, product_data: Dict) -> Dict:
        """Analyze organic certification claims"""
        target_groups = product_data.get('targetGroups', [])
        label_text = product_data.get('labelText', '')
        
        # Check for organic claims
        organic_claimed = False
        usda_verified = False
        claim_text = ""
        
        # Check target groups
        for group in target_groups:
            group_lower = group.lower()
            if 'organic' in group_lower:
                organic_claimed = True
                if 'usda' in group_lower:
                    usda_verified = True
                    claim_text = group
                break
        
        # Check label text if not found in target groups
        if not organic_claimed and label_text:
            organic_patterns = [
                r'\b(usda\s+)?organic\b',
                r'\bcertified\s+organic\b',
                r'\b100\s*%\s*organic\b'
            ]
            
            for pattern in organic_patterns:
                match = re.search(pattern, label_text.lower())
                if match:
                    organic_claimed = True
                    claim_text = match.group(0)
                    if 'usda' in claim_text:
                        usda_verified = True
                    break
        
        # Calculate points
        points = 0
        if organic_claimed:
            points = 3 if usda_verified else 2
        
        return {
            "claimed": organic_claimed,
            "claim_text": claim_text,
            "usda_verified": usda_verified,
            "certification_points": points
        }

    def _analyze_proprietary_blends(self, ingredients: List[Dict], product_data: Dict) -> Dict:
        """Analyze proprietary blend disclosure"""
        proprietary_db = self.databases.get('proprietary_blends_penalty', {})
        penalty_rules = proprietary_db.get('penalty_rules', [])
        
        blends = []
        has_proprietary = False
        transparency_penalty = 0
        
        for ingredient in ingredients:
            if ingredient.get('proprietaryBlend', False) or ingredient.get('isProprietaryBlend', False):
                has_proprietary = True
                
                # Check disclosure level
                disclosure_level = ingredient.get('disclosureLevel', 'none')
                quantity = ingredient.get('quantity', 0)
                
                # Apply penalties based on disclosure level
                for rule in penalty_rules:
                    if rule.get('disclosure_level') == disclosure_level:
                        transparency_penalty += rule.get('penalty', 0)
                
                blends.append({
                    "name": ingredient.get('name', ''),
                    "disclosure_level": disclosure_level,
                    "has_individual_amounts": quantity > 0,
                    "total_amount": quantity,
                    "unit": ingredient.get('unit', '')
                })
        
        # Determine overall disclosure level
        if not has_proprietary:
            overall_disclosure = "full"
        elif all(blend.get('has_individual_amounts', False) for blend in blends):
            overall_disclosure = "full"
        elif any(blend.get('disclosure_level') == 'partial' for blend in blends):
            overall_disclosure = "partial"
        else:
            overall_disclosure = "none"
        
        return {
            "has_proprietary": has_proprietary,
            "blends": blends,
            "disclosure_level": overall_disclosure,
            "transparency_penalty": transparency_penalty
        }

    def _detect_unsubstantiated_claims(self, product_data: Dict) -> Dict:
        """Detect egregious marketing claims"""
        label_text = product_data.get('labelText', '')
        product_name = product_data.get('fullName', '')
        claims = product_data.get('claims', [])
        
        # Combine all text for analysis
        all_text = ' '.join([product_name, label_text, str(claims)]).lower()
        
        flagged_claims = []
        flagged_terms = []
        
        # Egregious claim patterns
        egregious_patterns = [
            (r'\b(treats?|cures?|prevents?|heals?|eliminates?|reverses?)\s+(cancer|diabetes|alzheimer|arthritis|covid|hypertension|depression|anxiety)\b', 'disease_treatment', -10),
            (r'\b(fda\s+approved|approved\s+by\s+the\s+fda)\b', 'false_fda_approval', -15),
            (r'\b(instant|guaranteed|miracle|100\s*%\s*cure|magic)\b', 'unrealistic_promises', -5),
            (r'\b(lose\s+\d+\s+pounds?\s+in\s+\d+\s+days?|overnight\s+weight\s+loss)\b', 'unrealistic_weight_loss', -8),
            (r'\b(fountain\s+of\s+youth|anti[-\s]?aging\s+miracle|reverse\s+aging)\b', 'anti_aging_exaggeration', -6),
            (r'\b(scientifically\s+proven)\b(?!.*\bstudies?\b)', 'false_science_claims', -4)
        ]
        
        total_penalty = 0
        
        for pattern, claim_type, penalty in egregious_patterns:
            matches = re.findall(pattern, all_text)
            if matches:
                for match in matches:
                    flagged_term = match if isinstance(match, str) else ' '.join(match)
                    flagged_terms.append(flagged_term)
                    flagged_claims.append({
                        "claim_type": claim_type,
                        "flagged_text": flagged_term,
                        "penalty": penalty
                    })
                    total_penalty += penalty
        
        return {
            "found": len(flagged_claims) > 0,
            "claims": flagged_claims,
            "flagged_terms": list(set(flagged_terms)),
            "penalty": total_penalty
        }

    def _detect_bonus_features(self, product_data: Dict) -> Dict:
        """Detect physician-formulated, made in USA/EU, sustainability"""
        label_text = product_data.get('labelText', '')
        target_groups = product_data.get('targetGroups', [])
        
        # Combine text for analysis
        all_text = ' '.join([
            product_data.get('fullName', ''),
            label_text,
            ' '.join(target_groups)
        ]).lower()
        
        # Pre-compile regex patterns for better performance
        patterns = {
            'physician_formulated': [
                r'\b(doctor|physician|md)[-\s]?formulated\b',
                r'\bformulated\s+by\s+(doctor|physician|dr\.)\b',
                r'\b(physician|doctor)[-\s]?designed\b'
            ],
            'made_usa_eu': [
                r'\b(made|manufactured|produced)\s+in\s+(the\s+)?usa\b',
                r'\b(made|manufactured)\s+in\s+(america|united\s+states)\b',
                r'\b(made|manufactured)\s+in\s+(eu|european\s+union|germany|france|italy|netherlands)\b',
                r'\bmanufactured\s+in\s+fda[-\s]?approved\s+facility\b'
            ],
            'sustainability': [
                r'\b(recyclable|biodegradable|eco[-\s]?friendly|sustainable)\b',
                r'\bglass\s+bottle\b',
                r'\bplease\s+recycle\b',
                r'\bcarbon[-\s]?neutral\b',
                r'\benvironmentally\s+responsible\b'
            ]
        }
        
        # Detection results
        physician_formulated = False
        made_in_usa_eu = False
        made_in_text = ""
        sustainability = False
        sustainability_text = ""
        
        # Check physician formulated
        for pattern in patterns['physician_formulated']:
            match = re.search(pattern, all_text)
            if match:
                physician_formulated = True
                break
        
        # Check made in USA/EU
        for pattern in patterns['made_usa_eu']:
            match = re.search(pattern, all_text)
            if match:
                made_in_usa_eu = True
                made_in_text = match.group(0)
                break
        
        # Check sustainability
        for pattern in patterns['sustainability']:
            match = re.search(pattern, all_text)
            if match:
                sustainability = True
                sustainability_text = match.group(0)
                break
        
        # Calculate bonus points
        bonus_points = 0
        if physician_formulated:
            bonus_points += 1
        if made_in_usa_eu:
            bonus_points += 1
        if sustainability:
            bonus_points += 1
        
        return {
            "physician_formulated": physician_formulated,
            "made_in_usa_eu": made_in_usa_eu,
            "made_in_text": made_in_text,
            "sustainability": sustainability,
            "sustainability_text": sustainability_text,
            "bonus_points": bonus_points
        }

    def _analyze_rda_ul(self, ingredients: List[Dict]) -> Dict:
        """Analyze RDA/UL references for ingredients"""
        rda_data = self.databases.get('rda_optimal_uls', {})
        recommendations = rda_data.get('nutrient_recommendations', [])
        references = {}
        
        for ingredient in ingredients:
            standard_name = ingredient.get('standardName', '')
            quantity = ingredient.get('quantity', 0)
            unit = ingredient.get('unit', '')
            
            for rda_item in recommendations:
                if self._exact_ingredient_match(standard_name, rda_item.get('standard_name', ''), rda_item.get('aliases', [])):
                    # Get adult male/female RDA values (19-30 age group)
                    data = rda_item.get('data', [])
                    rda_adult_male = 0
                    rda_adult_female = 0
                    ul_value = None
                    
                    for data_point in data:
                        if data_point.get('group') == 'Male' and data_point.get('age_range') == '19-30':
                            rda_adult_male = data_point.get('rda_ai', 0)
                            ul_value = data_point.get('ul')
                        elif data_point.get('group') == 'Female' and data_point.get('age_range') == '19-30':
                            rda_adult_female = data_point.get('rda_ai', 0)
                    
                    # Calculate percentage RDA (using higher of male/female)
                    rda_reference = max(rda_adult_male, rda_adult_female)
                    percent_rda = (quantity / rda_reference * 100) if rda_reference > 0 else 0
                    
                    references[standard_name.replace(' ', '_').lower()] = {
                        "rda_adult_male": rda_adult_male,
                        "rda_adult_female": rda_adult_female,
                        "ul": ul_value,
                        "optimal_range": rda_item.get('optimal_range', ''),
                        "therapeutic_range": rda_item.get('therapeutic_range', ''),
                        "unit": unit,
                        "product_amount": quantity,
                        "percent_rda": round(percent_rda) if percent_rda else 0
                    }
                    break
        
        return references

    def _analyze_contaminants(self, all_ingredients: List[Dict], product_data: Dict) -> Dict:
        """Analyze contaminants with negation detection"""
        contaminant_analysis = {
            "banned_substances": {"found": False, "substances": [], "severity_deductions": 0},
            "harmful_additives": {"found": False, "additives": [], "total_deduction": 0, "capped_deduction": 0},
            "allergen_analysis": {"found": False, "allergens": [], "total_deduction": 0, "capped_deduction": 0},
            "final_contaminant_score": 15.0
        }
        
        # Get product text for negation context
        product_text = ' '.join([
            product_data.get('fullName', ''),
            str(product_data.get('targetGroups', [])),
            ' '.join([ing.get('notes', '') or '' for ing in all_ingredients])
        ])
        
        # Check banned substances
        banned_db = self.databases.get('banned_recalled_ingredients', {})
        all_banned_items = []
        for category, items in banned_db.items():
            if isinstance(items, list):
                all_banned_items.extend(items)
        
        for ingredient in all_ingredients:
            ingredient_name = ingredient.get('name', '')
            for banned_item in all_banned_items:
                if self._exact_ingredient_match(ingredient_name, banned_item.get('standard_name', ''), banned_item.get('aliases', [])):
                    severity = banned_item.get('severity', 'high')
                    deduction = self._get_banned_deduction(severity)
                    
                    contaminant_analysis["banned_substances"]["substances"].append({
                        "name": ingredient_name,
                        "banned_id": banned_item.get('id', ''),
                        "severity": severity,
                        "deduction": deduction
                    })
                    contaminant_analysis["banned_substances"]["severity_deductions"] += deduction
        
        contaminant_analysis["banned_substances"]["found"] = len(contaminant_analysis["banned_substances"]["substances"]) > 0
        
        # Check harmful additives
        harmful_db = self.databases.get('harmful_additives', {})
        harmful_items = harmful_db.get('harmful_additives', [])
        
        for ingredient in all_ingredients:
            ingredient_name = ingredient.get('name', '')
            for harmful_item in harmful_items:
                if self._exact_ingredient_match(ingredient_name, harmful_item.get('standard_name', ''), harmful_item.get('aliases', [])):
                    risk_level = harmful_item.get('risk_level', 'low')
                    deduction = self._get_harmful_deduction(risk_level)
                    
                    contaminant_analysis["harmful_additives"]["additives"].append({
                        "name": ingredient_name,
                        "risk_level": risk_level,
                        "deduction": deduction
                    })
                    contaminant_analysis["harmful_additives"]["total_deduction"] += deduction
        
        contaminant_analysis["harmful_additives"]["found"] = len(contaminant_analysis["harmful_additives"]["additives"]) > 0
        contaminant_analysis["harmful_additives"]["capped_deduction"] = max(contaminant_analysis["harmful_additives"]["total_deduction"], -10)
        
        # Check allergens with negation detection
        allergen_db = self.databases.get('allergens', {})
        allergen_items = allergen_db.get('allergens', [])
        
        for ingredient in all_ingredients:
            ingredient_name = ingredient.get('name', '')
            for allergen_item in allergen_items:
                allergen_name = allergen_item.get('standard_name', '')
                aliases = allergen_item.get('aliases', [])
                
                if self._exact_ingredient_match(ingredient_name, allergen_name, aliases):
                    # Check for negation context
                    if self._check_negation_context(product_text, allergen_name, aliases):
                        continue  # Skip if in negation context
                    
                    severity = allergen_item.get('severity_level', 'low')
                    deduction = self._get_allergen_deduction(severity)
                    
                    contaminant_analysis["allergen_analysis"]["allergens"].append({
                        "name": ingredient_name,
                        "severity": severity,
                        "deduction": deduction
                    })
                    contaminant_analysis["allergen_analysis"]["total_deduction"] += deduction
        
        contaminant_analysis["allergen_analysis"]["found"] = len(contaminant_analysis["allergen_analysis"]["allergens"]) > 0
        contaminant_analysis["allergen_analysis"]["capped_deduction"] = max(contaminant_analysis["allergen_analysis"]["total_deduction"], -5)
        
        # Calculate final contaminant score
        base_score = 15
        total_deductions = (
            contaminant_analysis["banned_substances"]["severity_deductions"] +
            contaminant_analysis["harmful_additives"]["capped_deduction"] +
            contaminant_analysis["allergen_analysis"]["capped_deduction"]
        )
        
        contaminant_analysis["final_contaminant_score"] = max(base_score + total_deductions, 0)
        
        return contaminant_analysis

    def _get_banned_deduction(self, severity: str) -> int:
        """Get deduction for banned substances"""
        deductions = {
            'critical': -50,
            'high': -20,
            'moderate': -10,
            'low': -5
        }
        return deductions.get(severity, -10)

    def _get_harmful_deduction(self, risk_level: str) -> float:
        """Get deduction for harmful additives"""
        deductions = {
            'critical': -3.0,
            'high': -2.0,
            'moderate': -1.0,
            'low': -0.5
        }
        return deductions.get(risk_level, -0.5)

    def _get_allergen_deduction(self, severity: str) -> float:
        """Get deduction for allergens"""
        deductions = {
            'critical': -3.0,
            'high': -2.0,
            'moderate': -1.5,
            'low': -1.0
        }
        return deductions.get(severity, -1.0)

    def _analyze_allergen_compliance(self, product_data: Dict, contaminant_analysis: Dict) -> Dict:
        """Analyze allergen compliance with cross-validation"""
        target_groups = product_data.get('targetGroups', [])
        detected_allergens = contaminant_analysis.get('allergen_analysis', {}).get('allergens', [])
        
        # Extract claims from target groups
        claims = {
            "dairy_free": any('dairy free' in group.lower() for group in target_groups),
            "soy_free": any('soy free' in group.lower() for group in target_groups),
            "gluten_free": any('gluten free' in group.lower() for group in target_groups),
            "egg_free": any('egg free' in group.lower() for group in target_groups),
            "shellfish_free": any('shellfish free' in group.lower() for group in target_groups),
            "yeast_free": any('yeast free' in group.lower() for group in target_groups)
        }
        
        # Check verification against detected allergens
        verified = True
        allergen_names = [allergen['name'].lower() for allergen in detected_allergens]
        
        if claims.get('dairy_free') and any('milk' in name or 'dairy' in name for name in allergen_names):
            verified = False
        if claims.get('soy_free') and any('soy' in name for name in allergen_names):
            verified = False
        if claims.get('gluten_free') and any('gluten' in name or 'wheat' in name for name in allergen_names):
            verified = False
        
        # Calculate points
        compliance_points = 2 if verified and any(claims.values()) else 0
        gluten_free_points = 1 if claims.get('gluten_free') and verified else 0
        
        vegan_vegetarian = any(group.lower() in ['vegan', 'vegetarian'] for group in target_groups)
        vegan_vegetarian_points = 1 if vegan_vegetarian and verified else 0
        
        return {
            "claims": claims,
            "verified": verified,
            "compliance_points": compliance_points,
            "gluten_free_points": gluten_free_points,
            "vegan_vegetarian_points": vegan_vegetarian_points
        }

    def _analyze_certifications(self, product_data: Dict) -> Dict:
        """Analyze certifications from product data"""
        target_groups = product_data.get('targetGroups', [])
        contacts = product_data.get('contacts', [])
        
        # Extract certifications from target groups
        certifications = []
        if any('usda organic' in group.lower() for group in target_groups):
            certifications.append("USDA Organic")
        if any('third-party tested' in group.lower() or 'third party tested' in group.lower() for group in target_groups):
            certifications.append("Third-Party-Tested")
        if any('non-gmo' in group.lower() for group in target_groups):
            certifications.append("Non-GMO")
        
        # Check GMP from contacts
        gmp_claimed = False
        gmp_verified = False
        for contact in contacts:
            if contact.get('isGMP', False):
                gmp_claimed = True
                gmp_verified = True
                break
        
        return {
            "third_party": {
                "certifications": certifications,
                "certification_count": len(certifications),
                "certification_points": len(certifications) * 5
            },
            "gmp": {
                "claimed": gmp_claimed,
                "text_found": "Good Manufacturing Practices (GMP)" if gmp_claimed else "",
                "verified": gmp_verified,
                "gmp_points": 4 if gmp_verified else 0
            },
            "batch_traceability": {
                "has_coa": False,
                "has_qr_code": False,
                "has_batch_lookup": False,
                "code_found": "",
                "traceability_points": 0
            }
        }

    def _analyze_manufacturer(self, product_data: Dict) -> Dict:
        """Analyze manufacturer reputation"""
        brand_name = product_data.get('brandName', '')
        contacts = product_data.get('contacts', [])
        
        # Check if in top manufacturers database
        top_manufacturers = self.databases.get('top_manufacturers_data', [])
        in_top = False
        reputation_points = 0
        
        for manufacturer in top_manufacturers:
            if self._exact_ingredient_match(brand_name, manufacturer.get('company_name', ''), manufacturer.get('aliases', [])):
                in_top = True
                reputation_points = manufacturer.get('reputation_score', 0)
                break
        
        # Get parent company from contacts
        parent_company = ""
        if contacts:
            parent_company = contacts[0].get('name', '')
        
        return {
            "company": brand_name,
            "parent_company": parent_company,
            "in_top_manufacturers": in_top,
            "reputation_points": reputation_points,
            "fda_violations": {
                "recalls": [],
                "warning_letters": [],
                "adverse_events": [],
                "total_penalty": 0,
                "last_checked": None
            }
        }

    def _set_quality_flags(self, enriched: Dict, product_data: Dict) -> Dict:
        """Set quality flags based on analysis"""
        flags = enriched["quality_flags"].copy()
        
        # Premium forms
        flags["has_premium_forms"] = enriched["ingredient_quality_analysis"].get("premium_forms_count", 0) > 0
        
        # Natural sources
        flags["has_natural_sources"] = any(item.get("natural", False) for item in enriched["form_quality_mapping"])
        
        # Clinical evidence
        flags["has_clinical_evidence"] = len(enriched["clinical_evidence_matches"]) > 0
        
        # Contaminants
        flags["has_harmful_additives"] = enriched["contaminant_analysis"]["harmful_additives"]["found"]
        flags["has_allergens"] = enriched["contaminant_analysis"]["allergen_analysis"]["found"]
        
        # Certifications
        flags["has_certifications"] = enriched["certification_analysis"]["third_party"]["certification_count"] > 0
        flags["has_gmp"] = enriched["certification_analysis"]["gmp"]["claimed"]
        flags["has_third_party"] = "Third-Party-Tested" in enriched["certification_analysis"]["third_party"]["certifications"]
        
        # Vegan/vegetarian
        target_groups = product_data.get('targetGroups', [])
        flags["is_vegan"] = any('vegan' in group.lower() for group in target_groups)
        
        # Made in USA
        flags["made_in_usa"] = any('usa' in group.lower() or 'united states' in group.lower() for group in target_groups)
        
        return flags

    def _calculate_metadata(self, enriched: Dict, product_data: Dict) -> Dict:
        """Calculate metadata for the enriched product"""
        active_ingredients = product_data.get('activeIngredients', [])
        ingredient_count = len(active_ingredients)
        
        # Check if single ingredient
        single_ingredient = ingredient_count == 1
        
        # Check if multivitamin (simplified check)
        is_multivitamin = ingredient_count >= 3 and any(
            'vitamin' in ing.get('category', '').lower() for ing in active_ingredients
        )
        
        # Calculate data completeness
        completeness = 100.0  # Default to 100%
        missing_data = []
        
        if not enriched["manufacturer_analysis"]["in_top_manufacturers"]:
            missing_data.append("manufacturer_verification")
            completeness -= 5
        
        if not enriched["certification_analysis"]["batch_traceability"]["code_found"]:
            missing_data.append("batch_traceability")
            completeness -= 5
        
        return {
            "requires_user_profile_scoring": ingredient_count > 1,
            "max_possible_score": 80,
            "current_base_score": enriched["scoring_precalculations"]["base_score_total"],
            "scoring_algorithm_version": "2.1.0",
            "data_completeness": completeness,
            "missing_data": missing_data,
            "single_ingredient_product": single_ingredient
        }

    def _calculate_scoring_precalculations(self, enriched: Dict) -> Dict:
        """Calculate scoring precalculations for final scoring script"""
        # Section A: Ingredient Quality
        a1_bioavailability = enriched["ingredient_quality_analysis"].get("capped_score", 0)
        a2_absorption = enriched["absorption_enhancers"]["enhancement_points"]
        a3_organic = enriched["organic_certification"]["certification_points"]
        a3_standardized = enriched["standardized_botanicals"]["standardization_points"]
        a3_premium_forms = 3 if enriched["ingredient_quality_analysis"].get("premium_forms_count", 0) >= 2 else 0
        a3_enhanced_delivery = enriched["enhanced_delivery"]["delivery_points"]
        a3_synergy = enriched["synergy_analysis"]["total_synergy_points"]
        a3_subtotal = a3_organic + a3_standardized + a3_premium_forms + a3_enhanced_delivery + a3_synergy
        
        section_a_total = a1_bioavailability + a2_absorption + a3_subtotal
        section_a_capped = min(section_a_total, 25)
        
        # Section B: Safety & Quality
        b1_base = 15
        b1_banned = enriched["contaminant_analysis"]["banned_substances"]["severity_deductions"]
        b1_harmful = enriched["contaminant_analysis"]["harmful_additives"]["capped_deduction"]
        b1_allergen = enriched["contaminant_analysis"]["allergen_analysis"]["capped_deduction"]
        b1_subtotal = max(b1_base + b1_banned + b1_harmful + b1_allergen, 0)
        
        b2_compliance = (
            enriched["allergen_compliance"]["compliance_points"] +
            enriched["allergen_compliance"]["gluten_free_points"] +
            enriched["allergen_compliance"]["vegan_vegetarian_points"]
        )
        
        b3_third_party = enriched["certification_analysis"]["third_party"]["certification_points"]
        b3_gmp = enriched["certification_analysis"]["gmp"]["gmp_points"]
        b3_traceability = enriched["certification_analysis"]["batch_traceability"]["traceability_points"]
        b3_subtotal = b3_third_party + b3_gmp + b3_traceability
        
        b4_transparency = enriched["proprietary_blend_analysis"]["transparency_penalty"]
        
        section_b_total = b1_subtotal + b2_compliance + b3_subtotal + b4_transparency
        
        # Section C: Evidence & Claims
        evidence_score = sum(match["score_contribution"] for match in enriched["clinical_evidence_matches"])
        claims_penalty = enriched["unsubstantiated_claims"]["penalty"]
        section_c_total = evidence_score + claims_penalty
        
        # Section D: Brand & Disclosure
        manufacturer_score = enriched["manufacturer_analysis"]["reputation_points"]
        disclosure_score = enriched["disclosure_quality"]["disclosure_points"]
        physician_formulated = 1 if enriched["bonus_features"]["physician_formulated"] else 0
        made_usa_eu = 1 if enriched["bonus_features"]["made_in_usa_eu"] else 0
        sustainability = 1 if enriched["bonus_features"]["sustainability"] else 0
        bonuses_subtotal = physician_formulated + made_usa_eu + sustainability
        
        section_d_total = manufacturer_score + disclosure_score + bonuses_subtotal
        
        # Base score total
        base_score_total = section_a_capped + section_b_total + section_c_total + section_d_total
        
        return {
            "section_a": {
                "a1_bioavailability": round(a1_bioavailability, 2),
                "a2_absorption": a2_absorption,
                "a3_organic": a3_organic,
                "a3_standardized": a3_standardized,
                "a3_premium_forms": a3_premium_forms,
                "a3_enhanced_delivery": a3_enhanced_delivery,
                "a3_synergy": a3_synergy,
                "a3_subtotal": a3_subtotal,
                "total": round(section_a_total, 2),
                "capped": round(section_a_capped, 2)
            },
            "section_b": {
                "b1_contaminant_base": b1_base,
                "b1_banned_deduction": b1_banned,
                "b1_harmful_deduction": b1_harmful,
                "b1_allergen_deduction": b1_allergen,
                "b1_subtotal": b1_subtotal,
                "b2_allergen_compliance": b2_compliance,
                "b3_third_party": b3_third_party,
                "b3_gmp": b3_gmp,
                "b3_traceability": b3_traceability,
                "b3_subtotal": b3_subtotal,
                "b4_transparency": b4_transparency,
                "total": section_b_total
            },
            "section_c": {
                "evidence": evidence_score,
                "claims_penalty": claims_penalty,
                "total": section_c_total
            },
            "section_d": {
                "manufacturer": manufacturer_score,
                "disclosure": disclosure_score,
                "physician_formulated": physician_formulated,
                "made_usa_eu": made_usa_eu,
                "sustainability": sustainability,
                "bonuses_subtotal": bonuses_subtotal,
                "total": section_d_total
            },
            "base_score_total": round(base_score_total, 2),
            "base_score_max": 80
        }

    def process_batch(self, input_file: str, output_dir: str) -> Dict:
        """Process a batch of products"""
        try:
            # Load input data
            with open(input_file, 'r', encoding='utf-8') as f:
                products = json.load(f)
            
            if not isinstance(products, list):
                products = [products]
            
            self.logger.info(f"Processing batch: {len(products)} products from {os.path.basename(input_file)}")
            
            enriched_products = []
            review_products = []
            
            for product in products:
                product_id = product.get('id', 'unknown')
                product_name = product.get('fullName', 'Unknown Product')
                
                self.logger.info(f"Enriching product {product_id}: {product_name}")
                
                enriched, issues = self.enrich_product(product)
                
                if enriched and not issues:
                    enriched_products.append(enriched)
                else:
                    review_products.append({
                        "product": enriched or product,
                        "issues": issues,
                        "requires_review": True
                    })
            
            # Save outputs
            base_name = os.path.splitext(os.path.basename(input_file))[0]
            
            # Save enriched products
            if enriched_products:
                enriched_dir = os.path.join(output_dir, "enriched")
                os.makedirs(enriched_dir, exist_ok=True)
                enriched_file = os.path.join(enriched_dir, f"enriched_{base_name}.json")
                
                with open(enriched_file, 'w', encoding='utf-8') as f:
                    json.dump(enriched_products, f, indent=2, ensure_ascii=False)
                
                self.logger.info(f"Saved {len(enriched_products)} enriched products to {enriched_file}")
            
            # Save review products
            if review_products:
                review_dir = os.path.join(output_dir, "needs_review")
                os.makedirs(review_dir, exist_ok=True)
                review_file = os.path.join(review_dir, f"review_{base_name}.json")
                
                with open(review_file, 'w', encoding='utf-8') as f:
                    json.dump(review_products, f, indent=2, ensure_ascii=False)
                
                self.logger.info(f"Saved {len(review_products)} products for review to {review_file}")
            
            success_rate = (len(enriched_products) / len(products)) * 100 if products else 0
            self.logger.info(f"Batch processing complete: {success_rate:.1f}% success rate")
            
            return {
                "total_products": len(products),
                "successful_enrichments": len(enriched_products),
                "products_needing_review": len(review_products),
                "success_rate": success_rate
            }
            
        except Exception as e:
            self.logger.error(f"Error processing batch {input_file}: {e}")
            self.logger.error(traceback.format_exc())
            raise

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='DSLD Supplement Enrichment System v2.0.0')
    parser.add_argument('input_path', nargs='?', help='Input file or directory path (optional if using config)')
    parser.add_argument('output_base', nargs='?', help='Output base directory (optional if using config)')
    parser.add_argument('--config', default='config/enrichment_config.json', 
                       help='Configuration file path')
    parser.add_argument('--workers', type=int, 
                       help='Number of worker processes (overrides config)')
    parser.add_argument('--batch-size', type=int,
                       help='Batch size for processing (overrides config)')
    parser.add_argument('--input-dir', 
                       help='Input directory (overrides config)')
    parser.add_argument('--output-dir',
                       help='Output directory (overrides config)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Test run without writing files')
    
    args = parser.parse_args()
    
    try:
        # Initialize enricher
        enricher = SupplementEnricherV2(args.config)
        
        # Determine input and output paths
        # Priority: command line args > config file > defaults
        if args.input_path and args.output_base:
            # Traditional command line usage
            input_path = args.input_path
            output_base = args.output_base
        elif args.input_dir and args.output_dir:
            # Override config with command line
            input_path = args.input_dir
            output_base = args.output_dir
        else:
            # Use config file paths
            paths_config = enricher.config.get('paths', {})
            input_path = paths_config.get('input_directory', '.')
            output_base = paths_config.get('output_directory', 'output_enriched')
        
        # Override processing settings from command line
        processing_config = enricher.config.get('processing_config', {})
        if args.workers:
            processing_config['max_workers'] = args.workers
        if args.batch_size:
            processing_config['batch_size'] = args.batch_size
        
        # Get input files
        input_files = []
        if os.path.isfile(input_path):
            input_files = [input_path]
        elif os.path.isdir(input_path):
            file_pattern = enricher.config.get('paths', {}).get('input_file_pattern', '*.json')
            if file_pattern == '*.json':
                input_files = [
                    os.path.join(input_path, f) 
                    for f in os.listdir(input_path) 
                    if f.endswith('.json')
                ]
            else:
                import glob
                input_files = glob.glob(os.path.join(input_path, file_pattern))
        else:
            raise FileNotFoundError(f"Input path not found: {input_path}")
        
        if not input_files:
            raise ValueError(f"No JSON files found to process in: {input_path}")
        
        if args.dry_run:
            enricher.logger.info("DRY RUN MODE - No files will be written")
            enricher.logger.info(f"Would process {len(input_files)} files:")
            for f in input_files:
                enricher.logger.info(f"  - {f}")
            enricher.logger.info(f"Output would go to: {output_base}")
            return
        
        enricher.logger.info(f"Found {len(input_files)} files to process")
        enricher.logger.info(f"Input directory: {input_path}")
        enricher.logger.info(f"Output directory: {output_base}")
        enricher.logger.info(f"Batch size: {processing_config.get('batch_size', 100)}")
        enricher.logger.info(f"Max workers: {processing_config.get('max_workers', 4)}")
        
        # Process all files
        start_time = datetime.utcnow()
        total_stats = {
            "total_products": 0,
            "successful_enrichments": 0,
            "products_needing_review": 0
        }
        
        for input_file in input_files:
            enricher.logger.info(f"Processing file: {os.path.basename(input_file)}")
            batch_stats = enricher.process_batch(input_file, output_base)
            
            # Accumulate stats
            for key in total_stats:
                total_stats[key] += batch_stats.get(key, 0)
        
        # Final summary
        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()
        overall_success_rate = (total_stats["successful_enrichments"] / total_stats["total_products"]) * 100 if total_stats["total_products"] > 0 else 0
        
        enricher.logger.info("=" * 50)
        enricher.logger.info("ENRICHMENT PROCESSING COMPLETE")
        enricher.logger.info(f"Total products processed: {total_stats['total_products']}")
        enricher.logger.info(f"Success rate: {overall_success_rate:.1f}%")
        enricher.logger.info(f"Total processing time: {processing_time:.2f} seconds")
        
        # Save final summary
        summary = {
            "overall_processing": {
                "total_files_processed": len(input_files),
                "total_processing_time_seconds": round(processing_time, 2),
                "processing_timestamp": end_time.isoformat() + "Z",
                "enrichment_version": "2.0.0"
            },
            "aggregate_stats": {
                "total_products_processed": total_stats["total_products"],
                "successful_enrichments": total_stats["successful_enrichments"],
                "failed_enrichments": total_stats["products_needing_review"],
                "overall_success_rate": round(overall_success_rate, 1)
            }
        }
        
        summary_file = os.path.join(output_base, "reports", f"enrichment_final_summary_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
        os.makedirs(os.path.dirname(summary_file), exist_ok=True)
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        enricher.logger.info(f"Final summary saved: {summary_file}")
        enricher.logger.info("=" * 50)
        
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        logging.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()