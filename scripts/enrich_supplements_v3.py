#!/usr/bin/env python3
"""
DSLD Supplement Enrichment System v3.0.0
=========================================
Lean, focused enrichment pipeline that collects data for scoring.
NO scoring calculations - only data collection and organization.

Architecture: Modular "pipe and filter" pattern with separation of concerns.
- Each collector method gathers data from specific databases
- No score calculations (scoring script handles all math)
- Clear output structure designed for scoring consumption

Usage:
    python enrich_supplements_v3.py
    python enrich_supplements_v3.py --config config/enrichment_config.json
    python enrich_supplements_v3.py --dry-run

Author: PharmaGuide Team
Version: 3.0.0
"""

import copy
import json
import os
import sys
import re
import logging
import argparse
import traceback
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

# Optional tqdm import for progress bars
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    tqdm = None

# Optional RapidFuzz for faster/better fuzzy matching
try:
    from rapidfuzz import fuzz as rf_fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False
    rf_fuzz = None

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from constants import (
    DATA_DIR,
    CERTIFICATION_PATTERNS,
    ALLERGEN_FREE_PATTERNS,
    STANDARDIZATION_PATTERNS,
    VALIDATION_THRESHOLDS,
    LOG_FORMAT,
    LOG_DATE_FORMAT
)


class SupplementEnricherV3:
    """
    Lean enrichment system focused on data collection for scoring.

    Design Principles:
    1. NO scoring calculations - only data collection
    2. Modular collectors for each scoring section
    3. Clear separation between enrichment and scoring
    4. Preserve all cleaned data, add enrichment layer
    """

    VERSION = "3.1.0"
    COMPATIBLE_SCORING_VERSIONS = ["3.0.0", "3.0.1", "3.1.0", "3.2.0", "3.3.0"]

    # Required fields for product validation
    # Accept both enrichment-canonical names AND cleaned-output names
    REQUIRED_FIELD_VARIANTS = {
        'dsld_id': ['dsld_id', 'id'],           # enrichment name: [accepted variants]
        'product_name': ['product_name', 'fullName'],
    }
    OPTIONAL_PRODUCT_FIELDS = ['brand_name', 'activeIngredients', 'otherIngredients', 'product_form']

    # Empty schema for validation failures - ensures consistent output structure
    EMPTY_ENRICHMENT_SCHEMA = {
        'ingredient_quality_data': {
            'ingredients': [], 'premium_form_count': 0, 'unmapped_count': 0,
            'total_active': 0
        },
        'delivery_data': {},
        'absorption_data': {},
        'formulation_data': {},
        'contaminant_data': {
            'banned_found': [], 'harmful_found': [], 'allergen_risks': [],
            'allergens': {'found': False, 'allergens': []}
        },
        'compliance_data': {},
        'certification_data': {'certifications_found': []},
        'evidence_data': {},
        'manufacturer_data': {},
        'probiotic_data': {'is_probiotic_product': False},
        'dietary_sensitivity_data': {},
        'rda_ul_data': {},
        'proprietary_data': {},
        'enrichment_metadata': {'ready_for_scoring': False}
    }

    @staticmethod
    def validate_product(product: Dict) -> Tuple[bool, List[str]]:
        """
        Validate product structure before enrichment.
        Accepts both enrichment-canonical field names (dsld_id, product_name)
        AND cleaned-output field names (id, fullName).
        Returns: (is_valid, list of issues)
        """
        issues = []

        if not isinstance(product, dict):
            return False, ["Product must be a dictionary"]

        # Check required fields - accept any variant name
        for canonical, variants in SupplementEnricherV3.REQUIRED_FIELD_VARIANTS.items():
            found = False
            value = None
            for variant in variants:
                if variant in product:
                    found = True
                    value = product[variant]
                    break
            if not found:
                issues.append(f"Missing required field: {canonical} (or {variants})")
            elif value is None or value == '':
                issues.append(f"Empty required field: {canonical}")

        # Validate activeIngredients structure if present
        active_ings = product.get('activeIngredients')
        if active_ings is not None:
            if not isinstance(active_ings, list):
                issues.append("activeIngredients must be a list")
            else:
                for i, ing in enumerate(active_ings):
                    if not isinstance(ing, dict):
                        issues.append(f"activeIngredients[{i}] must be a dictionary")

        return len(issues) == 0, issues

    @staticmethod
    def _atomic_write_json(file_path: str, data: Any, indent: int = 2) -> None:
        """
        Write JSON data atomically using tmp file + os.replace().
        Prevents partial writes on crash/interrupt.
        """
        tmp_path = file_path + '.tmp'
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            os.replace(tmp_path, file_path)
        except Exception:
            # Clean up tmp file on failure
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def _write_quarantine(self, output_dir: str, file_path: str, error_type: str,
                          message: str, stage: str = "enrichment",
                          traceback_str: str = None) -> None:
        """
        Write structured error record to quarantine directory.
        Used when a batch file fails to parse or process.
        """
        quarantine_dir = os.path.join(output_dir, "quarantine")
        os.makedirs(quarantine_dir, exist_ok=True)

        base_name = os.path.splitext(os.path.basename(file_path))[0]
        quarantine_file = os.path.join(quarantine_dir, f"{base_name}_error.json")

        error_record = {
            "original_file": file_path,
            "error_type": error_type,
            "error_message": message,
            "stage": stage,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "enrichment_version": self.VERSION,
        }
        if traceback_str:
            error_record["traceback"] = traceback_str

        try:
            self._atomic_write_json(quarantine_file, error_record)
            self.logger.warning(f"Quarantine record written: {quarantine_file}")
        except Exception as e:
            self.logger.error(f"Failed to write quarantine: {e}")

    def __init__(self, config_path: str = "config/enrichment_config.json"):
        """Initialize enrichment system with configuration"""
        self.logger = self._setup_logging()
        self.config = self._load_config(config_path)
        self.databases = {}
        self._load_all_databases()
        self._compile_patterns()

        # Track unmapped ingredients across batch
        self.unmapped_tracker = {}

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format=LOG_FORMAT,
            datefmt=LOG_DATE_FORMAT,
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        return logging.getLogger(__name__)

    def _load_config(self, config_path: str) -> Dict:
        """Load enrichment configuration"""
        try:
            # Handle relative paths
            if not os.path.isabs(config_path):
                script_dir = Path(__file__).parent
                config_path = script_dir / config_path

            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            self.logger.info(f"Configuration loaded from {config_path}")
            return config
        except FileNotFoundError:
            self.logger.warning(f"Config not found at {config_path}, using defaults")
            return self._default_config()
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in config file {config_path}: {e}")
            return self._default_config()
        except PermissionError as e:
            self.logger.error(f"Permission denied reading config {config_path}: {e}")
            return self._default_config()
        except (IOError, OSError) as e:
            self.logger.error(f"Failed to read config file {config_path}: {e}")
            return self._default_config()

    def _default_config(self) -> Dict:
        """Return default configuration"""
        return {
            "paths": {
                "input_directory": "output_Lozenges/cleaned",
                "output_directory": "output_Lozenges_enriched",
                "reference_data": "data"
            },
            "processing_config": {
                "batch_size": 100,
                "max_workers": 4
            },
            "ui": {
                "show_progress_bar": True
            }
        }

    def _load_all_databases(self):
        """Load all reference databases with fail-fast on critical databases"""
        db_paths = self.config.get('database_paths', {})

        # Validate database_paths key exists
        if not db_paths:
            self.logger.warning("No 'database_paths' key in config - using defaults")
            db_paths = {
                "ingredient_quality_map": "data/ingredient_quality_map.json",
                "absorption_enhancers": "data/absorption_enhancers.json",
                "enhanced_delivery": "data/enhanced_delivery.json",
                "standardized_botanicals": "data/standardized_botanicals.json",
                "synergy_cluster": "data/synergy_cluster.json",
                "banned_recalled_ingredients": "data/banned_recalled_ingredients.json",
                "harmful_additives": "data/harmful_additives.json",
                "allergens": "data/allergens.json",
                "backed_clinical_studies": "data/backed_clinical_studies.json",
                "top_manufacturers_data": "data/top_manufacturers_data.json",
                "manufacturer_violations": "data/manufacturer_violations.json",
                "rda_optimal_uls": "data/rda_optimal_uls.json",
                "clinically_relevant_strains": "data/clinically_relevant_strains.json",
                "color_indicators": "data/color_indicators.json"
            }

        # Add clinically_relevant_strains if not present
        if "clinically_relevant_strains" not in db_paths:
            db_paths["clinically_relevant_strains"] = "data/clinically_relevant_strains.json"

        # Define critical databases that must exist
        critical_dbs = {
            "ingredient_quality_map", "harmful_additives",
            "allergens", "banned_recalled_ingredients", "color_indicators"
        }

        script_dir = Path(__file__).parent
        missing_critical = []

        for db_name, db_path in db_paths.items():
            try:
                # Handle relative paths
                if not os.path.isabs(db_path):
                    full_path = script_dir / db_path
                else:
                    full_path = Path(db_path)

                if full_path.exists():
                    with open(full_path, 'r', encoding='utf-8') as f:
                        self.databases[db_name] = json.load(f)
                    self.logger.info(f"Loaded {db_name}: {len(self.databases[db_name])} entries")
                else:
                    self.databases[db_name] = {}
                    if db_name in critical_dbs:
                        missing_critical.append(f"{db_name}: {full_path}")
                    else:
                        self.logger.warning(f"Database not found: {db_path}")
            except json.JSONDecodeError as e:
                self.databases[db_name] = {}
                if db_name in critical_dbs:
                    missing_critical.append(f"{db_name}: Invalid JSON - {e}")
                else:
                    self.logger.warning(f"Invalid JSON in {db_name} at {db_path}: {e}")
            except PermissionError as e:
                self.databases[db_name] = {}
                if db_name in critical_dbs:
                    missing_critical.append(f"{db_name}: Permission denied - {e}")
                else:
                    self.logger.warning(f"Permission denied reading {db_name}: {e}")
            except (IOError, OSError) as e:
                self.databases[db_name] = {}
                if db_name in critical_dbs:
                    missing_critical.append(f"{db_name}: {e}")
                else:
                    self.logger.warning(f"Failed to load {db_name}: {e}")

        # FAIL-FAST: Critical database files missing
        if missing_critical:
            raise FileNotFoundError(
                f"CRITICAL: Required database files not found or unreadable:\n"
                + "\n".join(f"  - {m}" for m in missing_critical) +
                f"\n\nEnsure database_paths in config point to valid files."
            )

        # POST-LOAD VALIDATION: Check critical vs recommended databases
        self._validate_loaded_databases()

        self.logger.info(f"Enrichment system initialized with {len(self.databases)} databases")

    def _validate_loaded_databases(self):
        """Validate that required databases are loaded. Critical = fail-fast."""
        critical_dbs = [
            "ingredient_quality_map", "harmful_additives",
            "allergens", "banned_recalled_ingredients",
            "color_indicators",  # P0.5: Required for natural/artificial color classification
        ]
        recommended_dbs = [
            "absorption_enhancers", "standardized_botanicals", "synergy_cluster",
            "backed_clinical_studies", "top_manufacturers_data", "manufacturer_violations",
            "rda_optimal_uls", "clinically_relevant_strains", "enhanced_delivery",
        ]

        # Log reference data versions for auditability
        self._log_reference_versions()

        missing_critical = [db for db in critical_dbs
                           if not self.databases.get(db) or len(self.databases.get(db, {})) == 0]
        if missing_critical:
            raise RuntimeError(
                f"CRITICAL: Required databases missing: {', '.join(missing_critical)}. "
                f"Cannot produce safe enrichment. Ensure files exist in data/"
            )

        missing_recommended = [db for db in recommended_dbs
                               if not self.databases.get(db) or len(self.databases.get(db, {})) == 0]
        if missing_recommended:
            self.logger.warning("RECOMMENDED databases missing: %s", ", ".join(missing_recommended))

    def _log_reference_versions(self):
        """Log versions of reference databases for auditability."""
        self.reference_versions = {}

        # Track color_indicators version
        color_db = self.databases.get('color_indicators', {})
        db_info = color_db.get('database_info', {})
        if db_info:
            version = db_info.get('version', 'unknown')
            last_updated = db_info.get('last_updated', 'unknown')
            self.reference_versions['color_indicators'] = {
                'version': version,
                'last_updated': last_updated
            }
            self.logger.info(
                f"Reference data: color_indicators v{version} (updated: {last_updated})"
            )

        # Track other versioned databases
        versioned_dbs = ['harmful_additives', 'allergens', 'ingredient_quality_map']
        for db_name in versioned_dbs:
            db = self.databases.get(db_name, {})
            db_info = db.get('database_info', db.get('_metadata', {}))
            if db_info:
                version = db_info.get('version', db_info.get('schema_version', 'unknown'))
                self.reference_versions[db_name] = {'version': version}

    def _compile_patterns(self):
        """Compile regex patterns for performance"""
        self.compiled_patterns = {
            # Organic certification patterns
            'usda_organic': re.compile(r'\bUSDA\s*Organic\b', re.I),
            'certified_organic': re.compile(r'\bcertified\s+organic\b', re.I),
            'organic_100': re.compile(r'\b100%?\s*organic\b', re.I),
            'made_with_organic': re.compile(r'\bmade\s+with\s+organic\s+ingredients\b', re.I),

            # GMP patterns
            'gmp': re.compile(r'\b(c?GMP|GMP)\s*(certified|compliant|registered|facility)?\b', re.I),
            'nsf_gmp': re.compile(r'\bNSF\s*GMP\b', re.I),
            'fda_registered': re.compile(r'\bFDA[-\s]?registered\s+facility\b', re.I),

            # Batch traceability
            'coa': re.compile(r'\b(certificate\s+of\s+analysis|COA)\b', re.I),
            'qr_code': re.compile(r'\bQR\s*code\b', re.I),
            'batch_lookup': re.compile(r'\b(batch|lot)\s+(lookup|search|verify)\b', re.I),

            # Country of origin
            'made_usa': re.compile(r'\b(made|manufactured|produced)\s+in\s+(the\s+)?USA\b', re.I),
            'made_eu': re.compile(r'\b(made|manufactured|produced)\s+in\s+(the\s+)?(EU|European\s+Union|Germany|France|Italy|Netherlands|Sweden|Denmark|Switzerland)\b', re.I),

            # Physician formulated
            'physician': re.compile(r'\b(doctor|physician|md)[-\s]?formulated\b', re.I),

            # Sustainability
            'sustainability': re.compile(r'\b(glass\s+(bottle|jar|container)|recyclable|recycled|compostable|biodegradable|eco[-\s]?friendly|plastic[-\s]?free)\b', re.I),

            # CFU extraction for probiotics
            'cfu_billion': re.compile(r'(\d+(?:\.\d+)?)\s*billion\s*(CFU|cfus|cfu|live|bacteria|cultures)?', re.I),
            'cfu_billion_abbrev': re.compile(r'(\d+(?:\.\d+)?)\s*B\s*(CFU|cfus|cfu)\b', re.I),  # "1.5 B CFU" format
            'cfu_million': re.compile(r'(\d+(?:\.\d+)?)\s*million\s*(CFU|cfus|cfu|live|bacteria|cultures)?', re.I),
            'cfu_expiration': re.compile(r'(until\s+expiration|through\s+shelf\s+life|at\s+expiration|guaranteed\s+through)', re.I),
            'cfu_manufacture': re.compile(r'(at\s+manufacture|when\s+manufactured|at\s+time\s+of\s+manufacture)', re.I),

            # Standardization percentage
            'standardized_pct': re.compile(r'standardized\s+to\s+(\d+(?:\.\d+)?)\s*%', re.I),
            'pct_compound': re.compile(r'(\d+(?:\.\d+)?)\s*%\s*([a-zA-Z\s]+)', re.I),

            # Unsubstantiated claims (egregious only)
            'disease_claims': re.compile(r'\b(treats?|cures?|prevents?|heals?|eliminates?|reverses?)\s+(cancer|diabetes|alzheimer|arthritis|covid|hypertension|heart\s+disease|depression|anxiety)\b', re.I),
            'miracle_claims': re.compile(r'\b(miracle|instant\s+(cure|healing)|100\s*%\s*(cure|effective)|guaranteed\s+results)\b', re.I),
            'fda_approved': re.compile(r'\b(FDA\s+approved|approved\s+by\s+(the\s+)?FDA)\b(?!.*facility)', re.I)
        }

    # =========================================================================
    # CORE MATCHING UTILITIES
    # =========================================================================

    def _normalize_text(self, text: str) -> str:
        """Normalize text for matching"""
        if not text:
            return ""
        # Lowercase, strip, collapse whitespace
        text = text.lower().strip()
        text = re.sub(r'\s+', ' ', text)
        # Remove trademark symbols
        text = re.sub(r'[™®©]', '', text)
        return text

    def _normalize_company_name(self, name: str) -> str:
        """
        Normalize company name for matching.
        Removes common suffixes like LLC, Inc, Corp, etc.
        """
        if not name:
            return ""
        name = self._normalize_text(name)
        # Remove common corporate suffixes
        suffixes = [
            r'\s*,?\s*(llc|l\.l\.c\.|inc\.?|incorporated|corp\.?|corporation|'
            r'co\.?|company|ltd\.?|limited|plc|gmbh|ag|sa|nv|bv|pty|pvt)\.?\s*$'
        ]
        for suffix in suffixes:
            name = re.sub(suffix, '', name, flags=re.I)
        return name.strip()

    def _fuzzy_company_match(self, name1: str, name2: str, threshold: float = 0.85) -> Tuple[bool, float]:
        """
        Fuzzy match company names using best available method.
        Returns (is_match, similarity_score).

        Uses RapidFuzz if available (faster, more accurate), otherwise difflib.
        Handles common cases like:
        - "Healthy Directions" vs "Healthy Directions, LLC"
        - "Dr. David Williams" vs "David Williams"
        """
        if not name1 or not name2:
            return False, 0.0

        # Normalize company names (removes LLC, Inc, etc.)
        norm1 = self._normalize_company_name(name1)
        norm2 = self._normalize_company_name(name2)

        # Exact match after normalization
        if norm1 == norm2:
            return True, 1.0

        # Empty after normalization
        if not norm1 or not norm2:
            return False, 0.0

        if RAPIDFUZZ_AVAILABLE:
            # RapidFuzz: Use WRatio for best results with partial matches
            # WRatio handles "ACME Factory" vs "ACME Factory Inc." well
            score = rf_fuzz.WRatio(norm1, norm2) / 100.0

            # Also check partial_ratio for substring matches
            partial_score = rf_fuzz.partial_ratio(norm1, norm2) / 100.0

            # Use the higher score
            best_score = max(score, partial_score)
        else:
            # Fallback to difflib SequenceMatcher
            # Standard ratio
            score = SequenceMatcher(None, norm1, norm2).ratio()

            # Partial match: check if shorter is contained in longer
            shorter, longer = (norm1, norm2) if len(norm1) <= len(norm2) else (norm2, norm1)
            partial_score = 0.0
            if shorter in longer:
                partial_score = 1.0
            else:
                # Find best substring match
                for i in range(len(longer) - len(shorter) + 1):
                    substring = longer[i:i + len(shorter)]
                    s = SequenceMatcher(None, shorter, substring).ratio()
                    partial_score = max(partial_score, s)

            best_score = max(score, partial_score)

        return best_score >= threshold, best_score

    def _exact_match(self, ingredient_name: str, target_name: str, aliases: List[str]) -> bool:
        """Perform exact matching against name and aliases"""
        if not ingredient_name or not target_name:
            return False

        ing_norm = self._normalize_text(ingredient_name)
        target_norm = self._normalize_text(target_name)

        # Direct match
        if ing_norm == target_norm:
            return True

        # Check aliases
        for alias in aliases:
            if ing_norm == self._normalize_text(alias):
                return True

        return False

    def _strain_match(self, strain_name: str, target_name: str, aliases: List[str]) -> bool:
        """
        Match probiotic strain names with support for:
        - Genus abbreviations (L. reuteri = Lactobacillus reuteri)
        - Genus name changes (Limosilactobacillus reuteri = Lactobacillus reuteri)
        - Strain IDs (ATCC PTA 5289, DSM 17938)
        """
        if not strain_name or not target_name:
            return False

        # First try exact match
        if self._exact_match(strain_name, target_name, aliases):
            return True

        # Normalize for comparison
        strain_norm = self._normalize_text(strain_name)

        # Map of genus name variations (old/new nomenclature)
        genus_mappings = {
            'limosilactobacillus': ['lactobacillus', 'l'],
            'lactobacillus': ['limosilactobacillus', 'l'],
            'lacticaseibacillus': ['lactobacillus', 'l'],
            'lactiplantibacillus': ['lactobacillus', 'l'],
            'bifidobacterium': ['b'],
            'streptococcus': ['s'],
            'bacillus': ['b'],
            'saccharomyces': ['s'],
        }

        # Extract strain ID patterns (e.g., "ATCC PTA 5289", "DSM 17938", "K12", "M18")
        strain_id_pattern = re.compile(r'(atcc\s*(?:pta\s*)?[\d]+|dsm\s*[\d]+|ncfm|gg|k12|m18|bb-?12|bb536|hn019|bi-?07|de111|299v)', re.IGNORECASE)
        strain_ids = strain_id_pattern.findall(strain_norm)

        # Extract species name (second word, e.g., "reuteri", "rhamnosus")
        words = strain_norm.split()
        species = words[1] if len(words) > 1 else None

        # Check all aliases with genus normalization
        all_targets = [target_name] + aliases
        for target in all_targets:
            target_norm = self._normalize_text(target)
            target_words = target_norm.split()
            target_species = target_words[1] if len(target_words) > 1 else None

            # If species match, check genus compatibility
            if species and target_species and species == target_species:
                # Check if strain IDs match (if present in both)
                target_ids = strain_id_pattern.findall(target_norm)
                if strain_ids and target_ids:
                    # Normalize IDs for comparison
                    strain_ids_norm = {re.sub(r'\s+', '', sid.lower()) for sid in strain_ids}
                    target_ids_norm = {re.sub(r'\s+', '', tid.lower()) for tid in target_ids}
                    if strain_ids_norm & target_ids_norm:  # If any ID matches
                        return True
                elif not strain_ids and not target_ids:
                    # No strain IDs in either - match on genus/species
                    strain_genus = words[0] if words else ''
                    target_genus = target_words[0] if target_words else ''

                    # Direct genus match or abbreviated match
                    if strain_genus == target_genus:
                        return True
                    # Check if abbreviated (e.g., "l" matches "lactobacillus")
                    if target_genus in genus_mappings.get(strain_genus, []):
                        return True
                    if strain_genus in genus_mappings.get(target_genus, []):
                        return True

            # Check for substring match with strain ID
            if strain_ids:
                for sid in strain_ids:
                    sid_norm = re.sub(r'\s+', '', sid.lower())
                    if sid_norm in re.sub(r'\s+', '', target_norm):
                        # Also verify species matches
                        if species and species in target_norm:
                            return True

        return False

    def _get_safe_text_field(self, product: Dict, field: str) -> str:
        """Safely extract text from field that may be string or dict."""
        value = product.get(field, '')
        if isinstance(value, dict):
            return value.get('raw', '') or value.get('text', '') or ''
        elif isinstance(value, str):
            return value
        return ''

    def _get_all_product_text(self, product: Dict) -> str:
        """Combine all product text fields for pattern matching"""
        texts = [
            product.get('fullName', '') or '',
            product.get('brandName', '') or '',
            self._get_safe_text_field(product, 'labelText')
        ]

        # Handle targetGroups - can be list of strings or dicts
        target_groups = product.get('targetGroups', [])
        if target_groups:
            for tg in target_groups:
                if isinstance(tg, str):
                    texts.append(tg)
                elif isinstance(tg, dict):
                    texts.append(tg.get('text', '') or tg.get('name', '') or '')

        # Handle statements - can be list of dicts with 'notes' or 'text' key
        statements = product.get('statements', [])
        if statements:
            for s in statements:
                if isinstance(s, str):
                    texts.append(s)
                elif isinstance(s, dict):
                    # Try multiple possible text fields
                    text = s.get('text', '') or s.get('notes', '') or s.get('type', '') or ''
                    texts.append(text)

        # Handle claims - can be list of dicts with various text fields
        claims = product.get('claims', [])
        if claims:
            for c in claims:
                if isinstance(c, str):
                    texts.append(c)
                elif isinstance(c, dict):
                    # Try multiple possible text fields
                    text = c.get('text', '') or c.get('langualCodeDescription', '') or c.get('notes', '') or ''
                    texts.append(text)

        # Add ingredient notes
        for ing in product.get('activeIngredients', []):
            texts.append(ing.get('notes', '') or '')
            texts.append(ing.get('harvestMethod', '') or '')

        return ' '.join(filter(None, texts))

    # =========================================================================
    # SECTION A: INGREDIENT QUALITY DATA COLLECTORS
    # =========================================================================

    def _collect_ingredient_quality_data(self, product: Dict) -> Dict:
        """
        Collect ingredient quality data for scoring Section A1-A2.
        Returns bio_score, dosage_importance, form matches - NO calculations.
        """
        quality_map = self.databases.get('ingredient_quality_map', {})
        active_ingredients = product.get('activeIngredients', [])

        quality_data = []
        premium_form_count = 0
        unmapped_count = 0

        for ingredient in active_ingredients:
            ing_name = ingredient.get('name', '')
            std_name = ingredient.get('standardName', '') or ing_name
            quantity = ingredient.get('quantity', 0)
            unit = ingredient.get('unit', '')

            # Try to match against quality map
            match_result = self._match_quality_map(ing_name, std_name, quality_map)

            # Preserve hierarchyType from cleaning phase (prevents double-scoring of summaries/sources)
            hierarchy_type = ingredient.get('hierarchyType')

            if match_result:
                bio_score = match_result.get('bio_score', 5)
                natural = match_result.get('natural', False)
                dosage_importance = match_result.get('dosage_importance', 1.0)

                # Use pre-calculated 'score' directly from database match
                score = match_result.get('score', bio_score + (3 if natural else 0))

                # Count premium forms (bio_score > 12)
                if bio_score > 12:
                    premium_form_count += 1

                quality_data.append({
                    "name": ing_name,
                    "standard_name": match_result.get('standard_name', std_name),
                    "matched_form": match_result.get('form_name', 'standard'),
                    "bio_score": bio_score,
                    "natural": natural,
                    "score": score,  # Pre-calculated from database
                    "dosage_importance": dosage_importance,
                    "category": match_result.get('category', 'other'),
                    "quantity": quantity,
                    "unit": unit,
                    "mapped": True,
                    "hierarchyType": hierarchy_type  # Preserve for scoring (skip summaries/sources)
                })
            else:
                # Unmapped ingredient
                unmapped_count += 1
                self._track_unmapped(ing_name, 'active')

                quality_data.append({
                    "name": ing_name,
                    "standard_name": std_name,
                    "matched_form": None,
                    "bio_score": None,  # Scoring will use fallback
                    "natural": None,
                    "score": 5,  # Default score for unmapped (conservative fallback)
                    "dosage_importance": 1.0,  # Default
                    "category": ingredient.get('category', 'unknown'),
                    "quantity": quantity,
                    "unit": unit,
                    "mapped": False,
                    "hierarchyType": hierarchy_type  # Preserve for scoring (skip summaries/sources)
                })

        return {
            "ingredients": quality_data,
            "premium_form_count": premium_form_count,
            "unmapped_count": unmapped_count,
            "total_active": len(active_ingredients)
        }

    def _match_quality_map(self, ing_name: str, std_name: str, quality_map: Dict) -> Optional[Dict]:
        """Match ingredient against quality map, return form data if found"""
        ing_norm = self._normalize_text(ing_name)
        std_norm = self._normalize_text(std_name)

        for parent_key, parent_data in quality_map.items():
            if parent_key.startswith("_") or not isinstance(parent_data, dict):
                continue

            # Check forms first (more specific)
            forms = parent_data.get('forms', {})
            for form_name, form_data in forms.items():
                form_aliases = form_data.get('aliases', [])

                if self._exact_match(ing_name, form_name, form_aliases) or \
                   self._exact_match(std_name, form_name, form_aliases):
                    # Use 'score' directly from database if available, otherwise calculate
                    bio_score = form_data.get('bio_score', 5)
                    natural = form_data.get('natural', False)
                    # Prefer the pre-calculated 'score' field from database
                    score = form_data.get('score', bio_score + (3 if natural else 0))
                    return {
                        "standard_name": parent_data.get('standard_name', parent_key),
                        "form_name": form_name,
                        "bio_score": bio_score,
                        "natural": natural,
                        "score": score,  # Pre-calculated combined score from database
                        "dosage_importance": form_data.get('dosage_importance', 1.0),
                        "category": parent_data.get('category', 'other')
                    }

            # Check parent level
            parent_aliases = parent_data.get('aliases', [])
            parent_std_name = parent_data.get('standard_name', '')

            if self._exact_match(ing_name, parent_std_name, parent_aliases) or \
               self._exact_match(std_name, parent_std_name, parent_aliases):
                # Use first form or defaults
                if forms:
                    first_form_name = list(forms.keys())[0]
                    first_form = forms[first_form_name]
                    bio_score = first_form.get('bio_score', 5)
                    natural = first_form.get('natural', False)
                    # Prefer the pre-calculated 'score' field from database
                    score = first_form.get('score', bio_score + (3 if natural else 0))
                    return {
                        "standard_name": parent_std_name,
                        "form_name": first_form_name,
                        "bio_score": bio_score,
                        "natural": natural,
                        "score": score,
                        "dosage_importance": first_form.get('dosage_importance', 1.0),
                        "category": parent_data.get('category', 'other')
                    }
                else:
                    return {
                        "standard_name": parent_std_name,
                        "form_name": "standard",
                        "bio_score": 5,
                        "natural": False,
                        "score": 5,  # Default for forms without specific data
                        "dosage_importance": 1.0,
                        "category": parent_data.get('category', 'other')
                    }

        return None

    def _collect_delivery_data(self, product: Dict) -> Dict:
        """
        Collect enhanced delivery system data for scoring Section A3.
        """
        delivery_db = self.databases.get('enhanced_delivery', {})
        all_text = self._get_all_product_text(product).lower()
        physical_state = product.get('physicalState', {}).get('langualCodeDescription', '').lower()

        matched_systems = []

        for delivery_name, delivery_data in delivery_db.items():
            if delivery_name.startswith("_") or not isinstance(delivery_data, dict):
                continue

            delivery_lower = delivery_name.lower()

            # Check if delivery system mentioned in product
            if delivery_lower in all_text or delivery_lower in physical_state:
                matched_systems.append({
                    "name": delivery_name,
                    "tier": delivery_data.get('tier', 3),
                    "category": delivery_data.get('category', 'delivery'),
                    "description": delivery_data.get('description', '')
                })

        # Check physical state for lozenge (use data from JSON if available)
        if 'lozenge' in physical_state and not any(s['name'].lower() == 'lozenge' for s in matched_systems):
            lozenge_data = delivery_db.get('lozenge', {})
            matched_systems.append({
                "name": "lozenge",
                "tier": lozenge_data.get('tier', 2),
                "category": lozenge_data.get('category', 'delivery'),
                "description": lozenge_data.get('description', 'Lozenge delivery form')
            })

        return {
            "matched": len(matched_systems) > 0,
            "systems": matched_systems,
            "highest_tier": min([s['tier'] for s in matched_systems]) if matched_systems else None
        }

    def _collect_absorption_data(self, product: Dict) -> Dict:
        """
        Collect absorption enhancer data for scoring Section A4.
        Award bonus only if enhancer AND enhanced nutrient BOTH present.
        """
        enhancers_db = self.databases.get('absorption_enhancers', {})
        enhancers_list = enhancers_db.get('absorption_enhancers', [])

        all_ingredients = product.get('activeIngredients', []) + product.get('inactiveIngredients', [])

        # Build ingredient name set for quick lookup
        ingredient_names = set()
        for ing in all_ingredients:
            ingredient_names.add(self._normalize_text(ing.get('name', '')))
            ingredient_names.add(self._normalize_text(ing.get('standardName', '')))

        found_enhancers = []
        enhanced_nutrients_present = []

        for enhancer in enhancers_list:
            enhancer_name = enhancer.get('name', '')
            enhancer_aliases = enhancer.get('aliases', [])

            # Check if enhancer present
            enhancer_found = False
            for ing in all_ingredients:
                if self._exact_match(ing.get('name', ''), enhancer_name, enhancer_aliases) or \
                   self._exact_match(ing.get('standardName', ''), enhancer_name, enhancer_aliases):
                    enhancer_found = True
                    break

            if enhancer_found:
                # Check which enhanced nutrients are present
                enhances = enhancer.get('enhances', [])
                nutrients_found = []

                for nutrient in enhances:
                    nutrient_norm = self._normalize_text(nutrient)
                    if nutrient_norm in ingredient_names:
                        nutrients_found.append(nutrient)

                if nutrients_found:
                    enhanced_nutrients_present.extend(nutrients_found)

                found_enhancers.append({
                    "name": enhancer_name,
                    "id": enhancer.get('id', ''),
                    "enhances": enhances,
                    "nutrients_found_in_product": nutrients_found
                })

        # Qualify for bonus only if both enhancer AND enhanced nutrient present
        qualifies = len(found_enhancers) > 0 and len(enhanced_nutrients_present) > 0

        return {
            "enhancer_present": len(found_enhancers) > 0,
            "enhancers": found_enhancers,
            "enhanced_nutrients_present": list(set(enhanced_nutrients_present)),
            "qualifies_for_bonus": qualifies
        }

    def _collect_formulation_data(self, product: Dict) -> Dict:
        """
        Collect formulation excellence data for scoring Section A5.
        - Organic certification
        - Standardized botanicals
        - Synergy clusters
        """
        all_text = self._get_all_product_text(product)

        return {
            "organic": self._collect_organic_data(product, all_text),
            "standardized_botanicals": self._collect_standardized_botanicals(product),
            "synergy_clusters": self._collect_synergy_data(product)
        }

    def _collect_organic_data(self, product: Dict, all_text: str) -> Dict:
        """Collect organic certification data"""
        # Check for USDA Organic (product-level, not ingredient-level)
        usda_verified = bool(self.compiled_patterns['usda_organic'].search(all_text))
        certified_organic = bool(self.compiled_patterns['certified_organic'].search(all_text))
        organic_100 = bool(self.compiled_patterns['organic_100'].search(all_text))

        # Exclusion: "made with organic ingredients" doesn't count as certified
        made_with_organic = bool(self.compiled_patterns['made_with_organic'].search(all_text))

        claimed = usda_verified or certified_organic or organic_100

        # Determine claim text
        claim_text = ""
        if usda_verified:
            claim_text = "USDA Organic"
        elif certified_organic:
            claim_text = "Certified Organic"
        elif organic_100:
            claim_text = "100% Organic"

        return {
            "claimed": claimed and not made_with_organic,
            "usda_verified": usda_verified,
            "claim_text": claim_text,
            "exclusion_matched": made_with_organic
        }

    def _collect_standardized_botanicals(self, product: Dict) -> List[Dict]:
        """Collect standardized botanical data"""
        botanicals_db = self.databases.get('standardized_botanicals', {})
        botanicals_list = botanicals_db.get('standardized_botanicals', [])

        active_ingredients = product.get('activeIngredients', [])
        all_text = self._get_all_product_text(product)

        found_botanicals = []

        for ingredient in active_ingredients:
            ing_name = ingredient.get('name', '')
            std_name = ingredient.get('standardName', '') or ing_name
            notes = ingredient.get('notes', '') or ''

            for botanical in botanicals_list:
                bot_name = botanical.get('standard_name', '')
                bot_aliases = botanical.get('aliases', [])

                if self._exact_match(ing_name, bot_name, bot_aliases) or \
                   self._exact_match(std_name, bot_name, bot_aliases):

                    # Extract standardization percentage
                    markers = botanical.get('markers', [])
                    min_threshold = botanical.get('min_threshold')
                    percentage = self._extract_percentage(notes + ' ' + all_text, markers)

                    # Determine if meets threshold
                    meets_threshold = False
                    if min_threshold is not None:
                        # Handle threshold stored as 97 vs 0.97
                        threshold = min_threshold if min_threshold <= 1 else min_threshold / 100
                        meets_threshold = percentage >= threshold if percentage > 0 else False
                    else:
                        # No threshold - any standardization mention qualifies
                        meets_threshold = percentage > 0 or any(
                            self._normalize_text(m) in self._normalize_text(notes + all_text)
                            for m in markers
                        )

                    found_botanicals.append({
                        "name": ing_name,
                        "botanical_id": botanical.get('id', ''),
                        "standard_name": bot_name,
                        "markers": markers,
                        "percentage_found": percentage,
                        "min_threshold": min_threshold,
                        "meets_threshold": meets_threshold
                    })
                    break  # One match per ingredient

        return found_botanicals

    def _extract_percentage(self, text: str, markers: List[str]) -> float:
        """Extract standardization percentage from text"""
        if not text:
            return 0.0

        text_lower = text.lower()

        # Try standardized pattern first
        match = self.compiled_patterns['standardized_pct'].search(text_lower)
        if match:
            return float(match.group(1))

        # Try marker-specific patterns
        for marker in markers:
            marker_lower = marker.lower()
            pattern = rf'(\d+(?:\.\d+)?)\s*%\s*{re.escape(marker_lower)}'
            match = re.search(pattern, text_lower)
            if match:
                return float(match.group(1))

        return 0.0

    def _collect_synergy_data(self, product: Dict) -> List[Dict]:
        """Collect synergy cluster data"""
        synergy_db = self.databases.get('synergy_cluster', {})
        clusters = synergy_db.get('synergy_clusters', [])

        active_ingredients = product.get('activeIngredients', [])

        # Build ingredient lookup
        ingredient_info = {}
        for ing in active_ingredients:
            key = self._normalize_text(ing.get('standardName', '') or ing.get('name', ''))
            ingredient_info[key] = {
                "name": ing.get('name', ''),
                "quantity": ing.get('quantity', 0),
                "unit": ing.get('unit', '')
            }

        matched_clusters = []

        for cluster in clusters:
            cluster_ingredients = cluster.get('ingredients', [])
            min_doses = cluster.get('min_effective_doses', {})

            matched_ings = []
            doses_adequate = []

            for cluster_ing in cluster_ingredients:
                cluster_ing_norm = self._normalize_text(cluster_ing)

                # Check if this cluster ingredient is in product
                for ing_key, ing_data in ingredient_info.items():
                    # Prefer exact match to avoid false positives (e.g. "EPA" in "HEPATIC")
                    is_match = False
                    if cluster_ing_norm == ing_key:
                        is_match = True
                    # Allow substring match only for terms >= 6 chars
                    elif len(cluster_ing_norm) >= 6 and len(ing_key) >= 6:
                        if cluster_ing_norm in ing_key or ing_key in cluster_ing_norm:
                            is_match = True

                    if is_match:
                        # Found match
                        quantity = ing_data['quantity']
                        min_dose = min_doses.get(cluster_ing_norm, min_doses.get(cluster_ing, 0))

                        meets_min = quantity >= min_dose if min_dose > 0 else True

                        matched_ings.append({
                            "ingredient": ing_data['name'],
                            "cluster_ingredient": cluster_ing,
                            "quantity": quantity,
                            "unit": ing_data['unit'],
                            "min_effective_dose": min_dose,
                            "meets_minimum": meets_min
                        })
                        doses_adequate.append(meets_min)
                        break

            # Need at least 2 ingredients for synergy
            if len(matched_ings) >= 2:
                matched_clusters.append({
                    "cluster_id": cluster.get('id', ''),
                    "cluster_name": cluster.get('name', ''),
                    "evidence_tier": cluster.get('evidence_tier', 3),
                    "matched_ingredients": matched_ings,
                    "match_count": len(matched_ings),
                    "doses_adequate": doses_adequate,
                    "all_adequate": all(doses_adequate) if doses_adequate else False
                })

        return matched_clusters

    # =========================================================================
    # SECTION B: SAFETY & PURITY DATA COLLECTORS
    # =========================================================================

    def _collect_contaminant_data(self, product: Dict) -> Dict:
        """
        Collect contaminant data for scoring Section B1.
        - Banned substances
        - Harmful additives
        - Allergens
        """
        all_ingredients = product.get('activeIngredients', []) + product.get('inactiveIngredients', [])

        return {
            "banned_substances": self._check_banned_substances(all_ingredients),
            "harmful_additives": self._check_harmful_additives(all_ingredients),
            "allergens": self._check_allergens(all_ingredients, product)
        }

    def _check_banned_substances(self, ingredients: List[Dict]) -> Dict:
        """Check for banned/recalled substances"""
        banned_db = self.databases.get('banned_recalled_ingredients', {})
        found = []

        # Get all sections dynamically
        for section_key, section_data in banned_db.items():
            if section_key.startswith("_") or not isinstance(section_data, list):
                continue

            for ingredient in ingredients:
                ing_name = ingredient.get('name', '')
                std_name = ingredient.get('standardName', '') or ing_name

                for banned_item in section_data:
                    if not isinstance(banned_item, dict):
                        continue

                    banned_name = banned_item.get('standard_name', '')
                    banned_aliases = banned_item.get('aliases', [])

                    if self._exact_match(ing_name, banned_name, banned_aliases) or \
                       self._exact_match(std_name, banned_name, banned_aliases):
                        found.append({
                            "ingredient": ing_name,
                            "banned_name": banned_name,
                            "banned_id": banned_item.get('id', ''),
                            "category": section_key,
                            "severity_level": banned_item.get('severity_level', 'high'),
                            "reason": banned_item.get('reason', '')
                        })

        return {
            "found": len(found) > 0,
            "substances": found
        }

    @property
    def NATURAL_COLOR_INDICATORS(self) -> List[str]:
        """P0.5: Natural color indicators - loaded from data/color_indicators.json (required)"""
        color_db = self.databases.get('color_indicators', {})
        indicators = color_db.get('natural_indicators', [])
        if not indicators:
            # This should never happen if _validate_loaded_databases passed
            raise RuntimeError("color_indicators.json missing or empty - cannot classify colors")
        return indicators

    @property
    def ARTIFICIAL_COLOR_INDICATORS(self) -> List[str]:
        """P0.5: Artificial color indicators - loaded from data/color_indicators.json (required)"""
        color_db = self.databases.get('color_indicators', {})
        return color_db.get('artificial_indicators', [])

    @property
    def EXPLICIT_NATURAL_DYES(self) -> List[str]:
        """P0.5: Explicit natural dyes - exact match bypasses indicator heuristics"""
        color_db = self.databases.get('color_indicators', {})
        return color_db.get('explicit_natural_dyes', [])

    @property
    def EXPLICIT_ARTIFICIAL_DYES(self) -> List[str]:
        """P0.5: Explicit artificial dyes - exact match bypasses indicator heuristics"""
        color_db = self.databases.get('color_indicators', {})
        return color_db.get('explicit_artificial_dyes', [])

    def _check_harmful_additives(self, ingredients: List[Dict]) -> Dict:
        """
        Check for harmful additives.

        P0.5: Natural colors classification with EXPLICIT DYE PRIORITY:
        1. Check explicit_artificial_dyes FIRST (deterministic) - always flag as artificial
        2. Check explicit_natural_dyes NEXT - never flag as artificial
        3. Fall back to indicator matching for ambiguous "Colors" ingredients
        """
        harmful_db = self.databases.get('harmful_additives', {})
        harmful_list = harmful_db.get('harmful_additives', [])
        found = []

        # Pre-lowercase explicit dye lists for matching
        explicit_artificial = [d.lower() for d in self.EXPLICIT_ARTIFICIAL_DYES]
        explicit_natural = [d.lower() for d in self.EXPLICIT_NATURAL_DYES]

        for ingredient in ingredients:
            ing_name = ingredient.get('name', '')
            std_name = ingredient.get('standardName', '') or ing_name
            ing_forms = ingredient.get('forms', [])
            ing_notes = ingredient.get('notes', '')
            ing_name_lower = ing_name.lower()
            std_name_lower = std_name.lower()

            # P0.5 PRIORITY 1: Check explicit artificial dyes FIRST (deterministic)
            # These ALWAYS get flagged, regardless of context
            is_explicit_artificial = any(
                dye in ing_name_lower or dye in std_name_lower
                for dye in explicit_artificial
            )
            matched_explicit_artificial = None
            if is_explicit_artificial:
                matched_explicit_artificial = next(
                    (dye for dye in self.EXPLICIT_ARTIFICIAL_DYES
                     if dye.lower() in ing_name_lower or dye.lower() in std_name_lower),
                    None
                )

            # P0.5 PRIORITY 2: Check explicit natural dyes NEXT
            # These NEVER get flagged as artificial
            is_explicit_natural = any(
                dye in ing_name_lower or dye in std_name_lower
                for dye in explicit_natural
            )
            matched_explicit_natural = None
            if is_explicit_natural:
                matched_explicit_natural = next(
                    (dye for dye in self.EXPLICIT_NATURAL_DYES
                     if dye.lower() in ing_name_lower or dye.lower() in std_name_lower),
                    None
                )

            # P0.5 PRIORITY 3: Indicator-based matching (fallback for ambiguous terms)
            # Only used if no explicit dye match
            forms_text = ''
            if ing_forms:
                for form in ing_forms:
                    if isinstance(form, dict):
                        form_prefix = form.get('prefix', '') or ''
                        form_name = form.get('name', '') or ''
                        forms_text += ' ' + form_prefix + ' ' + form_name
                    elif isinstance(form, str):
                        forms_text += ' ' + form

            combined_text = (forms_text + ' ' + (ing_notes or '')).lower()
            matched_natural_indicator = None
            matched_artificial_indicator = None

            if not is_explicit_artificial and not is_explicit_natural:
                # Only check indicators if no explicit match
                for ind in self.NATURAL_COLOR_INDICATORS:
                    if ind in combined_text:
                        matched_natural_indicator = ind
                        break
                for ind in self.ARTIFICIAL_COLOR_INDICATORS:
                    if ind in combined_text:
                        matched_artificial_indicator = ind
                        break

            # Determine final classification
            # Priority: explicit_artificial > explicit_natural > artificial_indicator > natural_indicator
            is_natural_color = (
                is_explicit_natural or
                (matched_natural_indicator and not is_explicit_artificial and not matched_artificial_indicator)
            )
            is_artificial_color = is_explicit_artificial or (matched_artificial_indicator and not is_explicit_natural)

            for additive in harmful_list:
                additive_name = additive.get('standard_name', '')
                additive_id = additive.get('id', '')
                additive_aliases = additive.get('aliases', [])
                additive_category = additive.get('category', '')

                # P0.5: Skip "Artificial Colors (General)" for natural colorants
                # BUT always include if this is an explicit artificial dye
                if not is_explicit_artificial and is_natural_color and (
                    additive_id == 'ADD_ARTIFICIAL_COLORS' or
                    'artificial color' in additive_name.lower() or
                    additive_category == 'colorant_artificial'
                ):
                    continue

                if self._exact_match(ing_name, additive_name, additive_aliases) or \
                   self._exact_match(std_name, additive_name, additive_aliases):
                    # Build classification evidence
                    classification_evidence = {}
                    if matched_explicit_artificial:
                        classification_evidence['matched_explicit_artificial_dye'] = matched_explicit_artificial
                    if matched_explicit_natural:
                        classification_evidence['matched_explicit_natural_dye'] = matched_explicit_natural
                    if matched_natural_indicator:
                        classification_evidence['matched_natural_indicator'] = matched_natural_indicator
                    if matched_artificial_indicator:
                        classification_evidence['matched_artificial_indicator'] = matched_artificial_indicator

                    found.append({
                        "ingredient": ing_name,
                        "additive_name": additive_name,
                        "additive_id": additive_id,
                        "risk_level": additive.get('risk_level', 'low'),
                        "category": additive_category,
                        "is_natural_color": is_natural_color if 'color' in ing_name_lower else None,
                        "classification_evidence": classification_evidence if classification_evidence else None
                    })

        return {
            "found": len(found) > 0,
            "additives": found
        }

    # P0.1: Allergen presence type precedence (higher = wins in conflicts)
    ALLERGEN_PRESENCE_PRIORITY = {
        "contains": 5,
        "may_contain": 4,
        "facility_warning": 3,
        "ingredient_list": 2,
        "unknown": 1
    }

    def _extract_allergen_presence_from_text(self, product: Dict) -> List[Dict]:
        """
        P0.1: Extract allergens with presence_type from label text sources.

        Parses:
        - labelText.parsed.allergens (e.g., ["soy", "milk"])
        - labelText.parsed.warnings (e.g., "Contains: Milk")
        - statements[] for "Contains milk and soy", "May contain", "Manufactured in a facility"

        Returns: List of {allergen_id, presence_type, evidence_text, matched_text}
        """
        allergen_db = self.databases.get('allergens', {})
        allergen_list = allergen_db.get('common_allergens', allergen_db.get('allergens', []))

        found = []

        # Build allergen lookup by name/alias
        allergen_lookup = {}
        for allergen in allergen_list:
            allergen_name = allergen.get('standard_name', '').lower()
            allergen_lookup[allergen_name] = allergen
            for alias in allergen.get('aliases', []):
                allergen_lookup[alias.lower()] = allergen

        # Source 1: labelText.parsed.allergens
        label_text = product.get('labelText', {})
        if isinstance(label_text, dict):
            parsed = label_text.get('parsed', {})
            parsed_allergens = parsed.get('allergens', [])
            for allergen_text in parsed_allergens:
                if isinstance(allergen_text, str):
                    allergen_lower = allergen_text.lower().strip()
                    if allergen_lower in allergen_lookup:
                        allergen = allergen_lookup[allergen_lower]
                        found.append({
                            "allergen_id": allergen.get('id', ''),
                            "allergen_name": allergen.get('standard_name', ''),
                            "presence_type": "contains",  # Parsed allergens imply contains
                            "source": "label_parsed",
                            "evidence": f"labelText.parsed.allergens: {allergen_text}",
                            "matched_text": allergen_text,
                            "severity_level": allergen.get('severity_level', 'low'),
                            "regulatory_status": allergen.get('regulatory_status', ''),
                            "general_handling": allergen.get('general_handling', 'flag_only')
                        })

            # Source 2: labelText.parsed.warnings
            parsed_warnings = parsed.get('warnings', [])
            for warning in parsed_warnings:
                warning_text = warning if isinstance(warning, str) else str(warning)
                self._parse_allergen_statement(warning_text, allergen_lookup, found, "label_warning")

        # Source 3: statements[]
        statements = product.get('statements', [])
        for statement in statements:
            if isinstance(statement, dict):
                statement_text = statement.get('text', '') or statement.get('notes', '') or ''
            else:
                statement_text = str(statement)

            self._parse_allergen_statement(statement_text, allergen_lookup, found, "label_statement")

        return found

    def _parse_allergen_statement(self, text: str, allergen_lookup: Dict, found: List[Dict], source: str) -> None:
        """
        Parse a text statement for allergen declarations.

        Patterns:
        - "Contains: milk, soy" -> presence_type=contains
        - "May contain peanuts" -> presence_type=may_contain
        - "Manufactured in a facility that processes tree nuts" -> presence_type=facility_warning
        """
        text_lower = text.lower()

        # Pattern 1: "Contains X" / "Contains: X, Y"
        contains_patterns = [
            r'contains[:\s]+([^.]+)',
            r'contains\s+(\w+(?:\s+and\s+\w+)*)',
        ]
        for pattern in contains_patterns:
            match = re.search(pattern, text_lower)
            if match:
                allergen_text = match.group(1)
                self._extract_allergens_from_text(allergen_text, allergen_lookup, found,
                                                   "contains", source, text)

        # Pattern 2: "May contain X"
        may_contain_patterns = [
            r'may\s+contain[:\s]+([^.]+)',
            r'may\s+contain\s+(\w+(?:\s+and\s+\w+)*)',
        ]
        for pattern in may_contain_patterns:
            match = re.search(pattern, text_lower)
            if match:
                allergen_text = match.group(1)
                self._extract_allergens_from_text(allergen_text, allergen_lookup, found,
                                                   "may_contain", source, text)

        # Pattern 3: Facility warnings
        facility_patterns = [
            r'manufactured\s+in\s+a\s+facility\s+(?:that\s+)?(?:also\s+)?(?:processes|handles|produces)[:\s]+([^.]+)',
            r'produced\s+in\s+a\s+facility\s+(?:that\s+)?(?:also\s+)?(?:processes|handles)[:\s]+([^.]+)',
            r'made\s+in\s+a\s+facility\s+that\s+(?:also\s+)?(?:processes|handles)[:\s]+([^.]+)',
        ]
        for pattern in facility_patterns:
            match = re.search(pattern, text_lower)
            if match:
                allergen_text = match.group(1)
                self._extract_allergens_from_text(allergen_text, allergen_lookup, found,
                                                   "facility_warning", source, text)

    def _extract_allergens_from_text(self, text: str, allergen_lookup: Dict, found: List[Dict],
                                      presence_type: str, source: str, evidence: str) -> None:
        """Extract individual allergens from a comma/and-separated text."""
        # Split on comma, "and", "&"
        parts = re.split(r'[,&]|\band\b', text.lower())

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Check if this matches any allergen
            if part in allergen_lookup:
                allergen = allergen_lookup[part]
                found.append({
                    "allergen_id": allergen.get('id', ''),
                    "allergen_name": allergen.get('standard_name', ''),
                    "presence_type": presence_type,
                    "source": source,
                    "evidence": evidence,
                    "matched_text": part,
                    "severity_level": allergen.get('severity_level', 'low'),
                    "regulatory_status": allergen.get('regulatory_status', ''),
                    "general_handling": allergen.get('general_handling', 'flag_only')
                })

    def _check_allergens(self, ingredients: List[Dict], product: Dict) -> Dict:
        """
        P0.1: Check for allergens with presence_type and precedence.

        Sources (in precedence order):
        1. Label statements/warnings (Contains / May contain / Facility)
        2. Ingredient list (direct ingredient-derived)
        3. Heuristics (hidden allergens)

        Conflict Resolution:
        - contains > may_contain > facility_warning > ingredient_list > unknown
        - If same allergen from multiple sources, highest precedence wins
        """
        allergen_db = self.databases.get('allergens', {})
        allergen_list = allergen_db.get('common_allergens', allergen_db.get('allergens', []))

        all_text = self._get_all_product_text(product).lower()

        # Collect allergens from all sources
        all_found = []

        # Source 1: Label text (has precedence)
        label_allergens = self._extract_allergen_presence_from_text(product)
        all_found.extend(label_allergens)

        # Source 2: Ingredient list
        for ingredient in ingredients:
            ing_name = ingredient.get('name', '')
            std_name = ingredient.get('standardName', '') or ing_name

            for allergen in allergen_list:
                allergen_name = allergen.get('standard_name', '')
                allergen_aliases = allergen.get('aliases', [])

                if self._exact_match(ing_name, allergen_name, allergen_aliases) or \
                   self._exact_match(std_name, allergen_name, allergen_aliases):

                    # Check for negation context
                    if self._is_negated(allergen_name, allergen_aliases, all_text):
                        continue

                    all_found.append({
                        "allergen_id": allergen.get('id', ''),
                        "allergen_name": allergen_name,
                        "ingredient": ing_name,
                        "presence_type": "ingredient_list",
                        "source": "ingredient_list",
                        "evidence": f"Ingredient: {ing_name}",
                        "matched_text": ing_name,
                        "severity_level": allergen.get('severity_level', 'low'),
                        "regulatory_status": allergen.get('regulatory_status', ''),
                        "general_handling": allergen.get('general_handling', 'flag_only'),
                        "category": allergen.get('category', '')
                    })

        # Deduplicate by allergen_id, keeping highest precedence
        deduplicated = {}
        for item in all_found:
            allergen_id = item.get('allergen_id', '')
            if not allergen_id:
                continue

            existing = deduplicated.get(allergen_id)
            if existing:
                # Compare precedence
                existing_priority = self.ALLERGEN_PRESENCE_PRIORITY.get(existing.get('presence_type', 'unknown'), 1)
                new_priority = self.ALLERGEN_PRESENCE_PRIORITY.get(item.get('presence_type', 'unknown'), 1)

                if new_priority > existing_priority:
                    deduplicated[allergen_id] = item
            else:
                deduplicated[allergen_id] = item

        found = list(deduplicated.values())

        # Check for may_contain/facility warnings
        has_may_contain = any(a.get('presence_type') in ['may_contain', 'facility_warning'] for a in found)

        return {
            "found": len(found) > 0,
            "allergens": found,
            "has_may_contain_warning": has_may_contain
        }

    def _is_negated(self, name: str, aliases: List[str], text: str) -> bool:
        """Check if allergen mention is in negation context"""
        negation_patterns = [
            r'\bno\s+', r'\bfree\s+(from|of)\s+', r'\bwithout\s+',
            r'\bdoes\s+not\s+contain\s+', r'\bcontains\s+no\s+'
        ]

        terms = [name.lower()] + [a.lower() for a in aliases]

        for term in terms:
            for pattern in negation_patterns:
                if re.search(pattern + r'.*?' + re.escape(term), text):
                    return True

        return False

    def _collect_compliance_data(self, product: Dict,
                                  contaminant_data: Optional[Dict] = None) -> Dict:
        """
        Collect allergen & dietary compliance data for scoring Section B2.

        Args:
            product: The product dict to analyze
            contaminant_data: Pre-collected contaminant data to avoid double-collection
        """
        target_groups = product.get('targetGroups', [])
        all_text = self._get_all_product_text(product).lower()

        # Extract claims from target groups and text
        allergen_free_claims = []
        for pattern_name, pattern in ALLERGEN_FREE_PATTERNS.items():
            if re.search(pattern, all_text, re.I):
                allergen_free_claims.append(pattern_name)

        # Check target groups - normalize list items (can be str or dict)
        normalized_groups = []
        for tg in target_groups:
            if isinstance(tg, str):
                normalized_groups.append(tg)
            elif isinstance(tg, dict):
                normalized_groups.append(tg.get('text', '') or tg.get('name', '') or '')
        target_lower = ' '.join(normalized_groups).lower()

        gluten_free = 'gluten free' in target_lower or 'gluten-free' in target_lower
        dairy_free = 'dairy free' in target_lower or 'dairy-free' in target_lower
        soy_free = 'soy free' in target_lower or 'soy-free' in target_lower
        vegan = 'vegan' in target_lower
        vegetarian = 'vegetarian' in target_lower

        # Check for conflicts with detected allergens
        # Use pre-collected data if provided (avoids double-collection)
        if contaminant_data is None:
            contaminant_data = self._collect_contaminant_data(product)
        detected_allergens = contaminant_data['allergens']['allergens']

        conflicts = []
        if dairy_free and any('milk' in a['allergen_name'].lower() or 'dairy' in a['allergen_name'].lower()
                             for a in detected_allergens):
            conflicts.append("dairy-free claim conflicts with detected dairy")
        if soy_free and any('soy' in a['allergen_name'].lower() for a in detected_allergens):
            conflicts.append("soy-free claim conflicts with detected soy")
        if gluten_free and any('wheat' in a['allergen_name'].lower() or 'gluten' in a['allergen_name'].lower()
                              for a in detected_allergens):
            conflicts.append("gluten-free claim conflicts with detected gluten/wheat")

        # P0.1: Use structured allergen data for may_contain detection
        # Fall back to text search if not available
        may_contain_from_allergens = contaminant_data['allergens'].get('has_may_contain_warning', False)
        may_contain_from_text = 'may contain' in all_text or 'shared equipment' in all_text
        may_contain = may_contain_from_allergens or may_contain_from_text

        return {
            "allergen_free_claims": allergen_free_claims,
            "gluten_free": gluten_free,
            "dairy_free": dairy_free,
            "soy_free": soy_free,
            "vegan": vegan,
            "vegetarian": vegetarian,
            "conflicts": conflicts,
            "has_may_contain_warning": may_contain,
            "verified": len(conflicts) == 0
        }

    def _collect_certification_data(self, product: Dict) -> Dict:
        """
        Collect certification data for scoring Section B3.

        Also derives safety verification flags from certifications:
        - purity_verified: Product tested by program that tests for contaminants
        - heavy_metal_tested: Product tested by program that tests for heavy metals
        - label_accuracy_verified: Product tested by program that verifies label claims
        """
        all_text = self._get_all_product_text(product)

        third_party = self._collect_third_party_certs(all_text)
        gmp = self._collect_gmp_data(all_text)
        traceability = self._collect_traceability_data(all_text)

        # Derive safety flags from certifications
        # These programs test for heavy metals, contaminants, and/or label accuracy
        safety_flags = self._derive_safety_flags(third_party, product)

        return {
            "third_party_programs": third_party,
            "gmp": gmp,
            "batch_traceability": traceability,
            # Safety verification flags for app display
            "purity_verified": safety_flags["purity_verified"],
            "heavy_metal_tested": safety_flags["heavy_metal_tested"],
            "label_accuracy_verified": safety_flags["label_accuracy_verified"],
            "category_contamination_risk": safety_flags["category_contamination_risk"]
        }

    def _collect_third_party_certs(self, text: str) -> List[Dict]:
        """Collect third-party testing certifications"""
        certs = []

        # Priority certification patterns (named programs only)
        cert_checks = [
            ("NSF Sport", r'\bNSF\b.*certified\s*for\s*sport\b|\bNSF[-\s]?sport\b'),
            ("NSF Certified", r'\bNSF\b.*(certified|certification)\b(?!.*sport)|\bNSF/ANSI\s*173\b'),
            ("USP Verified", r'\bUSP\b.*(Verified|Verification\s*Program)\b'),
            ("ConsumerLab", r'\bConsumerLab\b.*(Approved|Seal)\b'),
            ("Informed Sport", r'\bInformed[-\s]?Sport\b'),
            ("Informed Choice", r'\bInformed[-\s]?Choice\b'),
            ("BSCG", r'\bBSCG\b.*(Certified|Drug\s*Free)\b'),
            ("IFOS", r'\bIFOS\b|\bInternational\s*Fish\s*Oil\s*Standards\b')
        ]

        for cert_name, pattern in cert_checks:
            if re.search(pattern, text, re.I):
                certs.append({
                    "name": cert_name,
                    "verified": True
                })

        # Check for generic "third-party tested" (doesn't count for points)
        generic_third_party = bool(re.search(r'\b(third[-\s]?party|3rd[-\s]?party)\s*(tested|verified)\b', text, re.I))

        return {
            "programs": certs,
            "count": len(certs),
            "has_generic_claim_only": generic_third_party and len(certs) == 0
        }

    def _collect_gmp_data(self, text: str) -> Dict:
        """Collect GMP certification data"""
        gmp_found = bool(self.compiled_patterns['gmp'].search(text))
        nsf_gmp = bool(self.compiled_patterns['nsf_gmp'].search(text))
        fda_registered = bool(self.compiled_patterns['fda_registered'].search(text))

        return {
            "claimed": gmp_found or nsf_gmp or fda_registered,
            "nsf_gmp": nsf_gmp,
            "fda_registered": fda_registered,
            "text_matched": "NSF GMP" if nsf_gmp else "FDA Registered" if fda_registered else "GMP" if gmp_found else ""
        }

    def _collect_traceability_data(self, text: str) -> Dict:
        """Collect batch traceability data"""
        has_coa = bool(self.compiled_patterns['coa'].search(text))
        has_qr = bool(self.compiled_patterns['qr_code'].search(text))
        has_batch_lookup = bool(self.compiled_patterns['batch_lookup'].search(text))

        return {
            "has_coa": has_coa,
            "has_qr_code": has_qr,
            "has_batch_lookup": has_batch_lookup,
            "qualifies": has_coa or has_qr or has_batch_lookup
        }

    # Programs that test for heavy metals (lead, arsenic, mercury, cadmium)
    HEAVY_METAL_TESTING_PROGRAMS = [
        "NSF Sport", "NSF Certified", "USP Verified", "ConsumerLab", "IFOS"
    ]

    # Programs that verify label accuracy (ingredient identity & potency)
    LABEL_ACCURACY_PROGRAMS = [
        "USP Verified", "ConsumerLab", "NSF Certified"
    ]

    # Programs that test for purity/contaminants (pesticides, microbes, etc.)
    PURITY_TESTING_PROGRAMS = [
        "NSF Sport", "NSF Certified", "USP Verified", "ConsumerLab",
        "IFOS", "Informed Sport", "Informed Choice", "BSCG"
    ]

    # Categories with elevated contamination risk (based on ConsumerLab/FDA data)
    HIGH_CONTAMINATION_RISK_CATEGORIES = {
        "protein_powder": {
            "risk_level": "elevated",
            "concerns": ["heavy_metals", "bpa"],
            "note": "Independent tests found lead/arsenic in many protein supplements"
        },
        "greens_superfood": {
            "risk_level": "elevated",
            "concerns": ["heavy_metals", "pesticides"],
            "note": "Plant-based concentrates may accumulate soil contaminants"
        },
        "ayurvedic_herbal": {
            "risk_level": "high",
            "concerns": ["heavy_metals", "adulterants"],
            "note": "Traditional preparations sometimes contain lead/mercury"
        },
        "weight_loss": {
            "risk_level": "high",
            "concerns": ["adulterants", "stimulants"],
            "note": "FDA has found hidden drugs in weight loss supplements"
        },
        "sexual_enhancement": {
            "risk_level": "high",
            "concerns": ["adulterants", "prescription_drugs"],
            "note": "FDA frequently finds hidden Viagra/Cialis analogs"
        },
        "sports_performance": {
            "risk_level": "moderate",
            "concerns": ["banned_substances", "stimulants"],
            "note": "May contain substances banned by WADA"
        }
    }

    def _derive_safety_flags(self, third_party: Dict, product: Dict) -> Dict:
        """
        Derive safety verification flags from certification programs.

        These flags indicate whether the product has been tested by programs
        that verify specific safety criteria:
        - purity_verified: Tested for contaminants (pesticides, microbes, etc.)
        - heavy_metal_tested: Tested for heavy metals (Pb, As, Hg, Cd)
        - label_accuracy_verified: Ingredient identity and potency verified

        Also assesses category-based contamination risk.
        """
        programs = third_party.get("programs", [])
        program_names = [p.get("name", "") for p in programs]

        # Check if any program covers each safety criterion
        purity_verified = any(
            name in self.PURITY_TESTING_PROGRAMS for name in program_names
        )
        heavy_metal_tested = any(
            name in self.HEAVY_METAL_TESTING_PROGRAMS for name in program_names
        )
        label_accuracy_verified = any(
            name in self.LABEL_ACCURACY_PROGRAMS for name in program_names
        )

        # Assess category-based contamination risk
        category_risk = self._assess_category_contamination_risk(product)

        return {
            "purity_verified": purity_verified,
            "heavy_metal_tested": heavy_metal_tested,
            "label_accuracy_verified": label_accuracy_verified,
            "verifying_programs": program_names if program_names else [],
            "category_contamination_risk": category_risk
        }

    def _assess_category_contamination_risk(self, product: Dict) -> Dict:
        """
        Assess contamination risk based on product category.

        Returns risk level and specific concerns for high-risk categories.
        """
        product_name = (product.get("product_name", "") or product.get("fullName", "")).lower()
        # Normalize targetGroups - can be list of strings or dicts
        raw_groups = product.get("targetGroups", [])
        normalized_groups = []
        for tg in raw_groups:
            if isinstance(tg, str):
                normalized_groups.append(tg)
            elif isinstance(tg, dict):
                normalized_groups.append(tg.get('text', '') or tg.get('name', '') or '')
        target_groups = " ".join(normalized_groups).lower()
        all_text = f"{product_name} {target_groups}"

        # Check for high-risk category indicators
        risk_indicators = {
            "protein_powder": ["protein powder", "whey protein", "casein protein",
                              "plant protein", "pea protein", "protein isolate"],
            "greens_superfood": ["greens powder", "superfood", "green blend",
                                "spirulina", "chlorella", "barley grass"],
            "ayurvedic_herbal": ["ayurvedic", "ayurveda", "ashwagandha", "triphala",
                                "guggul", "brahmi", "shatavari"],
            "weight_loss": ["weight loss", "fat burner", "thermogenic", "metabolism",
                           "appetite suppressant", "diet pill"],
            "sexual_enhancement": ["sexual enhancement", "male enhancement", "libido",
                                  "testosterone booster", "ed support"],
            "sports_performance": ["pre-workout", "pre workout", "bcaa", "creatine",
                                  "sports performance", "athletic"]
        }

        detected_category = None
        for category, keywords in risk_indicators.items():
            if any(keyword in all_text for keyword in keywords):
                detected_category = category
                break

        if detected_category and detected_category in self.HIGH_CONTAMINATION_RISK_CATEGORIES:
            risk_info = self.HIGH_CONTAMINATION_RISK_CATEGORIES[detected_category]
            return {
                "has_elevated_risk": True,
                "category": detected_category,
                "risk_level": risk_info["risk_level"],
                "concerns": risk_info["concerns"],
                "note": risk_info["note"]
            }

        return {
            "has_elevated_risk": False,
            "category": None,
            "risk_level": "standard",
            "concerns": [],
            "note": None
        }

    def _collect_proprietary_data(self, product: Dict) -> Dict:
        """
        Collect proprietary blend data for scoring Section B4.
        """
        active_ingredients = product.get('activeIngredients', [])

        blends = []
        total_active = len(active_ingredients)

        for ingredient in active_ingredients:
            if ingredient.get('proprietaryBlend', False) or ingredient.get('isProprietaryBlend', False):
                disclosure = ingredient.get('disclosureLevel', 'none')
                nested = ingredient.get('nestedIngredients', [])

                blends.append({
                    "name": ingredient.get('name', ''),
                    "disclosure_level": disclosure,
                    "nested_count": len(nested),
                    "total_weight": ingredient.get('quantity', 0),
                    "unit": ingredient.get('unit', '')
                })

        return {
            "has_proprietary_blends": len(blends) > 0,
            "blends": blends,
            "blend_count": len(blends),
            "total_active_ingredients": total_active
        }

    # =========================================================================
    # SECTION C: EVIDENCE & RESEARCH DATA COLLECTORS
    # =========================================================================

    def _collect_evidence_data(self, product: Dict) -> Dict:
        """
        Collect clinical evidence data for scoring Section C.
        """
        clinical_db = self.databases.get('backed_clinical_studies', {})
        studies = clinical_db.get('backed_clinical_studies', [])

        active_ingredients = product.get('activeIngredients', [])
        matches = []

        for ingredient in active_ingredients:
            ing_name = ingredient.get('name', '')
            std_name = ingredient.get('standardName', '') or ing_name

            for study in studies:
                study_name = study.get('standard_name', '')
                study_aliases = study.get('aliases', [])

                if self._exact_match(ing_name, study_name, study_aliases) or \
                   self._exact_match(std_name, study_name, study_aliases):

                    # For brand-specific studies, check brand mention
                    study_id = study.get('id', '')
                    if study_id.startswith('BRAND_'):
                        if not self._brand_mentioned(study_name, study_aliases, product):
                            continue

                    matches.append({
                        "ingredient": ing_name,
                        "study_id": study_id,
                        "study_name": study_name,
                        "evidence_level": study.get('evidence_level', 'ingredient-human'),
                        "study_type": study.get('study_type', 'rct_single'),
                        "score_contribution": study.get('score_contribution', 'tier_3'),
                        "health_goals_supported": study.get('health_goals_supported', []),
                        "key_endpoints": study.get('key_endpoints', [])
                    })
                    break  # One match per ingredient

        # Check for unsubstantiated claims
        all_text = self._get_all_product_text(product)
        unsubstantiated = self._check_unsubstantiated_claims(all_text)

        return {
            "clinical_matches": matches,
            "match_count": len(matches),
            "unsubstantiated_claims": unsubstantiated
        }

    def _brand_mentioned(self, study_name: str, aliases: List[str], product: Dict) -> bool:
        """Check if brand is explicitly mentioned in product"""
        all_text = self._get_all_product_text(product).lower()

        terms = [study_name.lower()] + [a.lower() for a in aliases]
        return any(term in all_text for term in terms)

    def _check_unsubstantiated_claims(self, text: str) -> Dict:
        """Check for egregious unsubstantiated claims"""
        found_claims = []

        checks = [
            ('disease_claims', 'disease treatment claim', -5),
            ('miracle_claims', 'miracle/instant cure claim', -5),
            ('fda_approved', 'false FDA approval claim', -5)
        ]

        for pattern_name, claim_type, penalty in checks:
            if self.compiled_patterns[pattern_name].search(text):
                found_claims.append({
                    "type": claim_type,
                    "severity": "critical"
                })

        return {
            "found": len(found_claims) > 0,
            "claims": found_claims
        }

    # =========================================================================
    # SECTION D: BRAND TRUST DATA COLLECTORS
    # =========================================================================

    def _collect_manufacturer_data(self, product: Dict) -> Dict:
        """
        Collect manufacturer data for scoring Section D.
        """
        brand_name = product.get('brandName', '')
        contacts = product.get('contacts', [])

        # Get manufacturer from contacts
        manufacturer = ""
        for contact in contacts:
            if 'Manufacturer' in contact.get('types', []):
                manufacturer = contact.get('contactDetails', {}).get('name', '')
                break

        if not manufacturer:
            manufacturer = brand_name

        return {
            "brand_name": brand_name,
            "manufacturer": manufacturer,
            "top_manufacturer": self._check_top_manufacturer(brand_name, manufacturer),
            "violations": self._check_violations(brand_name, manufacturer),
            "country_of_origin": self._extract_country(product),
            "bonus_features": self._collect_bonus_features(product)
        }

    def _check_top_manufacturer(self, brand: str, manufacturer: str) -> Dict:
        """
        Check if manufacturer is in top manufacturers list.
        Uses exact match first, then fuzzy match as fallback.
        """
        top_db = self.databases.get('top_manufacturers_data', {})
        top_list = top_db.get('top_manufacturers', [])

        for top_mfr in top_list:
            std_name = top_mfr.get('standard_name', '')
            aliases = top_mfr.get('aliases', [])

            # Try exact match first (faster, more reliable)
            if self._exact_match(brand, std_name, aliases) or \
               self._exact_match(manufacturer, std_name, aliases):
                return {
                    "found": True,
                    "manufacturer_id": top_mfr.get('id', ''),
                    "name": std_name,
                    "match_type": "exact"
                }

            # Fuzzy match as fallback for variations like "Thorne" vs "Thorne Research"
            brand_match, brand_score = self._fuzzy_company_match(brand, std_name)
            mfr_match, mfr_score = self._fuzzy_company_match(manufacturer, std_name)

            if brand_match or mfr_match:
                return {
                    "found": True,
                    "manufacturer_id": top_mfr.get('id', ''),
                    "name": std_name,
                    "match_type": "fuzzy",
                    "match_confidence": round(max(brand_score, mfr_score), 3)
                }

        return {"found": False}

    def _check_violations(self, brand: str, manufacturer: str) -> Dict:
        """
        Check for manufacturer violations using fuzzy matching.

        Handles variations like:
        - "Healthy Directions" vs "Healthy Directions, LLC"
        - "Dr. David Williams" vs "David Williams"
        - "Natural Living" vs "Natural Living, Inc."
        """
        violations_db = self.databases.get('manufacturer_violations', {})
        violations_list = violations_db.get('manufacturer_violations', [])

        found = []
        for violation in violations_list:
            mfr_name = violation.get('manufacturer', '')
            if not mfr_name:
                continue

            # Check for match using fuzzy company name matching
            brand_match, brand_score = self._fuzzy_company_match(brand, mfr_name)
            mfr_match, mfr_score = self._fuzzy_company_match(manufacturer, mfr_name)

            if brand_match or mfr_match:
                match_score = max(brand_score, mfr_score)
                found.append({
                    "violation_id": violation.get('id', ''),
                    "violation_type": violation.get('violation_type', ''),
                    "severity": violation.get('violation_severity', ''),
                    "date": violation.get('date', ''),
                    "total_deduction": violation.get('total_deduction_applied', 0),
                    "is_resolved": violation.get('is_resolved', False),
                    "match_confidence": round(match_score, 3)
                })

        return {
            "found": len(found) > 0,
            "violations": found
        }

    def _extract_country(self, product: Dict) -> Dict:
        """Extract country of origin data"""
        all_text = self._get_all_product_text(product)

        made_usa = bool(self.compiled_patterns['made_usa'].search(all_text))
        made_eu = bool(self.compiled_patterns['made_eu'].search(all_text))

        # List of high-regulation countries
        high_reg = made_usa or made_eu

        country = ""
        if made_usa:
            country = "USA"
        elif made_eu:
            # Try to extract specific EU country
            eu_match = self.compiled_patterns['made_eu'].search(all_text)
            if eu_match:
                country = eu_match.group(0)

        return {
            "detected": country != "",
            "country": country,
            "high_regulation_country": high_reg
        }

    def _collect_bonus_features(self, product: Dict) -> Dict:
        """Collect bonus feature data"""
        all_text = self._get_all_product_text(product)

        physician = bool(self.compiled_patterns['physician'].search(all_text))
        sustainability = bool(self.compiled_patterns['sustainability'].search(all_text))

        # Extract sustainability text if found
        sustainability_text = ""
        if sustainability:
            match = self.compiled_patterns['sustainability'].search(all_text)
            if match:
                sustainability_text = match.group(0)

        return {
            "physician_formulated": physician,
            "sustainability_claim": sustainability,
            "sustainability_text": sustainability_text
        }

    # =========================================================================
    # PROBIOTIC-SPECIFIC DATA COLLECTOR
    # =========================================================================

    # Survivability coating keywords for probiotic scoring
    # P1.2: Enhanced with additional common phrases
    SURVIVABILITY_KEYWORDS = [
        "enteric coated", "enteric-coated", "enteric coating",
        "delayed release", "delayed-release", "dr caps", "drcaps",
        "bio-tract", "biotract", "livebac",
        "acid-resistant", "acid resistant", "acid-protected",
        "survives stomach acid", "stomach acid resistant",
        "patented delivery", "targeted release",
        "spore-based", "spore-forming", "spore forming",
        "bacillus coagulans", "bacillus subtilis",  # Inherently spore-forming
        # P1.2: Additional keywords from plan
        "protected by an outer layer", "protected by patented",
        "outer protective layer", "proprietary coating",
        "microencapsulated", "acid-resistant coating",
        "protective coating", "survives digestive tract",
        "survives gi tract", "gastric bypass",
        "protected strain", "protected probiotic"
    ]

    def _collect_probiotic_data(self, product: Dict) -> Dict:
        """
        Collect probiotic-specific data for scoring.
        - CFU count and guarantee type
        - Strain diversity
        - Clinically relevant strains
        - Prebiotic pairing
        - Survivability coating
        """
        active_ingredients = product.get('activeIngredients', [])
        all_ingredients = active_ingredients + product.get('inactiveIngredients', [])

        # Check if this is a probiotic product
        probiotic_blends = []
        total_strains = 0
        all_nested_strains = []

        for ingredient in active_ingredients:
            ing_name = ingredient.get('name', '').lower()
            category = ingredient.get('category', '').lower()

            # Check for probiotic indicators (including abbreviated forms and strain names)
            probiotic_terms = [
                'probiotic', 'lactobacillus', 'bifidobacterium', 'streptococcus',
                'bacillus', 'saccharomyces', 'limosilactobacillus',
                # Strain-specific terms
                'reuteri', 'rhamnosus', 'acidophilus', 'plantarum', 'casei',
                'salivarius', 'coagulans', 'prodentis', 'protectis', 'subtilis',
                # Abbreviated forms
                'l. reuteri', 'l. rhamnosus', 'l. acidophilus', 'l. plantarum',
                'b. lactis', 'b. longum', 'b. infantis', 's. salivarius',
                'b. subtilis', 'b. coagulans',
                # CFU indicators
                'cfu', 'billion cfu', 'live cultures', 'viable cells'
            ]
            is_probiotic = any(term in ing_name for term in probiotic_terms)
            is_probiotic = is_probiotic or 'probiotic' in category or 'bacteria' in category

            if is_probiotic:
                nested = ingredient.get('nestedIngredients', [])
                harvest = ingredient.get('harvestMethod', '') or ''
                notes = ingredient.get('notes', '') or ''

                # P1.1: Extract CFU from text AND from quantity/unit
                # Also include product statements for guarantee type (e.g., "At the time of manufacture.")
                statements_text = ' '.join([
                    s.get('notes', '') or s.get('text', '') or str(s)
                    for s in product.get('statements', [])
                    if isinstance(s, dict) or isinstance(s, str)
                ])
                cfu_text = harvest + ' ' + notes + ' ' + statements_text
                cfu_data = self._extract_cfu(cfu_text, ingredient=ingredient)

                probiotic_blends.append({
                    "name": ingredient.get('name', ''),
                    "strain_count": len(nested) if nested else 1,
                    "strains": [n.get('name', '') for n in nested] if nested else [ingredient.get('name', '')],
                    "cfu_data": cfu_data
                })

                total_strains += len(nested) if nested else 1
                all_nested_strains.extend([n.get('name', '') for n in nested] if nested else [ingredient.get('name', '')])

        if not probiotic_blends:
            return {"is_probiotic_product": False}

        # Check for clinically relevant strains
        strains_db = self.databases.get('clinically_relevant_strains', {})
        clinical_strains = strains_db.get('clinically_relevant_strains', [])

        found_clinical_strains = []
        for strain in all_nested_strains:
            for clinical in clinical_strains:
                clin_name = clinical.get('standard_name', '')
                clin_aliases = clinical.get('aliases', [])

                # Use strain-specific matching for probiotic strain names
                if self._strain_match(strain, clin_name, clin_aliases):
                    found_clinical_strains.append({
                        "strain": strain,
                        "clinical_id": clinical.get('id', ''),
                        "evidence_level": clinical.get('evidence_level', 'moderate')
                    })
                    break

        # Check for prebiotic pairing
        prebiotics_data = strains_db.get('prebiotics', {}).get('ingredients', [])
        prebiotic_found = False
        prebiotic_name = ""

        for ing in all_ingredients:
            ing_name = ing.get('name', '')
            std_name = ing.get('standardName', '') or ing_name

            for prebiotic in prebiotics_data:
                pre_name = prebiotic.get('standard_name', '')
                pre_aliases = prebiotic.get('aliases', [])

                if self._exact_match(ing_name, pre_name, pre_aliases) or \
                   self._exact_match(std_name, pre_name, pre_aliases):
                    prebiotic_found = True
                    prebiotic_name = pre_name
                    break
            if prebiotic_found:
                break

        # Check for survivability coating
        has_survivability_coating = False
        survivability_reason = ""

        # Build text to search: product name, delivery form, harvestMethod, notes, label text
        product_name = product.get('product_name', product.get('fullName', '')).lower()
        delivery_form = product.get('deliveryForm', '').lower()
        label_text = self._get_safe_text_field(product, 'labelText').lower()

        # Combine all text sources for checking
        texts_to_check = [product_name, delivery_form, label_text]

        # Also check harvestMethod and notes from probiotic ingredients
        for blend in probiotic_blends:
            for ing in active_ingredients:
                if ing.get('name', '') == blend.get('name', ''):
                    texts_to_check.append((ing.get('harvestMethod', '') or '').lower())
                    texts_to_check.append((ing.get('notes', '') or '').lower())

        combined_text = ' '.join(texts_to_check)

        for keyword in self.SURVIVABILITY_KEYWORDS:
            if keyword in combined_text:
                has_survivability_coating = True
                survivability_reason = keyword
                break

        # Calculate aggregate CFU data from blends
        total_cfu = 0
        has_cfu = False
        guarantee_type = None
        total_billion_count = 0.0

        for blend in probiotic_blends:
            cfu_data = blend.get('cfu_data', {})
            if cfu_data.get('has_cfu'):
                has_cfu = True
                total_cfu += cfu_data.get('cfu_count', 0)
                total_billion_count += cfu_data.get('billion_count', 0)
            # Take first non-None guarantee_type
            if not guarantee_type and cfu_data.get('guarantee_type'):
                guarantee_type = cfu_data.get('guarantee_type')

        return {
            "is_probiotic": True,  # Top-level flag for quick filtering
            "is_probiotic_product": True,
            "probiotic_blends": probiotic_blends,
            "total_strain_count": total_strains,
            # Aggregate CFU data at top level for easy access
            "has_cfu": has_cfu,
            "total_cfu": total_cfu,
            "total_billion_count": total_billion_count,
            "guarantee_type": guarantee_type,
            # Clinical and other data
            "clinical_strains": found_clinical_strains,
            "clinical_strain_count": len(found_clinical_strains),
            "prebiotic_present": prebiotic_found,
            "prebiotic_name": prebiotic_name,
            "has_survivability_coating": has_survivability_coating,
            "survivability_reason": survivability_reason
        }

    # P1.1: CFU-equivalent units
    CFU_EQUIVALENT_UNITS = [
        'viable cell(s)', 'viable cells', 'cells', 'cfu',
        'colony forming units', 'live cells', 'active cells'
    ]

    def _extract_cfu(self, text: str, ingredient: Optional[Dict] = None) -> Dict:
        """
        Extract CFU information from text and ingredient quantity.

        P1.1: Recognizes "Viable Cell(s)" as CFU-equivalent unit.
        """
        result = {
            "has_cfu": False,
            "cfu_count": 0,
            "billion_count": 0,
            "guarantee_type": None  # 'at_manufacture' or 'at_expiration'
        }

        # P1.1: First check ingredient quantity/unit for CFU-equivalent units
        if ingredient:
            quantity = ingredient.get('quantity', 0)
            unit = (ingredient.get('unit', '') or '').lower()

            if unit and any(cfu_unit in unit for cfu_unit in self.CFU_EQUIVALENT_UNITS):
                if quantity and quantity > 0:
                    result["has_cfu"] = True
                    result["cfu_count"] = quantity
                    result["billion_count"] = quantity / 1e9

        # Also check text for CFU mentions
        if text:
            # Extract billion count from text (full word "billion")
            match = self.compiled_patterns['cfu_billion'].search(text)
            if match:
                billion_from_text = float(match.group(1))
                # Only override if ingredient didn't provide CFU or text has higher value
                if not result["has_cfu"] or billion_from_text > result["billion_count"]:
                    result["has_cfu"] = True
                    result["billion_count"] = billion_from_text
                    result["cfu_count"] = billion_from_text * 1e9

            # Also check abbreviated billion format (e.g., "1.5 B CFU")
            if not result["has_cfu"]:
                abbrev_match = self.compiled_patterns['cfu_billion_abbrev'].search(text)
                if abbrev_match:
                    billion_from_text = float(abbrev_match.group(1))
                    result["has_cfu"] = True
                    result["billion_count"] = billion_from_text
                    result["cfu_count"] = billion_from_text * 1e9

            # Also check for million CFU (e.g., "500 Million CFUs")
            if not result["has_cfu"]:
                million_match = self.compiled_patterns['cfu_million'].search(text)
                if million_match:
                    million_from_text = float(million_match.group(1))
                    result["has_cfu"] = True
                    result["billion_count"] = million_from_text / 1000  # Convert to billions
                    result["cfu_count"] = million_from_text * 1e6

            # P1.1: Enhanced guarantee type parsing
            result["guarantee_type"] = self._extract_guarantee_type(text)

        return result

    def _extract_guarantee_type(self, text: str) -> Optional[str]:
        """
        P1.1: Extract CFU guarantee type from text.

        Returns:
        - 'at_manufacture' for "At the time of manufacture"
        - 'at_expiration' for "Until expiration" / "Through expiration"
        - None if no guarantee statement found
        """
        if not text:
            return None

        text_lower = text.lower()

        # Check for expiration guarantee first (more valuable)
        if self.compiled_patterns['cfu_expiration'].search(text):
            return "at_expiration"

        # Check for manufacture guarantee
        if self.compiled_patterns['cfu_manufacture'].search(text):
            return "at_manufacture"

        # P1.1: Additional patterns for guarantee type
        expiration_patterns = [
            'until expiration', 'through expiration', 'at expiration',
            'best by date', 'until best by', 'at time of expiration'
        ]
        manufacture_patterns = [
            'at the time of manufacture', 'at time of manufacture',
            'at manufacture', 'when manufactured', 'at production'
        ]

        for pattern in expiration_patterns:
            if pattern in text_lower:
                return "at_expiration"

        for pattern in manufacture_patterns:
            if pattern in text_lower:
                return "at_manufacture"

        return None

    # =========================================================================
    # SUPPLEMENT TYPE CLASSIFIER
    # =========================================================================

    def _classify_supplement_type(self, product: Dict) -> Dict:
        """
        Classify supplement type for context-aware scoring.
        Types: single_nutrient, targeted, multivitamin, herbal_blend, probiotic, prebiotic, specialty
        """
        active_ingredients = product.get('activeIngredients', [])
        inactive_ingredients = product.get('inactiveIngredients', [])

        active_count = len(active_ingredients)
        total_count = active_count + len(inactive_ingredients)

        # Count categories
        category_counts = {}
        for ing in active_ingredients:
            cat = ing.get('category', 'other').lower()
            category_counts[cat] = category_counts.get(cat, 0) + 1

        # Determine type
        supplement_type = "unknown"

        # Single nutrient
        if active_count == 1:
            supplement_type = "single_nutrient"

        # Probiotic (>50% probiotic strains)
        elif category_counts.get('probiotic', 0) + category_counts.get('bacteria', 0) > active_count * 0.5:
            supplement_type = "probiotic"

        # Herbal blend (>60% botanicals)
        elif category_counts.get('botanical', 0) + category_counts.get('herb', 0) > active_count * 0.6:
            supplement_type = "herbal_blend"

        # Multivitamin (6+ actives, mixed categories)
        elif active_count >= 6 and len(category_counts) >= 3:
            supplement_type = "multivitamin"

        # Targeted (2-5 actives, same category)
        elif 2 <= active_count <= 5:
            if len(category_counts) <= 2:
                supplement_type = "targeted"
            else:
                supplement_type = "specialty"

        else:
            supplement_type = "specialty"

        return {
            "type": supplement_type,
            "active_count": active_count,
            "total_count": total_count,
            "category_breakdown": category_counts
        }

    # =========================================================================
    # DIETARY SENSITIVITY DATA COLLECTOR (Sugar/Sodium for Diabetes/Hypertension)
    # =========================================================================

    # FDA/AHA Thresholds for sodium per serving (based on FDA labeling rules)
    SODIUM_THRESHOLDS = {
        "sodium_free": 5,          # <5mg = "Sodium-Free" (FDA 21 CFR 101.61)
        "very_low_sodium": 35,     # ≤35mg = "Very Low Sodium" (FDA)
        "low_sodium": 140,         # ≤140mg = "Low Sodium" (FDA/AHA recommended)
        "moderate_sodium": 400,    # >140mg but ≤400mg = moderate concern
        "high_sodium": 400         # >400mg = high concern for hypertension
    }

    # Sugar thresholds per serving (based on FDA labeling and ADA guidelines)
    SUGAR_THRESHOLDS = {
        "sugar_free": 0.5,         # <0.5g = "Sugar-Free" (FDA 21 CFR 101.60)
        "low_sugar": 3,            # ≤3g = generally acceptable for diabetics
        "moderate_sugar": 5,       # 3-5g = moderate concern
        "high_sugar": 5            # >5g = high concern for diabetics
    }

    def _collect_dietary_sensitivity_data(self, product: Dict) -> Dict:
        """
        Collect sugar and sodium data for users with dietary sensitivities.

        Designed to help users with:
        - Diabetes (Type 1, Type 2, Prediabetes) - sugar awareness
        - Hypertension (high blood pressure) - sodium awareness
        - Heart disease / cardiovascular conditions - both
        - Kidney disease - sodium and sugar awareness

        Thresholds based on:
        - FDA labeling requirements (21 CFR 101.60, 101.61)
        - American Heart Association recommendations (<1,500mg/day sodium)
        - American Diabetes Association Standards of Care 2024
        """
        nutritional_info = product.get('nutritionalInfo', {})

        # Extract sugar data
        sugar_data = self._analyze_sugar_content(product, nutritional_info)

        # Extract sodium data
        sodium_data = self._analyze_sodium_content(product, nutritional_info)

        # Check for problematic sweeteners (for diabetics)
        sweetener_data = self._check_problematic_sweeteners(product)

        # Generate user-facing warnings
        warnings = self._generate_dietary_warnings(sugar_data, sodium_data, sweetener_data)

        return {
            "sugar": sugar_data,
            "sodium": sodium_data,
            "sweeteners": sweetener_data,
            "warnings": warnings,
            # Quick boolean flags for filtering
            # P0.2: Use contains_sugar from sugar_data (considers both amount AND ingredient sources)
            "contains_sugar": sugar_data.get("contains_sugar", sugar_data["amount_g"] > 0),
            "contains_sodium": sodium_data["amount_mg"] > 0,
            # P0.2: diabetes_friendly must be false if contains_sugar is true
            "diabetes_friendly": not sugar_data.get("contains_sugar", False) and sugar_data["level"] in ["sugar_free", "low"],
            "hypertension_friendly": sodium_data["level"] in ["sodium_free", "very_low", "low"]
        }

    def _collect_serving_basis_data(self, product: Dict) -> Dict:
        """
        P0.4: Extract serving basis information for deterministic prescore
        and on-device recalculation.

        Derives from:
        - servingSizes[] → basis_count, canonical_serving_size_quantity
        - physicalState.langualCodeDescription → form_factor
        - delivery_data.systems[0].name → form_factor (fallback)
        - statements[] directions parsing → min_recommended, max_recommended
        - userGroups[] → selection_policy

        Returns:
            Dict with serving_basis and form_factor at top level
        """
        serving_sizes = product.get('servingSizes', [])
        physical_state = product.get('physicalState', {})
        statements = product.get('statements', [])
        user_groups = product.get('userGroups', [])

        # Determine form_factor from physicalState
        form_factor = None
        langual_desc = physical_state.get('langualCodeDescription', '')
        if langual_desc:
            form_factor = self._normalize_form_factor(langual_desc)

        # Fallback: try delivery_data if already collected
        if not form_factor:
            delivery_data = getattr(self, '_last_delivery_data', None)
            if delivery_data and delivery_data.get('systems'):
                form_factor = delivery_data['systems'][0].get('name', '').lower()

        # Extract basis from servingSizes
        basis_count = None
        basis_unit = None
        canonical_serving_size_qty = None

        if serving_sizes and isinstance(serving_sizes, list):
            # Look for adult/primary serving size
            primary_serving = self._select_canonical_serving(serving_sizes, user_groups)
            if primary_serving:
                # Handle various field names for quantity
                basis_count = (
                    primary_serving.get('quantity') or
                    primary_serving.get('servingSizeQuantity') or
                    primary_serving.get('maxQuantity') or
                    primary_serving.get('minQuantity')
                )
                # Handle various field names for unit
                basis_unit = (
                    primary_serving.get('servingSizeUnitOfMeasure') or
                    primary_serving.get('unit') or
                    ''
                )
                canonical_serving_size_qty = basis_count

                # Normalize unit - FIX: use replace() not rstrip()
                if basis_unit:
                    basis_unit = basis_unit.lower()
                    # Remove common suffixes properly
                    basis_unit = basis_unit.replace('(ies)', '').replace('(s)', '').replace('(es)', '')
                    basis_unit = basis_unit.rstrip('s') if basis_unit.endswith('ies') == False else basis_unit[:-3] + 'y'
                    # Final cleanup for "gummy(ie" type issues
                    basis_unit = re.sub(r'\([^)]*$', '', basis_unit)  # Remove unclosed parens
                    basis_unit = basis_unit.strip()

        # Parse directions for min/max recommended
        min_recommended = None
        max_recommended = None
        parsed_from_directions = False

        # First check labelText.parsed.directions
        label_text = product.get('labelText', {})
        if isinstance(label_text, dict):
            parsed = label_text.get('parsed', {})
            directions_text = parsed.get('directions', '')
            if directions_text:
                dosage_info = self._parse_dosage_from_directions(directions_text)
                if dosage_info:
                    min_recommended = dosage_info.get('min')
                    max_recommended = dosage_info.get('max')
                    parsed_from_directions = True

        # Fallback to statements if not found
        if not parsed_from_directions:
            for statement in statements:
                if isinstance(statement, dict):
                    stmt_type = statement.get('type', '').lower()
                    stmt_text = statement.get('text', '') or statement.get('notes', '')
                else:
                    stmt_type = ''
                    stmt_text = str(statement)

                if 'direction' in stmt_type or 'dosage' in stmt_type or 'take' in stmt_text.lower() or 'chew' in stmt_text.lower():
                    dosage_info = self._parse_dosage_from_directions(stmt_text)
                    if dosage_info:
                        min_recommended = dosage_info.get('min')
                        max_recommended = dosage_info.get('max')
                        parsed_from_directions = True
                        break

        # Determine selection policy
        selection_policy = "first_serving"
        selected_from = "servingSizes"
        basis_reason = "default"

        if user_groups:
            # Check if we have adult-specific groups
            for group in user_groups:
                if isinstance(group, dict):
                    # Handle various field names in userGroups
                    group_text = (
                        group.get('text', '') or
                        group.get('dailyValueTargetGroupName', '') or
                        group.get('langualCodeDescription', '') or
                        group.get('name', '')
                    )
                else:
                    group_text = str(group)

                if 'adult' in group_text.lower() or 'children 4' in group_text.lower():
                    selection_policy = "adult_primary"
                    selected_from = "userGroups"
                    basis_reason = "adult_default_from_userGroups"
                    break

        return {
            "serving_basis": {
                "basis_count": basis_count,
                "basis_unit": basis_unit,
                "basis_reason": basis_reason,
                "min_recommended": min_recommended,
                "max_recommended": max_recommended,
                "parsed_from_directions": parsed_from_directions,
                "selection_policy": selection_policy,
                "selected_from": selected_from,
                "canonical_serving_size_quantity": canonical_serving_size_qty
            },
            "form_factor": form_factor
        }

    def _normalize_form_factor(self, langual_desc: str) -> Optional[str]:
        """Normalize langualCodeDescription to standard form_factor."""
        desc_lower = langual_desc.lower()

        form_mapping = {
            'gummy': 'gummy',
            'gummies': 'gummy',
            'chewable': 'chewable',
            'tablet': 'tablet',
            'capsule': 'capsule',
            'softgel': 'softgel',
            'liquid': 'liquid',
            'powder': 'powder',
            'drop': 'drop',
            'lozenge': 'lozenge',
            'spray': 'spray',
            'patch': 'patch'
        }

        for key, value in form_mapping.items():
            if key in desc_lower:
                return value

        return langual_desc.lower() if langual_desc else None

    def _select_canonical_serving(self, serving_sizes: List[Dict], user_groups: List) -> Optional[Dict]:
        """
        Select the canonical serving size based on user groups.

        Selection Rule (P0.3/P0.4):
        1. Choose adult/primary basis if present (often "Adults and children 4+")
        2. If no adult group, use highest serving_size_quantity
        3. Default to first serving size
        """
        if not serving_sizes:
            return None

        # If we have user groups, try to match adult serving
        if user_groups:
            for group in user_groups:
                if isinstance(group, dict):
                    group_text = (
                        group.get('text', '') or
                        group.get('dailyValueTargetGroupName', '') or
                        group.get('langualCodeDescription', '') or
                        group.get('name', '')
                    )
                else:
                    group_text = str(group)

                if 'adult' in group_text.lower():
                    # Find serving size that matches this group (highest quantity = adult)
                    # Since cleaned servingSizes don't have targetGroup, use highest quantity
                    pass  # Fall through to max quantity selection

        # Find the highest serving quantity (adult default)
        max_serving = None
        max_qty = 0
        for serving in serving_sizes:
            # Handle various field names for quantity
            qty = (
                serving.get('quantity') or
                serving.get('servingSizeQuantity') or
                serving.get('maxQuantity') or
                serving.get('minQuantity') or
                serving.get('normalizedServing') or
                0
            )
            if qty > max_qty:
                max_qty = qty
                max_serving = serving

        return max_serving or (serving_sizes[0] if serving_sizes else None)

    # Word to number mapping for dosage parsing
    WORD_TO_NUM = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
    }

    def _parse_dosage_from_directions(self, text: str) -> Optional[Dict]:
        """Parse min/max dosage from directions text.

        Handles both numeric and word-based dosages:
        - "Take 2 gummies daily"
        - "Chew two gummies daily"
        - "Adults: chew two gummies"

        For multi-group directions, extracts the adult/max dosage.
        """
        text_lower = text.lower()

        # First convert word numbers to digits for easier parsing
        for word, num in self.WORD_TO_NUM.items():
            text_lower = re.sub(rf'\b{word}\b', str(num), text_lower)

        # Look for adult dosage specifically (prioritize adult instructions)
        adult_patterns = [
            r'adults[^:]*:\s*(?:chew|take)\s+(\d+)',  # "Adults: chew 2"
            r'adults[^:]*:\s*(\d+)\s+(?:tablet|capsule|gumm|softgel)',  # "Adults: 2 gummies"
            r'(?:4|four)\s+years[^:]*:\s*(?:chew|take)\s+(\d+)',  # "4 years: chew 2"
            r'older:\s*(?:chew|take)\s+(\d+)',  # "older: chew 2"
        ]

        for pattern in adult_patterns:
            match = re.search(pattern, text_lower)
            if match:
                adult_dose = int(match.group(1))
                # Also look for child dose to get range
                child_patterns = [
                    r'children\s+(?:\d+\s+to\s+)?(\d+)[^:]*:\s*(?:chew|take)\s+(\d+)',
                    r'(\d+)\s+to\s+\d+\s+years[^:]*:\s*(?:chew|take)\s+(\d+)',
                ]
                child_dose = None
                for cp in child_patterns:
                    cm = re.search(cp, text_lower)
                    if cm:
                        child_dose = int(cm.group(2)) if len(cm.groups()) >= 2 else int(cm.group(1))
                        break

                if child_dose and child_dose < adult_dose:
                    return {"min": child_dose, "max": adult_dose}
                return {"min": adult_dose, "max": adult_dose}

        # Fallback patterns for simpler directions
        patterns = [
            r'(?:take|chew)\s+(\d+)\s*(?:to|-)\s*(\d+)',  # "take 2 to 4"
            r'(?:take|chew)\s+(\d+)',  # "take 2" or "chew 2"
            r'(\d+)\s*(?:to|-)\s*(\d+)\s+(?:tablet|capsule|gumm|softgel)',  # "2 to 4 tablets"
            r'(\d+)\s+(?:tablet|capsule|gumm|softgel)',  # "2 tablets"
        ]

        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                groups = match.groups()
                if len(groups) >= 2 and groups[1]:
                    return {"min": int(groups[0]), "max": int(groups[1])}
                elif len(groups) >= 1:
                    return {"min": int(groups[0]), "max": int(groups[0])}

        return None

    def _analyze_sugar_content(self, product: Dict, nutritional_info: Dict) -> Dict:
        """
        Analyze sugar content from nutritionalInfo and ingredients.

        P0.2 Guardrail: Internal consistency enforcement
        - If has_added_sugar == true OR amount_g > 0, then contains_sugar = true
        - Never allow sugar_free level when amount_g > 0 or has_added_sugar
        """
        sugar_info = nutritional_info.get('sugars', {})
        amount = sugar_info.get('amount', 0) or 0
        unit = sugar_info.get('unit', 'Gram(s)')

        # Normalize to grams
        amount_g = float(amount) if amount else 0.0
        if 'mg' in str(unit).lower():
            amount_g = amount_g / 1000

        # Check if sugar is in inactive ingredients FIRST (needed for guardrail)
        sugar_in_ingredients = self._find_sugar_in_ingredients(product)
        has_added_sugar = len(sugar_in_ingredients) > 0

        # P0.2 GUARDRAIL: Determine contains_sugar flag
        # If sugar_g > 0 OR has_added_sugar, then contains_sugar = true
        contains_sugar = amount_g > 0 or has_added_sugar

        # Determine level based on FDA thresholds
        # P0.2 GUARDRAIL: Never allow sugar_free when contains_sugar is true
        if amount_g < self.SUGAR_THRESHOLDS["sugar_free"] and not contains_sugar:
            level = "sugar_free"
            level_display = "Sugar-Free"
        elif amount_g <= self.SUGAR_THRESHOLDS["low_sugar"]:
            level = "low"
            level_display = "Low Sugar"
        elif amount_g <= self.SUGAR_THRESHOLDS["moderate_sugar"]:
            level = "moderate"
            level_display = "Moderate Sugar"
        else:
            level = "high"
            level_display = "High Sugar"

        return {
            "amount_g": round(amount_g, 1),
            "unit": "g",
            "level": level,
            "level_display": level_display,
            "contains_sugar": contains_sugar,
            "exceeds_diabetic_threshold": amount_g > self.SUGAR_THRESHOLDS["low_sugar"],
            "sugar_sources": sugar_in_ingredients,
            "has_added_sugar": has_added_sugar
        }

    def _analyze_sodium_content(self, product: Dict, nutritional_info: Dict) -> Dict:
        """
        Analyze sodium content from nutritionalInfo and ingredients.
        """
        sodium_info = nutritional_info.get('sodium', {})
        amount = sodium_info.get('amount', 0) or 0
        unit = sodium_info.get('unit', 'mg')

        # Normalize to mg
        amount_mg = float(amount) if amount else 0.0
        if 'g' in str(unit).lower() and 'mg' not in str(unit).lower():
            amount_mg = amount_mg * 1000

        # Determine level based on FDA/AHA thresholds
        if amount_mg < self.SODIUM_THRESHOLDS["sodium_free"]:
            level = "sodium_free"
            level_display = "Sodium-Free"
        elif amount_mg <= self.SODIUM_THRESHOLDS["very_low_sodium"]:
            level = "very_low"
            level_display = "Very Low Sodium"
        elif amount_mg <= self.SODIUM_THRESHOLDS["low_sodium"]:
            level = "low"
            level_display = "Low Sodium"
        elif amount_mg <= self.SODIUM_THRESHOLDS["moderate_sodium"]:
            level = "moderate"
            level_display = "Moderate Sodium"
        else:
            level = "high"
            level_display = "High Sodium"

        # Check for sodium-containing ingredients
        sodium_sources = self._find_sodium_in_ingredients(product)

        return {
            "amount_mg": round(amount_mg, 1),
            "unit": "mg",
            "level": level,
            "level_display": level_display,
            "exceeds_aha_threshold": amount_mg > self.SODIUM_THRESHOLDS["low_sodium"],
            "percent_daily_value": round((amount_mg / 2300) * 100, 1) if amount_mg > 0 else 0,
            "sodium_sources": sodium_sources
        }

    def _find_sugar_in_ingredients(self, product: Dict) -> List[str]:
        """Find sugar-containing ingredients in the product."""
        sugar_keywords = [
            'sugar', 'sucrose', 'glucose', 'fructose', 'dextrose', 'maltose',
            'corn syrup', 'high fructose', 'cane', 'honey', 'agave', 'molasses',
            'maple syrup', 'brown rice syrup', 'tapioca syrup', 'invert sugar'
        ]

        found = []
        all_ingredients = (
            product.get('inactiveIngredients', []) +
            product.get('activeIngredients', [])
        )

        for ing in all_ingredients:
            name = ing.get('name', '').lower()
            std_name = ing.get('standardName', '').lower()

            for keyword in sugar_keywords:
                if keyword in name or keyword in std_name:
                    found.append(ing.get('name', ''))
                    break

        return list(set(found))

    def _find_sodium_in_ingredients(self, product: Dict) -> List[str]:
        """Find sodium-containing ingredients in the product."""
        # Note: Not all sodium compounds contribute dietary sodium equally
        # Salt (NaCl) is the primary concern; some sodium compounds are minimal
        high_sodium_keywords = [
            'salt', 'sodium chloride', 'sea salt', 'table salt'
        ]
        # These contain sodium but in smaller amounts
        moderate_sodium_keywords = [
            'sodium citrate', 'sodium bicarbonate', 'baking soda',
            'sodium ascorbate', 'sodium benzoate'
        ]

        found = []
        all_ingredients = (
            product.get('inactiveIngredients', []) +
            product.get('activeIngredients', [])
        )

        for ing in all_ingredients:
            name = ing.get('name', '').lower()
            std_name = ing.get('standardName', '').lower()

            # Check high-sodium sources first
            for keyword in high_sodium_keywords:
                if keyword in name or keyword in std_name:
                    found.append(f"{ing.get('name', '')} (high)")
                    break
            else:
                # Check moderate sodium sources
                for keyword in moderate_sodium_keywords:
                    if keyword in name or keyword in std_name:
                        found.append(f"{ing.get('name', '')} (trace)")
                        break

        return list(set(found))

    def _check_problematic_sweeteners(self, product: Dict) -> Dict:
        """
        Check for sweeteners that may be problematic for specific conditions.

        Based on:
        - WHO 2023 guidance on non-nutritive sweeteners
        - ADA 2024 standards (sweeteners can be used in moderation)
        - Recent research on gut microbiome effects
        """
        # High glycemic / problematic for diabetics
        high_glycemic_sweeteners = [
            'maltodextrin', 'dextrose', 'glucose syrup', 'corn syrup solids',
            'tapioca maltodextrin', 'rice syrup'
        ]

        # Artificial sweeteners (controversial, some research concerns)
        artificial_sweeteners = [
            'aspartame', 'sucralose', 'saccharin', 'acesulfame',
            'neotame', 'advantame'
        ]

        # Sugar alcohols (may cause GI issues)
        sugar_alcohols = [
            'sorbitol', 'mannitol', 'xylitol', 'erythritol', 'maltitol',
            'isomalt', 'lactitol'
        ]

        # Generally safer alternatives for diabetics
        safer_alternatives = [
            'stevia', 'monk fruit', 'allulose', 'lo han guo'
        ]

        found_high_glycemic = []
        found_artificial = []
        found_sugar_alcohols = []
        found_safer = []

        all_ingredients = (
            product.get('inactiveIngredients', []) +
            product.get('activeIngredients', [])
        )

        for ing in all_ingredients:
            name = ing.get('name', '').lower()
            std_name = ing.get('standardName', '').lower()
            combined = f"{name} {std_name}"

            for sweetener in high_glycemic_sweeteners:
                if sweetener in combined:
                    found_high_glycemic.append(ing.get('name', ''))
                    break

            for sweetener in artificial_sweeteners:
                if sweetener in combined:
                    found_artificial.append(ing.get('name', ''))
                    break

            for sweetener in sugar_alcohols:
                if sweetener in combined:
                    found_sugar_alcohols.append(ing.get('name', ''))
                    break

            for sweetener in safer_alternatives:
                if sweetener in combined:
                    found_safer.append(ing.get('name', ''))
                    break

        return {
            "high_glycemic": list(set(found_high_glycemic)),
            "artificial": list(set(found_artificial)),
            "sugar_alcohols": list(set(found_sugar_alcohols)),
            "safer_alternatives": list(set(found_safer)),
            "has_high_glycemic": len(found_high_glycemic) > 0,
            "has_artificial": len(found_artificial) > 0,
            "has_sugar_alcohols": len(found_sugar_alcohols) > 0,
            "uses_safer_alternatives": len(found_safer) > 0
        }

    def _generate_dietary_warnings(self, sugar_data: Dict, sodium_data: Dict,
                                   sweetener_data: Dict) -> List[Dict]:
        """
        Generate user-facing warnings for dietary sensitivities.
        """
        warnings = []

        # Sugar warnings for diabetics
        if sugar_data["exceeds_diabetic_threshold"]:
            warnings.append({
                "type": "diabetes",
                "severity": "high" if sugar_data["level"] == "high" else "moderate",
                "message": f"Contains {sugar_data['amount_g']}g sugar per serving. "
                          f"May affect blood glucose levels.",
                "recommendation": "Consult healthcare provider if managing diabetes."
            })

        # High glycemic sweetener warning
        if sweetener_data["has_high_glycemic"]:
            warnings.append({
                "type": "diabetes",
                "severity": "moderate",
                "message": f"Contains high-glycemic sweeteners: "
                          f"{', '.join(sweetener_data['high_glycemic'])}",
                "recommendation": "May cause blood sugar spikes despite low sugar content."
            })

        # Sodium warnings for hypertension
        if sodium_data["exceeds_aha_threshold"]:
            warnings.append({
                "type": "hypertension",
                "severity": "high" if sodium_data["level"] == "high" else "moderate",
                "message": f"Contains {sodium_data['amount_mg']}mg sodium per serving "
                          f"({sodium_data['percent_daily_value']}% DV).",
                "recommendation": "Monitor intake if managing blood pressure."
            })

        # Sugar alcohol warning (GI issues)
        if sweetener_data["has_sugar_alcohols"]:
            warnings.append({
                "type": "digestive",
                "severity": "low",
                "message": f"Contains sugar alcohols: "
                          f"{', '.join(sweetener_data['sugar_alcohols'])}",
                "recommendation": "May cause digestive discomfort in some individuals."
            })

        return warnings

    # =========================================================================
    # RDA/UL DATA COLLECTOR (for user profile scoring on device)
    # =========================================================================

    def _collect_rda_ul_data(self, product: Dict) -> Dict:
        """
        Collect RDA/UL reference data for user profile scoring (Section E).
        This data is sent to device for user-specific calculations.
        """
        rda_db = self.databases.get('rda_optimal_uls', {})
        nutrient_recs = rda_db.get('nutrient_recommendations', [])

        active_ingredients = product.get('activeIngredients', [])
        rda_data = []

        for ingredient in active_ingredients:
            ing_name = ingredient.get('name', '')
            std_name = ingredient.get('standardName', '') or ing_name
            quantity = ingredient.get('quantity', 0)
            unit = ingredient.get('unit', '')

            # Find matching RDA data
            for nutrient in nutrient_recs:
                nutrient_name = nutrient.get('standard_name', '')

                if self._normalize_text(std_name) == self._normalize_text(nutrient_name) or \
                   self._normalize_text(ing_name) == self._normalize_text(nutrient_name):

                    rda_data.append({
                        "ingredient": ing_name,
                        "standard_name": nutrient_name,
                        "quantity": quantity,
                        "unit": unit,
                        "nutrient_unit": nutrient.get('unit', ''),
                        "highest_ul": nutrient.get('highest_ul', 0),
                        "optimal_range": nutrient.get('optimal_range', ''),
                        "warnings": nutrient.get('warnings', []),
                        "data_by_group": nutrient.get('data', [])  # All age/sex data
                    })
                    break

        return {
            "ingredients_with_rda": rda_data,
            "count": len(rda_data)
        }

    # =========================================================================
    # MAIN ENRICHMENT METHOD
    # =========================================================================

    def enrich_product(self, product: Dict) -> Tuple[Dict, List[str]]:
        """
        Enrich a single product with all data needed for scoring.
        Returns: (enriched_product, issues_list)
        """
        product_id = product.get('dsld_id', product.get('id', 'unknown'))
        issues = []

        # Validate product structure before processing
        is_valid, validation_issues = self.validate_product(product)
        if not is_valid:
            issues.extend(validation_issues)
            self.logger.warning(
                "Product %s: Validation failed - %s", product_id, validation_issues
            )
            # Return product with empty schema placeholders for consistent output
            product.update(copy.deepcopy(self.EMPTY_ENRICHMENT_SCHEMA))
            product["enrichment_status"] = "validation_failed"
            product["enrichment_error"] = "; ".join(validation_issues)
            return product, issues

        try:
            # Start with all cleaned data
            enriched = dict(product)

            # Map DSLD field names to scoring-expected names for consistency
            if 'id' in enriched and 'dsld_id' not in enriched:
                enriched['dsld_id'] = enriched['id']
            if 'fullName' in enriched and 'product_name' not in enriched:
                enriched['product_name'] = enriched['fullName']

            # Add enrichment metadata
            enriched["enrichment_version"] = self.VERSION
            enriched["compatible_scoring_versions"] = self.COMPATIBLE_SCORING_VERSIONS
            enriched["enriched_date"] = datetime.utcnow().isoformat() + "Z"
            enriched["reference_versions"] = self.reference_versions  # Track data file versions for auditability

            # Classify supplement type (determines scoring adjustments)
            enriched["supplement_type"] = self._classify_supplement_type(product)

            # Section A: Ingredient Quality
            enriched["ingredient_quality_data"] = self._collect_ingredient_quality_data(product)
            enriched["delivery_data"] = self._collect_delivery_data(product)
            enriched["absorption_data"] = self._collect_absorption_data(product)
            enriched["formulation_data"] = self._collect_formulation_data(product)

            # Section B: Safety & Purity
            # Collect contaminant_data once, pass to compliance to avoid double-collection
            contaminant_data = self._collect_contaminant_data(product)
            enriched["contaminant_data"] = contaminant_data
            enriched["compliance_data"] = self._collect_compliance_data(
                product, contaminant_data=contaminant_data
            )
            enriched["certification_data"] = self._collect_certification_data(product)
            enriched["proprietary_data"] = self._collect_proprietary_data(product)

            # Section C: Evidence & Research
            enriched["evidence_data"] = self._collect_evidence_data(product)

            # Section D: Brand Trust
            manufacturer_data = self._collect_manufacturer_data(product)
            enriched["manufacturer_data"] = manufacturer_data

            # P1.3: Add manufacturer_normalized at top-level for stable matching
            manufacturer_raw = manufacturer_data.get('manufacturer', '') or manufacturer_data.get('brand_name', '')
            enriched["manufacturer_normalized"] = self._normalize_company_name(manufacturer_raw)

            # Section E: User Profile Data (for device-side scoring)
            enriched["rda_ul_data"] = self._collect_rda_ul_data(product)

            # Probiotic-specific data
            enriched["probiotic_data"] = self._collect_probiotic_data(product)

            # Dietary sensitivity data (sugar/sodium for diabetes/hypertension users)
            enriched["dietary_sensitivity_data"] = self._collect_dietary_sensitivity_data(product)

            # P0.4: Serving basis and form factor for deterministic prescore
            serving_data = self._collect_serving_basis_data(product)
            enriched["serving_basis"] = serving_data["serving_basis"]
            enriched["form_factor"] = serving_data["form_factor"]

            # Enrichment metadata (version lock for scoring compatibility)
            enriched["enrichment_metadata"] = {
                "enrichment_version": self.VERSION,
                "scoring_compatibility": self.COMPATIBLE_SCORING_VERSIONS,
                "generated_by": "SupplementEnricherV3",
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "data_completeness": self._calculate_completeness(enriched),
                "ready_for_scoring": True,
                "unmapped_active_count": enriched["ingredient_quality_data"]["unmapped_count"]
            }

            return enriched, issues

        except (KeyError, TypeError) as e:
            # Data structure issues - log and continue
            self.logger.error(f"Product {product_id}: Data structure error: {e}")
            issues.append(f"Data structure error: {str(e)}")
            product["enrichment_status"] = "failed"
            product["enrichment_error"] = f"Data structure error: {str(e)}"
            return product, issues
        except (ValueError, AttributeError) as e:
            # Value/attribute issues - log and continue
            self.logger.error(f"Product {product_id}: Value error: {e}")
            issues.append(f"Value error: {str(e)}")
            product["enrichment_status"] = "failed"
            product["enrichment_error"] = f"Value error: {str(e)}"
            return product, issues
        except Exception as e:
            # Unexpected error - log with traceback for debugging, but don't crash batch
            self.logger.error(f"Product {product_id}: Unexpected enrichment error: {e}", exc_info=True)
            issues.append(f"Enrichment error: {str(e)}")

            # Return product with minimal enrichment
            product["enrichment_version"] = self.VERSION
            product["enriched_date"] = datetime.utcnow().isoformat() + "Z"
            product["enrichment_status"] = "failed"
            product["enrichment_error"] = str(e)

            return product, issues

    def _calculate_completeness(self, enriched: Dict) -> float:
        """Calculate data completeness percentage"""
        checks = [
            enriched.get("ingredient_quality_data", {}).get("total_active", 0) > 0,
            enriched.get("supplement_type", {}).get("type") != "unknown",
            enriched.get("manufacturer_data", {}).get("brand_name", "") != "",
            enriched.get("certification_data") is not None,
            enriched.get("contaminant_data") is not None
        ]

        return (sum(checks) / len(checks)) * 100

    def _track_unmapped(self, ingredient_name: str, ing_type: str):
        """Track unmapped ingredients for reporting"""
        key = f"{ing_type}:{ingredient_name}"
        self.unmapped_tracker[key] = self.unmapped_tracker.get(key, 0) + 1

    # =========================================================================
    # BATCH PROCESSING
    # =========================================================================

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
            issues_count = 0

            # Check if progress bar should be shown
            show_progress = self.config.get("ui", {}).get("show_progress_bar", True)

            iterator = products
            if show_progress and len(products) > 10 and TQDM_AVAILABLE:
                iterator = tqdm(products, desc="Enriching", unit="product")

            for product in iterator:
                enriched, issues = self.enrich_product(product)
                enriched_products.append(enriched)
                if issues:
                    issues_count += 1

            # Save outputs
            base_name = os.path.splitext(os.path.basename(input_file))[0]

            enriched_dir = os.path.join(output_dir, "enriched")
            os.makedirs(enriched_dir, exist_ok=True)

            output_file = os.path.join(enriched_dir, f"enriched_{base_name}.json")

            # Atomic write: prevents partial files on crash
            self._atomic_write_json(output_file, enriched_products)

            self.logger.info(f"Saved {len(enriched_products)} enriched products to {output_file}")

            # Calculate real success rate based on enrichment_status
            failed_count = sum(
                1 for p in enriched_products
                if p.get('enrichment_status') in ('failed', 'validation_failed')
            )
            successful_count = len(enriched_products) - failed_count
            success_rate = (
                (successful_count / len(enriched_products) * 100)
                if enriched_products else 0
            )

            return {
                "total_products": len(products),
                "successful": successful_count,
                "failed": failed_count,
                "with_issues": issues_count,
                "success_rate": round(success_rate, 1)
            }

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in batch {input_file}: {e}")
            self._write_quarantine(output_dir, input_file, "JSONDecodeError", str(e), "load")
            raise
        except PermissionError as e:
            self.logger.error(f"Permission denied for batch {input_file}: {e}")
            self._write_quarantine(output_dir, input_file, "PermissionError", str(e), "load")
            raise
        except (IOError, OSError) as e:
            self.logger.error(f"I/O error processing batch {input_file}: {e}")
            self._write_quarantine(output_dir, input_file, "IOError", str(e), "load")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error processing batch {input_file}: {e}", exc_info=True)
            self._write_quarantine(
                output_dir, input_file, type(e).__name__, str(e),
                "enrichment", traceback.format_exc()
            )
            raise

    def process_all(self, input_path: str, output_dir: str) -> Dict:
        """Process all files in input path"""
        script_dir = Path(__file__).parent

        # Handle relative paths
        if not os.path.isabs(input_path):
            input_path = script_dir / input_path
        if not os.path.isabs(output_dir):
            output_dir = script_dir / output_dir

        # Get input files
        input_files = []
        if os.path.isfile(input_path):
            input_files = [str(input_path)]
        elif os.path.isdir(input_path):
            input_files = [
                os.path.join(input_path, f)
                for f in os.listdir(input_path)
                if f.endswith('.json')
            ]
        else:
            raise FileNotFoundError(f"Input path not found: {input_path}")

        # Sort for deterministic processing order (reproducible runs)
        input_files.sort()

        if not input_files:
            raise ValueError(f"No JSON files found in: {input_path}")

        self.logger.info(f"Found {len(input_files)} files to process")

        # Process all files
        start_time = datetime.utcnow()
        total_stats = {
            "total_products": 0,
            "successful": 0,
            "with_issues": 0
        }

        for input_file in input_files:
            self.logger.info(f"Processing: {os.path.basename(input_file)}")
            batch_stats = self.process_batch(input_file, str(output_dir))

            for key in total_stats:
                total_stats[key] += batch_stats.get(key, 0)

        # Generate summary
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        summary = {
            "processing_info": {
                "version": self.VERSION,
                "files_processed": len(input_files),
                "duration_seconds": round(duration, 2),
                "timestamp": end_time.isoformat() + "Z"
            },
            "stats": total_stats,
            "unmapped_ingredients": dict(self.unmapped_tracker)
        }

        # Save summary
        reports_dir = os.path.join(output_dir, "reports")
        os.makedirs(reports_dir, exist_ok=True)

        summary_file = os.path.join(reports_dir, f"enrichment_summary_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")

        # Atomic write: prevents partial files on crash
        self._atomic_write_json(summary_file, summary)

        self.logger.info("=" * 50)
        self.logger.info("ENRICHMENT COMPLETE")
        self.logger.info(f"Total products: {total_stats['total_products']}")
        self.logger.info(f"Duration: {duration:.2f}s")
        self.logger.info(f"Summary saved: {summary_file}")
        self.logger.info("=" * 50)

        return summary

def _verify_working_directory(config_path: str) -> None:
    """
    Verify that relative paths in config will resolve correctly from CWD.
    Prevents loading empty DBs and producing garbage enrichment.
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return  # Config errors handled later by SupplementEnricherV3

    db_paths = config.get("database_paths", {})
    if db_paths:
        first_db_path = next(iter(db_paths.values()), None)
        if first_db_path and not os.path.isabs(first_db_path):
            db_dir = os.path.dirname(first_db_path)
            if db_dir and not os.path.exists(db_dir):
                print("\n❌ WORKING DIRECTORY ERROR", file=sys.stderr)
                print(f"   Current directory: {os.getcwd()}", file=sys.stderr)
                print(f"   Expected '{db_dir}/' does not exist here.", file=sys.stderr)
                print("\n   Solution: cd to scripts/ and run again.\n", file=sys.stderr)
                sys.exit(1)



def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='DSLD Supplement Enrichment System v3.0.0',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python enrich_supplements_v3.py
    python enrich_supplements_v3.py --config config/enrichment_config.json
    python enrich_supplements_v3.py --input-dir cleaned_data --output-dir enriched_output
    python enrich_supplements_v3.py --dry-run
        """
    )

    parser.add_argument('--config', default='config/enrichment_config.json',
                        help='Configuration file path')
    parser.add_argument('--input-dir', help='Input directory (overrides config)')
    parser.add_argument('--output-dir', help='Output directory (overrides config)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Test run without writing files')

    args = parser.parse_args()

    # GUARD: Verify working directory before anything else
    _verify_working_directory(args.config)

    try:
        # Initialize enricher
        enricher = SupplementEnricherV3(args.config)

        # Determine paths
        if args.input_dir and args.output_dir:
            input_path = args.input_dir
            output_dir = args.output_dir
        else:
            paths = enricher.config.get('paths', {})
            input_path = paths.get('input_directory', 'output_Lozenges/cleaned')
            output_dir = paths.get('output_directory', 'output_Lozenges_enriched')

        if args.dry_run:
            enricher.logger.info("DRY RUN MODE")
            enricher.logger.info(f"Would process files from: {input_path}")
            enricher.logger.info(f"Would output to: {output_dir}")
            return

        # Process all files
        enricher.process_all(input_path, output_dir)

    except FileNotFoundError as e:
        logging.error(f"File or directory not found: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON file: {e}")
        sys.exit(1)
    except PermissionError as e:
        logging.error(f"Permission denied: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logging.info("Processing interrupted by user")
        sys.exit(130)
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
