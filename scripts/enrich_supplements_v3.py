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
import fnmatch
import json
import os
import sys
import re
import math
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
    LOG_DATE_FORMAT,
    CERT_CLAIM_RULES,
    UNIT_CONVERSIONS_DB,
    # Scorable ingredient classification constants
    NON_THERAPEUTIC_PARENT_DENYLIST,
    ADDITIVE_TYPES_SKIP_SCORING,
    BLEND_HEADER_PATTERNS_HIGH_CONFIDENCE,
    BLEND_HEADER_EXACT_NAMES,
    BLEND_HEADER_PATTERNS_LOW_CONFIDENCE,
    EXCIPIENT_NEVER_PROMOTE,
    POTENCY_MARKERS_HIGH_SIGNAL,
    POTENCY_MARKERS_LOW_SIGNAL,
    PSEUDO_UNITS_INVALID,
    ABSORPTION_ENHANCERS_PROMOTE_EXCEPTION,
    SERVING_UNIT_NORMALIZATION_MAP,
    SKIP_REASON_ADDITIVE,
    SKIP_REASON_ADDITIVE_TYPE,
    SKIP_REASON_NESTED_NON_THERAPEUTIC,
    SKIP_REASON_BLEND_HEADER_NO_DOSE,
    SKIP_REASON_BLEND_HEADER_WITH_WEIGHT,
    SKIP_REASON_RECOGNIZED_NON_SCORABLE,
    SKIP_REASON_LABEL_PHRASE,
    SKIP_REASON_NUTRITION_FACT,
    EXCLUDED_LABEL_PHRASES,
    EXCLUDED_NUTRITION_FACTS,
    PROMOTE_REASON_KNOWN_DB,
    PROMOTE_REASON_HAS_DOSE,
    PROMOTE_REASON_PRODUCT_TYPE_RESCUE,
    PROMOTE_REASON_ABSORPTION_ENHANCER,
)

# Import scoring hardening modules
from unit_converter import UnitConverter, ConversionResult
from dosage_normalizer import DosageNormalizer, DosageNormalizationResult
from proprietary_blend_detector import ProprietaryBlendDetector, BlendAnalysisResult
from rda_ul_calculator import RDAULCalculator, NutrientAdequacyResult
import normalization as norm_module  # Single-source normalization
from match_ledger import (
    MatchLedgerBuilder,
    DOMAIN_INGREDIENTS,
    DOMAIN_ADDITIVES,
    DOMAIN_ALLERGENS,
    DOMAIN_MANUFACTURER,
    DOMAIN_DELIVERY,
    DOMAIN_CLAIMS,
    METHOD_EXACT,
    METHOD_NORMALIZED,
    METHOD_PATTERN,
    METHOD_CONTAINS,
    METHOD_FUZZY,
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
    # Allowlist/denylist patterns for banned matching are loaded from config.

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
            # Schema version
            'quality_data_schema_version': 2,
            # Legacy fields (kept for backward compatibility)
            'ingredients': [], 'premium_form_count': 0, 'unmapped_count': 0,
            'total_active': 0,
            # New two-pass classification fields
            'ingredients_scorable': [],
            'ingredients_skipped': [],
            'unmapped_scorable_count': 0,
            'total_scorable_active_count': 0,
            'skipped_non_scorable_count': 0,
            'skipped_reasons_breakdown': {},
            'promoted_from_inactive': [],
            'blend_only_product': False,
            # Coverage metrics with leak detection
            'total_records_seen': 0,
            'total_ingredients_evaluated': 0,
            'unevaluated_records': 0,
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
        'interaction_profile': {
            'ingredient_alerts': [],
            'condition_summary': {},
            'drug_class_summary': {},
            'highest_severity': None,
            'data_sources': [],
            'rules_version': None,
            'taxonomy_version': None,
            'user_condition_alerts': {
                'enabled': False,
                'conditions_checked': [],
                'drug_classes_checked': [],
                'alerts': [],
                'highest_severity': None
            }
        },
        'user_condition_alerts': {
            'enabled': False,
            'conditions_checked': [],
            'drug_classes_checked': [],
            'alerts': [],
            'highest_severity': None
        },
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
        self._apply_logging_config()
        self.company_fuzzy_threshold = self._resolve_company_fuzzy_threshold()
        # Per-product ephemeral cache for repeated text aggregation hot path.
        self._product_text_cache_enabled = False
        self._product_text_cache: Dict[int, str] = {}
        self._product_text_lower_cache: Dict[int, str] = {}
        # Per-quality-map cache: normalized context term -> preferred parent key.
        self._quality_parent_context_index_cache: Dict[int, Dict[str, str]] = {}
        self.databases = {}
        self._load_all_databases()
        self._compile_patterns()

        # ── Performance indexes (built once, used per-ingredient) ──
        # IQM alias indexes for O(1) lookups instead of O(n) parent scans
        self._iqm_exact_index: Dict[str, List] = {}  # exact_norm → [(parent_key, form_key|None, alias_text, priority, match_mode)]
        self._iqm_norm_index: Dict[str, List] = {}   # normalized → [(parent_key, form_key|None, alias_text, priority, match_mode)]
        # Non-scorable DB index for O(1) recognition lookups
        self._nonscorable_index: Dict[str, Dict] = {}  # normalized_variant → result_dict
        self._build_performance_indexes()

        # Track unmapped ingredients across batch
        self.unmapped_tracker = {}
        self.match_counters = {
            "pattern_match_wins_count": 0,
            "contains_match_wins_count": 0,
            "parent_fallback_count": 0
        }
        # Track unmapped forms for database expansion
        # Key: raw_form_text, Value: {count, examples, base_names}
        self.unmapped_forms_tracker = {}
        self._rda_ul_warning_count = 0
        self._ambiguity_warning_count = 0
        self._parent_fallback_info_count = 0
        self._parent_fallback_details = []  # Collect ALL fallback details for report
        self._form_fallback_details = []   # Collect FORM_UNMAPPED_FALLBACK details for audit

        # Initialize scoring hardening modules
        self._init_scoring_modules()

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format=LOG_FORMAT,
            datefmt=LOG_DATE_FORMAT,
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        return logging.getLogger(__name__)

    def _init_scoring_modules(self):
        """Initialize scoring hardening modules for evidence collection."""
        try:
            # Unit converter for dosage normalization
            self.unit_converter = UnitConverter()
            self.logger.info("UnitConverter initialized")

            # Dosage normalizer for serving basis
            self.dosage_normalizer = DosageNormalizer(self.unit_converter)
            self.logger.info("DosageNormalizer initialized")

            # Proprietary blend detector
            self.blend_detector = ProprietaryBlendDetector()
            self.logger.info("ProprietaryBlendDetector initialized")

            # RDA/UL calculator
            self.rda_calculator = RDAULCalculator()
            self.logger.info("RDAULCalculator initialized")

        except Exception as e:
            self.logger.warning(
                f"Failed to initialize scoring modules: {e}. "
                "Evidence collection will use fallback methods."
            )
            self.unit_converter = None
            self.dosage_normalizer = None
            self.blend_detector = None
            self.rda_calculator = None

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

    def _resolve_company_fuzzy_threshold(self) -> float:
        """Resolve company fuzzy threshold from config, normalizing to 0-1."""
        raw_threshold = self.config.get("processing_config", {}).get("fuzzy_threshold", 90)
        try:
            threshold = float(raw_threshold)
        except (TypeError, ValueError):
            self.logger.warning(
                "Invalid processing_config.fuzzy_threshold=%r; defaulting to 90",
                raw_threshold,
            )
            threshold = 90.0

        if threshold > 1.0:
            threshold = threshold / 100.0

        if threshold < 0.0 or threshold > 1.0:
            self.logger.warning(
                "Out-of-range fuzzy threshold %.3f; defaulting to 0.90", threshold
            )
            return 0.90

        return threshold

    def _apply_logging_config(self) -> None:
        """Apply config-driven logging level controls."""
        processing_cfg = self.config.get("processing_config", {})
        if not processing_cfg.get("enable_logging", True):
            self.logger.setLevel(logging.CRITICAL)
            return

        level_name = str(processing_cfg.get("log_level", "INFO")).upper()
        level = getattr(logging, level_name, logging.INFO)
        self.logger.setLevel(level)

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
                "max_workers": 4,
                "collect_rda_ul_data": True
            },
            "validation": {
                "strict_db_validation": False,
                "_strict_db_validation_note": "Set True in CI to fail-fast on DB key violations"
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
                "banned_match_allowlist": "data/banned_match_allowlist.json",
                "harmful_additives": "data/harmful_additives.json",
                "allergens": "data/allergens.json",
                "backed_clinical_studies": "data/backed_clinical_studies.json",
                "top_manufacturers_data": "data/top_manufacturers_data.json",
                "manufacturer_violations": "data/manufacturer_violations.json",
                "rda_optimal_uls": "data/rda_optimal_uls.json",
                "clinically_relevant_strains": "data/clinically_relevant_strains.json",
                "color_indicators": "data/color_indicators.json",
                "cert_claim_rules": "data/cert_claim_rules.json",
                # Tiered matching: other_ingredients for recognized-but-non-scorable
                "other_ingredients": "data/other_ingredients.json",
                "percentile_categories": "data/percentile_categories.json",
                "clinical_risk_taxonomy": "data/clinical_risk_taxonomy.json",
                "ingredient_interaction_rules": "data/ingredient_interaction_rules.json",
            }

        # Add clinically_relevant_strains if not present
        if "clinically_relevant_strains" not in db_paths:
            db_paths["clinically_relevant_strains"] = "data/clinically_relevant_strains.json"
        if "banned_match_allowlist" not in db_paths:
            db_paths["banned_match_allowlist"] = "data/banned_match_allowlist.json"

        # Define critical databases that must exist
        critical_dbs = {
            "ingredient_quality_map", "harmful_additives",
            "allergens", "banned_recalled_ingredients", "color_indicators"
        }

        script_dir = Path(__file__).parent
        missing_critical = []

        def _db_entry_count(payload: Any) -> int:
            """Return a meaningful entry count for mixed JSON schemas."""
            if isinstance(payload, list):
                return len(payload)
            if isinstance(payload, dict):
                preferred_list_keys = (
                    "ingredients",
                    "allergens",
                    "common_allergens",
                    "harmful_additives",
                    "absorption_enhancers",
                    "botanical_ingredients",
                    "other_ingredients",
                    "nutrient_recommendations",
                    "therapeutic_dosing",
                    "standardized_botanicals",
                    "synergy_clusters",
                    "top_manufacturers",
                    "manufacturer_violations",
                    "proprietary_blend_concerns",
                    "clinically_relevant_strains",
                    "backed_clinical_studies",
                    "studies",
                    "manufacturers",
                    "allowlist",
                    "denylist",
                    "entries",
                    "interaction_rules",
                    "conditions",
                    "drug_classes",
                )
                for key in preferred_list_keys:
                    value = payload.get(key)
                    if isinstance(value, list):
                        return len(value)
                return len(payload)
            return 0

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
                    self.logger.info(f"Loaded {db_name}: {_db_entry_count(self.databases[db_name])} entries")
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
            "cert_claim_rules",  # Required for evidence-based claims detection
            "banned_match_allowlist",
            "percentile_categories",
            "clinical_risk_taxonomy",
            "ingredient_interaction_rules",
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

        # Validate snake_case key convention for ingredient_quality_map
        quality_map = self.databases.get('ingredient_quality_map', {})
        self._validate_snake_case_keys(quality_map, 'ingredient_quality_map')
        self._validate_banned_match_allowlist()

        # Special validation for cert_claim_rules - claims hardening depends on it
        cert_rules = self.databases.get('cert_claim_rules', {})
        if not cert_rules or len(cert_rules) == 0:
            self.logger.warning(
                "CLAIMS HARDENING DISABLED: cert_claim_rules database is empty or missing. "
                "Evidence-based claim detection will not produce results. "
                "Add 'cert_claim_rules' to database_paths in enrichment_config.json"
            )
        elif 'third_party_programs' not in cert_rules.get('rules', {}):
            self.logger.warning(
                "CLAIMS HARDENING INCOMPLETE: cert_claim_rules missing third_party_programs. "
                "Certification evidence will not be collected."
            )

    def _log_reference_versions(self):
        """Log versions of reference databases for auditability."""
        self.reference_versions = {}

        # Track color_indicators version
        color_db = self.databases.get('color_indicators', {})
        db_info = color_db.get('_metadata', {})
        if db_info:
            version = db_info.get('schema_version', db_info.get('version', 'unknown'))
            last_updated = db_info.get('last_updated', 'unknown')
            self.reference_versions['color_indicators'] = {
                'version': version,
                'last_updated': last_updated
            }
            self.logger.info(
                f"Reference data: color_indicators v{version} (updated: {last_updated})"
            )

        # Track cert_claim_rules version
        cert_rules_db = self.databases.get('cert_claim_rules', {})
        cert_db_info = cert_rules_db.get('_metadata', {})
        if cert_db_info:
            version = cert_db_info.get('schema_version', cert_db_info.get('version', 'unknown'))
            last_updated = cert_db_info.get('last_updated', 'unknown')
            self.reference_versions['cert_claim_rules'] = {
                'version': version,
                'last_updated': last_updated
            }
            self.logger.info(
                f"Reference data: cert_claim_rules v{version} (updated: {last_updated})"
            )

        # Track other versioned databases
        versioned_dbs = [
            'harmful_additives', 'allergens', 'ingredient_quality_map', 'banned_match_allowlist',
            'percentile_categories', 'clinical_risk_taxonomy', 'ingredient_interaction_rules'
        ]
        for db_name in versioned_dbs:
            db = self.databases.get(db_name, {})
            db_info = db.get('_metadata', {})
            if db_info:
                version = db_info.get('version', db_info.get('schema_version', 'unknown'))
                self.reference_versions[db_name] = {'version': version}

    def _validate_banned_match_allowlist(self):
        """
        Validate banned match allowlist/denylist against banned catalog.

        Enforces:
        - Each entry must reference a canonical banned id.
        - Canonical id must exist in banned_recalled_ingredients.
        """
        allowlist_db = self.databases.get('banned_match_allowlist', {}) or {}
        if not allowlist_db:
            return

        banned_db = self.databases.get('banned_recalled_ingredients', {}) or {}
        banned_ids = set()
        for section_data in banned_db.values():
            if isinstance(section_data, list):
                for item in section_data:
                    if isinstance(item, dict) and item.get('id'):
                        banned_ids.add(item['id'])

        errors = []
        for section_key in ('allowlist', 'denylist'):
            for entry in allowlist_db.get(section_key, []) or []:
                entry_id = entry.get('id', 'unknown')
                canonical_id = entry.get('canonical_id')
                if not canonical_id:
                    errors.append(f"{section_key}:{entry_id} missing canonical_id")
                elif canonical_id not in banned_ids:
                    errors.append(
                        f"{section_key}:{entry_id} canonical_id not found: {canonical_id}"
                    )

        if errors:
            message = (
                "BANNED_MATCH_ALLOWLIST validation errors:\n  - " +
                "\n  - ".join(errors)
            )
            strict = self.config.get('validation', {}).get('strict_db_validation', False)
            if strict:
                raise ValueError(message)
            self.logger.warning(message)

    def _validate_snake_case_keys(self, db: Dict, db_name: str):
        """
        Validate database keys follow snake_case convention.

        Enforces:
        - No spaces in keys (use underscores)
        - No duplicate keys (case-insensitive)
        - In strict mode (CI): raises ValueError on violations
        - In normal mode: logs errors for visibility
        """
        if not db:
            return

        # Check if strict validation is enabled (default: False)
        strict_mode = self.config.get('validation', {}).get('strict_db_validation', False)

        invalid_keys = []
        seen_normalized = {}  # normalized_key -> original_key

        for key in db.keys():
            # Skip metadata keys
            if key.startswith('_'):
                continue

            # Check for spaces (should use underscores)
            if ' ' in key:
                invalid_keys.append((key, "contains spaces"))

            # Check for case-insensitive duplicates
            normalized = key.lower().replace(' ', '_')
            if normalized in seen_normalized:
                self.logger.warning(
                    f"{db_name}: Possible duplicate key detected: "
                    f"'{key}' and '{seen_normalized[normalized]}' normalize to same value"
                )
            seen_normalized[normalized] = key

        if invalid_keys:
            violations = "; ".join([f"'{k}' ({reason})" for k, reason in invalid_keys])
            error_msg = (
                f"{db_name}: Key naming convention violations detected: {violations}. "
                f"Keys must use snake_case (underscores, not spaces)."
            )

            if strict_mode:
                # Fail-fast in CI/strict mode
                raise ValueError(error_msg)
            else:
                # Log error for visibility in normal mode
                self.logger.error(error_msg)

    def _build_performance_indexes(self):
        """
        Build O(1) lookup indexes for IQM and non-scorable databases.

        Called once at init. Converts the O(n) linear scans in
        _match_quality_map() and _is_recognized_non_scorable() into
        O(1) dict lookups, giving ~5-10x speedup on matching.
        """
        import time
        t0 = time.monotonic()

        quality_map = self.databases.get('ingredient_quality_map', {})

        # ── IQM indexes: alias → [(parent_key, form_key|None, alias_text, priority, match_mode)] ──
        exact_idx: Dict[str, list] = {}
        norm_idx: Dict[str, list] = {}

        for parent_key, parent_data in quality_map.items():
            if parent_key.startswith("_") or not isinstance(parent_data, dict):
                continue

            match_rules = parent_data.get('match_rules', {})
            priority = match_rules.get('priority', 1)
            match_mode = match_rules.get('match_mode', 'alias_and_fuzzy')

            parent_std = parent_data.get('standard_name', parent_key)
            parent_aliases = parent_data.get('aliases', []) or []

            # Index parent-level names
            for alias_text in [parent_std] + list(parent_aliases):
                if not alias_text:
                    continue
                exact_norm = norm_module.normalize_exact_text(alias_text)
                if exact_norm:
                    exact_idx.setdefault(exact_norm, []).append(
                        (parent_key, None, alias_text, priority, match_mode)
                    )
                text_norm = norm_module.normalize_text(alias_text)
                if text_norm:
                    norm_idx.setdefault(text_norm, []).append(
                        (parent_key, None, alias_text, priority, match_mode)
                    )

            # Index form-level names
            forms = parent_data.get('forms', {})
            for form_name, form_data in forms.items():
                if not isinstance(form_data, dict):
                    continue
                form_aliases = form_data.get('aliases', []) or []
                for alias_text in [form_name] + list(form_aliases):
                    if not alias_text:
                        continue
                    exact_norm = norm_module.normalize_exact_text(alias_text)
                    if exact_norm:
                        exact_idx.setdefault(exact_norm, []).append(
                            (parent_key, form_name, alias_text, priority, match_mode)
                        )
                    text_norm = norm_module.normalize_text(alias_text)
                    if text_norm:
                        norm_idx.setdefault(text_norm, []).append(
                            (parent_key, form_name, alias_text, priority, match_mode)
                        )

        self._iqm_exact_index = exact_idx
        self._iqm_norm_index = norm_idx

        # ── Non-scorable DB index: normalized_name → result dict ──
        nonscorable_idx: Dict[str, Dict] = {}

        db_configs = [
            ('other_ingredients', 'other_ingredients', 'non_scorable',
             lambda e: e.get('category', 'other_ingredient')),
            ('harmful_additives', 'harmful_additives', 'non_scorable',
             lambda e: 'known_additive'),
            ('botanical_ingredients', 'botanical_ingredients', 'botanical_unscored',
             lambda e: e.get('category', 'botanical')),
            ('standardized_botanicals', 'standardized_botanicals', 'botanical_unscored',
             lambda e: 'botanical_identity'),
        ]

        for db_key, list_key, rec_type, reason_fn in db_configs:
            db = self.databases.get(db_key, {})
            entries = db.get(list_key, []) if isinstance(db, dict) else []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                result = {
                    "recognition_source": db_key,
                    "recognition_reason": reason_fn(entry),
                    "matched_entry_id": entry.get('id'),
                    "matched_entry_name": entry.get('standard_name'),
                    "recognition_type": rec_type,
                }
                # Index standard_name and all aliases
                for name_text in [entry.get('standard_name', '')] + (entry.get('aliases', []) or []):
                    if not name_text:
                        continue
                    text_norm = norm_module.normalize_text(name_text)
                    if text_norm and text_norm not in nonscorable_idx:
                        nonscorable_idx[text_norm] = result

        # Index banned_recalled_ingredients separately (different structure)
        banned_db = self.databases.get('banned_recalled_ingredients', {})
        banned_list = banned_db.get('ingredients', []) if isinstance(banned_db, dict) else []
        for entry in banned_list:
            if not isinstance(entry, dict):
                continue
            entity_type = entry.get('entity_type', 'ingredient')
            if entity_type not in {'ingredient', 'contaminant', None, ''}:
                continue
            result = {
                "recognition_source": "banned_recalled_ingredients",
                "recognition_reason": "banned",
                "matched_entry_id": entry.get('id'),
                "matched_entry_name": entry.get('standard_name'),
                "recognition_type": "non_scorable",
            }
            for name_text in [entry.get('standard_name', '')] + (entry.get('aliases', []) or []):
                if not name_text:
                    continue
                text_norm = norm_module.normalize_text(name_text)
                if text_norm and text_norm not in nonscorable_idx:
                    nonscorable_idx[text_norm] = result

        self._nonscorable_index = nonscorable_idx

        elapsed = time.monotonic() - t0
        self.logger.info(
            f"Performance indexes built in {elapsed:.2f}s: "
            f"IQM exact={len(exact_idx)} norm={len(norm_idx)} entries, "
            f"non-scorable={len(nonscorable_idx)} entries"
        )

    def _compile_patterns(self):
        """Compile regex patterns for performance"""
        self.compiled_patterns = {
            # Organic certification patterns
            'usda_organic': re.compile(r'\bUSDA[\s-]*Organic\b', re.I),
            'certified_organic': re.compile(r'\bcertified[\s-]+organic\b', re.I),
            'organic_100': re.compile(r'\b100(?:%|\s*percent)?[\s-]*organic\b', re.I),
            'made_with_organic': re.compile(r'\bmade[\s-]+with[\s-]+organic[\s-]+ingredients?\b', re.I),

            # GMP patterns
            'gmp': re.compile(r'\b(c?GMP|GMP)[\s-]*(certified|compliant|registered|facility)?\b', re.I),
            'nsf_gmp': re.compile(r'\bNSF[\s-]*GMP\b', re.I),
            'fda_registered': re.compile(r'\bFDA[\s-]?(registered|inspected)[\s-]+facility\b', re.I),

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
        """
        Normalize text for matching.

        Delegates to normalization module for consistent behavior across pipeline.

        Handles:
        - Case normalization (lowercase)
        - Greek beta (β): Only in known supplement compounds
        - Micro sign (µ): Only before gram units (µg → mcg)
        - Em-dashes, en-dashes → regular hyphen
        - Numeric slashes (1/2 → 1 2)
        - Commas, middle dots → space
        - Trademark/copyright symbols removed
        - Whitespace collapsed
        """
        return norm_module.normalize_text(text)

    def _normalize_exact_text(self, text: str) -> str:
        """
        Minimal normalization for exact matching.
        Only lowercase and trim to preserve punctuation and symbols.

        Delegates to normalization module for consistency.
        """
        return norm_module.normalize_exact_text(text)

    def _normalize_company_name(self, name: str) -> str:
        """
        Normalize company name for matching.
        Removes common suffixes like LLC, Inc, Corp, etc.

        Delegates to normalization module for consistency.
        """
        return norm_module.normalize_company_name(name)

    def _extract_form_from_label(self, label: str) -> Dict[str, Any]:
        """
        Extract base ingredient name and form specifications from complex labels.

        Handles patterns like:
        - "Vitamin A (as retinyl palmitate and 50% B-carotene)"
        - "Vitamin C (as ascorbic acid)"
        - "Vitamin D (as AlgeD3® cholecalciferol [D3] from algae)"
        - "Vitamin B6 (as pyridoxal 5'-phosphate monohydrate [P-5-P])"
        - "Vitamin B12 (as adenosylcobalamin and methylcobalamin)"

        Returns dict with:
        - original: The original label text (immutable)
        - base_name: The ingredient name before parentheses (e.g., "Vitamin A")
        - extracted_forms: List of form info dicts with:
            - raw_form_text: exact extracted string (immutable)
            - match_candidates: list of strings to try for matching (includes bracket tokens)
            - display_form: human-readable cleaned version
            - percent_share: float or None (e.g., 0.50 for "50%")
        - is_dual_form: True if multiple forms detected
        - form_extraction_success: True if any forms were extracted
        - has_form_evidence: True if label has "(as ...)" or bracket forms (mapping should not downgrade to unspecified)
        """
        result = {
            'original': label,
            'base_name': None,
            'extracted_forms': [],
            'is_dual_form': False,
            'form_extraction_success': False,
            'has_form_evidence': False
        }

        if not label:
            return result

        # Extract base name (before parentheses or brackets)
        base_match = re.match(r'^([^(\[]+)', label)
        if base_match:
            result['base_name'] = base_match.group(1).strip()

        # Check for form evidence patterns
        has_as_pattern = bool(re.search(r'\(as\s+', label, re.IGNORECASE))
        has_bracket_form = bool(re.search(r'\[[A-Z0-9\-]+\]', label))
        result['has_form_evidence'] = has_as_pattern or has_bracket_form

        # Extract bracket tokens BEFORE cleaning (these are valuable match candidates)
        bracket_tokens = re.findall(r'\[([^\]]+)\]', label)
        # Filter out vitamin identity brackets like "[Vitamin B1]"
        form_bracket_tokens = [
            t for t in bracket_tokens
            if not re.match(r'^Vitamin\s+[A-Z]\d*$', t, re.IGNORECASE)
        ]

        # Extract '(as ...)' form specification - common pattern
        as_match = re.search(r'\(as\s+(.+?)\)(?:\s*$|\s*,|\s*\[)', label, re.IGNORECASE)
        if not as_match:
            # Try without trailing boundary
            as_match = re.search(r'\(as\s+(.+)\)', label, re.IGNORECASE)

        if as_match:
            form_text = as_match.group(1).strip()

            # Check for dual forms (e.g., "retinyl palmitate and 50% B-carotene")
            if ' and ' in form_text.lower():
                result['is_dual_form'] = True
                parts = re.split(r'\s+and\s+', form_text, flags=re.IGNORECASE)
                total_explicit_percent = 0.0
                forms_with_percent = []

                for part in parts:
                    form_info = self._parse_single_form(part, form_bracket_tokens)
                    if form_info:
                        forms_with_percent.append(form_info)
                        if form_info['percent_share'] is not None:
                            total_explicit_percent += form_info['percent_share']

                # Distribute remaining percentage if needed
                if forms_with_percent:
                    forms_without_percent = [f for f in forms_with_percent if f['percent_share'] is None]
                    if forms_without_percent and total_explicit_percent < 1.0:
                        remaining = 1.0 - total_explicit_percent
                        # Check for weird percentages
                        if total_explicit_percent > 1.0:
                            # Fallback to equal weight and log
                            self.logger.warning(
                                f"Percentage sum > 100% in label '{label}', using equal weight"
                            )
                            equal_share = 1.0 / len(forms_with_percent)
                            for f in forms_with_percent:
                                f['percent_share'] = equal_share
                        else:
                            per_form = remaining / len(forms_without_percent)
                            for f in forms_without_percent:
                                f['percent_share'] = per_form
                    elif not forms_without_percent and abs(total_explicit_percent - 1.0) > 0.01:
                        # All have percentages but don't sum to 100 - normalize
                        if total_explicit_percent > 0:
                            for f in forms_with_percent:
                                if f['percent_share'] is not None:
                                    f['percent_share'] /= total_explicit_percent

                result['extracted_forms'] = forms_with_percent
            else:
                # Single form
                form_info = self._parse_single_form(form_text, form_bracket_tokens)
                if form_info:
                    form_info['percent_share'] = 1.0  # Single form = 100%
                    result['extracted_forms'] = [form_info]

        result['form_extraction_success'] = len(result['extracted_forms']) > 0
        return result

    def _parse_single_form(self, form_text: str, bracket_tokens: List[str]) -> Optional[Dict]:
        """
        Parse a single form specification into structured data.

        Returns dict with:
        - raw_form_text: exact extracted string (immutable)
        - match_candidates: list of strings to try for matching
        - display_form: human-readable cleaned version
        - percent_share: float or None
        """
        if not form_text or not form_text.strip():
            return None

        raw_text = form_text.strip()

        # Extract percentage if present (e.g., "50% B-carotene")
        percent_share = None
        percent_match = re.match(r'^(\d+(?:\.\d+)?)\s*%\s*(.+)$', raw_text)
        if percent_match:
            percent_share = float(percent_match.group(1)) / 100.0
            raw_text = percent_match.group(2).strip()

        # Build match candidates (preserve bracket tokens!)
        match_candidates = []

        # 1. Original text (with TM removed but brackets preserved)
        candidate1 = re.sub(r'[®™]', '', raw_text).strip()
        if candidate1:
            match_candidates.append(candidate1)

        # 2. Text with brackets removed (for display matching)
        candidate2 = re.sub(r'\s*\[[^\]]*\]', '', candidate1).strip()
        if candidate2 and candidate2 != candidate1:
            match_candidates.append(candidate2)

        # 3. Add bracket tokens as separate candidates (e.g., "P-5-P", "D3", "L-5-MTHF Ca")
        for token in bracket_tokens:
            token_clean = token.strip()
            if token_clean and token_clean.lower() not in [c.lower() for c in match_candidates]:
                match_candidates.append(token_clean)

        # 4. Extract bracket content from this specific form text
        local_brackets = re.findall(r'\[([^\]]+)\]', raw_text)
        for token in local_brackets:
            token_clean = token.strip()
            if token_clean and token_clean.lower() not in [c.lower() for c in match_candidates]:
                match_candidates.append(token_clean)

        # 5. Add hyphen variants (e.g., "P-5-P" -> "P5P")
        for candidate in list(match_candidates):
            no_hyphen = candidate.replace('-', '')
            if no_hyphen != candidate and no_hyphen.lower() not in [c.lower() for c in match_candidates]:
                match_candidates.append(no_hyphen)

        # 6. Remove "from X" suffix for additional candidate
        from_removed = re.sub(r'\s+from\s+\w+\s*$', '', candidate2, flags=re.IGNORECASE).strip()
        if from_removed and from_removed != candidate2 and from_removed.lower() not in [c.lower() for c in match_candidates]:
            match_candidates.append(from_removed)

        # Display form: cleaned for human readability
        display_form = re.sub(r'[®™]', '', raw_text)
        display_form = re.sub(r'\s*\[[^\]]*\]', '', display_form).strip()
        display_form = re.sub(r'\s+from\s+\w+\s*$', '', display_form, flags=re.IGNORECASE).strip()

        return {
            'raw_form_text': raw_text,
            'match_candidates': match_candidates,
            'display_form': display_form,
            'percent_share': percent_share
        }

    def _fuzzy_company_match(
        self,
        name1: str,
        name2: str,
        threshold: Optional[float] = None
    ) -> Tuple[bool, float]:
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
        if not self.config.get("processing_config", {}).get("enable_fuzzy_matching", True):
            return False, 0.0

        if threshold is None:
            threshold = self.company_fuzzy_threshold
        if threshold > 1.0:
            threshold = threshold / 100.0
        threshold = max(0.0, min(1.0, threshold))

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

    def _fuzzy_ingredient_match(
        self,
        ingredient_name: str,
        target_name: str,
        aliases: List[str],
        threshold: float = 0.85,
        review_threshold: float = 0.90
    ) -> Optional[Dict]:
        """
        Fuzzy match ingredient names as a FALLBACK for quality matching.

        NOT USED FOR: Banned substance detection (safety-critical - use exact only)
        USED FOR: Ingredient quality/form matching where typos may occur

        Args:
            ingredient_name: The ingredient name to match
            target_name: The canonical target name
            aliases: List of known aliases
            threshold: Minimum score (0-1) to accept match (default 0.85)
            review_threshold: Matches below this score are flagged for review

        Returns:
            Dict with match details or None if no match above threshold.
            Includes: method, matched_alias, score, needs_review
        """
        if not ingredient_name or not target_name:
            return None

        ing_norm = self._normalize_text(ingredient_name)
        if not ing_norm:
            return None

        candidates = [target_name] + aliases
        best_match = None
        best_score = 0.0

        for candidate in candidates:
            cand_norm = self._normalize_text(candidate)
            if not cand_norm:
                continue

            if RAPIDFUZZ_AVAILABLE:
                # Use token_sort_ratio for word order flexibility
                # "Vitamin B12" should match "B12 Vitamin"
                score = rf_fuzz.token_sort_ratio(ing_norm, cand_norm) / 100.0
            else:
                # Fallback to difflib
                score = SequenceMatcher(None, ing_norm, cand_norm).ratio()

            if score > best_score:
                best_score = score
                best_match = candidate

        if best_score < threshold:
            return None

        return {
            "method": "fuzzy",
            "matched_alias": best_match if best_match != target_name else None,
            "score": best_score,
            "needs_review": best_score < review_threshold
        }

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

    def _collect_clinical_aliases(self, study: Dict) -> List[str]:
        """Collect alias variants from clinical-study records."""
        aliases: List[str] = []
        for field in ("aliases", "aliases_normalized"):
            value = study.get(field)
            if isinstance(value, list):
                aliases.extend([str(item) for item in value if item])
        return aliases

    def _clinical_study_match(self, candidates: List[str], study: Dict) -> Optional[Dict]:
        """
        Exact clinical-study matching with optional false-positive suppression.

        Supports schema extensions:
          - aliases_normalized: pre-normalized alias list
          - exclude_aliases: ingredient strings that should explicitly not match
        """
        study_name = str(study.get("standard_name", "") or "")
        if not study_name:
            return None

        candidate_pairs: List[Tuple[str, str]] = []
        for candidate in candidates:
            norm = self._normalize_text(candidate)
            if norm:
                candidate_pairs.append((str(candidate), norm))
        if not candidate_pairs:
            return None

        excluded = {
            self._normalize_text(value)
            for value in (study.get("exclude_aliases") or [])
            if self._normalize_text(value)
        }
        if excluded and any(norm in excluded for _, norm in candidate_pairs):
            return None

        target_norm = self._normalize_text(study_name)
        if any(norm == target_norm for _, norm in candidate_pairs):
            return {"method": "standard_name", "matched_term": study_name}

        alias_map = {}
        for alias in self._collect_clinical_aliases(study):
            alias_norm = self._normalize_text(alias)
            if alias_norm:
                alias_map[alias_norm] = alias

        for _, norm in candidate_pairs:
            matched_alias = alias_map.get(norm)
            if matched_alias and norm not in excluded:
                return {"method": "alias", "matched_term": matched_alias}

        return None

    def _check_additive_match(
        self,
        ing_name: str,
        std_name: str,
        target_name: str,
        aliases: List[str]
    ) -> Optional[Dict]:
        """
        Check if ingredient matches additive and return match details.

        Returns dict with match_method and matched_alias for provenance tracking,
        or None if no match.

        LABEL NAME PRESERVATION: This method tracks HOW a match occurred
        so we can show the user the canonical name while preserving the
        original label text for audit.
        """
        if not ing_name and not std_name:
            return None

        ing_norm = self._normalize_text(ing_name) if ing_name else ""
        std_norm = self._normalize_text(std_name) if std_name else ""
        target_norm = self._normalize_text(target_name)

        # Check direct match against canonical name
        if ing_norm and ing_norm == target_norm:
            return {"method": "exact", "matched_alias": None}
        if std_norm and std_norm == target_norm:
            return {"method": "exact_via_std", "matched_alias": None}

        # Check alias matches
        for alias in aliases:
            alias_norm = self._normalize_text(alias)
            if ing_norm and ing_norm == alias_norm:
                return {"method": "alias", "matched_alias": alias}
            if std_norm and std_norm == alias_norm:
                return {"method": "alias_via_std", "matched_alias": alias}

        return None

    def _token_bounded_match(
        self, ingredient_name: str, target_name: str, aliases: List[str]
    ) -> Tuple[bool, Optional[str]]:
        """
        Match target/aliases as whole tokens within ingredient string.
        Prevents substring collisions while allowing bounded matches in longer strings.
        """
        if not ingredient_name or not target_name:
            return False, None

        ing_norm = self._normalize_text(ingredient_name)
        if not ing_norm:
            return False, None

        candidates = [target_name] + aliases
        for candidate in candidates:
            cand_norm = self._normalize_text(candidate)
            if not cand_norm:
                continue
            if ing_norm == cand_norm:
                return True, candidate
            pattern = r'(?<![a-z0-9])' + re.escape(cand_norm) + r'(?![a-z0-9])'
            if re.search(pattern, ing_norm):
                return True, candidate

        return False, None

    def _is_low_precision_token_alias(self, alias: str) -> bool:
        """
        Reject low-information aliases for token-bounded matching.

        These phrases are too generic and create false positives
        (e.g. "mushroom extract", "disodium salt").
        """
        alias_norm = self._normalize_text(alias)
        if not alias_norm:
            return True

        explicit_deny = {
            "disodium salt",
            "mushroom extract",
            "functional mushroom blend",
            "extract",
            "blend",
            "powder",
            "oil",
            "salt",
        }
        if alias_norm in explicit_deny:
            return True

        generic_tokens = {
            "functional", "proprietary", "natural", "organic",
            "extract", "blend", "powder", "oil", "salt",
            "disodium", "sodium",
        }
        tokens = [t for t in re.split(r"[\s/-]+", alias_norm) if t]
        if not tokens:
            return True

        informative = [
            t for t in tokens
            if len(t) >= 4 and t not in generic_tokens and not t.isdigit()
        ]
        return len(informative) == 0

    def _filter_safe_token_aliases(self, target_name: str, aliases: List[str]) -> List[str]:
        """Return aliases safe for token-bounded matching."""
        safe = []
        for alias in aliases:
            if not self._is_low_precision_token_alias(alias):
                safe.append(alias)

        # Always include canonical target if present.
        if target_name:
            safe.insert(0, target_name)
        return safe

    def _token_match_has_required_context(
        self,
        ingredient_name: str,
        banned_item: Dict[str, Any],
        matched_variant: Optional[str],
    ) -> bool:
        """
        Require domain context for high-collision categories (e.g. colorants).
        """
        ingredient_norm = self._normalize_text(ingredient_name)
        category = self._normalize_text(banned_item.get("category", ""))
        class_tags = [self._normalize_text(t) for t in banned_item.get("class_tags", []) if isinstance(t, str)]
        banned_name = self._normalize_text(banned_item.get("standard_name", ""))
        matched_norm = self._normalize_text(matched_variant or "")

        is_colorant = (
            "color" in category
            or "colour" in category
            or any("color" in t or "colour" in t for t in class_tags)
            or banned_name in {"orange b", "red 40", "blue 1"}
        )
        if not is_colorant:
            return True

        # If we matched the canonical banned color token itself, allow.
        if matched_norm and matched_norm == banned_name:
            return True

        # Otherwise require explicit color context in label ingredient text.
        return bool(
            re.search(r"(?<![a-z0-9])(dye|color|colour|fd\s*&\s*c|fdc|lake|pigment)(?![a-z0-9])", ingredient_norm)
        )

    def _hyphen_space_token_pattern(self, variant: str) -> Optional[re.Pattern]:
        """Build a token-bounded regex that tolerates hyphens/spaces between tokens."""
        norm = self._normalize_text(variant)
        if not norm:
            return None
        tokens = [t for t in re.split(r'[\s-]+', norm) if t]
        if not tokens:
            return None
        pattern = r'(?<![a-z0-9])' + r'[-\s]+'.join(map(re.escape, tokens)) + r'(?![a-z0-9])'
        return re.compile(pattern)

    def _allowlist_match(self, ingredient_name: str, allowlist_entries: List[Dict]) -> Optional[Dict]:
        """Match against explicit banned allowlist rules with bounded policies."""
        if not ingredient_name:
            return None

        ing_norm = self._normalize_text(ingredient_name)
        if not ing_norm:
            return None

        for entry in allowlist_entries:
            policy = entry.get("match_policy", "token_bounded")
            variants = entry.get("variants", []) or []
            variants_regex = entry.get("variants_regex", []) or []

            if policy == "token_bounded_hyphen_space":
                for variant in variants:
                    pattern = self._hyphen_space_token_pattern(variant)
                    if pattern and pattern.search(ing_norm):
                        return {
                            "match_method": f"allowlist_{policy}",
                            "matched_variant": variant,
                            "allowlist_id": entry.get("id", ""),
                        }
            elif policy == "token_bounded_regex":
                for pattern in variants_regex:
                    if re.search(pattern, ing_norm):
                        return {
                            "match_method": f"allowlist_{policy}",
                            "matched_variant": pattern,
                            "allowlist_id": entry.get("id", ""),
                        }
            else:
                for variant in variants:
                    matched, matched_variant = self._token_bounded_match(ingredient_name, variant, [])
                    if matched:
                        return {
                            "match_method": "allowlist_token_bounded",
                            "matched_variant": matched_variant or variant,
                            "allowlist_id": entry.get("id", ""),
                        }

        return None

    def _denylist_match(self, ingredient_name: str, denylist_entries: List[Dict]) -> Optional[Dict]:
        """Match against explicit denylist rules to prevent false positives."""
        if not ingredient_name:
            return None

        ing_norm = self._normalize_text(ingredient_name)
        if not ing_norm:
            return None

        for entry in denylist_entries:
            policy = entry.get("match_policy", "token_bounded")
            pattern = entry.get("pattern")
            variants = entry.get("variants", []) or []

            if pattern:
                if re.search(pattern, ing_norm):
                    return {
                        "denylist_id": entry.get("id", ""),
                        "matched_pattern": pattern,
                    }
            elif policy == "token_bounded_hyphen_space":
                for variant in variants:
                    compiled = self._hyphen_space_token_pattern(variant)
                    if compiled and compiled.search(ing_norm):
                        return {
                            "denylist_id": entry.get("id", ""),
                            "matched_pattern": variant,
                        }
            else:
                for variant in variants:
                    matched, matched_variant = self._token_bounded_match(ingredient_name, variant, [])
                    if matched:
                        return {
                            "denylist_id": entry.get("id", ""),
                            "matched_pattern": matched_variant or variant,
                        }

        return None

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
        strain_id_pattern = re.compile(r'(atcc\s*(?:pta\s*)?[\d]+|dsm\s*[\d]+|ncfm|\bgg\b|\bk12\b|\bm18\b|bb-?12|bb536|hn019|bi-?07|de111|299v)', re.IGNORECASE)
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
        cache_enabled = bool(getattr(self, "_product_text_cache_enabled", False))
        if not hasattr(self, "_product_text_cache") or not isinstance(self._product_text_cache, dict):
            self._product_text_cache = {}

        cache_key = id(product)
        if cache_enabled:
            cached = self._product_text_cache.get(cache_key)
            if cached is not None:
                return cached

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

        combined = ' '.join(filter(None, texts))
        if cache_enabled:
            self._product_text_cache[cache_key] = combined
        return combined

    def _get_all_product_text_lower(self, product: Dict) -> str:
        """Cached lowercase variant of combined product text."""
        cache_enabled = bool(getattr(self, "_product_text_cache_enabled", False))
        if not hasattr(self, "_product_text_lower_cache") or not isinstance(self._product_text_lower_cache, dict):
            self._product_text_lower_cache = {}

        cache_key = id(product)
        if cache_enabled:
            cached = self._product_text_lower_cache.get(cache_key)
            if cached is not None:
                return cached

        lowered = self._get_all_product_text(product).lower()
        if cache_enabled:
            self._product_text_lower_cache[cache_key] = lowered
        return lowered

    # =========================================================================
    # SECTION A: INGREDIENT QUALITY DATA COLLECTORS
    # =========================================================================

    def _collect_ingredient_quality_data(self, product: Dict) -> Dict:
        """
        Collect ingredient quality data for scoring Section A1-A2.

        TWO-PASS CLASSIFICATION SYSTEM:
        - Pass 1: Filter activeIngredients into scorable vs skipped (non-scorable)
        - Pass 2: Rescue therapeutic actives from inactiveIngredients

        This prevents inflation of unmapped_count from excipients, sweeteners,
        and blend header rows that should never be quality-scored.

        Returns bio_score, dosage_importance, form matches - NO calculations.
        """
        quality_map = self.databases.get('ingredient_quality_map', {})
        botanicals_db = self.databases.get('standardized_botanicals', {})
        active_ingredients = product.get('activeIngredients', [])
        inactive_ingredients = product.get('inactiveIngredients', [])

        # Track classification results
        ingredients_scorable = []
        ingredients_skipped = []
        promoted_from_inactive = []
        skipped_reasons_breakdown = {}
        blend_header_rows = []

        # Legacy tracking (backward compatibility)
        all_quality_data = []
        premium_form_count = 0
        legacy_unmapped_count = 0

        # New scorable-only tracking
        unmapped_scorable_count = 0
        recognized_non_scorable_count = 0  # Tiered matching: recognized but not therapeutic
        pattern_match_wins_count = 0
        contains_match_wins_count = 0
        parent_fallback_count = 0

        # =================================================================
        # PASS 1: Classify activeIngredients as scorable or skipped
        # =================================================================
        for ingredient in active_ingredients:
            # Use branded_token_extracted for matching if present AND it differs from name.
            # When branded_token_extracted == name the clean stage collapsed the full label
            # to just the brand prefix (e.g. "Albion" from "Albion Magnesium Bisglycinate Chelate").
            # In that case prefer raw_source_text so IQM alias matching can resolve the full form.
            _bte = ingredient.get('branded_token_extracted', '')
            _raw = ingredient.get('name', '')
            if _bte and _bte != _raw:
                ing_name = _bte
            else:
                ing_name = ingredient.get('raw_source_text') or _raw
            std_name = ingredient.get('standardName', '') or ing_name
            quantity = ingredient.get('quantity', 0)
            unit = ingredient.get('unit', '')
            hierarchy_type = ingredient.get('hierarchyType')

            # Check for skip conditions
            skip_reason = self._should_skip_from_scoring(ingredient, quality_map, botanicals_db)

            if skip_reason:
                # Track skip reason breakdown
                skipped_reasons_breakdown[skip_reason] = skipped_reasons_breakdown.get(skip_reason, 0) + 1

                # Track blend headers separately for blend-only detection
                if skip_reason == SKIP_REASON_BLEND_HEADER_NO_DOSE:
                    blend_header_rows.append(ing_name)

                recognition_info = None
                if skip_reason == SKIP_REASON_RECOGNIZED_NON_SCORABLE:
                    recognition_info = self._is_recognized_non_scorable(ing_name, std_name)
                    if recognition_info:
                        recognized_non_scorable_count += 1

                has_dose, _ = self._has_valid_therapeutic_dose(ingredient)
                unit_normalized = self._normalize_unit_for_signal(unit)
                is_excipient, never_promote_reason = self._compute_excipient_flags(ingredient)
                blend_flags = self._compute_blend_flags(ingredient, skip_reason)

                # LABEL NAME PRESERVATION: Track raw label text for skipped items
                raw_source_text = ingredient.get('raw_source_text') or ing_name
                ingredients_skipped.append({
                    # LABEL NAME PRESERVATION:
                    "name": ing_name,  # Label-facing name
                    "raw_source_text": raw_source_text,  # Exact label text (provenance)
                    "standard_name": std_name,
                    "skip_reason": skip_reason,
                    "quantity": quantity,
                    "unit": unit,
                    "unit_normalized": unit_normalized,
                    "has_dose": has_dose,
                    "is_blend_header": blend_flags["is_blend_header"],
                    "is_proprietary_blend": blend_flags["is_proprietary_blend"],
                    "blend_total_weight_only": blend_flags["blend_total_weight_only"],
                    "blend_disclosed_components_count": blend_flags["blend_disclosed_components_count"],
                    "is_excipient": is_excipient,
                    "never_promote_reason": never_promote_reason,
                    "recognition_source": (recognition_info or {}).get("recognition_source"),
                    "recognition_reason": (recognition_info or {}).get("recognition_reason"),
                    "recognition_type": (recognition_info or {}).get("recognition_type"),
                    "recognized_entry_id": (recognition_info or {}).get("matched_entry_id"),
                    "recognized_entry_name": (recognition_info or {}).get("matched_entry_name"),
                    "mapped_identity": bool(recognition_info) or bool(is_excipient),
                    "scoreable_identity": False,
                    "role_classification": "inactive_non_scorable",
                    "identity_confidence": 1.0 if (recognition_info or is_excipient) else 0.0,
                    "identity_decision_reason": skip_reason,
                    "safety_hits": [],
                    "certificates": [],
                    "source_section": "active",
                    "hierarchyType": hierarchy_type
                })
                # DO NOT track as unmapped - these are intentionally not scored
                continue

            # Scorable ingredient - try to match against quality map
            # Pass cleaned forms[] to enable form-aware matching (P0 form-loss fix)
            ingredient_forms = ingredient.get('forms') or []
            match_result = self._match_quality_map(
                ing_name, std_name, quality_map, cleaned_forms=ingredient_forms
            )
            quality_entry = self._build_quality_entry(
                ingredient, match_result, hierarchy_type, source_section="active"
            )
            is_quality_match = bool(
                match_result and isinstance(match_result, dict) and match_result.get("match_status") != "FORM_UNMAPPED"
            )

            if is_quality_match:
                match_tier = match_result.get('match_tier')
                if match_tier == "pattern":
                    pattern_match_wins_count += 1
                elif match_tier == "contains":
                    contains_match_wins_count += 1
                if match_result.get('fallback_form_selected'):
                    parent_fallback_count += 1
                if match_result.get('bio_score', 0) > 12:
                    premium_form_count += 1
            else:
                # TIERED MATCHING (per dev feedback):
                # Before marking as unmapped, check if recognized in other databases
                recognition = self._is_recognized_non_scorable(ing_name, std_name)
                if recognition:
                    # Recognized but non-scorable - don't count as unmapped
                    # Mark in quality_entry for transparency
                    quality_entry['recognized_non_scorable'] = True
                    quality_entry['recognition_source'] = recognition.get('recognition_source')
                    quality_entry['recognition_reason'] = recognition.get('recognition_reason')
                    quality_entry['recognition_type'] = recognition.get('recognition_type')
                    quality_entry['matched_entry_id'] = recognition.get('matched_entry_id')
                    quality_entry['matched_entry_name'] = recognition.get('matched_entry_name')
                    quality_entry['mapped'] = True
                    quality_entry['mapped_identity'] = True
                    quality_entry['scoreable_identity'] = False
                    quality_entry['role_classification'] = 'recognized_non_scorable'
                    quality_entry['identity_confidence'] = 1.0
                    quality_entry['identity_decision_reason'] = recognition.get('recognition_reason') or 'recognized_non_scorable'
                    # Track for coverage metrics (separate from unmapped)
                    recognized_non_scorable_count += 1
                else:
                    # Truly unmapped - track as before
                    unmapped_scorable_count += 1
                    legacy_unmapped_count += 1
                    self._track_unmapped(ing_name, 'active')

            ingredients_scorable.append(quality_entry)
            all_quality_data.append(quality_entry)

        # =================================================================
        # PASS 2: Rescue therapeutic actives from inactiveIngredients
        # =================================================================
        for ingredient in inactive_ingredients:
            # Same branded_token_extracted logic as Pass 1: prefer raw_source_text when
            # the token was collapsed to just the brand prefix (e.g., "Albion").
            _bte = ingredient.get('branded_token_extracted', '')
            _raw = ingredient.get('name', '')
            if _bte and _bte != _raw:
                ing_name = _bte
            else:
                ing_name = ingredient.get('raw_source_text') or _raw
            std_name = ingredient.get('standardName', '') or ing_name
            quantity = ingredient.get('quantity', 0)
            unit = ingredient.get('unit', '')
            hierarchy_type = ingredient.get('hierarchyType')

            # Check promotion eligibility
            promotion_result = self._should_promote_to_scorable(
                ingredient, quality_map, botanicals_db, len(ingredients_scorable)
            )

            if promotion_result:
                promotion_reason = promotion_result.get('reason')
                promotion_confidence = promotion_result.get('confidence', 'MEDIUM')
                dose_present = bool(quantity and unit)

                ingredient_forms = ingredient.get('forms') or []
                match_result = self._match_quality_map(
                    ing_name, std_name, quality_map, cleaned_forms=ingredient_forms
                )
                quality_entry = self._build_quality_entry(
                    ingredient, match_result, hierarchy_type,
                    source_section="inactive_promoted",
                    promotion_reason=promotion_reason,
                    promotion_confidence=promotion_confidence,
                    dose_present=dose_present
                )
                is_quality_match = bool(
                    match_result and isinstance(match_result, dict) and match_result.get("match_status") != "FORM_UNMAPPED"
                )

                if is_quality_match:
                    match_tier = match_result.get('match_tier')
                    if match_tier == "pattern":
                        pattern_match_wins_count += 1
                    elif match_tier == "contains":
                        contains_match_wins_count += 1
                    if match_result.get('fallback_form_selected'):
                        parent_fallback_count += 1
                    if match_result.get('bio_score', 0) > 12:
                        premium_form_count += 1
                else:
                    # Apply the same identity fallback used in pass-1 actives.
                    # Promoted inactives can be therapeutically relevant botanicals
                    # that are recognized in non-quality DBs.
                    recognition = self._is_recognized_non_scorable(ing_name, std_name)
                    if recognition:
                        quality_entry['recognized_non_scorable'] = True
                        quality_entry['recognition_source'] = recognition.get('recognition_source')
                        quality_entry['recognition_reason'] = recognition.get('recognition_reason')
                        quality_entry['recognition_type'] = recognition.get('recognition_type')
                        quality_entry['matched_entry_id'] = recognition.get('matched_entry_id')
                        quality_entry['matched_entry_name'] = recognition.get('matched_entry_name')
                        quality_entry['mapped'] = True
                        quality_entry['mapped_identity'] = True
                        quality_entry['scoreable_identity'] = False
                        quality_entry['role_classification'] = 'recognized_non_scorable'
                        quality_entry['identity_confidence'] = 1.0
                        quality_entry['identity_decision_reason'] = (
                            recognition.get('recognition_reason') or 'recognized_non_scorable'
                        )
                        recognized_non_scorable_count += 1
                    else:
                        unmapped_scorable_count += 1
                        legacy_unmapped_count += 1
                        self._track_unmapped(ing_name, 'active_promoted')

                ingredients_scorable.append(quality_entry)
                all_quality_data.append(quality_entry)
                # LABEL NAME PRESERVATION
                raw_source_text = ingredient.get('raw_source_text') or ing_name
                promoted_from_inactive.append({
                    "name": ing_name,  # Label-facing name
                    "raw_source_text": raw_source_text,  # Exact label text
                    "promotion_reason": promotion_reason,
                    "promotion_confidence": promotion_confidence,
                    "dose_present": dose_present
                })

        # Mark top-level nutrient totals when nested child forms of the same
        # canonical ingredient are present in active rows.
        self._mark_parent_total_rows(ingredients_scorable)

        # =================================================================
        # BLEND-ONLY PRODUCT DETECTION
        # =================================================================
        total_scorable = len(ingredients_scorable)
        blend_only_product = (
            total_scorable <= 1 and
            len(blend_header_rows) >= 1 and
            len(active_ingredients) > 1
        )

        # =================================================================
        # BUILD NORMALIZED NAMES SET FOR QUICK LOOKUPS
        # =================================================================
        # Used by scoring for synergy detection, absorption enhancer pairing,
        # and cross-section linking without recomputing normalization
        scorable_names_normalized = set()
        for ing in ingredients_scorable:
            std_name = ing.get('standard_name', '')
            if std_name:
                scorable_names_normalized.add(self._normalize_text(std_name))
            # Also add original name normalized
            orig_name = ing.get('name', '')
            if orig_name:
                scorable_names_normalized.add(self._normalize_text(orig_name))

        # =================================================================
        # COVERAGE METRICS WITH LEAK DETECTION
        # =================================================================
        # Records seen = what entered pass 1 classification (active ingredients)
        total_records_seen = len(active_ingredients)
        total_skipped = len(ingredients_skipped)
        total_promoted = len(promoted_from_inactive)

        # Scorable from pass 1 = total scorable minus promoted from inactive
        scorable_from_pass1 = total_scorable - total_promoted

        # Invariant check: all active records must end up classified
        # scorable_from_pass1 + skipped should equal total_records_seen
        unevaluated_records = total_records_seen - (scorable_from_pass1 + total_skipped)

        # Total evaluated = scorable + skipped (includes promoted in scorable)
        total_ingredients_evaluated = total_scorable + total_skipped

        return {
            # Schema version for forward compatibility
            "quality_data_schema_version": 2,

            # Legacy fields (backward compatibility)
            "ingredients": all_quality_data,
            "premium_form_count": premium_form_count,
            "unmapped_count": legacy_unmapped_count,
            "total_active": len(active_ingredients),

            # New two-pass classification fields
            "ingredients_scorable": ingredients_scorable,
            "ingredients_skipped": ingredients_skipped,
            "unmapped_scorable_count": unmapped_scorable_count,
            "total_scorable_active_count": total_scorable,
            "skipped_non_scorable_count": total_skipped,
            "skipped_reasons_breakdown": skipped_reasons_breakdown,
            "promoted_from_inactive": promoted_from_inactive,
            "blend_only_product": blend_only_product,
            "blend_header_rows": blend_header_rows,

            # Coverage metrics with leak detection
            "total_records_seen": total_records_seen,
            "total_ingredients_evaluated": total_ingredients_evaluated,
            "unevaluated_records": unevaluated_records,  # Should be 0
            "pattern_match_wins_count": pattern_match_wins_count,
            "contains_match_wins_count": contains_match_wins_count,
            "parent_fallback_count": parent_fallback_count,

            # Quick-lookup normalized names for scoring efficiency
            "scorable_ingredient_names_normalized": list(scorable_names_normalized),
        }

    def _has_valid_therapeutic_dose(self, ingredient: Dict) -> Tuple[bool, bool]:
        """
        Validate if ingredient has a valid therapeutic dose.

        Handles edge cases:
        - Quantity as string "0" or "0.0"
        - Unit as whitespace or pseudo-unit ("serving", "n/a", etc.)
        - Unit missing entirely

        Returns:
            (has_dose: bool, is_blend_header_weight: bool)
            - has_dose: True if quantity > 0 AND unit is a valid therapeutic unit
            - is_blend_header_weight: True if has numeric value but might be blend total
        """
        quantity = ingredient.get('quantity')
        unit = ingredient.get('unit', '')

        # Normalize unit
        unit_normalized = (str(unit) if unit is not None else '').strip().lower()

        # Check for pseudo-units (not valid therapeutic doses)
        if unit_normalized in PSEUDO_UNITS_INVALID:
            return (False, False)

        # Empty unit after normalization = no dose
        if not unit_normalized:
            return (False, False)

        # Check quantity is present and meaningful
        if quantity is None:
            return (False, False)

        # Handle string quantities
        if isinstance(quantity, str):
            try:
                quantity = float(quantity.strip())
            except (ValueError, AttributeError):
                return (False, False)

        # Zero or negative quantity = no dose
        if quantity <= 0:
            return (False, False)

        # Valid therapeutic dose found
        return (True, True)

    def _normalize_unit_for_signal(self, unit: Any) -> str:
        """Normalize unit for ingredient-level signals."""
        if unit is None:
            return ""
        unit_normalized = str(unit).strip().lower()
        unit_normalized = unit_normalized.replace('µg', 'mcg').replace('μg', 'mcg')
        unit_normalized = unit_normalized.replace(' ', '')
        return unit_normalized

    def _compute_excipient_flags(self, ingredient: Dict) -> Tuple[bool, Optional[str]]:
        """Determine excipient status for ingredient-level signals."""
        ing_name = (ingredient.get('name', '') or '').strip().lower()

        if ingredient.get('isAdditive', False):
            return True, SKIP_REASON_ADDITIVE

        additive_type = ingredient.get('additiveType', '')
        if additive_type and additive_type.lower() in ADDITIVE_TYPES_SKIP_SCORING:
            return True, SKIP_REASON_ADDITIVE_TYPE

        # Check ingredient name only — DSLD standardName can misclassify active botanicals
        # (e.g. Elderberry/Turmeric → "natural colors"), causing false excipient gates.
        # isAdditive=True (genuine additives) is already handled above.
        if ing_name in EXCIPIENT_NEVER_PROMOTE:
            return True, "excipient_never_promote"

        for excipient in EXCIPIENT_NEVER_PROMOTE:
            if excipient in ing_name:
                return True, "excipient_never_promote"

        return False, None

    def _compute_blend_flags(self, ingredient: Dict, skip_reason: Optional[str]) -> Dict:
        """Compute blend-related flags for ingredient-level signals."""
        nested = ingredient.get('nestedIngredients') or []
        is_proprietary_blend = bool(
            ingredient.get('proprietaryBlend', False) or ingredient.get('isProprietaryBlend', False)
        )
        is_blend_header = skip_reason in (
            SKIP_REASON_BLEND_HEADER_NO_DOSE,
            SKIP_REASON_BLEND_HEADER_WITH_WEIGHT
        )
        blend_total_weight_only = skip_reason == SKIP_REASON_BLEND_HEADER_WITH_WEIGHT

        return {
            "is_blend_header": is_blend_header,
            "is_proprietary_blend": is_proprietary_blend,
            "blend_total_weight_only": blend_total_weight_only,
            "blend_disclosed_components_count": len(nested) if isinstance(nested, list) else 0
        }

    def _normalize_exclusion_text(self, value: str) -> str:
        """Normalize label text for robust exclusion checks."""
        text = (value or "").lower().strip()
        text = re.sub(r"\s+", " ", text)
        text = text.rstrip(":;,")
        return text

    def _excluded_text_reason(self, value: str) -> Optional[str]:
        """
        Return exclusion reason if text is a known label/header or nutrition rollup.

        Protects against punctuation/casing variants like:
        - "Less than 2%:"
        - "Contains < 2%"
        - "May also contain <2% of:"
        """
        text = self._normalize_exclusion_text(value)
        if not text:
            return None

        if text in EXCLUDED_LABEL_PHRASES:
            return SKIP_REASON_LABEL_PHRASE
        if text in EXCLUDED_NUTRITION_FACTS:
            return SKIP_REASON_NUTRITION_FACT

        # Header/label phrase variants that are never ingredients.
        if re.match(r"^(contains|may also contain)\s*(less than|<)\s*\d+\s*%(\s*of)?", text):
            return SKIP_REASON_LABEL_PHRASE
        if re.match(r"^contains?\s+\d+\s*percent\s+or\s+less(\s+of)?", text):
            return SKIP_REASON_LABEL_PHRASE
        if re.match(r"^less than\s*\d+\s*%(\s*of)?", text):
            return SKIP_REASON_LABEL_PHRASE
        if re.match(r"^<\s*\d+\s*%\s*of", text):
            return SKIP_REASON_LABEL_PHRASE
        # Spec-string fragments emitted by parser; these are not standalone ingredients.
        if re.match(r"^\s*min\.\s*\d+", text):
            return SKIP_REASON_LABEL_PHRASE
        if re.match(r"^\s*providing(?:\s+minimum)?\s+\d+", text):
            return SKIP_REASON_LABEL_PHRASE
        if re.match(r"^\s*providing[:\s]", text):
            return SKIP_REASON_LABEL_PHRASE
        if re.match(r"^\s*provides?\b", text):
            return SKIP_REASON_LABEL_PHRASE
        if re.match(r"^\s*supplying\b", text):
            return SKIP_REASON_LABEL_PHRASE
        if re.match(r"^\s*typical(?:ly)?\b", text):
            return SKIP_REASON_LABEL_PHRASE
        if re.match(r"^\s*which\s+contains?\s+\d", text):
            return SKIP_REASON_LABEL_PHRASE
        if re.match(r"^\s*contains?\s+\d+(?:,\d{3})?(?:\.\d+)?\s*(mg|mcg|g|iu|cfu|billion|million)\b", text):
            return SKIP_REASON_LABEL_PHRASE
        if re.match(r"^\s*<\s*\d+(?:,\d{3})?(?:\.\d+)?\s*(mg|mcg|g|iu|cfu|billion|million)\s+of\b", text):
            return SKIP_REASON_LABEL_PHRASE
        if re.match(r"^\s*standardized\s+to\s+contain(?:ing)?\s+\d+", text):
            return SKIP_REASON_LABEL_PHRASE
        if re.match(r"^\s*from\s+\d+(?:,\d{3})?(?:\.\d+)?\s*(mg|mcg|g|iu|billion|million)\b", text):
            return SKIP_REASON_LABEL_PHRASE

        # Nutrition rollup variants.
        if re.match(r"^other omega[- ]\d+\s+fatty acids$", text):
            return SKIP_REASON_NUTRITION_FACT
        if re.match(r"^other omega\s+fatty acids$", text):
            return SKIP_REASON_NUTRITION_FACT
        # Descriptor/rollup rows frequently emitted as pseudo-ingredients.
        if re.match(r"^contains\s+zeaxanthin$", text):
            return SKIP_REASON_NUTRITION_FACT
        if re.match(r"^total\s+(mixed\s+)?tocopherols?$", text):
            return SKIP_REASON_NUTRITION_FACT
        if re.match(r"^total\s+mixed\s+carotenoids?$", text):
            return SKIP_REASON_NUTRITION_FACT
        if re.match(r"^total\s+curcuminoids?$", text):
            return SKIP_REASON_NUTRITION_FACT
        if re.match(r"^total\s+gingerols(\s+and\s+shogaols?)?$", text):
            return SKIP_REASON_NUTRITION_FACT
        if re.match(r"^total\s+calamari\s+oil$", text):
            return SKIP_REASON_NUTRITION_FACT
        if re.match(r"^total\s+omega[- ]?3.*", text):
            return SKIP_REASON_NUTRITION_FACT
        if re.match(r"^other\s+omega[- ]?3.*", text):
            return SKIP_REASON_NUTRITION_FACT
        if re.match(r"^total\s+(astaxanthin|cbd|cannabidiol|vitamin a)$", text):
            return SKIP_REASON_NUTRITION_FACT
        if re.match(r"^also\s+containing\s+additional\s+carotenoids?$", text):
            return SKIP_REASON_NUTRITION_FACT
        if re.match(r"^these\s+three\s+oils\s+typically\s+provide\s+the\s+following\s+fatty\s+acid\s+profile$", text):
            return SKIP_REASON_NUTRITION_FACT
        if re.match(r"^quath\s+dravya\s+of$", text):
            return SKIP_REASON_LABEL_PHRASE

        return None

    def _should_skip_from_scoring(self, ingredient: Dict, quality_map: Dict, botanicals_db: Dict) -> Optional[str]:
        """
        Determine if an ingredient should be SKIPPED from quality scoring.

        Skip Group Z (unconditional, before any override):
        - Exact match in BLEND_HEADER_EXACT_NAMES
        - Exact match in EXCLUDED_LABEL_PHRASES (e.g., "Contains less than 2%")
        - Exact match in EXCLUDED_NUTRITION_FACTS (e.g., "Other Omega-3 Fatty Acids")

        Skip Group A (high confidence):
        - isAdditive == true
        - additiveType is present
        - isNestedIngredient under non-therapeutic parent

        Skip Group B (header rows):
        - Matches blend/proprietary header patterns AND has no dosage
        - Matches blend/proprietary header patterns AND has only total weight
        - proprietaryBlend == true + LOW-CONFIDENCE pattern match (even with dose)

        Override (keep scorable):
        - Exists in quality_map or botanicals_db
        - Has potency markers

        Returns skip_reason string if should skip, None if scorable.
        """
        ing_name = ingredient.get('name', '')
        std_name = ingredient.get('standardName', '') or ing_name
        name_lower = ing_name.lower().strip()
        std_lower = std_name.lower().strip()
        name_norm = self._normalize_exclusion_text(ing_name)
        std_norm = self._normalize_exclusion_text(std_name)
        raw_source = ingredient.get('raw_source_text', '')

        # =================================================================
        # GROUP Z: Unconditional skips — these are NEVER real ingredients.
        # No quality_map / potency override can rescue them.
        # =================================================================

        # Z1: Known label-level blend names should always be treated as headers.
        if name_norm in BLEND_HEADER_EXACT_NAMES or std_norm in BLEND_HEADER_EXACT_NAMES:
            return SKIP_REASON_BLEND_HEADER_WITH_WEIGHT

        # Z2/Z3: Excluded label phrases and nutrition-fact rollups.
        for text in (ing_name, std_name, raw_source, name_lower, std_lower):
            exclusion_reason = self._excluded_text_reason(text)
            if exclusion_reason:
                return exclusion_reason

        # =================================================================
        # STRUCTURAL BLEND CHECK: Containers with nested children are never
        # individually scored — even if the name is a known therapeutic.
        # "Full Spectrum Turmeric Blend" (nested: Turmeric Extract, Turmeric
        # Root) must be skipped; its dose is the total blend weight, not an
        # individual ingredient dose.  This check intentionally runs BEFORE
        # the therapeutic override below.
        # =================================================================
        nested_pre = ingredient.get('nestedIngredients') or []
        ingredient_group_pre = (ingredient.get('ingredientGroup', '') or '').lower()
        if isinstance(nested_pre, list) and nested_pre and 'blend' in ingredient_group_pre:
            has_dose_pre, _ = self._has_valid_therapeutic_dose(ingredient)
            return (
                SKIP_REASON_BLEND_HEADER_WITH_WEIGHT if has_dose_pre
                else SKIP_REASON_BLEND_HEADER_NO_DOSE
            )

        # =================================================================
        # OVERRIDE CHECK: If known in quality map or botanicals, always score
        # =================================================================
        if self._is_known_therapeutic(ing_name, std_name, quality_map, botanicals_db):
            return None

        # Deterministic role split: recognized non-scorable identities are skipped.
        # This prevents excipients/label technologies from inflating unmapped actives.
        recognized = self._is_recognized_non_scorable(ing_name, std_name)
        if recognized:
            return SKIP_REASON_RECOGNIZED_NON_SCORABLE

        # OVERRIDE CHECK: If has potency markers in name, always score
        if self._has_potency_markers(ing_name):
            return None

        # =================================================================
        # GROUP A: Structural flags from cleaning
        # =================================================================

        # A1: Check isAdditive flag
        if ingredient.get('isAdditive', False):
            return SKIP_REASON_ADDITIVE

        # A2: Check additiveType
        additive_type = ingredient.get('additiveType', '')
        if additive_type and additive_type.lower() in ADDITIVE_TYPES_SKIP_SCORING:
            return SKIP_REASON_ADDITIVE_TYPE

        # A3: Check nested under non-therapeutic parent
        if ingredient.get('isNestedIngredient', False):
            parent_blend = ingredient.get('parentBlend', '')
            if parent_blend and parent_blend.lower().strip() in NON_THERAPEUTIC_PARENT_DENYLIST:
                return SKIP_REASON_NESTED_NON_THERAPEUTIC
            # Nested rows inside proprietary blends without dose are usually label artifacts.
            has_dose_nested, _ = self._has_valid_therapeutic_dose(ingredient)
            ingredient_group = (ingredient.get('ingredientGroup', '') or '').lower()
            if not has_dose_nested and (
                ingredient.get('proprietaryBlend', False)
                or ('blend' in ingredient_group)
                or bool(parent_blend)
            ):
                return SKIP_REASON_NESTED_NON_THERAPEUTIC

        # =================================================================
        # GROUP B: Blend header pattern matching
        # =================================================================
        has_dose, is_blend_weight = self._has_valid_therapeutic_dose(ingredient)

        # B1: Structured blend headers with nested components should never be scored.
        ingredient_group = (ingredient.get('ingredientGroup', '') or '').lower()
        nested = ingredient.get('nestedIngredients') or []
        if isinstance(nested, list) and nested and ('blend' in ingredient_group):
            return SKIP_REASON_BLEND_HEADER_WITH_WEIGHT if has_dose else SKIP_REASON_BLEND_HEADER_NO_DOSE

        # B1b: Strong structural blend container signal from cleaning.
        # Some labels emit non-nested container rows (e.g., "Rice Protein Matrix and Polyphenols")
        # with proprietary flags and blend-like group tags, which should not enter A1/mapping gate.
        is_non_nested = not bool(ingredient.get('isNestedIngredient', False))
        has_proprietary_flag = bool(
            ingredient.get('proprietaryBlend', False) or ingredient.get('isProprietaryBlend', False)
        )
        group_signals_blend = any(
            token in ingredient_group for token in ('blend', 'proprietary')
        )
        if is_non_nested and has_proprietary_flag and group_signals_blend:
            return SKIP_REASON_BLEND_HEADER_WITH_WEIGHT if has_dose else SKIP_REASON_BLEND_HEADER_NO_DOSE

        # B2: HIGH-CONFIDENCE patterns: skip regardless of dose
        for pattern in BLEND_HEADER_PATTERNS_HIGH_CONFIDENCE:
            if re.search(pattern, name_lower, re.IGNORECASE):
                if not has_dose:
                    return SKIP_REASON_BLEND_HEADER_NO_DOSE
                else:
                    return SKIP_REASON_BLEND_HEADER_WITH_WEIGHT

        # B3: LOW-CONFIDENCE patterns — skip if no dose
        if not has_dose:
            for pattern in BLEND_HEADER_PATTERNS_LOW_CONFIDENCE:
                if re.search(pattern, name_lower, re.IGNORECASE):
                    return SKIP_REASON_BLEND_HEADER_NO_DOSE

        # B4: LOW-CONFIDENCE patterns WITH dose — skip if structural evidence
        # says this is a blend header carrying total weight, not a real active.
        # Evidence: proprietaryBlend flag, ingredientGroup contains "blend",
        # or hierarchyType indicates summary/header.
        is_structural_blend = (
            ingredient.get('proprietaryBlend', False)
            or ingredient.get('isProprietaryBlend', False)
            or ('blend' in ingredient_group and 'blend' not in name_lower.split()[-1:])
        )
        hierarchy_type = ingredient.get('hierarchyType', '')
        is_header_hierarchy = hierarchy_type in ('summary', 'source', 'blend_header')

        if has_dose and (is_structural_blend or is_header_hierarchy):
            for pattern in BLEND_HEADER_PATTERNS_LOW_CONFIDENCE:
                if re.search(pattern, name_lower, re.IGNORECASE):
                    return SKIP_REASON_BLEND_HEADER_WITH_WEIGHT

        return None

    def _should_promote_to_scorable(self, ingredient: Dict, quality_map: Dict,
                                     botanicals_db: Dict,
                                     current_scorable_count: int) -> Optional[Dict]:
        """
        Determine if an inactive ingredient should be PROMOTED to scorable.

        TWO-FACTOR PROMOTION (prevents excipient backdoors):
        - RULE A: Known therapeutic (single factor - high confidence)
        - RULE B: Has dose AND therapeutic signal (two factors required)
        - RULE C: Absorption enhancer exception (specific allowlist)
        - RULE D: Product-type rescue (very conservative, low confidence)

        Hard exclusions:
        - Label phrases and nutrition facts (never real ingredients)
        - Blend header exact names
        - Common excipients (EXCIPIENT_NEVER_PROMOTE)
        - isAdditive == true

        Returns dict with {reason, confidence} if should promote, None otherwise.
        """
        ing_name = ingredient.get('name', '')
        std_name = ingredient.get('standardName', '') or ing_name
        name_lower = ing_name.lower().strip()
        std_lower = std_name.lower().strip()
        name_norm = self._normalize_exclusion_text(ing_name)
        std_norm = self._normalize_exclusion_text(std_name)
        raw_source = ingredient.get('raw_source_text', '')

        # HARD EXCLUSION: Label phrases, nutrition facts, blend headers
        # These are never real ingredients — block before any promotion rule.
        for text in (ing_name, std_name, raw_source, name_lower, std_lower):
            if self._excluded_text_reason(text):
                return None
        if name_norm in BLEND_HEADER_EXACT_NAMES or std_norm in BLEND_HEADER_EXACT_NAMES:
            return None
        for pattern in BLEND_HEADER_PATTERNS_HIGH_CONFIDENCE:
            if re.search(pattern, name_lower, re.IGNORECASE):
                return None

        # RULE C: Absorption enhancer exception (checked BEFORE hard exclusions)
        # These are therapeutically relevant even without dose
        is_absorption_enhancer = self._is_absorption_enhancer(name_lower, std_lower)
        if is_absorption_enhancer:
            return {
                "reason": PROMOTE_REASON_ABSORPTION_ENHANCER,
                "confidence": "LOW"  # Low confidence because no dose specified
            }

        # HARD EXCLUSION: isAdditive flag
        if ingredient.get('isAdditive', False):
            return None

        # HARD EXCLUSION: Known excipients
        # P0 FIX: Only check ing_name (name_lower), NOT std_name (std_lower).
        # DSLD assigns misleading standardNames (e.g., "natural colors" for elderberry).
        # Checking std_name causes false negatives for real botanicals in inactiveIngredients.
        # Consistent with the same guard in _compute_excipient_flags and _is_recognized_non_scorable.
        if name_lower in EXCIPIENT_NEVER_PROMOTE:
            return None

        # Check for partial matches in excipient list (ing_name only)
        for excipient in EXCIPIENT_NEVER_PROMOTE:
            if excipient in name_lower:
                return None

        # RULE A: Known therapeutic ingredient (single factor - high confidence)
        is_known = self._is_known_therapeutic(
            ing_name, std_name, quality_map, botanicals_db
        )
        if is_known:
            return {
                "reason": PROMOTE_REASON_KNOWN_DB,
                "confidence": "HIGH"
            }

        # RULE B: TWO-FACTOR - Has dose AND therapeutic signal
        # Dose alone is not sufficient (prevents "2g sorbitol" backdoor)
        # Use validated dose check instead of simple truthiness
        has_dose, _ = self._has_valid_therapeutic_dose(ingredient)
        has_high_signal = self._has_high_signal_potency(ing_name)
        has_therapeutic_signal = self._has_therapeutic_signal(ing_name, std_name)

        if has_dose and (has_high_signal or has_therapeutic_signal):
            return {
                "reason": PROMOTE_REASON_HAS_DOSE,
                "confidence": "MEDIUM"
            }

        # High-signal markers alone (without explicit dose) - still decent signal
        if has_high_signal:
            return {
                "reason": PROMOTE_REASON_HAS_DOSE,
                "confidence": "LOW"
            }

        # RULE D: Product-type rescue (only when scorable count is very low)
        # More restrictive: must look like a specific botanical, not just "extract"
        if current_scorable_count <= 1:
            botanical_parts = [
                'root', 'leaf', 'herb', 'flower', 'berry',
                'fruit', 'seed', 'bark', 'rhizome', 'bulb'
            ]
            # Must have a plant part indicator, not just "extract"
            if any(part in name_lower for part in botanical_parts):
                return {
                    "reason": PROMOTE_REASON_PRODUCT_TYPE_RESCUE,
                    "confidence": "LOW"
                }

        return None

    def _is_absorption_enhancer(self, name_lower: str, std_lower: str) -> bool:
        """
        Check if ingredient is a known absorption enhancer.

        These are therapeutically relevant for bioavailability and
        should be promoted even without explicit dose.
        """
        # Check exact matches
        if name_lower in ABSORPTION_ENHANCERS_PROMOTE_EXCEPTION:
            return True
        if std_lower in ABSORPTION_ENHANCERS_PROMOTE_EXCEPTION:
            return True

        # Check partial matches for common absorption enhancers
        # (e.g., "BioPerine® black pepper extract" should match "black pepper extract")
        for enhancer in ABSORPTION_ENHANCERS_PROMOTE_EXCEPTION:
            # Only check if enhancer is a multi-word term (avoid false positives)
            if ' ' in enhancer:
                if enhancer in name_lower or enhancer in std_lower:
                    return True

        # Check for specific branded absorption enhancers
        branded_enhancers = ['bioperine', 'piperine']
        for brand in branded_enhancers:
            if brand in name_lower or brand in std_lower:
                return True

        return False

    def _has_therapeutic_signal(self, ing_name: str, std_name: str) -> bool:
        """
        Check if ingredient has signals indicating it's therapeutic, not excipient.
        Used as second factor for promotion decisions.
        """
        text = f"{ing_name} {std_name}".lower()

        # Botanical/therapeutic indicators (excluding bare "extract")
        therapeutic_patterns = [
            r'\b(vitamin|mineral|amino\s*acid|probiotic|enzyme)\b',
            r'\b(root|leaf|herb|flower|berry|fruit|seed|bark)\b',
            r'\b(powder|capsule|tablet)\s+(of|from)\b',
            r'\b(standardized|concentrated)\b',
            r'\b\d+:\d+\b',  # Extract ratios
        ]

        for pattern in therapeutic_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        return False

    def _is_known_therapeutic(self, ing_name: str, std_name: str,
                               quality_map: Dict, botanicals_db: Dict) -> bool:
        """Check if ingredient exists in therapeutic databases."""
        # Check quality map
        quality_match = self._match_quality_map(ing_name, std_name, quality_map)
        if quality_match and quality_match.get("match_status") != "FORM_UNMAPPED":
            return True

        # Check botanicals database
        # IMPORTANT: Normalize BOTH input and DB values consistently
        # to handle trademarks, whitespace, etc.
        ing_norm = self._normalize_text(ing_name)
        std_norm = self._normalize_text(std_name)

        botanicals_list = None
        if isinstance(botanicals_db, dict):
            botanicals_list = botanicals_db.get('standardized_botanicals')

        if isinstance(botanicals_list, list):
            for data in botanicals_list:
                if not isinstance(data, dict):
                    continue
                # Normalize DB values the same way as input
                bot_name = self._normalize_text(data.get('standard_name', ''))
                aliases = [self._normalize_text(a) for a in data.get('aliases', [])]

                if ing_norm == bot_name or std_norm == bot_name:
                    return True
                if ing_norm in aliases or std_norm in aliases:
                    return True
            return False

        # Fallback: iterate dict directly (legacy DB format)
        if isinstance(botanicals_db, dict):
            for key, data in botanicals_db.items():
                if key.startswith("_") or not isinstance(data, dict):
                    continue

                bot_name = self._normalize_text(data.get('standard_name', key))
                aliases = [self._normalize_text(a) for a in data.get('aliases', [])]

                if ing_norm == bot_name or std_norm == bot_name:
                    return True
                if ing_norm in aliases or std_norm in aliases:
                    return True

        return False

    def _is_recognized_non_scorable(self, ing_name: str, std_name: str) -> Optional[Dict]:
        """
        Check if ingredient is recognized in non-scorable databases.

        TIERED MATCHING (per dev feedback):
        - Tier 1: quality_map → scorable bioactive
        - Tier 2: botanicals → recognized (scorable if modeled)
        - Tier 3: other_ingredients → recognized_non_scorable (THIS METHOD)
        - Tier 4: excipient_list → recognized_non_scorable
        - Tier 5: unmatched

        This prevents oils, food powders, and carriers from counting as
        "unmapped ingredients" and inflating the unmapped count.

        Returns:
            Dict with recognition_source and reason if recognized, None otherwise.
        """
        # ── FAST PATH: O(1) index lookup before expensive variant generation ──
        if self._nonscorable_index:
            # Check ing_name directly (most common hit)
            ing_norm = self._normalize_text(ing_name)
            if ing_norm in self._nonscorable_index:
                return dict(self._nonscorable_index[ing_norm])

            # Check std_name (unless it's an excipient descriptor)
            std_name_norm = self._normalize_text(std_name)
            if std_name_norm not in EXCIPIENT_NEVER_PROMOTE:
                if std_name_norm in self._nonscorable_index:
                    return dict(self._nonscorable_index[std_name_norm])

            # Check preprocessed variants for quick wins
            ing_pre = norm_module.preprocess_text(ing_name)
            ing_pre_norm = self._normalize_text(ing_pre)
            if ing_pre_norm and ing_pre_norm in self._nonscorable_index:
                return dict(self._nonscorable_index[ing_pre_norm])

            # Strip parenthetical groups (common pattern: "Oregano (Origanum vulgare)")
            ing_no_parens = self._normalize_text(re.sub(r"\([^)]*\)", " ", ing_name))
            if ing_no_parens and ing_no_parens in self._nonscorable_index:
                return dict(self._nonscorable_index[ing_no_parens])
        # ── END FAST PATH — fall through to full variant scan if no hit ──

        def _variants(value: str) -> List[str]:
            base = self._normalize_text(value)
            pre = norm_module.preprocess_text(value)
            variants = {base, self._normalize_text(pre)}
            # Strip parenthetical groups for identity matching.
            variants.add(self._normalize_text(re.sub(r"\([^)]*\)", " ", value)))
            # Strip leading dosage wrappers occasionally leaked into name fields.
            variants.add(
                self._normalize_text(
                    re.sub(
                        r"^\s*\d+(?:\.\d+)?\s*(?:mg|mcg|g|iu|cfu)\b\s*",
                        "",
                        re.sub(r"[{}\[\]]", " ", value),
                        flags=re.IGNORECASE,
                    )
                )
            )
            # Strip inline quantity tokens (e.g., "... 24 mg hydroethanolic extract").
            variants.add(
                self._normalize_text(
                    re.sub(
                        r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|iu|cfu)\b",
                        " ",
                        re.sub(r"[{}\[\]]", " ", value),
                        flags=re.IGNORECASE,
                    )
                )
            )
            # Strip percentage + "whole" prefix commonly found in fruit extracts.
            variants.add(re.sub(r'^\d+(?:\.\d+)?%\s*whole\s+', '', base).strip())
            variants.add(re.sub(r'^\d+(?:\.\d+)?%\s*whole\s+', '', self._normalize_text(pre)).strip())
            # Strip benign qualifiers for identity-only recognition.
            variants.add(re.sub(r'^(?:organic|natural|raw|pure)\s+', '', base).strip())
            variants.add(re.sub(r'^(?:organic|natural|raw|pure)\s+', '', self._normalize_text(pre)).strip())
            # Strip common processing qualifiers that should not block identity matching.
            for v in list(variants):
                stripped = re.sub(
                    r'\b(cold[-\s]?pressed|extra virgin|unrefined|certified organic|virgin)\b',
                    '',
                    v,
                    flags=re.IGNORECASE
                ).strip()
                variants.add(re.sub(r'\s+', ' ', stripped).strip())
            # Reorder comma suffix qualifiers: "pumpkin seed oil, cold-pressed" -> "cold-pressed pumpkin seed oil"
            for v in list(variants):
                if ',' not in v:
                    continue
                parts = [p.strip() for p in v.split(',') if p and p.strip()]
                if len(parts) >= 2:
                    variants.add(' '.join(parts[1:] + parts[:1]))
            # Strip common botanical plant-part suffixes for identity-only recognition.
            for v in list(variants):
                variants.add(re.sub(r'\b(root|leaf|fruit|seed|flower|bark)\b', '', v).strip())
            return [v for v in variants if v]

        # Guard: don't include std_name in candidates when it's a known excipient/category
        # descriptor. DSLD sometimes assigns standardName="natural colors" to botanical
        # actives (e.g., elderberry), which would falsely match NHA_NATURAL_COLORS if
        # std_name variants were included.
        std_name_norm = self._normalize_text(std_name)
        if std_name_norm in EXCIPIENT_NEVER_PROMOTE:
            candidates = set(_variants(ing_name))
        else:
            candidates = set(_variants(ing_name) + _variants(std_name))

        # Check other_ingredients.json
        other_db = self.databases.get('other_ingredients', {})
        other_list = other_db.get('other_ingredients', []) if isinstance(other_db, dict) else []

        for entry in other_list:
            if not isinstance(entry, dict):
                continue
            entry_name = self._normalize_text(entry.get('standard_name', ''))
            entry_aliases = [self._normalize_text(a) for a in entry.get('aliases', [])]
            entry_variants = set(_variants(entry.get('standard_name', '')))
            for alias in entry.get('aliases', []):
                entry_variants.update(_variants(alias))

            if entry_name in candidates or any(v in candidates for v in entry_variants):
                return {
                    "recognition_source": "other_ingredients",
                    "recognition_reason": entry.get('category', 'other_ingredient'),
                    "matched_entry_id": entry.get('id'),
                    "matched_entry_name": entry.get('standard_name'),
                    "recognition_type": "non_scorable",
                }

        # Check harmful_additives DB for known additive identities.
        harmful_db = self.databases.get('harmful_additives', {})
        harmful_list = harmful_db.get('harmful_additives', []) if isinstance(harmful_db, dict) else []
        for entry in harmful_list:
            if not isinstance(entry, dict):
                continue
            entry_variants = set(_variants(entry.get('standard_name', '')))
            for alias in entry.get('aliases', []):
                entry_variants.update(_variants(alias))
            if any(v in candidates for v in entry_variants):
                return {
                    "recognition_source": "harmful_additives",
                    "recognition_reason": "known_additive",
                    "matched_entry_id": entry.get('id'),
                    "matched_entry_name": entry.get('standard_name'),
                    "recognition_type": "non_scorable",
                }

        # Check botanical identity DB (recognized identity, but not quality-scored yet).
        botanical_db = self.databases.get('botanical_ingredients', {})
        botanical_list = botanical_db.get('botanical_ingredients', []) if isinstance(botanical_db, dict) else []
        for entry in botanical_list:
            if not isinstance(entry, dict):
                continue
            entry_variants = set(_variants(entry.get('standard_name', '')))
            for alias in entry.get('aliases', []):
                entry_variants.update(_variants(alias))
            if any(v in candidates for v in entry_variants):
                return {
                    "recognition_source": "botanical_ingredients",
                    "recognition_reason": entry.get('category', 'botanical'),
                    "matched_entry_id": entry.get('id'),
                    "matched_entry_name": entry.get('standard_name'),
                    "recognition_type": "botanical_unscored",
                }

        # Check standardized_botanicals DB as identity-only fallback.
        standardized_db = self.databases.get('standardized_botanicals', {})
        standardized_list = standardized_db.get('standardized_botanicals', []) if isinstance(standardized_db, dict) else []
        for entry in standardized_list:
            if not isinstance(entry, dict):
                continue
            entry_variants = set(_variants(entry.get('standard_name', '')))
            for alias in entry.get('aliases', []):
                entry_variants.update(_variants(alias))
            if any(v in candidates for v in entry_variants):
                return {
                    "recognition_source": "standardized_botanicals",
                    "recognition_reason": "botanical_identity",
                    "matched_entry_id": entry.get('id'),
                    "matched_entry_name": entry.get('standard_name'),
                    "recognition_type": "botanical_unscored",
                }

        # Check banned_recalled_ingredients DB for identity-only recognition.
        # Prevents banned items from inflating the unmapped count.
        banned_db = self.databases.get('banned_recalled_ingredients', {})
        banned_list = banned_db.get('ingredients', []) if isinstance(banned_db, dict) else []
        for entry in banned_list:
            if not isinstance(entry, dict):
                continue
            # Skip non-matchable entity types (products, classes, threats)
            entity_type = entry.get('entity_type', 'ingredient')
            if entity_type not in {'ingredient', 'contaminant', None, ''}:
                continue
            entry_variants = set(_variants(entry.get('standard_name', '')))
            for alias in entry.get('aliases', []):
                entry_variants.update(_variants(alias))
            if any(v in candidates for v in entry_variants):
                return {
                    "recognition_source": "banned_recalled_ingredients",
                    "recognition_reason": "banned",
                    "matched_entry_id": entry.get('id'),
                    "matched_entry_name": entry.get('standard_name'),
                    "recognition_type": "non_scorable",
                }

        # Check against EXCIPIENT_NEVER_PROMOTE constant list
        # Only check ing_name (the label-facing name), NOT std_name.
        # DSLD sometimes assigns a category std_name like "natural colors" to botanical
        # actives (e.g., elderberry), and using std_name here would falsely classify
        # them as excipients. This mirrors the P0 fix in _compute_excipient_flags.
        name_lower = ing_name.lower().strip()

        if name_lower in EXCIPIENT_NEVER_PROMOTE:
            return {
                "recognition_source": "excipient_list",
                "recognition_reason": "known_excipient",
                "matched_entry_id": None,
                "matched_entry_name": name_lower,
                "recognition_type": "non_scorable",
            }

        # Check for partial matches (e.g., "organic sunflower oil" matches "sunflower oil")
        # Only match against ing_name — std_name is excluded for the same reason as above.
        for excipient in EXCIPIENT_NEVER_PROMOTE:
            if excipient in name_lower:
                return {
                    "recognition_source": "excipient_list",
                    "recognition_reason": "known_excipient_partial",
                    "matched_entry_id": None,
                    "matched_entry_name": excipient,
                    "recognition_type": "non_scorable",
                }

        return None

    def _has_high_signal_potency(self, text: str) -> bool:
        """
        Check if text contains HIGH-SIGNAL potency markers.
        These are strong indicators of therapeutic ingredients.
        """
        text_lower = text.lower()
        for pattern in POTENCY_MARKERS_HIGH_SIGNAL:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True
        return False

    def _has_potency_markers(self, text: str) -> bool:
        """
        Check if text contains any potency/dose markers (high or low signal).
        Used for skip override decisions in Pass 1.
        """
        # High-signal markers are always valid
        if self._has_high_signal_potency(text):
            return True

        # Low-signal markers only count with additional context
        # (handled by caller with _has_therapeutic_signal)
        return False

    # Category keyword map for unmapped ingredients (name-based inference)
    _CATEGORY_KEYWORDS = {
        "vitamins": [
            "vitamin", "retinol", "thiamine", "riboflavin", "niacin", "pantothenic",
            "pyridoxine", "biotin", "folate", "folic acid", "cobalamin", "ascorbic",
            "cholecalciferol", "ergocalciferol", "tocopherol", "phylloquinone",
            "menaquinone", "methylcobalamin", "methylfolate", "mthf",
        ],
        "minerals": [
            "calcium", "magnesium", "zinc", "iron", "copper", "manganese",
            "chromium", "selenium", "molybdenum", "potassium", "iodine", "boron",
            "vanadium", "phosphorus", "silica", "silicon", "lithium",
        ],
        "probiotics": [
            "probiotic", "lactobacillus", "bifidobacterium", "streptococcus",
            "bacillus", "saccharomyces", "limosilactobacillus", "lacticaseibacillus",
            "lactiplantibacillus", "cfu", "billion organisms",
        ],
        "amino_acids": [
            "l-glutamine", "l-lysine", "l-arginine", "l-carnitine", "l-theanine",
            "l-tryptophan", "l-tyrosine", "l-cysteine", "l-methionine", "l-leucine",
            "l-isoleucine", "l-valine", "l-proline", "l-serine", "l-histidine",
            "l-alanine", "l-glycine", "amino acid", "bcaa", "taurine", "creatine",
            "beta-alanine", "citrulline", "ornithine", "glutathione",
        ],
        "herbs": [
            "ashwagandha", "turmeric", "ginseng", "echinacea", "valerian",
            "ginkgo", "milk thistle", "rhodiola", "elderberry", "saw palmetto",
            "garlic", "oregano", "cinnamon", "ginger", "chamomile", "passionflower",
            "holy basil", "fenugreek", "astragalus", "cat's claw", "boswellia",
            "root extract", "leaf extract", "bark extract", "herb extract",
            "herbal", "botanical", "plant extract",
        ],
        "fatty_acids": [
            "omega-3", "omega-6", "omega 3", "omega 6", "fish oil", "dha",
            "epa", "flaxseed oil", "evening primrose", "borage oil", "krill oil",
            "cod liver oil", "cla", "conjugated linoleic",
        ],
        "enzymes": [
            "enzyme", "protease", "lipase", "amylase", "cellulase", "lactase",
            "bromelain", "papain", "serrapeptase", "nattokinase", "coq10",
            "coenzyme q10", "ubiquinol", "ubiquinone",
        ],
        "antioxidants": [
            "quercetin", "resveratrol", "lycopene", "lutein", "zeaxanthin",
            "astaxanthin", "alpha lipoic acid", "pycnogenol", "grape seed extract",
        ],
        "fibers": [
            "fiber", "fibre", "psyllium", "inulin", "fos", "prebiotic",
            "pectin", "glucomannan",
        ],
    }

    @staticmethod
    def _infer_category_from_name(ing_name: str, std_name: str = "") -> str:
        """Infer ingredient category from name when IQM match is unavailable.

        Used for unmapped ingredients so that supplement type classification
        (_classify_supplement_type) gets useful category data instead of 'unknown'.
        """
        text = f"{ing_name} {std_name}".lower()
        for category, keywords in SupplementEnricherV3._CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    return category
        return "unknown"

    def _build_quality_entry(self, ingredient: Dict, match_result: Optional[Dict],
                              hierarchy_type: Optional[str], source_section: str = "active",
                              promotion_reason: str = None, promotion_confidence: str = None,
                              dose_present: bool = None) -> Dict:
        """Build a quality data entry for an ingredient.

        LABEL NAME PRESERVATION:
        - raw_source_text: Exact label text (provenance)
        - name: User-facing label name (may be slightly cleaned)
        - standard_name: Canonical name from database (internal matching)
        """
        ing_name = ingredient.get('name', '')
        std_name = ingredient.get('standardName', '') or ing_name
        # LABEL NAME PRESERVATION: Track exact label text for audit
        raw_source_text = ingredient.get('raw_source_text') or ing_name
        quantity = ingredient.get('quantity', 0)
        unit = ingredient.get('unit', '')
        has_dose, _ = self._has_valid_therapeutic_dose(ingredient)
        unit_normalized = self._normalize_unit_for_signal(unit)
        is_excipient, never_promote_reason = self._compute_excipient_flags(ingredient)
        blend_flags = self._compute_blend_flags(ingredient, None)
        is_form_unmapped = bool(
            match_result and isinstance(match_result, dict) and match_result.get("match_status") == "FORM_UNMAPPED"
        )

        if is_form_unmapped:
            entry = {
                "name": ing_name,
                "raw_source_text": raw_source_text,
                "standard_name": match_result.get("base_name", std_name),
                "matched_form": None,
                "canonical_id": None,
                "form_id": None,
                "match_tier": None,
                "matched_alias": None,
                "matched_target": None,
                "match_ambiguity_candidates": [],
                "bio_score": None,
                "natural": None,
                "score": 9,
                "absorption": None,
                "notes": None,
                "dosage_importance": 1.0,
                "category": self._infer_category_from_name(ing_name, std_name),
                "quantity": quantity,
                "unit": unit,
                "unit_normalized": unit_normalized,
                "has_dose": has_dose,
                "is_blend_header": blend_flags["is_blend_header"],
                "is_proprietary_blend": blend_flags["is_proprietary_blend"],
                "blend_total_weight_only": blend_flags["blend_total_weight_only"],
                "blend_disclosed_components_count": blend_flags["blend_disclosed_components_count"],
                "is_excipient": is_excipient,
                "never_promote_reason": never_promote_reason,
                "certificates": [],
                "mapped": False,
                "mapped_identity": False,
                "scoreable_identity": False,
                "role_classification": "active_unmapped",
                "identity_confidence": 0.0,
                "identity_decision_reason": "form_unmapped",
                "safety_hits": [],
                "hierarchyType": hierarchy_type,
                "source_section": source_section,
                "is_nested_ingredient": bool(ingredient.get("isNestedIngredient", False)),
                "parent_blend": ingredient.get("parentBlend"),
                "is_parent_total": False,
                "form_extraction_used": True,
                "is_dual_form": bool(match_result.get("is_dual_form")),
                "original_label": match_result.get("original_label"),
                "extracted_forms": match_result.get("extracted_forms", []),
                "matched_forms": [],
                "unmapped_forms": match_result.get("unmapped_forms", []),
                "aggregation_method": None,
                "final_form_bio_score": None,
                "additional_forms": [],
                "form_source": match_result.get("form_source"),
            }
        elif match_result:
            bio_score = match_result.get('bio_score', 5)
            natural = match_result.get('natural', False)
            score = match_result.get('score', bio_score + (3 if natural else 0))
            used_form_fallback = match_result.get('match_status') == 'FORM_UNMAPPED_FALLBACK'

            # Track form fallbacks for audit report
            if used_form_fallback:
                unmapped_forms = match_result.get('unmapped_forms', [])
                fallback_form_name = match_result.get('form_name', '(unspecified)')
                self._form_fallback_details.append({
                    "ingredient_label": ing_name,
                    "raw_source_text": raw_source_text,
                    "canonical_id": match_result.get('canonical_id', ''),
                    "parent_name": match_result.get('standard_name', ''),
                    "unmapped_form_text": ', '.join(unmapped_forms) if unmapped_forms else ing_name,
                    "fallback_form": fallback_form_name,
                    "fallback_bio_score": bio_score,
                    "fallback_score": score,
                    "forms_differ": bool(unmapped_forms and fallback_form_name not in [
                        f.lower().strip() for f in unmapped_forms
                    ]),
                    "form_source": match_result.get('form_source', ''),
                    "source_section": source_section,
                })

            entry = {
                # LABEL NAME PRESERVATION:
                "name": ing_name,  # Label-facing name (user-visible)
                "raw_source_text": raw_source_text,  # Exact label text (provenance)
                "standard_name": match_result.get('standard_name', std_name),  # Canonical
                "matched_form": match_result.get('form_name', 'standard'),
                "canonical_id": match_result.get('canonical_id'),
                "form_id": match_result.get('form_id'),
                "match_tier": match_result.get('match_tier'),
                "matched_alias": match_result.get('matched_alias'),
                "matched_target": match_result.get('matched_target'),
                "match_ambiguity_candidates": match_result.get('match_ambiguity_candidates', []),
                "bio_score": bio_score,
                "natural": natural,
                "score": score,
                "absorption": match_result.get('absorption'),
                "notes": match_result.get('notes'),
                "dosage_importance": match_result.get('dosage_importance', 1.0),
                "category": match_result.get('category', 'other'),
                "quantity": quantity,
                "unit": unit,
                "unit_normalized": unit_normalized,
                "has_dose": has_dose,
                "is_blend_header": blend_flags["is_blend_header"],
                "is_proprietary_blend": blend_flags["is_proprietary_blend"],
                "blend_total_weight_only": blend_flags["blend_total_weight_only"],
                "blend_disclosed_components_count": blend_flags["blend_disclosed_components_count"],
                "is_excipient": is_excipient,
                "never_promote_reason": never_promote_reason,
                "certificates": [],
                "mapped": True,
                "mapped_identity": True,
                "scoreable_identity": True,
                "role_classification": "active_scorable",
                "identity_confidence": 0.8 if used_form_fallback else (1.0 if match_result.get('match_tier') == "exact" else 0.9),
                "identity_decision_reason": "form_unmapped_fallback" if used_form_fallback else "quality_map_match",
                "safety_hits": [],
                "hierarchyType": hierarchy_type,
                "source_section": source_section,
                "is_nested_ingredient": bool(ingredient.get("isNestedIngredient", False)),
                "parent_blend": ingredient.get("parentBlend"),
                "is_parent_total": False,
                # Multi-form contract fields (if present)
                "form_extraction_used": match_result.get('form_extraction_used', False),
                "is_dual_form": match_result.get('is_dual_form', False),
                "original_label": match_result.get('original_label'),
                "extracted_forms": match_result.get('extracted_forms', []),
                "matched_forms": match_result.get('matched_forms', []),
                "unmapped_forms": match_result.get('unmapped_forms', []),
                "aggregation_method": match_result.get('aggregation_method'),
                "final_form_bio_score": match_result.get('final_form_bio_score'),
                "additional_forms": match_result.get('additional_forms', []),
                "form_source": match_result.get('form_source'),
                "form_unmapped": bool(used_form_fallback),
            }
        else:
            entry = {
                # LABEL NAME PRESERVATION:
                "name": ing_name,  # Label-facing name (user-visible)
                "raw_source_text": raw_source_text,  # Exact label text (provenance)
                "standard_name": std_name,  # No canonical match
                "matched_form": None,
                "canonical_id": None,
                "form_id": None,
                "match_tier": None,
                "matched_alias": None,
                "matched_target": None,
                "match_ambiguity_candidates": [],
                "bio_score": None,
                "natural": None,
                "score": 9,  # Neutral midpoint fallback for unmapped
                "absorption": None,
                "notes": None,
                "dosage_importance": 1.0,
                "category": self._infer_category_from_name(ing_name, std_name),
                "quantity": quantity,
                "unit": unit,
                "unit_normalized": unit_normalized,
                "has_dose": has_dose,
                "is_blend_header": blend_flags["is_blend_header"],
                "is_proprietary_blend": blend_flags["is_proprietary_blend"],
                "blend_total_weight_only": blend_flags["blend_total_weight_only"],
                "blend_disclosed_components_count": blend_flags["blend_disclosed_components_count"],
                "is_excipient": is_excipient,
                "never_promote_reason": never_promote_reason,
                "certificates": [],
                "mapped": False,
                "mapped_identity": False,
                "scoreable_identity": False,
                "role_classification": "active_unmapped",
                "identity_confidence": 0.0,
                "identity_decision_reason": "no_quality_map_match",
                "safety_hits": [],
                "hierarchyType": hierarchy_type,
                "source_section": source_section,
                "is_nested_ingredient": bool(ingredient.get("isNestedIngredient", False)),
                "parent_blend": ingredient.get("parentBlend"),
                "is_parent_total": False,
            }

        # Add promotion metadata if applicable
        if promotion_reason:
            entry["promotion_reason"] = promotion_reason
            entry["promotion_confidence"] = promotion_confidence
            entry["dose_present"] = dose_present

        return entry

    def _mark_parent_total_rows(self, ingredients_scorable: List[Dict[str, Any]]) -> None:
        """
        Mark parent nutrient total rows to prevent A1 double-counting.

        A parent total row is flagged when:
        1) It is a top-level active row (is_nested_ingredient=False), and
        2) A nested active child in the same canonical_id group points back to
           this row via parent_blend.
        """
        canonical_groups: Dict[str, List[Dict[str, Any]]] = {}
        for ing in ingredients_scorable:
            canonical_id = ing.get("canonical_id")
            if not canonical_id:
                continue
            canonical_groups.setdefault(str(canonical_id), []).append(ing)

        for group in canonical_groups.values():
            if len(group) <= 1:
                continue

            parent_blend_names = set()
            for ing in group:
                if ing.get("source_section") != "active":
                    continue
                if not bool(ing.get("is_nested_ingredient", False)):
                    continue
                parent_blend = self._normalize_text(ing.get("parent_blend", "") or "")
                if parent_blend:
                    parent_blend_names.add(parent_blend)

            if not parent_blend_names:
                continue

            for ing in group:
                if ing.get("source_section") != "active":
                    continue
                if bool(ing.get("is_nested_ingredient", False)):
                    continue
                ing_name = self._normalize_text(ing.get("name", "") or "")
                if ing_name and ing_name in parent_blend_names:
                    ing["is_parent_total"] = True

    def _match_multi_form(self, form_info: Dict, quality_map: Dict) -> Optional[Dict]:
        """
        Match multiple extracted forms and aggregate scores using weighted average.

        Multi-Form Contract:
        - extracted_forms: list of form info dicts from extraction
        - matched_forms: list of {form_key, bio_score, natural, match_method, percent_share}
        - unmapped_forms: list of raw strings that failed to match
        - aggregation_method: 'weighted' | 'equal' | 'single'
        - final_form_bio_score: numeric (0-15) - the aggregated score

        Returns None if no forms match successfully.
        """
        extracted_forms = form_info.get('extracted_forms', [])
        if not extracted_forms:
            return None

        # Derive preferred_parent from base ingredient name.
        # This resolves compound forms (e.g., "calcium ascorbate") that exist
        # under multiple parents — the parent matching the base ingredient wins.
        preferred_parent = None
        base_name = form_info.get('base_name', '')
        if base_name:
            preferred_parent = self._infer_preferred_parent_from_context_cached(
                base_name, quality_map
            )

        matched_forms = []
        unmapped_forms = []
        generic_form_tokens = []

        for form_data in extracted_forms:
            match_candidates = form_data.get('match_candidates', [])
            percent_share = form_data.get('percent_share', 1.0 / max(1, len(extracted_forms)))
            raw_form_text = form_data.get('raw_form_text', '')

            # Try each match candidate until one succeeds
            form_match = None
            matched_candidate = None
            matched_unspecified = False
            for candidate in match_candidates:
                form_match = self._match_quality_map(
                    candidate, candidate, quality_map, _form_extraction_attempt=True,
                    preferred_parent=preferred_parent
                )
                if form_match:
                    form_id = form_match.get('form_id', '')
                    # Accept if it's a specific form (not unspecified)
                    if form_id and 'unspecified' not in form_id.lower():
                        matched_candidate = candidate
                        break
                    else:
                        # Generic/source descriptors frequently resolve to
                        # unspecified forms (e.g., "fish oil" for DHA/EPA).
                        # Track these separately to avoid false form-loss flags.
                        matched_unspecified = True
                        form_match = None

            if form_match and matched_candidate:
                bio_score = form_match.get('bio_score', 5)
                natural = form_match.get('natural', False)
                # Use pre-computed score from database, fall back to calculation only if missing
                score = form_match.get('score', bio_score + (3 if natural else 0))
                matched_forms.append({
                    'form_key': form_match.get('form_id'),
                    'canonical_id': form_match.get('canonical_id'),
                    'bio_score': bio_score,
                    'natural': natural,
                    'score': score,  # Pre-computed from database
                    'match_method': form_match.get('match_tier', 'unknown'),
                    'matched_candidate': matched_candidate,
                    'percent_share': percent_share,
                    'raw_form_text': raw_form_text,
                    'full_match_data': form_match
                })
            else:
                if matched_unspecified:
                    generic_form_tokens.append(raw_form_text)
                else:
                    unmapped_forms.append(raw_form_text)
                    # Track unmapped form for database expansion
                    base_name = form_info.get('base_name', '')
                    original_label = form_info.get('original', '')
                    if raw_form_text:
                        self._track_unmapped_form(raw_form_text, base_name, original_label)

        # If no forms matched, return None (let caller handle FORM_UNMAPPED)
        if not matched_forms:
            if generic_form_tokens and not unmapped_forms:
                # All form tokens were generic/source descriptors that only
                # resolved to unspecified forms; treat as no actionable form
                # evidence and continue with parent matching.
                return {
                    'all_forms_generic': True,
                    'generic_form_tokens': generic_form_tokens,
                    'unmapped_forms': [],
                    'form_extraction_used': True,
                }
            return None

        # Determine aggregation method
        if len(matched_forms) == 1:
            aggregation_method = 'single'
        elif any(f.get('percent_share') != matched_forms[0].get('percent_share') for f in matched_forms):
            aggregation_method = 'weighted'
        else:
            aggregation_method = 'equal'

        # Calculate weighted average of bio_score and score
        total_weight = sum(f['percent_share'] for f in matched_forms)
        if total_weight > 0:
            final_bio_score = sum(
                f['bio_score'] * f['percent_share'] for f in matched_forms
            ) / total_weight
            # Use pre-computed score from database (weighted average)
            final_score = sum(
                f['score'] * f['percent_share'] for f in matched_forms
            ) / total_weight
        else:
            if matched_forms:
                final_bio_score = sum(f['bio_score'] for f in matched_forms) / len(matched_forms)
                final_score = sum(f['score'] for f in matched_forms) / len(matched_forms)
            else:
                final_bio_score = 5.0  # Conservative fallback (unspecified)
                final_score = 5.0

        # Round to 1 decimal place for consistency
        final_bio_score = round(final_bio_score, 1)
        final_score = round(final_score, 1)

        # Use primary form (first matched) as the base for canonical fields
        primary_match = matched_forms[0]['full_match_data']

        # Build result with multi-form contract
        result = {
            # Standard match fields (from primary)
            'canonical_id': primary_match.get('canonical_id'),
            'form_id': primary_match.get('form_id'),
            'standard_name': primary_match.get('standard_name'),
            'form_name': primary_match.get('form_name'),
            'category': primary_match.get('category'),
            'absorption': primary_match.get('absorption'),
            'notes': primary_match.get('notes'),
            'dosage_importance': primary_match.get('dosage_importance', 1.0),
            'match_tier': primary_match.get('match_tier'),
            'matched_alias': primary_match.get('matched_alias'),
            'matched_target': primary_match.get('matched_target'),

            # Aggregated scores (using pre-computed scores from database)
            'bio_score': final_bio_score,
            'natural': any(f['natural'] for f in matched_forms),  # Natural if any form is natural
            'score': final_score,  # Pre-computed weighted average from database scores

            # Multi-form contract fields
            'form_extraction_used': True,
            'original_label': form_info.get('original'),
            'is_dual_form': form_info.get('is_dual_form', False),
            'extracted_forms': form_info.get('extracted_forms', []),
            'matched_forms': [
                {
                    'form_key': f['form_key'],
                    'canonical_id': f['canonical_id'],
                    'bio_score': f['bio_score'],
                    'natural': f['natural'],
                    'score': f['score'],  # Pre-computed from database
                    'match_method': f['match_method'],
                    'percent_share': f['percent_share'],
                    'raw_form_text': f['raw_form_text'],
                    'matched_candidate': f['matched_candidate']
                }
                for f in matched_forms
            ],
            'unmapped_forms': unmapped_forms,
            'aggregation_method': aggregation_method,
            'final_form_bio_score': final_bio_score,

            # Additional forms beyond primary (for transparency)
            'additional_forms': [
                {
                    'form_key': f['form_key'],
                    'bio_score': f['bio_score'],
                    'score': f['score'],  # Pre-computed from database
                    'percent_share': f['percent_share']
                }
                for f in matched_forms[1:]
            ] if len(matched_forms) > 1 else []
        }

        return result

    def _build_form_info_from_cleaned(self, ing_name: str, cleaned_forms: List[Dict]) -> Optional[Dict]:
        """
        Build a form_info dict from the cleaning stage's structured forms[] array.

        This bridges the gap between the cleaning stage (which parses
        "Vitamin A (as Retinyl Palmitate)" into forms[]) and the enricher's
        _match_multi_form() which expects a form_info dict.

        Args:
            ing_name: The ingredient name (e.g., "Vitamin A")
            cleaned_forms: List of form dicts from cleaning, e.g.:
                [{"name": "Retinyl Palmitate", "percent": null, "order": 1}]

        Returns:
            form_info dict compatible with _match_multi_form(), or None if
            cleaned_forms has no usable entries.
        """
        if not cleaned_forms:
            return None

        # Pre-pass: identify "from"-prefix forms and link them as source hints to
        # the preceding form.  A form with prefix "from" (e.g. "L-5-Methyltetrahydrofolic
        # Acid" with prefix="from" following "Glucosamine Salt") describes the SOURCE
        # MATERIAL the compound is derived from, not an independent chemical form.
        # Adding the source name as a high-priority match candidate lets the IQM
        # resolve the biologically-active compound rather than the salt/carrier.
        _FROM_PREFIXES = frozenset({'from', 'From', 'from '})
        from_source_map: Dict[int, str] = {}  # index → source name
        for i, form in enumerate(cleaned_forms):
            if form.get('prefix', '') in _FROM_PREFIXES and i > 0:
                src = (form.get('name') or '').strip()
                if src:
                    from_source_map[i - 1] = src

        extracted_forms = []
        for i, form in enumerate(cleaned_forms):
            # Skip forms that are source descriptors (prefix "from"):
            # their names are already inserted as priority candidates for the
            # preceding form via from_source_map.
            if form.get('prefix', '') in _FROM_PREFIXES:
                continue

            form_name = form.get('name', '')
            if not form_name or not form_name.strip():
                continue

            # Build match candidates.  If a "from"-source exists for this form,
            # prepend it so the biologically-active acid is tried before the
            # salt/carrier name.
            match_candidates = []
            if i in from_source_map:
                source_name = from_source_map[i]
                match_candidates.append(source_name)
                stripped_src = source_name.strip()
                if stripped_src != source_name:
                    match_candidates.append(stripped_src)

            # Then try the form name itself + common variations
            match_candidates.append(form_name)
            # Also try lowercase and stripped version
            stripped = form_name.strip()
            if stripped != form_name:
                match_candidates.append(stripped)
            # Normalize wrapper punctuation often emitted by cleaning.
            unwrapped = re.sub(r'[\{\}\[\]]', '', stripped)
            unwrapped = re.sub(r'\(([^)]+)\)', r'\1', unwrapped)
            unwrapped = re.sub(r'\s+', ' ', unwrapped).strip()
            if unwrapped and unwrapped not in match_candidates:
                match_candidates.append(unwrapped)

            # BRANDED PREFIX RECONSTRUCTION: When the ingredient name is a bare
            # branded prefix (e.g. "MicroActive") and the form is the actual
            # compound (e.g. "Melatonin"), try "MicroActive Melatonin" as a
            # combined candidate.  This enables IQM alias matching for branded
            # delivery technologies whose label text was split by the cleaner.
            combined = f"{ing_name} {form_name}".strip()
            combined_lower = combined.lower()
            if (combined_lower != form_name.lower().strip()
                    and combined_lower != ing_name.lower().strip()
                    and combined not in match_candidates):
                match_candidates.append(combined)

            # Convert percent field: cleaning uses None or a float (0-100)
            percent_raw = form.get('percent')
            percent_share = None
            if percent_raw is not None:
                try:
                    percent_share = float(percent_raw) / 100.0
                except (TypeError, ValueError):
                    pass

            extracted_forms.append({
                'raw_form_text': form_name,
                'match_candidates': match_candidates,
                'display_form': form_name,
                'percent_share': percent_share,
            })

        if not extracted_forms:
            return None

        # Compute equal shares for forms without explicit percentages
        forms_without_pct = [f for f in extracted_forms if f['percent_share'] is None]
        forms_with_pct = [f for f in extracted_forms if f['percent_share'] is not None]
        total_explicit = sum(f['percent_share'] for f in forms_with_pct)
        remaining = max(0.0, 1.0 - total_explicit)

        if forms_without_pct:
            equal_share = remaining / len(forms_without_pct)
            for f in forms_without_pct:
                f['percent_share'] = equal_share

        return {
            'original': ing_name,
            'base_name': ing_name,
            'extracted_forms': extracted_forms,
            'is_dual_form': len(extracted_forms) > 1,
            'form_extraction_success': True,
            'has_form_evidence': True,
        }

    def _match_quality_map(self, ing_name: str, std_name: str, quality_map: Dict,
                           _form_extraction_attempt: bool = False,
                           cleaned_forms: Optional[List[Dict]] = None,
                           preferred_parent: Optional[str] = None) -> Optional[Dict]:
        """
        Match ingredient against quality map using explicit precedence rules.

        Precedence (highest to lowest):
        1. Form-level exact match (name/alias)
        2. Parent-level exact match (name/alias)
        3. Form-level normalized match
        4. Parent-level normalized match
        5. Form-level pattern/contains match (if present in DB)
        6. Parent-level pattern/contains match (if present in DB)

        Tie-breakers (within same tier):
        1. Context parent preference (when available)
        2. Longest matched alias wins
        3. Form-level outranks parent-level (if applicable)
        4. Canonical key alphabetical
        5. Form key alphabetical

        Multi-Form Enhancement:
        - Uses pre-parsed cleaned_forms[] from cleaning stage when available
        - Falls back to label text extraction via _extract_form_from_label()
        - For dual-form ingredients, matches ALL forms and uses weighted average
        - Preserves bracket tokens as match candidates
        - If form evidence exists but mapping fails, marks as FORM_UNMAPPED (not unspecified)

        Args:
            ing_name: Ingredient name from label
            std_name: Standardized name
            quality_map: Quality map database
            _form_extraction_attempt: Internal flag to prevent recursion
            cleaned_forms: Pre-parsed forms[] from cleaning stage, e.g.
                           [{"name": "Retinyl Palmitate", "percent": None, ...}]

        Logs structured warnings when multiple candidates exist in the winning tier.
        """
        # MULTI-FORM MATCHING: Try structured cleaned_forms first, then fall back
        # to label text extraction. This fixes the "form loss" issue where cleaning
        # already parsed "Vitamin A (as Retinyl Palmitate)" into forms[] but the
        # enricher was only seeing "Vitamin A".
        if not _form_extraction_attempt:
            # PRIORITY 1: Use cleaned_forms[] from cleaning stage (structured, reliable)
            if cleaned_forms and isinstance(cleaned_forms, list) and len(cleaned_forms) > 0:
                form_info = self._build_form_info_from_cleaned(ing_name, cleaned_forms)
                if form_info and form_info.get('form_extraction_success'):
                    multi_form_result = self._match_multi_form(form_info, quality_map)
                    if multi_form_result:
                        if not multi_form_result.get('all_forms_generic'):
                            return multi_form_result

                    # If form evidence exists but ALL forms failed to match
                    if form_info.get('has_form_evidence') and not (
                        multi_form_result and multi_form_result.get('all_forms_generic')
                    ):
                        # Fallback: try parent/base matching so product can still score
                        # conservatively while preserving form-unmapped telemetry.
                        fallback_base = form_info.get('base_name') or ing_name
                        fallback_match = self._match_quality_map(
                            fallback_base, std_name, quality_map, _form_extraction_attempt=True
                        )
                        if fallback_match:
                            fallback = dict(fallback_match)
                            fallback['match_status'] = 'FORM_UNMAPPED_FALLBACK'
                            fallback['has_form_evidence'] = True
                            fallback['original_label'] = ing_name
                            fallback['extracted_forms'] = form_info['extracted_forms']
                            fallback['unmapped_forms'] = [f['raw_form_text'] for f in form_info['extracted_forms']]
                            fallback['base_name'] = form_info['base_name']
                            fallback['form_source'] = 'cleaned_forms'
                            fallback['form_extraction_used'] = True
                            return fallback
                        return {
                            'match_status': 'FORM_UNMAPPED',
                            'has_form_evidence': True,
                            'original_label': ing_name,
                            'extracted_forms': form_info['extracted_forms'],
                            'unmapped_forms': [f['raw_form_text'] for f in form_info['extracted_forms']],
                            'base_name': form_info['base_name'],
                            'form_source': 'cleaned_forms',
                        }

            # PRIORITY 2: Fall back to label text extraction (for labels with "(as ...)")
            form_info = self._extract_form_from_label(ing_name)
            if form_info['form_extraction_success']:
                multi_form_result = self._match_multi_form(form_info, quality_map)
                if multi_form_result:
                    if not multi_form_result.get('all_forms_generic'):
                        return multi_form_result

                # If form evidence exists but ALL forms failed to match, mark as FORM_UNMAPPED
                if form_info['has_form_evidence'] and not (
                    multi_form_result and multi_form_result.get('all_forms_generic')
                ):
                    fallback_base = form_info.get('base_name') or ing_name
                    fallback_match = self._match_quality_map(
                        fallback_base, std_name, quality_map, _form_extraction_attempt=True
                    )
                    if fallback_match:
                        fallback = dict(fallback_match)
                        fallback['match_status'] = 'FORM_UNMAPPED_FALLBACK'
                        fallback['has_form_evidence'] = True
                        fallback['original_label'] = ing_name
                        fallback['extracted_forms'] = form_info['extracted_forms']
                        fallback['unmapped_forms'] = [f['raw_form_text'] for f in form_info['extracted_forms']]
                        fallback['base_name'] = form_info['base_name']
                        fallback['form_source'] = 'label_extraction'
                        fallback['form_extraction_used'] = True
                        return fallback
                    return {
                        'match_status': 'FORM_UNMAPPED',
                        'has_form_evidence': True,
                        'original_label': ing_name,
                        'extracted_forms': form_info['extracted_forms'],
                        'unmapped_forms': [f['raw_form_text'] for f in form_info['extracted_forms']],
                        'base_name': form_info['base_name'],
                        'form_source': 'label_extraction',
                    }

        ing_exact = self._normalize_exact_text(ing_name)
        std_exact = self._normalize_exact_text(std_name)
        ing_norm = self._normalize_text(ing_name)
        std_norm = self._normalize_text(std_name)

        # Also try base name without parenthetical content or trailing dosages for matching
        # This handles labels like:
        # - "Vitamin K1 (Phylloquinone)" where form extraction doesn't trigger (no "as" keyword)
        # - "Beta-Glucan 250mg" where there's a trailing dosage
        base_name = None
        if not _form_extraction_attempt:
            form_info = self._extract_form_from_label(ing_name)
            base_name = form_info.get('base_name')

            # Also strip trailing dosage/percentage patterns if base_name still has them
            # Patterns like "250mg", "500 mg", "1000mcg", "5g", "98%", "10 Billion CFU", etc.
            if base_name:
                # First strip dosage with units
                stripped = re.sub(
                    r'\s+\d+(?:\.\d+)?\s*(?:mg|mcg|ug|µg|g|kg|ml|l|iu|billion|million|cfu)\s*$',
                    '', base_name, flags=re.IGNORECASE
                ).strip()
                # Also strip trailing percentage (e.g., "98%", "80%")
                stripped = re.sub(r'\s+\d+(?:\.\d+)?\s*%\s*$', '', stripped).strip()
                if stripped and stripped != base_name:
                    base_name = stripped

        def _resolve_compound_parent_override(
            ing_norm_value: str,
            std_norm_value: str,
            base_norm_value: Optional[str],
        ) -> Optional[str]:
            """
            Resolve known cross-parent compound forms without alphabetical tie-breaks.

            Example: "niacinamide ascorbate" appears under vitamin_b3_niacin and vitamin_c.
            If no explicit context is available, default to vitamin_c (ascorbate-bearing form).
            """
            blob = " ".join(
                x for x in (ing_norm_value, std_norm_value, base_norm_value or "") if x
            )
            compound_tokens = (
                "niacinamide ascorbate",
                "nicotinamide ascorbate",
                "ascorbate niacinamide",
            )
            if not any(token in blob for token in compound_tokens):
                return None

            context_blob = " ".join(x for x in (std_norm_value, base_norm_value or "") if x)
            if re.search(r"\b(niacin|vitamin b3)\b", context_blob):
                return "vitamin_b3_niacin"
            if re.search(r"\b(vitamin c|ascorbic acid|ascorbate)\b", context_blob):
                return "vitamin_c"

            # Default when context is missing or mixed.
            return "vitamin_c"

        # If caller didn't pass a parent context, infer from standardized/base names.
        # This prevents deterministic-but-wrong alphabetical picks when one form exists
        # under multiple parents (e.g., calcium pantothenate under calcium and B5).
        if not preferred_parent:
            for context_name in (std_name, base_name, ing_name):
                inferred_parent = self._infer_preferred_parent_from_context_cached(
                    context_name, quality_map
                )
                if inferred_parent:
                    preferred_parent = inferred_parent
                    break

        # If base name is different from full name, include it in matching candidates
        base_exact = self._normalize_exact_text(base_name) if base_name else None
        base_norm = self._normalize_text(base_name) if base_name else None

        # Compound-form override for known cross-parent aliases when context is absent.
        if not preferred_parent:
            preferred_parent = _resolve_compound_parent_override(ing_norm, std_norm, base_norm)

        candidates = []
        seen = set()

        def _strip_parenthesis_chars(value: str) -> str:
            # Keep parenthetical content but remove bracket characters.
            # Example: "Oregano (Origanum vulgare) (leaf)" -> "Oregano Origanum vulgare leaf"
            return re.sub(r"[()\[\]]", " ", value or "")

        def _strip_parenthetical_groups(value: str) -> str:
            # Drop parenthetical groups entirely.
            # Example: "Red Raspberry (Rubus idaeus) powder" -> "Red Raspberry powder"
            return re.sub(r"\([^)]*\)", " ", value or "")

        def _strip_leading_quantity_prefix(value: str) -> str:
            # Drop leading quantity wrappers leaked from label fragments.
            # Example: "30 mg {Garlic} hydroethanolic extract" -> "Garlic hydroethanolic extract"
            text = re.sub(r"[{}\[\]]", " ", value or "")
            text = re.sub(r"^\s*\d+(?:\.\d+)?\s*(?:mg|mcg|g|iu|cfu)\b\s*", "", text, flags=re.IGNORECASE)
            return text

        def _strip_inline_quantity_tokens(value: str) -> str:
            # Drop inline dose tokens that are identity-irrelevant.
            # Example: "Commiphora ... 24 mg hydroethanolic extract" -> "Commiphora ... hydroethanolic extract"
            text = re.sub(r"[{}\[\]]", " ", value or "")
            text = re.sub(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|iu|cfu)\b", " ", text, flags=re.IGNORECASE)
            return re.sub(r"\s+", " ", text).strip()

        def _comma_reorder(value: str) -> str:
            # Handle qualifier suffixes like "Garlic Bulb Extract, Odorless"
            # so they can match aliases like "Odorless Garlic Bulb Extract".
            text = value or ""
            if "," not in text:
                return text
            parts = [p.strip() for p in text.split(",") if p and p.strip()]
            if len(parts) < 2:
                return text
            return " ".join(parts[1:] + parts[:1])

        def _build_exact_candidates() -> List[Tuple[str, int]]:
            out: Dict[str, int] = {}

            def add(value: Optional[str], source: int):
                if not value:
                    return
                normed = self._normalize_exact_text(value)
                if not normed:
                    return
                if normed not in out or source < out[normed]:
                    out[normed] = source

            add(ing_name, 0)
            add(std_name, 1)
            add(base_name, 2)
            return sorted(out.items(), key=lambda item: item[1])

        def _build_normalized_candidates() -> List[Tuple[str, int]]:
            out: Dict[str, int] = {}

            def add(value: Optional[str], source: int):
                if not value:
                    return
                variants = {
                    value,
                    _strip_parenthesis_chars(value),
                    _strip_parenthetical_groups(value),
                    _strip_leading_quantity_prefix(value),
                    _strip_inline_quantity_tokens(value),
                    _strip_leading_quantity_prefix(_strip_parenthesis_chars(value)),
                    _strip_leading_quantity_prefix(_strip_parenthetical_groups(value)),
                    _strip_inline_quantity_tokens(_strip_parenthesis_chars(value)),
                    _strip_inline_quantity_tokens(_strip_parenthetical_groups(value)),
                }
                for v in list(variants):
                    variants.add(_comma_reorder(v))
                for v in variants:
                    normed = self._normalize_text(v)
                    if not normed:
                        continue
                    if normed not in out or source < out[normed]:
                        out[normed] = source

            add(ing_name, 0)
            add(std_name, 1)
            add(base_name, 2)
            return sorted(out.items(), key=lambda item: item[1])

        exact_candidates = _build_exact_candidates()
        normalized_candidates = _build_normalized_candidates()

        def alias_length(match_type: str, alias: str) -> int:
            if match_type == "exact":
                return len(self._normalize_exact_text(alias))
            return len(self._normalize_text(alias))

        def build_form_match_data(
            parent_key: str, parent_data: Dict, form_name: str, form_data: Dict
        ) -> Dict:
            def _as_float(value, default):
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return default

            def _coerce_dosage_importance(value) -> float:
                if isinstance(value, (int, float)):
                    return float(value)
                if isinstance(value, str):
                    normalized = value.strip().lower()
                    str_map = {
                        "primary": 1.5,
                        "high": 1.5,
                        "major": 1.5,
                        "secondary": 1.0,
                        "moderate": 1.0,
                        "medium": 1.0,
                        "normal": 1.0,
                        "trace": 0.5,
                        "low": 0.5,
                        "minor": 0.5,
                    }
                    if normalized in str_map:
                        return str_map[normalized]
                return 1.0

            review_status = str((parent_data.get("data_quality") or {}).get("review_status", "")).strip().lower()
            low_confidence_review = review_status in {"stub", "pending", "needs_review"}

            bio_score = _as_float(form_data.get('bio_score', 5), 5.0)
            natural = bool(form_data.get('natural', False))
            expected_score = bio_score + (3.0 if natural else 0.0)
            score = _as_float(form_data.get('score', expected_score), expected_score)

            # Conservative runtime cap for provisional IQM entries until validated.
            # Prevents provisional records from receiving premium-form credit.
            if low_confidence_review:
                bio_score = min(bio_score, 10.0)
                score = min(score, 10.0)

            return {
                "canonical_id": parent_key,
                "form_id": form_name,
                "standard_name": parent_data.get('standard_name', parent_key),
                "form_name": form_name,
                "bio_score": bio_score,
                "natural": natural,
                "score": score,
                "absorption": form_data.get('absorption'),
                "notes": form_data.get('notes'),
                "dosage_importance": _coerce_dosage_importance(form_data.get('dosage_importance', 1.0)),
                "category": parent_data.get('category', 'other'),
            }

        def build_parent_match_data(parent_key: str, parent_data: Dict) -> Tuple[Dict, bool, Optional[str]]:
            forms = parent_data.get('forms', {})
            if forms:
                def _norm(value: str) -> str:
                    return str(value or "").strip().lower()

                def _select_conservative_parent_form(forms_dict: Dict) -> Tuple[str, Dict]:
                    """
                    Select a conservative fallback form for parent-level matches.

                    Best-practice policy:
                    1) If label text clearly indicates a preparation (e.g., powder/oil),
                       prefer the corresponding non-premium form when available.
                    2) Otherwise prefer explicit unspecified/default forms when actual form
                       is unknown.
                    3) Otherwise choose the lowest-score form to avoid premium over-credit.
                    """
                    preferred_tokens = ("unspecified", "unknown", "generic", "default")

                    input_norm = f"{_norm(ing_name)} {_norm(std_name)}".strip()
                    hint_tokens = {
                        "powder": ("powder", "particulate", "meal"),
                        "oil": ("oil",),
                    }

                    def _form_matches_hint(form_name: str, form_data: Dict, hint: str) -> bool:
                        form_norm = _norm(form_name)
                        if hint in form_norm:
                            return True
                        for alias in form_data.get("aliases", []) or []:
                            if hint in _norm(alias):
                                return True
                        return False

                    def _score_key(item: Tuple[str, Dict]) -> Tuple[float, str]:
                        form_name, form_data = item
                        score = form_data.get("score")
                        bio = form_data.get("bio_score")
                        try:
                            numeric = float(score if score is not None else bio if bio is not None else 5.0)
                        except (TypeError, ValueError):
                            numeric = 5.0
                        return numeric, _norm(form_name)

                    for hint, tokens in hint_tokens.items():
                        if any(token in input_norm for token in tokens):
                            hinted_matches = [
                                (form_name, form_data)
                                for form_name, form_data in forms_dict.items()
                                if _form_matches_hint(form_name, form_data, hint)
                            ]
                            if hinted_matches:
                                for form_name, form_data in hinted_matches:
                                    normalized = _norm(form_name)
                                    if any(token in normalized for token in preferred_tokens):
                                        return form_name, form_data
                                return min(hinted_matches, key=_score_key)

                    for form_name, form_data in forms_dict.items():
                        normalized = _norm(form_name)
                        if any(token in normalized for token in preferred_tokens):
                            return form_name, form_data

                    return min(forms_dict.items(), key=_score_key)

                selected_form_name, selected_form = _select_conservative_parent_form(forms)
                return (
                    build_form_match_data(parent_key, parent_data, selected_form_name, selected_form),
                    True,
                    selected_form_name
                )
            return (
                {
                    "canonical_id": parent_key,
                    "form_id": None,
                    "standard_name": parent_data.get('standard_name', parent_key),
                    "form_name": "standard",
                    "bio_score": 5,
                    "natural": False,
                    "score": 5,
                    "absorption": None,
                    "notes": None,
                    "dosage_importance": 1.0,
                    "category": parent_data.get('category', 'other'),
                },
                False,
                None
            )

        def add_candidate(candidate: Dict):
            key = (
                candidate["parent_key"],
                candidate["form_key"],
                candidate["matched_alias"],
                candidate["match_type"],
                candidate["tier"],
            )
            if key in seen:
                return
            seen.add(key)
            candidates.append(candidate)

        def collect_alias_matches(
            candidate_values: List[Tuple[str, int]],
            target_name: str,
            aliases: List[str],
            normalize_fn,
            match_type: str,
            match_scope: str,
        ) -> List[Dict]:
            matches = []

            if target_name:
                target_norm = normalize_fn(target_name)
                if target_norm:
                    source_hits = [source for value, source in candidate_values if value == target_norm]
                    if source_hits:
                        matches.append({
                            "matched_alias": target_name,
                            "matched_on": f"{match_scope}_name",
                            "alias_len": alias_length(match_type, target_name),
                            "match_source": min(source_hits),
                        })
            for alias in aliases:
                alias_norm = normalize_fn(alias)
                if not alias_norm:
                    continue
                source_hits = [source for value, source in candidate_values if value == alias_norm]
                if source_hits:
                    matches.append({
                        "matched_alias": alias,
                        "matched_on": f"{match_scope}_alias",
                        "alias_len": alias_length(match_type, alias),
                        "match_source": min(source_hits),
                    })
            return matches

        def collect_pattern_matches(
            ing_text: str,
            std_text: str,
            ing_norm_text: str,
            std_norm_text: str,
            pattern_aliases: List[str],
            contains_aliases: List[str],
            match_scope: str,
        ) -> List[Dict]:
            matches = []
            if pattern_aliases:
                for pattern in pattern_aliases:
                    try:
                        if re.search(pattern, ing_text, re.I) or re.search(pattern, std_text, re.I):
                            matches.append({
                                "matched_alias": pattern,
                                "matched_on": f"{match_scope}_pattern",
                                "alias_len": alias_length("pattern", pattern),
                            })
                    except re.error:
                        self.logger.warning(f"Invalid regex pattern '{pattern}' in {match_scope} pattern aliases")
            if contains_aliases:
                for phrase in contains_aliases:
                    phrase_norm = self._normalize_text(phrase)
                    if not phrase_norm:
                        continue
                    if phrase_norm in ing_norm_text or phrase_norm in std_norm_text:
                        matches.append({
                            "matched_alias": phrase,
                            "matched_on": f"{match_scope}_contains",
                            "alias_len": alias_length("pattern", phrase),
                        })
            return matches

        # ── PERFORMANCE: Pre-filter parents using index ──
        # Instead of scanning all 498 parents, use the index to find only
        # parents whose aliases match any of our candidate values.
        # This reduces the inner loop from O(498) to O(matched_parents) (~1-5 typically).
        _candidate_parent_keys = set()
        _use_index_filter = (quality_map is self.databases.get('ingredient_quality_map', {}))
        if _use_index_filter and self._iqm_exact_index:
            for cand_val, _ in exact_candidates:
                for entry in self._iqm_exact_index.get(cand_val, []):
                    _candidate_parent_keys.add(entry[0])  # parent_key
            for cand_val, _ in normalized_candidates:
                for entry in self._iqm_norm_index.get(cand_val, []):
                    _candidate_parent_keys.add(entry[0])  # parent_key
            # Pattern/contains aliases can't be indexed, so if no exact/norm hits,
            # fall back to full scan to allow pattern matches
            if not _candidate_parent_keys:
                _use_index_filter = False
            else:
                # SAFETY: Parents with contains_aliases or pattern_aliases must
                # never be skipped by the index filter, since their matching
                # paths use substring/regex which cannot be pre-indexed.
                # (Only ~4 parents currently; negligible cost.)
                for _pk, _pd in quality_map.items():
                    if _pk.startswith("_") or not isinstance(_pd, dict):
                        continue
                    if _pd.get('contains_aliases') or _pd.get('pattern_aliases'):
                        _candidate_parent_keys.add(_pk)

        for parent_key, parent_data in quality_map.items():
            if parent_key.startswith("_") or not isinstance(parent_data, dict):
                continue

            # Skip parents not in the pre-filtered set (index-accelerated path)
            if _use_index_filter and parent_key not in _candidate_parent_keys:
                continue

            # Extract match_rules for this parent
            match_rules = parent_data.get('match_rules', {})
            parent_priority = match_rules.get('priority', 1)  # Default to secondary priority
            parent_match_mode = match_rules.get('match_mode', 'alias_and_fuzzy')
            parent_exclusions = match_rules.get('exclusions', [])

            # Check exclusions: if any exclusion term is found in the input, skip this parent
            # This prevents false positives (e.g., "ferric oxide" shouldn't match "iron")
            if parent_exclusions:
                input_text_lower = f"{ing_name} {std_name}".lower()
                excluded = False
                for exclusion in parent_exclusions:
                    excl_lower = exclusion.lower()
                    # Token-bounded check: word boundary match
                    if re.search(r'\b' + re.escape(excl_lower) + r'\b', input_text_lower):
                        excluded = True
                        break
                if excluded:
                    continue  # Skip this parent entirely

            normalized_match_mode = str(parent_match_mode or "alias_and_fuzzy").strip().lower()
            legacy_mode_map = {
                "standard": "exact",
                "alias": "normalized",
            }
            normalized_match_mode = legacy_mode_map.get(normalized_match_mode, normalized_match_mode)
            if normalized_match_mode not in {"exact", "normalized", "alias_and_fuzzy"}:
                normalized_match_mode = "normalized"

            # match_mode gates which tiers are allowed
            # exact: only tier 1,2 (exact matches)
            # normalized: tier 1,2,3,4 (exact + normalized)
            # alias_and_fuzzy: all tiers (exact + normalized + contains/pattern)
            allowed_tiers = {1, 2, 3, 4, 5, 6}  # Default: all
            if normalized_match_mode == 'exact':
                allowed_tiers = {1, 2}
            elif normalized_match_mode == 'normalized':
                allowed_tiers = {1, 2, 3, 4}
            # alias_and_fuzzy allows all tiers (default)

            forms = parent_data.get('forms', {})
            parent_std_name = parent_data.get('standard_name', parent_key)
            parent_aliases = parent_data.get('aliases', [])
            parent_pattern_aliases = parent_data.get('pattern_aliases', [])
            parent_contains_aliases = parent_data.get('contains_aliases', [])

            # Form-level matches
            for form_name, form_data in forms.items():
                form_aliases = form_data.get('aliases', [])
                form_pattern_aliases = form_data.get('pattern_aliases', [])
                form_contains_aliases = form_data.get('contains_aliases', [])

                exact_matches = collect_alias_matches(
                    exact_candidates, form_name, form_aliases,
                    self._normalize_exact_text, "exact", "form"
                )
                for match in exact_matches:
                    if 1 in allowed_tiers:  # Tier gate
                        add_candidate({
                            "parent_key": parent_key,
                            "form_key": form_name,
                            "matched_on": match["matched_on"],
                            "matched_alias": match["matched_alias"],
                            "match_type": "exact",
                            "tier": 1,
                            "alias_len": match["alias_len"],
                            "match_source": match.get("match_source", 1),
                            "priority": parent_priority,  # From match_rules
                            "fallback_form_selected": False,
                            "fallback_form_name": None,
                            "match_data": build_form_match_data(parent_key, parent_data, form_name, form_data),
                        })

                normalized_matches = collect_alias_matches(
                    normalized_candidates, form_name, form_aliases,
                    self._normalize_text, "normalized", "form"
                )
                for match in normalized_matches:
                    if 3 in allowed_tiers:  # Tier gate
                        add_candidate({
                            "parent_key": parent_key,
                            "form_key": form_name,
                            "matched_on": match["matched_on"],
                            "matched_alias": match["matched_alias"],
                            "match_type": "normalized",
                            "tier": 3,
                            "alias_len": match["alias_len"],
                            "match_source": match.get("match_source", 1),
                            "priority": parent_priority,  # From match_rules
                            "fallback_form_selected": False,
                            "fallback_form_name": None,
                            "match_data": build_form_match_data(parent_key, parent_data, form_name, form_data),
                        })

                pattern_matches = collect_pattern_matches(
                    ing_name, std_name, ing_norm, std_norm,
                    form_pattern_aliases, form_contains_aliases, "form"
                )
                for match in pattern_matches:
                    if 5 in allowed_tiers:  # Tier gate
                        add_candidate({
                            "parent_key": parent_key,
                            "form_key": form_name,
                            "matched_on": match["matched_on"],
                            "matched_alias": match["matched_alias"],
                            "match_type": "pattern",
                            "tier": 5,
                            "alias_len": match["alias_len"],
                            "priority": parent_priority,  # From match_rules
                            "fallback_form_selected": False,
                            "fallback_form_name": None,
                            "match_data": build_form_match_data(parent_key, parent_data, form_name, form_data),
                        })

            # Parent-level matches
            exact_matches = collect_alias_matches(
                exact_candidates, parent_std_name, parent_aliases,
                self._normalize_exact_text, "exact", "parent"
            )
            for match in exact_matches:
                if 2 in allowed_tiers:  # Tier gate
                    match_data, fallback_selected, fallback_form = build_parent_match_data(parent_key, parent_data)
                    add_candidate({
                        "parent_key": parent_key,
                        "form_key": None,
                        "matched_on": match["matched_on"],
                        "matched_alias": match["matched_alias"],
                        "match_type": "exact",
                        "tier": 2,
                        "alias_len": match["alias_len"],
                        "match_source": match.get("match_source", 1),
                        "priority": parent_priority,  # From match_rules
                        "fallback_form_selected": fallback_selected,
                        "fallback_form_name": fallback_form,
                        "match_data": match_data,
                    })

            normalized_matches = collect_alias_matches(
                normalized_candidates, parent_std_name, parent_aliases,
                self._normalize_text, "normalized", "parent"
            )
            for match in normalized_matches:
                if 4 in allowed_tiers:  # Tier gate
                    match_data, fallback_selected, fallback_form = build_parent_match_data(parent_key, parent_data)
                    add_candidate({
                        "parent_key": parent_key,
                        "form_key": None,
                        "matched_on": match["matched_on"],
                        "matched_alias": match["matched_alias"],
                        "match_type": "normalized",
                        "tier": 4,
                        "alias_len": match["alias_len"],
                        "match_source": match.get("match_source", 1),
                        "priority": parent_priority,  # From match_rules
                        "fallback_form_selected": fallback_selected,
                        "fallback_form_name": fallback_form,
                        "match_data": match_data,
                    })

            pattern_matches = collect_pattern_matches(
                ing_name, std_name, ing_norm, std_norm,
                parent_pattern_aliases, parent_contains_aliases, "parent"
            )
            for match in pattern_matches:
                if 6 in allowed_tiers:  # Tier gate
                    match_data, fallback_selected, fallback_form = build_parent_match_data(parent_key, parent_data)
                    add_candidate({
                        "parent_key": parent_key,
                        "form_key": None,
                        "matched_on": match["matched_on"],
                        "matched_alias": match["matched_alias"],
                        "match_type": "pattern",
                        "tier": 6,
                        "priority": parent_priority,  # From match_rules
                        "alias_len": match["alias_len"],
                        "fallback_form_selected": fallback_selected,
                        "fallback_form_name": fallback_form,
                        "match_data": match_data,
                    })

        if not candidates:
            return None

        def candidate_sort_key(candidate: Dict) -> Tuple:
            # Prefer candidate whose parent matches the base ingredient context.
            # This resolves compound forms like "calcium ascorbate" appearing under
            # both vitamin_c and calcium — when the base ingredient is "Vitamin C",
            # vitamin_c wins; when it's "Calcium", calcium wins.
            parent_pref = 0 if (preferred_parent and candidate["parent_key"] == preferred_parent) else 1
            return (
                candidate["tier"],                      # 1. Tier (exact > normalized > contains/pattern)
                candidate.get("match_source", 1),       # 2. Match source (raw > std > base)
                candidate.get("priority", 1),           # 3. Priority from match_rules (0 > 1 > 2)
                parent_pref,                            # 4. Prefer parent matching base ingredient
                -candidate["alias_len"],                # 5. Longer alias wins within same priority
                0 if candidate["form_key"] else 1,      # 6. Form-level beats parent-level
                candidate["parent_key"],                # 7. Alphabetical parent key
                candidate["form_key"] or "",            # 8. Alphabetical form key
            )

        candidates.sort(key=candidate_sort_key)
        best = candidates[0]

        winning_tier = best["tier"]
        winning_candidates = [c for c in candidates if c["tier"] == winning_tier]

        match_tier = best["match_type"]
        if best["match_type"] == "pattern":
            if best["matched_on"].endswith("_contains"):
                match_tier = "contains"
            elif best["matched_on"].endswith("_pattern"):
                match_tier = "pattern"

        ambiguity_candidates = []
        if len(winning_candidates) > 1:
            reasons = ["tier"]
            best_match_source = best.get("match_source", 1)
            if any(c.get("match_source", 1) != best_match_source for c in winning_candidates):
                reasons.append("raw_name_priority")  # Raw input match beats std/base match
            else:
                best_priority = best.get("priority", 1)
                if any(c.get("priority", 1) != best_priority for c in winning_candidates):
                    reasons.append("match_rules_priority")  # Priority from match_rules
                else:
                    best_parent_pref = 0 if (preferred_parent and best["parent_key"] == preferred_parent) else 1
                    if any((0 if (preferred_parent and c["parent_key"] == preferred_parent) else 1) != best_parent_pref for c in winning_candidates):
                        reasons.append("parent_context_preference")
                    else:
                        best_alias_len = best["alias_len"]
                        if any(c["alias_len"] != best_alias_len for c in winning_candidates):
                            reasons.append("longest_alias")
                        else:
                            best_form_rank = 0 if best["form_key"] else 1
                            if any((0 if c["form_key"] else 1) != best_form_rank for c in winning_candidates):
                                reasons.append("form_over_parent")
                            else:
                                best_parent_key = best["parent_key"]
                                if any(c["parent_key"] != best_parent_key for c in winning_candidates):
                                    reasons.append("alphabetical_parent_key")
                                else:
                                    best_form_key = best["form_key"] or ""
                                    if any((c["form_key"] or "") != best_form_key for c in winning_candidates):
                                        reasons.append("alphabetical_form_key")
                                    else:
                                        reasons.append("alphabetical_fallback")

            payload = {
                "ingredient_raw": ing_name,
                "ingredient_normalized": ing_norm,
                "candidates": [
                    {
                        "canonical_id": c["parent_key"],
                        "form_key": c["form_key"],
                        "matched_alias": c["matched_alias"],
                        "matched_on": c["matched_on"],
                        "match_type": c["match_type"],
                        "tier": c["tier"],
                        "alias_len": c["alias_len"],
                    }
                    for c in winning_candidates
                ],
                "chosen": {
                    "canonical_id": best["parent_key"],
                    "form_key": best["form_key"],
                    "matched_alias": best["matched_alias"],
                    "matched_on": best["matched_on"],
                    "match_type": best["match_type"],
                    "tier": best["tier"],
                    "alias_len": best["alias_len"],
                },
                "preferred_parent": preferred_parent,
                "reason": reasons,
            }
            ambiguity_candidates = payload["candidates"]
            # Only warn if not resolved cleanly by source precedence or context parent preference.
            # Set ENRICH_DEBUG_AMBIGUITY=1 to see all ambiguity warnings
            if (
                ("raw_name_priority" not in reasons and "parent_context_preference" not in reasons)
                or os.environ.get("ENRICH_DEBUG_AMBIGUITY")
            ):
                self._ambiguity_warning_count += 1
                if self._ambiguity_warning_count <= 10:
                    self.logger.warning(f"Ambiguous quality-map match: {json.dumps(payload, sort_keys=True)}")
                elif self._ambiguity_warning_count == 11:
                    self.logger.warning(
                        "Ambiguous quality-map warnings are being suppressed after 10 occurrences; "
                        "set ENRICH_DEBUG_AMBIGUITY=1 to log all details."
                    )
                else:
                    self.logger.debug(f"Ambiguous quality-map match: {json.dumps(payload, sort_keys=True)}")
            else:
                self.logger.debug(
                    f"Ambiguity resolved by source/context precedence: {json.dumps(payload, sort_keys=True)}"
                )

        best["match_data"]["canonical_id"] = best["parent_key"]
        best["match_data"]["form_id"] = best["form_key"] or best["fallback_form_name"]
        best["match_data"]["match_tier"] = match_tier
        best["match_data"]["matched_alias"] = best["matched_alias"]
        best["match_data"]["matched_target"] = best["matched_on"]
        best["match_data"]["match_ambiguity_candidates"] = ambiguity_candidates
        best["match_data"]["fallback_form_selected"] = best["fallback_form_selected"]
        best["match_data"]["fallback_form_name"] = best["fallback_form_name"]

        if match_tier == "pattern":
            self.match_counters["pattern_match_wins_count"] += 1
        elif match_tier == "contains":
            self.match_counters["contains_match_wins_count"] += 1

        if best["fallback_form_selected"]:
            self.match_counters["parent_fallback_count"] += 1
            payload = {
                "ingredient_raw": ing_name,
                "ingredient_normalized": ing_norm,
                "canonical_id": best["parent_key"],
                "fallback_form_name": best["fallback_form_name"],
                "match_type": best["match_type"],
                "tier": best["tier"],
            }
            self._parent_fallback_details.append(payload)
            self._parent_fallback_info_count += 1
            if self._parent_fallback_info_count <= 10:
                self.logger.info(f"Parent fallback form selected: {json.dumps(payload, sort_keys=True)}")
            elif self._parent_fallback_info_count == 11:
                self.logger.info(
                    "Parent fallback logs suppressed after 10; full details saved to "
                    "parent_fallback_report.json in output directory."
                )
            else:
                self.logger.debug(f"Parent fallback form selected: {json.dumps(payload, sort_keys=True)}")

        return best["match_data"]

    def _collect_delivery_data(self, product: Dict) -> Dict:
        """
        Collect enhanced delivery system data for scoring Section A3.
        """
        delivery_db = self.databases.get('enhanced_delivery', {})
        all_text = self._get_all_product_text_lower(product)
        physical_state = product.get('physicalState', {}).get('langualCodeDescription', '').lower()

        matched_systems = []

        for delivery_name, delivery_data in delivery_db.items():
            if delivery_name.startswith("_") or not isinstance(delivery_data, dict):
                continue

            delivery_lower = delivery_name.lower()

            # Check if delivery system mentioned in product
            # LABEL NAME PRESERVATION: Track WHERE the match was found
            match_source = None
            if delivery_lower in all_text:
                match_source = "product_text"
            elif delivery_lower in physical_state:
                match_source = "physical_state"

            if match_source:
                matched_systems.append({
                    # LABEL NAME PRESERVATION:
                    "name": delivery_name,  # Canonical from DB (used for scoring)
                    "canonical_name": delivery_name,  # Explicit canonical field
                    "raw_source_text": delivery_lower,  # What was matched in product
                    "match_source": match_source,  # Where it was found
                    "tier": delivery_data.get('tier', 3),
                    "category": delivery_data.get('category', 'delivery'),
                    "description": delivery_data.get('description', '')
                })

        # Check physical state for lozenge (use data from JSON if available)
        if 'lozenge' in physical_state and not any(s['name'].lower() == 'lozenge' for s in matched_systems):
            lozenge_data = delivery_db.get('lozenge', {})
            matched_systems.append({
                # LABEL NAME PRESERVATION:
                "name": "lozenge",  # Canonical from DB
                "canonical_name": "lozenge",  # Explicit canonical field
                "raw_source_text": "lozenge",  # What was matched in physical state
                "match_source": "physical_state",  # Where it was found
                "tier": lozenge_data.get('tier', 2),
                "category": lozenge_data.get('category', 'delivery'),
                "description": lozenge_data.get('description', 'Lozenge delivery form')
            })

        delivery_data = {
            "matched": len(matched_systems) > 0,
            "systems": matched_systems,
            "highest_tier": min([s['tier'] for s in matched_systems]) if matched_systems else None
        }
        self._last_delivery_data = delivery_data
        return delivery_data

    def _collect_absorption_data(self, product: Dict) -> Dict:
        """
        Collect absorption enhancer data for scoring Section A4.
        Award bonus only if enhancer AND enhanced nutrient BOTH present.
        """
        enhancers_db = self.databases.get('absorption_enhancers', {})
        enhancers_list = enhancers_db.get('absorption_enhancers', [])

        # v3.0 scoring contract: enhancer pairing is ACTIVE-ONLY.
        all_ingredients = product.get('activeIngredients', [])

        # Build ingredient name set for quick lookup
        ingredient_names = set()
        for ing in all_ingredients:
            ingredient_names.add(self._normalize_text(ing.get('name', '')))
            ingredient_names.add(self._normalize_text(ing.get('standardName', '')))

        found_enhancers = []
        enhanced_nutrients_present = []

        for enhancer in enhancers_list:
            # DB uses standard_name (not name) as primary identifier
            enhancer_name = enhancer.get('standard_name') or enhancer.get('name', '')
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
            "enhanced_nutrients_present": sorted(set(enhanced_nutrients_present)),
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
        # LEGACY: Check for USDA Organic (product-level, not ingredient-level)
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

        # ENHANCED (v1.0.0): Evidence-based organic detection
        organic_evidence = self._collect_claims_from_rules_db(product, 'organic_certifications')
        certified_organic_evidence = any(
            ev.get("score_eligible", False) and ev.get("rule_id") == "CERT_USDA_ORGANIC"
            for ev in organic_evidence
        )

        if certified_organic_evidence:
            claimed = True
            usda_verified = True
            if not claim_text:
                claim_text = "USDA Organic"

        return {
            # Legacy format for backward compatibility
            "claimed": claimed and not made_with_organic,
            "usda_verified": usda_verified,
            "claim_text": claim_text,
            "exclusion_matched": made_with_organic,
            # ENHANCED: Evidence-based detection (for hardened scoring)
            "evidence_based": {
                "organic_certifications": organic_evidence,
                "rules_db_version": self.reference_versions.get('cert_claim_rules', {}).get('version', 'unknown')
            }
        }

    def _collect_standardized_botanicals(self, product: Dict) -> List[Dict]:
        """Collect standardized botanical data"""
        botanicals_db = self.databases.get('standardized_botanicals', {})
        botanicals_list = self._merge_standardized_botanicals(
            botanicals_db.get('standardized_botanicals', [])
        )

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
                    local_text = " ".join([
                        ing_name,
                        std_name,
                        notes,
                        ingredient.get("raw_source_text", "") or "",
                        ingredient.get("rawName", "") or "",
                    ]).strip()
                    alias_terms = bot_aliases if isinstance(bot_aliases, list) else []
                    context_terms = [ing_name, std_name, bot_name] + alias_terms[:12]
                    context_text = self._extract_text_windows_by_terms(
                        all_text,
                        context_terms,
                        radius=140,
                        max_windows=8,
                    )

                    percentage = self._extract_percentage(
                        local_text,
                        markers,
                        require_marker_proximity=False,
                    )
                    percentage_source = "local"
                    if percentage <= 0 and context_text:
                        percentage = self._extract_percentage(
                            context_text,
                            markers,
                            require_marker_proximity=True,
                        )
                        if percentage > 0:
                            percentage_source = "context"
                    marker_text = f"{local_text} {context_text}".strip()

                    # Determine if meets threshold
                    # Both percentage and min_threshold are stored as raw percentages
                    # e.g., percentage=5.0 means 5%, min_threshold=50 means 50%
                    meets_threshold = False
                    evidence_source = "none"
                    if min_threshold is not None:
                        if percentage > 0:
                            # Direct comparison - both are raw percentage values
                            meets_threshold = percentage >= min_threshold
                            evidence_source = f"percentage_{percentage_source}"
                        else:
                            # No explicit percentage on label — fall through to
                            # marker word evidence (branded extracts like Longvida,
                            # Meriva, KSM-66 may not restate percentage)
                            meets_threshold = self._has_marker_word_match(
                                markers, marker_text
                            )
                            if meets_threshold:
                                evidence_source = "marker_word_match"
                    else:
                        # No threshold - check for standardization evidence
                        # Use word boundary matching to avoid false positives like
                        # "De-Glycyrrhizinated" matching "glycyrrhizin"
                        meets_threshold = percentage > 0 or self._has_marker_word_match(
                            markers, marker_text
                        )
                        if percentage > 0:
                            evidence_source = f"percentage_{percentage_source}"
                        elif meets_threshold:
                            evidence_source = "marker_word_match"

                    found_botanicals.append({
                        "name": ing_name,
                        "botanical_id": botanical.get('id', ''),
                        "standard_name": bot_name,
                        "markers": markers,
                        "percentage_found": percentage,
                        "percentage_source": percentage_source if percentage > 0 else None,
                        "min_threshold": min_threshold,
                        "meets_threshold": meets_threshold,
                        "evidence_source": evidence_source,
                    })
                    break  # One match per ingredient

        return found_botanicals

    def _merge_standardized_botanicals(self, entries: List[Dict]) -> List[Dict]:
        """
        Merge duplicate standardized-botanical rows by standard_name.

        Keeps the first record as canonical and unions aliases/markers to avoid
        duplicate bonus evaluation from DB duplicates (e.g., cat's claw variants).
        """
        merged: Dict[str, Dict] = {}
        for entry in (entries if isinstance(entries, list) else []):
            if not isinstance(entry, dict):
                continue
            name = (entry.get("standard_name") or "").strip()
            if not name:
                continue
            key = self._normalize_text(name)
            current = merged.get(key)
            if current is None:
                item = dict(entry)
                entry_aliases = entry.get("aliases") if isinstance(entry.get("aliases"), list) else []
                entry_markers = entry.get("markers") if isinstance(entry.get("markers"), list) else []
                item["aliases"] = list(dict.fromkeys(entry_aliases))
                item["markers"] = list(dict.fromkeys(entry_markers))
                merged[key] = item
                continue

            # Merge aliases/markers with stable order and conservative thresholding.
            current_aliases = current.get("aliases") if isinstance(current.get("aliases"), list) else []
            entry_aliases = entry.get("aliases") if isinstance(entry.get("aliases"), list) else []
            current_markers = current.get("markers") if isinstance(current.get("markers"), list) else []
            entry_markers = entry.get("markers") if isinstance(entry.get("markers"), list) else []
            aliases = list(dict.fromkeys(current_aliases + entry_aliases))
            markers = list(dict.fromkeys(current_markers + entry_markers))
            current["aliases"] = aliases
            current["markers"] = markers

            cur_min = current.get("min_threshold")
            new_min = entry.get("min_threshold")
            if cur_min is None and new_min is not None:
                current["min_threshold"] = new_min
            elif isinstance(cur_min, (int, float)) and isinstance(new_min, (int, float)):
                # Higher threshold is more conservative for bonus qualification.
                current["min_threshold"] = max(cur_min, new_min)

        return list(merged.values())

    def _extract_text_windows_by_terms(
        self,
        text: str,
        terms: List[str],
        radius: int = 120,
        max_windows: int = 6,
    ) -> str:
        """Extract nearby text windows around matched terms for evidence-local checks."""
        if not text:
            return ""
        text_lower = text.lower()
        windows: List[str] = []
        seen = set()

        for term in (terms if isinstance(terms, list) else []):
            term_norm = re.sub(r"\s+", " ", (term or "").lower()).strip()
            if not term_norm or len(term_norm) < 3:
                continue
            term_pattern = re.escape(term_norm).replace(r"\ ", r"\s+")
            pattern = re.compile(term_pattern)
            for m in pattern.finditer(text_lower):
                start = max(0, m.start() - radius)
                end = min(len(text_lower), m.end() + radius)
                key = (start, end)
                if key in seen:
                    continue
                seen.add(key)
                windows.append(text_lower[start:end])
                if len(windows) >= max_windows:
                    return " ".join(windows)
        return " ".join(windows)

    def _extract_percentage(
        self,
        text: str,
        markers: List[str],
        require_marker_proximity: bool = True,
    ) -> float:
        """Extract standardization percentage from text"""
        if not text:
            return 0.0

        text_lower = text.lower()

        # Marker-specific patterns (highest confidence).
        for marker in markers:
            marker_lower = marker.lower()
            marker_patterns = [
                rf'(\d+(?:\.\d+)?)\s*%\s*(?:total\s+)?{re.escape(marker_lower)}\b',
                rf'{re.escape(marker_lower)}\s*\(?\s*(\d+(?:\.\d+)?)\s*%\)?',
            ]
            for pattern in marker_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    return float(match.group(1))

        # Generic standardized pattern (only valid with marker proximity when markers exist).
        pattern = self.compiled_patterns['standardized_pct']
        for match in pattern.finditer(text_lower):
            pct = float(match.group(1))
            if not markers or not require_marker_proximity:
                return pct
            nearby = (
                text_lower[max(0, match.start() - 60):match.start()]
                + " "
                + text_lower[match.end(): match.end() + 140]
            )
            if self._has_marker_word_match(markers, nearby):
                return pct

        return 0.0

    def _has_marker_word_match(self, markers: List[str], text: str) -> bool:
        """
        Check if any marker appears as a whole word in text.

        Uses word boundary matching to avoid false positives like:
        - "De-Glycyrrhizinated" should NOT match "glycyrrhizin"
        - "glycyrrhizin content" SHOULD match "glycyrrhizin"

        Args:
            markers: List of marker compound names to search for
            text: Text to search within

        Returns:
            True if any marker is found as a word boundary match
        """
        if not text or not markers:
            return False

        text_lower = text.lower()

        for marker in markers:
            marker_lower = marker.lower()
            # Use word boundary regex to ensure we match whole words
            # \b matches word boundaries (start/end of word)
            pattern = rf'\b{re.escape(marker_lower)}\b'
            if re.search(pattern, text_lower):
                return True

        return False

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
                sources = cluster.get("sources", [])
                if not isinstance(sources, list):
                    sources = []
                matched_clusters.append({
                    "cluster_id": cluster.get('id', ''),
                    "cluster_name": cluster.get('standard_name', ''),
                    "evidence_tier": cluster.get('evidence_tier', 3),
                    "note": cluster.get("note") or cluster.get("synergy_mechanism") or "",
                    "sources": sources,
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
            "banned_substances": self._check_banned_substances(all_ingredients, product),
            "harmful_additives": self._check_harmful_additives(all_ingredients),
            "allergens": self._check_allergens(all_ingredients, product)
        }

    def _check_banned_substances(self, ingredients: List[Dict], product: Optional[Dict] = None) -> Dict:
        """Check for banned/recalled substances.

        Supports both legacy (category-based) and v3 (ingredients[]) structures.
        Implements negative_match_terms filtering and entity_type filtering.
        """
        banned_db = self.databases.get('banned_recalled_ingredients', {})
        allowlist_db = self.databases.get('banned_match_allowlist', {}) or {}
        allowlist_entries = allowlist_db.get('allowlist', []) or []
        denylist_entries = allowlist_db.get('denylist', []) or []
        allowlist_version = allowlist_db.get('_metadata', {}).get('version', 'unknown')
        found = []

        allowlist_by_id = {}
        for entry in allowlist_entries:
            canonical_id = entry.get('canonical_id')
            if canonical_id:
                allowlist_by_id.setdefault(canonical_id, []).append(entry)

        denylist_by_id = {}
        for entry in denylist_entries:
            canonical_id = entry.get('canonical_id')
            if canonical_id:
                denylist_by_id.setdefault(canonical_id, []).append(entry)

        # Collect banned items from either structure
        banned_items_with_category = []

        # v3 structure: single ingredients[] list
        if 'ingredients' in banned_db and isinstance(banned_db['ingredients'], list):
            for item in banned_db['ingredients']:
                if isinstance(item, dict):
                    # Use source_category or class_tags for category
                    category = item.get('source_category', '')
                    if not category and item.get('class_tags'):
                        category = item['class_tags'][0] if item['class_tags'] else ''
                    banned_items_with_category.append((category, item))
        else:
            # Legacy structure: category-based
            for section_key, section_data in banned_db.items():
                if section_key.startswith("_") or not isinstance(section_data, list):
                    continue
                for item in section_data:
                    if isinstance(item, dict):
                        banned_items_with_category.append((section_key, item))

        # Entity types that should be matched against ingredient labels
        # Classes and threats should NOT match via fuzzy/token matching
        # Products are now matchable with brand-qualified aliases and negative_match_terms
        MATCHABLE_ENTITY_TYPES = {'ingredient', 'contaminant', 'product', None, ''}

        product_name = ""
        brand_name = ""
        if isinstance(product, dict):
            product_name = (
                product.get('product_name')
                or product.get('fullName')
                or ""
            )
            brand_name = (
                product.get('brandName')
                or product.get('brand_name')
                or ""
            )

        scan_ingredients = ingredients if ingredients else [{}]

        for ing_idx, ingredient in enumerate(scan_ingredients):
            ing_name = ingredient.get('name', '')
            std_name = ingredient.get('standardName', '') or ing_name
            ing_name_lower = ing_name.lower()

            for section_key, banned_item in banned_items_with_category:
                if not isinstance(banned_item, dict):
                    continue

                # P0: Filter by entity_type - skip products/classes/threats
                entity_type = banned_item.get('entity_type', 'ingredient')
                if entity_type not in MATCHABLE_ENTITY_TYPES:
                    continue

                # P0b: Filter by match_mode - skip disabled/historical entries
                match_mode = banned_item.get('match_mode', 'active')
                if match_mode in ('disabled', 'historical'):
                    continue

                # Product-level recalls/bans should match product identity
                # (full name / brand), not ingredient labels.
                candidate_ing_name = ing_name
                candidate_std_name = std_name
                if entity_type == 'product':
                    if ing_idx > 0:
                        continue
                    candidate_ing_name = product_name or ing_name
                    candidate_std_name = brand_name or std_name
                candidate_ing_name_lower = candidate_ing_name.lower()
                candidate_std_name_lower = candidate_std_name.lower()

                banned_name = banned_item.get('standard_name', '')
                banned_aliases = banned_item.get('aliases', [])
                all_aliases = sorted(set(banned_aliases))

                banned_id = banned_item.get('id')
                allowlist_for = allowlist_by_id.get(banned_id, [])
                denylist_for = denylist_by_id.get(banned_id, [])

                # Check denylist first
                deny_hit = self._denylist_match(candidate_ing_name, denylist_for) or \
                    self._denylist_match(candidate_std_name, denylist_for)
                if deny_hit:
                    continue

                # P0: Check negative_match_terms (reduces false positives)
                match_rules = banned_item.get('match_rules', {})
                negative_terms = match_rules.get('negative_match_terms', [])
                if negative_terms and (
                    self._has_negative_match_term(candidate_ing_name_lower, negative_terms)
                    or self._has_negative_match_term(candidate_std_name_lower, negative_terms)
                ):
                    continue

                match_method = None
                matched_variant = None
                allowlist_id = None

                # Prefer strict exact/alias classification when available.
                # This supports B0 confidence gating in scoring without
                # relying on token-bounded fallback for every hit.
                direct_match = self._check_additive_match(
                    candidate_ing_name, candidate_std_name, banned_name, all_aliases
                )
                if direct_match:
                    method = str(direct_match.get("method", "")).lower()
                    if "alias" in method:
                        match_method = "alias"
                        matched_variant = direct_match.get("matched_alias")
                    else:
                        match_method = "exact"
                        matched_variant = banned_name

                if not match_method:
                    safe_token_aliases = self._filter_safe_token_aliases(banned_name, all_aliases)
                    matched, matched_variant = self._token_bounded_match(
                        candidate_ing_name, banned_name, safe_token_aliases
                    )
                    if matched:
                        if self._token_match_has_required_context(candidate_ing_name, banned_item, matched_variant):
                            match_method = "token_bounded"
                    else:
                        matched, matched_variant = self._token_bounded_match(
                            candidate_std_name, banned_name, safe_token_aliases
                        )
                        if matched:
                            if self._token_match_has_required_context(candidate_std_name, banned_item, matched_variant):
                                match_method = "token_bounded"

                if not match_method and allowlist_for:
                    allowlist_match = self._allowlist_match(candidate_ing_name, allowlist_for)
                    if not allowlist_match:
                        allowlist_match = self._allowlist_match(candidate_std_name, allowlist_for)
                    if allowlist_match:
                        match_method = allowlist_match.get("match_method")
                        matched_variant = allowlist_match.get("matched_variant")
                        allowlist_id = allowlist_match.get("allowlist_id")

                if match_method:
                    # Guardrail: do not flag explicitly negated mentions like
                    # "X-free" / "free from X" / "contains no X".
                    negation_target = matched_variant or banned_name
                    if self._is_negated_match_phrase(candidate_ing_name_lower, negation_target) or \
                       self._is_negated_match_phrase(candidate_std_name_lower, negation_target):
                        continue

                    match_type = match_method
                    if match_type not in {"exact", "alias", "token_bounded"}:
                        mm = str(match_method).lower()
                        if "exact" in mm:
                            match_type = "exact"
                        elif "alias" in mm:
                            match_type = "alias"
                        elif "token" in mm:
                            match_type = "token_bounded"

                    confidence_map = {
                        "exact": 1.0,
                        "alias": 0.9,
                        "token_bounded": 0.7
                    }

                    # Derive severity_level from status for backward compat with scorer
                    _STATUS_TO_SEVERITY = {
                        "banned": "critical", "recalled": "critical",
                        "high_risk": "moderate", "watchlist": "low"
                    }
                    derived_severity = _STATUS_TO_SEVERITY.get(
                        banned_item.get('status', ''), 'high'
                    )

                    found.append({
                        "ingredient": candidate_ing_name,
                        "banned_name": banned_name,
                        "banned_id": banned_item.get('id', ''),
                        "category": section_key,
                        "status": banned_item.get('status') or banned_item.get('recall_status'),
                        "severity_level": derived_severity,
                        "reason": banned_item.get('reason', ''),
                        "match_type": match_type,
                        "confidence": confidence_map.get(match_type, 0.5),
                        "match_method": match_method,
                        "matched_variant": matched_variant,
                        "allowlist_id": allowlist_id,
                        "allowlist_version": allowlist_version if allowlist_id else None,
                        "entity_type": entity_type,
                        "legal_status_enum": banned_item.get('legal_status_enum'),
                        "clinical_risk_enum": banned_item.get('clinical_risk_enum'),
                        "regulatory_date": banned_item.get('regulatory_date'),
                        "regulatory_date_label": banned_item.get('regulatory_date_label'),
                    })

        return {
            "found": len(found) > 0,
            "substances": found
        }

    def _has_negative_match_term(self, text: str, negative_terms: List[str]) -> bool:
        """Check if text contains any negative match terms (case-insensitive).

        Used to filter out false positives like 'ephedra-free', 'kava-free', etc.
        """
        text_lower = text.lower()
        for term in negative_terms:
            if term.lower() in text_lower:
                return True
        return False

    def _is_negated_match_phrase(self, text: str, matched_term: str) -> bool:
        """Detect explicit negation patterns around a matched term."""
        term = (matched_term or "").strip().lower()
        if not text or not term:
            return False

        text_lower = text.lower()
        escaped_term = re.escape(term)
        negation_patterns = (
            rf"\b{escaped_term}\s*-\s*free\b",
            rf"\bfree\s+from\s+{escaped_term}\b",
            rf"\bcontains?\s+no\s+{escaped_term}\b",
            rf"\bno\s+{escaped_term}\b",
            rf"\bwithout\s+{escaped_term}\b",
            rf"\bnon[-\s]+{escaped_term}\b",
        )
        return any(re.search(pattern, text_lower) for pattern in negation_patterns)

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

                # Check for match and track HOW matched for provenance
                match_result = self._check_additive_match(
                    ing_name, std_name, additive_name, additive_aliases
                )
                if match_result:
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
                        # LABEL NAME PRESERVATION:
                        # - ingredient/raw_source_text: exact label text (user-facing)
                        # - additive_name/canonical_name: database canonical (internal)
                        "ingredient": ing_name,  # Label-facing name
                        "raw_source_text": ing_name,  # Provenance (exact label text)
                        "additive_name": additive_name,  # Canonical from DB
                        "canonical_name": additive_name,  # Explicit canonical field
                        "additive_id": additive_id,  # Canonical ID
                        "match_method": match_result["method"],  # How matched
                        "matched_alias": match_result.get("matched_alias"),  # Which alias if any
                        "severity_level": additive.get('severity_level', 'low'),
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
        allergen_list = allergen_db.get('allergens', allergen_db.get('common_allergens', []))

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

            # CRITICAL FIX: Build set of negated allergen terms from multiple sources
            # This prevents detecting allergens when product claims to be free of them
            # Example: Product with "dairy-free" claim should NOT detect milk allergen
            negated_terms = set()

            # Source 1: labelText.parsed.allergenFree (from upstream parser)
            allergen_free_raw = parsed.get('allergenFree', [])
            for free_claim in allergen_free_raw:
                if isinstance(free_claim, str):
                    negated_terms.add(free_claim.lower().strip())

            # Source 2: compliance_data.allergen_free_claims (authoritative enrichment source)
            # This catches edge cases where parsed allergenFree might be incomplete
            compliance_data = product.get('compliance_data', {})
            for claim in compliance_data.get('allergen_free_claims', []):
                if isinstance(claim, str):
                    negated_terms.add(claim.lower().strip())

            # Source 3: targetGroups for "X Free" claims
            target_groups = product.get('targetGroups', [])
            for tg in target_groups:
                tg_text = tg if isinstance(tg, str) else (tg.get('text', '') if isinstance(tg, dict) else '')
                tg_lower = tg_text.lower()
                # Extract "X" from "X Free" or "X-Free" patterns
                free_match = re.search(r'(\w+)[\s-]*free', tg_lower)
                if free_match:
                    negated_terms.add(free_match.group(1))

            for allergen_text in parsed_allergens:
                if isinstance(allergen_text, str):
                    allergen_lower = allergen_text.lower().strip()
                    if allergen_lower in allergen_lookup:
                        allergen = allergen_lookup[allergen_lower]

                        # Check if this allergen is negated by a "free" claim
                        # Compare against allergen name AND all its aliases
                        allergen_name_lower = allergen.get('standard_name', '').lower()
                        allergen_aliases = [a.lower() for a in allergen.get('aliases', [])]
                        all_allergen_terms = {allergen_lower, allergen_name_lower} | set(allergen_aliases)

                        # If any allergen term matches any negated term, skip this allergen
                        if negated_terms & all_allergen_terms:
                            self.logger.debug(
                                f"Skipping negated allergen '{allergen_text}' "
                                f"(free claims: {negated_terms & all_allergen_terms})"
                            )
                            continue

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

        IMPORTANT: Negation patterns are SKIPPED:
        - "Contains no milk, soy" -> NOT added (this is an allergen-free claim)
        - "Free from milk and soy" -> NOT added
        - "Does not contain milk" -> NOT added
        """
        text_lower = text.lower()

        # CRITICAL: Check for negation patterns FIRST - skip entire statement if negated
        # These statements list allergens the product is FREE FROM, not containing
        negation_patterns = [
            r'contains?\s+no\s+',           # "Contains no milk"
            r'does\s+not\s+contain',        # "Does not contain milk"
            r'free\s+(?:from|of)\s+',       # "Free from milk"
            r'without\s+',                  # "Without milk"
            r'no\s+added\s+',               # "No added milk"
        ]
        for neg_pattern in negation_patterns:
            if re.search(neg_pattern, text_lower):
                self.logger.debug(f"Skipping negated allergen statement: {text[:80]}...")
                return  # Skip this entire statement - it's declaring what product is FREE FROM

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
        allergen_list = allergen_db.get('allergens', allergen_db.get('common_allergens', []))

        all_text = self._get_all_product_text_lower(product)

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
        """
        Check if allergen mention is in negation context.

        IMPORTANT - SCOPE LIMITATION:
        This negation check applies ONLY to free-text fields:
        - allergenStatement (e.g., "Contains no milk, egg, or soy")
        - labelStatement (e.g., "Free from common allergens")
        - targetGroups text (e.g., "Dairy-Free")
        - marketing claims and descriptions

        This check MUST NOT be used to filter out allergens detected from:
        - structured ingredient rows (activeIngredients, inactiveIngredients)
        - ingredient name fields directly

        Rationale: If "Milk Protein" appears as an ingredient row, it IS an
        allergen regardless of any "dairy-free" claim elsewhere. The structured
        ingredient list is authoritative. Negation only filters allergens
        detected via text scanning of unstructured fields.

        Args:
            name: Allergen standard name (e.g., "milk")
            aliases: List of allergen aliases (e.g., ["dairy", "lactose"])
            text: The free-text to scan for negation context (must be lowercase)

        Returns:
            True if allergen appears in negation context, False otherwise
        """
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
        all_text = self._get_all_product_text_lower(product)

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

        # ENHANCED (v1.0.0): Evidence-based allergen claims with validation
        allergen_evidence = self._collect_claims_from_rules_db(product, 'allergen_free_claims')

        # Promote evidence-based allergen claims to canonical flags so statement-only
        # labels (without targetGroups metadata) do not silently miss bonuses.
        eligible_allergen_evidence = [ev for ev in allergen_evidence if ev.get('score_eligible', False)]
        claim_keys = set(str(x).strip().lower() for x in allergen_free_claims if x)
        for ev in eligible_allergen_evidence:
            dedupe_key = str(ev.get('dedupe_key', '')).strip().lower()
            if dedupe_key.startswith('allergen_free:'):
                key = dedupe_key.split(':', 1)[1].strip()
                if key:
                    claim_keys.add(key)
        allergen_free_claims = sorted(claim_keys)

        gluten_free = gluten_free or any(
            ev.get('rule_id') in {'CLAIM_GLUTEN_FREE', 'CLAIM_GLUTEN_FREE_GFCO'}
            for ev in eligible_allergen_evidence
        )
        dairy_free = dairy_free or any(
            str(ev.get('dedupe_key', '')).lower() == 'allergen_free:dairy'
            for ev in eligible_allergen_evidence
        )
        soy_free = soy_free or any(
            str(ev.get('dedupe_key', '')).lower() == 'allergen_free:soy'
            for ev in eligible_allergen_evidence
        )

        eligible_dietary_evidence = [
            ev for ev in eligible_allergen_evidence
            if str(ev.get('dedupe_key', '')).lower().startswith('dietary:')
        ]
        vegan = vegan or any(
            ev.get('rule_id') in {'CLAIM_VEGAN', 'CLAIM_VEGAN_CERTIFIED'}
            for ev in eligible_dietary_evidence
        )
        vegetarian = vegetarian or any(
            ev.get('rule_id') == 'CLAIM_VEGETARIAN'
            for ev in eligible_dietary_evidence
        )

        # Apply conflict checking to evidence objects
        for evidence in allergen_evidence:
            conflict_allergens = []
            dedupe_key = evidence.get('dedupe_key', '')

            # Check for actual allergen conflicts
            if 'gluten' in dedupe_key and any(
                'wheat' in a['allergen_name'].lower() or 'gluten' in a['allergen_name'].lower()
                for a in detected_allergens
            ):
                conflict_allergens.append('gluten/wheat detected')
            if 'dairy' in dedupe_key and any(
                'milk' in a['allergen_name'].lower() or 'dairy' in a['allergen_name'].lower()
                for a in detected_allergens
            ):
                conflict_allergens.append('dairy/milk detected')
            if 'soy' in dedupe_key and any(
                'soy' in a['allergen_name'].lower() for a in detected_allergens
            ):
                conflict_allergens.append('soy detected')
            if 'nut' in dedupe_key and any(
                'nut' in a['allergen_name'].lower() for a in detected_allergens
            ):
                conflict_allergens.append('nut detected')

            # Update score_eligible based on conflicts
            if conflict_allergens and evidence.get('score_eligible', False):
                evidence['score_eligible'] = False
                evidence['ineligibility_reason'] = f'allergen_conflict:{",".join(conflict_allergens)}'
                evidence['proximity_conflicts'].extend(conflict_allergens)

            # Also check for may_contain warning
            if may_contain and evidence.get('score_eligible', False):
                evidence['score_eligible'] = False
                evidence['ineligibility_reason'] = 'may_contain_warning'

        return {
            # Legacy format for backward compatibility
            "allergen_free_claims": allergen_free_claims,
            "gluten_free": gluten_free,
            "dairy_free": dairy_free,
            "soy_free": soy_free,
            "vegan": vegan,
            "vegetarian": vegetarian,
            "conflicts": conflicts,
            "has_may_contain_warning": may_contain,
            "verified": len(conflicts) == 0,
            # ENHANCED: Evidence-based detection (for hardened scoring)
            "evidence_based": {
                "allergen_free_claims": allergen_evidence,
                "rules_db_version": self.reference_versions.get('cert_claim_rules', {}).get('version', 'unknown')
            }
        }

    # =========================================================================
    # CLAIMS VALIDATION SYSTEM (v1.0.0 - Evidence-based claim detection)
    # =========================================================================

    def _get_field_groups(self) -> Dict[str, List[str]]:
        """Get source field groups from cert_claim_rules database."""
        cert_rules = self.databases.get('cert_claim_rules', {})
        return cert_rules.get('config', {}).get('source_field_groups', {
            'product_level_fields': ['statements', 'qualityFeatures', 'certifications',
                                      'claims', 'labelText'],
            'ingredient_fields': ['ingredients', 'activeIngredients', 'inactiveIngredients',
                                   'supplementFacts', 'otherIngredients', 'ingredientRows'],
            'any_field': ['*']
        })

    def _check_claim_with_validation(self, text: str, source_field: str, rule: Dict,
                                      field_groups: Dict) -> Optional[Dict]:
        """
        Check claim against rule with negative pattern and scope validation.

        This method implements the hardened claim detection system:
        1. Match positive patterns to find potential claims
        2. Check negative patterns to reject false positives
        3. Validate scope (product-level claims only from approved fields)
        4. Return evidence object with full audit trail

        NOTE: Does NOT compute points_awarded - that's scoring's responsibility

        Args:
            text: Text to search for claim
            source_field: Field name where text came from (for scope validation)
            rule: Rule definition from cert_claim_rules.json
            field_groups: Centralized field groups for scope validation

        Returns:
            Evidence object if claim found, None otherwise
        """
        # 1. Check positive patterns
        positive_match = None
        for i, pattern in enumerate(rule.get('positive_patterns', [])):
            try:
                match = re.search(pattern, text, re.I)
                if match:
                    positive_match = {
                        'text': match.group(),
                        'start': match.start(),
                        'end': match.end(),
                        'pattern_id': f"{rule.get('id', 'UNKNOWN')}_positive_{i}"
                    }
                    break
            except re.error as e:
                self.logger.warning(f"Invalid regex pattern in rule {rule.get('id')}: {e}")
                continue

        if not positive_match:
            return None  # No claim found

        # 2. SCOPE VALIDATION (using centralized field groups)
        scope_rule = rule.get('scope_rule', 'any')
        approved_field_group = rule.get('approved_field_group', 'any_field')
        approved_fields = field_groups.get(approved_field_group, ['*'])
        scope_violation = False

        if scope_rule == 'product_level_only' and '*' not in approved_fields:
            # Check if source_field base is in approved group
            field_base = source_field.split('[')[0].split('.')[0]
            if field_base not in approved_fields:
                scope_violation = True

        # 3. Check negative patterns with evidence capture
        negation = {
            'negated': False,
            'negation_match_text': None,
            'negation_source_field': None,
            'negation_pattern_id': None
        }
        for j, pattern in enumerate(rule.get('negative_patterns', [])):
            try:
                neg_match = re.search(pattern, text, re.I)
                if neg_match:
                    negation = {
                        'negated': True,
                        'negation_match_text': neg_match.group(),
                        'negation_source_field': source_field,
                        'negation_pattern_id': f"{rule.get('id', 'UNKNOWN')}_negative_{j}"
                    }
                    break
            except re.error:
                continue

        # 4. Check required tokens if specified
        required_tokens = rule.get('required_tokens', [])
        required_tokens_missing = False
        if required_tokens:
            text_lower = text.lower()
            if not any(token.lower() in text_lower for token in required_tokens):
                required_tokens_missing = True

        # 5. Check required context if specified (for batch traceability)
        required_context = rule.get('required_context', [])
        context_missing = False
        if required_context:
            text_lower = text.lower()
            if not any(ctx.lower() in text_lower for ctx in required_context):
                context_missing = True

        # 6. Proximity check (for allergen claims)
        proximity_window = rule.get('proximity_window', 150)
        proximity_conflicts = []
        conflict_allergens = rule.get('conflict_allergens', [])
        if conflict_allergens:
            window_start = max(0, positive_match['start'] - proximity_window)
            window_end = min(len(text), positive_match['end'] + proximity_window)
            nearby_text = text[window_start:window_end].lower()

            for allergen in conflict_allergens:
                if allergen.lower() in nearby_text:
                    # Check if it's not the "-free" claim itself
                    if f"{allergen.lower()}-free" not in nearby_text and f"{allergen.lower()} free" not in nearby_text:
                        proximity_conflicts.append(allergen)

        # 7. Determine score eligibility with REASON
        evidence_strength = rule.get('evidence_strength', 'weak')
        score_eligible = True
        ineligibility_reason = None

        if negation['negated']:
            score_eligible = False
            ineligibility_reason = 'negated'
        elif scope_violation:
            score_eligible = False
            ineligibility_reason = 'scope_violation'
        elif required_tokens_missing:
            score_eligible = False
            ineligibility_reason = 'required_tokens_missing'
        elif context_missing:
            score_eligible = False
            ineligibility_reason = 'required_context_missing'
        elif len(proximity_conflicts) > 0:
            score_eligible = False
            ineligibility_reason = f'proximity_conflict:{",".join(proximity_conflicts)}'
        elif evidence_strength == 'weak':
            score_eligible = False
            ineligibility_reason = 'weak_evidence'

        # NOTE: points_awarded is NOT computed here - scoring does that
        return {
            'rule_id': rule.get('id', 'UNKNOWN'),
            'claim_type': rule.get('claim_type', 'unknown'),
            'display_name': rule.get('display_name', rule.get('id', 'Unknown')),
            'dedupe_key': rule.get('dedupe_key'),
            'matched_text': positive_match['text'],
            'source_field': source_field,
            'pattern_id': positive_match['pattern_id'],
            'scope_rule': scope_rule,
            'approved_field_group': approved_field_group,
            'scope_violation': scope_violation,
            'negation': negation,
            'proximity_conflicts': proximity_conflicts,
            'evidence_strength': evidence_strength,
            'score_eligible': score_eligible,
            'ineligibility_reason': ineligibility_reason,
            'points_if_eligible': rule.get('points_if_eligible', 0)
        }

    def _collect_claims_from_rules_db(self, product: Dict, rule_category: str) -> List[Dict]:
        """
        Collect claims from a specific category in cert_claim_rules.json.

        FIXED (v1.0.1): Now scans field-by-field for proper scope validation.
        - Iterates through each product field separately
        - Passes real source_field path to _check_claim_with_validation
        - Deduplicates by dedupe_key, keeping best evidence
        - Adds context_snippet for audit readability

        Args:
            product: Product data
            rule_category: Category key in cert_claim_rules (e.g., 'third_party_programs', 'gmp_certifications')

        Returns:
            List of evidence objects for matched claims (deduplicated)
        """
        cert_rules = self.databases.get('cert_claim_rules', {})
        rules = cert_rules.get('rules', {}).get(rule_category, {})
        field_groups = self._get_field_groups()

        # Collect all text sources with their field paths
        text_sources = self._extract_text_sources(product)

        # Collect all matches (may have duplicates)
        all_matches = []

        for rule_key, rule in rules.items():
            if rule_key.startswith('_'):
                continue
            if not isinstance(rule, dict):
                continue
            if 'positive_patterns' not in rule:
                continue

            # Scan all fields - scope validation happens in _check_claim_with_validation
            for source_field, text in text_sources:
                if not text or len(text.strip()) < 3:
                    continue

                # For 'any' scope, scan all fields
                # For 'product_level_only', still scan all but let validation catch violations
                evidence = self._check_claim_with_validation(
                    text, source_field, rule, field_groups
                )
                if evidence:
                    # Add context snippet for audit readability
                    evidence['context_snippet'] = self._get_context_snippet(
                        text, evidence.get('matched_text', ''), context_chars=80
                    )
                    all_matches.append(evidence)

        # Deduplicate by dedupe_key, keeping the best evidence
        return self._deduplicate_evidence(all_matches)

    def _extract_text_sources(self, product: Dict) -> List[Tuple[str, str]]:
        """
        Extract all text sources from product with their field paths.

        Returns list of (field_path, text) tuples for field-by-field scanning.
        """
        sources = []

        # Product-level fields (for scope validation)
        # statements - list of dicts with 'notes' or 'text'
        for i, stmt in enumerate(product.get('statements', [])):
            if isinstance(stmt, str):
                sources.append((f'statements[{i}]', stmt))
            elif isinstance(stmt, dict):
                notes = stmt.get('notes', '') or stmt.get('text', '') or ''
                stmt_type = stmt.get('type', '')
                if notes:
                    sources.append((f'statements[{i}].notes', notes))
                if stmt_type:
                    sources.append((f'statements[{i}].type', stmt_type))

        # qualityFeatures - list of strings or dicts
        for i, qf in enumerate(product.get('qualityFeatures', [])):
            if isinstance(qf, str):
                sources.append((f'qualityFeatures[{i}]', qf))
            elif isinstance(qf, dict):
                text = qf.get('text', '') or qf.get('name', '') or qf.get('notes', '') or ''
                if text:
                    sources.append((f'qualityFeatures[{i}]', text))

        # certifications - list of strings or dicts
        for i, cert in enumerate(product.get('certifications', [])):
            if isinstance(cert, str):
                sources.append((f'certifications[{i}]', cert))
            elif isinstance(cert, dict):
                text = cert.get('text', '') or cert.get('name', '') or ''
                if text:
                    sources.append((f'certifications[{i}]', text))

        # claims - list of dicts with langualCodeDescription
        for i, claim in enumerate(product.get('claims', [])):
            if isinstance(claim, str):
                sources.append((f'claims[{i}]', claim))
            elif isinstance(claim, dict):
                text = claim.get('text', '') or claim.get('langualCodeDescription', '') or claim.get('notes', '') or ''
                if text:
                    sources.append((f'claims[{i}]', text))

        # labelText - string or nested dict
        label_text = product.get('labelText', '')
        if isinstance(label_text, str) and label_text:
            sources.append(('labelText', label_text))
        elif isinstance(label_text, dict):
            raw = label_text.get('raw', '')
            if raw:
                sources.append(('labelText.raw', raw))
            parsed = label_text.get('parsed', {})
            if isinstance(parsed, dict):
                for key, val in parsed.items():
                    if isinstance(val, str) and val:
                        sources.append((f'labelText.parsed.{key}', val))
                    elif isinstance(val, list):
                        for j, item in enumerate(val):
                            if isinstance(item, str) and item:
                                sources.append((f'labelText.parsed.{key}[{j}]', item))

        # fullName and brandName (product-level)
        full_name = product.get('fullName', '')
        if full_name:
            sources.append(('fullName', full_name))
        brand_name = product.get('brandName', '')
        if brand_name:
            sources.append(('brandName', brand_name))

        # Ingredient-level fields (for 'any' scope rules)
        for i, ing in enumerate(product.get('activeIngredients', [])):
            notes = ing.get('notes', '')
            if notes:
                sources.append((f'activeIngredients[{i}].notes', notes))

        for i, ing in enumerate(product.get('inactiveIngredients', [])):
            notes = ing.get('notes', '') or ing.get('name', '') or ''
            if notes:
                sources.append((f'inactiveIngredients[{i}]', notes))

        # otherIngredients - often a string
        other_ing = product.get('otherIngredients', '')
        if isinstance(other_ing, str) and other_ing:
            sources.append(('otherIngredients', other_ing))
        elif isinstance(other_ing, list):
            for i, oi in enumerate(other_ing):
                if isinstance(oi, str) and oi:
                    sources.append((f'otherIngredients[{i}]', oi))
                elif isinstance(oi, dict):
                    text = oi.get('text', '') or oi.get('name', '') or ''
                    if text:
                        sources.append((f'otherIngredients[{i}]', text))

        return sources

    def _get_context_snippet(self, full_text: str, matched_text: str, context_chars: int = 80) -> str:
        """
        Extract context snippet around matched text for audit readability.

        Returns matched text with ±context_chars of surrounding text.
        """
        if not matched_text or not full_text:
            return ''

        try:
            idx = full_text.lower().find(matched_text.lower())
            if idx == -1:
                return matched_text

            start = max(0, idx - context_chars)
            end = min(len(full_text), idx + len(matched_text) + context_chars)

            snippet = full_text[start:end]

            # Add ellipsis if truncated
            if start > 0:
                snippet = '...' + snippet
            if end < len(full_text):
                snippet = snippet + '...'

            return snippet.replace('\n', ' ').replace('\t', ' ')
        except Exception:
            return matched_text

    def _deduplicate_evidence(self, evidence_list: List[Dict]) -> List[Dict]:
        """
        Deduplicate evidence objects by dedupe_key, keeping the best evidence.

        Priority order (best first):
        1. Strong evidence > Medium > Weak
        2. Non-negated > Negated
        3. Non-scope-violation > Scope violation
        4. score_eligible=True > False
        """
        if not evidence_list:
            return []

        # Group by dedupe_key
        by_key = {}
        for ev in evidence_list:
            key = ev.get('dedupe_key') or ev.get('rule_id', 'unknown')
            if key not in by_key:
                by_key[key] = []
            by_key[key].append(ev)

        # For each group, pick the best evidence
        strength_rank = {'strong': 3, 'medium': 2, 'weak': 1}
        deduplicated = []

        for key, candidates in by_key.items():
            # Sort by quality (best first)
            def sort_key(ev):
                return (
                    strength_rank.get(ev.get('evidence_strength', 'weak'), 0),  # Higher is better
                    0 if ev.get('negation', {}).get('negated') else 1,  # Non-negated better
                    0 if ev.get('scope_violation') else 1,  # Non-violation better
                    1 if ev.get('score_eligible') else 0,  # Eligible better
                )

            candidates.sort(key=sort_key, reverse=True)
            best = candidates[0]

            # Add duplicate count for audit
            if len(candidates) > 1:
                best['duplicate_count'] = len(candidates)
                best['other_sources'] = [c.get('source_field') for c in candidates[1:]][:5]

            deduplicated.append(best)

        return deduplicated

    def _collect_certification_data(self, product: Dict) -> Dict:
        """
        Collect certification data for scoring Section B3.

        ENHANCED (v1.0.0): Now uses cert_claim_rules.json for evidence-based detection.
        - Returns evidence objects with full audit trail
        - Validates claims with negative patterns
        - Enforces scope rules (product-level only)
        - Scoring decides points based on evidence_strength and score_eligible

        Also derives safety verification flags from certifications:
        - purity_verified: Product tested by program that tests for contaminants
        - heavy_metal_tested: Product tested by program that tests for heavy metals
        - label_accuracy_verified: Product tested by program that verifies label claims
        """
        all_text = self._get_all_product_text(product)

        # LEGACY: Collect using old patterns for backward compatibility
        third_party = self._collect_third_party_certs(all_text)
        gmp = self._collect_gmp_data(all_text)
        traceability = self._collect_traceability_data(all_text)

        # ENHANCED (v1.0.0): Collect using rules database with evidence objects
        # These provide full audit trail for hardened scoring
        third_party_evidence = self._collect_claims_from_rules_db(product, 'third_party_programs')
        gmp_evidence = self._collect_claims_from_rules_db(product, 'gmp_certifications')
        batch_evidence = self._collect_claims_from_rules_db(product, 'batch_traceability')

        # Merge evidence-based third-party detections into legacy structure.
        # Scoring currently reads projected named_cert_programs from
        # certification_data.third_party_programs.programs, so keep that source
        # complete even when only rules-db evidence finds a match.
        third_party = self._merge_evidence_third_party_programs(third_party, third_party_evidence)

        # Manufacturer-level certification injection: when the product matches a
        # known top-manufacturer, cross-reference that manufacturer's evidence
        # strings for certification keywords.  This catches certifications that
        # are not printed on the physical label but are publicly verifiable
        # at the company level (e.g., "NSF Certified for Sport" for Thorne).
        third_party = self._inject_manufacturer_certs(third_party, product, gmp)

        # Derive safety flags from certifications
        # These programs test for heavy metals, contaminants, and/or label accuracy
        safety_flags = self._derive_safety_flags(third_party, product)

        return {
            # Legacy format for backward compatibility
            "third_party_programs": third_party,
            "gmp": gmp,
            "batch_traceability": traceability,
            # Safety verification flags for app display
            "purity_verified": safety_flags["purity_verified"],
            "heavy_metal_tested": safety_flags["heavy_metal_tested"],
            "label_accuracy_verified": safety_flags["label_accuracy_verified"],
            "category_contamination_risk": safety_flags["category_contamination_risk"],
            # ENHANCED: Evidence-based detection (for hardened scoring)
            "evidence_based": {
                "third_party_programs": third_party_evidence,
                "gmp_certifications": gmp_evidence,
                "batch_traceability": batch_evidence,
                "rules_db_version": self.reference_versions.get('cert_claim_rules', {}).get('version', 'unknown')
            }
        }

    def _merge_evidence_third_party_programs(self, third_party: Dict, evidence_list: List[Dict]) -> Dict:
        """
        Backfill third_party_programs from rules-db evidence when legacy regex
        misses formatting variants (e.g., line breaks in certification claims).
        """
        programs = list((third_party or {}).get("programs", []) or [])
        existing = {self._normalize_text((p or {}).get("name")) for p in programs if isinstance(p, dict)}

        # Map evidence rule IDs to canonical display names used by safety flags.
        canonical_name_map = {
            "CERT_NSF_SPORT": "NSF Sport",
            "CERT_NSF_CONTENTS": "NSF Certified",
            "CERT_USP_VERIFIED": "USP Verified",
            "CERT_CONSUMERLAB": "ConsumerLab",
            "CERT_INFORMED_SPORT": "Informed Sport",
            "CERT_INFORMED_CHOICE": "Informed Choice",
            "CERT_BSCG": "BSCG",
            "CERT_IFOS": "IFOS",
            "CERT_LABDOOR": "Labdoor Tested",
        }

        for ev in evidence_list or []:
            if not isinstance(ev, dict) or not ev.get("score_eligible", False):
                continue
            rule_id = self._normalize_text(ev.get("rule_id"))
            mapped_name = canonical_name_map.get(rule_id.upper()) if rule_id else None
            if not mapped_name:
                mapped_name = ev.get("display_name")
            key = self._normalize_text(mapped_name)
            if not key or key in existing:
                continue
            programs.append({"name": mapped_name, "verified": True, "source": "rules_db"})
            existing.add(key)

        merged = dict(third_party or {})
        merged["programs"] = programs
        merged["count"] = len(programs)
        merged["has_generic_claim_only"] = bool(merged.get("has_generic_claim_only", False) and len(programs) == 0)
        return merged

    # Patterns mapping manufacturer evidence strings to canonical cert names.
    _MANUFACTURER_CERT_PATTERNS = [
        (re.compile(r'NSF\s+Certified\s+for\s+Sport', re.I), "NSF Sport"),
        (re.compile(r'NSF\s+Certified', re.I), "NSF Certified"),
        (re.compile(r'USP.?verified', re.I), "USP Verified"),
        (re.compile(r'ConsumerLab', re.I), "ConsumerLab"),
        (re.compile(r'Informed[\s-]?Sport', re.I), "Informed Sport"),
        (re.compile(r'Informed[\s-]?Choice', re.I), "Informed Choice"),
        (re.compile(r'BSCG', re.I), "BSCG"),
        (re.compile(r'\bIFOS\b', re.I), "IFOS"),
        (re.compile(r'\bGMP\b', re.I), None),  # GMP handled separately
    ]

    def _inject_manufacturer_certs(
        self, third_party: Dict, product: Dict, gmp: Dict
    ) -> Dict:
        """Inject certifications from top_manufacturers_data evidence strings.

        When a product matches a known top-manufacturer, that manufacturer's
        ``evidence`` list is scanned for certification keywords.  Detected
        certifications are added to the third_party programs list (deduped).
        GMP evidence is injected into the gmp dict in-place.
        """
        brand = product.get("brandName", "")
        contacts = product.get("contacts", [])
        manufacturer = ""
        for contact in contacts:
            if "Manufacturer" in (contact.get("types") or []):
                manufacturer = (
                    contact.get("contactDetails", {}) or {}
                ).get("name", "")
                break
        if not manufacturer:
            manufacturer = brand

        top_match = self._check_top_manufacturer(brand, manufacturer)
        if not top_match.get("found"):
            return third_party

        # Find the matching manufacturer entry to get evidence strings.
        top_db = self.databases.get("top_manufacturers_data", {})
        top_list = top_db.get("top_manufacturers", [])
        evidence_strings = []
        matched_id = top_match.get("manufacturer_id", "")
        for entry in top_list:
            if entry.get("id") == matched_id:
                evidence_strings = entry.get("evidence", [])
                break

        if not evidence_strings:
            return third_party

        programs = list((third_party or {}).get("programs", []) or [])
        existing = {
            self._normalize_text((p or {}).get("name"))
            for p in programs
            if isinstance(p, dict)
        }

        for ev_str in evidence_strings:
            for pattern, cert_name in self._MANUFACTURER_CERT_PATTERNS:
                if not pattern.search(ev_str):
                    continue
                if cert_name is None:
                    # GMP — inject into gmp dict
                    if not gmp.get("nsf_gmp") and not gmp.get("claimed"):
                        gmp["claimed"] = True
                        gmp["source"] = "manufacturer_evidence"
                    continue
                key = self._normalize_text(cert_name)
                if key in existing:
                    continue
                programs.append({
                    "name": cert_name,
                    "verified": True,
                    "source": "manufacturer_evidence",
                })
                existing.add(key)
                break  # one cert per evidence string

        merged = dict(third_party or {})
        merged["programs"] = programs
        merged["count"] = len(programs)
        if programs:
            merged["has_generic_claim_only"] = False
        return merged

    def _collect_third_party_certs(self, text: str) -> List[Dict]:
        """Collect third-party testing certifications"""
        certs = []

        # Priority certification patterns (named programs only)
        cert_checks = [
            ("NSF Sport", r'\bNSF\b.*certified(?:\s*for)?\s*sport\b|\bNSF[-\s]?sport\b'),
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
            "severity_level": "elevated",
            "concerns": ["heavy_metals", "bpa"],
            "note": "Independent tests found lead/arsenic in many protein supplements"
        },
        "greens_superfood": {
            "severity_level": "elevated",
            "concerns": ["heavy_metals", "pesticides"],
            "note": "Plant-based concentrates may accumulate soil contaminants"
        },
        "ayurvedic_herbal": {
            "severity_level": "high",
            "concerns": ["heavy_metals", "adulterants"],
            "note": "Traditional preparations sometimes contain lead/mercury"
        },
        "weight_loss": {
            "severity_level": "high",
            "concerns": ["adulterants", "stimulants"],
            "note": "FDA has found hidden drugs in weight loss supplements"
        },
        "sexual_enhancement": {
            "severity_level": "high",
            "concerns": ["adulterants", "prescription_drugs"],
            "note": "FDA frequently finds hidden Viagra/Cialis analogs"
        },
        "sports_performance": {
            "severity_level": "moderate",
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
                "severity_level": risk_info["severity_level"],
                "concerns": risk_info["concerns"],
                "note": risk_info["note"]
            }

        return {
            "has_elevated_risk": False,
            "category": None,
            "severity_level": "standard",
            "concerns": [],
            "note": None
        }

    def _collect_proprietary_data(self, product: Dict) -> Dict:
        """
        Collect proprietary blend data for scoring Section B4.

        UNION-OF-EVIDENCE CONTRACT:
        Enrichment proprietary_data MUST be union of:
        1. Detector evidence (pattern-based from ProprietaryBlendDetector)
        2. Cleaning evidence (indicator-based from proprietaryBlend flags)
        3. Deduplicated to prevent double-penalizing

        This ensures blends flagged during cleaning are NEVER silently dropped
        when the detector returns empty results.

        Merge Precedence Rules (when same blend from both sources):
        - disclosure_level: prefer detector (more accurate analysis)
        - blend_total_amount: prefer detector if parsed, else cleaning
        - blend_ingredient_count: prefer detector if available
        - blend_name: prefer cleaning (better for UI display)
        """
        active_ingredients = product.get('activeIngredients', [])
        inactive_ingredients = product.get('inactiveIngredients', [])
        total_active = len(active_ingredients)

        def _looks_like_blend_label(value: str) -> bool:
            text = (value or "").strip().lower()
            if not text:
                return False
            normalized = self._normalize_exclusion_text(text)
            if normalized in BLEND_HEADER_EXACT_NAMES:
                return True
            for pattern in BLEND_HEADER_PATTERNS_HIGH_CONFIDENCE:
                if re.search(pattern, text, re.IGNORECASE):
                    return True
            for pattern in BLEND_HEADER_PATTERNS_LOW_CONFIDENCE:
                if re.search(pattern, text, re.IGNORECASE):
                    return True
            # Safety net for simple canonical blend terms.
            return bool(re.search(r"\b(proprietary|blend|complex|matrix|formula|stack)\b", text))

        def _is_non_proprietary_aggregate(value: str) -> bool:
            text = (value or "").strip().lower()
            if not text:
                return False
            normalized = self._normalize_exclusion_text(text)
            if self._excluded_text_reason(text):
                return True
            if normalized in {"total cultures", "total omega 3s", "total omega 6s", "total omega 9s"}:
                return True
            if re.match(r"^(total|other)\s+", normalized) and not re.search(
                r"\b(proprietary|blend|complex|matrix|formula|stack)\b", normalized
            ):
                return True
            return False

        # Step 1: Collect detector blends (pattern-based)
        detector_blends = []
        if self.blend_detector:
            try:
                result = self.blend_detector.analyze_product(product)
                for blend in result.blends_detected:
                    detector_with_amounts = blend.ingredients_with_amounts or []
                    detector_without_amounts = blend.ingredients_without_amounts or []
                    detector_children = [
                        {
                            "name": item.get("name", ""),
                            "amount": item.get("amount"),
                            "unit": item.get("unit", "") or "",
                        }
                        for item in detector_with_amounts
                    ] + [
                        {
                            "name": name,
                            "amount": None,
                            "unit": "",
                        }
                        for name in detector_without_amounts
                    ]
                    detector_blends.append({
                        "name": blend.blend_name,
                        "disclosure_level": blend.disclosure_level,
                        "nested_count": blend.blend_ingredient_count,
                        "total_weight": blend.blend_total_amount,
                        "unit": blend.blend_total_unit or "",
                        "hidden_count": len(detector_without_amounts),
                        "source_field": blend.source_field,
                        "source_path": blend.source_field,
                        "child_ingredients": detector_children,
                        "sources": ["detector"],
                        "evidence": {
                            "blend_id": blend.blend_id,
                            "matched_text": blend.matched_text,
                            "source_field": blend.source_field,
                            "risk_category": blend.risk_category,
                            "severity_level": blend.severity_level,
                            "amounts_present": blend.blend_amounts_present,
                            "ingredients_with_amounts": blend.ingredients_with_amounts,
                            "ingredients_without_amounts": blend.ingredients_without_amounts,
                            "penalty_applicable": blend.penalty_applicable,
                            "penalty_reason": blend.penalty_reason
                        }
                    })
            except Exception as e:
                self.logger.warning(
                    f"ProprietaryBlendDetector failed for product "
                    f"{product.get('dsld_id', 'unknown')}: {e} — "
                    f"B5 blend penalty will NOT be applied"
                )

        # Step 2: Collect cleaning blends (indicator-based from proprietaryBlend flags)
        # Nested proprietary children should roll up to their parent blend to avoid
        # inflating B5 penalties (e.g., each enzyme row being treated as a separate blend).
        cleaning_blends = []
        nested_parent_groups = {}
        def _collect_child_amounts(children: List[Dict]) -> Tuple[List[Dict], List[str]]:
            with_amounts: List[Dict] = []
            without_amounts: List[str] = []
            for child in children:
                if not isinstance(child, dict):
                    continue
                child_name = (child.get("name", "") or "").strip()
                child_qty = child.get("quantity")
                if isinstance(child_qty, (int, float)) and child_qty > 0:
                    with_amounts.append(
                        {
                            "name": child_name,
                            "amount": float(child_qty),
                            "unit": (child.get("unit", "") or ""),
                        }
                    )
                elif child_name:
                    without_amounts.append(child_name)
            return with_amounts, without_amounts

        for source_name, ingredient_list in (
            ("activeIngredients", active_ingredients),
            ("inactiveIngredients", inactive_ingredients),
        ):
            for idx, ingredient in enumerate(ingredient_list):
                is_blend = (
                    ingredient.get('proprietaryBlend', False) or
                    ingredient.get('isProprietaryBlend', False)
                )
                if not is_blend:
                    continue

                disclosure = ingredient.get('disclosureLevel', 'none')
                nested = ingredient.get('nestedIngredients', [])
                is_nested = bool(ingredient.get('isNestedIngredient', False))
                parent_blend = (ingredient.get('parentBlend', '') or '').strip()
                quantity = ingredient.get('quantity', 0) or 0
                unit = ingredient.get('unit', '') or ''
                ingredient_group = ingredient.get('ingredientGroup', '') or ''
                source_field = f"{source_name}[{idx}]"
                name = ingredient.get('name', '') or ''
                has_nested_children = isinstance(nested, list) and len(nested) > 0
                has_parent = bool(parent_blend)
                name_looks_like_blend = (
                    _looks_like_blend_label(name)
                    or _looks_like_blend_label(ingredient_group)
                )
                parent_looks_like_blend = _looks_like_blend_label(parent_blend)
                parent_is_non_proprietary_aggregate = _is_non_proprietary_aggregate(parent_blend)
                name_is_non_proprietary_aggregate = _is_non_proprietary_aggregate(name)

                # Clean-stage proprietary flags can leak onto single ingredients
                # (e.g., "Vitamin D", "Bacillus coagulans"). Keep only entries
                # with structural blend evidence.
                if name_is_non_proprietary_aggregate:
                    continue
                if not has_nested_children and not has_parent and not name_looks_like_blend:
                    continue

                # Roll nested rows under parent blend key when available.
                if is_nested and parent_blend:
                    # Parent aggregates like "Total Cultures"/"Total Omega-3s"
                    # are not proprietary blends unless the parent label itself
                    # carries proprietary/blend structure.
                    if parent_is_non_proprietary_aggregate or not parent_looks_like_blend:
                        continue

                    group_key = (parent_blend.lower(), disclosure)
                    group = nested_parent_groups.get(group_key)
                    if not group:
                        group = {
                            "name": parent_blend,
                            "disclosure_level": disclosure,
                            "nested_count": 0,
                            "total_weight": 0.0,
                            "unit": "",
                            "hidden_count": 0,
                            "source_field": source_field,
                            "source_path": source_field,
                            "sources": ["cleaning"],
                            "_source_fields": set(),
                            "_children_with_amounts": [],
                            "_children_without_amounts": set(),
                        }
                        nested_parent_groups[group_key] = group

                    group["_source_fields"].add(source_field)
                    child_name = (ingredient.get('name', '') or '').strip()
                    child_qty = ingredient.get('quantity')
                    child_unit = ingredient.get('unit', '') or ''
                    if isinstance(child_qty, (int, float)) and child_qty > 0 and child_name:
                        group["_children_with_amounts"].append(
                            {"name": child_name, "amount": float(child_qty), "unit": child_unit}
                        )
                    elif child_name:
                        group["_children_without_amounts"].add(child_name)

                    # Preserve any measured parent quantity if it exists on nested rows.
                    if isinstance(quantity, (int, float)) and quantity > group["total_weight"]:
                        group["total_weight"] = float(quantity)
                        group["unit"] = unit
                    continue

                children_with_amounts, children_without_amounts = _collect_child_amounts(
                    nested if isinstance(nested, list) else []
                )
                child_ingredients = [
                    {
                        "name": item.get("name", ""),
                        "amount": item.get("amount"),
                        "unit": item.get("unit", "") or "",
                    }
                    for item in children_with_amounts
                ] + [
                    {"name": child_name, "amount": None, "unit": ""}
                    for child_name in children_without_amounts
                ]
                cleaning_blends.append({
                    "name": ingredient.get('name', ''),
                    "disclosure_level": disclosure,
                    "nested_count": len(nested),
                    "hidden_count": len(children_without_amounts),
                    "total_weight": quantity,
                    "unit": unit,
                    "source_field": source_field,
                    "source_path": source_field,
                    "child_ingredients": child_ingredients,
                    "sources": ["cleaning"],
                    "evidence": {
                        "source_field": source_field,
                        "ingredients_with_amounts": children_with_amounts,
                        "ingredients_without_amounts": children_without_amounts,
                    }
                })

        for group in nested_parent_groups.values():
            with_amounts = group.pop("_children_with_amounts", [])
            without_amounts = sorted(group.pop("_children_without_amounts", set()))
            source_fields = sorted(group.pop("_source_fields", set()))
            group["source_fields"] = source_fields
            if source_fields:
                group["source_field"] = source_fields[0]
                group["source_path"] = source_fields[0]
            group["child_ingredients"] = [
                {
                    "name": item.get("name", ""),
                    "amount": item.get("amount"),
                    "unit": item.get("unit", "") or "",
                }
                for item in with_amounts
            ] + [{"name": child_name, "amount": None, "unit": ""} for child_name in without_amounts]
            group["hidden_count"] = len(without_amounts)
            group["evidence"] = {
                "source_field": group.get("source_field", ""),
                "source_fields": source_fields,
                "ingredients_with_amounts": with_amounts,
                "ingredients_without_amounts": without_amounts,
            }
            group["nested_count"] = max(group["nested_count"], len(with_amounts) + len(without_amounts))
            cleaning_blends.append(group)

        # Step 3: Merge and dedupe using union-of-evidence
        merged_blends = self._merge_blend_evidence(detector_blends, cleaning_blends)

        # Step 3b: Normalize blend_total_mg for scorer direct access.
        # The scorer reads blend_total_mg (in mg) first, falls back to total_weight.
        # We convert here so the scorer doesn't have to guess units.
        for blend in merged_blends:
            tw = blend.get("total_weight")
            bu = (blend.get("unit") or "").strip().lower()
            if tw is not None and isinstance(tw, (int, float)) and tw > 0:
                if bu in ("mg", "milligram", "milligrams", ""):
                    blend["blend_total_mg"] = round(float(tw), 4)
                elif bu in ("g", "gram", "grams", "gram(s)"):
                    blend["blend_total_mg"] = round(float(tw) * 1000.0, 4)
                elif bu in ("mcg", "ug", "microgram", "micrograms"):
                    blend["blend_total_mg"] = round(float(tw) / 1000.0, 4)
                else:
                    blend["blend_total_mg"] = None  # Unknown unit
            else:
                blend["blend_total_mg"] = None

        # Step 3c: Compute total_active_mg for scorer B5 impact calculation.
        total_active_mg = 0.0
        for ing in active_ingredients:
            qty_list = ing.get("quantity", [])
            qty_val = 0.0
            qty_unit = ""
            if isinstance(qty_list, list) and qty_list:
                entry = qty_list[0] if qty_list else {}
                qty_val = entry.get("quantity", 0) if isinstance(entry.get("quantity"), (int, float)) else 0
                qty_unit = (entry.get("unit", "") or "").strip().lower()
            elif isinstance(qty_list, (int, float)):
                qty_val = qty_list
                qty_unit = (ing.get("unit", "") or "").strip().lower()
            if qty_val and qty_val > 0:
                if qty_unit in ("mg", "milligram", "milligrams", ""):
                    total_active_mg += qty_val
                elif qty_unit in ("g", "gram", "grams", "gram(s)"):
                    total_active_mg += qty_val * 1000.0
                elif qty_unit in ("mcg", "ug", "microgram", "micrograms"):
                    total_active_mg += qty_val / 1000.0

        # Step 4: Compute counts and metrics for transparency
        detector_count = len(detector_blends)
        cleaning_count = len(cleaning_blends)
        raw_total = detector_count + cleaning_count  # Before deduplication
        merged_count = len(merged_blends)  # After deduplication

        # Deduplication rate: how many duplicates were removed
        # This is expected due to detector finding same blend from multiple sources
        dedup_count = raw_total - merged_count
        dedup_rate = dedup_count / raw_total if raw_total > 0 else 0.0

        # Blend loss rate: cleaning blends that didn't make it to merged
        # This should be 0% after the union-of-evidence fix
        blend_loss_rate = 0.0
        if cleaning_count > 0:
            cleaning_names = {b["name"].lower().strip() for b in cleaning_blends}
            merged_names = {b["name"].lower().strip() for b in merged_blends}
            lost_names = cleaning_names - merged_names
            blend_loss_rate = len(lost_names) / cleaning_count if cleaning_count > 0 else 0.0

        return {
            "has_proprietary_blends": len(merged_blends) > 0,
            "blends": merged_blends,
            "blend_count": len(merged_blends),
            "total_active_ingredients": total_active,
            "total_active_mg": round(total_active_mg, 4),
            # Provenance tracking for auditing (Issue #1 & #2 from audit)
            "blend_sources": {
                # Raw counts (before deduplication)
                "detector_raw_count": detector_count,
                "cleaning_raw_count": cleaning_count,
                "raw_total": raw_total,
                # After deduplication
                "merged_count": merged_count,
                "dedup_count": dedup_count,
                "dedup_rate": round(dedup_rate, 4),
                # Quality metric (should be 0)
                "blend_loss_rate": round(blend_loss_rate, 4)
            }
        }

    def _merge_blend_evidence(
        self,
        detector_blends: List[Dict],
        cleaning_blends: List[Dict]
    ) -> List[Dict]:
        """
        Merge detector and cleaning blend evidence with deduplication.

        Dedupe key: (normalized_name, 5mg_bucket, nested_count)
        This matches the dedupe logic in B4 scoring.

        Merge Precedence:
        - disclosure_level: prefer detector (more accurate)
        - blend_total_amount: prefer detector if parsed
        - blend_ingredient_count: prefer detector if available
        - blend_name: prefer cleaning (better UI display, label-facing)
        - detector_group: preserve detector's classification category
        - sources: union of both

        AUDIT CLARITY:
        - `name`: Label-facing blend name (from cleaning when available)
        - `detector_group`: Detector's classification (e.g., "General Proprietary Blends")
        This preserves both the human-readable label name and the detector category.
        """
        merged = {}

        def dedupe_key(blend: Dict) -> tuple:
            """Generate deduplication key matching B4 scoring logic."""
            name = (blend.get("name") or "").lower().strip()
            mg = blend.get("total_weight")
            # 5mg bucket to tolerate parsing variance
            mg_bucket = int(round(mg / 5.0) * 5) if mg and mg > 0 else None
            nested = blend.get("nested_count", 0)
            return (name, mg_bucket, nested)

        # Add detector blends first (higher precedence for most fields)
        for blend in detector_blends:
            key = dedupe_key(blend)
            blend_copy = blend.copy()
            # Store detector's classification as detector_group for audit
            blend_copy["detector_group"] = blend.get("name")
            merged[key] = blend_copy

        # Merge cleaning blends (may add new or enrich existing)
        for cleaning_blend in cleaning_blends:
            key = dedupe_key(cleaning_blend)

            if key in merged:
                # Blend exists from detector - merge sources and prefer cleaning name
                existing = merged[key]
                # Union sources
                existing_sources = set(existing.get("sources", []))
                existing_sources.add("cleaning")
                existing["sources"] = list(existing_sources)
                # Preserve source field provenance.
                source_paths = set(existing.get("source_fields", []))
                if existing.get("source_field"):
                    source_paths.add(existing["source_field"])
                if cleaning_blend.get("source_field"):
                    source_paths.add(cleaning_blend["source_field"])
                for path in cleaning_blend.get("source_fields", []):
                    if path:
                        source_paths.add(path)
                existing["source_fields"] = sorted(source_paths)
                if existing.get("source_fields"):
                    existing["source_field"] = existing["source_fields"][0]
                    existing["source_path"] = existing["source_fields"][0]
                # Prefer cleaning name for UI (label-facing, more specific)
                # Keep detector_group as the classifier category
                if cleaning_blend.get("name"):
                    existing["name"] = cleaning_blend["name"]
                # Prefer richer child payload from cleaning when available.
                if cleaning_blend.get("child_ingredients"):
                    existing["child_ingredients"] = cleaning_blend.get("child_ingredients", [])
                    existing["hidden_count"] = cleaning_blend.get("hidden_count", existing.get("hidden_count", 0))
                    cleaning_evidence = cleaning_blend.get("evidence") or {}
                    existing_evidence = existing.get("evidence") or {}
                    existing_evidence["ingredients_with_amounts"] = cleaning_evidence.get(
                        "ingredients_with_amounts",
                        existing_evidence.get("ingredients_with_amounts", []),
                    )
                    existing_evidence["ingredients_without_amounts"] = cleaning_evidence.get(
                        "ingredients_without_amounts",
                        existing_evidence.get("ingredients_without_amounts", []),
                    )
                    existing["evidence"] = existing_evidence
            else:
                # New blend from cleaning only - no detector_group
                blend_copy = cleaning_blend.copy()
                blend_copy["detector_group"] = None  # Not detected by pattern DB
                merged[key] = blend_copy

        return list(merged.values())

    def _extract_strain_ids_from_product(self, product: Dict) -> List[str]:
        """Extract probiotic strain IDs from product text and ingredient fields."""
        strain_id_pattern = re.compile(
            r'(atcc\s*(?:pta\s*)?[\d]+|dsm\s*[\d]+|ncfm|\bgg\b|\bk12\b|\bm18\b|bb-?12|bb536|hn019|bi-?07|de111|299v)',
            re.IGNORECASE
        )
        texts = [self._get_all_product_text(product)]
        for ing in product.get('activeIngredients', []) + product.get('inactiveIngredients', []):
            texts.append(ing.get('name', '') or '')
            texts.append(ing.get('standardName', '') or '')
            texts.append(ing.get('notes', '') or '')
            texts.append(ing.get('harvestMethod', '') or '')
        combined = ' '.join(filter(None, texts))
        matches = strain_id_pattern.findall(combined)
        deduped = sorted({re.sub(r'\s+', ' ', m.strip()) for m in matches if m})
        return deduped

    def _collect_product_signals(
        self,
        product: Dict,
        ingredient_quality_data: Dict,
        certification_data: Dict,
        formulation_data: Dict,
        probiotic_data: Dict
    ) -> Dict:
        """Collect product-level signals for auditing and UI display."""
        coverage = {
            "total_records_seen": ingredient_quality_data.get("total_records_seen", 0),
            "total_ingredients_evaluated": ingredient_quality_data.get("total_ingredients_evaluated", 0),
            "unevaluated_records": ingredient_quality_data.get("unevaluated_records", 0),
            "pattern_match_wins_count": ingredient_quality_data.get("pattern_match_wins_count", 0),
            "contains_match_wins_count": ingredient_quality_data.get("contains_match_wins_count", 0),
            "parent_fallback_count": ingredient_quality_data.get("parent_fallback_count", 0)
        }

        cert_types = set()
        third_party_programs = certification_data.get("third_party_programs", {}).get("programs", [])
        for program in third_party_programs:
            name = program.get("name")
            if name:
                cert_types.add(name)

        gmp = certification_data.get("gmp", {})
        if gmp.get("claimed"):
            cert_types.add(gmp.get("text_matched") or "GMP")

        batch = certification_data.get("batch_traceability", {})
        if batch.get("has_coa"):
            cert_types.add("COA")
        if batch.get("has_qr_code"):
            cert_types.add("QR Code")
        if batch.get("has_batch_lookup"):
            cert_types.add("Batch Lookup")

        label_text = self._get_all_product_text(product)
        trademark_present = bool(re.search(r'[™®©]', label_text))
        standardized_botanicals = formulation_data.get("standardized_botanicals", [])
        strain_ids = self._extract_strain_ids_from_product(product)

        label_disclosure_signals = {
            "standardized_botanicals_count": len(standardized_botanicals),
            "standardized_botanicals": standardized_botanicals,
            "strain_ids": strain_ids,
            "strain_id_count": len(strain_ids),
            "total_strain_count": probiotic_data.get("total_strain_count", 0),
            "clinical_strain_count": probiotic_data.get("clinical_strain_count", 0),
            "has_trademarked_forms": trademark_present
        }

        return {
            "coverage": coverage,
            "certificates_present": bool(cert_types),
            "certificate_types": sorted(cert_types),
            "label_disclosure_signals": label_disclosure_signals
        }

    def _project_scoring_fields(self, enriched: Dict) -> None:
        """
        Project nested enrichment outputs into stable top-level fields used by
        scoring and downstream consumers.
        """
        delivery_data = enriched.get("delivery_data", {}) or {}
        absorption_data = enriched.get("absorption_data", {}) or {}
        formulation_data = enriched.get("formulation_data", {}) or {}
        contaminant_data = enriched.get("contaminant_data", {}) or {}
        compliance_data = enriched.get("compliance_data", {}) or {}
        certification_data = enriched.get("certification_data", {}) or {}
        proprietary_data = enriched.get("proprietary_data", {}) or {}
        evidence_data = enriched.get("evidence_data", {}) or {}
        manufacturer_data = enriched.get("manufacturer_data", {}) or {}
        ingredient_quality_data = enriched.get("ingredient_quality_data", {}) or {}

        enriched["delivery_tier"] = delivery_data.get("highest_tier")
        enriched["absorption_enhancer_paired"] = bool(
            absorption_data.get("qualifies_for_bonus", False)
        )

        organic_data = formulation_data.get("organic", {})
        if isinstance(organic_data, dict):
            is_certified_organic = bool(
                organic_data.get("usda_verified")
                or (organic_data.get("claimed") and not organic_data.get("exclusion_matched"))
            )
        else:
            is_certified_organic = bool(organic_data)
        enriched["is_certified_organic"] = is_certified_organic

        standardized_botanicals = formulation_data.get("standardized_botanicals", []) or []
        enriched["has_standardized_botanical"] = any(
            bool(item.get("meets_threshold"))
            for item in standardized_botanicals
            if isinstance(item, dict)
        )

        synergy_clusters = formulation_data.get("synergy_clusters", []) or []
        synergy_cluster_qualified = False
        for cluster in synergy_clusters:
            if not isinstance(cluster, dict):
                continue
            matched_ingredients = cluster.get("matched_ingredients", []) or []
            match_count = cluster.get("match_count", len(matched_ingredients)) or 0
            try:
                match_count = int(match_count)
            except (TypeError, ValueError):
                match_count = 0

            if match_count < 2:
                continue

            checkable = []
            for item in matched_ingredients:
                if not isinstance(item, dict):
                    continue
                min_dose = item.get("min_effective_dose", 0) or 0
                try:
                    min_dose = float(min_dose)
                except (TypeError, ValueError):
                    min_dose = 0
                if min_dose > 0:
                    checkable.append(item)

            # Require at least one ingredient with a defined effective-dose threshold.
            # This prevents broad "ingredient co-occurrence" matches from earning A5c
            # without any dose-anchored evidence check.
            if not checkable:
                continue

            dosed = [item for item in checkable if bool(item.get("meets_minimum", False))]
            required = (len(checkable) + 1) // 2
            if len(dosed) >= required:
                synergy_cluster_qualified = True
                break

        enriched["synergy_cluster_qualified"] = synergy_cluster_qualified

        harmful_additives = (
            contaminant_data.get("harmful_additives", {}).get("additives", []) or []
        )
        allergen_hits = (
            contaminant_data.get("allergens", {}).get("allergens", []) or []
        )
        enriched["harmful_additives"] = harmful_additives
        enriched["allergen_hits"] = allergen_hits

        conflicts = [
            str(x).lower()
            for x in (compliance_data.get("conflicts", []) or [])
        ]
        has_may_contain = bool(compliance_data.get("has_may_contain_warning", False))
        allergen_claims = compliance_data.get("allergen_free_claims", []) or []

        allergen_contradiction = has_may_contain or any(
            any(term in c for term in ["allergen", "dairy", "soy", "egg", "gluten", "wheat", "shellfish", "nut"])
            for c in conflicts
        )
        gluten_contradiction = has_may_contain or any(
            ("gluten" in c) or ("wheat" in c) for c in conflicts
        )
        vegan_contradiction = any(
            any(term in c for term in ["gelatin", "bovine", "porcine", "vegan", "vegetarian"])
            for c in conflicts
        )

        enriched["claim_allergen_free_validated"] = bool(allergen_claims) and not allergen_contradiction and len(allergen_hits) == 0
        enriched["claim_gluten_free_validated"] = bool(compliance_data.get("gluten_free", False)) and not gluten_contradiction
        enriched["claim_vegan_validated"] = bool(
            compliance_data.get("vegan", False) or compliance_data.get("vegetarian", False)
        ) and not vegan_contradiction

        third_party_programs = certification_data.get("third_party_programs", {}).get("programs", []) or []
        named_programs = []
        for program in third_party_programs:
            if isinstance(program, dict):
                name = program.get("name")
            else:
                name = program
            if name:
                named_programs.append(name)
        enriched["named_cert_programs"] = named_programs

        gmp_data = certification_data.get("gmp", {}) or {}
        if bool(gmp_data.get("nsf_gmp") or gmp_data.get("claimed")):
            gmp_level = "certified"
        elif bool(gmp_data.get("fda_registered")):
            gmp_level = "fda_registered"
        else:
            gmp_level = None
        enriched["gmp_level"] = gmp_level

        batch_data = certification_data.get("batch_traceability", {}) or {}
        enriched["has_coa"] = bool(batch_data.get("has_coa", False))
        enriched["has_batch_lookup"] = bool(
            batch_data.get("has_batch_lookup", False) or batch_data.get("has_qr_code", False)
        )

        enriched["proprietary_blends"] = proprietary_data.get("blends", []) or []
        enriched["has_disease_claims"] = bool(
            (evidence_data.get("unsubstantiated_claims", {}) or {}).get("found", False)
        )

        top_manufacturer = manufacturer_data.get("top_manufacturer", {}) or {}
        # Trusted-manufacturer bonus is exact-match only; fuzzy hits are audit-only.
        enriched["is_trusted_manufacturer"] = bool(
            top_manufacturer.get("found", False)
            and str(top_manufacturer.get("match_type", "")).lower() == "exact"
        )

        ingredients = ingredient_quality_data.get("ingredients_scorable", []) or ingredient_quality_data.get("ingredients", []) or []
        has_missing_dose = any(
            isinstance(item, dict) and not bool(item.get("has_dose", False))
            for item in ingredients
        )
        has_hidden_blends = any(
            isinstance(blend, dict) and str(blend.get("disclosure_level", "")).lower() in {"none", "partial"}
            for blend in enriched["proprietary_blends"]
        )
        enriched["has_full_disclosure"] = (not has_missing_dose) and (not has_hidden_blends)

        bonus_features = manufacturer_data.get("bonus_features", {}) or {}
        enriched["claim_physician_formulated"] = bool(bonus_features.get("physician_formulated", False))
        enriched["has_sustainable_packaging"] = bool(bonus_features.get("sustainability_claim", False))
        enriched["manufacturing_region"] = (
            manufacturer_data.get("country_of_origin", {}) or {}
        ).get("country")

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
            candidate_names = [
                ing_name,
                std_name,
                ingredient.get("raw_source_text", ""),
            ]

            for study in studies:
                study_name = study.get('standard_name', '')
                study_aliases = self._collect_clinical_aliases(study)
                matched = self._clinical_study_match(candidate_names, study)

                if matched:

                    # For brand-specific studies, check brand mention
                    study_id = study.get('id', '')
                    if study_id.startswith('BRAND_'):
                        if not self._brand_mentioned(study_name, study_aliases, product):
                            continue

                    match_payload = {
                        "ingredient": ing_name,
                        "standard_name": study_name,
                        "id": study_id,
                        "study_id": study_id,
                        "study_name": study_name,
                        "match_method": matched.get("method"),
                        "matched_term": matched.get("matched_term"),
                        "evidence_level": study.get('evidence_level', 'ingredient-human'),
                        "study_type": study.get('study_type', 'rct_single'),
                        "score_contribution": study.get('score_contribution', 'tier_3'),
                        "health_goals_supported": study.get('health_goals_supported', []),
                        "key_endpoints": study.get('key_endpoints', [])
                    }

                    # Optional schema extensions (forward-compatible passthrough).
                    optional_fields = [
                        "min_clinical_dose",
                        "dose_unit",
                        "typical_effective_dose",
                        "dose_range",
                        "base_points",
                        "multiplier",
                        "computed_score",
                    ]
                    for field in optional_fields:
                        if field in study and study.get(field) is not None:
                            match_payload[field] = study.get(field)

                    matches.append(match_payload)
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
        all_text = self._get_all_product_text_lower(product)

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

        AC2: Now includes provenance fields for auditability:
        - product_manufacturer_raw: Original text from product
        - product_manufacturer_normalized: Normalized version
        - source_path: Which field provided the match
        """
        top_db = self.databases.get('top_manufacturers_data', {})
        top_list = top_db.get('top_manufacturers', [])

        # Determine which input was used for matching (AC2 source_path)
        brand_normalized = self._normalize_company_name(brand) if brand else ""
        mfr_normalized = self._normalize_company_name(manufacturer) if manufacturer else ""

        # Pass 1: exact-only resolution across all entries.
        for top_mfr in top_list:
            std_name = top_mfr.get('standard_name', '')
            aliases = top_mfr.get('aliases', [])

            # Try exact match first (faster, more reliable)
            brand_exact = self._exact_match(brand, std_name, aliases)
            mfr_exact = self._exact_match(manufacturer, std_name, aliases)

            if brand_exact or mfr_exact:
                # Determine which input matched (AC2)
                matched_source = "brandName" if brand_exact else "manufacturer"
                matched_raw = brand if brand_exact else manufacturer
                matched_normalized = brand_normalized if brand_exact else mfr_normalized

                return {
                    "found": True,
                    "manufacturer_id": top_mfr.get('id', ''),
                    "name": std_name,
                    "match_type": "exact",
                    # AC2: Provenance fields for auditability
                    "product_manufacturer_raw": matched_raw,
                    "product_manufacturer_normalized": matched_normalized,
                    "source_path": matched_source,
                }

        # Pass 2: fuzzy fallback only when no exact match exists.
        best_fuzzy = None
        for top_mfr in top_list:
            std_name = top_mfr.get('standard_name', '')

            # Fuzzy match as fallback for variations like "Thorne" vs "Thorne Research"
            brand_match, brand_score = self._fuzzy_company_match(brand, std_name)
            mfr_match, mfr_score = self._fuzzy_company_match(manufacturer, std_name)

            if brand_match or mfr_match:
                # Determine which input matched better (AC2)
                if brand_score >= mfr_score:
                    matched_source = "brandName"
                    matched_raw = brand
                    matched_normalized = brand_normalized
                    match_conf = brand_score
                else:
                    matched_source = "manufacturer"
                    matched_raw = manufacturer
                    matched_normalized = mfr_normalized
                    match_conf = mfr_score

                candidate = {
                    "found": True,
                    "manufacturer_id": top_mfr.get('id', ''),
                    "name": std_name,
                    "match_type": "fuzzy",
                    "match_confidence": round(match_conf, 3),
                    # AC2: Provenance fields for auditability
                    "product_manufacturer_raw": matched_raw,
                    "product_manufacturer_normalized": matched_normalized,
                    "source_path": matched_source,
                }
                if best_fuzzy is None or match_conf > best_fuzzy.get("match_confidence", 0):
                    best_fuzzy = candidate

        if best_fuzzy is not None:
            return best_fuzzy

        # AC2: Include provenance even for non-matches
        return {
            "found": False,
            "product_manufacturer_raw": manufacturer or brand,
            "product_manufacturer_normalized": mfr_normalized or brand_normalized,
            "source_path": "manufacturer" if manufacturer else "brandName",
        }

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
                total_deduction_applied = violation.get('total_deduction_applied', 0.0)
                found.append({
                    "violation_id": violation.get('id', ''),
                    "violation_type": violation.get('violation_type', ''),
                    "severity_level": violation.get('severity_level', ''),
                    "date": violation.get('date', ''),
                    "total_deduction_applied": total_deduction_applied,
                    # Backward-compatible alias for legacy consumers.
                    "total_deduction": total_deduction_applied,
                    "is_resolved": violation.get('is_resolved', False),
                    "match_confidence": round(match_score, 3)
                })

        total_deduction_applied = 0.0
        for item in found:
            try:
                total_deduction_applied += float(item.get("total_deduction_applied", 0.0) or 0.0)
            except (TypeError, ValueError):
                continue

        return {
            "found": len(found) > 0,
            "total_deduction_applied": round(total_deduction_applied, 2),
            "violations": found
        }

    # Countries considered high-regulation for D4 scoring.
    _HIGH_REG_COUNTRIES = {
        "usa", "us", "united states", "united states of america",
        "canada", "uk", "united kingdom", "germany", "switzerland",
        "japan", "australia", "new zealand", "norway", "sweden",
        "denmark", "eu",
    }

    def _extract_country(self, product: Dict) -> Dict:
        """Extract country of origin data.

        Detection order:
        1. Regex scan of label text ("made in USA", etc.)
        2. Structured contacts[].contactDetails.country for Manufacturer contacts
        """
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

        # Fallback: read structured contacts for Manufacturer address
        if not country:
            for contact in product.get("contacts", []):
                if "Manufacturer" in (contact.get("types") or []):
                    details = contact.get("contactDetails", {}) or {}
                    raw_country = (details.get("country") or "").strip()
                    if raw_country:
                        country = raw_country
                        if raw_country.lower() in self._HIGH_REG_COUNTRIES:
                            high_reg = True
                        break

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
            std_name = ingredient.get('standardName', '').lower()
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
            is_probiotic = any(term in ing_name or term in std_name for term in probiotic_terms)
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

        prebiotic_candidates = []
        for ing in all_ingredients:
            ing_name = ing.get('name', '')
            std_name = ing.get('standardName', '') or ing_name
            prebiotic_candidates.append((ing_name, std_name))

            # Include nested blend children so prebiotic rows inside proprietary
            # blends are not silently missed.
            for nested_ing in ing.get('nestedIngredients', []) or []:
                if not isinstance(nested_ing, dict):
                    continue
                nested_name = nested_ing.get('name', '')
                nested_std = nested_ing.get('standardName', '') or nested_name
                prebiotic_candidates.append((nested_name, nested_std))

        for ing_name, std_name in prebiotic_candidates:
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

    def _canonical_token(self, value: Any) -> str:
        """Normalize free text to a stable underscore token for deterministic matching."""
        normalized = self._normalize_text(str(value or ""))
        return re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")

    def _word_token_match(self, token: str, haystack: str) -> bool:
        """Word-boundary token match that tolerates spaces/hyphens in tokens."""
        normalized = self._normalize_text(token)
        if not normalized:
            return False
        pattern = r"\b" + re.escape(normalized).replace(r"\ ", r"[\s\-]+") + r"\b"
        return bool(re.search(pattern, haystack, re.IGNORECASE))

    def _percentile_category_fallback_id(self, categories: Dict[str, Any]) -> str:
        for category_id, category_def in categories.items():
            if isinstance(category_def, dict) and category_def.get("is_fallback"):
                return str(category_id)
        return "general_supplement"

    def _collect_percentile_context(
        self,
        product: Dict[str, Any],
        enriched: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Collect normalized context fields used for percentile category inference."""
        name_blob = " ".join(
            str(v)
            for v in (
                product.get("fullName"),
                product.get("product_name"),
                product.get("bundleName"),
                enriched.get("product_name"),
            )
            if v
        )
        normalized_name = self._normalize_text(name_blob)

        canonical_ingredients: set[str] = set()
        iqd = enriched.get("ingredient_quality_data", {}) or {}
        ingredient_rows = iqd.get("ingredients_scorable") or iqd.get("ingredients") or []
        for ingredient in ingredient_rows:
            if not isinstance(ingredient, dict):
                continue
            for key in ("canonical_id", "standard_name", "standardName", "name"):
                token = self._canonical_token(ingredient.get(key))
                if token:
                    canonical_ingredients.add(token)

        supp_type = (
            enriched.get("supplement_type", {}).get("type")
            if isinstance(enriched.get("supplement_type"), dict)
            else enriched.get("supplement_type")
        )
        supplement_type = self._normalize_text(supp_type)

        form_factor = self._normalize_text(
            enriched.get("form_factor")
            or product.get("form_factor")
            or product.get("product_form")
            or ""
        )

        return {
            "normalized_name": normalized_name,
            "canonical_ingredients": canonical_ingredients,
            "supplement_type": supplement_type,
            "form_factor": form_factor,
        }

    def _infer_percentile_category(self, product: Dict, enriched: Dict) -> Dict[str, Any]:
        """
        Infer a stable percentile category for cohort scoring.

        Priority:
        1) explicit percentile_category in source payload (if valid)
        2) deterministic rule inference from percentile_categories database
        3) fallback category
        """
        db = self.databases.get("percentile_categories", {}) or {}
        categories = db.get("categories") if isinstance(db, dict) else None
        rules = db.get("classification_rules") if isinstance(db, dict) else None

        if not isinstance(categories, dict) or not categories:
            return {
                "percentile_category": "general_supplement",
                "percentile_category_label": "General Supplements",
                "percentile_category_source": "fallback",
                "percentile_category_confidence": 0.0,
                "percentile_category_signals": ["missing_percentile_categories_config"],
            }

        fallback_category = self._percentile_category_fallback_id(categories)
        fallback_label = str(
            (categories.get(fallback_category) or {}).get("label") or "General Supplements"
        )

        explicit_category = self._canonical_token(
            product.get("percentile_category") or enriched.get("percentile_category")
        )
        if explicit_category and explicit_category in categories:
            explicit_def = categories.get(explicit_category) or {}
            return {
                "percentile_category": explicit_category,
                "percentile_category_label": str(explicit_def.get("label") or explicit_category),
                "percentile_category_source": "explicit",
                "percentile_category_confidence": 1.0,
                "percentile_category_signals": ["explicit_field"],
            }

        context = self._collect_percentile_context(product, enriched)
        name_blob = context["normalized_name"]
        canonical_ingredients = context["canonical_ingredients"]
        supplement_type = context["supplement_type"]
        form_factor = context["form_factor"]

        candidates: List[Dict[str, Any]] = []
        for category_id, category_def in categories.items():
            if not isinstance(category_def, dict):
                continue
            if category_def.get("is_fallback"):
                continue

            required = category_def.get("required") or {}
            required_forms = required.get("form") if isinstance(required, dict) else None
            if required_forms:
                form_values = {
                    self._canonical_token(v)
                    for v in (required_forms if isinstance(required_forms, list) else [required_forms])
                    if v
                }
                if self._canonical_token(form_factor) not in form_values:
                    continue

            evidence_score = 0.0
            matched_signals: List[str] = []
            evidence = category_def.get("evidence") or {}

            name_evidence = evidence.get("name_tokens") if isinstance(evidence, dict) else None
            if isinstance(name_evidence, dict):
                weight = float(name_evidence.get("weight", 0))
                for token in name_evidence.get("values", []) or []:
                    if self._word_token_match(str(token), name_blob):
                        evidence_score += weight
                        matched_signals.append(f"name:{self._normalize_text(token)}")

            ing_evidence = evidence.get("canonical_ingredients") if isinstance(evidence, dict) else None
            if isinstance(ing_evidence, dict):
                weight = float(ing_evidence.get("weight", 0))
                min_match = int(ing_evidence.get("min_match", 1) or 1)
                configured = {
                    self._canonical_token(value)
                    for value in (ing_evidence.get("values") or [])
                    if value
                }
                matches = sorted(configured & canonical_ingredients)
                if len(matches) >= min_match:
                    evidence_score += weight * len(matches)
                    matched_signals.extend([f"ingredient:{m}" for m in matches])

            type_evidence = evidence.get("supplement_types") if isinstance(evidence, dict) else None
            if isinstance(type_evidence, dict):
                weight = float(type_evidence.get("weight", 0))
                configured_types = {
                    self._normalize_text(value) for value in (type_evidence.get("values") or []) if value
                }
                if supplement_type and supplement_type in configured_types:
                    evidence_score += weight
                    matched_signals.append(f"supp_type:{supplement_type}")

            min_evidence_score = float(category_def.get("min_evidence_score", 0) or 0)
            if evidence_score < min_evidence_score:
                continue

            candidates.append(
                {
                    "category": str(category_id),
                    "label": str(category_def.get("label") or category_id),
                    "score": evidence_score,
                    "signals": matched_signals,
                    "priority": int(category_def.get("priority", 999)),
                }
            )

        if not candidates:
            return {
                "percentile_category": fallback_category,
                "percentile_category_label": fallback_label,
                "percentile_category_source": "fallback",
                "percentile_category_confidence": 0.0,
                "percentile_category_signals": [],
            }

        candidates.sort(key=lambda item: (-item["score"], item["priority"], item["category"]))
        best = candidates[0]
        second = candidates[1] if len(candidates) > 1 else None

        rules = rules if isinstance(rules, dict) else {}
        margin_threshold = float(rules.get("margin_threshold", 2.0) or 2.0)
        confidence_threshold = float(rules.get("confidence_threshold", 0.4) or 0.4)
        score_normalizer = float(rules.get("score_normalizer", 12.0) or 12.0)
        second_score = float(second["score"]) if second else 0.0
        margin = float(best["score"]) - second_score

        if (
            second
            and best["score"] == second["score"]
            and best["priority"] == second["priority"]
            and margin < margin_threshold
        ):
            return {
                "percentile_category": fallback_category,
                "percentile_category_label": fallback_label,
                "percentile_category_source": "fallback",
                "percentile_category_confidence": 0.0,
                "percentile_category_signals": ["ambiguous_tie"],
            }

        raw_confidence = min(float(best["score"]) / max(score_normalizer, 1.0), 1.0)
        margin_factor = 1.0 if not second else min(margin / max(margin_threshold, 1.0), 1.0)
        confidence = round(raw_confidence * max(margin_factor, 0.0), 2)
        if confidence < confidence_threshold:
            return {
                "percentile_category": fallback_category,
                "percentile_category_label": fallback_label,
                "percentile_category_source": "fallback",
                "percentile_category_confidence": confidence,
                "percentile_category_signals": best["signals"] + ["low_confidence"],
            }

        return {
            "percentile_category": best["category"],
            "percentile_category_label": best["label"],
            "percentile_category_source": "inferred",
            "percentile_category_confidence": confidence,
            "percentile_category_signals": best["signals"],
        }

    def _classify_supplement_type(self, product: Dict) -> Dict:
        """
        Classify supplement type for context-aware scoring.
        Types: single_nutrient, targeted, multivitamin, herbal_blend, probiotic, prebiotic, specialty
        """
        active_ingredients = product.get('activeIngredients', [])
        inactive_ingredients = product.get('inactiveIngredients', [])

        active_count = len(active_ingredients)
        total_count = active_count + len(inactive_ingredients)

        # Count categories AND detect probiotic ingredients by name
        category_counts = {}
        probiotic_name_count = 0
        _probiotic_terms = (
            'probiotic', 'lactobacillus', 'bifidobacterium',
            'streptococcus', 'bacillus', 'saccharomyces',
            'limosilactobacillus', 'lacticaseibacillus',
        )
        _probiotic_cats = {'probiotic', 'bacteria'}
        for ing in active_ingredients:
            cat = ing.get('category', 'other').lower()
            category_counts[cat] = category_counts.get(cat, 0) + 1
            # Name-based detection only for ingredients NOT already
            # counted by their category (avoids double-counting)
            if cat not in _probiotic_cats:
                ing_name = (
                    ing.get('name', '') or ''
                ).lower()
                std_name = (
                    ing.get('standardName', '') or ''
                ).lower()
                if any(t in ing_name or t in std_name
                       for t in _probiotic_terms):
                    probiotic_name_count += 1

        # Determine type
        supplement_type = "unknown"

        # Probiotic detection: category + ingredient names (deduplicated)
        probiotic_total = (
            category_counts.get('probiotic', 0)
            + category_counts.get('bacteria', 0)
            + probiotic_name_count
        )
        product_name_text = " ".join([
            str(product.get('product_name', '') or ''),
            str(product.get('fullName', '') or ''),
            str(product.get('bundleName', '') or ''),
        ]).lower()
        probiotic_name_signal = any(term in product_name_text for term in _probiotic_terms)

        # Probiotic — check first so single-strain products
        # are classified correctly
        if probiotic_total > 0 and (
            active_count == 1
            or probiotic_total >= active_count * 0.5
            or probiotic_name_signal
        ):
            supplement_type = "probiotic"

        # Single nutrient (non-probiotic)
        elif active_count == 1:
            supplement_type = "single_nutrient"

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
        min_servings_per_day = None
        max_servings_per_day = None
        servings_per_day_source = "default"

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

                # Normalize unit using deterministic map (not heuristics)
                if basis_unit:
                    basis_unit_raw = basis_unit.lower().strip()
                    # Clean up parenthetical variants like "(ies)", "(s)", "(es)"
                    basis_unit_raw = basis_unit_raw.replace('(ies)', '')
                    basis_unit_raw = basis_unit_raw.replace('(s)', '')
                    basis_unit_raw = basis_unit_raw.replace('(es)', '')
                    # Remove any unclosed parens
                    basis_unit_raw = re.sub(r'\([^)]*$', '', basis_unit_raw).strip()
                    # Use deterministic map for canonical form
                    basis_unit = SERVING_UNIT_NORMALIZATION_MAP.get(
                        basis_unit_raw, basis_unit_raw
                    )

                # Extract daily servings if provided by DSLD
                min_servings_per_day = (
                    primary_serving.get('minDailyServings') or
                    primary_serving.get('minServingsPerDay') or
                    primary_serving.get('min_daily_servings')
                )
                max_servings_per_day = (
                    primary_serving.get('maxDailyServings') or
                    primary_serving.get('maxServingsPerDay') or
                    primary_serving.get('max_daily_servings')
                )
                if min_servings_per_day is not None or max_servings_per_day is not None:
                    servings_per_day_source = "servingSizes"

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

        if min_servings_per_day is None and max_servings_per_day is None and parsed_from_directions:
            if min_recommended is not None or max_recommended is not None:
                min_servings_per_day = min_recommended
                max_servings_per_day = max_recommended
                servings_per_day_source = "directions"

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
                "min_servings_per_day": min_servings_per_day,
                "max_servings_per_day": max_servings_per_day,
                "servings_per_day_source": servings_per_day_source,
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

        return sorted(set(found))

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

        return sorted(set(found))

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
            "high_glycemic": sorted(set(found_high_glycemic)),
            "artificial": sorted(set(found_artificial)),
            "sugar_alcohols": sorted(set(found_sugar_alcohols)),
            "safer_alternatives": sorted(set(found_safer)),
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
    # INTERACTION PROFILE COLLECTOR (alerts-only, score-neutral)
    # =========================================================================

    def _empty_interaction_profile(self, taxonomy_version: Optional[str] = None,
                                   rules_version: Optional[str] = None) -> Dict:
        return {
            "ingredient_alerts": [],
            "condition_summary": {},
            "drug_class_summary": {},
            "highest_severity": None,
            "data_sources": [],
            "rules_version": rules_version,
            "taxonomy_version": taxonomy_version,
            "user_condition_alerts": {
                "enabled": False,
                "conditions_checked": [],
                "drug_classes_checked": [],
                "alerts": [],
                "highest_severity": None
            }
        }

    def _interaction_severity_weight_map(self, taxonomy_db: Dict) -> Dict[str, float]:
        default = {
            "contraindicated": 5.0,
            "avoid": 4.0,
            "caution": 3.0,
            "monitor": 2.0,
            "info": 1.0,
        }
        levels = taxonomy_db.get("severity_levels", [])
        if not isinstance(levels, list):
            return default
        for level in levels:
            if not isinstance(level, dict):
                continue
            level_id = str(level.get("id", "")).strip().lower()
            if not level_id:
                continue
            try:
                default[level_id] = float(level.get("weight", default.get(level_id, 1.0)))
            except (TypeError, ValueError):
                continue
        return default

    def _normalize_interaction_db_key(self, value: Any) -> Optional[str]:
        db_key = str(value or "").strip().lower()
        valid = {
            "ingredient_quality_map",
            "other_ingredients",
            "harmful_additives",
            "banned_recalled_ingredients",
            "botanical_ingredients",
        }
        return db_key if db_key in valid else None

    def _derive_interaction_subject_ref(self, ingredient: Dict) -> Optional[Dict[str, str]]:
        canonical_id = str(ingredient.get("canonical_id") or "").strip()
        if canonical_id:
            return {
                "db": "ingredient_quality_map",
                "canonical_id": canonical_id,
            }

        recognition_source = self._normalize_interaction_db_key(ingredient.get("recognition_source"))
        recognized_id = str(
            ingredient.get("matched_entry_id")
            or ingredient.get("recognized_entry_id")
            or ""
        ).strip()
        if recognition_source and recognized_id:
            return {
                "db": recognition_source,
                "canonical_id": recognized_id,
            }
        return None

    def _interaction_rule_applies(self, rule: Dict, ingredient: Dict) -> bool:
        form_scope = rule.get("form_scope")
        if form_scope is None:
            return True
        if not isinstance(form_scope, list) or not form_scope:
            return False
        form_id = str(ingredient.get("form_id") or "").strip()
        if not form_id:
            return False
        return form_id in {str(item).strip() for item in form_scope if str(item).strip()}

    def _collect_profile_context(self, user_profile: Any) -> Dict[str, List[str]]:
        if not isinstance(user_profile, dict):
            return {"conditions": [], "drug_classes": []}

        def _collect_ids(raw: Any) -> List[str]:
            items: List[str] = []
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, str):
                        value = item.strip().lower()
                        if value:
                            items.append(value)
                    elif isinstance(item, dict):
                        value = str(item.get("id") or item.get("condition_id") or item.get("drug_class_id") or "").strip().lower()
                        if value:
                            items.append(value)
            elif isinstance(raw, str):
                value = raw.strip().lower()
                if value:
                    items.append(value)
            return items

        condition_fields = ("conditions", "condition_ids", "health_conditions")
        drug_fields = ("drug_classes", "medication_classes")

        conditions: List[str] = []
        drug_classes: List[str] = []

        for field in condition_fields:
            conditions.extend(_collect_ids(user_profile.get(field)))
        for field in drug_fields:
            drug_classes.extend(_collect_ids(user_profile.get(field)))

        return {
            "conditions": sorted(set(conditions)),
            "drug_classes": sorted(set(drug_classes)),
        }

    def _normalize_threshold_unit(self, unit: Any) -> str:
        text = str(unit or "").strip().lower()
        text = text.replace("µg", "mcg").replace("μg", "mcg").replace(" ", "").replace("_", "")
        alias_map = {
            "ug": "mcg",
            "microgram": "mcg",
            "micrograms": "mcg",
            "milligram": "mg",
            "milligrams": "mg",
            "gram": "g",
            "grams": "g",
            "internationalunits": "iu",
            "internationalunit": "iu",
        }
        return alias_map.get(text, text)

    def _is_mass_unit(self, unit: str) -> bool:
        return unit in {"mcg", "mg", "g"}

    def _convert_mass(self, value: float, from_unit: str, to_unit: str) -> Optional[float]:
        if not (self._is_mass_unit(from_unit) and self._is_mass_unit(to_unit)):
            return None
        factors_mg = {
            "mcg": 0.001,
            "mg": 1.0,
            "g": 1000.0,
        }
        mg_value = value * factors_mg[from_unit]
        return mg_value / factors_mg[to_unit]

    def _to_float_safe(self, value: Any) -> Optional[float]:
        try:
            converted = float(value)
            if math.isfinite(converted):
                return converted
        except (TypeError, ValueError):
            return None
        return None

    def _compare_threshold(self, amount: float, comparator: str, threshold: float) -> Optional[bool]:
        if comparator == ">":
            return amount > threshold
        if comparator == ">=":
            return amount >= threshold
        if comparator == "<":
            return amount < threshold
        if comparator == "<=":
            return amount <= threshold
        if comparator == "==":
            return amount == threshold
        return None

    def _convert_amount_to_target_unit(
        self,
        amount: float,
        from_unit: str,
        target_unit: str,
        ingredient_name: str,
        standard_name: str,
    ) -> Tuple[Optional[float], Optional[str]]:
        src = self._normalize_threshold_unit(from_unit)
        tgt = self._normalize_threshold_unit(target_unit)
        if not src or not tgt:
            return None, "missing_unit"
        if src == tgt:
            return amount, None

        mass_converted = self._convert_mass(amount, src, tgt)
        if mass_converted is not None:
            return mass_converted, None

        # Try nutrient-aware conversion (IU/RAE and nutrient-specific transforms).
        if self.unit_converter:
            try:
                conversion = self.unit_converter.convert_nutrient(
                    nutrient=standard_name or ingredient_name,
                    amount=amount,
                    from_unit=src,
                    ingredient_name=ingredient_name
                )
                conv_value = getattr(conversion, "converted_value", None)
                conv_unit = self._normalize_threshold_unit(getattr(conversion, "converted_unit", None))
                conv_success = bool(getattr(conversion, "success", False))
                if conv_success and conv_value is not None and conv_unit:
                    if conv_unit == tgt:
                        return float(conv_value), None
                    mass_from_conv = self._convert_mass(float(conv_value), conv_unit, tgt)
                    if mass_from_conv is not None:
                        return mass_from_conv, None
            except Exception as e:
                self.logger.warning(
                    "Dosage conversion exception for ingredient='%s' standard='%s' "
                    "amount=%s from_unit='%s' target_unit='%s': %s",
                    ingredient_name,
                    standard_name,
                    amount,
                    src,
                    tgt,
                    e,
                )
                return None, "conversion_exception"

        return None, "no_conversion_rule"

    def _evaluate_dose_thresholds_for_target(
        self,
        thresholds: List[Dict[str, Any]],
        target_type: str,
        target_id: str,
        ingredient: Dict[str, Any],
        servings_per_day_max: float,
        base_severity: str,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        relevant = []
        for threshold in thresholds:
            if not isinstance(threshold, dict):
                continue
            scope = str(threshold.get("scope") or "").strip().lower()
            scoped_target = str(threshold.get("target_id") or "").strip().lower()
            if scope == target_type and scoped_target == target_id:
                relevant.append(threshold)
        if not relevant:
            return base_severity, None

        quantity = self._to_float_safe(ingredient.get("quantity"))
        unit = self._normalize_threshold_unit(ingredient.get("unit"))
        ingredient_name = str(ingredient.get("raw_source_text") or ingredient.get("name") or "")
        standard_name = str(ingredient.get("standard_name") or "")
        if quantity is None or quantity <= 0 or not unit:
            return base_severity, {
                "evaluated": False,
                "reason": "missing_or_invalid_dose",
            }

        severity_candidate = base_severity
        evaluated_any = False
        details: Dict[str, Any] = {
            "evaluated": False,
            "matched_threshold": False,
            "thresholds_checked": [],
        }

        for threshold in relevant:
            comparator = str(threshold.get("comparator") or "").strip()
            threshold_value = self._to_float_safe(threshold.get("value"))
            threshold_unit = self._normalize_threshold_unit(threshold.get("unit"))
            basis = str(threshold.get("basis") or "per_day").strip().lower()
            severity_if_met = str(threshold.get("severity_if_met") or "").strip().lower()
            severity_if_not_met = str(threshold.get("severity_if_not_met") or "").strip().lower()
            if threshold_value is None or not threshold_unit or not comparator:
                details["thresholds_checked"].append({
                    "evaluated": False,
                    "reason": "invalid_threshold_definition",
                    "threshold": threshold,
                })
                continue

            amount_basis = quantity * (servings_per_day_max if basis == "per_day" else 1.0)
            converted_amount, convert_reason = self._convert_amount_to_target_unit(
                amount=amount_basis,
                from_unit=unit,
                target_unit=threshold_unit,
                ingredient_name=ingredient_name,
                standard_name=standard_name,
            )
            if converted_amount is None:
                details["thresholds_checked"].append({
                    "evaluated": False,
                    "reason": convert_reason or "conversion_failed",
                    "basis": basis,
                    "threshold_value": threshold_value,
                    "threshold_unit": threshold_unit,
                    "comparator": comparator,
                })
                continue

            comparison = self._compare_threshold(converted_amount, comparator, threshold_value)
            if comparison is None:
                details["thresholds_checked"].append({
                    "evaluated": False,
                    "reason": "invalid_comparator",
                    "basis": basis,
                    "computed_amount": converted_amount,
                    "threshold_value": threshold_value,
                    "threshold_unit": threshold_unit,
                    "comparator": comparator,
                })
                continue

            evaluated_any = True
            checked = {
                "evaluated": True,
                "basis": basis,
                "computed_amount": converted_amount,
                "computed_unit": threshold_unit,
                "threshold_value": threshold_value,
                "threshold_unit": threshold_unit,
                "comparator": comparator,
                "matched": bool(comparison),
            }
            details["thresholds_checked"].append(checked)

            if comparison and severity_if_met:
                severity_candidate = severity_if_met
                details["matched_threshold"] = True
                details["selected_from"] = "severity_if_met"
                details["selected_severity"] = severity_candidate
                break
            if (not comparison) and severity_if_not_met:
                severity_candidate = severity_if_not_met
                details["selected_from"] = "severity_if_not_met"
                details["selected_severity"] = severity_candidate

        details["evaluated"] = evaluated_any
        if not evaluated_any and "selected_severity" not in details:
            details["selected_severity"] = base_severity
            details["selected_from"] = "base_severity"
            details["reason"] = "dose_threshold_not_evaluable"
        elif "selected_severity" not in details:
            details["selected_severity"] = severity_candidate
            details["selected_from"] = "base_severity" if severity_candidate == base_severity else "threshold_not_met_override"

        return severity_candidate, details

    def _collect_interaction_profile(self, enriched: Dict, user_profile: Optional[Dict] = None) -> Dict:
        taxonomy_db = self.databases.get("clinical_risk_taxonomy", {}) or {}
        rules_db = self.databases.get("ingredient_interaction_rules", {}) or {}
        taxonomy_version = (taxonomy_db.get("_metadata") or {}).get("schema_version")
        rules_version = (rules_db.get("_metadata") or {}).get("schema_version")
        profile = self._empty_interaction_profile(
            taxonomy_version=taxonomy_version,
            rules_version=rules_version
        )

        iqd = enriched.get("ingredient_quality_data", {}) or {}
        ingredients = iqd.get("ingredients", [])
        skipped = iqd.get("ingredients_skipped", [])
        if not isinstance(ingredients, list):
            ingredients = []
        if not isinstance(skipped, list):
            skipped = []

        for ingredient in ingredients:
            if isinstance(ingredient, dict):
                ingredient["safety_hits"] = []
        for ingredient in skipped:
            if isinstance(ingredient, dict):
                ingredient["safety_hits"] = []

        condition_defs = taxonomy_db.get("conditions", []) if isinstance(taxonomy_db, dict) else []
        drug_defs = taxonomy_db.get("drug_classes", []) if isinstance(taxonomy_db, dict) else []
        evidence_defs = taxonomy_db.get("evidence_levels", []) if isinstance(taxonomy_db, dict) else []
        valid_conditions = {
            str(item.get("id")).strip().lower(): item
            for item in condition_defs if isinstance(item, dict) and item.get("id")
        }
        valid_drug_classes = {
            str(item.get("id")).strip().lower(): item
            for item in drug_defs if isinstance(item, dict) and item.get("id")
        }
        valid_evidence = {
            str(item.get("id")).strip().lower()
            for item in evidence_defs if isinstance(item, dict) and item.get("id")
        }
        severity_weights = self._interaction_severity_weight_map(taxonomy_db)
        serving_basis = enriched.get("serving_basis", {}) if isinstance(enriched, dict) else {}
        servings_per_day_max = self._to_float_safe((serving_basis or {}).get("max_servings_per_day"))
        if servings_per_day_max is None or servings_per_day_max <= 0:
            servings_per_day_max = self._to_float_safe((serving_basis or {}).get("min_servings_per_day"))
        if servings_per_day_max is None or servings_per_day_max <= 0:
            servings_per_day_max = 1.0

        raw_rules = rules_db.get("interaction_rules", []) if isinstance(rules_db, dict) else []
        if not isinstance(raw_rules, list) or not raw_rules:
            return profile

        rule_index: Dict[Tuple[str, str], List[Dict]] = {}
        for rule in raw_rules:
            if not isinstance(rule, dict):
                continue
            subject_ref = rule.get("subject_ref", {})
            if not isinstance(subject_ref, dict):
                continue
            db_key = self._normalize_interaction_db_key(subject_ref.get("db"))
            canonical_id = str(subject_ref.get("canonical_id") or "").strip()
            if not db_key or not canonical_id:
                continue
            rule_index.setdefault((db_key, canonical_id), []).append(rule)

        condition_summary_sets: Dict[str, Dict[str, Any]] = {}
        drug_summary_sets: Dict[str, Dict[str, Any]] = {}
        source_set: set = set()
        highest_weight = -1.0
        highest_severity: Optional[str] = None

        all_ingredient_rows: List[Tuple[str, Dict]] = []
        for row in ingredients:
            if isinstance(row, dict):
                all_ingredient_rows.append(("ingredients", row))
        for row in skipped:
            if isinstance(row, dict):
                all_ingredient_rows.append(("ingredients_skipped", row))

        for source_bucket, ingredient in all_ingredient_rows:
            subject = self._derive_interaction_subject_ref(ingredient)
            if not subject:
                continue

            matched_rules = rule_index.get((subject["db"], subject["canonical_id"]), [])
            if not matched_rules:
                continue

            ingredient_name = ingredient.get("raw_source_text") or ingredient.get("name") or ingredient.get("standard_name") or "unknown"

            for rule in matched_rules:
                if not self._interaction_rule_applies(rule, ingredient):
                    continue

                condition_hits: List[Dict[str, Any]] = []
                drug_hits: List[Dict[str, Any]] = []
                pregnancy_block = rule.get("pregnancy_lactation") if isinstance(rule.get("pregnancy_lactation"), dict) else None
                thresholds = rule.get("dose_thresholds", []) if isinstance(rule.get("dose_thresholds"), list) else []

                for cond_rule in rule.get("condition_rules", []) or []:
                    if not isinstance(cond_rule, dict):
                        continue
                    condition_id = str(cond_rule.get("condition_id") or "").strip().lower()
                    severity = str(cond_rule.get("severity") or "").strip().lower()
                    evidence = str(cond_rule.get("evidence_level") or "").strip().lower()
                    if condition_id not in valid_conditions or severity not in severity_weights:
                        continue
                    if evidence and valid_evidence and evidence not in valid_evidence:
                        continue
                    adjusted_severity, threshold_eval = self._evaluate_dose_thresholds_for_target(
                        thresholds=thresholds,
                        target_type="condition",
                        target_id=condition_id,
                        ingredient=ingredient,
                        servings_per_day_max=servings_per_day_max,
                        base_severity=severity,
                    )
                    if adjusted_severity in severity_weights:
                        severity = adjusted_severity
                    sources = [str(s).strip() for s in (cond_rule.get("sources") or []) if str(s).strip()]
                    for src in sources:
                        source_set.add(src)
                    condition_hits.append({
                        "condition_id": condition_id,
                        "severity": severity,
                        "evidence_level": evidence or None,
                        "mechanism": cond_rule.get("mechanism"),
                        "action": cond_rule.get("action"),
                        "sources": sources,
                        "dose_threshold_evaluation": threshold_eval,
                    })

                if pregnancy_block:
                    for cond_key, field in (("pregnancy", "pregnancy_category"), ("lactation", "lactation_category")):
                        severity = str(pregnancy_block.get(field) or "").strip().lower()
                        if severity and cond_key in valid_conditions and severity in severity_weights:
                            sources = [str(s).strip() for s in (pregnancy_block.get("sources") or []) if str(s).strip()]
                            for src in sources:
                                source_set.add(src)
                            condition_hits.append({
                                "condition_id": cond_key,
                                "severity": severity,
                                "evidence_level": str(pregnancy_block.get("evidence_level") or "").strip().lower() or None,
                                "mechanism": pregnancy_block.get("mechanism"),
                                "action": pregnancy_block.get("notes"),
                                "sources": sources,
                            })

                for drug_rule in rule.get("drug_class_rules", []) or []:
                    if not isinstance(drug_rule, dict):
                        continue
                    drug_class_id = str(drug_rule.get("drug_class_id") or "").strip().lower()
                    severity = str(drug_rule.get("severity") or "").strip().lower()
                    evidence = str(drug_rule.get("evidence_level") or "").strip().lower()
                    if drug_class_id not in valid_drug_classes or severity not in severity_weights:
                        continue
                    if evidence and valid_evidence and evidence not in valid_evidence:
                        continue
                    adjusted_severity, threshold_eval = self._evaluate_dose_thresholds_for_target(
                        thresholds=thresholds,
                        target_type="drug_class",
                        target_id=drug_class_id,
                        ingredient=ingredient,
                        servings_per_day_max=servings_per_day_max,
                        base_severity=severity,
                    )
                    if adjusted_severity in severity_weights:
                        severity = adjusted_severity
                    sources = [str(s).strip() for s in (drug_rule.get("sources") or []) if str(s).strip()]
                    for src in sources:
                        source_set.add(src)
                    drug_hits.append({
                        "drug_class_id": drug_class_id,
                        "severity": severity,
                        "evidence_level": evidence or None,
                        "mechanism": drug_rule.get("mechanism"),
                        "action": drug_rule.get("action"),
                        "sources": sources,
                        "dose_threshold_evaluation": threshold_eval,
                    })

                if not condition_hits and not drug_hits and not pregnancy_block:
                    continue

                safety_hit = {
                    "rule_id": rule.get("id"),
                    "subject_ref": subject,
                    "source_bucket": source_bucket,
                    "condition_hits": condition_hits,
                    "drug_class_hits": drug_hits,
                    "pregnancy_lactation": pregnancy_block or {},
                    "last_reviewed": rule.get("last_reviewed"),
                }
                ingredient.setdefault("safety_hits", []).append(safety_hit)

                profile["ingredient_alerts"].append({
                    "ingredient_name": ingredient_name,
                    "standard_name": ingredient.get("standard_name"),
                    "subject_ref": subject,
                    "rule_id": rule.get("id"),
                    "condition_hits": condition_hits,
                    "drug_class_hits": drug_hits,
                })

                for condition_hit in condition_hits:
                    condition_id = condition_hit["condition_id"]
                    bucket = condition_summary_sets.setdefault(
                        condition_id,
                        {
                            "label": valid_conditions.get(condition_id, {}).get("label", condition_id),
                            "highest_severity": None,
                            "highest_weight": -1.0,
                            "ingredients": set(),
                            "rule_ids": set(),
                            "actions": set(),
                        }
                    )
                    bucket["ingredients"].add(ingredient_name)
                    if safety_hit.get("rule_id"):
                        bucket["rule_ids"].add(safety_hit["rule_id"])
                    if condition_hit.get("action"):
                        bucket["actions"].add(str(condition_hit["action"]))
                    severity = condition_hit["severity"]
                    weight = severity_weights.get(severity, 0.0)
                    if weight > bucket["highest_weight"]:
                        bucket["highest_weight"] = weight
                        bucket["highest_severity"] = severity
                    if weight > highest_weight:
                        highest_weight = weight
                        highest_severity = severity

                for drug_hit in drug_hits:
                    drug_class_id = drug_hit["drug_class_id"]
                    bucket = drug_summary_sets.setdefault(
                        drug_class_id,
                        {
                            "label": valid_drug_classes.get(drug_class_id, {}).get("label", drug_class_id),
                            "highest_severity": None,
                            "highest_weight": -1.0,
                            "ingredients": set(),
                            "rule_ids": set(),
                            "actions": set(),
                        }
                    )
                    bucket["ingredients"].add(ingredient_name)
                    if safety_hit.get("rule_id"):
                        bucket["rule_ids"].add(safety_hit["rule_id"])
                    if drug_hit.get("action"):
                        bucket["actions"].add(str(drug_hit["action"]))
                    severity = drug_hit["severity"]
                    weight = severity_weights.get(severity, 0.0)
                    if weight > bucket["highest_weight"]:
                        bucket["highest_weight"] = weight
                        bucket["highest_severity"] = severity
                    if weight > highest_weight:
                        highest_weight = weight
                        highest_severity = severity

        profile["condition_summary"] = {
            key: {
                "label": value["label"],
                "highest_severity": value["highest_severity"],
                "ingredient_count": len(value["ingredients"]),
                "ingredients": sorted(value["ingredients"]),
                "rule_ids": sorted(value["rule_ids"]),
                "actions": sorted(value["actions"]),
            }
            for key, value in condition_summary_sets.items()
        }
        profile["drug_class_summary"] = {
            key: {
                "label": value["label"],
                "highest_severity": value["highest_severity"],
                "ingredient_count": len(value["ingredients"]),
                "ingredients": sorted(value["ingredients"]),
                "rule_ids": sorted(value["rule_ids"]),
                "actions": sorted(value["actions"]),
            }
            for key, value in drug_summary_sets.items()
        }
        profile["highest_severity"] = highest_severity
        profile["data_sources"] = sorted(source_set)

        context = self._collect_profile_context(user_profile)
        conditions_checked = context.get("conditions", [])
        drug_classes_checked = context.get("drug_classes", [])
        user_alerts = {
            "enabled": bool(conditions_checked or drug_classes_checked),
            "conditions_checked": conditions_checked,
            "drug_classes_checked": drug_classes_checked,
            "alerts": [],
            "highest_severity": None,
        }
        user_highest_weight = -1.0
        for ingredient_alert in profile["ingredient_alerts"]:
            ingredient_name = ingredient_alert.get("ingredient_name", "unknown")
            rule_id = ingredient_alert.get("rule_id")
            for condition_hit in ingredient_alert.get("condition_hits", []):
                condition_id = condition_hit.get("condition_id")
                if condition_id in conditions_checked:
                    severity = condition_hit.get("severity")
                    weight = severity_weights.get(severity, 0.0)
                    user_alerts["alerts"].append({
                        "type": "condition",
                        "condition_id": condition_id,
                        "ingredient_name": ingredient_name,
                        "rule_id": rule_id,
                        "severity": severity,
                        "action": condition_hit.get("action"),
                    })
                    if weight > user_highest_weight:
                        user_highest_weight = weight
                        user_alerts["highest_severity"] = severity
            for drug_hit in ingredient_alert.get("drug_class_hits", []):
                drug_class_id = drug_hit.get("drug_class_id")
                if drug_class_id in drug_classes_checked:
                    severity = drug_hit.get("severity")
                    weight = severity_weights.get(severity, 0.0)
                    user_alerts["alerts"].append({
                        "type": "drug_class",
                        "drug_class_id": drug_class_id,
                        "ingredient_name": ingredient_name,
                        "rule_id": rule_id,
                        "severity": severity,
                        "action": drug_hit.get("action"),
                    })
                    if weight > user_highest_weight:
                        user_highest_weight = weight
                        user_alerts["highest_severity"] = severity

        profile["user_condition_alerts"] = user_alerts
        return profile

    def _empty_rda_ul_payload(self, reason: str) -> Dict:
        """Return a schema-stable empty RDA/UL payload when collection is skipped."""
        return {
            "ingredients_with_rda": [],
            "analyzed_ingredients": [],
            "count": 0,
            "adequacy_results": [],
            "conversion_evidence": [],
            "safety_flags": [],
            "has_over_ul": False,
            "collection_enabled": False,
            "collection_reason": reason
        }

    # =========================================================================
    # RDA/UL DATA COLLECTOR (for user profile scoring on device)
    # =========================================================================

    def _collect_rda_ul_data(
        self,
        product: Dict,
        min_servings_per_day: Optional[float] = None,
        max_servings_per_day: Optional[float] = None
    ) -> Dict:
        """
        Collect RDA/UL reference data for user profile scoring (Section E).

        Uses RDAULCalculator and UnitConverter for evidence-based adequacy:
        - Unit conversion with form detection (Vitamin A, E)
        - Adequacy band classification
        - Safety flag generation for over-UL nutrients
        - Full evidence tracking
        """
        active_ingredients = product.get('activeIngredients', [])
        rda_data = []
        adequacy_results = []
        safety_flags = []
        conversion_evidence = []
        try:
            servings_min = float(min_servings_per_day) if min_servings_per_day is not None else None
        except (TypeError, ValueError):
            servings_min = None
        try:
            servings_max = float(max_servings_per_day) if max_servings_per_day is not None else None
        except (TypeError, ValueError):
            servings_max = None

        if servings_min is None or servings_min <= 0:
            servings_min = 1
        if servings_max is None or servings_max <= 0:
            servings_max = servings_min

        # Use new modules if available
        if self.unit_converter and self.rda_calculator:
            try:
                for ingredient in active_ingredients:
                    ing_name = ingredient.get('name', '')
                    std_name = ingredient.get('standardName', '') or ing_name
                    quantity = ingredient.get('quantity', 0)
                    unit = ingredient.get('unit', '')

                    # Convert quantity to float safely
                    try:
                        quantity_float = float(quantity) if quantity else 0
                    except (ValueError, TypeError):
                        continue

                    if quantity_float == 0:
                        continue

                    # Step 1: Convert units with form detection
                    conversion = self.unit_converter.convert_nutrient(
                        nutrient=std_name,
                        amount=quantity_float,
                        from_unit=unit,
                        ingredient_name=ing_name
                    )

                    conv_evidence = conversion.to_dict()
                    conv_evidence["ingredient"] = ing_name
                    conversion_evidence.append(conv_evidence)

                    # Step 2: Compute adequacy with converted amount
                    rule_id = (conversion.conversion_rule_id or '').lower()
                    form_detected = (conversion.form_detected or '').lower()
                    unknown_form = (
                        'unknown' in rule_id or
                        'unknown' in form_detected or
                        'unspecified' in form_detected
                    )
                    conversion_failed = (
                        not conversion.success or
                        conversion.converted_value is None or
                        conversion.converted_unit is None
                    )
                    if conversion_failed:
                        unit_normalized = unit.lower().replace('µg', 'mcg').replace(' ', '_').strip()
                        if unit_normalized.startswith('mcg') or unit_normalized.startswith('mg') or unit_normalized == 'g':
                            conversion_failed = False
                    skip_ul_check = False
                    skip_ul_reason = None
                    if unknown_form:
                        skip_ul_check = True
                        skip_ul_reason = "unknown_vitamin_form"
                    elif conversion_failed:
                        skip_ul_check = True
                        skip_ul_reason = "conversion_failed"

                    converted_amount = conversion.converted_value or float(quantity)
                    converted_unit = conversion.converted_unit or unit
                    per_day_min = converted_amount * servings_min
                    per_day_max = converted_amount * servings_max
                    amount_for_ul = per_day_max or per_day_min or converted_amount

                    adequacy = self.rda_calculator.compute_nutrient_adequacy(
                        nutrient=std_name,
                        amount=amount_for_ul,
                        unit=converted_unit
                    )

                    adequacy_dict = adequacy.to_dict()
                    if skip_ul_check:
                        adequacy_dict.update({
                            "rda_ai": None,
                            "rda_ai_source": "unknown",
                            "ul": None,
                            "ul_status": f"skipped_{skip_ul_reason}",
                            "pct_rda": None,
                            "pct_ul": None,
                            "adequacy_band": "unknown",
                            "over_ul": False,
                            "over_ul_amount": None,
                            "scoring_eligible": False,
                            "point_recommendation": 0,
                            "notes": [f"UL check skipped: {skip_ul_reason}"],
                            "warnings": []
                        })
                        adequacy_dict["skip_ul_check"] = True
                        adequacy_dict["skip_ul_reason"] = skip_ul_reason
                        if skip_ul_reason == "unknown_vitamin_form":
                            adequacy_dict["form_confidence"] = "LOW"
                    else:
                        adequacy_dict["skip_ul_check"] = False
                    adequacy_dict["original_quantity"] = quantity
                    adequacy_dict["original_unit"] = unit
                    adequacy_dict["conversion_applied"] = conversion.success
                    adequacy_dict["per_day_min"] = per_day_min
                    adequacy_dict["per_day_max"] = per_day_max
                    adequacy_dict["servings_per_day_min"] = servings_min
                    adequacy_dict["servings_per_day_max"] = servings_max
                    adequacy_results.append(adequacy_dict)

                    # Collect safety flags
                    if not skip_ul_check and adequacy.over_ul:
                        pct_ul_val = adequacy.pct_ul or 0
                        over_ul_amount = adequacy.over_ul_amount or 0
                        safety_flags.append({
                            "nutrient": ing_name,
                            "amount": amount_for_ul,
                            "unit": converted_unit,
                            "ul": adequacy.ul,
                            "pct_ul": pct_ul_val,
                            "over_amount": over_ul_amount,
                            "warning": f"Exceeds UL by {over_ul_amount:.1f}",
                            "severity": "critical" if pct_ul_val >= 200 else "warning"
                        })

                    # Legacy format for backward compatibility
                    rda_data.append({
                        "ingredient": ing_name,
                        "standard_name": std_name,
                        "quantity": quantity,
                        "unit": unit,
                        "converted_quantity": converted_amount,
                        "converted_unit": converted_unit,
                        "per_day_min": per_day_min,
                        "per_day_max": per_day_max,
                        "servings_per_day_min": servings_min,
                        "servings_per_day_max": servings_max,
                        "skip_ul_check": skip_ul_check,
                        "skip_ul_reason": skip_ul_reason,
                        "nutrient_unit": adequacy.unit,
                        "highest_ul": None if skip_ul_check else adequacy.ul,
                        "optimal_range": f"{adequacy.optimal_min}-{adequacy.optimal_max}" if adequacy.optimal_min else "",
                        "pct_rda": None if skip_ul_check else adequacy.pct_rda,
                        "adequacy_band": "unknown" if skip_ul_check else adequacy.adequacy_band,
                        "warnings": [] if skip_ul_check else adequacy.warnings,
                        "data_by_group": []  # Deprecated in new format
                    })

                return {
                    "ingredients_with_rda": rda_data,
                    "analyzed_ingredients": rda_data,  # AC3: Canonical field name for scoring
                    "count": len(rda_data),
                    # Enhanced evidence fields
                    "adequacy_results": adequacy_results,
                    "conversion_evidence": conversion_evidence,
                    "safety_flags": safety_flags,
                    "has_over_ul": len(safety_flags) > 0
                }

            except Exception as e:
                self._rda_ul_warning_count += 1
                if self._rda_ul_warning_count <= 3:
                    self.logger.warning(f"RDA/UL calculation failed, using fallback: {e}")
                elif self._rda_ul_warning_count == 4:
                    self.logger.warning(
                        "RDA/UL fallback warnings are being suppressed after 3 occurrences; "
                        "enable DEBUG logs for full detail."
                    )
                else:
                    self.logger.debug(f"RDA/UL calculation failed, using fallback: {e}")

        # Fallback: original logic
        rda_db = self.databases.get('rda_optimal_uls', {})
        nutrient_recs = rda_db.get('nutrient_recommendations', [])

        for ingredient in active_ingredients:
            ing_name = ingredient.get('name', '')
            std_name = ingredient.get('standardName', '') or ing_name
            quantity = ingredient.get('quantity', 0)
            unit = ingredient.get('unit', '')

            for nutrient in nutrient_recs:
                nutrient_name = nutrient.get('standard_name', '')
                name_match = (
                    self._normalize_text(std_name) == self._normalize_text(nutrient_name) or
                    self._normalize_text(ing_name) == self._normalize_text(nutrient_name)
                )
                if name_match:
                    try:
                        quantity_float = float(quantity)
                    except (TypeError, ValueError):
                        quantity_float = None

                    if quantity_float is None:
                        per_day_min = quantity
                        per_day_max = quantity
                    else:
                        per_day_min = quantity_float * servings_min
                        per_day_max = quantity_float * servings_max

                    rda_data.append({
                        "ingredient": ing_name,
                        "standard_name": nutrient_name,
                        "quantity": quantity,
                        "unit": unit,
                        "per_day_min": per_day_min,
                        "per_day_max": per_day_max,
                        "servings_per_day_min": servings_min,
                        "servings_per_day_max": servings_max,
                        "nutrient_unit": nutrient.get('unit', ''),
                        "highest_ul": nutrient.get('highest_ul', 0),
                        "optimal_range": nutrient.get('optimal_range', ''),
                        "warnings": nutrient.get('warnings', []),
                        "data_by_group": nutrient.get('data', [])
                    })
                    break

        return {
            "ingredients_with_rda": rda_data,
            "analyzed_ingredients": rda_data,  # AC3: Canonical field name for scoring
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

        self._product_text_cache_enabled = True
        self._product_text_cache.clear()
        self._product_text_lower_cache.clear()

        try:
            # Start with all cleaned data
            enriched = dict(product)

            # Strip PII: contacts contain phone, address, email
            # Manufacturer name is already extracted to manufacturer_data
            if 'contacts' in enriched:
                del enriched['contacts']

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

            # P0.4: Serving basis and form factor for deterministic prescore
            serving_data = self._collect_serving_basis_data(product)
            enriched["serving_basis"] = serving_data["serving_basis"]
            enriched["form_factor"] = serving_data["form_factor"]

            # Percentile category (config-driven, deterministic inference for cohort ranking)
            enriched.update(self._infer_percentile_category(product, enriched))

            # Section E: User Profile Data (for device-side scoring)
            collect_rda_ul_data = self.config.get("processing_config", {}).get("collect_rda_ul_data", True)
            if collect_rda_ul_data:
                servings_min = serving_data["serving_basis"].get("min_servings_per_day")
                servings_max = serving_data["serving_basis"].get("max_servings_per_day")
                enriched["rda_ul_data"] = self._collect_rda_ul_data(
                    product,
                    min_servings_per_day=servings_min,
                    max_servings_per_day=servings_max
                )
                if isinstance(enriched["rda_ul_data"], dict):
                    enriched["rda_ul_data"]["collection_enabled"] = True
            else:
                enriched["rda_ul_data"] = self._empty_rda_ul_payload("disabled_by_config")

            # Probiotic-specific data
            enriched["probiotic_data"] = self._collect_probiotic_data(product)

            # Dietary sensitivity data (sugar/sodium for diabetes/hypertension users)
            enriched["dietary_sensitivity_data"] = self._collect_dietary_sensitivity_data(product)

            # Interaction profile (alerts-only, score-neutral)
            interaction_profile = self._collect_interaction_profile(
                enriched,
                user_profile=product.get("user_profile")
            )
            enriched["interaction_profile"] = interaction_profile
            enriched["user_condition_alerts"] = interaction_profile.get("user_condition_alerts", {
                "enabled": False,
                "conditions_checked": [],
                "drug_classes_checked": [],
                "alerts": [],
                "highest_severity": None
            })

            # Product-level signals (coverage, certificates, label disclosure)
            enriched["product_signals"] = self._collect_product_signals(
                product,
                enriched.get("ingredient_quality_data", {}),
                enriched.get("certification_data", {}),
                enriched.get("formulation_data", {}),
                enriched.get("probiotic_data", {})
            )

            # Project nested enrichment outputs into stable top-level scoring fields.
            self._project_scoring_fields(enriched)

            # P0.2: Dosage normalization with unit conversion evidence
            if self.dosage_normalizer:
                try:
                    dosage_result = self.dosage_normalizer.normalize_product_dosages(product)
                    enriched["dosage_normalization"] = dosage_result.to_dict()
                except Exception as e:
                    self.logger.warning(f"Dosage normalization failed: {e}")
                    enriched["dosage_normalization"] = {"success": False, "error": str(e)}

            # Enrichment metadata (version lock for scoring compatibility)
            enriched["enrichment_metadata"] = {
                "enrichment_version": self.VERSION,
                "scoring_compatibility": self.COMPATIBLE_SCORING_VERSIONS,
                "generated_by": "SupplementEnricherV3",
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "data_completeness": self._calculate_completeness(enriched),
                "ready_for_scoring": True,
                "unmapped_active_count": enriched.get("ingredient_quality_data", {}).get("unmapped_count", 0)
            }

            # Build match ledger and unmatched lists (Pipeline Hardening Phase 3)
            ledger_data = self._build_match_ledger(product, enriched)
            enriched["match_ledger"] = ledger_data["match_ledger"]
            enriched["unmatched_ingredients"] = ledger_data.get("unmatched_ingredients", [])
            enriched["unmatched_additives"] = ledger_data.get("unmatched_additives", [])
            enriched["unmatched_allergens"] = ledger_data.get("unmatched_allergens", [])
            enriched["unmatched_delivery_systems"] = ledger_data.get("unmatched_delivery_systems", [])
            enriched["rejected_manufacturer_matches"] = ledger_data.get("rejected_manufacturer_matches", [])
            enriched["rejected_claim_matches"] = ledger_data.get("rejected_claim_matches", [])

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
        finally:
            # Prevent cache growth across products and avoid stale reads outside this call.
            self._product_text_cache_enabled = False
            self._product_text_cache.clear()
            self._product_text_lower_cache.clear()

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

    def _track_unmapped_form(self, raw_form_text: str, base_name: str, original_label: str):
        """
        Track unmapped forms for database expansion.

        Args:
            raw_form_text: The raw form string that failed to match
            base_name: The base ingredient name (e.g., "Vitamin A")
            original_label: The full original label text
        """
        # Normalize key for deduplication
        key = raw_form_text.lower().strip()
        if not key:
            return

        if key not in self.unmapped_forms_tracker:
            self.unmapped_forms_tracker[key] = {
                'raw_text': raw_form_text,
                'count': 0,
                'base_names': set(),
                'example_labels': []
            }

        entry = self.unmapped_forms_tracker[key]
        entry['count'] += 1
        entry['base_names'].add(base_name)
        if len(entry['example_labels']) < 3 and original_label not in entry['example_labels']:
            entry['example_labels'].append(original_label)

    def _build_quality_parent_context_index(self, quality_map: Dict) -> Dict[str, str]:
        """
        Build deterministic lookup for parent inference from normalized context terms.
        Uses first-seen parent to match existing loop-order tie behavior.
        """
        index: Dict[str, str] = {}
        for parent_key, parent_data in quality_map.items():
            if parent_key.startswith("_") or not isinstance(parent_data, dict):
                continue

            candidates = [parent_data.get("standard_name", ""), parent_key]
            aliases = parent_data.get("aliases", []) or []
            if isinstance(aliases, list):
                candidates.extend(aliases)

            for raw in candidates:
                normed = self._normalize_text(raw)
                if normed and normed not in index:
                    index[normed] = parent_key
        return index

    def _infer_preferred_parent_from_context_cached(
        self, context_name: Optional[str], quality_map: Dict
    ) -> Optional[str]:
        """Infer preferred parent via cached normalized context index."""
        context_norm = self._normalize_text(context_name or "")
        if not context_norm:
            return None

        # Cache only for the primary IQM map used in production.
        # Custom/testing maps may be mutated between calls, so keep lookup fresh.
        primary_quality_map = self.databases.get("ingredient_quality_map", {})
        if quality_map is not primary_quality_map:
            return self._build_quality_parent_context_index(quality_map).get(context_norm)

        cache_key = id(quality_map)
        index = self._quality_parent_context_index_cache.get(cache_key)
        if index is None:
            index = self._build_quality_parent_context_index(quality_map)
            # Prevent unbounded growth from ad-hoc test maps.
            if len(self._quality_parent_context_index_cache) > 16:
                self._quality_parent_context_index_cache.clear()
            self._quality_parent_context_index_cache[cache_key] = index
        return index.get(context_norm)

    def get_unmapped_forms_report(self) -> Dict:
        """
        Generate report of all unmapped forms for database expansion.

        Returns:
            Dict with unmapped forms sorted by frequency and base name associations.
        """
        report = {
            'total_unique_unmapped_forms': len(self.unmapped_forms_tracker),
            'total_unmapped_occurrences': sum(
                e['count'] for e in self.unmapped_forms_tracker.values()
            ),
            'forms_by_frequency': [],
            'forms_by_base_name': {}
        }

        # Sort by frequency (most common first)
        sorted_forms = sorted(
            self.unmapped_forms_tracker.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )

        for key, entry in sorted_forms:
            base_names_list = list(entry['base_names'])
            report['forms_by_frequency'].append({
                'raw_form': entry['raw_text'],
                'count': entry['count'],
                'base_names': base_names_list,
                'example_labels': entry['example_labels']
            })

            # Group by base name for easier database expansion
            for base_name in base_names_list:
                if base_name not in report['forms_by_base_name']:
                    report['forms_by_base_name'][base_name] = []
                report['forms_by_base_name'][base_name].append(entry['raw_text'])

        return report

    def _build_match_ledger(self, product: Dict, enriched: Dict) -> Dict:
        """
        Build match ledger from enriched data.

        Extracts match information from existing enrichment structures
        and builds a centralized audit ledger.

        Returns:
            Dict containing match_ledger and unmatched_* lists
        """
        ledger = MatchLedgerBuilder()

        # =====================================================================
        # INGREDIENTS DOMAIN
        # =====================================================================
        ingredient_data = enriched.get("ingredient_quality_data", {})

        # Process scorable ingredients (matched)
        for ing in ingredient_data.get("ingredients_scorable", []):
            raw_text = ing.get("original_name") or ing.get("name", "")
            std_name = ing.get("standard_name", "")
            canonical_id = ing.get("canonical_id")
            match_tier = ing.get("match_tier")

            # Determine source path from provenance if available
            source_path = ing.get("raw_source_path", "activeIngredients")
            normalized_key = ing.get("normalized_key") or norm_module.make_normalized_key(raw_text)

            if canonical_id:
                # Map match_tier to method
                method = METHOD_EXACT
                if match_tier == "normalized":
                    method = METHOD_NORMALIZED
                elif match_tier == "pattern":
                    method = METHOD_PATTERN
                elif match_tier == "contains":
                    method = METHOD_CONTAINS

                ledger.record_match(
                    domain=DOMAIN_INGREDIENTS,
                    raw_source_text=raw_text,
                    raw_source_path=source_path,
                    canonical_id=canonical_id,
                    match_method=method,
                    matched_to_name=std_name,
                    confidence=1.0 if match_tier == "exact" else 0.9,
                    normalized_key=normalized_key,
                )
            else:
                recognition_type = ing.get("recognition_type")
                if ing.get("recognized_non_scorable") and recognition_type == "botanical_unscored":
                    ledger.record_recognized_botanical_unscored(
                        domain=DOMAIN_INGREDIENTS,
                        raw_source_text=raw_text,
                        raw_source_path=source_path,
                        botanical_db_match=ing.get("matched_entry_name") or std_name or raw_text,
                        reason=ing.get("recognition_reason") or "botanical_unscored",
                        normalized_key=normalized_key,
                    )
                elif ing.get("recognized_non_scorable"):
                    ledger.record_recognized_non_scorable(
                        domain=DOMAIN_INGREDIENTS,
                        raw_source_text=raw_text,
                        raw_source_path=source_path,
                        recognition_source=ing.get("recognition_source") or "rule_based",
                        recognition_reason=ing.get("recognition_reason") or "recognized_non_scorable",
                        normalized_key=normalized_key,
                    )
                else:
                    # Unmapped scorable ingredient
                    ledger.record_unmatched(
                        domain=DOMAIN_INGREDIENTS,
                        raw_source_text=raw_text,
                        raw_source_path=source_path,
                        reason="no_match_found",
                        normalized_key=normalized_key,
                    )

        # Process skipped ingredients
        for ing in ingredient_data.get("ingredients_skipped", []):
            raw_text = ing.get("name", "")
            source_path = "activeIngredients" if ing.get("source_section") == "active" else "inactiveIngredients"
            skip_reason = ing.get("skip_reason", "non_scorable")
            normalized_key = ing.get("normalized_key") or norm_module.make_normalized_key(raw_text)
            recognition_type = ing.get("recognition_type")
            recognition_source = ing.get("recognition_source")
            recognition_reason = ing.get("recognition_reason")
            recognized_entry_name = ing.get("recognized_entry_name") or ing.get("name", "")

            if skip_reason == SKIP_REASON_RECOGNIZED_NON_SCORABLE:
                if recognition_type == "botanical_unscored":
                    ledger.record_recognized_botanical_unscored(
                        domain=DOMAIN_INGREDIENTS,
                        raw_source_text=raw_text,
                        raw_source_path=source_path,
                        botanical_db_match=recognized_entry_name,
                        reason=recognition_reason or "botanical_unscored",
                        normalized_key=normalized_key,
                    )
                else:
                    ledger.record_recognized_non_scorable(
                        domain=DOMAIN_INGREDIENTS,
                        raw_source_text=raw_text,
                        raw_source_path=source_path,
                        recognition_source=recognition_source or "rule_based",
                        recognition_reason=recognition_reason or "recognized_non_scorable",
                        normalized_key=normalized_key,
                    )
            else:
                ledger.record_skipped(
                    domain=DOMAIN_INGREDIENTS,
                    raw_source_text=raw_text,
                    raw_source_path=source_path,
                    skip_reason=skip_reason,
                    normalized_key=normalized_key,
                )

        # =====================================================================
        # ADDITIVES DOMAIN (from contaminant_data)
        # =====================================================================
        contaminant_data = enriched.get("contaminant_data", {})
        additive_hits = (
            contaminant_data.get("harmful_additives", {}).get("additives")
            if isinstance(contaminant_data.get("harmful_additives"), dict)
            else None
        )
        if additive_hits is None:
            # Backward-compatible fallback for older payload shape.
            additive_hits = contaminant_data.get("additives", [])

        for additive in additive_hits:
            raw_text = (
                additive.get("ingredient")
                or additive.get("raw_source_text")
                or additive.get("additive_name")
                or ""
            )
            matched_name = (
                additive.get("additive_name")
                or additive.get("canonical_name")
                or additive.get("matched_name")
                or ""
            )
            canonical_id = additive.get("additive_id") or additive.get("db_id")
            normalized_key = additive.get("normalized_key") or norm_module.make_normalized_key(raw_text)

            method_raw = self._normalize_text(additive.get("match_method", ""))
            if "exact" in method_raw:
                method = METHOD_EXACT
                confidence = 1.0
            elif "normalized" in method_raw:
                method = METHOD_NORMALIZED
                confidence = 0.9
            else:
                method = METHOD_PATTERN if method_raw else METHOD_NORMALIZED
                confidence = 0.8

            if canonical_id:
                ledger.record_match(
                    domain=DOMAIN_ADDITIVES,
                    raw_source_text=raw_text,
                    raw_source_path="inactiveIngredients",
                    canonical_id=canonical_id,
                    match_method=method,
                    matched_to_name=matched_name,
                    confidence=confidence,
                    normalized_key=normalized_key,
                )
            elif matched_name:
                # Matched but no canonical_id
                ledger.record_match(
                    domain=DOMAIN_ADDITIVES,
                    raw_source_text=raw_text,
                    raw_source_path="inactiveIngredients",
                    canonical_id=matched_name.lower().replace(" ", "_"),  # Generate ID
                    match_method=method,
                    matched_to_name=matched_name,
                    confidence=confidence,
                    normalized_key=normalized_key,
                )

        # =====================================================================
        # ALLERGENS DOMAIN (from compliance_data)
        # =====================================================================
        compliance_data = enriched.get("compliance_data", {})
        for allergen in compliance_data.get("allergens_detected", []):
            raw_text = allergen.get("source_ingredient") or allergen.get("allergen_name", "")
            allergen_type = allergen.get("allergen_type", "")
            normalized_key = norm_module.make_normalized_key(raw_text)

            ledger.record_match(
                domain=DOMAIN_ALLERGENS,
                raw_source_text=raw_text,
                raw_source_path=allergen.get("presence_type", "ingredient_derived"),
                canonical_id=allergen_type.lower().replace(" ", "_"),
                match_method=METHOD_EXACT,
                matched_to_name=allergen_type,
                confidence=1.0,
                normalized_key=normalized_key,
            )

        # =====================================================================
        # MANUFACTURER DOMAIN
        # =====================================================================
        manufacturer_data = enriched.get("manufacturer_data", {})
        top_match = manufacturer_data.get("top_manufacturer", {})

        if top_match.get("found"):
            # Use AC2 provenance fields if available
            raw_text = top_match.get("product_manufacturer_raw") or product.get("brandName") or product.get("manufacturer", "")
            source_path = top_match.get("source_path", "brandName")
            matched_name = top_match.get("name", "")
            canonical_id = top_match.get("manufacturer_id", "")
            confidence = top_match.get("match_confidence", 1.0)
            match_type = top_match.get("match_type", "exact")
            # CONSISTENCY FIX: Always use make_normalized_key() for normalized_key field
            # This ensures manufacturer keys use underscores like ingredient keys (e.g., "protocol_for_life_balance")
            # product_manufacturer_normalized (with spaces) is kept for fuzzy matching comparison only
            normalized_key = norm_module.make_normalized_key(raw_text)

            method = METHOD_EXACT if match_type == "exact" else METHOD_FUZZY

            if match_type == "exact":
                # Exact match - record as matched, will get scoring bonus
                ledger.record_match(
                    domain=DOMAIN_MANUFACTURER,
                    raw_source_text=raw_text,
                    raw_source_path=source_path,
                    canonical_id=canonical_id,
                    match_method=method,
                    matched_to_name=matched_name,
                    confidence=confidence,
                    normalized_key=normalized_key,
                )
            else:
                # POLICY: ALL fuzzy matches are rejected for scoring (exact only gets bonus)
                # Record as rejected regardless of confidence - this populates rejected_manufacturer_matches
                # for auditability of why the product didn't get manufacturer bonus
                rejection_reason = "fuzzy_match_rejected_for_scoring"
                if confidence < self.company_fuzzy_threshold:
                    rejection_reason = "fuzzy_below_threshold"
                ledger.record_rejected(
                    domain=DOMAIN_MANUFACTURER,
                    raw_source_text=raw_text,
                    raw_source_path=source_path,
                    best_match_id=canonical_id,
                    best_match_name=matched_name,
                    match_method=method,
                    confidence=confidence,
                    rejection_reason=rejection_reason,
                    normalized_key=normalized_key,
                )
                # Mirror the ledger rejection in the top_manufacturer dict so that
                # found=True/False always means "a trusted exact match exists" —
                # consistent with is_trusted_manufacturer semantics.  The rejected
                # candidate details (manufacturer_id, name, match_confidence) are
                # preserved for auditability; only the found flag is corrected.
                top_match["found"] = False
        else:
            # No match found - use AC2 provenance from top_match if available
            raw_text = top_match.get("product_manufacturer_raw") or product.get("brandName") or product.get("manufacturer", "")
            source_path = top_match.get("source_path", "brandName")
            # CONSISTENCY FIX: Always use make_normalized_key() for normalized_key field
            normalized_key = norm_module.make_normalized_key(raw_text)

            if raw_text:  # Only record if there was input text
                ledger.record_unmatched(
                    domain=DOMAIN_MANUFACTURER,
                    raw_source_text=raw_text,
                    raw_source_path=source_path,
                    reason="no_match_found",
                    normalized_key=normalized_key,
                )

        # =====================================================================
        # DELIVERY SYSTEMS DOMAIN
        # =====================================================================
        delivery_data = enriched.get("delivery_data", {})
        for system in delivery_data.get("matched_systems", []):
            raw_text = system.get("name", "")
            canonical_id = system.get("canonical_id") or raw_text.lower().replace(" ", "_")
            normalized_key = norm_module.make_normalized_key(raw_text)

            ledger.record_match(
                domain=DOMAIN_DELIVERY,
                raw_source_text=raw_text,
                raw_source_path="physicalState",
                canonical_id=canonical_id,
                match_method=METHOD_PATTERN,
                matched_to_name=raw_text,
                confidence=1.0,
                normalized_key=normalized_key,
            )

        # =====================================================================
        # BUILD FINAL OUTPUT
        # =====================================================================
        match_ledger = ledger.build()
        unmatched_lists = ledger.build_unmatched_lists()

        return {
            "match_ledger": match_ledger,
            **unmatched_lists,
        }

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
            output_cfg = self.config.get("output_structure", {})
            enriched_folder = str(output_cfg.get("enriched_folder", "enriched")).strip() or "enriched"
            batch_prefix = str(output_cfg.get("batch_prefix", "enriched_")).strip() or "enriched_"
            file_extension = str(output_cfg.get("file_extension", ".json")).strip() or ".json"
            if not file_extension.startswith("."):
                file_extension = f".{file_extension}"

            enriched_dir = os.path.join(output_dir, enriched_folder)
            os.makedirs(enriched_dir, exist_ok=True)

            output_file = os.path.join(enriched_dir, f"{batch_prefix}{base_name}{file_extension}")

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
            input_pattern = str(
                self.config.get("paths", {}).get("input_file_pattern", "*.json")
            ).strip() or "*.json"
            input_files = [
                os.path.join(input_path, f)
                for f in os.listdir(input_path)
                if fnmatch.fnmatch(f, input_pattern)
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
            "failed": 0,
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
            "match_counters": dict(self.match_counters),
            "unmapped_ingredients": dict(self.unmapped_tracker)
        }

        output_cfg = self.config.get("output_structure", {})
        reports_folder = str(output_cfg.get("reports_folder", "reports")).strip() or "reports"
        report_prefix = str(output_cfg.get("report_prefix", "enrichment_summary")).strip() or "enrichment_summary"
        generate_reports = bool(self.config.get("options", {}).get("generate_reports", True))
        summary_file = None

        if generate_reports:
            reports_dir = os.path.join(output_dir, reports_folder)
            os.makedirs(reports_dir, exist_ok=True)

            summary_file = os.path.join(
                reports_dir,
                f"{report_prefix}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json",
            )

            # Atomic write: prevents partial files on crash
            self._atomic_write_json(summary_file, summary)

            # Save parent fallback report (all details, not just first 10)
            if self._parent_fallback_details:
                # Deduplicate by ingredient_normalized + canonical_id for cleaner report
                seen_fallbacks = {}
                for fb in self._parent_fallback_details:
                    key = (fb.get("ingredient_normalized", ""), fb.get("canonical_id", ""))
                    if key not in seen_fallbacks:
                        seen_fallbacks[key] = {**fb, "occurrence_count": 1}
                    else:
                        seen_fallbacks[key]["occurrence_count"] += 1
                fallback_report = {
                    "total_fallback_count": len(self._parent_fallback_details),
                    "unique_fallback_count": len(seen_fallbacks),
                    "note": "These ingredients matched an IQM parent but no specific form alias. "
                            "They fell back to the (unspecified) form with conservative scoring. "
                            "Adding form-level aliases in IQM would improve scoring accuracy.",
                    "fallbacks": sorted(
                        seen_fallbacks.values(),
                        key=lambda x: (-x["occurrence_count"], x["canonical_id"])
                    ),
                }
                fallback_file = os.path.join(reports_dir, "parent_fallback_report.json")
                self._atomic_write_json(fallback_file, fallback_report)
                self.logger.info(
                    f"Parent fallback report saved: {fallback_file} "
                    f"({len(seen_fallbacks)} unique, {len(self._parent_fallback_details)} total)"
                )

            # Save FORM_UNMAPPED_FALLBACK audit report
            if self._form_fallback_details:
                # Deduplicate by (unmapped_form_text, canonical_id) and count occurrences
                seen_form_fb = {}
                for fb in self._form_fallback_details:
                    key = ((fb.get("unmapped_form_text") or "").lower().strip(), fb.get("canonical_id", ""))
                    if key not in seen_form_fb:
                        seen_form_fb[key] = {**fb, "occurrence_count": 1}
                    else:
                        seen_form_fb[key]["occurrence_count"] += 1

                # Separate into "differ" (needs alias) vs "same" (form matches fallback)
                differs = [v for v in seen_form_fb.values() if v["forms_differ"]]
                same = [v for v in seen_form_fb.values() if not v["forms_differ"]]

                form_fallback_report = {
                    "generated_at": datetime.utcnow().isoformat() + "Z",
                    "total_form_fallback_count": len(self._form_fallback_details),
                    "unique_form_fallback_count": len(seen_form_fb),
                    "forms_differ_count": len(differs),
                    "forms_same_count": len(same),
                    "note": (
                        "AUDIT THIS FILE: Each entry shows an ingredient where form evidence "
                        "existed but no IQM alias matched. The ingredient scored using the "
                        "parent's (unspecified) fallback. 'forms_differ=true' means the "
                        "unmapped form text is DIFFERENT from the fallback form — these are "
                        "the ones most likely to be scored wrong and need IQM alias additions."
                    ),
                    "action_needed_differs": sorted(
                        differs,
                        key=lambda x: (-x["occurrence_count"], x["canonical_id"]),
                    ),
                    "likely_ok_same": sorted(
                        same,
                        key=lambda x: (-x["occurrence_count"], x["canonical_id"]),
                    ),
                }
                form_fb_file = os.path.join(reports_dir, "form_fallback_audit_report.json")
                self._atomic_write_json(form_fb_file, form_fallback_report)
                self.logger.info(
                    f"Form fallback audit report saved: {form_fb_file} "
                    f"({len(differs)} differ, {len(same)} same, "
                    f"{len(self._form_fallback_details)} total occurrences)"
                )
        else:
            self.logger.info("Report generation disabled by config option: options.generate_reports=false")

        self.logger.info("=" * 50)
        self.logger.info("ENRICHMENT COMPLETE")
        self.logger.info(f"Total products: {total_stats['total_products']}")
        self.logger.info(
            f"Pattern match wins: {self.match_counters['pattern_match_wins_count']}; "
            f"Contains match wins: {self.match_counters['contains_match_wins_count']}; "
            f"Parent fallback count: {self.match_counters['parent_fallback_count']}"
        )
        self.logger.info(f"Duration: {duration:.2f}s")
        if summary_file:
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
