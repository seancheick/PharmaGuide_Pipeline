"""
Enhanced DSLD Data Normalizer Module
Improved ingredient mapping with fuzzy matching, better preprocessing, and expanded aliases
"""
import re
import json
import logging
import string
import os
import functools
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Import fuzzy matching with fallback
try:
    from fuzzywuzzy import fuzz, process
    FUZZY_AVAILABLE = True
except ImportError:
    from difflib import SequenceMatcher
    FUZZY_AVAILABLE = False
    print("⚠️ fuzzywuzzy not found. Install for better matching: pip install fuzzywuzzy python-levenshtein")

from constants import (
    INGREDIENT_QUALITY_MAP,
    HARMFUL_ADDITIVES,
    OTHER_INGREDIENTS,  # Merged: non_harmful + passive_inactive
    ALLERGENS,
    TOP_MANUFACTURERS,
    PROPRIETARY_BLENDS,
    EXCLUDED_NUTRITION_FACTS,
    EXCLUDED_LABEL_PHRASES,
    STANDARDIZED_BOTANICALS,
    BANNED_RECALLED,
    BOTANICAL_INGREDIENTS,
    ABSORPTION_ENHANCERS,
    ENHANCED_DELIVERY,
    RDA_OPTIMAL_ULS,
    RDA_THERAPEUTIC_DOSING,
    UNIT_CONVERSIONS,
    FUZZY_MATCHING_THRESHOLDS,
    SCORING_CONSTANTS,
    EVIDENCE_SCORING,
    UNIT_ALIASES,
    ENHANCED_EXCLUSION_PATTERNS,
    DSLD_IMAGE_URL_TEMPLATE,
    CERTIFICATION_PATTERNS,
    ALLERGEN_FREE_PATTERNS,
    UNSUBSTANTIATED_CLAIM_PATTERNS,
    NATURAL_SOURCE_PATTERNS,
    STANDARDIZATION_PATTERNS,
    PROPRIETARY_BLEND_INDICATORS,
    DELIVERY_ENHANCEMENT_PATTERNS,
    CLINICAL_EVIDENCE_PATTERNS,
    FORM_QUALIFIERS,
    DEFAULT_SERVING_SIZE,
    DEFAULT_DAILY_SERVINGS,
    EXCLUDED_NUTRITION_FACTS
)

# Import the UnmappedIngredientTracker
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unmapped_ingredient_tracker import UnmappedIngredientTracker
from functional_grouping_handler import FunctionalGroupingHandler

logger = logging.getLogger(__name__)


class EnhancedIngredientMatcher:
    """Enhanced ingredient matching with fuzzy logic and comprehensive preprocessing"""

    def __init__(self):
        # SAFETY FIRST: Increased thresholds for critical ingredient matching
        self.fuzzy_threshold = FUZZY_MATCHING_THRESHOLDS["fuzzy_threshold"]
        self.partial_threshold = FUZZY_MATCHING_THRESHOLDS["partial_threshold"]
        self.minimum_fuzzy_length = FUZZY_MATCHING_THRESHOLDS["minimum_fuzzy_length"]

        # SAFETY: Whitelist of categories where fuzzy matching is safe
        self.safe_fuzzy_categories = {
            "botanical",  # Herb names often have spelling variations
            "flavor",     # Natural flavors, artificial flavors
            "color",      # Natural colors, artificial colors
            "inactive",   # Non-critical inactive ingredients
            "excipient"   # Manufacturing aids, generally safe to fuzzy match
        }

        # CRITICAL SAFETY: Comprehensive blacklist - pairs that should NEVER be matched
        self.fuzzy_blacklist = {
            # (query_pattern, target_pattern) - if query matches first and target matches second, reject
            
            # === CRITICAL SAFETY: Natural vs Synthetic ===
            ("natural", "artificial"),  # Natural vs Artificial anything
            ("organic", "synthetic"),   # Organic vs Synthetic
            ("whole", "isolated"),       # Whole food vs Isolated
            ("extract", "synthetic"),    # Natural extract vs Synthetic
            
            # === CRITICAL SAFETY: Different Food Sources ===
            ("corn starch", "corn syrup"),  # Different corn products
            ("corn flour", "corn syrup"),   # Different corn products
            ("wheat flour", "wheat protein"),  # Different wheat products
            ("soy oil", "soy protein"),     # Different soy products
            ("milk powder", "milk protein"), # Different milk products
            ("rice bran", "rice protein"),  # Different rice products
            ("pea fiber", "pea protein"),   # Different pea products
            
            # === CRITICAL SAFETY: Sugars vs Sugar Alcohols ===
            ("sugar", "sugar alcohol"),     # Sugar vs Sugar alcohols
            ("glucose", "mannitol"),        # Sugar vs Sugar alcohol
            ("glucose", "sorbitol"),        # Sugar vs Sugar alcohol
            ("fructose", "erythritol"),     # Sugar vs Sugar alcohol
            ("sucrose", "xylitol"),         # Sugar vs Sugar alcohol
            
            # === CRITICAL SAFETY: Vitamin Forms (Different Bioavailability) ===
            ("vitamin d", "vitamin d2"),    # D vs D2 (different forms)
            ("vitamin d", "vitamin d3"),    # D vs D3 (different forms)
            ("vitamin b12", "methylcobalamin"), # Different B12 forms
            ("vitamin b12", "cyanocobalamin"), # Different B12 forms
            ("vitamin k", "vitamin k2"),    # Different K forms
            ("vitamin e", "alpha tocopherol"), # Different E forms
            ("folate", "folic acid"),       # Natural vs synthetic
            ("beta carotene", "vitamin a"), # Precursor vs vitamin
            
            # === CRITICAL SAFETY: Fatty Acids (Different Benefits) ===
            ("omega 3", "omega 6"),         # Different omega fatty acids
            ("omega 3", "omega 9"),         # Different omega fatty acids
            ("epa", "dha"),                 # Different omega-3s
            ("linoleic acid", "linolenic acid"), # Omega-6 vs Omega-3
            
            # === CRITICAL SAFETY: Gut Health (Often Confused) ===
            ("probiotic", "prebiotic"),     # Different but often confused
            ("lactose", "lactase"),         # Sugar vs Enzyme
            ("digestive enzyme", "probiotic"), # Enzyme vs Bacteria
            ("fiber", "probiotic"),         # Prebiotic vs Probiotic
            
            # === CRITICAL SAFETY: Amino Acids vs Similar Compounds ===
            ("glucose", "glucosamine"),     # Sugar vs Amino sugar
            ("glycine", "glycerol"),        # Amino acid vs Alcohol
            ("taurine", "l-tyrosine"),      # Different amino acids
            ("arginine", "ornithine"),      # Related but different amino acids
            ("lysine", "glycine"),          # Different amino acids
            ("methionine", "metformin"),    # Amino acid vs Drug
            
            # === CRITICAL SAFETY: Minerals vs Compounds ===
            ("calcium", "calcium carbonate"), # Element vs Specific form
            ("magnesium", "magnesium oxide"), # Element vs Specific form
            ("magnesium", "magnesium stearate"), # Element vs Flow agent/lubricant
            ("magnesium stearate", "magnesium"), # Flow agent vs Element (reverse)
            ("iron", "iron sulfate"),       # Element vs Specific form
            ("zinc", "zinc oxide"),         # Element vs Specific form
            ("chromium", "chromium picolinate"), # Element vs Specific form
            
            # === CRITICAL SAFETY: Acids vs Salts (Different Absorption) ===
            ("folic acid", "folinic acid"), # Different folate forms
            ("citric acid", "citrate"),     # Acid vs Salt form
            ("lactic acid", "lactate"),     # Acid vs Salt form
            ("ascorbic acid", "ascorbate"), # Vitamin C acid vs salt
            ("malic acid", "malate"),       # Acid vs Salt form
            
            # === CRITICAL SAFETY: Herbs vs Extracts (Different Potency) ===
            ("ginkgo", "ginkgo extract"),   # Whole herb vs concentrated extract
            ("ginseng", "ginseng extract"), # Whole herb vs concentrated extract
            ("turmeric", "curcumin"),       # Whole herb vs active compound
            ("milk thistle", "silymarin"),  # Whole herb vs active compound
            ("green tea", "egcg"),          # Whole herb vs active compound
            ("grape seed", "resveratrol"),  # Different grape compounds
            
            # === CRITICAL SAFETY: Stimulants vs Non-Stimulants ===
            ("caffeine", "l-theanine"),     # Stimulant vs Calming amino acid
            ("guarana", "gaba"),            # Stimulant vs Calming neurotransmitter
            ("ephedra", "echinacea"),       # Banned stimulant vs Immune herb
            
            # === CRITICAL SAFETY: Hormones vs Precursors ===
            ("melatonin", "tryptophan"),    # Hormone vs Precursor amino acid
            ("testosterone", "tribulus"),   # Hormone vs Herb
            ("dhea", "dha"),                # Hormone vs Fatty acid
            ("growth hormone", "arginine"), # Hormone vs Amino acid
            
            # === CRITICAL SAFETY: Antioxidants (Different Mechanisms) ===
            ("vitamin c", "vitamin e"),     # Different antioxidants
            ("coq10", "alpha lipoic acid"), # Different antioxidants
            ("glutathione", "n-acetyl cysteine"), # Antioxidant vs precursor
            ("selenium", "sulfur"),         # Different minerals
            
            # === CRITICAL SAFETY: Joint Support (Different Mechanisms) ===
            ("glucosamine", "chondroitin"), # Different joint compounds
            ("msm", "dmso"),                # Different sulfur compounds
            ("collagen", "gelatin"),        # Different protein forms
            ("hyaluronic acid", "chondroitin"), # Different joint compounds
            
            # === CRITICAL SAFETY: Brain/Cognitive (Different Effects) ===
            ("ginkgo", "gaba"),             # Circulation vs Neurotransmitter
            ("phosphatidylserine", "phosphatidylcholine"), # Different phospholipids
            ("acetyl l-carnitine", "l-carnitine"), # Different carnitine forms
            ("dmae", "choline"),            # Different brain compounds
            
            # === CRITICAL SAFETY: Energy/Metabolism ===
            ("creatine", "carnitine"),      # Different energy compounds
            ("pyruvate", "citrate"),        # Different metabolic compounds
            ("ribose", "glucose"),          # Different sugars

            # === ULTRA CRITICAL: Vitamin/Mineral Number Protection ===
            # Prevent ANY cross-matching between numbered vitamins/minerals
            ("b1", "b2"), ("b1", "b3"), ("b1", "b5"), ("b1", "b6"), ("b1", "b7"), ("b1", "b8"), ("b1", "b9"), ("b1", "b12"),
            ("b2", "b1"), ("b2", "b3"), ("b2", "b5"), ("b2", "b6"), ("b2", "b7"), ("b2", "b8"), ("b2", "b9"), ("b2", "b12"),
            ("b3", "b1"), ("b3", "b2"), ("b3", "b5"), ("b3", "b6"), ("b3", "b7"), ("b3", "b8"), ("b3", "b9"), ("b3", "b12"),
            ("b5", "b1"), ("b5", "b2"), ("b5", "b3"), ("b5", "b6"), ("b5", "b7"), ("b5", "b8"), ("b5", "b9"), ("b5", "b12"),
            ("b6", "b1"), ("b6", "b2"), ("b6", "b3"), ("b6", "b5"), ("b6", "b7"), ("b6", "b8"), ("b6", "b9"), ("b6", "b12"),
            ("b7", "b1"), ("b7", "b2"), ("b7", "b3"), ("b7", "b5"), ("b7", "b6"), ("b7", "b8"), ("b7", "b9"), ("b7", "b12"),
            ("b8", "b1"), ("b8", "b2"), ("b8", "b3"), ("b8", "b5"), ("b8", "b6"), ("b8", "b7"), ("b8", "b9"), ("b8", "b12"),
            ("b9", "b1"), ("b9", "b2"), ("b9", "b3"), ("b9", "b5"), ("b9", "b6"), ("b9", "b7"), ("b9", "b8"), ("b9", "b12"),
            ("b12", "b1"), ("b12", "b2"), ("b12", "b3"), ("b12", "b5"), ("b12", "b6"), ("b12", "b7"), ("b12", "b8"), ("b12", "b9"),

            # Vitamin D protection (D2 vs D3 are VERY different)
            ("d2", "d3"), ("d3", "d2"),
            ("vitamin d2", "vitamin d3"), ("vitamin d3", "vitamin d2"),

            # Vitamin K protection (K1 vs K2 have different functions)
            ("k1", "k2"), ("k2", "k1"),
            ("vitamin k1", "vitamin k2"), ("vitamin k2", "vitamin k1"),

            # Additional mineral protection
            ("chromium", "vanadium"),       # Different trace minerals
        }
        
    @functools.lru_cache(maxsize=2000)  # PERFORMANCE: Reduced from 10000 to prevent memory bloat
    def preprocess_text(self, text: str) -> str:
        """
        Comprehensive text preprocessing with enhanced validation
        """
        # SAFETY: Comprehensive input validation
        text = self.validate_input(text, "ingredient_name")
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower().strip()
        
        # Remove common parenthetical information
        text = re.sub(r'\([^)]*\)', '', text)

        # Remove brackets and their contents
        text = re.sub(r'\[[^\]]*\]', '', text)

        # Remove curly braces but keep their contents
        text = re.sub(r'[{}]', '', text)

        # Remove trademark symbols
        text = re.sub(r'[™®©]', '', text)
        
        # Remove extra whitespace and punctuation at ends
        text = text.strip(string.punctuation + string.whitespace)
        
        # Normalize multiple spaces
        text = re.sub(r'\s+', ' ', text)
        
        # Remove common prefixes/suffixes that don't affect matching
        prefixes_to_remove = ['dl-', 'd-', 'l-', 'natural ', 'synthetic ', 'organic ']
        for prefix in prefixes_to_remove:
            if text.startswith(prefix):
                text = text[len(prefix):]
                break

        # Loop suffix removal to handle multiple suffixes like "Extract, Powder"
        suffixes_to_remove = [' extract', ' powder', ' oil', ' concentrate']
        changed = True
        while changed:
            changed = False
            # Strip punctuation first to handle cases like "juice, powder" → "juice powder"
            text = text.strip(string.punctuation + string.whitespace)
            for suffix in suffixes_to_remove:
                if text.endswith(suffix):
                    text = text[:-len(suffix)]
                    changed = True
                    break

        # Final cleanup
        text = text.strip(string.punctuation + string.whitespace)

        return text.strip()
    
    def generate_variations(self, text: str) -> List[str]:
        """
        Generate common variations of ingredient names
        """
        variations = [text]
        
        # Add version without spaces
        no_space = text.replace(' ', '')
        if no_space != text:
            variations.append(no_space)
        
        # Add version with hyphens instead of spaces
        hyphenated = text.replace(' ', '-')
        if hyphenated != text:
            variations.append(hyphenated)
        
        # Add common abbreviations
        abbreviations = {
            'vitamin': 'vit',
            'alpha': 'a',
            'beta': 'b',
            'gamma': 'g',
            'delta': 'd',
            'tocopherol': 'toco',
            'tocopheryl': 'toco',
            'ascorbic acid': 'ascorbate',
            'cholecalciferol': 'cholecal',
            'cyanocobalamin': 'cyano',
            'methylcobalamin': 'methyl',
            'pyridoxine': 'pyr',
            'riboflavin': 'ribo',
            'thiamine': 'thia',
            'phylloquinone': 'phyllo'
        }
        
        for full, abbrev in abbreviations.items():
            if full in text:
                variations.append(text.replace(full, abbrev))
            if abbrev in text:
                variations.append(text.replace(abbrev, full))
        
        # Add numeric variations (vitamin d3 -> vitamin d 3)
        if re.search(r'[a-z]\d+', text):
            spaced_num = re.sub(r'([a-z])(\d+)', r'\1 \2', text)
            variations.append(spaced_num)
        
        if re.search(r'[a-z]\s\d+', text):
            unspaced_num = re.sub(r'([a-z])\s(\d+)', r'\1\2', text)
            variations.append(unspaced_num)
        
        return list(set(variations))  # Remove duplicates

    def is_safe_for_fuzzy_matching(self, query: str, category: str = None) -> bool:
        """
        Determine if an ingredient is safe for fuzzy matching based on category and content
        """
        # Always allow exact matches
        if not query:
            return False

        query_lower = query.lower()

        # SAFETY: Block fuzzy matching for critical vitamins/minerals by content analysis
        critical_patterns = [
            r'\bb[1-9][\d]*\b',      # B1, B2, B3, etc.
            r'\bvitamin\s*[a-z]\d+\b',  # vitamin D3, vitamin K2, etc.
            r'\bd[23]\b',            # D2, D3
            r'\bk[12]\b',            # K1, K2
            r'\bomega\s*[369]\b',    # omega-3, omega-6, omega-9
        ]

        for pattern in critical_patterns:
            if re.search(pattern, query_lower):
                return False  # Never fuzzy match critical vitamins/minerals

        # SAFETY: Check if category is in safe list
        if category and category.lower() in self.safe_fuzzy_categories:
            return True

        # SAFETY: Default to EXACT MATCH ONLY for safety
        return False

    def exact_match_critical_aliases(self, query: str, targets: List[str]) -> Optional[str]:
        """
        SAFE exact matching for critical short aliases (B1, D3, K2, etc.)
        This ensures short critical vitamins/minerals get proper exact matches
        """
        if not query or not targets:
            return None

        query_lower = query.lower().strip()

        # Critical short patterns that must be matched exactly
        critical_short_patterns = [
            r'^b[1-9][\d]*$',      # B1, B2, B3, B12, etc.
            r'^d[23]$',            # D2, D3
            r'^k[12]$',            # K1, K2
            r'^vitamin\s*[a-z]\d*$', # vitamin D3, vitamin K2, etc.
        ]

        # Check if query is a critical short pattern
        is_critical = any(re.match(pattern, query_lower) for pattern in critical_short_patterns)

        if is_critical:
            # For critical patterns, only allow exact matches
            for target in targets:
                if query_lower == target.lower().strip():
                    logger.info(f"CRITICAL exact match: '{query}' -> '{target}'")
                    return target

        return None

    def validate_input(self, text: str, field_name: str = "input") -> str:
        """
        Comprehensive input validation with standardized empty handling
        """
        # Handle None
        if text is None:
            logger.debug(f"NULL {field_name} converted to empty string")
            return ""

        # Handle non-string types
        if not isinstance(text, str):
            try:
                text = str(text)
                logger.debug(f"Non-string {field_name} converted: {type(text)} -> str")
            except Exception:
                logger.warning(f"Failed to convert {field_name} to string, using empty")
                return ""

        # Handle whitespace-only strings
        stripped = text.strip()
        if not stripped:
            if text != "":  # Was whitespace-only
                logger.debug(f"Whitespace-only {field_name} converted to empty string")
            return ""

        # Handle common placeholder values
        placeholder_values = {
            "none", "null", "n/a", "na", "not applicable", "unknown",
            "unspecified", "not specified", "nil", "empty", "-", "--", "___"
        }

        if stripped.lower() in placeholder_values:
            logger.debug(f"Placeholder {field_name} '{stripped}' converted to empty string")
            return ""

        return stripped

    def fuzzy_match(self, query: str, targets: List[str], category: str = None) -> Tuple[Optional[str], int]:
        """
        SAFETY-FIRST fuzzy matching with whitelist approach and thread-safe caching
        """
        if not targets or not query:
            return None, 0

        # SAFETY FIRST: Check if fuzzy matching is safe for this ingredient
        if not self.is_safe_for_fuzzy_matching(query, category):
            return None, 0  # Block fuzzy matching for critical ingredients

        # Use thread-safe @lru_cache - convert list to tuple for hashability
        targets_tuple = tuple(targets)
        return self._safe_fuzzy_match_cached(query, targets_tuple, category)

    @functools.lru_cache(maxsize=1000)  # PERFORMANCE: Reduced from 5000 to prevent memory bloat
    def _safe_fuzzy_match_cached(self, query: str, targets_tuple: tuple, category: str = None) -> Tuple[Optional[str], int]:
        """Thread-safe cached version of fuzzy matching"""
        # Convert tuple back to list for processing
        targets = list(targets_tuple)
        return self._perform_safe_fuzzy_match(query, targets, category)

    def _perform_safe_fuzzy_match(self, query: str, targets: List[str], category: str = None) -> Tuple[Optional[str], int]:
        """
        SAFETY-ENHANCED fuzzy matching with comprehensive protection
        """
        # SAFETY: Enhanced minimum length check to prevent false positives
        if len(query) < self.minimum_fuzzy_length:
            return None, 0

        if FUZZY_AVAILABLE:
            # SAFETY: More aggressive filtering - prevent short critical aliases from matching
            # Restore critical vitamins (B1, D3, K2) but only for EXACT matching in other methods
            filtered_targets = [t for t in targets if len(t) >= self.minimum_fuzzy_length]

            # SAFETY: First try exact ratio matching with higher threshold
            match = process.extractOne(query, filtered_targets, scorer=fuzz.ratio)
            if match and match[1] >= self.fuzzy_threshold:
                # SAFETY: Enhanced blacklist checking
                if not self._is_blacklisted_match(query, match[0]):
                    logger.info(f"SAFE fuzzy match: '{query}' -> '{match[0]}' (score: {match[1]}, category: {category})")
                    return match[0], match[1]
                else:
                    logger.warning(f"BLOCKED dangerous fuzzy match: '{query}' -> '{match[0]}' (score: {match[1]})")
                    return None, 0

            # SAFETY: Conservative partial matching only for longer queries and safe categories
            if len(query) >= 8 and category in self.safe_fuzzy_categories:
                match = process.extractOne(query, filtered_targets, scorer=fuzz.partial_ratio)
                if match and match[1] >= self.partial_threshold:
                    if not self._is_blacklisted_match(query, match[0]):
                        logger.info(f"SAFE partial match: '{query}' -> '{match[0]}' (score: {match[1]}, category: {category})")
                        return match[0], match[1]
        else:
            # Fallback to difflib with same safety checks
            best_match = None
            best_score = 0

            filtered_targets = [t for t in targets if len(t) >= self.minimum_fuzzy_length]

            for target in filtered_targets:
                ratio = SequenceMatcher(None, query, target).ratio() * 100
                if ratio > best_score and ratio >= self.fuzzy_threshold:
                    if not self._is_blacklisted_match(query, target):
                        best_score = ratio
                        best_match = target

            if best_match:
                logger.info(f"SAFE difflib match: '{query}' -> '{best_match}' (score: {int(best_score)}, category: {category})")
                return best_match, int(best_score)

        return None, 0
    
    def _is_blacklisted_match(self, query: str, target: str) -> bool:
        """Check if a fuzzy match should be rejected based on blacklist"""
        query_lower = query.lower()
        target_lower = target.lower()
        
        # CRITICAL SAFETY: Check dosage confusion
        if self._has_dosage_confusion(query_lower, target_lower):
            return True
        
        # CRITICAL SAFETY: Check unit confusion  
        if self._has_unit_confusion(query_lower, target_lower):
            return True
        
        # Check standard blacklist
        for blacklisted_query, blacklisted_target in self.fuzzy_blacklist:
            # Check if query contains blacklisted pattern and target contains its counterpart
            if blacklisted_query in query_lower and blacklisted_target in target_lower:
                return True
            # Check reverse direction too
            if blacklisted_target in query_lower and blacklisted_query in target_lower:
                return True
        
        return False
    
    def _has_dosage_confusion(self, query: str, target: str) -> bool:
        """Check if two ingredients have different dosages - CRITICAL for scoring accuracy"""
        import re
        
        # Extract dosages from both strings
        dosage_pattern = r'(\d+(?:\.\d+)?)\s*(mg|mcg|iu|g|units?|billion|million)'
        
        query_dosages = re.findall(dosage_pattern, query, re.IGNORECASE)
        target_dosages = re.findall(dosage_pattern, target, re.IGNORECASE)
        
        # If both have dosages, check if they're different
        if query_dosages and target_dosages:
            # Normalize units for comparison
            query_normalized = self._normalize_dosage(query_dosages[0])
            target_normalized = self._normalize_dosage(target_dosages[0])
            
            # If dosages are significantly different (>20% difference), block the match
            if query_normalized and target_normalized:
                difference_ratio = abs(query_normalized - target_normalized) / max(query_normalized, target_normalized)
                if difference_ratio > 0.2:  # More than 20% difference
                    return True
        
        return False
    
    def _normalize_dosage(self, dosage_tuple) -> float:
        """Normalize dosage to mg for comparison"""
        amount, unit = dosage_tuple
        amount = float(amount)
        unit_lower = unit.lower()
        
        # Convert to mg
        if unit_lower in ['mcg', 'μg']:
            return amount / 1000  # mcg to mg
        elif unit_lower == 'g':
            return amount * 1000  # g to mg
        elif unit_lower == 'iu':
            # IU conversion is complex and vitamin-specific, so we'll be conservative
            # For vitamin D: 1 IU ≈ 0.025 mcg
            # For vitamin E: 1 IU ≈ 0.67 mg
            # Since we can't know the vitamin, we'll treat IU as a special case
            return amount  # Keep as-is for IU
        elif unit_lower in ['mg']:
            return amount
        elif unit_lower in ['billion', 'million']:
            # For probiotics - keep as-is since these are counts, not weights
            return amount
        else:
            return amount  # Default case
    
    def _has_unit_confusion(self, query: str, target: str) -> bool:
        """Check for dangerous unit confusions (IU vs mcg, etc.)"""
        import re
        
        # Dangerous unit pairs that should never be matched
        dangerous_unit_pairs = [
            ('iu', 'mcg'),    # International Units vs micrograms
            ('iu', 'mg'),     # International Units vs milligrams  
            ('mg', 'g'),      # Different magnitudes
            ('mcg', 'mg'),    # 1000x difference
            ('billion', 'million'),  # For probiotics
        ]
        
        unit_pattern = r'\d+\s*(mg|mcg|iu|g|units?|billion|million)'
        
        query_units = re.findall(unit_pattern, query, re.IGNORECASE)
        target_units = re.findall(unit_pattern, target, re.IGNORECASE)
        
        if query_units and target_units:
            query_unit = query_units[0].lower()
            target_unit = target_units[0].lower()
            
            # Check if this is a dangerous unit pairing
            for unit1, unit2 in dangerous_unit_pairs:
                if (query_unit == unit1 and target_unit == unit2) or \
                   (query_unit == unit2 and target_unit == unit1):
                    return True
        
        return False

    def disambiguate_ingredient_match(self, context_text: str, ingredient_data: Dict[str, Any]) -> bool:
        """
        Determine if an ingredient match is valid based on context disambiguation
        
        Args:
            context_text: Text context around the matched ingredient
            ingredient_data: Ingredient form data with context_include/context_exclude
            
        Returns:
            True if match is valid, False if should be rejected
        """
        import re
        
        context_include = ingredient_data.get('context_include', [])
        context_exclude = ingredient_data.get('context_exclude', [])
        
        context_lower = context_text.lower()
        
        # Check for exclusion words (negative confirmation) using word boundaries
        for word in context_exclude:
            # Use word boundaries to match whole words only
            pattern = rf'\b{re.escape(word.lower())}\b'
            if re.search(pattern, context_lower):
                return False  # Definitely not this ingredient
            
        # Check for inclusion words (positive confirmation) using word boundaries
        include_found = False
        for word in context_include:
            pattern = rf'\b{re.escape(word.lower())}\b'
            if re.search(pattern, context_lower):
                include_found = True
                break
                
        if include_found:
            return True   # Definitely this ingredient
            
        # If no disambiguation rules defined, accept the match
        if not context_include and not context_exclude:
            return True
            
        # If disambiguation rules exist but no include words found, be conservative
        if context_include and not include_found:
            return False  # Ambiguous - skip this match
            
        return True  # Default to accepting

    def clear_cache(self):
        """Clear fuzzy matching cache to free memory - now using @lru_cache"""
        # Clear the lru_cache decorators
        if hasattr(self.preprocess_text, 'cache_clear'):
            self.preprocess_text.cache_clear()
        if hasattr(self._safe_fuzzy_match_cached, 'cache_clear'):
            self._safe_fuzzy_match_cached.cache_clear()


class EnhancedDSLDNormalizer:
    """Enhanced DSLD normalizer with improved matching and preprocessing"""
    
    def __init__(self):
        # Load reference data
        self.ingredient_map = self._load_json(INGREDIENT_QUALITY_MAP)
        self.harmful_additives = self._load_json(HARMFUL_ADDITIVES)
        self.allergens_db = self._load_json(ALLERGENS)
        self.manufacturers_db = self._load_json(TOP_MANUFACTURERS)
        self.proprietary_blends = self._load_json(PROPRIETARY_BLENDS)
        self.standardized_botanicals = self._load_json(STANDARDIZED_BOTANICALS)
        self.banned_recalled = self._load_json(BANNED_RECALLED)
        self.other_ingredients = self._load_json(OTHER_INGREDIENTS)  # Merged: non_harmful + passive_inactive
        self.botanical_ingredients = self._load_json(BOTANICAL_INGREDIENTS)
        self.absorption_enhancers = self._load_json(ABSORPTION_ENHANCERS)

        # Load RDA databases for clinical dosing validation
        self.rda_optimal = self._load_json(RDA_OPTIMAL_ULS)
        self.rda_therapeutic = self._load_json(RDA_THERAPEUTIC_DOSING)
        self.enhanced_delivery = self._load_json(ENHANCED_DELIVERY)
        
        # Initialize enhanced matcher
        self.matcher = EnhancedIngredientMatcher()

        # Initialize functional grouping handler for transparency scoring
        self.grouping_handler = FunctionalGroupingHandler()

        # Preprocess excluded phrases for fast matching
        self._preprocessed_excluded_labels = {
            self.matcher.preprocess_text(phrase) for phrase in EXCLUDED_LABEL_PHRASES
        }
        self._preprocessed_excluded_nutrition = {
            self.matcher.preprocess_text(fact) for fact in EXCLUDED_NUTRITION_FACTS
        }

        # Build enhanced lookup indices
        self._build_enhanced_indices()

        # PERFORMANCE OPTIMIZATION: Cache variation lists to avoid recreating them
        # These lists are created once and reused for all fuzzy matching operations
        self._ingredient_variations_cache = None
        self._form_variations_cache = None
        self._harmful_variations_cache = None
        self._non_harmful_variations_cache = None
        self._allergen_variations_cache = None
        self._banned_variations_cache = None
        self._inactive_variations_cache = None
        self._botanical_variations_cache = None

        # Track unmapped ingredients with more detail
        self.unmapped_ingredients = Counter()
        self.unmapped_details = {}  # Store more context about unmapped ingredients

        # Initialize the enhanced unmapped ingredient tracker for separate active/inactive files
        self.unmapped_tracker = None  # Will be initialized when output_dir is set

        # THREAD-SAFE OPTIMIZATION: Using @lru_cache decorators for thread safety
        # No more manual cache management - Python's lru_cache handles thread safety

        # OPTIMIZATION: Performance tracking for monitoring
        self._cache_stats = {
            "ingredient_calls": 0, "allergen_calls": 0, "harmful_calls": 0,
            "non_harmful_calls": 0, "accuracy_stats": {}
        }

        # OPTIMIZATION: Parallel processing configuration
        self._max_workers = min(8, (os.cpu_count() or 4))  # Adaptive worker count
        self._parallel_threshold = FUZZY_MATCHING_THRESHOLDS["parallel_threshold"]

        # OPTIMIZATION: Fast lookup indices for common operations
        self._fast_exact_lookup = {}  # Combined exact match lookup
        self._common_ingredients_cache = {}  # Cache for most common ingredients
        self._build_fast_lookups()

    def set_output_directory(self, output_dir: Path):
        """Set the output directory and initialize the unmapped tracker"""
        self.unmapped_tracker = UnmappedIngredientTracker(output_dir / "unmapped")
        
    def clear_caches(self):
        """Clear all thread-safe @lru_cache caches"""
        # Clear all @lru_cache decorated methods
        cache_methods = [
            '_enhanced_ingredient_mapping_cached',
            '_enhanced_allergen_check_cached',
            '_enhanced_harmful_check_cached',
            '_enhanced_non_harmful_check_cached'
        ]

        for method_name in cache_methods:
            if hasattr(self, method_name):
                method = getattr(self, method_name)
                if hasattr(method, 'cache_clear'):
                    method.cache_clear()

        # Clear matcher caches
        self.matcher.clear_cache()

        # Clear simple lookup caches
        self._fast_exact_lookup.clear()
        self._common_ingredients_cache.clear()

        logger.info("Cleared all thread-safe LRU caches")

    def validate_database_integrity(self) -> Dict[str, any]:
        """
        Comprehensive database integrity validation
        Returns detailed report of any issues found
        """
        integrity_report = {
            "timestamp": datetime.now().isoformat(),
            "status": "validating",
            "errors": [],
            "warnings": [],
            "statistics": {}
        }

        logger.info("🔍 Starting comprehensive database integrity validation...")

        try:
            # 1. Validate database cross-references
            self._validate_cross_references(integrity_report)

            # 2. Check for orphaned data
            self._check_orphaned_data(integrity_report)

            # 3. Validate required fields
            self._validate_required_fields(integrity_report)

            # 4. Check for data consistency
            self._validate_data_consistency(integrity_report)

            # 5. Generate summary statistics
            self._generate_integrity_statistics(integrity_report)

            # Determine overall status
            if integrity_report["errors"]:
                integrity_report["status"] = "failed"
                logger.error(f"❌ Database integrity validation FAILED with {len(integrity_report['errors'])} errors")
            elif integrity_report["warnings"]:
                integrity_report["status"] = "passed_with_warnings"
                logger.warning(f"⚠️ Database integrity validation PASSED with {len(integrity_report['warnings'])} warnings")
            else:
                integrity_report["status"] = "passed"
                logger.info("✅ Database integrity validation PASSED - all checks successful")

        except Exception as e:
            integrity_report["status"] = "error"
            integrity_report["errors"].append(f"Validation process failed: {str(e)}")
            logger.error(f"💥 Database integrity validation crashed: {e}")

        return integrity_report

    def _validate_cross_references(self, report: Dict):
        """Validate cross-references between databases"""
        logger.info("🔗 Validating database cross-references...")

        # Check if all ingredients in quality map have safety data
        quality_ingredients = set(self.ingredient_alias_lookup.keys())
        allergen_ingredients = set(self.allergen_lookup.keys())
        harmful_ingredients = set(self.harmful_lookup.keys())
        other_ingredients_set = set(self.other_ingredients_lookup.keys())

        # Find ingredients with no safety classification
        no_safety_data = quality_ingredients - (allergen_ingredients | harmful_ingredients | other_ingredients_set)

        if no_safety_data:
            if len(no_safety_data) > 50:  # If too many, this might be expected
                report["warnings"].append(f"{len(no_safety_data)} ingredients in quality database lack safety classification")
            else:
                for ingredient in list(no_safety_data)[:10]:  # Show first 10
                    report["warnings"].append(f"Ingredient '{ingredient}' has no safety classification")

    def _check_orphaned_data(self, report: Dict):
        """Check for orphaned data entries"""
        logger.info("🔍 Checking for orphaned data...")

        # Check for safety entries not in quality database
        quality_ingredients = set(self.ingredient_alias_lookup.keys())

        # Find orphaned allergen entries
        orphaned_allergens = set(self.allergen_lookup.keys()) - quality_ingredients
        if orphaned_allergens:
            report["warnings"].append(f"{len(orphaned_allergens)} allergen entries not found in quality database")

        # Find orphaned harmful entries
        orphaned_harmful = set(self.harmful_lookup.keys()) - quality_ingredients
        if orphaned_harmful:
            report["warnings"].append(f"{len(orphaned_harmful)} harmful additive entries not found in quality database")

    def _validate_required_fields(self, report: Dict):
        """Validate that all database entries have required fields"""
        logger.info("📋 Validating required fields...")

        # Check quality database entries
        for ingredient_name, standard_name in self.ingredient_alias_lookup.items():
            if not standard_name or not standard_name.strip():
                report["errors"].append(f"Quality ingredient '{ingredient_name}' missing standard_name")

        # Check allergen database entries
        for allergen_key, allergen_data in self.allergen_lookup.items():
            if not allergen_data.get("standard_name"):
                report["errors"].append(f"Allergen '{allergen_key}' missing standard_name")
            if not allergen_data.get("severity_level"):
                report["warnings"].append(f"Allergen '{allergen_key}' missing severity_level")

        # Check harmful additive entries
        for harmful_key, harmful_data in self.harmful_lookup.items():
            if not harmful_data.get("category"):
                report["errors"].append(f"Harmful additive '{harmful_key}' missing category")

    def _validate_data_consistency(self, report: Dict):
        """Validate data consistency across databases"""
        logger.info("🔄 Validating data consistency...")

        # Check for duplicate standard names in quality database
        standard_names = {}
        for alias, standard_name in self.ingredient_alias_lookup.items():
            if standard_name in standard_names:
                standard_names[standard_name].append(alias)
            else:
                standard_names[standard_name] = [alias]

        # Report standard names with many aliases (might be okay, but worth checking)
        for standard_name, aliases in standard_names.items():
            if len(aliases) > 20:  # Threshold for review
                report["warnings"].append(f"Standard name '{standard_name}' has {len(aliases)} aliases - verify correctness")

    def _generate_integrity_statistics(self, report: Dict):
        """Generate comprehensive statistics"""
        report["statistics"] = {
            "quality_database": len(self.ingredient_alias_lookup),
            "allergen_database": len(self.allergen_lookup),
            "harmful_database": len(self.harmful_lookup),
            "other_ingredients_database": len(self.other_ingredients_lookup),
            "botanical_database": len(getattr(self, 'botanical_lookup', {})),
            "total_errors": len(report["errors"]),
            "total_warnings": len(report["warnings"])
        }

    def get_cache_stats(self) -> Dict[str, any]:
        """Get performance statistics for thread-safe caching system"""
        cache_info = {}

        # Get cache info from @lru_cache decorated methods
        cache_methods = [
            ('ingredient_mapping', '_enhanced_ingredient_mapping_cached'),
            ('allergen_check', '_enhanced_allergen_check_cached'),
            ('harmful_check', '_enhanced_harmful_check_cached'),
            ('non_harmful_check', '_enhanced_non_harmful_check_cached'),
            ('fuzzy_matching', 'matcher._safe_fuzzy_match_cached'),
            ('text_preprocessing', 'matcher.preprocess_text')
        ]

        for name, method_path in cache_methods:
            try:
                if '.' in method_path:
                    obj, method_name = method_path.split('.', 1)
                    method = getattr(getattr(self, obj), method_name)
                else:
                    method = getattr(self, method_path)

                if hasattr(method, 'cache_info'):
                    info = method.cache_info()
                    cache_info[name] = {
                        "hits": info.hits,
                        "misses": info.misses,
                        "current_size": info.currsize,
                        "max_size": info.maxsize
                    }
            except AttributeError:
                cache_info[name] = {"status": "not_cached"}

        return {
            "cache_performance": cache_info,
            "processing_stats": self._cache_stats.copy()
        }

    def _build_fast_lookups(self):
        """Build optimized lookup indices for common operations"""
        # This will be called after the main indices are built
        self._build_fast_lookups_impl()

    def _build_fast_lookups_impl(self):
        """Build optimized fast lookup indices"""
        logger.info("Building fast lookup indices...")

        # Build combined exact match lookup for all databases
        self._fast_exact_lookup = {}

        # PRIORITY 1: Add BANNED/RECALLED lookups (HIGHEST PRIORITY - safety first)
        # Iterate through ALL sections in banned_recalled database dynamically
        for key, value in self.banned_recalled.items():
            if isinstance(value, list) and len(value) > 0:
                # Check if items have the expected structure for banned substances
                if any(isinstance(item, dict) and 'standard_name' in item for item in value):
                    banned_ingredients = value
                    for banned in banned_ingredients:
                        standard_name = banned.get("standard_name", "")
                        if standard_name:
                            processed_standard = self.matcher.preprocess_text(standard_name)
                            self._fast_exact_lookup[processed_standard] = {
                                "type": "banned",
                                "standard_name": standard_name,
                                "severity": banned.get("severity_level", "critical"),
                                "reason": banned.get("reason", banned.get("recall_reason", "banned")),
                                "mapped": True,
                                "priority": 1
                            }

                            # Add aliases
                            for alias in banned.get("aliases", []) or []:
                                processed_alias = self.matcher.preprocess_text(alias)
                                self._fast_exact_lookup[processed_alias] = {
                                    "type": "banned",
                                    "standard_name": standard_name,
                                    "severity": banned.get("severity_level", "critical"),
                                    "reason": banned.get("reason", banned.get("recall_reason", "banned")),
                                    "mapped": True,
                                    "priority": 1
                                }

        # PRIORITY 2: Add allergen lookups (safety-critical)
        for key, value in self.allergen_lookup.items():
            # Only add if not already present (banned takes priority)
            if key not in self._fast_exact_lookup:
                # SAFETY: Ensure standard_name exists before accessing
                standard_name = value.get("standard_name", "")
                if not standard_name:
                    logger.warning(f"Allergen missing standard_name: {key}")
                    continue
                self._fast_exact_lookup[key] = {
                    "type": "allergen",
                    "allergen_type": standard_name.lower(),
                    "severity": value.get("severity_level", "low"),
                    "mapped": True,
                    "priority": 2
                }

        # PRIORITY 3: Add harmful additive lookups (safety-critical)
        for key, value in self.harmful_lookup.items():
            # Only add if not already present (higher priorities take precedence)
            if key not in self._fast_exact_lookup:
                self._fast_exact_lookup[key] = {
                    "type": "harmful",
                    "category": value.get("category", "other"),
                    "risk_level": value.get("risk_level", "low"),
                    "mapped": True,
                    "priority": 3
                }

        # PRIORITY 4: Add ingredient lookups (active ingredients)
        for key, value in self.ingredient_alias_lookup.items():
            if key not in self._fast_exact_lookup:
                self._fast_exact_lookup[key] = {
                    "type": "ingredient",
                    "standard_name": value,
                    "mapped": True,
                    "priority": 4
                }

        # PRIORITY 5: Add STANDARDIZED BOTANICALS lookups
        standardized_botanicals = self.standardized_botanicals.get("standardized_botanicals", [])
        for std_botanical in standardized_botanicals:
            standard_name = std_botanical.get("standard_name", "")
            if standard_name:
                processed_standard = self.matcher.preprocess_text(standard_name)
                if processed_standard not in self._fast_exact_lookup:
                    self._fast_exact_lookup[processed_standard] = {
                        "type": "standardized_botanical",
                        "standard_name": standard_name,
                        "category": std_botanical.get("category", "botanical"),
                        "standardization": std_botanical.get("standardization", ""),
                        "mapped": True,
                        "priority": 5
                    }

                # Add aliases
                for alias in std_botanical.get("aliases", []) or []:
                    processed_alias = self.matcher.preprocess_text(alias)
                    if processed_alias not in self._fast_exact_lookup:
                        self._fast_exact_lookup[processed_alias] = {
                            "type": "standardized_botanical",
                            "standard_name": standard_name,
                            "category": std_botanical.get("category", "botanical"),
                            "standardization": std_botanical.get("standardization", ""),
                            "mapped": True,
                            "priority": 5
                        }

        # PRIORITY 6: Add BOTANICAL INGREDIENTS lookups
        botanical_ingredients = self.botanical_ingredients.get("botanical_ingredients", [])
        for botanical in botanical_ingredients:
            standard_name = botanical.get("standard_name", "")
            if standard_name:
                processed_standard = self.matcher.preprocess_text(standard_name)
                # Only add if not already present (standardized botanicals have higher priority)
                if processed_standard not in self._fast_exact_lookup:
                    self._fast_exact_lookup[processed_standard] = {
                        "type": "botanical",
                        "standard_name": standard_name,
                        "category": botanical.get("category", "botanical"),
                        "mapped": True,
                        "priority": 6
                    }

                # Add aliases
                for alias in botanical.get("aliases", []) or []:
                    processed_alias = self.matcher.preprocess_text(alias)
                    if processed_alias not in self._fast_exact_lookup:
                        self._fast_exact_lookup[processed_alias] = {
                            "type": "botanical",
                            "standard_name": standard_name,
                            "category": botanical.get("category", "botanical"),
                            "mapped": True,
                            "priority": 6
                        }

        # PRIORITY 7: Add OTHER INGREDIENTS lookups (safe additives/excipients)
        for key, value in self.other_ingredients_lookup.items():
            # Only add if not already present (higher priorities take precedence)
            if key not in self._fast_exact_lookup:
                self._fast_exact_lookup[key] = {
                    "type": "other_ingredient",
                    "standard_name": value.get("standard_name", key),
                    "category": value.get("category", "other"),
                    "additive_type": value.get("additive_type", "unknown"),
                    "clean_label_score": value.get("clean_label_score", 7),
                    "mapped": True,
                    "priority": 7
                }

        # PRIORITY 8: Add PROPRIETARY BLENDS lookups
        proprietary_blend_concerns = self.proprietary_blends.get("proprietary_blend_concerns", [])
        for concern in proprietary_blend_concerns:
            standard_name = concern.get("standard_name", "")
            if standard_name:
                processed_standard = self.matcher.preprocess_text(standard_name)
                if processed_standard not in self._fast_exact_lookup:
                    self._fast_exact_lookup[processed_standard] = {
                        "type": "proprietary_blend",
                        "standard_name": standard_name,
                        "category": concern.get("category", "blend"),
                        "mapped": True,
                        "priority": 8
                    }

                # Add red flag terms as aliases
                for red_flag_term in concern.get("red_flag_terms", []) or []:
                    processed_term = self.matcher.preprocess_text(red_flag_term)
                    if processed_term not in self._fast_exact_lookup:
                        self._fast_exact_lookup[processed_term] = {
                            "type": "proprietary_blend",
                            "standard_name": standard_name,
                            "category": concern.get("category", "blend"),
                            "mapped": True,
                            "priority": 8
                        }

        # PRIORITY 9: Add OTHER INGREDIENTS (FDA terminology) lookups (lowest priority - catch-all)
        other_ingredients_list = self.other_ingredients.get("other_ingredients", [])
        for other_ing in other_ingredients_list:
            standard_name = other_ing.get("standard_name", "")
            if standard_name:
                processed_standard = self.matcher.preprocess_text(standard_name)
                # Only add if not already present (all higher priorities take precedence)
                if processed_standard not in self._fast_exact_lookup:
                    self._fast_exact_lookup[processed_standard] = {
                        "type": "other_ingredient",
                        "standard_name": standard_name,
                        "category": other_ing.get("category", "other"),
                        "is_additive": other_ing.get("is_additive", False),
                        "mapped": True,
                        "priority": 9
                    }

                # Add aliases
                for alias in other_ing.get("aliases", []) or []:
                    processed_alias = self.matcher.preprocess_text(alias)
                    if processed_alias not in self._fast_exact_lookup:
                        self._fast_exact_lookup[processed_alias] = {
                            "type": "other_ingredient",
                            "standard_name": standard_name,
                            "category": other_ing.get("category", "other"),
                            "is_additive": other_ing.get("is_additive", False),
                            "mapped": True,
                            "priority": 9
                        }

        # PRIORITY 10: Add ABSORPTION ENHANCERS lookups
        absorption_enhancers_list = self.absorption_enhancers.get("absorption_enhancers", [])
        for enhancer in absorption_enhancers_list:
            enhancer_name = enhancer.get("name", "")  # Note: uses 'name' not 'standard_name'
            if enhancer_name:
                processed_name = self.matcher.preprocess_text(enhancer_name)
                if processed_name not in self._fast_exact_lookup:
                    self._fast_exact_lookup[processed_name] = {
                        "type": "absorption_enhancer",
                        "standard_name": enhancer_name,
                        "category": "absorption",
                        "mapped": True,
                        "priority": 10
                    }
                # Add aliases
                for alias in enhancer.get("aliases", []) or []:
                    processed_alias = self.matcher.preprocess_text(alias)
                    if processed_alias not in self._fast_exact_lookup:
                        self._fast_exact_lookup[processed_alias] = {
                            "type": "absorption_enhancer",
                            "standard_name": enhancer_name,
                            "category": "absorption",
                            "mapped": True,
                            "priority": 10
                        }

        # PRIORITY 11: Add ENHANCED DELIVERY lookups
        for delivery_key, delivery_data in self.enhanced_delivery.items():
            delivery_name = delivery_key.replace("_", " ").title()  # Convert key to readable name
            processed_name = self.matcher.preprocess_text(delivery_key)
            if processed_name not in self._fast_exact_lookup:
                self._fast_exact_lookup[processed_name] = {
                    "type": "enhanced_delivery",
                    "standard_name": delivery_name,
                    "category": delivery_data.get("category", "delivery"),
                    "points": delivery_data.get("points", 0),
                    "mapped": True,
                    "priority": 11
                }

        logger.info(f"Built comprehensive fast lookup index with {len(self._fast_exact_lookup)} entries")

        # Log breakdown by type for debugging
        type_counts = {}
        for entry in self._fast_exact_lookup.values():
            entry_type = entry.get("type", "unknown")
            type_counts[entry_type] = type_counts.get(entry_type, 0) + 1

        for entry_type, count in sorted(type_counts.items()):
            logger.info(f"  - {entry_type}: {count} entries")

    def _fast_ingredient_lookup(self, name: str) -> Dict[str, Any]:
        """Fast combined lookup for ingredient, harmful, and allergen data"""
        processed_name = self.matcher.preprocess_text(name)

        # Check fast exact lookup first
        if processed_name in self._fast_exact_lookup:
            return self._fast_exact_lookup[processed_name]

        # Return default "not found" result
        return {
            "type": "none",
            "mapped": False
        }

    def _process_ingredient_parallel(self, ingredient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single ingredient for parallel execution"""
        name = ingredient_data.get("name", "")

        # Extract form names from forms array - each form is a dict with "name" field
        forms_data = ingredient_data.get("forms", [])
        forms = []
        if forms_data and isinstance(forms_data, list):
            for form_dict in forms_data:
                if isinstance(form_dict, dict) and "name" in form_dict:
                    form_name = form_dict.get("name", "")
                    if form_name:
                        forms.append(form_name)

        # Enhanced mapping
        standard_name, mapped, _ = self._enhanced_ingredient_mapping(name, forms)

        # Enhanced checks
        allergen_info = self._enhanced_allergen_check(name, forms)
        harmful_info = self._enhanced_harmful_check(name)

        # Check if proprietary blend
        is_proprietary = self._is_proprietary_blend_name(name)

        # Calculate final mapping status
        is_mapped = (mapped or
                    harmful_info["category"] != "none" or
                    allergen_info["is_allergen"] or
                    is_proprietary)

        # Track unmapped ingredients only if not found in any database
        # DATA INTEGRITY FIX: Filter out label phrases and nutrition facts
        # This prevents "None", "Contains < 2% of", etc. from appearing in unmapped list
        if not is_mapped and not self._is_nutrition_fact(name):
            processed_name = self.matcher.preprocess_text(name)
            # Thread-safe tracking (Counter is thread-safe for basic operations)
            self.unmapped_ingredients[name] += 1
            self.unmapped_details[name] = {
                "processed_name": processed_name,
                "forms": forms,
                "variations_tried": self.matcher.generate_variations(processed_name),
                "is_active": True  # This method is for active ingredients from the context
            }

        return {
            "order": ingredient_data.get("order", 0),
            "name": name,
            "standardName": standard_name,
            "category": ingredient_data.get("category", ""),
            "ingredientGroup": ingredient_data.get("ingredientGroup", ""),
            "isHarmful": harmful_info["category"] != "none",
            "harmfulCategory": harmful_info["category"],
            "riskLevel": harmful_info["risk_level"],
            "allergen": allergen_info["is_allergen"],
            "allergenType": allergen_info["type"],
            "allergenSeverity": allergen_info["severity"],
            "mapped": is_mapped
        }

    @property
    def ingredient_variations(self) -> List[str]:
        """Cached ingredient variations list for fuzzy matching"""
        if self._ingredient_variations_cache is None:
            self._ingredient_variations_cache = list(self.ingredient_alias_lookup.keys())
        return self._ingredient_variations_cache

    @property
    def form_variations(self) -> List[str]:
        """Cached form variations list for fuzzy matching"""
        if self._form_variations_cache is None:
            self._form_variations_cache = list(self.ingredient_forms_lookup.keys())
        return self._form_variations_cache

    @property
    def harmful_variations(self) -> List[str]:
        """Cached harmful variations list for fuzzy matching"""
        if self._harmful_variations_cache is None:
            self._harmful_variations_cache = list(self.harmful_lookup.keys())
        return self._harmful_variations_cache

    @property
    def non_harmful_variations(self) -> List[str]:
        """Cached non-harmful additive variations list for fuzzy matching"""
        if self._non_harmful_variations_cache is None:
            self._non_harmful_variations_cache = list(self.other_ingredients_lookup.keys())
        return self._non_harmful_variations_cache

    @property
    def allergen_variations(self) -> List[str]:
        """Cached allergen variations list for fuzzy matching"""
        if not hasattr(self, '_allergen_variations_cache'):
            self._allergen_variations_cache = None
        if self._allergen_variations_cache is None:
            self._allergen_variations_cache = list(self.allergen_lookup.keys())
        return self._allergen_variations_cache

    @property
    def banned_variations(self) -> List[str]:
        """Cached banned variations list for fuzzy matching"""
        if self._banned_variations_cache is None:
            all_banned_terms = []
            # Get all banned substances from all categories
            for category, items in self.banned_recalled.items():
                if isinstance(items, list):
                    for banned in items:
                        all_banned_terms.append(banned.get("standard_name", "").lower())
                        all_banned_terms.extend([alias.lower() for alias in banned.get("aliases", []) or []])
            self._banned_variations_cache = [term for term in all_banned_terms if term]
        return self._banned_variations_cache

    @property
    def inactive_variations(self) -> List[str]:
        """Cached inactive variations list for fuzzy matching"""
        if self._inactive_variations_cache is None:
            all_inactive_terms = []
            inactive_ingredients = self.other_ingredients.get("other_ingredients", [])
            for inactive in inactive_ingredients:
                all_inactive_terms.append(inactive.get("standard_name", "").lower())
                all_inactive_terms.extend([alias.lower() for alias in inactive.get("aliases", []) or []])
            self._inactive_variations_cache = [term for term in all_inactive_terms if term]
        return self._inactive_variations_cache

    @property
    def botanical_variations(self) -> List[str]:
        """Cached botanical variations list for fuzzy matching"""
        if self._botanical_variations_cache is None:
            all_botanical_terms = []
            botanical_ingredients = self.botanical_ingredients.get("botanical_ingredients", [])
            for botanical in botanical_ingredients:
                all_botanical_terms.append(botanical.get("standard_name", "").lower())
                all_botanical_terms.extend([alias.lower() for alias in botanical.get("aliases", []) or []])
            self._botanical_variations_cache = [term for term in all_botanical_terms if term]
        return self._botanical_variations_cache

    def _load_json(self, filepath: Path) -> Dict:
        """Load JSON reference file with error handling"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load {filepath}: {str(e)}")
            return {}
    
    def _build_enhanced_indices(self):
        """Build comprehensive lookup indices with variations - fixed to prevent overwrites"""
        logger.info("Building enhanced ingredient lookup indices...")
        
        # Build ingredient alias lookup with variations
        self.ingredient_alias_lookup = {}
        self.ingredient_forms_lookup = {}
        
        # NEW: Store full form data for disambiguation
        self.ingredient_context_lookup = {}
        
        # Track conflicts to debug mapping issues
        conflicts = {}
        
        for vitamin_name, vitamin_data in self.ingredient_map.items():
            standard_name = vitamin_data.get("standard_name", vitamin_name)
            
            # Add standard name and its variations FIRST (prioritize exact matches)
            standard_variations = self.matcher.generate_variations(
                self.matcher.preprocess_text(standard_name)
            )
            for variation in standard_variations:
                if variation in self.ingredient_alias_lookup:
                    existing = self.ingredient_alias_lookup[variation]
                    if existing != standard_name:
                        conflicts[variation] = f"{existing} -> {standard_name}"
                        # Keep the first mapping, don't overwrite
                        continue
                self.ingredient_alias_lookup[variation] = standard_name
            
            # Add vitamin name (key) and its variations
            name_variations = self.matcher.generate_variations(
                self.matcher.preprocess_text(vitamin_name)
            )
            for variation in name_variations:
                if variation in self.ingredient_alias_lookup:
                    existing = self.ingredient_alias_lookup[variation]
                    if existing != standard_name:
                        conflicts[variation] = f"{existing} -> {standard_name}"
                        # Keep the first mapping, don't overwrite
                        continue
                self.ingredient_alias_lookup[variation] = standard_name
            
            # Add all form aliases and their variations
            for form_name, form_data in (vitamin_data.get("forms", {}) or {}).items():
                form_variations = self.matcher.generate_variations(
                    self.matcher.preprocess_text(form_name)
                )
                for variation in form_variations:
                    if variation in self.ingredient_alias_lookup:
                        existing = self.ingredient_alias_lookup[variation]
                        if existing != standard_name:
                            conflicts[variation] = f"{existing} -> {standard_name}"
                            # Keep the first mapping, don't overwrite
                            continue
                    self.ingredient_alias_lookup[variation] = standard_name
                    self.ingredient_forms_lookup[variation] = form_name
                
                # Add aliases for this form
                for alias in form_data.get("aliases", []) or []:
                    alias_variations = self.matcher.generate_variations(
                        self.matcher.preprocess_text(alias)
                    )
                    for variation in alias_variations:
                        if variation in self.ingredient_alias_lookup:
                            existing = self.ingredient_alias_lookup[variation]
                            if existing != standard_name:
                                conflicts[variation] = f"{existing} -> {standard_name}"
                                # Keep the first mapping, don't overwrite
                                continue
                        self.ingredient_alias_lookup[variation] = standard_name
                        self.ingredient_forms_lookup[variation] = form_name
                        
                        # Store full form data for disambiguation
                        self.ingredient_context_lookup[variation] = {
                            'standard_name': standard_name,
                            'form_name': form_name,
                            'form_data': form_data
                        }
        
        # Log conflicts for debugging (reduced verbosity)
        if conflicts:
            logger.debug(f"Found {len(conflicts)} mapping conflicts - keeping first mappings")
            for variation, conflict in list(conflicts.items())[:5]:  # Show first 5
                logger.debug(f"Conflict: '{variation}' {conflict}")
        
        # Build enhanced allergen lookup
        self.allergen_lookup = {}

        for allergen in self.allergens_db.get("common_allergens", []) or []:
            standard_name = allergen["standard_name"]

            # Add standard name variations
            name_variations = self.matcher.generate_variations(
                self.matcher.preprocess_text(standard_name)
            )
            for variation in name_variations:
                self.allergen_lookup[variation] = allergen

            # Add alias variations
            for alias in allergen.get("aliases", []) or []:
                alias_variations = self.matcher.generate_variations(
                    self.matcher.preprocess_text(alias)
                )
                for variation in alias_variations:
                    self.allergen_lookup[variation] = allergen
        
        # Build enhanced harmful additive lookup
        self.harmful_lookup = {}

        for additive in self.harmful_additives.get("harmful_additives", []) or []:
            standard_name = additive["standard_name"]

            # Add standard name variations
            name_variations = self.matcher.generate_variations(
                self.matcher.preprocess_text(standard_name)
            )
            for variation in name_variations:
                self.harmful_lookup[variation] = additive

            # Add alias variations
            for alias in additive.get("aliases", []) or []:
                alias_variations = self.matcher.generate_variations(
                    self.matcher.preprocess_text(alias)
                )
                for variation in alias_variations:
                    self.harmful_lookup[variation] = additive
                    
                # CRITICAL FIX: Add simple harmful ingredients to main ingredient lookup
                # This prevents fuzzy matching from picking up complex forms instead
                processed_alias = self.matcher.preprocess_text(alias)
                if processed_alias not in self.ingredient_alias_lookup:
                    self.ingredient_alias_lookup[processed_alias] = alias  # Use the alias as standard name
        
        # Build enhanced other ingredients lookup (safe additives/excipients - FDA "Other Ingredients")
        self.other_ingredients_lookup = {}
        for other_ing in self.other_ingredients.get("other_ingredients", []) or []:
            standard_name = other_ing["standard_name"]
            # Add standard name variations
            name_variations = self.matcher.generate_variations(
                self.matcher.preprocess_text(standard_name)
            )
            for variation in name_variations:
                self.other_ingredients_lookup[variation] = other_ing

            # Add alias variations
            for alias in other_ing.get("aliases", []) or []:
                alias_variations = self.matcher.generate_variations(
                    self.matcher.preprocess_text(alias)
                )
                for variation in alias_variations:
                    self.other_ingredients_lookup[variation] = other_ing

                # Add to main ingredient lookup to prevent fuzzy conflicts
                processed_alias = self.matcher.preprocess_text(alias)
                if processed_alias not in self.ingredient_alias_lookup:
                    self.ingredient_alias_lookup[processed_alias] = alias

        # CRITICAL FIX: Add other ingredients to main lookup to prevent fuzzy conflicts
        for ingredient in self.other_ingredients.get("other_ingredients", []) or []:
            standard_name = ingredient.get("standard_name", "")
            if standard_name:
                processed_standard = self.matcher.preprocess_text(standard_name)
                if processed_standard not in self.ingredient_alias_lookup:
                    self.ingredient_alias_lookup[processed_standard] = standard_name
                    
            for alias in ingredient.get("aliases", []) or []:
                processed_alias = self.matcher.preprocess_text(alias)
                if processed_alias not in self.ingredient_alias_lookup:
                    self.ingredient_alias_lookup[processed_alias] = alias

        logger.info(f"Built lookup indices with {len(self.ingredient_alias_lookup)} ingredient variations")
        logger.info(f"Built allergen index with {len(self.allergen_lookup)} variations")
        logger.info(f"Built harmful additive index with {len(self.harmful_lookup)} variations")
        logger.info(f"Built other ingredients index with {len(self.other_ingredients_lookup)} variations")

        # Build optimized fast lookups
        self._build_fast_lookups_impl()
    
    def _enhanced_ingredient_mapping(self, name: str, forms: List[str] = None) -> Tuple[str, bool, List[str]]:
        """
        Enhanced ingredient mapping with comprehensive validation and thread-safe caching
        """
        # SAFETY: Comprehensive input validation
        validated_name = self.matcher.validate_input(name, "ingredient_name")
        if not validated_name:
            return "", False, []

        # SAFETY: Validate and clean forms list
        validated_forms = []
        if forms:
            # Handle case where forms might be a dict instead of list
            if isinstance(forms, dict):
                # Extract values from dict or convert to list based on content
                if 'forms' in forms:
                    forms = forms['forms']
                else:
                    forms = list(forms.values()) if forms.values() else []

            # Ensure forms is iterable
            if not hasattr(forms, '__iter__') or isinstance(forms, str):
                forms = [forms] if forms else []

            for form in forms:
                if isinstance(form, dict):
                    # If form is a dict, try to extract a name or convert to string
                    form_str = form.get('name', '') or str(form)
                    validated_form = self.matcher.validate_input(form_str, "ingredient_form")
                    if validated_form:
                        validated_forms.append(validated_form)
                elif isinstance(form, (str, int, float)):  # Only process string-like values
                    validated_form = self.matcher.validate_input(str(form), "ingredient_form")
                    if validated_form:  # Only add non-empty forms
                        validated_forms.append(validated_form)

        self._cache_stats["ingredient_calls"] += 1

        # Use thread-safe @lru_cache - convert list to tuple for hashability
        forms_tuple = tuple(sorted(validated_forms)) if validated_forms else ()
        return self._enhanced_ingredient_mapping_cached(validated_name, forms_tuple)

    @functools.lru_cache(maxsize=2000)  # PERFORMANCE: Reduced from 10000 to prevent memory bloat
    def _enhanced_ingredient_mapping_cached(self, name: str, forms_tuple: tuple) -> Tuple[str, bool, List[str]]:
        """Thread-safe cached ingredient mapping"""
        forms = list(forms_tuple) if forms_tuple else []
        return self._perform_ingredient_mapping(name, forms)

    def _perform_ingredient_mapping(self, name: str, forms: List[str] = None) -> Tuple[str, bool, List[str]]:
        """Perform the actual ingredient mapping logic"""
        forms = forms or []

        # Preprocess the input name
        processed_name = self.matcher.preprocess_text(name)

        # SAFETY FIRST: Try critical exact matching for short aliases (B1, D3, K2, etc.)
        critical_match = self.matcher.exact_match_critical_aliases(name, list(self.ingredient_alias_lookup.keys()))
        if critical_match:
            mapped_name = self.ingredient_alias_lookup[critical_match]
            logger.info(f"CRITICAL vitamin/mineral exact match: '{name}' -> '{mapped_name}'")
            return mapped_name, True, forms or []

        # Debug logging for specific ingredients
        if name in ["Molybdenum", "Choline", "Alpha-Lipoic Acid"]:
            logger.debug(f"Mapping '{name}' -> processed: '{processed_name}'")
            logger.debug(f"Is '{processed_name}' in lookup? {processed_name in self.ingredient_alias_lookup}")

        # Try exact match
        if processed_name in self.ingredient_alias_lookup:
            # Check for disambiguation if needed
            if processed_name in self.ingredient_context_lookup:
                context_data = self.ingredient_context_lookup[processed_name]
                form_data = context_data.get('form_data', {})
                
                # If this ingredient has context rules, use disambiguation
                if form_data.get('context_include') or form_data.get('context_exclude'):
                    # Use the original full text as context for disambiguation
                    context_text = name.lower()
                    if not self.matcher.disambiguate_ingredient_match(context_text, form_data):
                        # Disambiguation failed, try fuzzy matching instead
                        pass
                    else:
                        mapped_name = self.ingredient_alias_lookup[processed_name]
                        mapped_forms = []
                        
                        # Try to find specific forms
                        for form in forms:
                            processed_form = self.matcher.preprocess_text(form)
                            if processed_form in self.ingredient_forms_lookup:
                                mapped_forms.append(self.ingredient_forms_lookup[processed_form])
                        
                        return mapped_name, True, mapped_forms or forms
                else:
                    # No disambiguation needed
                    mapped_name = self.ingredient_alias_lookup[processed_name]
                    mapped_forms = []
                    
                    # Try to find specific forms
                    for form in forms:
                        processed_form = self.matcher.preprocess_text(form)
                        if processed_form in self.ingredient_forms_lookup:
                            mapped_forms.append(self.ingredient_forms_lookup[processed_form])
                    
                    return mapped_name, True, mapped_forms or forms
            else:
                # No context data available, proceed normally
                mapped_name = self.ingredient_alias_lookup[processed_name]
                mapped_forms = []
                
                # Try to find specific forms
                for form in forms:
                    processed_form = self.matcher.preprocess_text(form)
                    if processed_form in self.ingredient_forms_lookup:
                        mapped_forms.append(self.ingredient_forms_lookup[processed_form])
                
                return mapped_name, True, mapped_forms or forms
        
        # Try fuzzy matching against all ingredient variations (using cached list)
        # SAFETY: Pass 'active' category for ingredient matching - this will be BLOCKED for critical vitamins/minerals
        fuzzy_match, score = self.matcher.fuzzy_match(processed_name, self.ingredient_variations, "active")
        
        if fuzzy_match:
            # Check for disambiguation on fuzzy matches too
            if fuzzy_match in self.ingredient_context_lookup:
                context_data = self.ingredient_context_lookup[fuzzy_match]
                form_data = context_data.get('form_data', {})
                
                # If this ingredient has context rules, use disambiguation
                if form_data.get('context_include') or form_data.get('context_exclude'):
                    # Use the original full text as context for disambiguation
                    context_text = name.lower()
                    if not self.matcher.disambiguate_ingredient_match(context_text, form_data):
                        # Disambiguation failed, continue searching
                        pass
                    else:
                        mapped_name = self.ingredient_alias_lookup[fuzzy_match]
                        logger.debug(f"Fuzzy matched '{name}' -> '{mapped_name}' (score: {score}) with disambiguation")
                        
                        # Try to find specific forms
                        mapped_forms = []
                        for form in forms:
                            processed_form = self.matcher.preprocess_text(form)
                            if processed_form in self.ingredient_forms_lookup:
                                mapped_forms.append(self.ingredient_forms_lookup[processed_form])
                            else:
                                # Try fuzzy matching for forms (using cached list)
                                # SAFETY: Forms are generally safe for fuzzy matching
                                fuzzy_form, form_score = self.matcher.fuzzy_match(processed_form, self.form_variations, "inactive")
                                if fuzzy_form:
                                    mapped_forms.append(self.ingredient_forms_lookup[fuzzy_form])
                                    logger.debug(f"Fuzzy matched form '{form}' -> '{fuzzy_form}' (score: {form_score})")
                        
                        return mapped_name, True, mapped_forms or forms
                else:
                    # No disambiguation needed
                    mapped_name = self.ingredient_alias_lookup[fuzzy_match]
                    logger.debug(f"Fuzzy matched '{name}' -> '{mapped_name}' (score: {score})")
                    
                    # Try to find specific forms
                    mapped_forms = []
                    for form in forms:
                        processed_form = self.matcher.preprocess_text(form)
                        if processed_form in self.ingredient_forms_lookup:
                            mapped_forms.append(self.ingredient_forms_lookup[processed_form])
                        else:
                            # Try fuzzy matching for forms (using cached list)
                            # SAFETY: Forms are generally safe for fuzzy matching
                            fuzzy_form, form_score = self.matcher.fuzzy_match(processed_form, self.form_variations, "inactive")
                            if fuzzy_form:
                                mapped_forms.append(self.ingredient_forms_lookup[fuzzy_form])
                                logger.debug(f"Fuzzy matched form '{form}' -> '{fuzzy_form}' (score: {form_score})")
                    
                    return mapped_name, True, mapped_forms or forms
            else:
                # No context data available, proceed normally
                mapped_name = self.ingredient_alias_lookup[fuzzy_match]
                logger.debug(f"Fuzzy matched '{name}' -> '{mapped_name}' (score: {score})")
                
                # Try to find specific forms
                mapped_forms = []
                for form in forms:
                    processed_form = self.matcher.preprocess_text(form)
                    if processed_form in self.ingredient_forms_lookup:
                        mapped_forms.append(self.ingredient_forms_lookup[processed_form])
                    else:
                        # Try fuzzy matching for forms (using cached list)
                        # SAFETY: Forms are generally safe for fuzzy matching
                        fuzzy_form, form_score = self.matcher.fuzzy_match(processed_form, self.form_variations, "inactive")
                        if fuzzy_form:
                            mapped_forms.append(self.ingredient_forms_lookup[fuzzy_form])
                            logger.debug(f"Fuzzy matched form '{form}' -> '{fuzzy_form}' (score: {form_score})")
                
                return mapped_name, True, mapped_forms or forms
        
        # Check if ingredient exists in harmful additives database
        harmful_info = self._enhanced_harmful_check(name)
        if harmful_info["category"] != "none":
            # DATA INTEGRITY FIX: Return canonical name from database, not input name
            # This ensures fuzzy-matched ingredients use standardized names
            processed_name = self.matcher.preprocess_text(name)
            if processed_name in self.harmful_lookup:
                canonical_name = self.harmful_lookup[processed_name].get("standard_name", name)
            else:
                # Must be a fuzzy match - find the canonical name
                fuzzy_match, _ = self.matcher.fuzzy_match(processed_name, self.harmful_variations, "harmful")
                canonical_name = self.harmful_lookup.get(fuzzy_match, {}).get("standard_name", name) if fuzzy_match else name

            logger.debug(f"Found '{name}' in harmful additives database -> '{canonical_name}' (category: {harmful_info['category']})")
            return canonical_name, True, forms

        # Check if ingredient exists in allergens database
        allergen_info = self._enhanced_allergen_check(name, forms)
        if allergen_info["is_allergen"]:
            # DATA INTEGRITY FIX: Return canonical name from database, not input name
            # This ensures fuzzy-matched allergens use standardized names
            processed_name = self.matcher.preprocess_text(name)
            if processed_name in self.allergen_lookup:
                canonical_name = self.allergen_lookup[processed_name].get("standard_name", name)
            else:
                # Must be a fuzzy match - find the canonical name
                fuzzy_match, _ = self.matcher.fuzzy_match(processed_name, self.allergen_variations, "allergen")
                canonical_name = self.allergen_lookup.get(fuzzy_match, {}).get("standard_name", name) if fuzzy_match else name

            logger.debug(f"Found '{name}' in allergens database -> '{canonical_name}' (type: {allergen_info['type']})")
            return canonical_name, True, forms
        
        # Use unified fast lookup for all remaining databases
        fast_result = self._fast_ingredient_lookup(name)
        if fast_result.get("mapped", False):
            result_type = fast_result.get("type", "unknown")
            standard_name = fast_result.get("standard_name", name)
            logger.debug(f"Found '{name}' in {result_type} database -> '{standard_name}' (priority: {fast_result.get('priority', 'N/A')})")
            return standard_name, True, forms
        
        # Don't track as unmapped here - will be handled at higher level
        # after all database checks (harmful, allergen, etc.) are complete
        return name, False, forms
    
    def _enhanced_allergen_check(self, name: str, forms: List[str] = None) -> Dict[str, Any]:
        """Enhanced allergen checking with thread-safe caching"""
        forms = forms or []
        self._cache_stats["allergen_calls"] += 1

        # Use thread-safe @lru_cache - convert list to tuple for hashability
        forms_tuple = tuple(sorted(forms)) if forms else ()
        return self._enhanced_allergen_check_cached(name, forms_tuple)

    @functools.lru_cache(maxsize=1000)  # PERFORMANCE: Reduced from 5000 to prevent memory bloat
    def _enhanced_allergen_check_cached(self, name: str, forms_tuple: tuple) -> Dict[str, Any]:
        """Thread-safe cached allergen checking"""
        forms = list(forms_tuple) if forms_tuple else []

        result = {
            "is_allergen": False,
            "type": None,
            "severity": None
        }

        check_terms = [name] + forms

        for term in check_terms:
            processed_term = self.matcher.preprocess_text(term)

            # Try exact match
            if processed_term in self.allergen_lookup:
                allergen = self.allergen_lookup[processed_term]
                # SAFETY: Ensure standard_name exists
                standard_name = allergen.get("standard_name", "")
                if standard_name:
                    result["is_allergen"] = True
                    result["type"] = standard_name.lower()
                    result["severity"] = allergen.get("severity_level", "low")
                    break

            # Try fuzzy match - SAFETY: Allergens should NOT use fuzzy matching for safety
            # This will be BLOCKED by the safety check but we'll try anyway to log the attempt
            fuzzy_match, score = self.matcher.fuzzy_match(processed_term, self.allergen_variations, "allergen")
            if fuzzy_match:
                allergen = self.allergen_lookup[fuzzy_match]
                # SAFETY: Ensure standard_name exists
                standard_name = allergen.get("standard_name", "")
                if standard_name:
                    result["is_allergen"] = True
                    result["type"] = standard_name.lower()
                    result["severity"] = allergen.get("severity_level", "low")
                    logger.debug(f"Fuzzy allergen match '{term}' -> '{fuzzy_match}' (score: {score})")
                    break

        return result
    
    def _enhanced_harmful_check(self, name: str) -> Dict[str, Any]:
        """Enhanced harmful additive checking with thread-safe caching"""
        self._cache_stats["harmful_calls"] += 1
        return self._enhanced_harmful_check_cached(name)

    @functools.lru_cache(maxsize=1000)  # PERFORMANCE: Reduced from 5000 to prevent memory bloat
    def _enhanced_harmful_check_cached(self, name: str) -> Dict[str, Any]:
        """Thread-safe cached harmful checking"""
        result = {
            "category": "none",
            "risk_level": None
        }

        processed_name = self.matcher.preprocess_text(name)

        # Try exact match
        if processed_name in self.harmful_lookup:
            harmful = self.harmful_lookup[processed_name]
            result["category"] = harmful.get("category", "other")
            result["risk_level"] = harmful.get("risk_level", "low")
        else:
            # Try fuzzy match (using cached list) - SAFETY: Harmful additives should NOT use fuzzy matching
            fuzzy_match, score = self.matcher.fuzzy_match(processed_name, self.harmful_variations, "harmful")
            if fuzzy_match:
                harmful = self.harmful_lookup[fuzzy_match]
                result["category"] = harmful.get("category", "other")
                result["risk_level"] = harmful.get("risk_level", "low")
                logger.debug(f"Fuzzy harmful match '{name}' -> '{fuzzy_match}' (score: {score})")

        return result

    def _enhanced_non_harmful_check(self, name: str) -> Dict[str, Any]:
        """Enhanced non-harmful additive checking with thread-safe caching"""
        self._cache_stats["non_harmful_calls"] += 1
        return self._enhanced_non_harmful_check_cached(name)

    @functools.lru_cache(maxsize=1000)  # PERFORMANCE: Reduced from 5000 to prevent memory bloat
    def _enhanced_non_harmful_check_cached(self, name: str) -> Dict[str, Any]:
        """Thread-safe cached non-harmful checking"""
        result = {
            "category": "none",
            "additive_type": None,
            "clean_label_score": None,
            "is_additive": None
        }

        processed_name = self.matcher.preprocess_text(name)

        # Try exact match
        if processed_name in self.other_ingredients_lookup:
            other_ing = self.other_ingredients_lookup[processed_name]
            result["category"] = other_ing.get("category", "other")
            result["additive_type"] = other_ing.get("additive_type", "unknown")
            result["clean_label_score"] = other_ing.get("clean_label_score", 7)
            result["is_additive"] = other_ing.get("is_additive", False)
        else:
            # Try fuzzy match (using cached list) - SAFETY: Other ingredients are safe for fuzzy matching
            fuzzy_match, score = self.matcher.fuzzy_match(processed_name, self.non_harmful_variations, "inactive")
            if fuzzy_match:
                other_ing = self.other_ingredients_lookup[fuzzy_match]
                result["category"] = other_ing.get("category", "other")
                result["additive_type"] = other_ing.get("additive_type", "unknown")
                result["clean_label_score"] = other_ing.get("clean_label_score", 7)
                result["is_additive"] = other_ing.get("is_additive", False)
                logger.debug(f"Fuzzy other ingredient match '{name}' -> '{fuzzy_match}' (score: {score})")

        return result
    
    def _check_banned_recalled(self, name: str) -> bool:
        """Check if ingredient exists in banned/recalled ingredients database"""
        processed_name = self.matcher.preprocess_text(name)
        
        # Get ALL arrays from the banned/recalled database dynamically
        arrays_to_check = []
        for key, value in self.banned_recalled.items():
            if isinstance(value, list) and len(value) > 0:
                # Check if items in the list have the expected structure for banned substances
                if any(isinstance(item, dict) and 'standard_name' in item for item in value):
                    arrays_to_check.append(key)

        # Define critical sections for prioritized checking (substring/fuzzy matching)
        critical_sections = [
            "permanently_banned", "nootropic_banned", "sarms_prohibited",
            "illegal_spiking_agents", "new_emerging_threats", "pharmaceutical_adulterants"
        ]
        
        # Check all arrays in the database for exact matches first
        for array_name in arrays_to_check:
            items = self.banned_recalled.get(array_name, [])

            for item in items:
                # Check standard_name - exact match
                standard_name = self.matcher.preprocess_text(item.get("standard_name", ""))
                if standard_name and processed_name == standard_name:
                    return True

                # Check aliases - exact match
                for alias in item.get("aliases", []) or []:
                    processed_alias = self.matcher.preprocess_text(alias)
                    if processed_name == processed_alias:
                        return True

        # Check for substring matches (bidirectional) for critical banned substances
        critical_sections = ["permanently_banned", "sarms_prohibited", "nootropic_banned",
                           "illegal_spiking_agents", "new_emerging_threats", "pharmaceutical_adulterants"]

        for array_name in critical_sections:
            items = self.banned_recalled.get(array_name, [])
            for item in items:
                # Check if banned substance name is contained in ingredient name
                standard_name = self.matcher.preprocess_text(item.get("standard_name", ""))
                if standard_name and len(standard_name) >= 4:  # Avoid short false positives
                    if standard_name in processed_name or processed_name in standard_name:
                        logger.warning(f"Substring banned match: '{name}' contains banned substance '{item.get('standard_name', '')}'")
                        return True

                # Check aliases for substring matches
                for alias in item.get("aliases", []) or []:
                    processed_alias = self.matcher.preprocess_text(alias)
                    if processed_alias and len(processed_alias) >= 4:  # Avoid short false positives
                        if processed_alias in processed_name or processed_name in processed_alias:
                            logger.warning(f"Substring banned match: '{name}' contains banned substance '{alias}'")
                            return True
        
        # Try fuzzy matching for critical banned substances only (high threshold for safety)
        critical_banned_terms = []
        for array_name in critical_sections:
            items = self.banned_recalled.get(array_name, [])
            for item in items:
                if item.get("severity_level") == "critical":  # Only critical severity for fuzzy matching
                    critical_banned_terms.append(item.get("standard_name", "").lower())
                    critical_banned_terms.extend([alias.lower() for alias in item.get("aliases", []) or []])

        critical_banned_terms = [term for term in critical_banned_terms if term and len(term) >= 5]  # Minimum length 5

        if critical_banned_terms:
            fuzzy_match, score = self.matcher.fuzzy_match(processed_name, critical_banned_terms, "banned")
            # Use higher threshold (0.9) for banned substances to reduce false positives
            if fuzzy_match and score >= 0.9:
                logger.warning(f"CRITICAL: Fuzzy banned match '{name}' -> '{fuzzy_match}' (score: {score})")
                return True
        
        return False
    
    def _priority_based_classification(self, name: str, forms: List[str] = None) -> Dict[str, Any]:
        """
        Priority-based ingredient classification to handle overlapping ingredients
        
        Priority order (highest to lowest):
        1. Banned/Recalled ingredients (critical safety)
        2. Harmful additives (risk assessment)
        3. Non-harmful additives (safe additives flagging)
        4. Allergens (safety concern)
        5. Passive/Inactive ingredients (quality neutral)
        
        Returns classification with applied priority rules
        """
        forms = forms or []
        
        # Initialize all classification results
        banned_info = {"is_banned": False, "severity": None, "category": None}
        harmful_info = {"category": "none", "risk_level": None}
        non_harmful_info = {"category": "none", "additive_type": None, "clean_label_score": None}
        allergen_info = {"is_allergen": False, "type": None, "severity": None}
        passive_info = {"is_passive": False, "category": None}
        
        # Use unified fast lookup for all databases
        fast_result = self._fast_ingredient_lookup(name)
        result_type = fast_result.get("type", "none") if fast_result.get("mapped", False) else "none"

        # Map fast lookup results to expected boolean/dict formats
        is_banned = result_type == "banned"
        is_harmful = self._enhanced_harmful_check(name)  # Keep existing for complex logic
        is_non_harmful = self._enhanced_non_harmful_check(name)  # Keep existing for complex logic
        is_allergen = self._enhanced_allergen_check(name, forms)  # Keep existing for complex logic
        is_passive = result_type == "passive"
        
        # Apply priority rules
        if is_banned:
            # PRIORITY 1: Banned/Recalled - highest priority, overrides all others
            banned_info = {"is_banned": True, "severity": "critical", "category": "banned"}
            # Still populate other info but they won't be used for scoring
            harmful_info = is_harmful
            non_harmful_info = is_non_harmful
            allergen_info = is_allergen
            passive_info = {"is_passive": False, "category": None}  # Override passive classification
            
        elif is_harmful["category"] != "none":
            # PRIORITY 2: Harmful additives - second priority
            harmful_info = is_harmful
            non_harmful_info = {"category": "none", "additive_type": None, "clean_label_score": None}  # Override
            allergen_info = is_allergen  # Allow allergen info to coexist
            passive_info = {"is_passive": False, "category": None}  # Override passive classification
            
        elif is_non_harmful["category"] != "none":
            # PRIORITY 3: Non-harmful additives - third priority (flagged but safe)
            non_harmful_info = is_non_harmful
            harmful_info = {"category": "none", "risk_level": None}  # Override
            allergen_info = is_allergen  # Allow allergen info to coexist
            passive_info = {"is_passive": False, "category": None}  # Override passive classification
            
        elif is_allergen["is_allergen"]:
            # PRIORITY 4: Allergens - fourth priority
            allergen_info = is_allergen
            # Reset others to none since allergen takes priority over passive
            harmful_info = {"category": "none", "risk_level": None}
            non_harmful_info = {"category": "none", "additive_type": None, "clean_label_score": None}
            passive_info = {"is_passive": False, "category": None}  # Override passive classification
            
        elif is_passive:
            # PRIORITY 5: Passive/Inactive - lowest priority, only applies if no higher priority match
            passive_info = {"is_passive": True, "category": "passive_ingredient"}
            # Keep other classifications as none
            harmful_info = {"category": "none", "risk_level": None}
            non_harmful_info = {"category": "none", "additive_type": None, "clean_label_score": None}
            allergen_info = {"is_allergen": False, "type": None, "severity": None}
        
        else:
            # No classification found in any database
            harmful_info = is_harmful  # Might still have fuzzy matches
            non_harmful_info = is_non_harmful  # Might still have fuzzy matches
            allergen_info = is_allergen  # Might still have fuzzy matches
        
        return {
            "banned_info": banned_info,
            "harmful_info": harmful_info,
            "non_harmful_info": non_harmful_info,
            "allergen_info": allergen_info,
            "passive_info": passive_info,
            "priority_applied": {
                "banned": is_banned,
                "harmful": is_harmful["category"] != "none",
                "non_harmful": is_non_harmful["category"] != "none",
                "allergen": is_allergen["is_allergen"],
                "passive": is_passive
            }
        }
    
    def _flatten_nested_ingredients(self, ingredient_rows: List[Dict]) -> List[Dict]:
        """Flatten nested ingredients from blends for better scoring, preserving blend structure"""
        flattened = []
        
        for ing in ingredient_rows:
            # Add the main ingredient
            flattened.append(ing)
            
            # For proprietary blends, nested ingredients are already processed in the main ingredient
            # Only add nested ingredients to flattened list if they're not part of a proprietary blend
            nested = ing.get("nestedRows", [])
            is_proprietary_blend = self._is_proprietary_blend_name(ing.get("name", ""))
            
            if nested and not is_proprietary_blend:
                for nested_ing in nested:
                    # Mark as part of a blend
                    nested_ing["parentBlend"] = ing.get("name", "Unknown Blend")
                    nested_ing["isNestedIngredient"] = True
                    
                    # Recursively flatten if there are more levels
                    if nested_ing.get("nestedRows"):
                        sub_flattened = self._flatten_nested_ingredients([nested_ing])
                        flattened.extend(sub_flattened)
                    else:
                        flattened.append(nested_ing)
        
        return flattened
    
    def normalize_product(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhanced product normalization with improved ingredient mapping
        """
        try:
            # Extract basic product info
            product_id = str(raw_data.get("id", ""))
            
            # Process status and dates
            off_market = raw_data.get("offMarket", 0)
            status = "discontinued" if off_market == 1 else "active"
            discontinued_date = self._extract_discontinued_date(raw_data.get("events", []) or [])
            
            # Generate image URL
            image_url = self._generate_image_url(raw_data.get("thumbnail", ""), product_id)
            
            # Process contacts
            contacts = self._process_contacts(raw_data.get("contacts", []) or [])
            
            # Flatten and process ingredients with enhanced mapping
            raw_ingredients = raw_data.get("ingredientRows", []) or []
            flattened_ingredients = self._flatten_nested_ingredients(raw_ingredients)
            
            # Extract nutritional warnings before filtering out nutrition facts
            # Need to check both active ingredients and other ingredients for nutritional facts
            # Handle both "otherIngredients" and "otheringredients" keys
            other_ing_data = raw_data.get("otherIngredients", raw_data.get("otheringredients", {})) or {}
            other_ingredients_raw = other_ing_data.get("ingredients", [])
            # Handle None values from DSLD data
            if other_ingredients_raw is None:
                other_ingredients_raw = []
            all_ingredients_for_warnings = flattened_ingredients + other_ingredients_raw
            nutritional_warnings = self._extract_nutritional_warnings(all_ingredients_for_warnings)
            
            active_ingredients = self._process_ingredients_enhanced(flattened_ingredients, is_active=True)
            
            # Process other ingredients - handle both key formats
            inactive_ingredients = self._process_other_ingredients_enhanced(other_ing_data)
            
            # Process statements
            statements = self._process_statements(raw_data.get("statements", []) or [])
            
            # Process claims
            claims = self._process_claims(raw_data.get("claims", []) or [])
            
            # Process serving sizes
            serving_sizes = self._process_serving_sizes(raw_data.get("servingSizes", []) or [])
            
            # Extract quality flags
            quality_flags = self._extract_quality_flags(
                active_ingredients, 
                inactive_ingredients, 
                statements
            )
            
            # CRITICAL FIX: Aggregate GMP certifications from statements to contacts
            # Check if any statement has GMP certification
            has_gmp_from_statements = any(stmt.get("gmpCertified", False) for stmt in statements)
            if has_gmp_from_statements and contacts:
                # contacts is a list, update all contact entries
                for contact in contacts:
                    contact["isGMP"] = True
                
            # Extract clinical evidence from statements
            clinical_evidence_mentions = []
            for stmt in statements:
                notes = stmt.get("notes", "")
                for pattern in CLINICAL_EVIDENCE_PATTERNS:
                    match = re.search(pattern, notes, re.IGNORECASE)
                    if match:
                        try:
                            clinical_evidence_mentions.append(match.group(0))
                        except IndexError:
                            # Skip if group access fails
                            pass
            
            # Calculate mapping statistics
            total_ingredients = len(active_ingredients) + len(inactive_ingredients)
            mapped_ingredients = sum(1 for ing in active_ingredients + inactive_ingredients if ing.get("mapped"))
            
            # Calculate proprietary blend disclosure statistics
            blend_stats = self._calculate_blend_disclosure_stats(active_ingredients + inactive_ingredients)

            # Industry benchmarking against transparency leaders
            industry_benchmark = self._benchmark_against_industry_leaders(blend_stats)

            # Enhanced penalty weighting based on ingredient category risk
            penalty_weighting = self._calculate_enhanced_penalty_weighting(
                active_ingredients + inactive_ingredients, blend_stats
            )
            
            # Extract all certifications for product-level aggregation
            all_certifications = []
            for stmt in statements:
                all_certifications.extend(stmt.get("certifications", []) or [])
            
            # Calculate full ingredient disclosure flag for transparency
            has_full_disclosure = self._has_full_ingredient_disclosure(blend_stats)

            # Build cleaned product
            cleaned = {
                # Core identifiers
                "id": product_id,
                "fullName": raw_data.get("fullName", ""),
                "brandName": raw_data.get("brandName", ""),
                "upcSku": raw_data.get("upcSku", ""),
                "hasOuterCarton": raw_data.get("hasOuterCarton", None),
                "upcValid": self._validate_upc(raw_data.get("upcSku", "")),

                # Status
                "status": status,
                "discontinuedDate": discontinued_date,
                "offMarket": off_market,
                
                # Product details
                "servingsPerContainer": self._safe_int(raw_data.get("servingsPerContainer", 0)),
                "netContents": self._extract_net_contents(raw_data.get("netContents", [])),
                "targetGroups": raw_data.get("targetGroups", []) or [],
                "productType": self._extract_field_value(raw_data.get("productType", "")),
                "physicalState": self._extract_field_value(raw_data.get("physicalState", "")),
                
                # Images
                "imageUrl": image_url,
                "images": raw_data.get("images", []) or [],
                
                # Manufacturer info
                "contacts": contacts,
                
                # Events
                "events": raw_data.get("events", []) or [],
                
                # Ingredients
                "activeIngredients": active_ingredients,
                "inactiveIngredients": inactive_ingredients,
                
                # Statements and claims (with original preserved)
                "statements": statements,
                "claims": claims,
                "original_statements": raw_data.get("statements", []) or [],  # Preserve raw statements for claim extraction
                
                # Serving info
                "servingSizes": serving_sizes,
                
                # Label relationships
                "labelRelationships": raw_data.get("labelRelationships", []) or [],
                
                # Combined label text for search (with original preserved)
                "labelText": self._generate_label_text(
                    active_ingredients,
                    inactive_ingredients,
                    statements
                ),
                "original_label_text": self._extract_original_label_text(raw_data),  # Preserve raw text for enrichment parsing
                
                # RDA compliance (empty for future use)
                "rdaCompliance": [],
                
                # Nutritional warnings for UI display
                "nutritionalWarnings": nutritional_warnings,
                
                # Certifications (product-level aggregation)
                "hasCertifications": len(all_certifications) > 0,
                "certificationTypes": list(set(all_certifications)),

                # Transparency flag for data preservation
                "has_full_ingredient_disclosure": has_full_disclosure,
                
                # Enhanced metadata
                "metadata": {
                    "lastCleaned": datetime.utcnow().isoformat() + "Z",
                    "cleaningVersion": "2.0.0",  # Enhanced version
                    "completeness": {
                        "score": 0,  # Will be set by validator
                        "missingFields": [],
                        "criticalFieldsComplete": True
                    },
                    "qualityFlags": quality_flags,
                    "mappingStats": {
                        "totalIngredients": total_ingredients,
                        "mappedIngredients": mapped_ingredients,
                        "unmappedIngredients": total_ingredients - mapped_ingredients,
                        "mappingRate": round((mapped_ingredients / total_ingredients * 100), 2) if total_ingredients > 0 else 0
                    },
                    "enhancedFeatures": {
                        "fuzzyMatchingUsed": FUZZY_AVAILABLE,
                        "nestedIngredientsFlattened": len(flattened_ingredients) > len(raw_ingredients),
                        "preprocessingApplied": True
                    },
                    "proprietaryBlendStats": blend_stats,
                    "industryBenchmark": industry_benchmark,
                    "penaltyWeighting": penalty_weighting
                }
            }
            
            return cleaned
            
        except Exception as e:
            logger.error(f"Error normalizing product {raw_data.get('id', 'unknown')}: {str(e)}")
            raise
    
    def _process_ingredients_enhanced(self, ingredient_rows: List[Dict], is_active: bool = True) -> List[Dict]:
        """Process ingredients with enhanced mapping"""
        processed = []
        
        for ing in ingredient_rows:
            processed_ing = self._process_single_ingredient_enhanced(ing, is_active)
            # Skip None values (nutrition facts that were filtered out)
            if processed_ing is not None:
                processed.append(processed_ing)
        
        return processed
    
    def _process_single_ingredient_enhanced(self, ing: Dict, is_active: bool) -> Dict[str, Any]:
        """Process a single ingredient with enhanced mapping"""
        name = ing.get("name", "")
        notes = ing.get("notes", "")
        forms = [f.get("name", "") for f in ing.get("forms", []) or []]

        # Extract form information from ingredient name if no explicit forms provided
        if not forms and name:
            extracted_forms = self._extract_forms_from_ingredient_name(name)
            if extracted_forms:
                forms = extracted_forms

        # Skip nutritional facts - these are not supplement ingredients
        # Note: Harmful nutrition facts (trans fat, sugar, sodium) are captured by
        # _extract_nutritional_warnings() which runs before ingredient processing
        if self._is_nutrition_fact(name):
            logger.debug(f"Skipping nutrition fact: {name}")
            return None
        
        # Enhanced mapping with fuzzy matching
        standard_name, mapped, mapped_forms = self._enhanced_ingredient_mapping(name, forms)
        
        # Get ingredient quality info - ONLY for active ingredients
        quality_info = {"natural": False, "bio_score": 0}
        if is_active:
            quality_info = self._get_ingredient_quality_info(standard_name, mapped_forms)
        
        # Priority-based ingredient classification to handle overlaps
        classification = self._priority_based_classification(name, forms)
        
        # Extract individual classification results with priority handling
        allergen_info = classification["allergen_info"]
        harmful_info = classification["harmful_info"]
        non_harmful_info = classification["non_harmful_info"]
        banned_info = classification["banned_info"]
        passive_info = classification["passive_info"]

        # Extract features from notes
        extracted_features = self._extract_ingredient_features(notes)

        # Process quantity - handle both nested and flat formats
        quantity_data = ing.get("quantity", [])
        
        # If unit is at ingredient level, merge it with quantity data
        if ing.get("unit") and not isinstance(quantity_data, (list, dict)):
            # Convert flat format to nested format for consistent processing
            quantity_data = {"quantity": quantity_data, "unit": ing.get("unit")}
        elif ing.get("unit") and isinstance(quantity_data, dict) and "unit" not in quantity_data:
            # Add unit to existing dict format
            quantity_data["unit"] = ing.get("unit")
            
        quantity, unit, daily_value = self._process_quantity(quantity_data)

        # Check if proprietary - based on quantity OR if name contains blend indicators
        is_proprietary = quantity == 0 or unit == "NP" or self._is_proprietary_blend_name(name)
        
        # Determine disclosure level for proprietary blends and process nested ingredients
        disclosure_level = None
        nested_ingredients_processed = []
        nested_rows = ing.get("nestedRows", [])
        
        if is_proprietary or self._is_proprietary_blend_name(name):
            disclosure_level = self._determine_disclosure_level(name, quantity, unit, nested_rows)

            # Process nested ingredients for blends
            if nested_rows:
                for nested_ing in nested_rows:
                    nested_processed = self._process_single_ingredient_enhanced(nested_ing, is_active)
                    if nested_processed:
                        nested_processed["parentBlend"] = name
                        nested_processed["isNestedIngredient"] = True
                        nested_ingredients_processed.append(nested_processed)

        # An ingredient is considered "mapped" if it's found in ANY reference database
        # This includes ingredient databases, harmful additives, non-harmful additives, allergens, banned, passive databases, or proprietary blends
        is_mapped = (mapped or
                    harmful_info["category"] != "none" or
                    non_harmful_info["category"] != "none" or
                    allergen_info["is_allergen"] or
                    banned_info["is_banned"] or
                    passive_info["is_passive"] or
                    is_proprietary)

        # Track unmapped ingredients only if not found in any database
        # AND not a nutrition fact/label phrase
        if not is_mapped and not self._is_nutrition_fact(name):
            processed_name = self.matcher.preprocess_text(name)
            self.unmapped_ingredients[name] += 1
            self.unmapped_details[name] = {
                "processed_name": processed_name,
                "forms": forms,
                "variations_tried": self.matcher.generate_variations(processed_name),
                "is_active": is_active  # Track whether this is an active ingredient
            }

        return {
            "order": ing.get("order", 0),
            "name": name,
            "standardName": standard_name,
            "quantity": quantity,
            "unit": unit,
            "dailyValue": daily_value,
            "forms": mapped_forms if mapped_forms else (forms if forms else ["unspecified"]),
            "formDetails": " ".join(mapped_forms) if mapped_forms else " ".join(forms),
            "notes": notes,
            "labelPhrases": extracted_features.get("phrases", []),
            "natural": quality_info.get("natural", False),
            "standardized": extracted_features.get("standardized", False),
            "standardizationPercent": extracted_features.get("standardization_percent", None),
            "category": ing.get("category", ""),
            "ingredientGroup": ing.get("ingredientGroup", ""),

            # Enhanced allergen info
            "allergen": allergen_info["is_allergen"],
            "allergenType": allergen_info["type"],
            "allergenSeverity": allergen_info["severity"],

            # Enhanced harmful info
            "harmfulCategory": harmful_info["category"],
            "riskLevel": harmful_info["risk_level"],

            # Enhanced non-harmful additive info
            "nonHarmfulCategory": non_harmful_info["category"],
            "additiveType": non_harmful_info["additive_type"],
            "cleanLabelScore": non_harmful_info["clean_label_score"],

            # Enhanced banned/recalled info
            "isBanned": banned_info["is_banned"],
            "bannedSeverity": banned_info["severity"],
            "bannedCategory": banned_info["category"],

            # Enhanced passive/inactive info
            "isPassiveIngredient": passive_info["is_passive"],
            "passiveCategory": passive_info["category"],

            # Proprietary and mapping
            "proprietaryBlend": is_proprietary,
            "isProprietaryBlend": is_proprietary,
            "disclosureLevel": disclosure_level,  # 'full', 'partial', 'none', or None for non-blends
            "transparencyPercentage": self._calculate_transparency_percentage(nested_rows) if is_proprietary and nested_rows else None,
            "mapped": is_mapped,
            
            # Blend information (if applicable)
            "parentBlend": ing.get("parentBlend", None),
            "isNestedIngredient": ing.get("isNestedIngredient", False),
            
            # Nested ingredients (preserved for blend structure)
            "nestedIngredients": nested_ingredients_processed,
            
            # Clinical dosing validation (evidence-based effectiveness assessment)
            "clinicalDosing": self._validate_clinical_dosing(name, quantity, unit, standard_name),

            # Enrichment placeholders (to be populated during enrichment phase)
            "clinicalEvidence": None,
            "synergyClusters": [],
            "enhancedDelivery": None,
            "brandedForm": None
        }
    
    def _process_other_ingredients_enhanced(self, other_ing_data: Dict) -> List[Dict]:
        """Process inactive/other ingredients with enhanced mapping and parallel processing"""
        ingredients = other_ing_data.get("ingredients", [])

        # Handle None values from DSLD data
        if ingredients is None:
            return []

        if not ingredients:
            return []

        # Normalize ingredients - convert strings to dict format if needed
        # PRESERVE forms exactly as they appear - do NOT expand
        normalized_ingredients = []
        for ing in ingredients:
            if isinstance(ing, str):
                # Convert string to dict format
                normalized_ingredients.append({"name": ing})
            elif isinstance(ing, dict):
                # Keep ingredient as-is, preserving all fields including forms
                normalized_ingredients.append(ing)
            else:
                # Skip invalid entries
                continue

        # OPTIMIZATION: Use parallel processing for large ingredient lists
        # ✅ THREAD-SAFE: Now using @lru_cache decorators for all caching - safe for parallel processing
        if len(normalized_ingredients) >= self._parallel_threshold:
            logger.info(f"🚀 Using parallel processing for {len(normalized_ingredients)} ingredients")
            return self._process_ingredients_parallel(normalized_ingredients)
        else:
            return self._process_ingredients_sequential(normalized_ingredients)

    def _process_ingredients_parallel(self, ingredients: List[Dict]) -> List[Dict]:
        """Process ingredients using parallel execution with functional grouping support"""
        # First, expand any functional groupings (must be done sequentially to preserve order)
        expanded_ingredients = []
        for ing in ingredients:
            name = ing.get("name", "")

            # TRANSPARENCY SCORING: Check for functional grouping
            grouping_data = self.grouping_handler.process_ingredient_for_cleaning(name)

            if grouping_data['type'] == 'functional_group_with_details':
                # Expand into multiple ingredients with functional context
                for specific_ing in grouping_data['ingredients']:
                    expanded_ingredients.append({
                        **ing,  # Copy order and other fields
                        "name": specific_ing,
                        "_functional_context": grouping_data['functional_type'],
                        "_functional_prefix": grouping_data['prefix'],
                        "_transparency": "good"
                    })
            elif grouping_data['type'] in ['functional_group_vague', 'vague_declaration']:
                # Keep as-is but add transparency flags
                expanded_ingredients.append({
                    **ing,
                    "_transparency": "poor",
                    "_vague_disclosure": True,
                    "_vague_flags": grouping_data.get('vague_flags', [])
                })
            else:
                # Regular ingredient
                expanded_ingredients.append({
                    **ing,
                    "_transparency": "standard"
                })

        # Now process expanded ingredients in parallel
        processed = []

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            # Submit all ingredient processing tasks
            future_to_ingredient = {
                executor.submit(self._process_ingredient_for_other_parallel, ing): ing
                for ing in expanded_ingredients
            }

            # Collect results as they complete
            for future in as_completed(future_to_ingredient):
                try:
                    result = future.result()
                    processed.append(result)
                except Exception as e:
                    ingredient = future_to_ingredient[future]
                    logger.error(f"Error processing ingredient '{ingredient.get('name', 'unknown')}': {e}")
                    # Add a basic result for failed processing
                    processed.append({
                        "order": ingredient.get("order", 0),
                        "name": ingredient.get("name", ""),
                        "standardName": ingredient.get("name", ""),
                        "category": ingredient.get("category", ""),
                        "ingredientGroup": ingredient.get("ingredientGroup", ""),
                        "isHarmful": False,
                        "harmfulCategory": "none",
                        "riskLevel": None,
                        "allergen": False,
                        "allergenType": None,
                        "allergenSeverity": None,
                        "mapped": False,
                        "transparency": "standard"
                    })

        # Sort by original order (with safe comparison)
        def safe_order_key(x):
            order = x.get("order", 0)
            # Ensure order is always a number
            try:
                return float(order) if order is not None else 0.0
            except (ValueError, TypeError):
                return 0.0

        processed.sort(key=safe_order_key)
        return processed

    def _process_ingredient_for_other_parallel(self, ingredient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single other/inactive ingredient for parallel execution"""
        name = ingredient_data.get("name", "")

        # Enhanced mapping
        standard_name, mapped, _ = self._enhanced_ingredient_mapping(name)

        # Enhanced checks
        allergen_info = self._enhanced_allergen_check(name)
        harmful_info = self._enhanced_harmful_check(name)

        # Check if proprietary blend
        is_proprietary = self._is_proprietary_blend_name(name)

        # Calculate final mapping status
        is_mapped = (mapped or
                    harmful_info["category"] != "none" or
                    allergen_info["is_allergen"] or
                    is_proprietary)

        # Track unmapped ingredients only if not found in any database
        if not is_mapped and not self._is_nutrition_fact(name):
            processed_name = self.matcher.preprocess_text(name)
            # Thread-safe tracking (Counter is thread-safe for basic operations)
            self.unmapped_ingredients[name] += 1
            self.unmapped_details[name] = {
                "processed_name": processed_name,
                "forms": [],
                "variations_tried": self.matcher.generate_variations(processed_name),
                "is_active": False  # Other ingredients
            }

        # Get non-harmful additive info for correct category
        non_harmful_info = self._enhanced_non_harmful_check(name)

        # Use category from our database if available, otherwise use DSLD category
        db_category = non_harmful_info.get("category", "none")
        if db_category != "none":
            # Use our database category (correct)
            category = db_category
            ingredient_group = non_harmful_info.get("additive_type", ingredient_data.get("ingredientGroup", ""))
        else:
            # Fall back to DSLD category (may be incorrect but better than nothing)
            category = ingredient_data.get("category", "")
            ingredient_group = ingredient_data.get("ingredientGroup", "")

        # Build result with transparency data
        result = {
            "order": ingredient_data.get("order", 0),
            "name": name,
            "standardName": standard_name,
            "category": category,
            "ingredientGroup": ingredient_group,
            "isHarmful": harmful_info["category"] != "none",
            "harmfulCategory": harmful_info["category"],
            "riskLevel": harmful_info["risk_level"],
            "allergen": allergen_info["is_allergen"],
            "allergenType": allergen_info["type"],
            "allergenSeverity": allergen_info["severity"],
            "mapped": is_mapped,
            "transparency": ingredient_data.get("_transparency", "standard")
        }

        # FORMS DISCLOSURE: Check if ingredient has forms array
        # If forms exist, preserve them and mark as disclosed
        # If no forms but it's a functional grouping, mark as undisclosed
        ing_forms = ingredient_data.get("forms", [])

        # List of functional grouping terms
        functional_terms = [
            "natural color", "natural colors",
            "natural flavor", "natural flavors",
            "artificial color", "artificial colors",
            "artificial flavor", "artificial flavors",
            "preservatives", "sweeteners", "enzymes"
        ]

        is_functional_grouping = any(
            term in name.lower()
            for term in functional_terms
        )

        if ing_forms and isinstance(ing_forms, list) and len(ing_forms) > 0:
            # Forms are disclosed - preserve them exactly as they appear
            forms_list = []
            for form_item in ing_forms:
                if isinstance(form_item, dict):
                    form_name = form_item.get("name", "")
                    if form_name:
                        forms_list.append(form_name)
                elif isinstance(form_item, str):
                    forms_list.append(form_item)

            if forms_list:
                result["forms"] = forms_list
                result["forms_disclosed"] = True
                # Good transparency because forms are disclosed
                result["transparency"] = "good"
        elif is_functional_grouping:
            # This is a functional grouping but no forms provided
            result["forms"] = "undisclosed"
            result["forms_disclosed"] = False
            # Keep existing transparency (usually "poor" for vague disclosures)

        # Add functional context if present (from colon-style groupings)
        if "_functional_context" in ingredient_data:
            result["functional_context"] = ingredient_data["_functional_context"]
            result["functional_prefix"] = ingredient_data["_functional_prefix"]

        # Add vague disclosure flags if present
        if ingredient_data.get("_vague_disclosure"):
            result["vague_disclosure"] = True
            result["vague_flags"] = ingredient_data.get("_vague_flags", [])

        return result

    def _process_ingredients_sequential(self, ingredients: List[Dict]) -> List[Dict]:
        """Process ingredients sequentially (for small lists)"""
        processed = []

        for ing in ingredients:
            name = ing.get("name", "")

            # TRANSPARENCY SCORING: Check for functional grouping first
            grouping_data = self.grouping_handler.process_ingredient_for_cleaning(name)

            if grouping_data['type'] == 'functional_group_with_details':
                # Good transparency - preserve with context (e.g., "Natural Colors: Beet Root Powder")
                for specific_ing in grouping_data['ingredients']:
                    # Process each specific ingredient
                    standard_name, mapped, _ = self._enhanced_ingredient_mapping(specific_ing)
                    allergen_info = self._enhanced_allergen_check(specific_ing)
                    harmful_info = self._enhanced_harmful_check(specific_ing)
                    is_proprietary = self._is_proprietary_blend_name(specific_ing)

                    is_mapped = (mapped or
                                harmful_info["category"] != "none" or
                                allergen_info["is_allergen"] or
                                is_proprietary)

                    # Track unmapped if needed
                    if not is_mapped and not self._is_nutrition_fact(specific_ing):
                        processed_name = self.matcher.preprocess_text(specific_ing)
                        self.unmapped_ingredients[specific_ing] += 1
                        self.unmapped_details[specific_ing] = {
                            "processed_name": processed_name,
                            "forms": [],
                            "variations_tried": self.matcher.generate_variations(processed_name),
                            "is_active": False
                        }

                    processed.append({
                        "order": ing.get("order", 0),
                        "name": specific_ing,
                        "standardName": standard_name,
                        "category": ing.get("category", ""),
                        "ingredientGroup": ing.get("ingredientGroup", ""),
                        "isHarmful": harmful_info["category"] != "none",
                        "harmfulCategory": harmful_info["category"],
                        "riskLevel": harmful_info["risk_level"],
                        "allergen": allergen_info["is_allergen"],
                        "allergenType": allergen_info["type"],
                        "allergenSeverity": allergen_info["severity"],
                        "mapped": is_mapped,
                        # TRANSPARENCY SCORING: Add functional context
                        "functional_context": grouping_data['functional_type'],
                        "functional_prefix": grouping_data['prefix'],
                        "transparency": "good"
                    })

            elif grouping_data['type'] in ['functional_group_vague', 'vague_declaration']:
                # Poor transparency - flag vague disclosure (e.g., just "Natural Flavors")
                # Still process the ingredient but flag it
                standard_name, mapped, _ = self._enhanced_ingredient_mapping(name)
                allergen_info = self._enhanced_allergen_check(name)
                harmful_info = self._enhanced_harmful_check(name)
                is_proprietary = self._is_proprietary_blend_name(name)

                is_mapped = (mapped or
                            harmful_info["category"] != "none" or
                            allergen_info["is_allergen"] or
                            is_proprietary)

                # Track unmapped if needed
                if not is_mapped and not self._is_nutrition_fact(name):
                    processed_name = self.matcher.preprocess_text(name)
                    self.unmapped_ingredients[name] += 1
                    self.unmapped_details[name] = {
                        "processed_name": processed_name,
                        "forms": [],
                        "variations_tried": self.matcher.generate_variations(processed_name),
                        "is_active": False
                    }

                processed.append({
                    "order": ing.get("order", 0),
                    "name": name,
                    "standardName": standard_name,
                    "category": ing.get("category", ""),
                    "ingredientGroup": ing.get("ingredientGroup", ""),
                    "isHarmful": harmful_info["category"] != "none",
                    "harmfulCategory": harmful_info["category"],
                    "riskLevel": harmful_info["risk_level"],
                    "allergen": allergen_info["is_allergen"],
                    "allergenType": allergen_info["type"],
                    "allergenSeverity": allergen_info["severity"],
                    "mapped": is_mapped,
                    # TRANSPARENCY SCORING: Add vague flags
                    "transparency": "poor",
                    "vague_disclosure": True,
                    "vague_flags": grouping_data.get('vague_flags', [])
                })

            else:
                # Regular ingredient - process normally
                # Enhanced mapping
                standard_name, mapped, _ = self._enhanced_ingredient_mapping(name)

                # Enhanced checks
                allergen_info = self._enhanced_allergen_check(name)
                harmful_info = self._enhanced_harmful_check(name)
                non_harmful_info = self._enhanced_non_harmful_check(name)

                # Check if proprietary blend
                is_proprietary = self._is_proprietary_blend_name(name)

                # An ingredient is considered "mapped" if it's found in ANY reference database
                # This includes ingredient databases, harmful additives, allergen databases, or proprietary blends
                is_mapped = (mapped or
                            harmful_info["category"] != "none" or
                            allergen_info["is_allergen"] or
                            is_proprietary)

                # Track unmapped ingredients only if not found in any database
                # DATA INTEGRITY FIX: Filter out label phrases and nutrition facts
                # This prevents "None", "Contains < 2% of", etc. from appearing in unmapped list
                if not is_mapped and not self._is_nutrition_fact(name):
                    processed_name = self.matcher.preprocess_text(name)
                    self.unmapped_ingredients[name] += 1
                    self.unmapped_details[name] = {
                        "processed_name": processed_name,
                        "forms": [],
                        "variations_tried": self.matcher.generate_variations(processed_name),
                        "is_active": False  # Inactive ingredients
                    }

                # Use category from our database if available, otherwise use DSLD category
                db_category = non_harmful_info.get("category", "none")
                if db_category != "none":
                    # Use our database category (correct)
                    category = db_category
                    ingredient_group = non_harmful_info.get("additive_type", ing.get("ingredientGroup", ""))
                else:
                    # Fall back to DSLD category (may be incorrect but better than nothing)
                    category = ing.get("category", "")
                    ingredient_group = ing.get("ingredientGroup", "")

                result = {
                    "order": ing.get("order", 0),
                    "name": name,
                    "standardName": standard_name,
                    "category": category,
                    "ingredientGroup": ingredient_group,
                    "isHarmful": harmful_info["category"] != "none",
                    "harmfulCategory": harmful_info["category"],
                    "riskLevel": harmful_info["risk_level"],
                    "allergen": allergen_info["is_allergen"],
                    "allergenType": allergen_info["type"],
                    "allergenSeverity": allergen_info["severity"],
                    "mapped": is_mapped,
                    "transparency": "standard"
                }

                # FORMS DISCLOSURE: Check if ingredient has forms array
                ing_forms = ing.get("forms", [])

                # List of functional grouping terms
                functional_terms = [
                    "natural color", "natural colors",
                    "natural flavor", "natural flavors",
                    "artificial color", "artificial colors",
                    "artificial flavor", "artificial flavors",
                    "preservatives", "sweeteners", "enzymes"
                ]

                is_functional_grouping = any(
                    term in name.lower()
                    for term in functional_terms
                )

                if ing_forms and isinstance(ing_forms, list) and len(ing_forms) > 0:
                    # Forms are disclosed - preserve them exactly as they appear
                    forms_list = []
                    for form_item in ing_forms:
                        if isinstance(form_item, dict):
                            form_name = form_item.get("name", "")
                            if form_name:
                                forms_list.append(form_name)
                        elif isinstance(form_item, str):
                            forms_list.append(form_item)

                    if forms_list:
                        result["forms"] = forms_list
                        result["forms_disclosed"] = True
                        # Good transparency because forms are disclosed
                        result["transparency"] = "good"
                elif is_functional_grouping:
                    # This is a functional grouping but no forms provided
                    result["forms"] = "undisclosed"
                    result["forms_disclosed"] = False
                    # Keep transparency as "standard" or "poor" depending on other checks

                processed.append(result)

        return processed
    
    # Include all other methods from the original normalizer
    # (I'll keep the existing methods for compatibility)
    
    def _safe_int(self, value: Any, field_name: str = "value", default: int = 0) -> int:
        """
        Safely convert value to integer with comprehensive error handling
        """
        # Handle None explicitly
        if value is None:
            logger.debug(f"NULL {field_name} converted to {default}")
            return default

        # Handle empty strings and "none"
        if isinstance(value, str):
            value = value.strip().lower()
            if not value or value == "none":
                logger.debug(f"Empty/none {field_name} converted to {default}")
                return default

        try:
            result = int(float(value))  # Handle "1.0" -> 1
            return result
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to convert {field_name} '{value}' to int: {e}. Using {default}")
            return default

    def _safe_float(self, value: Any, field_name: str = "value", default: float = 0.0) -> float:
        """
        Safely convert value to float with comprehensive error handling
        """
        # Handle None explicitly
        if value is None:
            logger.debug(f"NULL {field_name} converted to {default}")
            return default

        # Handle empty strings and "none"
        if isinstance(value, str):
            value = value.strip().lower()
            if not value or value == "none":
                logger.debug(f"Empty/none {field_name} converted to {default}")
                return default

        try:
            result = float(value)
            return result
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to convert {field_name} '{value}' to float: {e}. Using {default}")
            return default
    
    def _extract_field_value(self, field_data: Any) -> str:
        """Extract string value from field that can be either string or dict with langualCodeDescription"""
        if isinstance(field_data, str):
            return field_data
        elif isinstance(field_data, dict) and "langualCodeDescription" in field_data:
            return field_data["langualCodeDescription"]
        else:
            return str(field_data) if field_data else ""

    def _extract_forms_from_ingredient_name(self, ingredient_name: str) -> List[str]:
        """Extract form information from ingredient name for precise scoring"""
        name = ingredient_name.lower()
        extracted_forms = []
        
        # Enhanced parenthetical extraction for complex DSLD formats
        import re
        paren_matches = re.findall(r'\(([^)]+)\)', name)
        for match in paren_matches:
            clean_match = match.strip().lower()
            
            # Handle complex DSLD parenthetical formats like "Form: as D3 (Alt. Name: Cholecalciferol)"
            if "form:" in clean_match or "as " in clean_match:
                # Extract after "as " or "form: as "
                if "as " in clean_match:
                    form_part = clean_match.split("as ", 1)[1]
                    # Handle nested parentheses like "as D3 (Alt. Name: Cholecalciferol)"
                    if "(" in form_part:
                        form_part = form_part.split("(")[0].strip()
                    extracted_forms.append(form_part.strip())
            else:
                # Direct parenthetical forms - expanded list
                common_paren_forms = [
                    'cholecalciferol', 'ergocalciferol', 'ascorbic acid', 'calcium ascorbate',
                    'retinyl palmitate', 'retinyl acetate', 'beta-carotene', 
                    'd-alpha tocopherol', 'd-alpha tocopheryl acetate', 'dl-alpha tocopheryl acetate',
                    'methylcobalamin', 'cyanocobalamin', 'dibencozide', 'coenzyme b12'
                ]
                if clean_match in common_paren_forms:
                    extracted_forms.append(clean_match)
        
        # Extract form identifiers from the main name
        form_identifiers = []
        
        # Vitamin D forms
        if re.search(r'\b(?:vitamin\s*)?d3\b', name) or re.search(r'\bcholecalciferol\b', name):
            form_identifiers.append('D3')
            if 'cholecalciferol' not in extracted_forms:
                form_identifiers.append('cholecalciferol')
        elif re.search(r'\b(?:vitamin\s*)?d2\b', name) or re.search(r'\bergocalciferol\b', name):
            form_identifiers.append('D2')
            if 'ergocalciferol' not in extracted_forms:
                form_identifiers.append('ergocalciferol')
        
        # Vitamin C forms
        if re.search(r'\bascorbic\s*acid\b', name):
            form_identifiers.append('ascorbic acid')
        elif re.search(r'\bcalcium\s*ascorbate\b', name):
            form_identifiers.append('calcium ascorbate')
        elif re.search(r'\bmagnesium\s*ascorbate\b', name):
            form_identifiers.append('magnesium ascorbate')
        
        # Enhanced vitamin forms
        if re.search(r'\bretinyl\s*palmitate\b', name):
            form_identifiers.append('retinyl palmitate')
        if re.search(r'\bretinyl\s*acetate\b', name):
            form_identifiers.append('retinyl acetate')
        if re.search(r'\bbeta[\s-]*carotene\b', name):
            form_identifiers.append('beta-carotene')
        
        # Vitamin E forms
        if re.search(r'\bd[\s-]*alpha[\s-]*tocopherol\b', name):
            form_identifiers.append('d-alpha tocopherol')
        elif re.search(r'\bd[\s-]*alpha[\s-]*tocopheryl[\s-]*acetate\b', name):
            form_identifiers.append('d-alpha tocopheryl acetate')
        elif re.search(r'\bdl[\s-]*alpha[\s-]*tocopheryl[\s-]*acetate\b', name):
            form_identifiers.append('dl-alpha tocopheryl acetate')
        
        # B12 forms
        if re.search(r'\bmethylcobalamin\b', name):
            form_identifiers.append('methylcobalamin')
        elif re.search(r'\bcyanocobalamin\b', name):
            form_identifiers.append('cyanocobalamin')
        elif re.search(r'\bdibencozide\b', name) or re.search(r'\bcoenzyme\s*b12\b', name):
            form_identifiers.append('dibencozide')
        
        # Common mineral forms (existing)
        mineral_forms = ['bisglycinate', 'picolinate', 'citrate', 'glycinate', 'malate', 'taurate', 'carbonate', 'oxide']
        for mineral_form in mineral_forms:
            if re.search(rf'\b{mineral_form}\b', name):
                form_identifiers.append(mineral_form)
        
        # FIXED ISSUE #1: Sulfate forms detection
        sulfate_forms = ['sulfate', 'sulphate']  # Handle both spellings
        for sulfate_form in sulfate_forms:
            if re.search(rf'\b{sulfate_form}\b', name):
                form_identifiers.append('sulfate')
                break  # Only add sulfate once
        
        # FIXED ISSUE #2: HCl/Hydrochloride forms detection
        if re.search(r'\bhcl\b', name) or re.search(r'\bhydrochloride\b', name):
            form_identifiers.append('hydrochloride')
        
        # FIXED ISSUE #3: Extract forms detection
        if re.search(r'\bextract\b', name):
            form_identifiers.append('extract')
        
        # FIXED ISSUE #4: Standardized forms detection
        if re.search(r'\bstandardized\b', name) or re.search(r'\bstandardised\b', name):
            form_identifiers.append('standardized')
        
        # Chelated forms
        if re.search(r'\bchelate\b', name) or re.search(r'\bchelated\b', name):
            form_identifiers.append('chelated')
        
        # Organic/natural indicators
        if re.search(r'\borganic\b', name):
            form_identifiers.append('organic')
        if re.search(r'\bnatural\b', name) and not re.search(r'\bnatural\s+flavor', name):
            form_identifiers.append('natural')
        
        # Combine all extracted forms
        all_forms = extracted_forms + form_identifiers
        
        # Remove duplicates while preserving order
        seen = set()
        unique_forms = []
        for form in all_forms:
            if form not in seen:
                seen.add(form)
                unique_forms.append(form)
                
        return unique_forms
    
    def _validate_upc(self, upc: str) -> bool:
        """Validate UPC or SKU format based on retail standards"""
        from dsld_validator import DSLDValidator
        return DSLDValidator.validate_upc_sku(upc)
    
    def _generate_image_url(self, thumbnail: str, product_id: str) -> str:
        """Generate valid DSLD image URL"""
        if not product_id:
            return ""
        return DSLD_IMAGE_URL_TEMPLATE.format(product_id)
    
    def _extract_discontinued_date(self, events: List[Dict]) -> Optional[str]:
        """Extract discontinued date from events"""
        for event in events:
            if event.get("type") == "Off Market":
                date = event.get("date", "")
                if date:
                    return date + "T00:00:00Z"
        return None
    
    def _extract_net_contents(self, net_contents: List[Dict]) -> str:
        """Extract net contents display string"""
        if net_contents and len(net_contents) > 0:
            return net_contents[0].get("display", "")
        return "[]"
    
    def _process_contacts(self, contacts: List[Dict]) -> List[Dict]:
        """Process manufacturer contact information"""
        if not contacts:
            return []
        
        processed_contacts = []
        
        # Process all contacts (not just first one)
        for contact in contacts:
            # Handle both nested contactDetails and flat structure
            if "contactDetails" in contact:
                details = contact["contactDetails"]
                name = details.get("name", "")
                city = details.get("city", "")
                state = details.get("state", "")
                country = details.get("country", "")
                phone = details.get("phoneNumber", "")
                web = details.get("webAddress", "")
            else:
                # Flat structure (like our test data)
                name = contact.get("name", "")
                city = contact.get("city", "")
                state = contact.get("state", "")
                country = contact.get("country", "")
                phone = contact.get("phoneNumber", "")
                web = contact.get("webAddress", "")
                
            # Also preserve the type from flat structure if available
            contact_type = contact.get("type", "")
            
            # Look up manufacturer score
            manufacturer_score = None
            if name:
                # Search in top manufacturers database
                # Handle both array and object formats
                manufacturers = self.manufacturers_db
                if isinstance(self.manufacturers_db, dict):
                    manufacturers = self.manufacturers_db.get("manufacturers", [])
                
                for mfr in manufacturers:
                    mfr_name = mfr.get("standard_name", "")
                    if name.lower() in mfr_name.lower():
                        manufacturer_score = mfr.get("score_contribution", None)
                        break
            
            # Build processed contact
            processed_contact = {
                "name": name,
                "type": contact_type,
                "webAddress": web,
                "city": city,
                "state": state,
                "country": country,
                "phoneNumber": phone,
                "isGMP": False,  # Will be set from statements
                "manufacturerScore": manufacturer_score
            }
            
            processed_contacts.append(processed_contact)
        
        return processed_contacts
    
    def _process_quantity(self, quantities) -> Tuple[float, str, Optional[float]]:
        """Extract quantity, unit, and daily value from various quantity formats"""
        # Handle different input formats robustly
        if not quantities:
            return 0.0, "unspecified", None
        
        # Case 1: Direct numeric value (int/float)
        if isinstance(quantities, (int, float)):
            return float(quantities), "unspecified", None
        
        # Case 2: String value
        if isinstance(quantities, str):
            return self._safe_float(quantities), "unspecified", None
        
        # Case 3: Single dict object
        if isinstance(quantities, dict):
            quantity = self._safe_float(quantities.get("quantity", quantities.get("value", 0)))
            unit = quantities.get("unit", "unspecified")
            
            # Get daily value if available
            daily_value = None
            dv_groups = quantities.get("dailyValueTargetGroup", [])
            if dv_groups and isinstance(dv_groups, list):
                daily_value = self._safe_float(dv_groups[0].get("percent", 0))
            
            return quantity, unit, daily_value
        
        # Case 4: List of quantity objects (original expected format)
        if isinstance(quantities, list):
            # Take first quantity (usually for standard serving)
            q = quantities[0] if quantities else {}
            if isinstance(q, dict):
                quantity = self._safe_float(q.get("quantity", q.get("value", 0)))
                unit = q.get("unit", "unspecified")
                
                # Get daily value if available
                daily_value = None
                dv_groups = q.get("dailyValueTargetGroup", [])
                if dv_groups and isinstance(dv_groups, list):
                    daily_value = self._safe_float(dv_groups[0].get("percent", 0))
                
                # Convert units if needed (e.g., IU to mcg for Vitamin D)
                if unit == "IU" and "vitamin d" in unit.lower():
                    quantity = quantity * 0.025  # Convert to mcg
                    unit = "mcg"
                
                return quantity, unit, daily_value
            else:
                # List contains non-dict values, treat as direct numeric
                return self._safe_float(quantities[0]), "unspecified", None
        
        # Fallback for unexpected types
        logger.warning(f"Unexpected quantity format: {type(quantities)} - {quantities}")
        return 0.0, "unspecified", None
    
    def _get_ingredient_quality_info(self, standard_name: str, forms: List[str]) -> Dict[str, Any]:
        """Get quality information for ingredient"""
        info = {"natural": False, "bio_score": 0}
        
        # Look up in ingredient quality map
        for vitamin_name, vitamin_data in self.ingredient_map.items():
            if vitamin_data.get("standard_name", "").lower() == standard_name.lower():
                # Check each form
                for form in forms:
                    form_lower = form.lower()
                    for form_name, form_data in (vitamin_data.get("forms", {}) or {}).items():
                        if form_lower == form_name.lower() or form_lower in [a.lower() for a in form_data.get("aliases", []) or []]:
                            info["natural"] = form_data.get("natural", False)
                            info["bio_score"] = form_data.get("bio_score", 0)
                            return info
        
        return info
    
    def _extract_ingredient_features(self, notes: str) -> Dict[str, Any]:
        """Extract features from ingredient notes"""
        features = {
            "phrases": [],
            "standardized": False,
            "standardization_percent": None,
            "natural_source": None
        }
        
        if not notes:
            return features
        
        # Extract standardization
        for pattern in STANDARDIZATION_PATTERNS:
            match = re.search(pattern, notes, re.IGNORECASE)
            if match:
                features["standardized"] = True
                try:
                    features["standardization_percent"] = self._safe_float(match.group(1)) if len(match.groups()) >= 1 else 0.0
                    features["phrases"].append(match.group(0))
                except IndexError:
                    features["standardization_percent"] = 0.0
                    features["phrases"].append(match.group(0) if match else "")
                break
        
        # Extract natural source
        for pattern in NATURAL_SOURCE_PATTERNS:
            match = re.search(pattern, notes, re.IGNORECASE)
            if match:
                try:
                    features["natural_source"] = match.group(0)
                    features["phrases"].append(match.group(0))
                except IndexError:
                    features["natural_source"] = ""
                break
        
        # Check for proprietary blend
        for indicator in PROPRIETARY_BLEND_INDICATORS:
            if indicator.lower() in notes.lower():
                features["phrases"].append(indicator)
        
        # Check for delivery enhancement
        for pattern in DELIVERY_ENHANCEMENT_PATTERNS:
            if re.search(pattern, notes, re.IGNORECASE):
                features["phrases"].append(pattern)
        
        return features
    
    def _process_statements(self, statements: List[Dict]) -> List[Dict]:
        """Process and extract information from statements"""
        processed = []
        
        for stmt in statements:
            stmt_type = stmt.get("type", "")
            notes = stmt.get("notes", "")
            
            # Extract certifications
            certifications = []
            for cert_name, pattern in CERTIFICATION_PATTERNS.items():
                if re.search(pattern, notes, re.IGNORECASE):
                    certifications.append(cert_name)
            
            # Extract allergen-free claims
            allergen_free = []
            for allergen, pattern in ALLERGEN_FREE_PATTERNS.items():
                if re.search(pattern, notes, re.IGNORECASE):
                    allergen_free.append(allergen)
            
            # Check for GMP
            gmp_certified = bool(re.search(CERTIFICATION_PATTERNS["GMP-General"], notes, re.IGNORECASE))
            
            # Extract allergens mentioned
            allergens = []
            if "allergi" in stmt_type.lower():
                # Extract specific allergens mentioned
                for allergen_data in self.allergens_db.get("common_allergens", []) or []:
                    # SAFETY: Ensure standard_name exists
                    standard_name = allergen_data.get("standard_name", "")
                    if standard_name and standard_name.lower() in notes.lower():
                        allergens.append(standard_name.lower())
            
            processed.append({
                "type": stmt_type,
                "notes": notes,
                "certifications": certifications,
                "allergenFree": allergen_free,
                "allergens": allergens,
                "gmpCertified": gmp_certified,
                "thirdPartyTested": any(cert.startswith("Third-Party") for cert in certifications)
            })
        
        return processed
    
    def _process_claims(self, claims: List[Dict]) -> List[Dict]:
        """Process product claims"""
        processed = []
        
        for claim in claims:
            code = claim.get("langualCode", "")
            description = claim.get("langualCodeDescription", "")
            
            # For now, we don't have full claim text in the data
            full_text = ""
            
            # Check for unsubstantiated terms
            has_unsubstantiated = False
            flagged_terms = []
            
            for pattern in UNSUBSTANTIATED_CLAIM_PATTERNS:
                if re.search(pattern, full_text, re.IGNORECASE):
                    has_unsubstantiated = True
                    flagged_terms.append(pattern)
            
            processed.append({
                "code": code,
                "description": description,
                "fullText": full_text,
                "hasUnsubstantiated": has_unsubstantiated,
                "flaggedTerms": flagged_terms
            })
        
        return processed
    
    def _process_serving_sizes(self, serving_sizes: List[Dict]) -> List[Dict]:
        """Process serving size information"""
        processed = []
        
        for serving in serving_sizes:
            min_qty = self._safe_float(serving.get("minQuantity", DEFAULT_SERVING_SIZE))
            max_qty = self._safe_float(serving.get("maxQuantity", min_qty))
            
            processed.append({
                "minQuantity": min_qty,
                "maxQuantity": max_qty,
                "unit": serving.get("unit", "serving"),
                "minDailyServings": self._safe_int(serving.get("minDailyServings", DEFAULT_DAILY_SERVINGS)),
                "maxDailyServings": self._safe_int(serving.get("maxDailyServings", DEFAULT_DAILY_SERVINGS)),
                "normalizedServing": max_qty  # Use max as normalized
            })
        
        return processed
    
    def _extract_quality_flags(self, active_ingredients: List[Dict], 
                              inactive_ingredients: List[Dict], 
                              statements: List[Dict]) -> Dict[str, Any]:
        """Extract quality flags from processed data"""
        # Check for proprietary blends
        has_proprietary = any(ing.get("proprietaryBlend", False) for ing in active_ingredients)
        
        # Check for harmful additives
        has_harmful = any(ing.get("isHarmful", False) for ing in inactive_ingredients)
        
        # Check for allergens from ingredients
        allergen_types = []
        for ing in active_ingredients + inactive_ingredients:
            if ing.get("allergen"):
                allergen_type = ing.get("allergenType")
                if allergen_type:
                    allergen_types.append(allergen_type)
        
        # Add facility cross-contamination allergens from statements
        for stmt in statements:
            facility_allergens = stmt.get("allergens", []) or []
            allergen_types.extend(facility_allergens)
        
        # Check for standardized ingredients
        has_standardized = any(ing.get("standardized", False) for ing in active_ingredients)
        
        # Check for natural sources
        has_natural = any(ing.get("natural", False) for ing in active_ingredients)
        
        # Get certifications
        all_certifications = []
        for stmt in statements:
            all_certifications.extend(stmt.get("certifications", []) or [])
        
        # Check for unsubstantiated claims
        has_unsubstantiated = False  # Would be set from claims processing
        
        return {
            "hasProprietary": has_proprietary,
            "hasHarmfulAdditives": has_harmful,
            "hasAllergens": len(allergen_types) > 0,
            "allergenTypes": list(set(allergen_types)),
            "hasStandardized": has_standardized,
            "hasNaturalSources": has_natural,
            "hasCertifications": len(all_certifications) > 0,
            "certificationTypes": list(set(all_certifications)),
            "hasUnsubstantiatedClaims": has_unsubstantiated
        }
    
    def _generate_label_text(self, active_ingredients: List[Dict], 
                           inactive_ingredients: List[Dict], 
                           statements: List[Dict]) -> str:
        """Generate searchable label text"""
        text_parts = []
        
        # Add ingredient names
        for ing in active_ingredients:
            text_parts.append(ing.get("name", ""))
            # Extract form names from forms array
            forms_data = ing.get("forms", [])
            if forms_data and isinstance(forms_data, list):
                for form_dict in forms_data:
                    if isinstance(form_dict, dict) and "name" in form_dict:
                        form_name = form_dict.get("name", "")
                        if form_name:
                            text_parts.append(form_name)
            text_parts.append(ing.get("notes", ""))
        
        for ing in inactive_ingredients:
            text_parts.append(ing.get("name", ""))
        
        # Add statement notes
        for stmt in statements:
            text_parts.append(stmt.get("notes", ""))
        
        # Clean and join
        cleaned_parts = [p.strip() for p in text_parts if p]
        return " ".join(cleaned_parts)

    def _extract_original_label_text(self, raw_data: Dict[str, Any]) -> str:
        """
        Extract original raw text from statements for enrichment text parsing.
        Preserves unprocessed text for downstream analysis.
        """
        text_parts = []

        # Extract all statement notes from raw data
        raw_statements = raw_data.get("statements", []) or []
        for stmt in raw_statements:
            if isinstance(stmt, dict):
                notes = stmt.get("notes", "")
                if notes:
                    text_parts.append(notes)

        # Join all text
        return " ".join(text_parts).strip()

    def _has_full_ingredient_disclosure(self, blend_stats: Dict[str, Any]) -> bool:
        """
        Determine if product has full ingredient disclosure (transparency flag).

        Returns:
            True if no proprietary blends OR all blends have full disclosure
            False if any blend has partial or no disclosure
        """
        # If no proprietary blends, full disclosure is achieved
        if not blend_stats.get("hasProprietaryBlends", False):
            return True

        # If there are proprietary blends, check disclosure levels
        total_blends = blend_stats.get("totalBlends", 0)
        full_disclosure_count = blend_stats.get("fullDisclosure", 0)

        # All blends must have full disclosure
        return total_blends > 0 and full_disclosure_count == total_blends

    def get_unmapped_snapshot(self) -> set:
        """Get a snapshot of current unmapped ingredient names for delta tracking.

        Returns:
            Set of unmapped ingredient names currently tracked
        """
        return set(self.unmapped_ingredients.keys())

    def get_unmapped_delta(self, previous_snapshot: set) -> Dict[str, Any]:
        """Get unmapped ingredients added since the previous snapshot.

        Args:
            previous_snapshot: Set of ingredient names from previous snapshot

        Returns:
            Dict with newly unmapped ingredients and their details
        """
        current_snapshot = set(self.unmapped_ingredients.keys())
        new_unmapped = current_snapshot - previous_snapshot

        unmapped_with_details = []
        for name in new_unmapped:
            details = self.unmapped_details.get(name, {})
            unmapped_with_details.append({
                "name": name,
                "occurrences": self.unmapped_ingredients[name],
                "processedName": details.get("processed_name", ""),
                "forms": details.get("forms", []),
                "variationsTried": details.get("variations_tried", []),
                "isActive": details.get("is_active", False),
                "suggestedMapping": {
                    "needsReview": True,
                    "category": "unknown",
                    "confidence": "low"
                }
            })

        return {
            "unmapped": unmapped_with_details,
            "stats": {
                "totalUnmapped": len(new_unmapped),
                "totalOccurrences": sum(self.unmapped_ingredients[name] for name in new_unmapped),
                "enhancedProcessing": True,
                "fuzzyMatchingEnabled": FUZZY_AVAILABLE
            }
        }

    def get_enhanced_unmapped_summary(self) -> Dict[str, Any]:
        """Get detailed summary of unmapped ingredients with context"""
        unmapped_with_details = []

        for name, count in self.unmapped_ingredients.most_common():
            details = self.unmapped_details.get(name, {})
            unmapped_with_details.append({
                "name": name,
                "occurrences": count,
                "processedName": details.get("processed_name", ""),
                "forms": details.get("forms", []),
                "variationsTried": details.get("variations_tried", []),
                "isActive": details.get("is_active", False),  # Include active/inactive status
                "suggestedMapping": {
                    "needsReview": True,
                    "category": "unknown",
                    "confidence": "low"
                }
            })

        return {
            "unmapped": unmapped_with_details,
            "stats": {
                "totalUnmapped": len(self.unmapped_ingredients),
                "totalOccurrences": sum(self.unmapped_ingredients.values()),
                "enhancedProcessing": True,
                "fuzzyMatchingEnabled": FUZZY_AVAILABLE
            }
        }
    
    def process_and_save_unmapped_tracking(self):
        """Process unmapped ingredients and save separate active/inactive tracking files"""
        if not self.unmapped_tracker:
            logger.warning("Unmapped tracker not initialized. Call set_output_directory() first.")
            return
        
        # Separate active and inactive ingredients
        active_ingredients = set()
        unmapped_data = {}
        
        for name, count in self.unmapped_ingredients.items():
            details = self.unmapped_details.get(name, {})
            is_active = details.get("is_active", False)
            
            if is_active:
                active_ingredients.add(name)
            
            unmapped_data[name] = count
        
        # Process with the tracker
        self.unmapped_tracker.process_unmapped_ingredients(unmapped_data, active_ingredients)
        
        # Save the tracking files
        self.unmapped_tracker.save_tracking_files()
        
        return {
            "active_count": len(active_ingredients),
            "inactive_count": len(unmapped_data) - len(active_ingredients),
            "total_count": len(unmapped_data)
        }
    
    def _is_nutrition_fact(self, name: str) -> bool:
        """Check if ingredient name is a label phrase or nutrition fact to exclude"""
        if not name:
            return False

        # Preprocess the name for comparison
        processed_name = self.matcher.preprocess_text(name)

        # Check against preprocessed excluded nutrition facts
        if processed_name in self._preprocessed_excluded_nutrition:
            return True

        # Check against preprocessed label phrases
        if processed_name in self._preprocessed_excluded_labels:
            logger.debug(f"Excluding label phrase: {name}")
            return True

        # Enhanced pattern matching using ENHANCED_EXCLUSION_PATTERNS from constants
        name_lower = name.lower()

        # Use the enhanced patterns from constants for comprehensive exclusion
        for pattern in ENHANCED_EXCLUSION_PATTERNS:
            if re.search(pattern, name_lower):
                logger.debug(f"Excluding via enhanced pattern: {name}")
                return True

        # All pattern-based exclusions are now handled by ENHANCED_EXCLUSION_PATTERNS

        return False
    
    def _is_proprietary_blend_name(self, name: str) -> bool:
        """Check if ingredient name contains proprietary blend indicators"""
        if not name:
            return False

        name_lower = name.lower()

        # Check against known proprietary blend indicators
        for indicator in PROPRIETARY_BLEND_INDICATORS:
            if indicator.lower() in name_lower:
                logger.debug("Found proprietary blend indicator '%s' in '%s'", indicator, name)
                return True

        return False
    
    def _determine_disclosure_level(self, name: str, quantity: float, unit: str, nested_ingredients: List[Dict]) -> Optional[str]:
        """
        Determine the disclosure level of a proprietary blend
        
        Returns:
            'full' - All ingredients have specific quantities
            'partial' - Some ingredients have quantities, some don't
            'none' - Only total blend weight given, no individual quantities
            None - Not a proprietary blend
        """
        # Check if this is actually a blend
        if not (self._is_proprietary_blend_name(name) or unit == "NP" or quantity == 0):
            # Also check if it has nested ingredients (could be a blend even without keyword)
            if not nested_ingredients:
                return None

        # If no nested ingredients, it's a proprietary blend with no disclosure
        # This includes:
        # 1. Ingredients with proprietary keywords in name
        # 2. Ingredients marked proprietary by unit="NP" or quantity=0
        # In both cases, if there are no nested ingredients, disclosure is "none"
        if not nested_ingredients:
            return "none"  # No ingredient breakdown = no disclosure
        
        # Check disclosure level based on nested ingredients
        has_quantities = []
        for nested_ing in nested_ingredients:
            # Handle quantity as list format (DSLD uses list of quantity objects)
            quantity_list = nested_ing.get("quantity", [])
            nested_qty = 0
            nested_unit = ""
            
            if isinstance(quantity_list, list) and quantity_list:
                # Get first quantity entry
                qty_entry = quantity_list[0] if quantity_list else {}
                nested_qty = qty_entry.get("quantity", 0) if isinstance(qty_entry.get("quantity"), (int, float)) else 0
                nested_unit = qty_entry.get("unit", "")
            elif isinstance(quantity_list, (int, float)):
                nested_qty = quantity_list
                nested_unit = nested_ing.get("unit", "")
            
            # Check if nested ingredient has a real quantity
            if nested_qty > 0 and nested_unit not in ["NP", "", None]:
                has_quantities.append(True)
            else:
                has_quantities.append(False)
        
        # Determine disclosure level
        if all(has_quantities) and len(has_quantities) > 0:
            return "full"  # All nested ingredients have quantities
        elif any(has_quantities):
            return "partial"  # Some have quantities, some don't
        else:
            return "none"  # No individual quantities provided

    def _calculate_transparency_percentage(self, nested_ingredients: List[Dict]) -> float:
        """
        Calculate transparency percentage for partial disclosure blends
        Returns 0-100 percentage of ingredients with disclosed quantities
        """
        if not nested_ingredients:
            return 0.0

        disclosed_count = 0
        total_count = len(nested_ingredients)

        for nested_ing in nested_ingredients:
            # Extract quantity using same logic as disclosure determination
            quantity_list = nested_ing.get("quantity", [])
            nested_qty = 0
            nested_unit = ""

            if isinstance(quantity_list, list) and quantity_list:
                qty_entry = quantity_list[0] if quantity_list else {}
                nested_qty = qty_entry.get("quantity", 0) if isinstance(qty_entry.get("quantity"), (int, float)) else 0
                nested_unit = qty_entry.get("unit", "")
            elif isinstance(quantity_list, (int, float)):
                nested_qty = quantity_list
                nested_unit = nested_ing.get("unit", "")

            # Count as disclosed if has real quantity
            if nested_qty > 0 and nested_unit not in ["NP", "", None]:
                disclosed_count += 1

        transparency_percentage = (disclosed_count / total_count) * 100
        logger.debug(f"Transparency: {disclosed_count}/{total_count} = {transparency_percentage:.1f}%")

        return round(transparency_percentage, 1)

    def _validate_clinical_dosing(self, ingredient_name: str, quantity: float, unit: str, standard_name: str = None) -> Dict[str, any]:
        """
        Validate if disclosed quantity meets clinical effectiveness thresholds
        Returns clinical adequacy assessment with evidence-based scoring
        """
        # Ensure quantity is a number
        try:
            quantity = float(quantity) if quantity is not None else 0.0
        except (ValueError, TypeError):
            logger.warning(f"Invalid quantity for {ingredient_name}: {quantity}, defaulting to 0")
            quantity = 0.0

        # Initialize result
        validation_result = {
            "has_clinical_data": False,
            "adequacy_level": "unknown",
            "adequacy_percentage": 0.0,
            "clinical_min": 0,
            "clinical_max": 0,
            "optimal_dose": 0,
            "dose_unit": unit,
            "evidence_level": "none",
            "dosing_note": "No clinical data available",
            "clinical_score_modifier": 0
        }

        if quantity <= 0 or not unit:
            return validation_result

        # Normalize ingredient name for lookup
        lookup_names = [
            self.matcher.preprocess_text(ingredient_name),
            self.matcher.preprocess_text(standard_name) if standard_name else "",
            ingredient_name.lower().replace(" ", "-"),
            ingredient_name.lower().replace("-", "_")
        ]

        # First try RDA optimal database (vitamins/minerals), then therapeutic database (herbs/supplements)
        ingredient_data = self._search_rda_optimal(lookup_names)
        source_db = "rda_optimal"

        if not ingredient_data:
            ingredient_data = self._search_therapeutic_dosing(lookup_names)
            source_db = "rda_therapeutic"

        if not ingredient_data:
            return validation_result

        # Process the data based on source database
        if source_db == "rda_optimal":
            return self._process_rda_optimal_data(ingredient_data, quantity, unit, validation_result)
        else:
            return self._process_therapeutic_data(ingredient_data, quantity, unit, validation_result)

    def _search_rda_optimal(self, lookup_names: list) -> Dict:
        """Search RDA optimal database for vitamins/minerals"""
        for nutrient in self.rda_optimal.get("nutrient_recommendations", []):
            nutrient_name = nutrient.get("standard_name", "").lower()

            # Check if any lookup name matches the nutrient name or common variations
            for lookup_name in lookup_names:
                if (lookup_name in nutrient_name or nutrient_name in lookup_name or
                    self._check_vitamin_aliases(lookup_name, nutrient_name)):
                    return nutrient
        return None

    def _search_therapeutic_dosing(self, lookup_names: list) -> Dict:
        """Search therapeutic dosing database for herbs/supplements"""
        for ingredient in self.rda_therapeutic.get("therapeutic_dosing", []):
            ingredient_name = ingredient.get("standard_name", "").lower()
            aliases = [alias.lower() for alias in ingredient.get("aliases", [])]

            # Check if any lookup name matches the ingredient name or aliases
            for lookup_name in lookup_names:
                if (lookup_name in ingredient_name or ingredient_name in lookup_name or
                    any(lookup_name in alias or alias in lookup_name for alias in aliases)):
                    return ingredient
        return None

    def _check_vitamin_aliases(self, search_term: str, nutrient_name: str) -> bool:
        """Check common vitamin aliases and variations"""
        vitamin_aliases = {
            "vitamin d": ["vitamin d", "vitamin d3", "cholecalciferol"],
            "vitamin c": ["vitamin c", "ascorbic acid", "ascorbate"],
            "vitamin b12": ["vitamin b12", "b12", "cobalamin", "cyanocobalamin"],
            "vitamin b6": ["vitamin b6", "b6", "pyridoxine"],
            "vitamin b1": ["vitamin b1", "b1", "thiamin", "thiamine"],
            "vitamin b2": ["vitamin b2", "b2", "riboflavin"],
            "vitamin b3": ["vitamin b3", "b3", "niacin", "nicotinic acid"],
            "folate": ["folate", "folic acid", "vitamin b9", "b9"]
        }

        for vitamin, aliases in vitamin_aliases.items():
            if vitamin in nutrient_name:
                return any(alias in search_term for alias in aliases)
        return False

    def _process_rda_optimal_data(self, ingredient_data: Dict, quantity: float, unit: str, validation_result: Dict) -> Dict:
        """Process RDA optimal database results"""
        validation_result["has_clinical_data"] = True
        validation_result["evidence_level"] = "very_high"  # RDA data is highly evidence-based

        # Parse optimal range (e.g., "700-1500" or "25-100")
        optimal_range = ingredient_data.get("optimal_range", "")
        if "-" in optimal_range:
            try:
                range_parts = optimal_range.split("-")
                clinical_min = self._safe_float(range_parts[0].strip(), "clinical_min")
                clinical_max = self._safe_float(range_parts[1].strip(), "clinical_max")
                optimal_dose = (clinical_min + clinical_max) / 2  # Use middle of range as optimal

                # Get unit from ingredient data
                clinical_unit = ingredient_data.get("unit", "")

                # Convert units if necessary
                ingredient_name = ingredient_data.get("standard_name", "")
                converted_quantity = self._convert_dosing_units(quantity, unit, clinical_unit, ingredient_name)

                # Ensure converted_quantity is a number, not dict
                if not isinstance(converted_quantity, (int, float)):
                    logger.warning(f"Unit conversion returned non-numeric value for {ingredient_name}: {converted_quantity}")
                    validation_result["dosing_note"] = f"Unit conversion failed: {unit} to {clinical_unit}"
                    return validation_result

                if converted_quantity <= 0:
                    validation_result["dosing_note"] = f"Unit conversion failed: {unit} to {clinical_unit}"
                    return validation_result

                # Ensure all values are numbers before comparisons
                if not isinstance(optimal_dose, (int, float)):
                    logger.warning(f"optimal_dose is not numeric for {ingredient_name}: {optimal_dose}")
                    optimal_dose = 0
                if not isinstance(clinical_min, (int, float)):
                    logger.warning(f"clinical_min is not numeric for {ingredient_name}: {clinical_min}")
                    clinical_min = 0
                if not isinstance(clinical_max, (int, float)):
                    logger.warning(f"clinical_max is not numeric for {ingredient_name}: {clinical_max}")
                    clinical_max = 0

                # Calculate adequacy percentage
                adequacy_percentage = (converted_quantity / optimal_dose) * 100 if optimal_dose > 0 else 0

                # Determine adequacy level and score modifier
                if converted_quantity < clinical_min * 0.5:
                    adequacy_level = "severely_under_dosed"
                    score_modifier = -2
                elif converted_quantity < clinical_min:
                    adequacy_level = "under_dosed"
                    score_modifier = -1
                elif converted_quantity <= clinical_max:
                    adequacy_level = "optimal"
                    score_modifier = 2
                elif converted_quantity <= self._safe_float(ingredient_data.get("highest_ul"), "highest_ul", float('inf')):
                    adequacy_level = "high_dose"
                    score_modifier = 1
                else:
                    adequacy_level = "excessive"
                    score_modifier = -1

                validation_result.update({
                    "adequacy_level": adequacy_level,
                    "adequacy_percentage": round(adequacy_percentage, 1),
                    "clinical_min": clinical_min,
                    "clinical_max": clinical_max,
                    "optimal_dose": optimal_dose,
                    "dose_unit": clinical_unit,
                    "dosing_note": f"RDA-based: {converted_quantity} {clinical_unit} (optimal: {optimal_range} {clinical_unit})",
                    "clinical_score_modifier": score_modifier,
                    "converted_dose": converted_quantity
                })

            except (ValueError, IndexError):
                validation_result["dosing_note"] = f"Could not parse optimal range: {optimal_range}"

        return validation_result

    def _process_therapeutic_data(self, ingredient_data: Dict, quantity: float, unit: str, validation_result: Dict) -> Dict:
        """Process therapeutic dosing database results"""
        validation_result["has_clinical_data"] = True

        # Map evidence tier to level
        evidence_tier = ingredient_data.get("evidence_tier", 3)
        evidence_mapping = {1: "very_high", 2: "high", 3: "moderate"}
        validation_result["evidence_level"] = evidence_mapping.get(evidence_tier, "moderate")

        # Parse typical dosing range (e.g., "250-600" or "3-5")
        dosing_range = ingredient_data.get("typical_dosing_range", "")
        if "-" in dosing_range:
            try:
                range_parts = dosing_range.split("-")
                clinical_min = float(range_parts[0])
                clinical_max = float(range_parts[1])
                optimal_dose = ingredient_data.get("common_serving_size", (clinical_min + clinical_max) / 2)
                optimal_dose = float(optimal_dose) if isinstance(optimal_dose, str) else optimal_dose

                # Get unit from ingredient data
                clinical_unit = ingredient_data.get("unit", "")

                # Convert units if necessary
                ingredient_name = ingredient_data.get("standard_name", "")
                converted_quantity = self._convert_dosing_units(quantity, unit, clinical_unit, ingredient_name)

                # Ensure converted_quantity is a number, not dict
                if not isinstance(converted_quantity, (int, float)):
                    logger.warning(f"Unit conversion returned non-numeric value for {ingredient_name}: {converted_quantity}")
                    validation_result["dosing_note"] = f"Unit conversion failed: {unit} to {clinical_unit}"
                    return validation_result

                if converted_quantity <= 0:
                    validation_result["dosing_note"] = f"Unit conversion failed: {unit} to {clinical_unit}"
                    return validation_result

                # Ensure all values are numbers before comparisons
                if not isinstance(optimal_dose, (int, float)):
                    logger.warning(f"optimal_dose is not numeric for {ingredient_name}: {optimal_dose}")
                    optimal_dose = 0
                if not isinstance(clinical_min, (int, float)):
                    logger.warning(f"clinical_min is not numeric for {ingredient_name}: {clinical_min}")
                    clinical_min = 0
                if not isinstance(clinical_max, (int, float)):
                    logger.warning(f"clinical_max is not numeric for {ingredient_name}: {clinical_max}")
                    clinical_max = 0

                # Calculate adequacy percentage
                adequacy_percentage = (converted_quantity / optimal_dose) * 100 if optimal_dose > 0 else 0

                # Determine adequacy level and score modifier
                if converted_quantity < clinical_min * 0.5:
                    adequacy_level = "severely_under_dosed"
                    score_modifier = -2
                elif converted_quantity < clinical_min:
                    adequacy_level = "under_dosed"
                    score_modifier = -1
                elif converted_quantity <= clinical_max:
                    adequacy_level = "optimal"
                    score_modifier = 2
                elif converted_quantity <= self._safe_float(ingredient_data.get("upper_limit"), "upper_limit", float('inf')):
                    adequacy_level = "high_dose"
                    score_modifier = 1
                else:
                    adequacy_level = "excessive"
                    score_modifier = -1

                validation_result.update({
                    "adequacy_level": adequacy_level,
                    "adequacy_percentage": round(adequacy_percentage, 1),
                    "clinical_min": clinical_min,
                    "clinical_max": clinical_max,
                    "optimal_dose": optimal_dose,
                    "dose_unit": clinical_unit,
                    "dosing_note": f"Therapeutic: {converted_quantity} {clinical_unit} (range: {dosing_range} {clinical_unit})",
                    "clinical_score_modifier": score_modifier,
                    "converted_dose": converted_quantity
                })

                logger.info(f"🧬 Clinical dosing: {ingredient_data.get('standard_name', 'unknown')} {converted_quantity}{clinical_unit} = {adequacy_percentage:.1f}% of optimal ({adequacy_level})")

            except (ValueError, IndexError):
                validation_result["dosing_note"] = f"Could not parse dosing range: {dosing_range}"

        return validation_result

    def _convert_dosing_units(self, quantity: float, from_unit: str, to_unit: str, ingredient_context: str = None) -> float:
        """
        Convert between dosing units using sophisticated UNIT_CONVERSIONS system
        Supports context-aware conversions (e.g., vitamin-specific IU conversions)
        """
        if from_unit == to_unit:
            return quantity

        # Normalize units
        from_unit = from_unit.lower().strip()
        to_unit = to_unit.lower().strip()

        # Handle unit aliases
        unit_aliases = UNIT_ALIASES

        # Map to full unit names for lookup
        from_unit_full = unit_aliases.get(from_unit, from_unit)
        to_unit_full = unit_aliases.get(to_unit, to_unit)

        # Try context-aware conversion first (e.g., vitamin D specific)
        if ingredient_context and from_unit_full in UNIT_CONVERSIONS:
            context_conversions = UNIT_CONVERSIONS[from_unit_full]
            ingredient_lower = ingredient_context.lower()

            # Check for ingredient-specific conversions
            for ingredient_key, conversion_factor in context_conversions.items():
                if ingredient_key in ingredient_lower:
                    # Determine target unit based on vitamin type
                    if "vitamin a" in ingredient_key and to_unit in ["mcg", "microgram"]:
                        result = quantity * conversion_factor
                        logger.info(f"🔄 Context-aware conversion: {ingredient_context} {quantity} {from_unit} → {result} mcg RAE")
                        return result
                    elif "vitamin d" in ingredient_key and to_unit in ["mcg", "microgram"]:
                        result = quantity * conversion_factor
                        logger.info(f"🔄 Context-aware conversion: {ingredient_context} {quantity} {from_unit} → {result} mcg")
                        return result
                    elif "vitamin e" in ingredient_key and to_unit in ["mg", "milligram"]:
                        result = quantity * conversion_factor
                        logger.info(f"🔄 Context-aware conversion: {ingredient_context} {quantity} {from_unit} → {result} mg")
                        return result

        # Try direct unit conversions from UNIT_CONVERSIONS
        if from_unit_full in UNIT_CONVERSIONS:
            target_conversions = UNIT_CONVERSIONS[from_unit_full]
            if to_unit in target_conversions:
                conversion_factor = target_conversions[to_unit]
                return quantity * conversion_factor

        # Try reverse conversion
        if to_unit_full in UNIT_CONVERSIONS:
            source_conversions = UNIT_CONVERSIONS[to_unit_full]
            if from_unit in source_conversions:
                # Reverse the conversion factor
                conversion_factor = 1 / source_conversions[from_unit]
                return quantity * conversion_factor

        # Handle special nutrient equivalents conversions
        if "folate" in (ingredient_context or "").lower():
            # For folate, mcg and mcg DFE are equivalent for natural folate
            if (from_unit in ["mcg", "μg"] and "dfe" in to_unit.lower()) or \
               ("dfe" in from_unit.lower() and to_unit in ["mcg", "μg"]):
                logger.info(f"🔄 Folate DFE conversion: {quantity} {from_unit} → {quantity} {to_unit}")
                return quantity

        # Handle Niacin Equivalents (NE) conversions
        if "niacin" in (ingredient_context or "").lower():
            # For niacin, mg and mg NE are typically equivalent for direct niacin
            if (from_unit in ["mg"] and "ne" in to_unit.lower()) or \
               ("ne" in from_unit.lower() and to_unit in ["mg"]):
                logger.info(f"🔄 Niacin NE conversion: {quantity} {from_unit} → {quantity} {to_unit}")
                return quantity

        # Handle Vitamin A RAE (Retinol Activity Equivalents) conversions
        if "vitamin a" in (ingredient_context or "").lower():
            # IU to mcg RAE: 1 IU = 0.3 mcg RAE for retinol
            if from_unit in ["iu"] and "rae" in to_unit.lower():
                result = quantity * 0.3
                logger.info(f"🔄 Vitamin A RAE conversion: {quantity} {from_unit} → {result} {to_unit}")
                return result
            # mcg to mcg RAE: 1:1 for retinol equivalents
            elif from_unit in ["mcg", "μg"] and "rae" in to_unit.lower():
                logger.info(f"🔄 Vitamin A RAE conversion: {quantity} {from_unit} → {quantity} {to_unit}")
                return quantity
            # mcg RAE to IU: 1 mcg RAE = 3.33 IU
            elif "rae" in from_unit.lower() and to_unit in ["iu"]:
                result = quantity * 3.33
                logger.info(f"🔄 Vitamin A RAE conversion: {quantity} {from_unit} → {result} {to_unit}")
                return result

        # Handle Vitamin E alpha-tocopherol conversions
        if "vitamin e" in (ingredient_context or "").lower():
            # IU to mg alpha-tocopherol: 1 IU = 0.67 mg
            if from_unit in ["iu"] and "alpha-tocopherol" in to_unit.lower():
                result = quantity * 0.67
                logger.info(f"🔄 Vitamin E alpha-tocopherol conversion: {quantity} {from_unit} → {result} {to_unit}")
                return result

        # Handle gram(s) variant (with parentheses)
        from_unit_clean = from_unit.replace("(s)", "").replace("s)", "")
        to_unit_clean = to_unit.replace("(s)", "").replace("s)", "")

        # Standard metric conversions fallback
        standard_conversions = {
            ("gram", "mg"): 1000,
            ("gram", "mcg"): 1000000,
            ("g", "mg"): 1000,
            ("g", "mcg"): 1000000,
            ("milligram", "mcg"): 1000,
            ("mcg", "mg"): 0.001,
            ("mg", "g"): 0.001,
            ("mcg", "g"): 0.000001,
            ("μg", "mcg"): 1,
            ("mcg", "μg"): 1,
            # Folate DFE conversions
            ("mcg", "mcg dfe"): 1,
            ("mcg dfe", "mcg"): 1,
            ("μg", "mcg dfe"): 1,
            ("mcg dfe", "μg"): 1,
            # Niacin NE conversions
            ("mg", "mg ne"): 1,
            ("mg ne", "mg"): 1,
            # Vitamin A RAE conversions
            ("iu", "mcg rae"): 0.3,
            ("mcg rae", "iu"): 3.33,
            ("mcg", "mcg rae"): 1,
            ("mcg rae", "mcg"): 1,
            # Vitamin E alpha-tocopherol conversions
            ("iu", "mg alpha-tocopherol"): 0.67,
            ("mg alpha-tocopherol", "iu"): 1.49,
            # Standard mg to alpha-tocopherol (assumes natural form unless specified)
            ("mg", "mg alpha-tocopherol"): 1.0,
            ("mg alpha-tocopherol", "mg"): 1.0
        }

        # Try conversion with cleaned units first
        conversion_factor = standard_conversions.get((from_unit_clean, to_unit_clean))
        if conversion_factor:
            return quantity * conversion_factor

        conversion_factor = standard_conversions.get((from_unit_full, to_unit_full))
        if conversion_factor:
            return quantity * conversion_factor

        # Check for suspicious unit combinations that might be data entry errors
        if from_unit == "ng" and to_unit in ["mg", "mcg"]:
            logger.warning(f"Suspicious unit conversion: {from_unit} to {to_unit} for {ingredient_context}. "
                         f"'ng' (nanogram) might be a typo for 'mg' - flagging for manual review")
            return 0.0  # Return 0 to trigger manual review

        # No conversion available
        logger.warning(f"Cannot convert {from_unit} to {to_unit} for dosing validation{f' (ingredient: {ingredient_context})' if ingredient_context else ''}")
        return 0.0

    def _benchmark_against_industry_leaders(self, disclosure_stats: Dict, clinical_validation_stats: Dict = None) -> Dict[str, any]:
        """
        Benchmark transparency and clinical dosing against industry leaders (2025 standards)
        """
        benchmark_result = {
            "transparency_benchmark": {},
            "clinical_benchmark": {},
            "overall_grade": "C",
            "industry_percentile": 50,
            "leader_comparison": {},
            "improvement_recommendations": []
        }

        # Industry leader standards (based on 2025 research)
        industry_leaders = {
            "nutrabio": {
                "full_disclosure_rate": 100,  # 100% full disclosure, never uses proprietary blends
                "transparency_standard": 100,
                "clinical_dosing_adherence": 90,  # Uses clinically effective doses
                "grade": "A+",
                "percentile": 95
            },
            "transparent_labs": {
                "full_disclosure_rate": 100,
                "transparency_standard": 100,
                "clinical_dosing_adherence": 85,
                "grade": "A",
                "percentile": 90
            },
            "industry_average": {
                "full_disclosure_rate": 30,  # Most companies use proprietary blends
                "transparency_standard": 45,
                "clinical_dosing_adherence": 40,  # Often underdosed
                "grade": "C",
                "percentile": 50
            }
        }

        # Calculate transparency metrics
        total_blends = disclosure_stats.get("totalBlends", 0)
        full_disclosure = disclosure_stats.get("fullDisclosure", 0)
        no_disclosure = disclosure_stats.get("noDisclosure", 0)
        avg_transparency = disclosure_stats.get("averageTransparencyPercentage", 0)

        if total_blends > 0:
            full_disclosure_rate = (full_disclosure / total_blends) * 100
            no_disclosure_rate = (no_disclosure / total_blends) * 100
        else:
            full_disclosure_rate = 100 if not disclosure_stats.get("hasProprietaryBlends") else 0
            no_disclosure_rate = 0

        # Transparency benchmarking
        transparency_score = full_disclosure_rate
        if total_blends == 0:  # No proprietary blends at all
            transparency_score = 100

        benchmark_result["transparency_benchmark"] = {
            "full_disclosure_rate": full_disclosure_rate,
            "transparency_score": transparency_score,
            "industry_leader_comparison": {
                "nutrabio_gap": 100 - transparency_score,
                "industry_avg_difference": transparency_score - industry_leaders["industry_average"]["full_disclosure_rate"]
            }
        }

        # Clinical dosing benchmarking (if clinical validation stats provided)
        clinical_score = 70  # Default moderate score
        if clinical_validation_stats:
            # This would be populated with actual clinical validation data
            clinical_score = clinical_validation_stats.get("average_adequacy_percentage", 70)
            # Ensure clinical_score is not None
            clinical_score = clinical_score if clinical_score is not None else 70

        # Ensure transparency_score is not None
        transparency_score = transparency_score if transparency_score is not None else 100

        benchmark_result["clinical_benchmark"] = {
            "clinical_adequacy_score": clinical_score,
            "industry_leader_comparison": {
                "nutrabio_gap": industry_leaders["nutrabio"]["clinical_dosing_adherence"] - clinical_score,
                "industry_avg_difference": clinical_score - industry_leaders["industry_average"]["clinical_dosing_adherence"]
            }
        }

        # Overall grading (weighted: 60% transparency, 40% clinical)
        # Ensure both scores are numbers, not None
        transparency_score = transparency_score if transparency_score is not None else 100
        clinical_score = clinical_score if clinical_score is not None else 70
        overall_score = (transparency_score * 0.6) + (clinical_score * 0.4)

        # Grade assignment
        if overall_score >= 95:
            grade = "A+"
            percentile = 95
        elif overall_score >= 90:
            grade = "A"
            percentile = 90
        elif overall_score >= 80:
            grade = "B+"
            percentile = 80
        elif overall_score >= 70:
            grade = "B"
            percentile = 70
        elif overall_score >= 60:
            grade = "C+"
            percentile = 60
        elif overall_score >= 50:
            grade = "C"
            percentile = 50
        else:
            grade = "D"
            percentile = 25

        benchmark_result.update({
            "overall_grade": grade,
            "industry_percentile": percentile,
            "overall_score": round(overall_score, 1)
        })

        # Leader comparison
        for leader_name, leader_data in industry_leaders.items():
            if leader_name != "industry_average":
                benchmark_result["leader_comparison"][leader_name] = {
                    "transparency_gap": leader_data["full_disclosure_rate"] - transparency_score,
                    "clinical_gap": leader_data["clinical_dosing_adherence"] - clinical_score,
                    "overall_gap": leader_data["percentile"] - percentile
                }

        # Generate improvement recommendations
        recommendations = []
        if no_disclosure_rate > 0:
            recommendations.append("Eliminate proprietary blends with no ingredient disclosure")
        if transparency_score < 80:
            recommendations.append("Increase transparency by providing exact quantities for all ingredients")
        if clinical_score < 70:
            recommendations.append("Ensure ingredient doses meet clinically effective thresholds")
        if overall_score < 90:
            recommendations.append("Follow industry leaders like NutraBio for full transparency standards")

        benchmark_result["improvement_recommendations"] = recommendations

        logger.info(f"🏆 Industry Benchmark: Grade {grade} ({percentile}th percentile) - Transparency: {transparency_score:.1f}%, Clinical: {clinical_score:.1f}%")

        return benchmark_result

    def _calculate_enhanced_penalty_weighting(self, ingredients: List[Dict], blend_stats: Dict) -> Dict[str, any]:
        """
        Calculate risk-based penalty weighting for proprietary blends based on ingredient category
        Higher penalties for higher-risk categories (stimulants, hormones, etc.)
        """
        penalty_result = {
            "total_penalty_score": 0,
            "category_penalties": {},
            "risk_assessment": "low",
            "penalty_breakdown": []
        }

        # Risk-based penalty multipliers by ingredient category
        category_risk_multipliers = {
            "stimulant": 3.0,           # Highest risk - cardiovascular effects
            "hormone": 2.8,             # Very high risk - endocrine disruption
            "thermogenic": 2.5,         # High risk - metabolic effects
            "nootropic": 2.2,           # High risk - neurological effects
            "pre_workout": 2.0,         # Moderate-high risk - combination effects
            "fat_burner": 2.0,          # Moderate-high risk - metabolic stress
            "testosterone_booster": 2.8, # Very high risk - hormonal effects
            "sleep_aid": 1.8,           # Moderate risk - sedative effects
            "adaptogens": 1.5,          # Lower risk - generally safer
            "digestive": 1.3,           # Low risk - digestive enzymes, probiotics
            "immune": 1.2,              # Low risk - immune support
            "antioxidant": 1.1,         # Lowest risk - antioxidants
            "vitamin": 1.0,             # Baseline - essential nutrients
            "mineral": 1.0              # Baseline - essential nutrients
        }

        # Base penalties by disclosure level
        base_penalties = {
            "none": -10,      # Complete lack of disclosure
            "partial": -5,    # Some disclosure
            "full": 0         # Full disclosure, no penalty
        }

        total_penalty = 0
        category_penalties = {}

        for ingredient in ingredients:
            if not ingredient.get("isProprietaryBlend"):
                continue

            disclosure_level = ingredient.get("disclosureLevel", "none")
            transparency_percentage = ingredient.get("transparencyPercentage", 0)
            ingredient_name = ingredient.get("name", "Unknown")

            # Determine ingredient category risk level
            ingredient_category = self._determine_ingredient_category_risk(ingredient_name, ingredient)
            risk_multiplier = category_risk_multipliers.get(ingredient_category, 1.5)  # Default moderate risk

            # Calculate base penalty
            base_penalty = base_penalties.get(disclosure_level, -10)

            # Ensure values are not None
            risk_multiplier = risk_multiplier if risk_multiplier is not None else 1.5
            base_penalty = base_penalty if base_penalty is not None else -10

            # Apply risk multiplier
            weighted_penalty = base_penalty * risk_multiplier

            # Adjust for partial transparency
            if disclosure_level == "partial" and transparency_percentage > 0:
                # Reduce penalty based on transparency percentage
                transparency_bonus = (transparency_percentage / 100) * 2  # Up to 2 point bonus
                weighted_penalty += transparency_bonus

            # Clinical dosing adjustment
            clinical_data = ingredient.get("clinicalDosing", {})
            if clinical_data.get("has_clinical_data"):
                clinical_modifier = clinical_data.get("clinical_score_modifier", 0)
                clinical_modifier = clinical_modifier if clinical_modifier is not None else 0
                weighted_penalty += clinical_modifier

            # Track category penalties
            if ingredient_category not in category_penalties:
                category_penalties[ingredient_category] = {
                    "total_penalty": 0,
                    "ingredient_count": 0,
                    "risk_multiplier": risk_multiplier
                }

            category_penalties[ingredient_category]["total_penalty"] += weighted_penalty
            category_penalties[ingredient_category]["ingredient_count"] += 1

            penalty_result["penalty_breakdown"].append({
                "ingredient": ingredient_name,
                "category": ingredient_category,
                "disclosure_level": disclosure_level,
                "transparency_percentage": transparency_percentage,
                "base_penalty": base_penalty,
                "risk_multiplier": risk_multiplier,
                "final_penalty": round(weighted_penalty, 2)
            })

            total_penalty += weighted_penalty

        # Determine overall risk assessment
        if total_penalty <= -20:
            risk_assessment = "very_high"
        elif total_penalty <= -10:
            risk_assessment = "high"
        elif total_penalty <= -5:
            risk_assessment = "moderate"
        elif total_penalty <= -2:
            risk_assessment = "low"
        else:
            risk_assessment = "minimal"

        penalty_result.update({
            "total_penalty_score": round(total_penalty, 2),
            "category_penalties": category_penalties,
            "risk_assessment": risk_assessment
        })

        logger.info(f"⚖️ Enhanced Penalty Weighting: {total_penalty:.2f} points ({risk_assessment} risk)")

        return penalty_result

    def _determine_ingredient_category_risk(self, ingredient_name: str, ingredient_data: Dict) -> str:
        """
        Determine the risk category of an ingredient based on name and properties
        """
        name_lower = ingredient_name.lower()

        # High-risk stimulant indicators
        stimulant_indicators = [
            "caffeine", "guarana", "yerba mate", "green tea extract", "kola nut",
            "synephrine", "ephedra", "bitter orange", "dmaa", "dmha",
            "phenylethylamine", "hordenine", "tyramine"
        ]

        # Hormone/testosterone indicators
        hormone_indicators = [
            "dhea", "pregnenolone", "androstenedione", "tribulus",
            "tongkat ali", "fenugreek", "d-aspartic acid", "zinc aspartate",
            "boron", "ashwagandha"  # Can affect hormones
        ]

        # Thermogenic indicators
        thermogenic_indicators = [
            "capsaicin", "cayenne", "black pepper extract", "piperine",
            "forskolin", "yohimbine", "rauwolscine", "green coffee bean"
        ]

        # Nootropic indicators
        nootropic_indicators = [
            "noopept", "piracetam", "alpha gpc", "cdp choline", "huperzine a",
            "bacopa monnieri", "lion's mane", "rhodiola rosea", "ginkgo biloba"
        ]

        # Check against patterns
        for indicator in stimulant_indicators:
            if indicator in name_lower:
                return "stimulant"

        for indicator in hormone_indicators:
            if indicator in name_lower:
                return "hormone"

        for indicator in thermogenic_indicators:
            if indicator in name_lower:
                return "thermogenic"

        for indicator in nootropic_indicators:
            if indicator in name_lower:
                return "nootropic"

        # Check blend type indicators
        if any(term in name_lower for term in ["pre-workout", "pre workout", "energy blend"]):
            return "pre_workout"

        if any(term in name_lower for term in ["fat burn", "weight loss", "metabolism"]):
            return "fat_burner"

        if any(term in name_lower for term in ["sleep", "night", "pm formula", "melatonin"]):
            return "sleep_aid"

        if any(term in name_lower for term in ["digest", "enzyme", "probiotic"]):
            return "digestive"

        if any(term in name_lower for term in ["immune", "defense", "vitamin c"]):
            return "immune"

        if any(term in name_lower for term in ["antioxidant", "polyphenol", "flavonoid"]):
            return "antioxidant"

        if any(term in name_lower for term in ["vitamin", "b-complex", "multivitamin"]):
            return "vitamin"

        if any(term in name_lower for term in ["mineral", "calcium", "magnesium", "iron", "zinc"]):
            return "mineral"

        # Default to moderate risk adaptogen category
        return "adaptogens"

    def _calculate_blend_disclosure_stats(self, ingredients: List[Dict]) -> Dict[str, Any]:
        """Calculate statistics about proprietary blend disclosure levels with transparency metrics"""
        stats = {
            "totalBlends": 0,
            "fullDisclosure": 0,
            "partialDisclosure": 0,
            "noDisclosure": 0,
            "hasProprietaryBlends": False,
            "averageTransparencyPercentage": 0.0,
            "transparencyBreakdown": []
        }
        
        # Count blends by disclosure level and calculate transparency metrics
        transparency_percentages = []

        for ing in ingredients:
            if ing.get("isProprietaryBlend"):
                stats["hasProprietaryBlends"] = True
                stats["totalBlends"] += 1

                disclosure_level = ing.get("disclosureLevel")
                transparency_percentage = ing.get("transparencyPercentage", 0)
                # Ensure transparency_percentage is a number, not None
                if transparency_percentage is None:
                    transparency_percentage = 0

                # Track transparency metrics
                transparency_percentages.append(transparency_percentage)
                stats["transparencyBreakdown"].append({
                    "ingredientName": ing.get("name", "Unknown"),
                    "disclosureLevel": disclosure_level,
                    "transparencyPercentage": transparency_percentage
                })

                if disclosure_level == "full":
                    stats["fullDisclosure"] += 1
                elif disclosure_level == "partial":
                    stats["partialDisclosure"] += 1
                elif disclosure_level == "none":
                    stats["noDisclosure"] += 1

        # Calculate average transparency percentage
        if transparency_percentages:
            # Filter out None values and ensure all are numbers
            valid_percentages = [p for p in transparency_percentages if p is not None and isinstance(p, (int, float))]
            if valid_percentages:
                stats["averageTransparencyPercentage"] = round(
                    sum(valid_percentages) / len(valid_percentages), 1
                )
            else:
                stats["averageTransparencyPercentage"] = 0.0
        
        # Determine overall disclosure level
        if not stats["hasProprietaryBlends"]:
            stats["disclosure"] = None  # No proprietary blends
        elif stats["noDisclosure"] > 0:
            stats["disclosure"] = "none"  # Any blend with no disclosure = overall none
        elif stats["partialDisclosure"] > 0:
            stats["disclosure"] = "partial"  # Any partial disclosure = overall partial
        else:
            stats["disclosure"] = "full"  # All blends have full disclosure
        
        return stats
    
    def smart_split_ingredients(self, text: str) -> List[str]:
        """
        Enhanced comma splitting that respects nested parentheses and brackets
        Useful for parsing raw text ingredient lists from unstructured data
        """
        if not text or not isinstance(text, str):
            return []
        
        # Manual parsing to handle complex nesting
        parts = []
        current_part = ""
        paren_depth = 0
        bracket_depth = 0
        
        for char in text:
            if char == '(':
                paren_depth += 1
            elif char == ')':
                paren_depth -= 1
            elif char == '[':
                bracket_depth += 1
            elif char == ']':
                bracket_depth -= 1
            elif char == ',' and paren_depth == 0 and bracket_depth == 0:
                # Safe to split here
                if current_part.strip():
                    parts.append(current_part.strip())
                current_part = ""
                continue
            
            current_part += char
        
        # Add the last part
        if current_part.strip():
            parts.append(current_part.strip())
        
        return parts
    
    def extract_dose_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extract ingredient name and dose information from text using enhanced pattern recognition
        Returns dict with 'ingredient', 'value', 'unit' keys
        """
        if not text or not isinstance(text, str):
            return {"ingredient": text, "value": None, "unit": None}
        
        text = text.strip()
        
        # Try multiple dose patterns
        patterns = [
            # Pattern 1: "Ingredient 500mg" or "Ingredient (500mg)"
            r'^(.+?)\s*\(?(\d+(?:\.\d+)?)\s*(mg|mcg|g|μg|IU)\s*\)?$',
            # Pattern 2: "Ingredient 500 mg" (with space)
            r'^(.+?)\s+(\d+(?:\.\d+)?)\s+(mg|mcg|g|μg|IU)$',
            # Pattern 3: Handle parentheses with dose: "Ingredient (500 mg)"
            r'^(.+?)\s*\(\s*(\d+(?:\.\d+)?)\s+(mg|mcg|g|μg|IU)\s*\)$'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    # Ensure we have all required groups
                    if len(match.groups()) >= 3:
                        ingredient_name = match.group(1).strip()
                        # Remove trailing commas, colons, etc.
                        ingredient_name = re.sub(r'[,:;]\s*$', '', ingredient_name)
                        dose_value = float(match.group(2))
                        dose_unit = match.group(3)

                        return {
                            "ingredient": ingredient_name,
                            "value": dose_value,
                            "unit": dose_unit,
                            "original_text": text
                        }
                except (IndexError, ValueError) as e:
                    # Skip this pattern if groups are malformed
                    logger.debug(f"Pattern failed for '{text}': {e}")
                    continue
        
        # If no dose pattern found, return original text as ingredient
        return {"ingredient": text.strip(), "value": None, "unit": None}
    
    def normalize_ingredient_name(self, name: str) -> str:
        """
        Enhanced ingredient name normalization with explicit form qualifier removal
        """
        if not name or not isinstance(name, str):
            return name

        # Filter out regulatory text patterns that aren't ingredients
        regulatory_patterns = [
            r'contains\s*<?\s*\d+%\s*of:?',    # "Contains <2% of:", etc.
            r'contains\s*less\s*than\s*\d+%',   # "Contains less than 2%"
            r'one\s*or\s*more\s*of\s*the\s*following',  # "One or more of the following"
            r'may\s*contain\s*one\s*or\s*more',  # "May contain one or more"
            r'and\/or',                         # "and/or" connectors
            r'other\s*ingredients',             # "Other ingredients"
            r'inactive\s*ingredients',          # "Inactive ingredients"
            r'allergen\s*information',          # "Allergen information"
        ]

        # Check if this is a regulatory pattern rather than an ingredient
        name_lower = name.lower().strip()
        for pattern in regulatory_patterns:
            if re.match(pattern, name_lower, re.IGNORECASE):
                return ""  # Return empty string for non-ingredients

        # First apply existing preprocessing
        normalized = self.matcher.preprocess_text(name)

        # Remove form qualifiers more explicitly
        normalized = re.sub(FORM_QUALIFIERS, '', normalized, flags=re.IGNORECASE)

        # Clean up any extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()

        return normalized
    
    def _extract_nutritional_warnings(self, ingredient_rows: List[Dict]) -> Dict[str, Any]:
        """
        Extract nutritional warning information for UI display
        Only flag if above thresholds: sugar >1g, sodium >150mg, saturated fat >2g
        Trans fat is flagged at ANY amount (>0g)
        """
        warnings = {
            "excessiveDoses": [],  # Initialize but do not populate during cleaning
            "sugarContent": None,
            "sodiumContent": None,
            "fatContent": None,
            "transFat": None  # Added for trans fat warnings
        }

        # Define nutritional component patterns and thresholds
        nutritional_checks = {
            "sugar": {
                "keywords": ["sugar", "sugars", "total sugar", "total sugars", "added sugar"],
                "threshold": 1,  # grams
                "unit_conversions": {"g": 1, "gram": 1, "grams": 1, "mg": 0.001}
            },
            "sodium": {
                "keywords": ["sodium"],
                "threshold": 150,  # milligrams
                "unit_conversions": {"mg": 1, "milligram": 1, "milligrams": 1, "g": 1000}
            },
            "saturated_fat": {
                "keywords": ["saturated fat", "saturated fats", "sat fat"],
                "threshold": 2,  # grams
                "unit_conversions": {"g": 1, "gram": 1, "grams": 1, "mg": 0.001}
            },
            "trans_fat": {
                "keywords": ["trans fat", "trans fats", "trans fatty acid"],
                "threshold": 0,  # ANY amount of trans fat is flagged
                "unit_conversions": {"g": 1, "gram": 1, "grams": 1, "mg": 0.001}
            }
        }
        
        for ing in ingredient_rows:
            # Normalize ingredient format (handle both string and dict)
            if isinstance(ing, str):
                name = ing.lower().strip()
                ing_dict = {"name": ing}  # Convert to dict for consistent processing
            elif isinstance(ing, dict):
                name = ing.get("name", "").lower().strip()
                ing_dict = ing
            else:
                continue  # Skip invalid entries
            
            # Check sugar content
            for keyword in nutritional_checks["sugar"]["keywords"]:
                if keyword in name:
                    amount_info = self._extract_nutritional_amount(ing_dict)
                    if amount_info:
                        amount_in_g = self._convert_to_standard_unit(
                            amount_info["amount"], 
                            amount_info["unit"], 
                            nutritional_checks["sugar"]["unit_conversions"]
                        )
                        if amount_in_g > nutritional_checks["sugar"]["threshold"]:
                            warnings["sugarContent"] = f"{amount_in_g}g per serving"
                    break
            
            # Check sodium content
            for keyword in nutritional_checks["sodium"]["keywords"]:
                if keyword in name:
                    amount_info = self._extract_nutritional_amount(ing_dict)
                    if amount_info:
                        amount_in_mg = self._convert_to_standard_unit(
                            amount_info["amount"], 
                            amount_info["unit"], 
                            nutritional_checks["sodium"]["unit_conversions"]
                        )
                        if amount_in_mg > nutritional_checks["sodium"]["threshold"]:
                            warnings["sodiumContent"] = f"{amount_in_mg}mg per serving"
                    break
            
            # Check saturated fat content
            for keyword in nutritional_checks["saturated_fat"]["keywords"]:
                if keyword in name:
                    amount_info = self._extract_nutritional_amount(ing_dict)
                    if amount_info:
                        amount_in_g = self._convert_to_standard_unit(
                            amount_info["amount"],
                            amount_info["unit"],
                            nutritional_checks["saturated_fat"]["unit_conversions"]
                        )
                        if amount_in_g > nutritional_checks["saturated_fat"]["threshold"]:
                            warnings["fatContent"] = f"{amount_in_g}g saturated fat per serving"
                    break

            # Check trans fat content (ANY amount is flagged)
            for keyword in nutritional_checks["trans_fat"]["keywords"]:
                if keyword in name:
                    amount_info = self._extract_nutritional_amount(ing_dict)
                    if amount_info:
                        amount_in_g = self._convert_to_standard_unit(
                            amount_info["amount"],
                            amount_info["unit"],
                            nutritional_checks["trans_fat"]["unit_conversions"]
                        )
                        if amount_in_g > nutritional_checks["trans_fat"]["threshold"]:
                            warnings["transFat"] = f"{amount_in_g}g trans fat per serving"
                    break

        return warnings
    
    def _extract_nutritional_amount(self, ingredient: Dict) -> Optional[Dict]:
        """Extract amount information from ingredient for nutritional warnings"""
        # First check the quantity field
        quantity = ingredient.get("quantity", [])
        if quantity and isinstance(quantity, list) and len(quantity) > 0:
            q = quantity[0]
            if isinstance(q, dict):
                amount = q.get("amount")
                unit = q.get("unit", "").lower()
                if amount is not None and amount > 0:
                    return {"amount": amount, "unit": unit}
        
        # Then check forms
        forms = ingredient.get("forms", [])
        for form in forms:
            amount = form.get("amount")
            unit = form.get("unit", "").lower()
            if amount is not None and amount > 0:
                return {"amount": amount, "unit": unit}
        
        return None
    
    def _convert_to_standard_unit(self, amount: float, unit: str, conversions: Dict[str, float]) -> float:
        """Convert amount to standard unit using conversion factors"""
        unit_lower = unit.lower().strip()
        
        # Look for unit in conversions
        for conv_unit, factor in conversions.items():
            if conv_unit in unit_lower:
                return amount * factor
        
        # If no conversion found, assume it's already in the standard unit
        return amount
    
