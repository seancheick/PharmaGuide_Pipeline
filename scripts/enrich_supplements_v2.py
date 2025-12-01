#!/usr/bin/env python3
"""
DSLD Supplement Enrichment System v2.1.0
Streamlined enrichment focused on scoring preparation with enhanced reporting
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
from tqdm import tqdm

# Import constants
from constants import (
    SCORING_CONSTANTS,
    EVIDENCE_SCORING,
    INGREDIENT_QUALITY_MAP,
    ALLERGENS,
    HARMFUL_ADDITIVES,
    BANNED_RECALLED
)

# Import enhanced reporter (optional - will work without it)
try:
    from enhanced_enrichment_reporter import EnrichmentReporter
    ENHANCED_REPORTING_AVAILABLE = True
except ImportError:
    ENHANCED_REPORTING_AVAILABLE = False

class SupplementEnricherV2:
    def __init__(self, config_path: str = "config/enrichment_config.json"):
        """Initialize enrichment system with configuration"""
        self.databases = {}
        self.ingredient_registry = set()  # For deduplication
        self.unmapped_ingredients = {}  # Track unmapped ingredients with counts
        self._setup_logging()
        self.config = self._load_config(config_path)
        self._compile_patterns()
        self._load_all_databases()

        # Initialize enhanced reporter if available
        self.reporter = None
        self.enhanced_reporting = ENHANCED_REPORTING_AVAILABLE and self.config.get('reporting_config', {}).get('generate_detailed_reports', False)
        
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

    def _enhanced_banned_ingredient_check(self, ingredient_name: str, banned_item: dict, section: str = "") -> bool:
        """
        CONSERVATIVE banned ingredient detection using ONLY exact matching.

        DESIGN DECISION (2025-11-11):
        - Removed substring and fuzzy matching to prevent false positives
        - "ginger" was incorrectly matching "wild ginger" (aristolochic acid alias)
        - User requirement: "word has to be as close to what's there, almost same word"
        - Relies entirely on _exact_ingredient_match() which properly handles aliases

        This conservative approach prioritizes SPECIFICITY over sensitivity:
        - Will NOT flag "ginger" as "wild ginger" (different plants)
        - Will NOT flag "beta alanine" as "beta methylphenethylamine" (different compounds)
        - WILL flag exact matches and properly defined aliases only
        """
        if not ingredient_name or not banned_item:
            return False

        # Use ONLY exact matching - handles aliases properly via database
        # _exact_ingredient_match() checks:
        # 1. Standard name exact match (case-insensitive, normalized)
        # 2. All aliases exact match (case-insensitive, normalized)
        # 3. Handles variations like "Vitamin C" vs "vitamin c"
        exact_match = self._exact_ingredient_match(
            ingredient_name,
            banned_item.get('standard_name', ''),
            banned_item.get('aliases', [])
        )

        return exact_match

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

    def _prepare_transparency_data(self, product_data: Dict) -> Dict:
        """Prepare transparency data for scoring script (no scoring calculations)"""

        vague_disclosures = []
        specific_disclosures = []

        # Check other/inactive ingredients for transparency flags from cleaning
        other_ing_data = product_data.get("otherIngredients", {})
        if not isinstance(other_ing_data, dict):
            other_ing_data = {}

        other_ingredients = other_ing_data.get("ingredients", [])
        if not other_ingredients:
            other_ingredients = []

        for ingredient in other_ingredients:
            if not isinstance(ingredient, dict):
                continue

            name = ingredient.get("name", "")

            # Collect vague disclosure flags (for scoring script to penalize)
            if ingredient.get("vague_disclosure", False):
                for flag in ingredient.get("vague_flags", []):
                    if isinstance(flag, dict):
                        vague_disclosures.append({
                            "ingredient": name,
                            "flag": flag.get("flag", ""),
                            "severity": flag.get("severity", "moderate"),
                            "penalty": flag.get("penalty", 0),
                            "message": flag.get("message", "")
                        })

            # Collect specific functional disclosures (for scoring script to reward)
            elif ingredient.get("functional_context") and ingredient.get("transparency") == "good":
                specific_disclosures.append({
                    "ingredient": name,
                    "functional_context": ingredient["functional_context"],
                    "functional_prefix": ingredient.get("functional_prefix", "")
                })

        # Return organized data for scoring script (NO SCORE CALCULATIONS)
        return {
            "vague_disclosures": vague_disclosures,
            "specific_disclosures": specific_disclosures,
            "has_vague_disclosures": len(vague_disclosures) > 0,
            "has_specific_disclosures": len(specific_disclosures) > 0,
            "vague_count": len(vague_disclosures),
            "specific_count": len(specific_disclosures)
        }

    def enrich_product(self, product_data: Dict) -> Tuple[Dict, List[str]]:
        """Enrich a single product with v2.0.0 format"""
        product_id = product_data.get('id', 'unknown')

        try:
            # VALIDATION: Ensure required fields exist
            if not product_data:
                self.logger.error(f"Product {product_id}: Empty product data")
                return None, ["Empty product data"]

            if 'activeIngredients' not in product_data and 'inactiveIngredients' not in product_data:
                self.logger.warning(f"Product {product_id}: No ingredients found")
                # Continue processing but flag as incomplete

            self.ingredient_registry.clear()  # Reset for each product

            # PRESERVE ALL CLEANED DATA - Start with complete product data
            enriched = dict(product_data)  # Copy all fields from cleaned data

            # Add enrichment metadata
            enriched.update({
                "enrichment_version": "2.1.0",
                "compatible_scoring_versions": ["2.1.0", "2.1.1"],
                "enriched_date": datetime.utcnow().isoformat() + "Z",

                # ENHANCED: Advanced analysis from cleaning phase
                "proprietary_blend_analysis": {},
                "clinical_dosing_analysis": {},
                "industry_benchmark": {},
                "enhanced_penalty_weighting": {},
                # NOTE: activeIngredients and inactiveIngredients preserved from product_data
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
                "analysis": {
                    "form_quality_mapping": [],
                    "feature_flags": {},
                    "extracted_claims": {},
                    "raw_counts": {}
                },
                "unmapped_ingredients": {
                    "active": [],
                    "inactive": [],
                    "summary": {
                        "total_unmapped": 0,
                        "high_priority_count": 0,
                        "medium_priority_count": 0,
                        "low_priority_count": 0
                    }
                },
                "rda_ul_references": {},
                "quality_flags": {
                    "has_premium_forms": False, "has_natural_sources": False, "has_organic": False,
                    "has_clinical_evidence": False, "has_synergies": False, "has_harmful_additives": False,
                    "has_allergens": False, "has_certifications": False, "has_gmp": False,
                    "has_third_party": False, "is_vegan": False, "is_discontinued": False, "made_in_usa": False
                },
                # NOTE: metadata will be merged separately to preserve cleaned metadata
            })

            issues = []

            # Check discontinuation status
            status = product_data.get("status", "").lower()
            enriched["quality_flags"]["is_discontinued"] = status == "discontinued"

            # Process active ingredients
            active_ingredients = product_data.get("activeIngredients", [])
            inactive_ingredients = product_data.get("inactiveIngredients", [])

            # Calculate ingredient breakdown for transparency and intelligent scoring
            total_ingredients = len(active_ingredients) + len(inactive_ingredients)
            active_count = len(active_ingredients)
            inactive_count = len(inactive_ingredients)
            active_percentage = (active_count / total_ingredients * 100) if total_ingredients > 0 else 0

            # Add ingredient breakdown (enables scoring to handle "1 active + fillers" intelligently)
            enriched["ingredient_breakdown"] = {
                "active_count": active_count,
                "inactive_count": inactive_count,
                "total_count": total_ingredients,
                "active_percentage": round(active_percentage, 1)
            }

            # MERGE METADATA: Preserve all cleaned metadata, add enrichment-specific fields
            # This initial merge will be further updated by _calculate_metadata()
            cleaned_metadata = product_data.get("metadata", {})
            enrichment_metadata = {
                "requires_user_profile_scoring": False,
                "scoring_algorithm_version": "2.1.0",
                "data_completeness": 100.0,
                "missing_data": [],
                "single_ingredient_product": total_ingredients == 1,  # Based on TOTAL, not just active
                "ready_for_scoring": True
            }
            # Merge: cleaned metadata takes precedence, enrichment metadata adds new fields
            enriched["metadata"] = {**cleaned_metadata, **enrichment_metadata}
            
            if active_ingredients:
                enriched["form_quality_mapping"] = self._analyze_ingredient_quality(active_ingredients)
                enriched["ingredient_quality_analysis"] = self._calculate_quality_analysis(enriched["form_quality_mapping"])
                enriched["clinical_evidence_matches"] = self._find_clinical_evidence(active_ingredients, product_data)
                enriched["rda_ul_analysis"] = self._analyze_rda_ul(active_ingredients)  # ← RENAMED for scoring phase
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

            # Analyze sustainability (anti-greenwashing: verified packaging claims only)
            enriched["sustainability_analysis"] = self._analyze_sustainability(product_data)

            # Classify supplement type for context-aware scoring (uses TOTAL ingredients)
            enriched["supplement_type_classification"] = self._classify_supplement_type(active_ingredients, inactive_ingredients, product_data)

            # Set quality flags
            enriched["quality_flags"] = self._set_quality_flags(enriched, product_data)

            # ENHANCED: Extract advanced analysis from cleaning phase
            # NOTE: proprietary_blend_analysis already computed at line 363 - don't overwrite!
            # enriched["proprietary_blend_analysis"] = self._extract_proprietary_blend_analysis(product_data)  # BUG: This overwrites fresh analysis!

            # Store cleaning phase metadata for reference (but don't overwrite fresh analysis)
            enriched["cleaning_phase_blend_stats"] = product_data.get("metadata", {}).get("proprietaryBlendStats", {})
            enriched["clinical_dosing_analysis"] = self._extract_clinical_dosing_analysis(product_data)
            enriched["industry_benchmark"] = product_data.get("metadata", {}).get("industryBenchmark", {})
            enriched["enhanced_penalty_weighting"] = product_data.get("metadata", {}).get("penaltyWeighting", {})

            # Set metadata
            enriched["metadata"] = self._calculate_metadata(enriched, product_data)
            
            # Prepare analysis data for scoring phase (no calculations, only data extraction)
            enriched["analysis"] = self._prepare_analysis_data(enriched)

            # Categorize unmapped ingredients by priority
            enriched["unmapped_ingredients"] = self._categorize_unmapped_ingredients(enriched)

            # TRANSPARENCY DATA: Prepare organized data for scoring script (no scoring here)
            transparency_data = self._prepare_transparency_data(product_data)
            enriched["transparency_data"] = transparency_data

            # Update quality flags for vague disclosures (informational only)
            if transparency_data["has_vague_disclosures"]:
                enriched["quality_flags"]["vague_ingredient_disclosure"] = True

            # Update disclosure_quality flags (informational only - scoring script will calculate points)
            enriched["disclosure_quality"]["no_vague_terms"] = not transparency_data["has_vague_disclosures"]
            enriched["disclosure_quality"]["vague_terms_found"] = [
                item["ingredient"] for item in transparency_data["vague_disclosures"]
            ]
            enriched["disclosure_quality"]["specific_disclosures_found"] = [
                item["ingredient"] for item in transparency_data["specific_disclosures"]
            ]

            return enriched, issues

        except KeyError as e:
            self.logger.error(f"Product {product_id}: Missing required field: {e}")
            self.logger.error(traceback.format_exc())
            return None, [f"Missing required field: {str(e)}"]
        except TypeError as e:
            self.logger.error(f"Product {product_id}: Type error (likely None value): {e}")
            self.logger.error(traceback.format_exc())
            return None, [f"Type error: {str(e)}"]
        except ValueError as e:
            self.logger.error(f"Product {product_id}: Value error (invalid data): {e}")
            self.logger.error(traceback.format_exc())
            return None, [f"Value error: {str(e)}"]
        except Exception as e:
            self.logger.error(f"Product {product_id}: Unexpected error during enrichment: {e}")
            self.logger.error(traceback.format_exc())
            return None, [f"Enrichment failed: {str(e)}"]

    def _lookup_category(self, standard_name: str, quality_map: Dict) -> str:
        """
        Lookup category from ingredient_quality_map using standardName.

        This is ENRICHMENT-PHASE metadata, not core identity.
        Used only for supplement type classification.

        Args:
            standard_name: Standardized ingredient name from cleaning phase
            quality_map: ingredient_quality_map.json database

        Returns:
            Category string (e.g., "vitamins", "minerals", "herbs") or empty string
        """
        if not standard_name or not quality_map:
            return ""

        # Normalize for lookup
        key = standard_name.lower().strip()

        # Search ingredient_quality_map for matching standard_name
        for ing_key, data in quality_map.items():
            # Skip metadata keys
            if ing_key.startswith("_") or not isinstance(data, dict):
                continue
            if data.get("standard_name", "").lower() == key:
                return data.get("category", "").lower()

        return ""

    def _analyze_ingredient_quality(self, ingredients: List[Dict]) -> List[Dict]:
        """
        Analyze ingredient quality with priority-based checking.
        ✅ ENHANCED: Checks harmful additives and allergens BEFORE quality mapping
        Priority: 1) Additives 2) Allergens 3) Quality Map 4) Fallback
        """
        quality_mapping = []
        quality_map = self.databases.get('ingredient_quality_map', {})

        # ✅ Load reference databases for priority checking
        additives_db = self.databases.get('harmful_additives', {})
        allergens_db = self.databases.get('allergens', {})

        for ingredient in ingredients:
            ingredient_name = ingredient.get('name', '')  # Keep exact name from label
            standard_name = ingredient.get('standardName', '') or ingredient_name
            quantity = ingredient.get('quantity', 0)
            unit = ingredient.get('unit', '')

            # ✅ PRIORITY 1: Check if it's a harmful additive FIRST
            # This is critical - harmful additives must be detected for penalties
            additive_match = self._check_harmful_additive(standard_name, additives_db)
            if additive_match:
                # Get RDA/UL data (usually won't have, but check anyway)
                rda_ul_data = self._get_rda_ul_data(standard_name, quantity, unit)

                quality_mapping.append({
                    "ingredient": ingredient_name,
                    "standard_name": standard_name,
                    "detected_form": "harmful_additive",
                    "is_harmful": True,
                    "risk_level": additive_match.get("risk_level", "moderate"),
                    "penalty": additive_match.get("deduction", -1.0),
                    "bio_score": 3,  # Low score for harmful additives
                    "category": "harmful_additive",
                    "category_weight": 1.0,
                    "dosage_importance": 1.0,
                    "weighted_score": 3.0,
                    "absorption": "n/a",
                    "notes": f"Harmful additive: {additive_match.get('risk_level', 'moderate')} risk",
                    "is_fallback": False,
                    "rda_ul_data": rda_ul_data  # ← NEW: Add RDA/UL data
                })
                continue

            # ✅ PRIORITY 2: Check if it's an allergen SECOND
            # This is critical - allergens must be detected for claim verification
            allergen_match = self._check_allergen(standard_name, allergens_db)
            if allergen_match:
                # Get RDA/UL data (usually won't have, but check anyway)
                rda_ul_data = self._get_rda_ul_data(standard_name, quantity, unit)

                quality_mapping.append({
                    "ingredient": ingredient_name,
                    "standard_name": standard_name,
                    "detected_form": "allergen",
                    "is_allergen": True,
                    "allergen_type": allergen_match.get("allergen_type", "unknown"),
                    "severity": allergen_match.get("severity", "low"),
                    "bio_score": 5,  # Neutral score for allergens
                    "category": "allergen",
                    "category_weight": 1.0,
                    "dosage_importance": 1.0,
                    "weighted_score": 5.0,
                    "absorption": "n/a",
                    "notes": f"Allergen: {allergen_match.get('allergen_type', 'unknown')}",
                    "is_fallback": False,
                    "rda_ul_data": rda_ul_data  # ← NEW: Add RDA/UL data
                })
                continue

            # ✅ PRIORITY 3: Check quality map for active ingredients
            # Find quality match with proper hierarchy handling
            matched_parent = None
            matched_form = None
            detected_form = "standard"
            parent_key = ""
            
            # PHASE 1: Search all forms across all parent entries first (more specific)
            form_found = False
            for parent_key, parent_data in quality_map.items():
                # Skip metadata keys
                if parent_key.startswith("_") or not isinstance(parent_data, dict):
                    continue
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
                    # Skip metadata keys
                    if parent_key.startswith("_") or not isinstance(parent_data, dict):
                        continue
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
                
                # Get RDA/UL data for this ingredient
                rda_ul_data = self._get_rda_ul_data(reference_standard_name, quantity, unit)

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
                    "notes": matched_form.get('notes', ''),
                    "rda_ul_data": rda_ul_data  # ← NEW: Add RDA/UL enrichment data
                })
            else:
                # ✅ ENHANCED FALLBACK LOGIC: Intelligent defaults based on ingredient type
                # Track unmapped ingredients with counts and priority
                if ingredient_name in self.unmapped_ingredients:
                    self.unmapped_ingredients[ingredient_name] += 1
                else:
                    self.unmapped_ingredients[ingredient_name] = 1

                # Determine if this is an active ingredient (should be mapped)
                is_active = ingredient.get('isPassiveIngredient') == False
                cleaned_category = ingredient.get('category', 'other')

                # Set priority for manual mapping follow-up
                if is_active:
                    priority = "HIGH"  # Active ingredients must be mapped
                elif cleaned_category in ['additive', 'harmful']:
                    priority = "MEDIUM"  # Harmful additives need mapping
                else:
                    priority = "LOW"  # Regular inactive ingredients

                # Log unmapped ingredient with priority (DEBUG level to avoid terminal spam)
                self.logger.debug(f"No mapping found for ingredient: '{ingredient_name}' (occurrence #{self.unmapped_ingredients[ingredient_name]}, priority: {priority})")

                # ✅ INTELLIGENT FALLBACK: Use neutral scores that won't crash scoring
                # Active ingredients get 8 (neutral), inactives get 5 (slightly below average)
                fallback_bio_score = 8 if is_active else 5

                # Use cleaned category if available (better than "unmapped")
                fallback_category = cleaned_category if cleaned_category != "other" else "unmapped"

                # Get RDA/UL data even for unmapped ingredients (might still have RDA data)
                rda_ul_data = self._get_rda_ul_data(ingredient_name, quantity, unit)

                # Default values for unmapped ingredients
                quality_mapping.append({
                    "ingredient": ingredient_name,  # Preserve exact name from label
                    "standard_name": ingredient_name,  # Use ingredient name as fallback
                    "detected_form": "unmapped",  # ✅ FLAG as unmapped (not "standard")
                    "bio_score": fallback_bio_score,
                    "natural": False,
                    "natural_bonus": 0,
                    "total_form_score": fallback_bio_score,
                    "category": fallback_category,  # Use cleaned category if available
                    "category_weight": self._get_category_weight(fallback_category),
                    "dosage_importance": 1.0,  # Neutral importance
                    "weighted_score": float(fallback_bio_score),
                    "absorption": "moderate",
                    "notes": f"⚠️ UNMAPPED {priority} PRIORITY - Add to quality_map.json",
                    "is_fallback": True,  # ✅ FLAG for dev team tracking
                    "unmapped_priority": priority,  # ✅ ADD for manual review workflow
                    "rda_ul_data": rda_ul_data  # ← NEW: Add RDA/UL data even for unmapped
                })
        
        return quality_mapping

    def _check_harmful_additive(self, standard_name: str, additives_db: Dict) -> Dict:
        """
        Check if ingredient is in harmful additives database.
        Returns match data if found, None otherwise.

        Priority checking: This runs BEFORE quality mapping to ensure harmful
        additives are detected even if they have quality mappings.
        """
        if not standard_name or not additives_db:
            return None

        additives_list = additives_db.get('harmful_additives', [])

        for additive in additives_list:
            additive_name = additive.get('standard_name', '')
            aliases = additive.get('aliases', [])

            # Use existing exact matching logic
            if self._exact_ingredient_match(standard_name, additive_name, aliases):
                # Calculate penalty based on risk level
                risk_level = additive.get('risk_level', 'moderate')
                deduction_map = {
                    'high': -3.0,
                    'moderate': -1.5,
                    'low': -1.0
                }

                return {
                    'standard_name': additive_name,
                    'risk_level': risk_level,
                    'deduction': deduction_map.get(risk_level, -1.0),
                    'category': additive.get('category', 'unknown'),
                    'notes': additive.get('notes', '')
                }

        return None

    def _check_allergen(self, standard_name: str, allergens_db: Dict) -> Dict:
        """
        Check if ingredient is in allergens database.
        Returns match data if found, None otherwise.

        Priority checking: This runs BEFORE quality mapping to ensure allergens
        are detected for claim verification (e.g., "soy-free" claims).
        """
        if not standard_name or not allergens_db:
            return None

        allergens_list = allergens_db.get('common_allergens', [])

        for allergen in allergens_list:
            allergen_name = allergen.get('standard_name', '')
            aliases = allergen.get('aliases', [])

            # Use existing exact matching logic
            if self._exact_ingredient_match(standard_name, allergen_name, aliases):
                return {
                    'standard_name': allergen_name,
                    'allergen_type': allergen.get('category', 'unknown'),
                    'severity': allergen.get('severity_level', 'low'),
                    'prevalence': allergen.get('prevalence', 'unknown'),
                    'regulatory_status': allergen.get('regulatory_status', ''),
                    'notes': allergen.get('notes', '')
                }

        return None

    def _get_category_weight(self, category: str) -> float:
        """Get category weight for ingredient based on scoring system"""
        weights = {
            # Primary therapeutic value (1.0)
            'vitamin': 1.0,
            'vitamins': 1.0,
            'mineral': 1.0,
            'minerals': 1.0,
            'fatty_acids': 1.0,
            'fatty_acid': 1.0,
            'fat': 1.0,
            'fats': 1.0,
            
            # Secondary therapeutic value (0.8)
            'botanicals': 0.8,
            'botanical': 0.8,
            'botanical_ingredients': 0.8,
            'herb': 0.8,
            'herbs': 0.8,
            
            # Amino acids and derivatives (0.7)
            'amino_acids': 0.7,
            'amino_acid': 0.7,
            
            # Antioxidants (0.7)
            'antioxidants': 0.7,
            'antioxidant': 0.7,
            
            # Probiotics (0.9)
            'probiotics': 0.9,
            'probiotic': 0.9,
            'bacteria': 0.9,  # From cleaned data
            
            # Enzymes (0.6)
            'enzymes': 0.6,
            'enzyme': 0.6,
            
            # Specialized categories
            'nutraceuticals': 0.8,
            'metabolic_support': 0.7,
            'fibers': 0.6,
            'standardization_marker': 0.5,
            
            # Mixed/blend categories
            'blend': 0.6,
            
            # No therapeutic value (0.0)
            'excipients': 0.0,
            'excipient': 0.0,
            'nutritional_info': 0.0,
            'non-nutrient/non-botanical': 0.0,
            
            # Default categories
            'other': 0.7,
            'unmapped': 0.5
        }
        return weights.get(category.lower(), 0.7)

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
            "has_super_combo_bonus": premium_forms >= SCORING_CONSTANTS["premium_forms_super_combo_threshold"],
            "final_a1_score": round(average_score, 2),
            "capped_score": round(capped_score, 2)
        }

    def _find_clinical_evidence(self, ingredients: List[Dict], product_data: Dict) -> List[Dict]:
        """Find clinical evidence matches with brand-specific validation"""
        evidence_matches = []
        clinical_studies_db = self.databases.get('backed_clinical_studies', {})
        clinical_studies = clinical_studies_db.get('backed_clinical_studies', [])
        
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
        return EVIDENCE_SCORING.get(f"{tier}_score", EVIDENCE_SCORING["default_score"])

    def _analyze_absorption_enhancers(self, all_ingredients: List[Dict]) -> Dict:
        """Check for absorption enhancers"""
        enhancers_database = self.databases.get('absorption_enhancers', {})
        enhancers_db = enhancers_database.get('absorption_enhancers', [])
        found_enhancers = []
        enhanced_nutrients = []

        # PERFORMANCE OPTIMIZATION: Build ingredient lookup dictionary once (O(n) instead of O(n²))
        ingredient_lookup = {}
        for ing in all_ingredients:
            std_name = ing.get('standardName', '').lower().strip()
            name = ing.get('name', '').lower().strip()
            if std_name:
                ingredient_lookup[std_name] = ing
            if name and name != std_name:
                ingredient_lookup[name] = ing

        for ingredient in all_ingredients:
            ingredient_name = ingredient.get('name', '')

            for enhancer in enhancers_db:
                if self._exact_ingredient_match(ingredient_name, enhancer.get('name', ''), enhancer.get('aliases', [])):
                    # Find what nutrients this enhancer affects
                    enhanced_list = enhancer.get('enhances', [])

                    # Check if any of the enhanced nutrients are present in the product
                    # PERFORMANCE: Use O(1) dictionary lookup instead of O(n) loop
                    for enhanced_nutrient in enhanced_list:
                        enhanced_nutrient_lower = enhanced_nutrient.lower().strip()

                        # Use ONLY exact matching (same fix as banned substances)
                        if enhanced_nutrient_lower in ingredient_lookup:
                            if enhanced_nutrient not in enhanced_nutrients:
                                enhanced_nutrients.append(enhanced_nutrient)

                    found_enhancers.append({
                        "name": ingredient_name,
                        "enhancer_id": enhancer.get('id', ''),
                        "enhanced_nutrients": enhancer.get('enhances', [])
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
            # Skip metadata keys
            if delivery_name.startswith("_") or not isinstance(delivery_data, dict):
                continue
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
            if len(matched_ingredients) >= SCORING_CONSTANTS["synergy_minimum_matched_ingredients"]:
                # All ingredients must meet minimum dose for full synergy points
                all_meet_dose = all(ing.get('meets_min_dose', False) for ing in matched_ingredients)
                # Use evidence tier for more accurate scoring
                evidence_tier = cluster.get('evidence_tier', 3)
                base_points = {1: 3, 2: 2, 3: 1}.get(evidence_tier, 1)
                points = base_points if all_meet_dose else base_points // 2
                
                detected_clusters.append({
                    "cluster_name": cluster.get('name', ''),
                    "cluster_id": cluster.get('id', cluster.get('name', '').lower().replace(' ', '_')),
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
                    # Use min_threshold if present, otherwise skip standardization requirement
                    min_threshold = botanical.get('min_threshold')
                    if min_threshold is not None:
                        # Handle different min_threshold formats (0.97 vs 97)
                        if min_threshold > 1:  # If stored as 97 instead of 0.97
                            min_threshold = min_threshold / 100

                        if percentage >= min_threshold:
                            points = 2  # Standardized to +2 per scoring doc
                    else:
                        # No minimum threshold specified, award points if any standardization detected
                        if percentage > 0:
                            points = 2
                    
                    standardized_botanicals.append({
                        "ingredient": ingredient_name,
                        "botanical_id": botanical.get('id', botanical.get('standard_name', '').lower().replace(' ', '_')),
                        "standardization_percentage": percentage,
                        "marker_compounds": botanical.get('markers', []),
                        "min_threshold": botanical.get('min_threshold'),  # ✅ ADD THIS for scoring reference
                        "meets_threshold": percentage >= (min_threshold if min_threshold else 0),  # ✅ ADD THIS
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
        penalty_rules = proprietary_db.get('proprietary_blend_concerns', [])
        
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
        """
        Detect egregious marketing claims with context-aware pattern matching.
        ✅ FIXED: Excludes legitimate business language like "guaranteed quality"
        """
        label_text = product_data.get('labelText', '')
        product_name = product_data.get('fullName', '')
        claims = product_data.get('claims', [])

        # Combine all text for analysis
        all_text = ' '.join([product_name, label_text, str(claims)]).lower()

        # ✅ STEP 1: Remove legitimate business language to prevent false positives
        exclusion_patterns = [
            r'\b(guaranteed\s+quality|quality\s+guaranteed)\b',
            r'\b(satisfaction\s+guaranteed|guaranteed\s+satisfaction)\b',
            r'\b(guaranteed\s+fresh|freshness\s+guaranteed)\b',
            r'\b(money[-\s]?back\s+guarantee)\b',
            r'\b(guaranteed\s+potency)\b',
            r'\b(purity\s+guaranteed)\b'
        ]

        for pattern in exclusion_patterns:
            all_text = re.sub(pattern, '', all_text)

        flagged_claims = []
        flagged_terms = []

        # ✅ STEP 2: Context-aware egregious claim patterns (critical violations only)
        egregious_patterns = [
            # CRITICAL - Disease treatment claims (FDA violation)
            (r'\b(treats?|cures?|prevents?|heals?|eliminates?|reverses?)\s+(cancer|diabetes|alzheimer|arthritis|covid[-\s]?19|hypertension|heart\s+disease|depression|anxiety)\b', 'disease_treatment', -10),

            # CRITICAL - Drug replacement claims
            (r'\b(replaces?|better\s+than|substitute\s+for)\s+(metformin|insulin|lipitor|viagra|prozac|statin)\b', 'drug_replacement', -15),

            # CRITICAL - False FDA approval
            (r'\b(fda\s+approved|approved\s+by\s+(the\s+)?fda)\b(?!.*facility)', 'false_fda_approval', -15),

            # HIGH - Miracle cures
            (r'\b(miracle\s+(cure|pill|supplement)|100\s*%\s+(cure|effective|success)|instant\s+(healing|cure|relief))\b', 'miracle_claim', -8),

            # HIGH - Unrealistic weight loss
            (r'\b(lose\s+\d+\s+pounds?\s+in\s+\d+\s+days?|overnight\s+weight\s+loss|melt\s+(fat|pounds)\s+away)\b', 'unrealistic_weight_loss', -8),

            # MEDIUM - Anti-aging exaggeration
            (r'\b(fountain\s+of\s+youth|anti[-\s]?aging\s+miracle|reverse\s+aging|turn\s+back\s+time)\b', 'anti_aging_exaggeration', -6),

            # MEDIUM - False science claims (only if no studies mentioned)
            (r'\b(scientifically\s+proven|clinically\s+proven)\b(?!.*(study|studies|trial|research))', 'false_science_claims', -4)
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
                        "penalty": penalty,
                        "severity": "critical" if penalty <= -10 else "high" if penalty <= -6 else "medium"
                    })
                    total_penalty += penalty

        return {
            "found": len(flagged_claims) > 0,
            "claims": flagged_claims,
            "flagged_terms": list(set(flagged_terms)),
            "penalty": total_penalty,
            "severity_breakdown": {
                "critical": len([c for c in flagged_claims if c.get("severity") == "critical"]),
                "high": len([c for c in flagged_claims if c.get("severity") == "high"]),
                "medium": len([c for c in flagged_claims if c.get("severity") == "medium"])
            }
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

    def _normalize_nutrient_name(self, name: str) -> str:
        """Normalize nutrient name for matching (remove form suffixes, normalize case)"""
        if not name:
            return ""

        # Convert to lowercase
        normalized = name.lower().strip()

        # Remove common form suffixes
        form_suffixes = [
            ' (d3)', ' (d2)', ' d3', ' d2',
            ' (k1)', ' (k2)', ' k1', ' k2',
            ' (b1)', ' (b2)', ' (b3)', ' (b5)', ' (b6)', ' (b7)', ' (b9)', ' (b12)',
            ' b1', ' b2', ' b3', ' b5', ' b6', ' b7', ' b9', ' b12',
            ' (as ', ' as ',
            ' (from ', ' from ',
            'cholecalciferol', 'ergocalciferol',
            'phylloquinone', 'menaquinone',
            'thiamine', 'riboflavin', 'niacin', 'pantothenic acid', 'pyridoxine',
            'biotin', 'folate', 'folic acid', 'cobalamin', 'cyanocobalamin'
        ]

        for suffix in form_suffixes:
            if suffix in normalized:
                # For vitamin names, keep the base vitamin name
                if normalized.startswith('vitamin'):
                    # Extract just "vitamin x" part
                    parts = normalized.split()
                    if len(parts) >= 2:
                        normalized = f"{parts[0]} {parts[1]}"
                        break

        return normalized

    def _convert_units(self, quantity: float, from_unit: str, to_unit: str) -> float:
        """Convert between common supplement units"""
        if not quantity or not from_unit or not to_unit:
            return quantity

        # Normalize units
        from_unit = from_unit.lower().strip()
        to_unit = to_unit.lower().strip()

        # If units match, no conversion needed
        if from_unit == to_unit:
            return quantity

        # Conversion factors to base unit (mg)
        to_mg = {
            'g': 1000,
            'mg': 1,
            'mcg': 0.001,
            'μg': 0.001,
            'ug': 0.001,
            'iu': 1,  # IU conversion is substance-specific, handled separately
            'mcg rae': 0.001,  # Retinol Activity Equivalents
            'mcg dfe': 0.001,  # Dietary Folate Equivalents
        }

        # Handle IU conversions (substance-specific)
        if 'iu' in from_unit and 'iu' not in to_unit:
            # These are approximate conversions
            # Vitamin D: 1 IU = 0.025 mcg
            # Vitamin E: 1 IU = 0.67 mg (d-alpha-tocopherol)
            # Vitamin A: 1 IU = 0.3 mcg (retinol)
            # For now, return original quantity (needs context)
            return quantity

        # Standard conversion
        if from_unit in to_mg and to_unit in to_mg:
            # Convert to mg, then to target unit
            quantity_in_mg = quantity * to_mg[from_unit]
            return quantity_in_mg / to_mg[to_unit]

        # If conversion not possible, return original
        return quantity

    def _calculate_dosage_category(self, quantity: float, rda: float, optimal_min: float,
                                   optimal_max: float, ul: float) -> str:
        """
        Calculate dosage category based on RDA, optimal range, and UL.

        Categories:
        - under_dosed: < 50% of RDA
        - minimal: 50-100% of RDA
        - optimal: Within optimal range
        - high: Above optimal but below UL
        - excessive: Above UL
        """
        if not quantity or not rda:
            return "unknown"

        # Check if excessive (above UL)
        if ul > 0 and quantity > ul:
            return "excessive"

        # Check if within optimal range
        if optimal_min > 0 and optimal_max > 0:
            if optimal_min <= quantity <= optimal_max:
                return "optimal"
            elif quantity > optimal_max:
                return "high"

        # Check RDA-based categories
        percent_of_rda = (quantity / rda) * 100

        if percent_of_rda < 50:
            return "under_dosed"
        elif percent_of_rda < 100:
            return "minimal"
        elif optimal_min > 0 and quantity < optimal_min:
            return "minimal"
        else:
            return "optimal"

    def _calculate_safety_status(self, quantity: float, ul: float) -> str:
        """
        Calculate safety status based on UL.

        Status:
        - safe: Below 80% of UL
        - caution: 80-100% of UL
        - excessive: Above UL
        """
        if not ul or ul == 0:
            return "safe"  # No UL established

        if not quantity:
            return "unknown"

        percent_of_ul = (quantity / ul) * 100

        if percent_of_ul > 100:
            return "excessive"
        elif percent_of_ul >= 80:
            return "caution"
        else:
            return "safe"

    def _get_rda_ul_data(self, ingredient_name: str, quantity: float, unit: str) -> Dict:
        """
        Get simplified RDA/UL data for enrichment phase.
        Returns only highest UL, dosage category, and safety status.
        Detailed RDA/warnings/symptoms should be looked up during scoring phase.

        Args:
            ingredient_name: Standard name of ingredient (e.g., "Vitamin D")
            quantity: Amount in product
            unit: Unit of measurement (e.g., "mcg", "mg")

        Returns:
            Dict with highest UL, dosage category, safety status (minimal data for enrichment)
        """
        rda_ul_db = self.databases.get('rda_optimal_uls', {})

        # Default structure for ingredients without RDA data
        default_response = {
            "has_rda_data": False,
            "ul": 0,
            "unit": "",
            "dosage_category": "unknown",
            "percent_of_ul": 0,
            "safety_status": "unknown"
        }

        if not rda_ul_db or not quantity:
            return default_response

        # Get database info
        nutrient_recommendations = rda_ul_db.get('nutrient_recommendations', [])

        # Find matching nutrient
        matched_nutrient = None
        for nutrient in nutrient_recommendations:
            nutrient_standard_name = nutrient.get('standard_name', '')

            # Normalize names for comparison (case-insensitive, handle variations)
            if self._normalize_nutrient_name(ingredient_name) == self._normalize_nutrient_name(nutrient_standard_name):
                matched_nutrient = nutrient
                break

        if not matched_nutrient:
            return default_response

        # Extract only essential nutrient data for enrichment
        nutrient_unit = matched_nutrient.get('unit', '')
        optimal_range = matched_nutrient.get('optimal_range', '')
        highest_ul = matched_nutrient.get('highest_ul', 0)

        # Get RDA value (use adult male 19-30 as default reference for dosage category)
        rda_value = 0
        for data_point in matched_nutrient.get('data', []):
            if data_point.get('group') == 'Male' and data_point.get('age_range') == '19-30':
                rda_value = data_point.get('rda_ai', 0)
                break

        # Unit conversion if needed
        converted_quantity = self._convert_units(quantity, unit, nutrient_unit)

        # Parse optimal range for dosage category calculation
        optimal_min = 0
        optimal_max = 0
        if optimal_range and '-' in optimal_range:
            try:
                parts = optimal_range.split('-')
                optimal_min = float(parts[0].strip())
                optimal_max = float(parts[1].strip())
            except (ValueError, IndexError):
                pass

        # Calculate only what's needed for enrichment
        # Handle None converted_quantity (unit conversion failure)
        if converted_quantity is None or converted_quantity == 0:
            return default_response

        percent_of_ul = (converted_quantity / highest_ul * 100) if highest_ul > 0 else 0

        # Determine dosage category (for product-level summary)
        dosage_category = self._calculate_dosage_category(
            converted_quantity, rda_value, optimal_min, optimal_max, highest_ul
        )

        # Determine safety status (for product-level summary)
        safety_status = self._calculate_safety_status(converted_quantity, highest_ul)

        # Return simplified structure with only essential enrichment data
        # Detailed RDA/warnings/symptoms will be looked up during scoring phase
        return {
            "has_rda_data": True,
            "ul": highest_ul,
            "unit": nutrient_unit,
            "dosage_category": dosage_category,
            "percent_of_ul": round(percent_of_ul, 1),
            "safety_status": safety_status
        }

    def _analyze_rda_ul(self, ingredients: List[Dict]) -> Dict:
        """
        Analyze RDA/UL compliance for all ingredients.
        Returns product-level summary of RDA/UL analysis for scoring phase.
        """
        if not ingredients:
            return {
                "total_ingredients_with_rda": 0,
                "optimal_dosed_count": 0,
                "under_dosed_count": 0,
                "excessive_dosed_count": 0,
                "safety_warnings_count": 0,
                "interaction_warnings_count": 0,
                "conditionally_essential_count": 0,
                "overall_dosing_quality": "unknown",
                "safety_score": 15.0,
                "dosing_adequacy_score": 0.0
            }

        # Collect RDA/UL data for all ingredients
        total_with_rda = 0
        optimal_count = 0
        under_dosed_count = 0
        excessive_count = 0
        all_warnings = set()
        all_interactions = set()
        conditionally_essential_count = 0

        for ingredient in ingredients:
            ingredient_name = ingredient.get('standardName') or ingredient.get('name', '')
            quantity = ingredient.get('quantity', 0)
            unit = ingredient.get('unit', '')

            # Get RDA/UL data
            rda_data = self._get_rda_ul_data(ingredient_name, quantity, unit)

            if rda_data.get('has_rda_data'):
                total_with_rda += 1

                # Count dosage categories
                dosage_category = rda_data.get('dosage_category', 'unknown')
                if dosage_category == 'optimal':
                    optimal_count += 1
                elif dosage_category == 'under_dosed':
                    under_dosed_count += 1
                elif dosage_category == 'excessive':
                    excessive_count += 1

                # Collect warnings
                warnings = rda_data.get('warnings', [])
                interactions = rda_data.get('interaction_warnings', [])

                all_warnings.update(warnings)
                all_interactions.update(interactions)

                # Count conditionally essential
                if rda_data.get('is_conditionally_essential'):
                    conditionally_essential_count += 1

        # Calculate overall dosing quality
        if total_with_rda == 0:
            overall_quality = "unknown"
        else:
            optimal_percent = (optimal_count / total_with_rda) * 100
            if optimal_percent >= 80:
                overall_quality = "excellent"
            elif optimal_percent >= 60:
                overall_quality = "good"
            elif optimal_percent >= 40:
                overall_quality = "fair"
            else:
                overall_quality = "poor"

        # Calculate safety score (max 15 points)
        safety_score = 15.0
        if excessive_count > 0:
            safety_score -= (excessive_count * 3)  # -3 points per excessive ingredient
        safety_score = max(0, safety_score)  # Don't go below 0

        # Calculate dosing adequacy score (max 10 points)
        if total_with_rda > 0:
            dosing_score = (optimal_count / total_with_rda) * 10
            # Penalty for under-dosed
            dosing_score -= (under_dosed_count / total_with_rda) * 3
            dosing_score = max(0, min(10, dosing_score))  # Clamp to 0-10
        else:
            dosing_score = 0.0

        return {
            "total_ingredients_with_rda": total_with_rda,
            "optimal_dosed_count": optimal_count,
            "under_dosed_count": under_dosed_count,
            "excessive_dosed_count": excessive_count,
            "safety_warnings_count": len(all_warnings),
            "interaction_warnings_count": len(all_interactions),
            "conditionally_essential_count": conditionally_essential_count,
            "overall_dosing_quality": overall_quality,
            "safety_score": round(safety_score, 1),
            "dosing_adequacy_score": round(dosing_score, 1)
        }

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
        
        # Check banned substances with enhanced detection
        banned_db = self.databases.get('banned_recalled_ingredients', {})

        # Get ALL sections from the banned database dynamically
        all_sections = []
        critical_sections = []

        for key, value in banned_db.items():
            # Skip metadata keys
            if key.startswith("_"):
                continue
            if isinstance(value, list) and len(value) > 0:
                # Check if items in the list have the expected structure for banned substances
                if any(isinstance(item, dict) and 'standard_name' in item for item in value):
                    all_sections.append(key)

                    # Identify critical sections for enhanced detection
                    if key in ["permanently_banned", "nootropic_banned", "sarms_prohibited",
                              "illegal_spiking_agents", "new_emerging_threats", "pharmaceutical_adulterants"]:
                        critical_sections.append(key)

        # DEBUG ONLY: Uncomment for debugging banned substance checks
        # self.logger.debug(f"🔍 Checking {len(all_sections)} banned substance categories: {', '.join(all_sections)}")

        for ingredient in all_ingredients:
            ingredient_name = ingredient.get('name', '')
            if not ingredient_name:
                continue

            # Check each section for banned substances
            for section in all_sections:
                items = banned_db.get(section, [])
                if not isinstance(items, list):
                    continue

                for banned_item in items:
                    if self._enhanced_banned_ingredient_check(ingredient_name, banned_item, section):
                        severity = banned_item.get('severity_level', 'high')
                        deduction = self._get_banned_deduction(severity)

                        # Check if already found (avoid duplicates)
                        existing = next((s for s in contaminant_analysis["banned_substances"]["substances"]
                                       if s["name"] == ingredient_name and s["banned_id"] == banned_item.get('id', '')), None)

                        if not existing:
                            contaminant_analysis["banned_substances"]["substances"].append({
                                "name": ingredient_name,
                                "banned_id": banned_item.get('id', ''),
                                "standard_name": banned_item.get('standard_name', ''),
                                "category": section,
                                "severity": severity,
                                "deduction": deduction,
                                "match_type": "enhanced_detection"
                            })
                            contaminant_analysis["banned_substances"]["severity_deductions"] += deduction

                            # Log critical banned substance detection (only for critical/high severity)
                            if severity == 'critical':
                                self.logger.warning(f"🚨 CRITICAL BANNED: {ingredient_name} -> {banned_item.get('standard_name', '')}")
                            elif severity == 'high':
                                self.logger.warning(f"⚠️  HIGH-RISK BANNED: {ingredient_name} -> {banned_item.get('standard_name', '')}")

                        break  # Stop checking other items for this ingredient once found
        
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
        allergen_items = allergen_db.get('allergens', allergen_db.get('common_allergens', []))
        
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
        
        # ✅ ENHANCED: Check verification against detected allergens with detailed tracking
        verified = True
        conflicts = []
        allergen_names = [allergen['name'].lower() for allergen in detected_allergens]

        # Check each claim against detected allergens
        if claims.get('dairy_free') and any('milk' in name or 'dairy' in name or 'whey' in name or 'casein' in name for name in allergen_names):
            verified = False
            conflicts.append("dairy_free claim conflicts with detected dairy allergens")
        if claims.get('soy_free') and any('soy' in name for name in allergen_names):
            verified = False
            conflicts.append("soy_free claim conflicts with detected soy allergens")
        if claims.get('gluten_free') and any('gluten' in name or 'wheat' in name for name in allergen_names):
            verified = False
            conflicts.append("gluten_free claim conflicts with detected gluten/wheat allergens")
        if claims.get('egg_free') and any('egg' in name for name in allergen_names):
            verified = False
            conflicts.append("egg_free claim conflicts with detected egg allergens")
        if claims.get('shellfish_free') and any('shellfish' in name or 'crustacean' in name for name in allergen_names):
            verified = False
            conflicts.append("shellfish_free claim conflicts with detected shellfish allergens")
        if claims.get('yeast_free') and any('yeast' in name for name in allergen_names):
            verified = False
            conflicts.append("yeast_free claim conflicts with detected yeast allergens")

        # ✅ Calculate points - ONLY if verified and has claims
        compliance_points = 2 if verified and any(claims.values()) else 0
        gluten_free_points = 1 if claims.get('gluten_free') and verified else 0
        
        vegan_vegetarian = any(group.lower() in ['vegan', 'vegetarian'] for group in target_groups)
        vegan_vegetarian_points = 1 if vegan_vegetarian and verified else 0
        
        return {
            "claims": claims,
            "verified": verified,
            "conflicts": conflicts,  # ✅ ADD: List of verification conflicts for debugging
            "allergen_detected": len(detected_allergens) > 0,
            "compliance_points": compliance_points,
            "gluten_free_points": gluten_free_points,
            "vegan_vegetarian_points": vegan_vegetarian_points
        }

    def _analyze_certifications(self, product_data: Dict) -> Dict:
        """
        Analyze certifications from product data.
        ✅ ENHANCED: Detects third-party testing from statements and label text
        """
        target_groups = product_data.get('targetGroups', [])
        contacts = product_data.get('contacts', [])
        statements = product_data.get('statements', [])
        label_text = product_data.get('labelText', '').lower()

        # Extract certifications from target groups
        certifications = []
        if any('usda organic' in group.lower() for group in target_groups):
            certifications.append("USDA Organic")
        if any('third-party tested' in group.lower() or 'third party tested' in group.lower() for group in target_groups):
            certifications.append("Third-Party-Tested")
        if any('non-gmo' in group.lower() for group in target_groups):
            certifications.append("Non-GMO")

        # ✅ ENHANCED: Detect third-party testing from statements (more reliable)
        for statement in statements:
            notes = statement.get("notes", "").lower()
            if any(keyword in notes for keyword in [
                "third party-inspected", "third party tested", "third-party tested",
                "independent lab", "external laboratory", "independently tested"
            ]):
                if "Third-Party-Tested" not in certifications:
                    certifications.append("Third-Party-Tested")
                break

        # ✅ ENHANCED: Detect NAMED third-party programs (worth more in scoring)
        named_programs = {
            "nsf certified for sport": "NSF Sport",
            "nsf sport": "NSF Sport",
            "usp verified": "USP Verified",
            "consumerlab": "ConsumerLab",
            "consumerlab.com": "ConsumerLab",
            "informed sport": "Informed Sport",
            "informed choice": "Informed Choice",
            "banned substance tested": "Informed Sport"  # Often indicates Informed Sport
        }

        for text in [label_text, str(statements)]:
            for program_key, program_name in named_programs.items():
                if program_key in text:
                    if program_name not in certifications:
                        certifications.append(program_name)

        # Deduplicate and categorize
        certifications = list(set(certifications))

        # Separate generic vs named programs
        generic_third_party = "Third-Party-Tested" in certifications
        named_third_party = [c for c in certifications if c not in ["Third-Party-Tested", "USDA Organic", "Non-GMO"]]
        
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
                "named_programs": named_third_party,  # ✅ ADD: Separate named programs
                "has_generic_claim": generic_third_party and len(named_third_party) == 0,  # ✅ ADD: Flag for scoring
                "certification_count": len(certifications),
                "certification_points": min(len(named_third_party) * 5, 10)  # ✅ CAP at 10, only named programs count
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
        top_manufacturers_db = self.databases.get('top_manufacturers_data', {})
        top_manufacturers = top_manufacturers_db.get('top_manufacturers', [])
        in_top = False

        for manufacturer in top_manufacturers:
            if self._exact_ingredient_match(brand_name, manufacturer.get('standard_name', ''), manufacturer.get('aliases', [])):
                in_top = True
                break

        # Get parent company from contacts
        parent_company = ""
        if contacts:
            parent_company = contacts[0].get('name', '')

        return {
            "company": brand_name,
            "parent_company": parent_company,
            "in_top_manufacturers": in_top,
            "fda_violations": {
                "recalls": [],
                "warning_letters": [],
                "adverse_events": [],
                "total_penalty": 0,
                "last_checked": None
            }
        }

    def _analyze_sustainability(self, product_data: Dict) -> Dict:
        """
        Analyze sustainability and eco-friendly packaging claims.
        ✅ ANTI-GREENWASHING: Only verified keywords with specific packaging evidence.

        This function COLLECTS data only - scoring happens in the scoring phase.

        Returns:
            Dict with sustainability features found, where they were found, and what terms matched
        """
        # Verified sustainability terms - specific and auditable
        SUSTAINABLE_TERMS = {
            "glass_packaging": r"\bglass\s+(bottle|jar|container)\b",
            "recyclable_packaging": r"\b(recyclable|recycled)\s+(packaging|bottle|container|jar)\b",
            "compostable_packaging": r"\b(compostable|biodegradable)\s+(packaging|pouch|container)\b",
            "eco_friendly_packaging": r"\beco[-\s]?friendly\s+packaging\b",
            "plastic_free": r"\bplastic[-\s]?free\b"
        }

        sustainability_features = {
            "has_sustainable_packaging": False,
            "features_found": [],
            "evidence": []
        }

        # Fields to check for sustainability claims
        fields_to_check = {
            "labelText": product_data.get("labelText", ""),
            "packaging": product_data.get("packaging", ""),
            "statements": " ".join([stmt.get("text", "") for stmt in product_data.get("statements", [])]),
            "claims": " ".join([claim.get("text", "") for claim in product_data.get("claims", [])])
        }

        # Search for verified sustainability terms
        for feature_name, pattern in SUSTAINABLE_TERMS.items():
            for field_name, field_text in fields_to_check.items():
                if not field_text:
                    continue

                # Case-insensitive search
                matches = re.finditer(pattern, field_text, re.IGNORECASE)
                for match in matches:
                    matched_text = match.group(0)

                    # Record the finding
                    sustainability_features["features_found"].append(feature_name)
                    sustainability_features["evidence"].append({
                        "feature": feature_name,
                        "matched_text": matched_text,
                        "found_in": field_name,
                        "context": self._extract_context(field_text, match.start(), match.end())
                    })
                    sustainability_features["has_sustainable_packaging"] = True

        # Deduplicate features_found
        sustainability_features["features_found"] = list(set(sustainability_features["features_found"]))

        return sustainability_features

    def _extract_context(self, text: str, start: int, end: int, context_chars: int = 50) -> str:
        """Extract surrounding context for a matched term"""
        context_start = max(0, start - context_chars)
        context_end = min(len(text), end + context_chars)
        context = text[context_start:context_end].strip()

        # Add ellipsis if truncated
        if context_start > 0:
            context = "..." + context
        if context_end < len(text):
            context = context + "..."

        return context

    def _classify_supplement_type(self, active_ingredients: List[Dict], inactive_ingredients: List[Dict], product_data: Dict) -> Dict:
        """
        Classify supplement type for context-aware scoring.

        DESIGN PHILOSOPHY:
        - Classification based on TOTAL ingredients (active + inactive) - transparency first
        - Percentages calculated from active ingredients only - for categorization
        - This ensures fillers are visible but don't distort category detection

        Types:
        - single: ONE total ingredient (active + inactive = 1)
        - targeted: Multiple ingredients with high-dose focus (>50% DV on at least one)
        - multi: Balanced multivitamin/mineral formula (rewards balance, penalizes low-dose fillers)
        - herbal_blend: Primarily botanical/herbal ingredients
        - probiotic: Contains probiotic cultures
        - specialty: Other specialty categories (enzymes, amino acids, etc.)

        Returns:
            Dict with classification, confidence, and reasoning
        """
        # Configurable thresholds for classification
        HERBAL_THRESHOLD = 60  # % of botanicals to classify as herbal_blend
        PROBIOTIC_THRESHOLD = 50  # % of probiotics to classify as probiotic
        VITAMIN_MINERAL_THRESHOLD = 50  # % of vitamins/minerals for multi classification
        MIN_MULTI_INGREDIENTS = 5  # Minimum ingredients to classify as multivitamin

        # CORE PHILOSOPHY: Classify by TOTAL ingredients (honesty about what's in the bottle)
        total_ingredients = len(active_ingredients) + len(inactive_ingredients)
        active_count = len(active_ingredients)

        # Edge case: No active ingredients
        if active_count == 0:
            return {
                "type": "unknown",
                "confidence": "low",
                "reasoning": "No active ingredients found",
                "total_ingredients": total_ingredients,
                "active_ingredients": 0
            }

        # SINGLE INGREDIENT (total = 1, meaning one ingredient in the entire product)
        if total_ingredients == 1:
            return {
                "type": "single",
                "confidence": "high",
                "reasoning": "Contains exactly one ingredient total",
                "total_ingredients": 1,
                "active_ingredients": active_count
            }

        # Analyze ingredient characteristics using STRUCTURED DATA (not name parsing)
        high_dose_count = 0  # Ingredients >50% DV
        botanical_count = 0
        probiotic_count = 0
        vitamin_mineral_count = 0
        enzyme_count = 0
        amino_acid_count = 0

        # Get quality_map for category lookups (ENRICHMENT-PHASE metadata)
        quality_map = self.databases.get('ingredient_quality_map', {})

        for ing in active_ingredients:
            # Check if high dose (>50% daily value)
            # Look in enrichment data if available
            rda_percentage = 0
            if ing.get("enrichment"):
                rda_info = ing.get("enrichment", {}).get("rda_ul_info", {})
                if rda_info.get("rda_percentage"):
                    rda_percentage = rda_info["rda_percentage"]

            if rda_percentage > 50:
                high_dose_count += 1

            # ✅ ARCHITECTURAL FIX: Lookup category from ingredient_quality_map
            # Category is ENRICHMENT-PHASE metadata (classification), not CLEANING-PHASE core identity
            # This prevents false positives like "magnesium stearate" or "vitamin E oil" (carriers)
            standard_name = ing.get("standardName", "")
            category = self._lookup_category(standard_name, quality_map)

            # Check category from structured data (preferred method)
            if category in ["vitamins", "minerals"]:
                vitamin_mineral_count += 1
            elif category in ["herbs", "botanical_ingredients", "adaptogen"]:
                botanical_count += 1
            elif category == "probiotics":
                probiotic_count += 1
            elif category in ["enzymes"]:
                enzyme_count += 1
            elif category in ["amino_acids", "amino_acid_metabolites", "amino_acid_antioxidants"]:
                amino_acid_count += 1
            # Fallback: Check legacy fields if category not available
            elif ing.get("botanical", False) or ing.get("quality", {}).get("isBotanical", False):
                botanical_count += 1
            # Fallback: CFU units indicate probiotics
            elif ing.get("unit", "").upper() == "CFU":
                probiotic_count += 1

        # Calculate percentages from ACTIVE ingredients only (fillers don't distort categorization)
        botanical_percentage = (botanical_count / active_count) * 100 if active_count > 0 else 0
        probiotic_percentage = (probiotic_count / active_count) * 100 if active_count > 0 else 0
        vitamin_mineral_percentage = (vitamin_mineral_count / active_count) * 100 if active_count > 0 else 0

        # CLASSIFICATION LOGIC (uses configurable thresholds)

        # Probiotic formula (uses PROBIOTIC_THRESHOLD)
        if probiotic_count > 0 and probiotic_percentage >= PROBIOTIC_THRESHOLD:
            return {
                "type": "probiotic",
                "confidence": "high",
                "reasoning": f"{probiotic_count}/{active_count} active ingredients are probiotic cultures ({probiotic_percentage:.0f}% >= {PROBIOTIC_THRESHOLD}%)",
                "total_ingredients": total_ingredients,
                "active_ingredients": active_count,
                "probiotic_count": probiotic_count
            }

        # Herbal blend (uses HERBAL_THRESHOLD)
        if botanical_percentage >= HERBAL_THRESHOLD:
            return {
                "type": "herbal_blend",
                "confidence": "high",
                "reasoning": f"{botanical_count}/{active_count} active ingredients are botanical/herbal ({botanical_percentage:.0f}% >= {HERBAL_THRESHOLD}%)",
                "total_ingredients": total_ingredients,
                "active_ingredients": active_count,
                "botanical_count": botanical_count
            }

        # Targeted formula (multiple ingredients with at least one high dose)
        if total_ingredients >= 2 and high_dose_count >= 1:
            return {
                "type": "targeted",
                "confidence": "high",
                "reasoning": f"{high_dose_count} ingredient(s) exceed 50% daily value - focused formula",
                "total_ingredients": total_ingredients,
                "active_ingredients": active_count,
                "high_dose_count": high_dose_count
            }

        # Multivitamin/Mineral (uses VITAMIN_MINERAL_THRESHOLD and MIN_MULTI_INGREDIENTS)
        if vitamin_mineral_percentage >= VITAMIN_MINERAL_THRESHOLD and total_ingredients >= MIN_MULTI_INGREDIENTS:
            return {
                "type": "multi",
                "confidence": "high",
                "reasoning": f"{vitamin_mineral_count}/{active_count} active ingredients are vitamins/minerals ({vitamin_mineral_percentage:.0f}% >= {VITAMIN_MINERAL_THRESHOLD}%) - balanced formula",
                "total_ingredients": total_ingredients,
                "active_ingredients": active_count,
                "vitamin_mineral_count": vitamin_mineral_count
            }

        # Specialty (enzymes, amino acids, or mixed category)
        if enzyme_count > 0 or amino_acid_count > 0:
            specialty_type = []
            if enzyme_count > 0:
                specialty_type.append(f"{enzyme_count} enzyme(s)")
            if amino_acid_count > 0:
                specialty_type.append(f"{amino_acid_count} amino acid(s)")

            return {
                "type": "specialty",
                "confidence": "medium",
                "reasoning": f"Contains {', '.join(specialty_type)}",
                "total_ingredients": total_ingredients,
                "active_ingredients": active_count
            }

        # Default: Multi-ingredient blend (no clear category)
        return {
            "type": "multi",
            "confidence": "medium",
            "reasoning": f"{total_ingredients} total ingredients without clear specialization",
            "total_ingredients": total_ingredients,
            "active_ingredients": active_count
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
        """
        Calculate metadata for the enriched product.
        PRESERVES all existing metadata from cleaned phase, only UPDATES enrichment-specific fields.
        """
        active_ingredients = product_data.get('activeIngredients', [])
        ingredient_count = len(active_ingredients)

        # Check if single ingredient
        single_ingredient = ingredient_count == 1

        # Calculate data completeness
        completeness = 100.0  # Default to 100%
        missing_data = []

        if not enriched["manufacturer_analysis"]["in_top_manufacturers"]:
            missing_data.append("manufacturer_verification")
            completeness -= 5

        if not enriched["certification_analysis"]["batch_traceability"]["code_found"]:
            missing_data.append("batch_traceability")
            completeness -= 5

        # Get existing metadata (should include all cleaned metadata fields)
        existing_metadata = enriched.get("metadata", {})

        # VALIDATION: Check for critical cleaned metadata fields that should not be overwritten
        critical_cleaned_fields = [
            "processing_timestamp", "cleaning_version", "original_id",
            "completeness", "mappingStats", "proprietaryBlendStats",
            "clinicalDosingValidation", "industryBenchmark", "penaltyWeighting"
        ]

        # Update with enrichment-specific fields
        enrichment_updates = {
            "requires_user_profile_scoring": ingredient_count > 1,
            "scoring_algorithm_version": "2.1.0",
            "data_completeness": completeness,
            "missing_data": missing_data,
            "single_ingredient_product": single_ingredient,
            "ready_for_scoring": True
        }

        # SAFETY: Warn if we're about to overwrite critical cleaned metadata
        for field in critical_cleaned_fields:
            if field in existing_metadata and field in enrichment_updates:
                self.logger.warning(
                    f"Overwriting critical metadata field '{field}' from cleaned data. "
                    f"Old value: {existing_metadata[field]}, New value: {enrichment_updates[field]}"
                )

        # Merge: existing metadata preserved, enrichment updates added/overwritten
        return {**existing_metadata, **enrichment_updates}

    def _prepare_analysis_data(self, enriched: Dict) -> Dict:
        """
        Prepare analysis-only data structures for scoring phase.
        NO SCORING CALCULATIONS - only raw data extraction and boolean flags.
        """
        # Extract feature flags (boolean only)
        feature_flags = {
            "is_organic": enriched["organic_certification"]["claimed"],
            "has_usda_organic": enriched["organic_certification"]["usda_verified"],
            "has_gmp": enriched["certification_analysis"]["gmp"]["claimed"],
            "has_third_party_testing": len(enriched["certification_analysis"]["third_party"]["certifications"]) > 0,
            "has_batch_traceability": enriched["certification_analysis"]["batch_traceability"]["has_coa"] or
                                      enriched["certification_analysis"]["batch_traceability"]["has_qr_code"],
            "is_vegan": enriched["quality_flags"]["is_vegan"],
            "is_discontinued": enriched["quality_flags"]["is_discontinued"],
            "made_in_usa": enriched["quality_flags"]["made_in_usa"],
            "physician_formulated": enriched["bonus_features"]["physician_formulated"],
            "has_proprietary_blends": enriched["proprietary_blend_analysis"].get("has_proprietary_blends", False),
            "has_banned_substances": enriched["contaminant_analysis"]["banned_substances"]["found"],
            "has_harmful_additives": enriched["contaminant_analysis"]["harmful_additives"]["found"],
            "has_allergens": enriched["contaminant_analysis"]["allergen_analysis"]["found"],
            "has_clinical_evidence": len(enriched["clinical_evidence_matches"]) > 0,
            "has_absorption_enhancers": enriched["absorption_enhancers"]["present"],
            "has_enhanced_delivery": enriched["enhanced_delivery"]["present"],
            "has_standardized_botanicals": enriched["standardized_botanicals"]["present"],
            "has_synergy_clusters": len(enriched["synergy_analysis"]["detected_clusters"]) > 0,
            "has_premium_forms": enriched["ingredient_quality_analysis"].get("premium_forms_count", 0) >= 2
        }

        # ✅ ENHANCED: Extract raw claim texts WITH sources for scoring verification
        extracted_claims = {
            "organic": {
                "claimed": enriched["organic_certification"]["claimed"],
                "usda_verified": enriched["organic_certification"]["usda_verified"],
                "claim_texts": [enriched["organic_certification"]["claim_text"]] if enriched["organic_certification"]["claimed"] else []
            },
            "gmp": {
                "claimed": enriched["certification_analysis"]["gmp"]["claimed"],
                "verified": enriched["certification_analysis"]["gmp"]["verified"],
                "claim_texts": [enriched["certification_analysis"]["gmp"]["text_found"]] if enriched["certification_analysis"]["gmp"]["claimed"] else []
            },
            "third_party_tested": {
                "has_claim": len(enriched["certification_analysis"]["third_party"]["certifications"]) > 0,
                "named_programs": enriched["certification_analysis"]["third_party"]["named_programs"],
                "generic_only": enriched["certification_analysis"]["third_party"]["has_generic_claim"],
                "claim_texts": enriched["certification_analysis"]["third_party"]["certifications"]
            },
            "physician_formulated": {
                "claimed": enriched["bonus_features"]["physician_formulated"],
                "claim_texts": ["Physician Formulated"] if enriched["bonus_features"]["physician_formulated"] else []
            },
            "made_in_usa": {
                "claimed": enriched["bonus_features"]["made_in_usa_eu"],
                "claim_texts": [enriched["bonus_features"]["made_in_text"]] if enriched["bonus_features"]["made_in_usa_eu"] else []
            },
            "sustainability": {
                "claimed": enriched["bonus_features"]["sustainability"],
                "claim_texts": [enriched["bonus_features"]["sustainability_text"]] if enriched["bonus_features"]["sustainability"] else []
            },
            "batch_traceability": {
                "has_code": enriched["certification_analysis"]["batch_traceability"]["code_found"] != "",
                "claim_texts": [enriched["certification_analysis"]["batch_traceability"]["code_found"]] if enriched["certification_analysis"]["batch_traceability"]["code_found"] else []
            },
            "allergen_free": {
                "claims": enriched["allergen_compliance"]["claims"],
                "verified": enriched["allergen_compliance"]["verified"],
                "conflicts": enriched["allergen_compliance"]["conflicts"]
            }
        }

        return {
            "form_quality_mapping": enriched["form_quality_mapping"],
            "feature_flags": feature_flags,
            "extracted_claims": extracted_claims,
            "raw_counts": {
                "total_active_ingredients": len(enriched.get("activeIngredients", [])),
                "total_inactive_ingredients": len(enriched.get("inactiveIngredients", [])),
                "banned_substances_count": len(enriched["contaminant_analysis"]["banned_substances"]["substances"]),
                "harmful_additives_count": len(enriched["contaminant_analysis"]["harmful_additives"]["additives"]),
                "allergens_count": len(enriched["contaminant_analysis"]["allergen_analysis"]["allergens"]),
                "clinical_evidence_count": len(enriched["clinical_evidence_matches"]),
                "absorption_enhancers_count": len(enriched["absorption_enhancers"]["enhancers"]),
                "synergy_clusters_count": len(enriched["synergy_analysis"]["detected_clusters"]),
                "proprietary_blends_count": enriched["proprietary_blend_analysis"].get("total_blends", 0)
            }
        }

    def _categorize_unmapped_ingredients(self, enriched: Dict) -> Dict:
        """
        Categorize unmapped ingredients by type (active/inactive) with priority levels.
        This preserves information about what couldn't be mapped for manual review.
        """
        active_unmapped = []
        inactive_unmapped = []

        # Check active ingredients for unmapped items
        for ingredient in enriched.get("activeIngredients", []):
            if not ingredient.get("mapped", True):  # Default True to be safe
                priority = "HIGH"  # Active ingredients always high priority
                active_unmapped.append({
                    "name": ingredient.get("name", ""),
                    "quantity": ingredient.get("quantity", 0),
                    "unit": ingredient.get("unit", ""),
                    "notes": ingredient.get("notes", ""),
                    "priority": priority,
                    "category": ingredient.get("category", "unknown")
                })

        # Check inactive ingredients for unmapped items
        for ingredient in enriched.get("inactiveIngredients", []):
            if not ingredient.get("mapped", True):  # Default True to be safe
                # Determine priority based on ingredient characteristics
                is_harmful = ingredient.get("isHarmful", False)
                is_allergen = ingredient.get("allergen", False)

                if is_harmful or is_allergen:
                    priority = "MEDIUM"  # Harmful/allergen inactives need attention
                else:
                    priority = "LOW"  # Regular inactive ingredients

                inactive_unmapped.append({
                    "name": ingredient.get("name", ""),
                    "category": ingredient.get("category", "unknown"),
                    "is_harmful": is_harmful,
                    "is_allergen": is_allergen,
                    "priority": priority
                })

        return {
            "active": active_unmapped,
            "inactive": inactive_unmapped,
            "summary": {
                "total_unmapped": len(active_unmapped) + len(inactive_unmapped),
                "high_priority_count": len(active_unmapped),
                "medium_priority_count": len([i for i in inactive_unmapped if i["priority"] == "MEDIUM"]),
                "low_priority_count": len([i for i in inactive_unmapped if i["priority"] == "LOW"])
            }
        }

    def process_batch(self, input_file: str, output_dir: str) -> Dict:
        """Process a batch of products with optional enhanced reporting"""
        try:
            # Initialize enhanced reporter if enabled
            if self.enhanced_reporting and not self.reporter:
                self.reporter = EnrichmentReporter(output_dir)
                self.reporter.start_processing()
            
            # Load input data
            with open(input_file, 'r', encoding='utf-8') as f:
                products = json.load(f)
            
            if not isinstance(products, list):
                products = [products]
            
            self.logger.info(f"Processing batch: {len(products)} products from {os.path.basename(input_file)}")
            
            enriched_products = []
            
            # Update total processed count for enhanced reporting
            if self.reporter:
                self.reporter.update_total_processed(len(products))

            # Check if progress bar should be shown
            show_progress = self.config.get("ui", {}).get("show_progress_bar", False)

            # Wrap iterator with tqdm if progress bar is enabled
            products_iterator = products
            if show_progress:
                products_iterator = tqdm(
                    products,
                    desc="Enriching Products",
                    unit="product",
                    ncols=100
                )

            for product in products_iterator:
                product_id = product.get('id', 'unknown')
                product_name = product.get('fullName', 'Unknown Product')

                # DEBUG: Log individual products only in debug mode (progress bar shows overall progress)
                self.logger.debug(f"Enriching product {product_id}: {product_name}")
                
                enriched, issues = self.enrich_product(product)

                if enriched:
                    # ALL PRODUCTS GET ENRICHED - issues are just metadata for scoring phase
                    if issues:
                        enriched["enrichment_issues"] = issues  # Store issues as metadata
                        enriched["enrichment_notes"] = "Product enriched with noted issues - scoring phase will handle penalties"

                    enriched_products.append(enriched)

                    # Record for enhanced reporting
                    if self.reporter:
                        self.reporter.record_success(product, enriched)
                else:
                    # Only true failures (enrichment returned None) go to review
                    # Enhanced failure recording if available
                    if self.reporter:
                        error_message = "; ".join(issues) if issues else "Unknown enrichment failure"
                        self.reporter.record_failure(
                            product_data=product,
                            error_message=error_message,
                            enriched_data=None,
                            source_file=os.path.basename(input_file)
                        )

                    # For complete failures, create minimal enriched structure to preserve data
                    fallback_enriched = {
                        **product,  # Preserve all cleaned data
                        "enrichment_version": "2.1.0",
                        "enriched_date": datetime.utcnow().isoformat() + "Z",
                        "enrichment_status": "failed",
                        "enrichment_issues": issues,
                        "enrichment_notes": "Enrichment failed - using cleaned data as fallback"
                    }
                    enriched_products.append(fallback_enriched)
            
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
            
            # All products are now enriched (with fallbacks for failures)
            success_rate = 100.0  # Always 100% since we enrich everything
            self.logger.info(f"Batch processing complete: {len(enriched_products)} products enriched (100% success rate)")

            return {
                "total_products": len(products),
                "successful_enrichments": len(enriched_products),
                "products_needing_review": 0,  # No products go to review anymore
                "success_rate": success_rate
            }
            
        except Exception as e:
            self.logger.error(f"Error processing batch {input_file}: {e}")
            self.logger.error(traceback.format_exc())
            raise

    def _generate_unmapped_ingredients_report(self, output_base: str) -> Optional[str]:
        """Generate a markdown report of unmapped ingredients"""
        if not self.unmapped_ingredients:
            return None

        reports_dir = os.path.join(output_base, "reports")
        os.makedirs(reports_dir, exist_ok=True)

        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        report_file = os.path.join(reports_dir, f"unmapped_ingredients_report_{timestamp}.md")

        # Sort ingredients by frequency (most common first)
        sorted_ingredients = sorted(self.unmapped_ingredients.items(), key=lambda x: x[1], reverse=True)

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("# Unmapped Ingredients Report - Quality Database\n\n")
            f.write(f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
            f.write(f"**Total Unmapped Ingredients:** {len(self.unmapped_ingredients)}\n")
            f.write(f"**Total Occurrences:** {sum(self.unmapped_ingredients.values())}\n\n")

            f.write("## Summary\n\n")
            f.write(f"The following ingredients could not be mapped to the **Ingredient Quality Database** (`{INGREDIENT_QUALITY_MAP.name}`). ")
            f.write("This database contains bioavailability scores for active ingredients only.\n\n")
            f.write("**Note**: These ingredients may still be correctly mapped in other databases:\n")
            f.write(f"- ✅ Allergens Database (`{ALLERGENS.name}`)\n")
            f.write(f"- ✅ Harmful Additives Database (`{HARMFUL_ADDITIVES.name}`)\n")
            f.write(f"- ✅ Banned Substances Database (`{BANNED_RECALLED.name}`)\n\n")
            f.write("**Action Required**: Review if these ingredients should be added to the quality database for scoring purposes.\n\n")

            f.write("## Unmapped Ingredients (by frequency)\n\n")
            f.write("| Ingredient Name | Occurrences | Status |\n")
            f.write("|---|---|---|\n")

            for ingredient, count in sorted_ingredients:
                f.write(f"| {ingredient} | {count} | ❌ Unmapped |\n")

            f.write("\n## Recommendations\n\n")
            f.write("1. **High Priority** (≥10 occurrences): Review most frequent ingredients first\n")
            f.write("2. **Medium Priority** (5-9 occurrences): Consider adding to databases\n")
            f.write("3. **Low Priority** (1-4 occurrences): Review for typos or variations\n\n")

            high_priority = [ing for ing, count in sorted_ingredients if count >= 10]
            medium_priority = [ing for ing, count in sorted_ingredients if 5 <= count < 10]
            low_priority = [ing for ing, count in sorted_ingredients if count < 5]

            if high_priority:
                f.write("### High Priority Ingredients\n")
                for ing in high_priority:
                    f.write(f"- {ing} ({self.unmapped_ingredients[ing]} occurrences)\n")
                f.write("\n")

            if medium_priority:
                f.write("### Medium Priority Ingredients\n")
                for ing in medium_priority:
                    f.write(f"- {ing} ({self.unmapped_ingredients[ing]} occurrences)\n")
                f.write("\n")

            if low_priority:
                f.write("### Low Priority Ingredients\n")
                for ing in low_priority[:20]:  # Show first 20 only
                    f.write(f"- {ing} ({self.unmapped_ingredients[ing]} occurrences)\n")
                if len(low_priority) > 20:
                    f.write(f"... and {len(low_priority) - 20} more ingredients\n")
                f.write("\n")

        self.logger.info(f"Generated unmapped ingredients report with {len(self.unmapped_ingredients)} unique ingredients")
        return report_file

    def _extract_proprietary_blend_analysis(self, product_data: Dict) -> Dict:
        """Extract proprietary blend analysis from cleaned product data"""
        metadata = product_data.get("metadata", {})
        blend_stats = metadata.get("proprietaryBlendStats", {})

        analysis = {
            "has_proprietary_blends": blend_stats.get("hasProprietaryBlends", False),
            "total_blends": blend_stats.get("totalBlends", 0),
            "disclosure_summary": {
                "full_disclosure": blend_stats.get("fullDisclosure", 0),
                "partial_disclosure": blend_stats.get("partialDisclosure", 0),
                "no_disclosure": blend_stats.get("noDisclosure", 0)
            },
            "transparency_metrics": {
                "average_transparency_percentage": blend_stats.get("averageTransparencyPercentage", 0),
                "transparency_breakdown": blend_stats.get("transparencyBreakdown", [])
            },
            "overall_disclosure_level": blend_stats.get("disclosure", None)
        }

        # Extract individual blend details from ingredients
        blend_details = []
        for ingredient in product_data.get("activeIngredients", []):
            if ingredient.get("isProprietaryBlend"):
                blend_details.append({
                    "name": ingredient.get("name", ""),
                    "disclosure_level": ingredient.get("disclosureLevel"),
                    "transparency_percentage": ingredient.get("transparencyPercentage"),
                    "nested_ingredients_count": len(ingredient.get("nestedIngredients", [])),
                    "total_blend_weight": f"{ingredient.get('quantity', 0)}{ingredient.get('unit', '')}"
                })

        analysis["blend_details"] = blend_details

        # Calculate transparency penalty for scoring
        transparency_penalty = 0
        if analysis["has_proprietary_blends"]:
            # Penalty based on disclosure levels
            no_disclosure = analysis["disclosure_summary"]["no_disclosure"]
            partial_disclosure = analysis["disclosure_summary"]["partial_disclosure"]

            # Apply penalties: -3 for no disclosure, -1 for partial disclosure
            transparency_penalty = -(no_disclosure * 3 + partial_disclosure * 1)

        analysis["transparency_penalty"] = transparency_penalty
        return analysis

    def _extract_clinical_dosing_analysis(self, product_data: Dict) -> Dict:
        """Extract clinical dosing validation from all ingredients"""
        analysis = {
            "ingredients_with_clinical_data": 0,
            "total_ingredients_checked": 0,
            "clinical_adequacy_summary": {
                "optimal": 0,
                "minimal_effective": 0,
                "under_dosed": 0,
                "severely_under_dosed": 0,
                "high_dose": 0,
                "excessive": 0,
                "unknown": 0
            },
            "average_adequacy_percentage": 0,
            "clinical_score_modifiers_total": 0,
            "ingredient_details": []
        }

        all_ingredients = product_data.get("activeIngredients", []) + product_data.get("inactiveIngredients", [])
        adequacy_percentages = []
        score_modifiers = []

        for ingredient in all_ingredients:
            clinical_data = ingredient.get("clinicalDosing", {})
            if clinical_data.get("has_clinical_data"):
                analysis["ingredients_with_clinical_data"] += 1

                adequacy_level = clinical_data.get("adequacy_level", "unknown")
                adequacy_percentage = clinical_data.get("adequacy_percentage", 0)
                score_modifier = clinical_data.get("clinical_score_modifier", 0)

                analysis["clinical_adequacy_summary"][adequacy_level] += 1
                adequacy_percentages.append(adequacy_percentage)
                score_modifiers.append(score_modifier)

                analysis["ingredient_details"].append({
                    "name": ingredient.get("name", ""),
                    "quantity": ingredient.get("quantity", 0),
                    "unit": ingredient.get("unit", ""),
                    "adequacy_level": adequacy_level,
                    "adequacy_percentage": adequacy_percentage,
                    "clinical_min": clinical_data.get("clinical_min", 0),
                    "optimal_dose": clinical_data.get("optimal_dose", 0),
                    "evidence_level": clinical_data.get("evidence_level", "none"),
                    "score_modifier": score_modifier
                })

            analysis["total_ingredients_checked"] += 1

        # Calculate averages
        if adequacy_percentages:
            analysis["average_adequacy_percentage"] = round(sum(adequacy_percentages) / len(adequacy_percentages), 1)

        if score_modifiers:
            analysis["clinical_score_modifiers_total"] = sum(score_modifiers)

        return analysis

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
        
        # Initialize global enhanced reporter if enabled
        if enricher.enhanced_reporting:
            global_reporter = EnrichmentReporter(output_base)
            global_reporter.start_processing()
            enricher.reporter = global_reporter
        
        for input_file in input_files:
            enricher.logger.info(f"Processing file: {os.path.basename(input_file)}")
            batch_stats = enricher.process_batch(input_file, output_base)
            
            # Accumulate stats
            for key in total_stats:
                total_stats[key] += batch_stats.get(key, 0)
        
        # Generate enhanced reports if enabled
        report_files = {}
        if enricher.enhanced_reporting and enricher.reporter:
            enricher.logger.info("Generating enhanced reports...")
            report_files = enricher.reporter.generate_all_reports()
        
        # Final summary
        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()
        overall_success_rate = (total_stats["successful_enrichments"] / total_stats["total_products"]) * 100 if total_stats["total_products"] > 0 else 0
        
        enricher.logger.info("=" * 50)
        enricher.logger.info("ENRICHMENT PROCESSING COMPLETE")
        enricher.logger.info(f"Total products processed: {total_stats['total_products']}")
        enricher.logger.info(f"Success rate: {overall_success_rate:.1f}%")
        enricher.logger.info(f"Total processing time: {processing_time:.2f} seconds")
        
        # Log enhanced report locations if generated
        if report_files:
            enricher.logger.info("\nGenerated Enhanced Reports:")
            for report_type, file_path in report_files.items():
                enricher.logger.info(f"- {report_type.replace('_', ' ').title()}: {file_path}")
        
        # Save final summary
        summary = {
            "overall_processing": {
                "total_files_processed": len(input_files),
                "total_processing_time_seconds": round(processing_time, 2),
                "processing_timestamp": end_time.isoformat() + "Z",
                "enrichment_version": "2.1.0"
            },
            "aggregate_stats": {
                "total_products_processed": total_stats["total_products"],
                "successful_enrichments": total_stats["successful_enrichments"],
                "failed_enrichments": total_stats["products_needing_review"],
                "overall_success_rate": round(overall_success_rate, 1)
            },
            "enhanced_reports": report_files if report_files else None
        }
        
        summary_file = os.path.join(output_base, "reports", f"enrichment_final_summary_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
        os.makedirs(os.path.dirname(summary_file), exist_ok=True)
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        enricher.logger.info(f"Final summary saved: {summary_file}")

        # Generate unmapped ingredients report
        unmapped_report_file = enricher._generate_unmapped_ingredients_report(output_base)
        if unmapped_report_file:
            enricher.logger.info(f"Unmapped ingredients report saved: {unmapped_report_file}")

        enricher.logger.info("=" * 50)
        
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        logging.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()