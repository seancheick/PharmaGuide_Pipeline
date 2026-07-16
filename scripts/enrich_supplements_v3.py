#!/usr/bin/env python3
from __future__ import annotations
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
import math
import logging
import argparse
import traceback
from datetime import datetime, timezone
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
    BRANDED_INGREDIENT_TOKENS,
    DISPLAY_LEDGER_SOURCE_PRODUCT_NAME,
)
from stage_manifest import select_stage_input_files
from run_artifacts import ensure_run_id, report_run_directory
from supplement_type_utils import mark_compound_duplicate_rows
from supplement_taxonomy import classify_supplement, percentile_label_for
from form_factor_normalizer import canonicalize_form_factor
from scoring_input_contract import (
    build_scoring_classification,
    derive_product_scoring_evidence,
    get_scoring_ingredients,
)
from identity_integrity import (
    IdentityDecision,
    build_canonical_identity_registry,
    is_identity_scoreable,
    resolve_identity,
    validated_canonical_parent_relationships,
)

# Form-keyword vocabulary — single source of truth for omega-3 / probiotic /
# postbiotic / prebiotic / vitamin-mineral form patterns. Replaces 3-5
# hardcoded keyword lists previously scattered here, in score_supplements,
# and in enhanced_normalizer. Imported at module level so nested helper
# functions inside _collect_probiotic_data can close over it cleanly.
import form_vocab as _form_vocab  # noqa: E402

# Import scoring hardening modules
from unit_converter import UnitConverter, ConversionResult
from dosage_normalizer import DosageNormalizer, DosageNormalizationResult
from proprietary_blend_detector import ProprietaryBlendDetector, BlendAnalysisResult
from rda_ul_calculator import RDAULCalculator, NutrientAdequacyResult
from reference_data_contract import reference_stamp
from collagen_taxonomy import classify_collagen_subtype_strict, UNSPECIFIED as _COLLAGEN_UNSPECIFIED
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
    # Sprint 1.1 — cleaner-side match methods (UNII + alternateNames).
    # When the cleaner sets `cleaner_match_method` on a cleaned-ingredient
    # dict, the enricher's match_ledger uses one of these values instead
    # of the default tier-mapped METHOD_EXACT etc.
    METHOD_UNII_EXACT,
    METHOD_UNII_FORM_EXACT,
    METHOD_ALTERNATE_NAME,
)
from identity.safety import (
    has_explicit_form_evidence,
    safety_flag_from_banned_match,
    safety_jurisdiction_projection,
)

_RDA_REFERENCE_PROFILE = {
    "id": "adult_neutral_compatibility",
    "age_range": "19-30",
    "adequacy_basis": "higher_sourced_adult_male_female_rda_ai",
    "ul_basis": "lower_sourced_adult_male_female_ul",
}

# FDA/NIH labeling basis: 1,000 mcg synthetic folic acid is the adult UL;
# current Supplement Facts labels express its equivalent as 1,700 mcg DFE.
# These values only SCREEN an unknown-form row for review. They never establish
# that the product is over UL.
_FOLIC_ACID_ADULT_UL_MCG = 1000.0
_FOLIC_ACID_LABEL_DFE_FACTOR = 1.7
_FOLATE_DAILY_VALUE_DFE_MCG = 400.0


def _unknown_folate_ul_screening(
    quantity: float,
    unit: str,
    daily_value: Any = None,
) -> Optional[Dict[str, float | str]]:
    """Return worst-case folic-acid screening exposure for an ambiguous row."""
    raw_unit = str(unit or "").lower().strip()
    label_declares_dfe = "dfe" in raw_unit
    mass_token = re.sub(r"\bdfe\b", "", raw_unit).strip()
    canonical_unit = norm_module.canonicalize_mass_unit(mass_token)
    factors_to_mcg = {"g": 1_000_000.0, "mg": 1_000.0, "mcg": 1.0}
    factor = factors_to_mcg.get(canonical_unit)
    if factor is None:
        return None

    declared_mcg = float(quantity) * factor
    try:
        declared_daily_value = float(daily_value)
    except (TypeError, ValueError):
        declared_daily_value = None
    expected_dfe_daily_value = (
        declared_mcg / _FOLATE_DAILY_VALUE_DFE_MCG * 100.0
    )
    dfe_inferred_from_daily_value = bool(
        not label_declares_dfe
        and declared_daily_value is not None
        and abs(declared_daily_value - expected_dfe_daily_value)
        <= max(1.0, expected_dfe_daily_value * 0.02)
    )
    uses_dfe_basis = label_declares_dfe or dfe_inferred_from_daily_value
    screening_amount = (
        declared_mcg / _FOLIC_ACID_LABEL_DFE_FACTOR
        if uses_dfe_basis
        else declared_mcg
    )
    return {
        "screening_amount": screening_amount,
        "screening_unit": "mcg folic acid",
        "screening_ul": _FOLIC_ACID_ADULT_UL_MCG,
        "potential_pct_ul": (
            screening_amount / _FOLIC_ACID_ADULT_UL_MCG * 100.0
        ),
        "screening_basis": (
            "label_declared_dfe"
            if label_declares_dfe
            else (
                "dfe_inferred_from_daily_value"
                if dfe_inferred_from_daily_value
                else "bare_mass_worst_case"
            )
        ),
    }

# Sprint 1.1 — map cleaner-side match-method strings to match_ledger constants.
_CLEANER_MATCH_METHOD_MAP = {
    "unii_exact_match": METHOD_UNII_EXACT,
    "unii_form_exact_match": METHOD_UNII_FORM_EXACT,
    "alternate_name_match": METHOD_ALTERNATE_NAME,
}

_SOURCE_DESCRIPTOR_FORM_CATEGORIES = frozenset({
    "animal part or source",
    "plant part",
    "source material",
})
_SOURCE_DESCRIPTOR_FORM_PREFIXES = frozenset({
    "from",
    "culture of",
    "and culture of",
    "naturally occurring from",
    "derived from",
})


# Sprint E1.3.2 — probiotic CFU adequacy helpers.
# Pure module-level functions (testable in isolation, no SupplementEnricherV3
# state). Used by _collect_probiotic_data to attach per-strain adequacy
# tiers from Dr Pham's cfu_thresholds blocks onto found_clinical_strains.

_EVIDENCE_STRENGTH_TO_SUPPORT_LEVEL = {
    "strong": "high",
    "medium": "moderate",
    "weak": "weak",
}

# Reviewed IQM parent crossings where the form text is intentionally more
# specific than the cleaner's parent-level canonical. Any IQM-to-IQM crossing
# not listed here is treated as a resolver bug and falls back to the cleaner
# parent instead of silently changing the scored ingredient.
IQM_CANONICAL_CROSS_PARENT_ALLOWLIST: Dict[Tuple[str, str], Tuple[str, ...]] = {
    ("vitamin_k", "vitamin_k1"): (
        "phytonadione",
        "phylloquinone",
        "vitamin k1",
    ),
    ("turmeric", "curcumin"): (
        "curcuminoid",
    ),
}

# Botanical cleaner IDs whose active marker compounds must remain secondary
# metadata unless the cleaner has resolved the row directly to the marker's IQM
# canonical. This protects non-IQM source canonicals, which are outside the IQM
# parent hard-stop above.
BOTANICAL_SOURCE_MARKER_CANONICAL_BLOCKLIST: Dict[str, Tuple[str, ...]] = {
    "acerola_cherry": ("vitamin_c",),
    "tomato": ("lycopene",),
    "broccoli": ("sulforaphane",),
    "cayenne_pepper": ("capsaicin",),
    "cistanche": ("echinacea",),
    "green_tea": ("caffeine", "egcg", "epigallocatechin", "gallocatechin"),
    "green_tea_leaf": ("caffeine", "egcg", "epigallocatechin", "gallocatechin"),
    "horny_goat_weed": ("flavones",),
    "coffee_fruit": ("caffeine",),
    "japanese_knotweed": ("resveratrol",),
    "kanna_sceletium": ("mesembrine",),
    "lemon": ("vitamin_b9_folate",),
    "moringa": ("vitamin_a",),
    "sophora_japonica": ("quercetin",),
    "yerba_mate": ("caffeine",),
    "yerba_mate_leaf": ("caffeine",),
}

BOTANICAL_CANONICAL_SOURCE_DBS = {
    "botanical_ingredients",
    "standardized_botanicals",
}


# ---------------------------------------------------------------------------
# Sprint 1 UNII-first matching: canonical UNII normalizer (must stay in sync
# with `enhanced_normalizer._normalize_unii` — duplicated rather than imported
# to keep the cleaner and enricher independently testable). Contract:
#
#   FDA UNIIs are exactly 10 alphanumeric uppercase characters. Strip
#   whitespace, uppercase, and reject DSLD placeholder values ("0", "1", "").
#
# Returns: Optional[str] — 10-char canonical UNII, or None for placeholder/garbage.
# ---------------------------------------------------------------------------
_UNII_PLACEHOLDERS = frozenset({"", "0", "1"})


def _rda_mass_unit_key(value) -> Optional[str]:
    unit = "" if value is None else str(value)
    compact = (
        unit.lower()
        .replace("µg", "mcg")
        .replace("μg", "mcg")
        .replace(" ", "")
        .strip()
    )
    if compact in {"g", "gram", "grams", "gram(s)"}:
        return "g"
    if compact in {"mg", "milligram", "milligrams", "milligram(s)"}:
        return "mg"
    if compact in {"mcg", "ug", "microgram", "micrograms", "microgram(s)"}:
        return "mcg"
    return None


def _has_no_official_ul_reference(nutrient_record: Dict[str, Any]) -> bool:
    if not nutrient_record:
        return False
    highest_ul = nutrient_record.get("highest_ul")
    if highest_ul not in (None, ""):
        return False
    note = str(nutrient_record.get("ul_note") or "").lower()
    if "no official ul" in note or "no ul established" in note:
        return True
    data = nutrient_record.get("data")
    if isinstance(data, list) and data:
        statuses = [
            str(row.get("ul_status") or "").lower()
            for row in data
            if isinstance(row, dict)
        ]
        return bool(statuses) and all(status == "not_determined" for status in statuses)
    return True


def _normalize_unii(value):
    """Canonicalize a UNII string. Returns None for placeholders/garbage."""
    if not isinstance(value, str):
        return None
    canon = value.strip().upper()
    if not canon or canon in _UNII_PLACEHOLDERS:
        return None
    if len(canon) != 10 or not canon.isalnum():
        return None
    return canon


def _compute_strain_cfu_tier(cfu_per_day, tiers_cfu_per_day) -> Optional[str]:
    """Map a per-strain CFU count to its adequacy tier using Dr Pham's
    authored ``tiers_cfu_per_day`` band dict.

    Returns one of ``"low" | "adequate" | "good" | "excellent"`` or
    ``None`` when the dose is zero/missing or the bands dict is empty.
    Tolerates band-key order and missing ``upper_exclusive`` (treats it
    as +infinity) / missing ``lower_inclusive`` (treats it as 0).
    """
    if not isinstance(cfu_per_day, (int, float)) or cfu_per_day <= 0:
        return None
    if not isinstance(tiers_cfu_per_day, dict) or not tiers_cfu_per_day:
        return None

    for tier_name in ("low", "adequate", "good", "excellent"):
        band = tiers_cfu_per_day.get(tier_name)
        if not isinstance(band, dict):
            continue
        lower = band.get("lower_inclusive", 0)
        upper = band.get("upper_exclusive")
        lower_ok = cfu_per_day >= (lower if isinstance(lower, (int, float)) else 0)
        upper_ok = (
            upper is None
            or (isinstance(upper, (int, float)) and cfu_per_day < upper)
        )
        if lower_ok and upper_ok:
            return tier_name
    return None


# Sprint E1.3.2.b — probiotic confidence hybrid (descriptive layer).
# Deterministic mapping from adequacy signals to three controlled-
# vocabulary fields that surface evidence honesty without inventing
# clinician-final prose. Dev rule (external review 2026-04-22):
# ``dose_basis="clinical"`` is RESERVED — current cfu_thresholds blocks
# use industry-standard 1B/10B/50B bands, not per-strain trial arms,
# so today's pipeline never emits "clinical".
_CFU_CONFIDENCE_VALUES = ("high", "moderate", "low")
_DOSE_BASIS_VALUES = ("clinical", "industry_standard", "inferred")
_UI_COPY_HINT_VALUES = (
    "studied_range",
    "limited_evidence",
    "label_disclosed_no_threshold",
    "blend_not_individually_disclosed",
)
_PROBIOTIC_IDENTITY_RE = re.compile(
    r"\b("
    r"probiotic|lactobacillus|bifidobacterium|streptococcus|saccharomyces|"
    r"bacillus|limosilactobacillus|lacticaseibacillus|lactiplantibacillus|"
    r"lactococcus|acidophilus|reuteri|rhamnosus|plantarum|casei|salivarius|"
    r"coagulans|subtilis|bifidus|cfu|live\s+cultures?|viable\s+cells?"
    r")\b",
    re.IGNORECASE,
)


def _compute_probiotic_confidence_hybrid(
    cfu_per_day,
    adequacy_tier,
    clinical_support_level,
    threshold_dose_basis="industry_standard",
) -> Dict[str, str]:
    """Derive (cfu_confidence, dose_basis, ui_copy_hint) deterministically
    from the upstream adequacy signal.

    Precedence (first match wins):
      1. ``cfu_per_day is None`` → multi-strain blend, per-member CFU
         not knowable. ``ui_copy_hint="blend_not_individually_disclosed"``,
         ``cfu_confidence="low"``, ``dose_basis="industry_standard"`` (the
         strain's threshold block itself is industry-standard).
      2. ``adequacy_tier is None`` (but cfu known) — dose disclosed but
         no matching tier band. ``ui_copy_hint="label_disclosed_no_threshold"``,
         ``cfu_confidence="low"``, ``dose_basis="inferred"``.
      3. tier-matched: ``cfu_confidence`` mirrors ``clinical_support_level``
         with "weak" → "low"; ``ui_copy_hint="studied_range"`` on
         high/moderate, ``"limited_evidence"`` on weak. ``dose_basis``
         preserves an explicit validated clinical threshold source and
         otherwise defaults to ``"industry_standard"``.

    The output enums are the only allowed values; anything else is a
    programming error and should fail tests immediately.
    """
    dose_basis = (
        "clinical"
        if str(threshold_dose_basis or "").strip().lower() == "clinical"
        else "industry_standard"
    )

    # Case 1 — multi-strain blend (per-member CFU unknown)
    if cfu_per_day is None:
        return {
            "cfu_confidence": "low",
            "dose_basis": dose_basis,
            "ui_copy_hint": "blend_not_individually_disclosed",
        }

    # Case 2 — dose disclosed but no tier match
    if adequacy_tier is None:
        return {
            "cfu_confidence": "low",
            "dose_basis": "inferred",
            "ui_copy_hint": "label_disclosed_no_threshold",
        }

    # Case 3 — tier-matched
    support = (clinical_support_level or "weak").strip().lower()
    if support == "high":
        cfu_conf = "high"
        hint = "studied_range"
    elif support == "moderate":
        cfu_conf = "moderate"
        hint = "studied_range"
    else:  # weak or unknown
        cfu_conf = "low"
        hint = "limited_evidence"
    return {
        "cfu_confidence": cfu_conf,
        "dose_basis": dose_basis,
        "ui_copy_hint": hint,
    }


def _normalize_parent_blend_mg(mass, unit) -> Optional[float]:
    """Sprint E1.3.3 — convert (mass, unit) pair into milligrams.
    Tolerates the units DSLD uses on parent rows: mg, g, mcg/ug. Returns
    ``None`` when mass is missing or the unit is unrecognized."""
    if not isinstance(mass, (int, float)) or mass <= 0:
        return None
    u = (unit or "").strip().lower()
    if u in ("mg", "milligram", "milligrams", ""):
        return float(mass)
    if u in ("g", "gram", "grams"):
        return float(mass) * 1000.0
    if u in ("mcg", "ug", "µg", "microgram", "micrograms"):
        return float(mass) / 1000.0
    return None


def _derive_clinical_support_level(strain_entry) -> str:
    """Resolve ``clinical_support_level`` with a fallback chain:

      1. explicit ``cfu_thresholds.evidence.clinical_support_level``
      2. mapped from ``cfu_thresholds.evidence.evidence_strength``
         (strong→high, medium→moderate, weak→weak)
      3. conservative default ``"weak"`` (protects against overclaim)

    Returns exactly one of ``"high" | "moderate" | "weak"``.
    """
    if not isinstance(strain_entry, dict):
        return "weak"
    thresholds = strain_entry.get("cfu_thresholds") or {}
    evidence = (thresholds.get("evidence") or {}) if isinstance(thresholds, dict) else {}
    if not isinstance(evidence, dict):
        return "weak"

    explicit = evidence.get("clinical_support_level") or thresholds.get("clinical_support_level")
    if isinstance(explicit, str):
        lower = explicit.strip().lower()
        if lower in ("high", "moderate", "weak"):
            return lower

    strength = evidence.get("evidence_strength")
    if isinstance(strength, str):
        mapped = _EVIDENCE_STRENGTH_TO_SUPPORT_LEVEL.get(strength.strip().lower())
        if mapped:
            return mapped

    return "weak"


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
    EXPORT_REQUIRED_IQD_FIELDS = {
        "raw_source_text",
        "name",
        "standard_name",
        "bio_score",
        "natural",
        "score",
        "notes",
        "category",
        "mapped",
        "safety_hits",
    }

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

    def _validate_export_contract_fields(self, enriched: Dict) -> List[str]:
        """
        Validate the minimum field set required by final DB export.

        Enrichment should not silently drift away from the export contract.
        This validator surfaces issues in metadata and logs, while the export
        builder remains responsible for failing the final build loudly.
        """
        issues = []

        ingredient_quality_data = enriched.get("ingredient_quality_data", {}) or {}
        ingredients = ingredient_quality_data.get("ingredients", []) or []

        for idx, ingredient in enumerate(ingredients):
            if not isinstance(ingredient, dict):
                issues.append(f"ingredient_quality_data.ingredients[{idx}] is not an object")
                continue
            missing = sorted(
                field for field in self.EXPORT_REQUIRED_IQD_FIELDS
                if field not in ingredient
            )
            for field in missing:
                issues.append(
                    f"ingredient_quality_data.ingredients[{idx}].{field} missing"
                )

        return issues

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
            "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
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
        # Compiled-regex caches for high-volume banned/contaminant matching.
        # These preserve the exact same patterns while avoiding per-ingredient
        # recompilation on large labels with many active/nested rows.
        self._regex_pattern_cache: Dict[str, re.Pattern] = {}
        self._token_bounded_pattern_cache: Dict[str, re.Pattern] = {}
        self._hyphen_space_pattern_cache: Dict[str, re.Pattern] = {}
        self._color_context_pattern = re.compile(
            r"(?<![a-z0-9])(dye|color|colour|fd\s*&\s*c|fdc|lake|pigment)(?![a-z0-9])"
        )
        # Per-quality-map cache: normalized context term -> preferred parent key.
        self._quality_parent_context_index_cache: Dict[int, Dict[str, str]] = {}
        # Memoized ingredient-match results (see _match_quality_map). Keyed on the
        # full result-affecting argument tuple; run-lifetime, per enricher instance.
        # ponytail: unbounded dict — add an LRU cap only if one enricher is held
        # across a multi-million-row run and RSS becomes the binding constraint.
        self._match_quality_cache: Dict[str, Any] = {}
        self.databases = {}
        self._load_all_databases()
        self._rda_reference_stamp = reference_stamp(
            self.databases.get("rda_optimal_uls", {})
        )
        self._compile_patterns()

        # ── Performance indexes (built once, used per-ingredient) ──
        # IQM alias indexes for O(1) lookups instead of O(n) parent scans
        self._iqm_exact_index: Dict[str, List] = {}  # exact_norm → [(parent_key, form_key|None, alias_text, priority, match_mode)]
        self._iqm_norm_index: Dict[str, List] = {}   # normalized → [(parent_key, form_key|None, alias_text, priority, match_mode)]
        # Non-scorable DB index for O(1) recognition lookups
        self._nonscorable_index: Dict[str, Dict] = {}  # normalized_variant → result_dict
        # Sprint 1: UNII-anchored non-scorable recognition index. Mirrors
        # _nonscorable_index but keyed by canonical UNII for Tier-0 recognition
        # of inactive/recognized-non-scorable items via DSLD's uniiCode.
        self._nonscorable_unii_index: Dict[str, Dict] = {}
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

        except (RuntimeError, ValueError, KeyError) as e:
            # Critical failures: missing/corrupt reference data or config.
            # RuntimeError = DB file missing, ValueError = empty/invalid data,
            # KeyError = malformed config. All indicate the pipeline cannot
            # produce safe results — abort rather than silently degrade.
            raise
        except ImportError as e:
            # Optional dependency missing (e.g., psutil). Degrade gracefully.
            self.logger.warning(
                f"Optional scoring module dependency missing: {e}. "
                "Evidence collection will use fallback methods."
            )
            self.unit_converter = None
            self.dosage_normalizer = None
            self.blend_detector = None
            self.rda_calculator = None

    def _primary_active_ingredients_for_enrichment(
        self,
        product: Dict,
        ingredient_quality_data: Optional[Dict] = None,
    ) -> List[Dict]:
        """Return active rows eligible for active-only enrichment collectors.

        Cleaner/enrichment already splits primary scorable actives from
        disclosed-blend children. Synergy, clinical evidence, standardized
        botanical, and RDA/UL collectors must use that same contract instead of
        the flattened label list, otherwise undosed blend members behave like
        primary ingredients.
        """
        active_ingredients = [
            ing for ing in product.get('activeIngredients', [])
            if isinstance(ing, dict)
        ]
        iqd = ingredient_quality_data if isinstance(ingredient_quality_data, dict) else product.get("ingredient_quality_data")
        if not isinstance(iqd, dict) or not isinstance(iqd.get("ingredients_scorable"), list):
            return active_ingredients

        contract_product = dict(product)
        contract_product["ingredient_quality_data"] = iqd
        try:
            result = get_scoring_ingredients(
                contract_product,
                strict=True,
                allow_legacy_fallback=False,
            )
        except Exception as exc:  # pragma: no cover - defensive legacy fallback.
            self.logger.debug("strict scoring contract unavailable for enrichment: %s", exc)
            return active_ingredients

        scoring_rows = [
            row for row in result.rows
            if (
                str(row.get("scoring_input_kind") or "") != "product_level_evidence"
                and not self._is_display_only_blend_scoring_row(row)
            )
        ]
        if not scoring_rows:
            return []

        source_paths = {
            str(row.get("raw_source_path") or row.get("source_path") or "").strip()
            for row in scoring_rows
            if str(row.get("raw_source_path") or row.get("source_path") or "").strip()
        }
        terms = set()
        canonical_ids = set()
        for row in scoring_rows:
            for key in (
                "raw_source_text",
                "name",
                "standard_name",
                "standardName",
                "matched_name",
                "display_label",
            ):
                value = str(row.get(key) or "").strip()
                if value:
                    terms.add(norm_module.make_normalized_key(value))
            canonical = str(
                row.get("canonical_id") or row.get("parent_key") or row.get("normalized_key") or ""
            ).strip()
            if canonical:
                canonical_ids.add(canonical.lower())

        selected: List[Dict] = []
        for ing in active_ingredients:
            path = str(ing.get("raw_source_path") or ing.get("source_path") or "").strip()
            if path and path in source_paths:
                selected.append(ing)
                continue
            matched = False
            for key in (
                "raw_source_text",
                "name",
                "standardName",
                "standard_name",
                "matched_name",
                "display_label",
            ):
                value = str(ing.get(key) or "").strip()
                if value and norm_module.make_normalized_key(value) in terms:
                    matched = True
                    break
            canonical = str(
                ing.get("canonical_id") or ing.get("parent_key") or ing.get("normalized_key") or ""
            ).strip().lower()
            if matched or (canonical and canonical in canonical_ids):
                selected.append(ing)

        if selected:
            return selected

        return [self._active_ingredient_from_scoring_row(row) for row in scoring_rows]

    def _is_display_only_blend_scoring_row(self, row: Dict) -> bool:
        if str(row.get("scoring_input_kind") or "") != "recovered_active_identity":
            return False
        path = str(row.get("raw_source_path") or row.get("source_path") or "").lower()
        exclusion = str(row.get("score_exclusion_reason") or "").strip().lower()
        return (
            exclusion == "nested_display_only"
            or "nestedrows" in path
            or "child_ingredients" in path
        )

    def _active_ingredient_from_scoring_row(self, row: Dict) -> Dict:
        name = str(
            row.get("name")
            or row.get("standard_name")
            or row.get("raw_source_text")
            or row.get("canonical_id")
            or ""
        ).strip()
        standard_name = str(row.get("standard_name") or row.get("standardName") or name).strip()
        return {
            "name": name,
            "standardName": standard_name,
            "raw_source_text": row.get("raw_source_text") or name,
            "raw_source_path": row.get("raw_source_path"),
            "canonical_id": row.get("canonical_id") or row.get("parent_key"),
            "quantity": row.get("quantity", row.get("dosage")),
            "unit": row.get("unit", row.get("dosage_unit")),
            "forms": row.get("forms") or [],
            "matched_form": row.get("matched_form"),
            "dose_data_quality": row.get("dose_data_quality"),
        }

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
                # Cluster-matching alias map (canonical → variants). Used by
                # _collect_synergy_data to recover products where DSLD parser
                # writes "coenzyme q10" but the cluster ingredient is "coq10".
                "cluster_ingredient_aliases": "data/cluster_ingredient_aliases.json",
            }

        # Reviewed exact-identity redirects are part of the identity contract,
        # not an optional enrichment module. Load them even for older config
        # files so cleaner and enricher cannot silently drift.
        db_paths.setdefault(
            "canonical_equivalences", "data/canonical_equivalences.json"
        )

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
                    "equivalences",
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

        missing_critical = []
        for db in critical_dbs:
            db_data = self.databases.get(db, {})
            if not db_data or len(db_data) == 0:
                missing_critical.append(db)
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

        non_identity_form_names = {
            "molecular distilled",
            "triglyceride form",
            "phospholipid form",
        }

        for parent_key, parent_data in quality_map.items():
            if parent_key.startswith("_") or not isinstance(parent_data, dict):
                continue

            match_rules = parent_data.get('match_rules', {})
            if match_rules.get("deprecated_in_favor_of"):
                continue
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
                name_texts = list(form_aliases)
                if norm_module.normalize_text(form_name) not in non_identity_form_names:
                    name_texts.insert(0, form_name)
                for alias_text in name_texts:
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

        def _recognition_priority(result: Dict) -> int:
            source = (result or {}).get("recognition_source")
            priorities = {
                "other_ingredients": 1,
                "botanical_ingredients": 1,
                "standardized_botanicals": 1,
                "harmful_additives": 2,
                "banned_recalled_ingredients": 3,
            }
            return priorities.get(source, 0)

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
                    if not text_norm:
                        continue
                    existing = nonscorable_idx.get(text_norm)
                    if existing is None or _recognition_priority(result) > _recognition_priority(existing):
                        nonscorable_idx[text_norm] = result

        # Index banned_recalled_ingredients separately (different structure)
        banned_db = self.databases.get('banned_recalled_ingredients', {})
        banned_list = banned_db.get('ingredients', []) if isinstance(banned_db, dict) else []
        for entry in banned_list:
            if not isinstance(entry, dict):
                continue
            entity_type = entry.get('entity_type', 'ingredient')
            # Class entities (policy watchlists like SPIKE_ANABOLIC_STEROIDS)
            # expose specific molecule aliases that must be recognized via
            # exact dict lookup. Fuzzy/token matching for classes stays
            # disabled further down in _check_banned_substances.
            if entity_type not in {'ingredient', 'contaminant', 'class', None, ''}:
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
                if not text_norm:
                    continue
                existing = nonscorable_idx.get(text_norm)
                if existing is None or _recognition_priority(result) > _recognition_priority(existing):
                    nonscorable_idx[text_norm] = result

        self._nonscorable_index = nonscorable_idx

        # ── Sprint 1: UNII-anchored non-scorable index ──
        # Walk the same 4 reference DBs + banned_recalled and index by
        # entry's external_ids.unii. Higher recognition_priority wins on
        # cross-DB collision (banned > harmful > other/botanical/std_bot).
        nonscorable_unii_idx: Dict[str, Dict] = {}
        for db_key, list_key, rec_type, reason_fn in db_configs:
            db = self.databases.get(db_key, {})
            entries = db.get(list_key, []) if isinstance(db, dict) else []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                eid = entry.get("external_ids") or {}
                entry_unii = _normalize_unii(
                    (eid.get("unii") if isinstance(eid, dict) else None)
                    or entry.get("unii")
                )
                if not entry_unii:
                    continue
                result = {
                    "recognition_source": db_key,
                    "recognition_reason": reason_fn(entry),
                    "matched_entry_id": entry.get("id"),
                    "matched_entry_name": entry.get("standard_name"),
                    "recognition_type": rec_type,
                }
                existing = nonscorable_unii_idx.get(entry_unii)
                if existing is None or _recognition_priority(result) > _recognition_priority(existing):
                    nonscorable_unii_idx[entry_unii] = result

        # Also index banned_recalled by UNII (mirrors the name-indexed pass below)
        banned_db = self.databases.get("banned_recalled_ingredients", {})
        banned_list = banned_db.get("ingredients", []) if isinstance(banned_db, dict) else []
        for entry in banned_list:
            if not isinstance(entry, dict):
                continue
            entity_type = entry.get("entity_type", "ingredient")
            if entity_type not in {"ingredient", "contaminant", "class", None, ""}:
                continue
            eid = entry.get("external_ids") or {}
            entry_unii = _normalize_unii(
                (eid.get("unii") if isinstance(eid, dict) else None)
                or entry.get("unii")
            )
            if not entry_unii:
                continue
            result = {
                "recognition_source": "banned_recalled_ingredients",
                "recognition_reason": "banned",
                "matched_entry_id": entry.get("id"),
                "matched_entry_name": entry.get("standard_name"),
                "recognition_type": "non_scorable",
            }
            existing = nonscorable_unii_idx.get(entry_unii)
            if existing is None or _recognition_priority(result) > _recognition_priority(existing):
                nonscorable_unii_idx[entry_unii] = result

        self._nonscorable_unii_index = nonscorable_unii_idx

        elapsed = time.monotonic() - t0
        self.logger.info(
            f"Performance indexes built in {elapsed:.2f}s: "
            f"IQM exact={len(exact_idx)} norm={len(norm_idx)} entries, "
            f"non-scorable={len(nonscorable_idx)} entries, "
            f"non-scorable-UNII={len(nonscorable_unii_idx)} entries"
        )

    @staticmethod
    def _recognition_blocks_scoring(recognition: Optional[Dict]) -> bool:
        """Only banned/recalled ingredients block scoring outright (B0 gate).

        harmful_additives are a SEPARATE penalty concern (Section B1) and must
        NEVER block IQM quality scoring (Section A).  An ingredient can
        legitimately appear in both IQM and harmful_additives, but scoring
        is context-aware: the scorer suppresses low/moderate harmful
        penalties for active-source ingredients (their IQM quality score is
        the correct signal).  High/critical severity still fires for actives.
        """
        if not recognition:
            return False
        return recognition.get("recognition_source") in {
            "banned_recalled_ingredients",
        }

    @staticmethod
    def _is_blocked_botanical_source_marker_match(
        ingredient: Dict,
        match_result: Optional[Dict],
    ) -> bool:
        """Return True when a botanical cleaner ID was scored as a marker.

        The Phase 3 IQM hard-stop only applies when the cleaner's canonical is
        itself an IQM parent. Botanical source canonicals such as tomato and
        broccoli live in botanical databases, so they need a separate guard:
        marker compounds may annotate the row later, but they must not replace
        the declared botanical as the primary scored identity.
        """
        if not match_result or not isinstance(match_result, dict):
            return False
        source_db = ingredient.get("canonical_source_db")
        if source_db not in BOTANICAL_CANONICAL_SOURCE_DBS:
            return False
        source_id = ingredient.get("canonical_id")
        if not isinstance(source_id, str) or not source_id:
            return False
        resolved_id = match_result.get("canonical_id")
        blocked_markers = BOTANICAL_SOURCE_MARKER_CANONICAL_BLOCKLIST.get(source_id)
        if not blocked_markers:
            return False
        if resolved_id in blocked_markers:
            return True

        # Priority-first matching may correctly select the botanical parent
        # from the row name before considering a marker-valued form. The form
        # still declares the contradictory marker lineage and must trigger the
        # same fail-safe.
        blocked_form_names = {
            marker.replace("_", " ").casefold() for marker in blocked_markers
        }
        declared_form_names = {
            re.sub(r"[^a-z0-9]+", " ", str(form.get("name") or "").casefold()).strip()
            for form in ingredient.get("forms") or []
            if isinstance(form, dict)
        }
        return bool(blocked_form_names & declared_form_names)

    def _apply_context_canonical_override_match(
        self,
        ingredient: Dict,
        quality_map: Dict,
    ) -> Optional[Dict]:
        """Return a synthetic IQM match_result honoring a cleaner-stamped
        context override, or None.

        Consumed BEFORE _match_quality_map for any row that
        ``EnhancedDSLDNormalizer._apply_context_canonical_override`` stamped
        with ``context_override_applied=True``. When all of:
          - ``context_override_applied`` is True
          - ``cleaner_canonical_id_override`` is set
          - ``cleaner_preferred_iqm_form_override`` is set
          - the parent + form exist under that parent in quality_map
        are satisfied, we build a match_result mirroring the canonical
        shape returned by _match_quality_map's form-match path and return
        it. The match_tier is tagged ``curated_context_override`` so
        downstream audits can identify these decisions.

        FAIL-SAFE: if the override declares a form key that does NOT
        resolve under the parent (typo / IQM drift / parent renamed),
        we return None — the caller will fall through to normal
        _match_quality_map matching. We log a WARNING so the rerun
        verification catches the divergence. We do NOT silently swap
        in an unspecified form, because the whole point of the override
        is to force a specific form choice.

        Spec: reports/not_scored_triage/cleaner_side_context_routing_spec.md
        """
        if not isinstance(ingredient, dict):
            return None
        if not ingredient.get("context_override_applied"):
            return None
        parent_id = ingredient.get("cleaner_canonical_id_override")
        form_name = ingredient.get("cleaner_preferred_iqm_form_override")
        override_id = ingredient.get("context_override_id") or "?"
        if not parent_id or not form_name:
            # Override is parent-only (no explicit form). Let normal
            # matching run — the cleaner_canonical_id (now overwritten by
            # the applier) constrains the parent via Phase 3 authority.
            return None
        parent = quality_map.get(parent_id)
        # Use module-level logger if self.logger is unavailable (defensive —
        # the helper may be exercised in unit tests that bypass __init__).
        _log = getattr(self, "logger", None) or logging.getLogger(__name__)
        if not parent or not isinstance(parent, dict):
            _log.warning(
                "context_canonical_override %s set_canonical_id=%r not found in "
                "quality_map. Falling back to normal matching.",
                override_id, parent_id,
            )
            return None
        forms = parent.get("forms", {}) or {}
        form_data = forms.get(form_name)
        if not form_data or not isinstance(form_data, dict):
            _log.warning(
                "context_canonical_override %s set_preferred_iqm_form=%r not "
                "found under parent %r. Falling back to normal matching "
                "(NOT silently using unspecified form).",
                override_id, form_name, parent_id,
            )
            return None

        # Build the canonical match_result shape mirroring
        # _match_quality_map's form-level return at scripts/enrich_supplements_v3.py:6447
        bio_score = form_data.get("bio_score")
        natural = form_data.get("natural", False)
        # v3.6.0: score == bio_score (no natural+3 bake-in)
        score = bio_score
        return {
            "canonical_id": parent_id,
            "form_id": form_name,
            "standard_name": parent.get("standard_name", parent_id),
            "form_name": form_name,
            "bio_score": bio_score,
            "natural": natural,
            "score": score,
            "absorption": form_data.get("absorption"),
            "notes": form_data.get("notes"),
            "dosage_importance": form_data.get("dosage_importance", 1.0),
            "category": parent.get("category", "other"),
            "match_tier": "curated_context_override",
            "context_override_id": override_id,
            "context_override_applied": True,
            "context_override_review_validated": (
                ingredient.get("context_override_review_validated") is True
            ),
            "context_override_clinical_review_status": ingredient.get(
                "context_override_clinical_review_status"
            ),
            "context_override_review_scope": ingredient.get(
                "context_override_review_scope"
            ),
            "context_override_reviewer": ingredient.get(
                "context_override_reviewer"
            ),
            "context_override_review_date": ingredient.get(
                "context_override_review_date"
            ),
        }

    @staticmethod
    def _preserve_cleaner_safety_canonical(ingredient: Dict, quality_entry: Dict) -> None:
        """Attach safety canonical provenance without suppressing IQM scoring.

        High-risk/watchlist ingredients can still be legitimate active
        ingredients in the product. Section A may score the normal IQM identity,
        while B0/export warnings use banned_recalled_ingredients. Preserve that
        cleaner safety identity explicitly so downstream consumers do not have
        to infer it from the normal IQM canonical.
        """
        if ingredient.get("canonical_source_db") != "banned_recalled_ingredients":
            return
        canonical_id = ingredient.get("canonical_id")
        if not isinstance(canonical_id, str) or not canonical_id.startswith(("RISK_", "BANNED_")):
            return
        quality_entry["safety_canonical_id"] = canonical_id
        quality_entry["safety_canonical_source_db"] = "banned_recalled_ingredients"
        quality_entry["safety_canonical_preserved"] = True
        quality_entry["fallback_class"] = "clinical_fail_safe"
        quality_entry["fallback_reason"] = "cleaner_safety_canonical_preservation"

    @staticmethod
    def _preserve_cleaner_botanical_canonical(ingredient: Dict, quality_entry: Dict) -> None:
        """Identity_bioactivity_split Phase 5: preserve cleaner-set botanical
        canonical_id on the enriched quality_entry when the IQM matcher
        returned no match (canonical_id=None on the entry).

        Without this, source-botanical ingredients (acerola, turmeric, etc.)
        lose their cleaner-assigned canonical_id during enrichment because
        the IQM matcher only searches ingredient_quality_map.json. The
        canonical needs to survive so _compute_delivers_markers can look up
        marker contributions in botanical_marker_contributions.json.
        """
        cleaner_src = ingredient.get("canonical_source_db")
        if cleaner_src not in {"botanical_ingredients", "standardized_botanicals"}:
            return
        cleaner_cid = ingredient.get("canonical_id")
        if not isinstance(cleaner_cid, str) or not cleaner_cid:
            return
        # Only fill in when the matcher didn't already pick one up.
        if quality_entry.get("canonical_id"):
            return
        quality_entry["canonical_id"] = cleaner_cid
        quality_entry["canonical_source_db"] = cleaner_src
        quality_entry["canonical_preserved_from_cleaner"] = True
        quality_entry["fallback_class"] = "clinical_fail_safe"
        quality_entry["fallback_reason"] = "cleaner_botanical_canonical_preservation"

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
            'coa': re.compile(
                r'\b('
                r'COAs?|certificates?\s+of\s+analysis|analysis\s+certificates?|'
                r'(?:third[-\s]?party\s+)?lab\s+(?:test\s+)?reports?'
                r')\b',
                re.I,
            ),
            'qr_code': re.compile(r'\bQR\s*code\b', re.I),
            'batch_lookup': re.compile(
                r'\b(batch|lot)\s+(lookup|look\s*up|search|verify|verification|trace|tracking)\b|'
                r'\b(enter|submit|scan)\s+(?:your\s+|the\s+)?(batch|lot)\s+(number|code)\b|'
                r'\b(batch|lot)\s+(number|code)\b.{0,80}\b(test\s+results?|lab\s+reports?|COA|certificate\s+of\s+analysis)\b',
                re.I,
            ),

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
            'cfu_scientific': re.compile(
                r'(?P<coefficient>\d+(?:\.\d+)?)\s*'
                r'(?:'
                r'[x×]\s*10\s*(?:(?:\^|\*\*)\s*(?P<ascii_exponent>[+-]?\d+)|(?P<superscript_exponent>[⁰¹²³⁴⁵⁶⁷⁸⁹]+))'
                r'|e\s*(?P<e_exponent>[+-]?\d+)'
                r')\s*'
                r'(?:cfu(?:s)?|colony[\s-]*forming\s+unit(?:s)?)\b',
                re.I,
            ),
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
                    # When every form has an authored percentage, preserve it
                    # exactly. Any remainder is unknown form mass; normalizing
                    # the known forms to 100% overstates their evidence.

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

        # Comparison uses TWO normalizations:
        #   1. _normalize_text — case + symbols + dashes (preserves hyphens)
        #   2. make_normalized_key — additionally collapses hyphens/spaces
        #      so "Alpha-Lipoic Acid" matches "Alpha Lipoic Acid"
        #
        # Bug 2026-04-29: clinical_studies entries are inconsistent about
        # hyphens ("Alpha-Lipoic Acid" vs "Alpha Lipoic Acid") and so are
        # supplement labels. Without the key-level pass, real evidence
        # silently fails to match — Pure Encapsulations Alpha Lipoic Acid
        # 100mg, NAC, Coenzyme Q10, L-Carnitine, etc. were all hitting C=0.
        candidate_pairs: List[Tuple[str, str, str]] = []
        for candidate in candidates:
            norm = self._normalize_text(candidate)
            key = norm_module.make_normalized_key(candidate)
            if norm or key:
                candidate_pairs.append((str(candidate), norm, key))
        if not candidate_pairs:
            return None

        excluded_norms = set()
        excluded_keys = set()
        for value in (study.get("exclude_aliases") or []):
            n = self._normalize_text(value)
            k = norm_module.make_normalized_key(value)
            if n: excluded_norms.add(n)
            if k: excluded_keys.add(k)
        if excluded_norms and any(norm in excluded_norms for _, norm, _ in candidate_pairs):
            return None
        if excluded_keys and any(key in excluded_keys for _, _, key in candidate_pairs):
            return None

        target_norm = self._normalize_text(study_name)
        target_key = norm_module.make_normalized_key(study_name)
        if any(norm == target_norm for _, norm, _ in candidate_pairs):
            return {"method": "standard_name", "matched_term": study_name}
        if target_key and any(key == target_key for _, _, key in candidate_pairs):
            return {"method": "standard_name_key", "matched_term": study_name}

        alias_map_norm = {}
        alias_map_key = {}
        for alias in self._collect_clinical_aliases(study):
            an = self._normalize_text(alias)
            ak = norm_module.make_normalized_key(alias)
            if an: alias_map_norm[an] = alias
            if ak: alias_map_key[ak] = alias

        for _, norm, key in candidate_pairs:
            matched_alias = alias_map_norm.get(norm)
            if matched_alias and norm not in excluded_norms:
                return {"method": "alias", "matched_term": matched_alias}
        for _, norm, key in candidate_pairs:
            matched_alias = alias_map_key.get(key)
            if matched_alias and key not in excluded_keys:
                return {"method": "alias_key", "matched_term": matched_alias}

        return None

    def _product_context_branded_token_for_ingredient(
        self,
        product_text: str,
        ingredient: Dict,
        ing_name: str,
        std_name: str,
    ) -> Optional[str]:
        """Return a product-name branded token that safely applies to a row.

        Some DSLD rows put the branded extract in the product name rather than
        the active-ingredient row. Doctor's Best 82300 is the canonical shape:
        product name says "Ashwagandha With Sensoril" while the active row says
        only "Ashwagandha root and leaf extract" plus 10% withanolide
        glycosides. Do not apply product-level tokens globally; require the row
        identity to be compatible with the branded ingredient family.
        """
        if not product_text:
            return None

        canonical_id = str(ingredient.get("canonical_id") or "").strip().lower()
        row_text = " ".join(
            str(value or "")
            for value in (
                ing_name,
                std_name,
                ingredient.get("raw_source_text"),
                ingredient.get("standard_name"),
                " ".join(
                    str(form.get("name") or "")
                    for form in (ingredient.get("forms") or [])
                    if isinstance(form, dict)
                ),
            )
        ).lower()

        is_vitamin_c_row = (
            canonical_id == "vitamin_c"
            or re.search(r"(?<![a-z0-9])vit(?:amin)?\s*c(?![a-z0-9])", row_text)
            or "ascorb" in row_text
        )
        if is_vitamin_c_row:
            context_text = f"{product_text} {row_text}"
            context_lower = context_text.lower()
            product_lower = product_text.lower()
            context_key = norm_module.make_normalized_key(context_text)
            row_key = norm_module.make_normalized_key(row_text)
            negated_liposomal = bool(
                re.search(r"\b(?:non|not|without)\s*[- ]?liposomal\b", context_lower)
                or "nonliposomal" in context_key
            )
            row_has_pureway = "purewayc" in row_key or "pureway" in row_key
            direct_liposomal_pureway = bool(
                re.search(r"\bliposom\w*\s+pure\s*way[-\s]*c\b", context_lower)
                or re.search(r"\bliposom\w*\s+pureway[-\s]*c\b", context_lower)
                or re.search(r"\bliposom\w*\s+pure\s*way\b", context_lower)
                or re.search(r"\bpure\s*way[-\s]*c\s+liposom\w*\b", context_lower)
                or re.search(r"\bpureway[-\s]*c\s+liposom\w*\b", context_lower)
            )
            liposomal_vitamin_c_product = bool(
                re.search(r"\bliposom\w*\s+vit(?:amin)?\s*c\b", product_lower)
                or re.search(r"\bvit(?:amin)?\s*c\s+liposom\w*\b", product_lower)
            )
            if row_has_pureway and not negated_liposomal and (
                direct_liposomal_pureway or liposomal_vitamin_c_product
            ):
                return "Liposomal PureWay-C"

        is_collagen_row = (
            canonical_id == "collagen"
            or "collagen" in row_text
            or "cartilage" in row_text
        )
        if is_collagen_row:
            context_text = f"{product_text} {row_text}"
            context_key = norm_module.make_normalized_key(context_text)
            if (
                re.search(r"(?<![a-z0-9])uc-?ii(?![a-z0-9])", context_text.lower())
                or "interhealthucii" in context_key
            ):
                return "UC-II"

        is_ashwagandha_row = (
            canonical_id == "ashwagandha"
            or "ashwagandha" in row_text
            or "withania" in row_text
        )
        if not is_ashwagandha_row:
            return None

        allowed_tokens = {"KSM-66", "Sensoril", "Shoden"}
        product_text_lower = product_text.lower()
        product_text_key = norm_module.make_normalized_key(product_text)
        for raw_token, canonical_token in BRANDED_INGREDIENT_TOKENS.items():
            if canonical_token not in allowed_tokens:
                continue
            token_lower = raw_token.lower()
            token_key = norm_module.make_normalized_key(raw_token)
            token_found = bool(
                re.search(r"(?<![a-z0-9])" + re.escape(token_lower) + r"(?![a-z0-9])", product_text_lower)
                or (token_key and token_key in product_text_key)
            )
            if token_found:
                return canonical_token

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
        ing_key = norm_module.make_normalized_key(ing_name) if ing_name else ""
        std_key = norm_module.make_normalized_key(std_name) if std_name else ""
        target_key = norm_module.make_normalized_key(target_name)

        # Check direct match against canonical name
        if ing_norm and ing_norm == target_norm:
            return {"method": "exact", "matched_alias": None}
        if std_norm and std_norm == target_norm:
            return {"method": "exact_via_std", "matched_alias": None}
        if ing_key and ing_key == target_key:
            return {"method": "exact_key", "matched_alias": None}
        if std_key and std_key == target_key:
            return {"method": "exact_key_via_std", "matched_alias": None}

        # Check alias matches
        for alias in aliases:
            alias_norm = self._normalize_text(alias)
            alias_key = norm_module.make_normalized_key(alias)
            if ing_norm and ing_norm == alias_norm:
                return {"method": "alias", "matched_alias": alias}
            if std_norm and std_norm == alias_norm:
                return {"method": "alias_via_std", "matched_alias": alias}
            if ing_key and ing_key == alias_key:
                return {"method": "alias_key", "matched_alias": alias}
            if std_key and std_key == alias_key:
                return {"method": "alias_key_via_std", "matched_alias": alias}

        return None

    _REGEX_CACHE_LIMIT = 50000

    def _cached_compile_regex(self, pattern: str) -> re.Pattern:
        """Compile a regex once per enricher instance."""
        cached = self._regex_pattern_cache.get(pattern)
        if cached is not None:
            return cached
        if len(self._regex_pattern_cache) >= self._REGEX_CACHE_LIMIT:
            self._regex_pattern_cache.clear()
        compiled = re.compile(pattern)
        self._regex_pattern_cache[pattern] = compiled
        return compiled

    def _cached_token_bounded_pattern(self, normalized_text: str) -> Optional[re.Pattern]:
        """Return cached whole-token regex for already-normalized text."""
        if not normalized_text:
            return None
        cached = self._token_bounded_pattern_cache.get(normalized_text)
        if cached is not None:
            return cached
        if len(self._token_bounded_pattern_cache) >= self._REGEX_CACHE_LIMIT:
            self._token_bounded_pattern_cache.clear()
        pattern = r'(?<![a-z0-9])' + re.escape(normalized_text) + r'(?![a-z0-9])'
        compiled = re.compile(pattern)
        self._token_bounded_pattern_cache[normalized_text] = compiled
        return compiled

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
            if self._is_short_acronym_alias(candidate):
                if not self._literal_short_acronym_match(ingredient_name, candidate):
                    continue
            pattern = self._cached_token_bounded_pattern(cand_norm)
            if pattern and pattern.search(ing_norm):
                return True, candidate

        return False, None

    def _is_short_acronym_alias(self, alias: str) -> bool:
        """Return true for short acronym aliases that need literal bounds."""
        compact = re.sub(r"[^A-Za-z0-9]", "", str(alias or ""))
        if compact.lower() in {"pho", "phos"}:
            return True
        if not (2 <= len(compact) <= 5):
            return False
        uppercase_count = sum(1 for ch in compact if ch.isupper())
        return compact.isupper() or uppercase_count >= 2

    def _literal_short_acronym_match(self, ingredient_name: str, alias: str) -> bool:
        """Match short acronym aliases only as raw standalone tokens.

        Broad normalization turns hyphens into spaces. That is useful for
        normal ingredient names, but it made `Iso-Phos` look like it contained
        the PHO/PHOs acronym for partially hydrogenated oils. For acronym
        aliases, require the original label to contain the acronym without a
        neighboring alphanumeric or hyphen.
        """
        if not ingredient_name or not alias:
            return False
        pattern = re.compile(
            r"(?<![A-Za-z0-9-])" + re.escape(str(alias)) + r"(?![A-Za-z0-9-])",
            re.IGNORECASE,
        )
        return bool(pattern.search(str(ingredient_name)))

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
        return bool(self._color_context_pattern.search(ingredient_norm))

    def _hyphen_space_token_pattern(self, variant: str) -> Optional[re.Pattern]:
        """Build a token-bounded regex that tolerates hyphens/spaces between tokens."""
        norm = self._normalize_text(variant)
        if not norm:
            return None
        tokens = [t for t in re.split(r'[\s-]+', norm) if t]
        if not tokens:
            return None
        cached = self._hyphen_space_pattern_cache.get(norm)
        if cached is not None:
            return cached
        if len(self._hyphen_space_pattern_cache) >= self._REGEX_CACHE_LIMIT:
            self._hyphen_space_pattern_cache.clear()
        pattern = r'(?<![a-z0-9])' + r'[-\s]+'.join(map(re.escape, tokens)) + r'(?![a-z0-9])'
        compiled = re.compile(pattern)
        self._hyphen_space_pattern_cache[norm] = compiled
        return compiled

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
                    if self._cached_compile_regex(pattern).search(ing_norm):
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
                try:
                    matched = self._cached_compile_regex(pattern).search(ing_norm)
                except re.error as exc:
                    self.logger.warning(
                        "Skipping malformed banned denylist regex '%s' for denylist_id=%s: %s",
                        pattern,
                        entry.get("id", ""),
                        exc,
                    )
                    continue
                if matched:
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

        # Extract strain IDs structurally rather than maintaining a partial
        # allowlist. Missing one code (for example M-63 or bare 35624) makes two
        # different strains look species-only and can grant the wrong clinical
        # evidence. Bounds deliberately exclude one/two-digit dose and CFU text.
        strain_id_pattern = re.compile(
            r'('
            r'atcc\s*(?:pta\s*)?\d+|dsm\s*\d+|mtcc\s*\d+|'
            r'sd-[a-z0-9]+(?:-[a-z0-9]+){1,3}|'
            r'\b[a-z][a-z.]*-?\d+[a-z]?(?::\d+)?\b|'
            r'\b\d{3,6}[a-z]?(?::\d+)?\b|'
            r'ncfm|\blgg\b|\bgg\b|\bprodentis\b|\bshirota\b|\bnissle\b'
            r')',
            re.IGNORECASE,
        )
        strain_ids = strain_id_pattern.findall(strain_norm)

        # Extract species name (second word, e.g., "reuteri", "rhamnosus")
        words = strain_norm.split()
        species = words[1] if len(words) > 1 else None
        canonical_target_norm = self._normalize_text(target_name)
        canonical_target_words = canonical_target_norm.split()
        canonical_target_species = canonical_target_words[1] if len(canonical_target_words) > 1 else None

        # Check all aliases with genus normalization
        all_targets = [target_name] + aliases
        for target in all_targets:
            target_norm = self._normalize_text(target)
            target_words = target_norm.split()
            target_species = target_words[1] if len(target_words) > 1 else None
            target_ids = strain_id_pattern.findall(target_norm)

            if strain_ids and target_ids:
                strain_ids_norm = {re.sub(r'[^a-z0-9]+', '', sid.lower()) for sid in strain_ids}
                target_ids_norm = {re.sub(r'[^a-z0-9]+', '', tid.lower()) for tid in target_ids}
                if strain_ids_norm & target_ids_norm:
                    if not species:
                        return True
                    if species == target_species or species == canonical_target_species:
                        return True

            # If species match, check genus compatibility
            if species and target_species and species == target_species:
                # Check if strain IDs match (if present in both)
                if strain_ids and target_ids:
                    # Normalize IDs for comparison
                    strain_ids_norm = {re.sub(r'[^a-z0-9]+', '', sid.lower()) for sid in strain_ids}
                    target_ids_norm = {re.sub(r'[^a-z0-9]+', '', tid.lower()) for tid in target_ids}
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
                    sid_norm = re.sub(r'[^a-z0-9]+', '', sid.lower())
                    if sid_norm in re.sub(r'[^a-z0-9]+', '', target_norm):
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
            product.get('product_name', '') or '',
            product.get('bundleName', '') or '',
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
    # Identity vs Bioactivity Split — delivers_markers computation
    # =========================================================================
    # When a source-botanical ingredient ALSO contributes to a marker (e.g. an
    # acerola extract contributes vitamin_c), the marker contribution is recorded
    # in `delivers_markers[]` on the ingredient record. Section A scoring uses
    # the primary canonical_id; Section C scoring (Phase 5) uses delivers_markers
    # at scaled confidence. See scripts/data/botanical_marker_contributions.json.

    _STANDARDIZATION_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%", re.IGNORECASE)
    _STANDARDIZATION_TERMS_RE = re.compile(
        r"\bstandardi[sz]ed\s+to\b|\bstd\.?\s+to\b|\bcontaining\s+\d|\bmin\.?\s+\d+\s*%",
        re.IGNORECASE,
    )

    def _scan_label_for_standardization(
        self, label_text: str, keywords: List[str]
    ) -> Tuple[bool, Optional[float]]:
        """Returns (has_standardization, pct_value_or_None).

        has_standardization is True when the label text mentions ANY of the
        botanical's standardization_keywords (e.g. 'curcuminoid', '95%',
        'standardized to'). pct_value extracts the numeric standardization
        percentage when the keyword appears alongside a percentage.
        """
        if not label_text:
            return False, None
        text_l = label_text.lower()
        # Any keyword present?
        keyword_hit = any(k.lower() in text_l for k in (keywords or []))
        if not keyword_hit and not self._STANDARDIZATION_TERMS_RE.search(label_text):
            return False, None
        # Try to extract percentage if present
        m = self._STANDARDIZATION_PCT_RE.search(label_text)
        pct = float(m.group(1)) if m else None
        return True, pct

    def _compute_delivers_markers(
        self, ingredient_record: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Compute the marker contributions an ingredient delivers based on
        its primary canonical_id and scripts/data/botanical_marker_contributions.json.

        Returns a list of marker contribution dicts. Empty list when:
          - canonical_id is not a source-botanical with declared marker contributions
          - botanical_marker_contributions database is missing
          - canonical_id is itself a marker (no need to self-credit)

        Each marker entry has fields:
          - marker_canonical_id, marker_source_db
          - estimated_dose_mg (None when no dose computable)
          - estimation_method: one of
              'default_contribution' (USDA-cited default × ingredient mass)
              'standardization_pct'  (declared standardization % × ingredient mass)
              'standardization_keyword' (keyword present but no pct extractable)
              'none' (provenance only — no Section C credit)
          - confidence_scale (0.0–1.0 multiplier for Section C credit)
          - evidence_source, evidence_url, evidence_id (from contributions DB)
          - basis: short string explaining the calculation
        """
        bmc_db = (self.databases or {}).get("botanical_marker_contributions") or {}
        botanicals = bmc_db.get("botanicals") or {}
        if not botanicals:
            return []

        canonical_id = ingredient_record.get("canonical_id")
        if not canonical_id:
            return []
        contributions = (botanicals.get(canonical_id) or {}).get("delivers") or []
        if not contributions:
            return []

        # Label text for standardization scan: combine raw_source_text + matched_form + original_label
        label_text = " ".join(
            str(ingredient_record.get(k, "") or "")
            for k in ("raw_source_text", "matched_form", "original_label", "name")
        )

        # Ingredient mass in grams (for default-contribution dose math)
        quantity = ingredient_record.get("quantity")
        unit_norm = (ingredient_record.get("unit_normalized") or "").lower()
        try:
            qty_num = float(quantity) if quantity is not None else None
        except (TypeError, ValueError):
            qty_num = None
        mass_g: Optional[float] = None
        if qty_num is not None and qty_num > 0:
            if unit_norm in {"mg"}:
                mass_g = qty_num / 1000.0
            elif unit_norm in {"g", "gram", "grams"}:
                mass_g = qty_num
            elif unit_norm in {"ug", "mcg", "microgram", "micrograms"}:
                mass_g = qty_num / 1_000_000.0

        results: List[Dict[str, Any]] = []
        for contrib in contributions:
            marker_id = contrib.get("marker_canonical_id")
            model = contrib.get("model")
            keywords = contrib.get("standardization_keywords") or []
            entry: Dict[str, Any] = {
                "marker_canonical_id": marker_id,
                "marker_source_db": "ingredient_quality_map",
                "evidence_source": contrib.get("evidence_source"),
                "evidence_url": contrib.get("evidence_url"),
                "evidence_id": contrib.get("evidence_id"),
                "estimated_dose_mg": None,
                "estimation_method": "none",
                "confidence_scale": 0.0,
                "basis": "",
            }
            has_std, pct = self._scan_label_for_standardization(label_text, keywords)
            if model == "standardization_required":
                min_pct = contrib.get("min_standardization_pct_required")
                if not has_std:
                    entry["basis"] = (
                        f"No standardization keyword found in label "
                        f"({', '.join(keywords[:2])!r}…). Marker recorded for "
                        "provenance only; no Section C dose credit."
                    )
                elif pct is not None and (min_pct is None or pct >= min_pct):
                    # Explicit standardization with pct meeting min
                    if mass_g is not None:
                        entry["estimated_dose_mg"] = round(mass_g * 1000.0 * (pct / 100.0), 3)
                        entry["estimation_method"] = "standardization_pct"
                        entry["confidence_scale"] = 1.0
                        entry["basis"] = (
                            f"Label declares {pct}% standardization × ingredient mass "
                            f"{quantity} {unit_norm}"
                        )
                    else:
                        entry["estimation_method"] = "standardization_keyword"
                        entry["confidence_scale"] = 0.5
                        entry["basis"] = (
                            f"Label declares {pct}% standardization but ingredient "
                            "mass not computable (no dose)."
                        )
                else:
                    # Keyword present but pct missing or below min
                    entry["estimation_method"] = "standardization_keyword"
                    entry["confidence_scale"] = 0.5
                    entry["basis"] = (
                        f"Standardization keyword present (no pct extracted or "
                        f"below {min_pct}% minimum)."
                    )
            elif model == "default_contribution":
                default_mg_per_g = contrib.get("default_contribution_mg_per_g")
                if default_mg_per_g is None:
                    continue
                if has_std and pct is not None:
                    # Label explicitly declares standardization — use it preferentially
                    if mass_g is not None:
                        entry["estimated_dose_mg"] = round(mass_g * 1000.0 * (pct / 100.0), 3)
                        entry["estimation_method"] = "standardization_pct"
                        entry["confidence_scale"] = 1.0
                        entry["basis"] = (
                            f"Label declares {pct}% standardization × ingredient mass "
                            f"{quantity} {unit_norm} (overrides default contribution)"
                        )
                elif mass_g is not None:
                    entry["estimated_dose_mg"] = round(mass_g * float(default_mg_per_g), 3)
                    entry["estimation_method"] = "default_contribution"
                    entry["confidence_scale"] = 0.7
                    entry["basis"] = (
                        f"USDA default {default_mg_per_g} mg/g × ingredient mass "
                        f"{quantity} {unit_norm}"
                    )
                else:
                    entry["estimation_method"] = "default_contribution"
                    entry["confidence_scale"] = 0.4
                    entry["basis"] = (
                        f"USDA default {default_mg_per_g} mg/g but ingredient mass "
                        "not computable (no dose, provenance only)"
                    )
            else:
                entry["basis"] = f"Unknown contribution model {model!r}"
            results.append(entry)
        return results

    # =========================================================================
    # SECTION A: INGREDIENT QUALITY DATA COLLECTORS
    # =========================================================================

    @staticmethod
    def _quality_match_identity_confidence(match_result: Optional[Dict]) -> float:
        if not isinstance(match_result, dict):
            return 0.0
        if match_result.get("match_status") == "FORM_UNMAPPED_FALLBACK":
            return 0.8
        return 1.0 if match_result.get("match_tier") == "exact" else 0.9

    def _identity_unii_values(
        self,
        row: Dict,
        *,
        include_forms: bool = True,
    ) -> set[str]:
        values = set()

        def add(value: Any) -> None:
            normalized = _normalize_unii(value)
            if normalized:
                values.add(normalized)

        add(row.get("uniiCode"))
        add(row.get("unii"))
        external_ids = row.get("external_ids")
        if isinstance(external_ids, dict):
            add(external_ids.get("unii"))
        if include_forms:
            for form in row.get("forms") or []:
                if not isinstance(form, dict):
                    continue
                if self._is_source_descriptor_form(form, parent_row=row):
                    continue
                add(form.get("uniiCode"))
                add(form.get("unii"))
                form_external_ids = form.get("external_ids")
                if isinstance(form_external_ids, dict):
                    add(form_external_ids.get("unii"))
        raw_taxonomy = row.get("raw_taxonomy")
        if isinstance(raw_taxonomy, dict):
            add(raw_taxonomy.get("uniiCode"))
            add(raw_taxonomy.get("unii"))
            if include_forms:
                for form in raw_taxonomy.get("forms") or []:
                    if isinstance(form, dict):
                        if self._is_source_descriptor_form(
                            form,
                            parent_row=raw_taxonomy,
                        ):
                            continue
                        add(form.get("uniiCode"))
                        add(form.get("unii"))
        return values

    def _is_source_descriptor_form(
        self,
        form: Dict,
        *,
        parent_row: Optional[Dict] = None,
    ) -> bool:
        """Return whether a form identifies provenance rather than the active."""
        category = str(form.get("category") or "").strip().lower()
        prefix = str(form.get("prefix") or "").strip().lower()
        name = str(form.get("name") or "").strip()
        parent_row = parent_row if isinstance(parent_row, dict) else {}
        raw_taxonomy = parent_row.get("raw_taxonomy")
        parent_category = str(
            parent_row.get("raw_category")
            or parent_row.get("category")
            or (
                raw_taxonomy.get("category")
                if isinstance(raw_taxonomy, dict)
                else ""
            )
            or ""
        ).strip().lower()

        if category in _SOURCE_DESCRIPTOR_FORM_CATEGORIES:
            return True
        if category == "botanical" and parent_category != "botanical":
            return True
        return bool(
            prefix in _SOURCE_DESCRIPTOR_FORM_PREFIXES
            and not (
                prefix == "from"
                and self._should_keep_from_prefixed_form_as_actual(name)
            )
        )

    def _identity_taxonomy_coherent(
        self,
        ingredient: Dict,
        match_result: Optional[Dict],
        quality_map: Dict,
    ) -> bool:
        match_tier = (
            match_result.get("match_tier")
            if isinstance(match_result, dict)
            else None
        )
        curated_context_override = self._is_reviewed_context_override_match(
            match_result
        )
        strong_match_tier = match_tier in {"exact", "normalized"} or (
            match_tier == "cleaner_canonical_parent"
            and match_result.get("cleaner_canonical_enforced") is True
        ) or curated_context_override
        # Ambiguity among FORMS of the SAME canonical identity (e.g. an ashwagandha
        # row that a "Sensoril" context resolved to the sensoril form while the
        # unspecified form remained a candidate) does NOT make the identity
        # incoherent — the canonical is unambiguous, only the form was disambiguated.
        # Only ambiguity across DIFFERENT canonical identities breaks coherence. Any
        # candidate that names a different canonical, or names none at all, is treated
        # conservatively as identity-level ambiguity.
        matched_canonical_id = (
            match_result.get("canonical_id") if isinstance(match_result, dict) else None
        )
        identity_level_ambiguity = any(
            (not isinstance(cand, dict))
            or cand.get("canonical_id") != matched_canonical_id
            for cand in (
                match_result.get("match_ambiguity_candidates") or []
                if isinstance(match_result, dict)
                else []
            )
        )
        if (
            not isinstance(match_result, dict)
            or not strong_match_tier
            or match_result.get("match_status") == "FORM_UNMAPPED"
            or self._quality_match_identity_confidence(match_result) < 0.9
            or identity_level_ambiguity
        ):
            return False

        canonical_id = match_result.get("canonical_id")
        registry_entry = quality_map.get(canonical_id)
        if not canonical_id or not isinstance(registry_entry, dict):
            return False

        matched_standard = self._normalize_text(match_result.get("standard_name") or "")
        registry_standard = self._normalize_text(registry_entry.get("standard_name") or "")
        if not matched_standard or matched_standard != registry_standard:
            return False

        forms = registry_entry.get("forms") or {}
        form_id = match_result.get("form_id")
        selected_form = None
        if form_id:
            if not isinstance(forms, dict) or form_id not in forms:
                return False
            selected_form = forms[form_id]
        elif ingredient.get("forms"):
            return False

        # A direct row UNII identifies the active parent and therefore must be
        # consistent with the selected IQM parent.  UNIIs carried only by
        # ``forms`` identify source salts/forms instead (for example a
        # Phosphorus row sourced from calcium, potassium and sodium phosphate).
        # Requiring every source-form UNII to belong to the nutrient parent
        # conflates identity with formulation and rejects otherwise exact,
        # structured nutrient rows.  Form validity is already enforced above
        # by the selected IQM form and strong match tier.
        direct_uniis = self._identity_unii_values(
            ingredient,
            include_forms=False,
        )
        if direct_uniis:
            registry_uniis = self._identity_unii_values(registry_entry)
            if isinstance(selected_form, dict):
                registry_uniis.update(self._identity_unii_values(selected_form))
            if not registry_uniis or not direct_uniis.issubset(registry_uniis):
                return False

        return True

    @staticmethod
    def _is_reviewed_context_override_match(match_result: Optional[Dict]) -> bool:
        return bool(
            isinstance(match_result, dict)
            and match_result.get("match_tier") == "curated_context_override"
            and match_result.get("context_override_applied") is True
            and match_result.get("context_override_review_validated") is True
            and isinstance(match_result.get("context_override_id"), str)
            and match_result.get("context_override_id").strip()
            and match_result.get("context_override_id") != "?"
        )

    def _identity_candidate_resolver(
        self,
        quality_map: Dict,
        supplied_canonical_id: Optional[str] = None,
    ):
        identity_registry = self._current_canonical_identity_registry()

        def resolve(candidate: str) -> Optional[str]:
            # Structured taxonomy fields such as ``ingredientGroup`` name an
            # ingredient identity, not a form.  When that field resolves back
            # to the already-supplied IQM parent, accept it before consulting
            # the cross-database preferred index, whose flattened aliases also
            # include form names.  The equality guard is essential: it fixes
            # "Alpha-GPC" without newly trusting ambiguous standalone markers
            # such as AKBA.
            parent_preferred = self._infer_preferred_parent_from_context_cached(
                candidate,
                quality_map,
            )
            if parent_preferred and parent_preferred == supplied_canonical_id:
                return parent_preferred
            literal_preferred = identity_registry.preferred_index.get(
                str(candidate or "").lower().strip()
            )
            if literal_preferred:
                return literal_preferred[0]
            match_result = self._match_quality_map(
                candidate,
                candidate,
                quality_map,
                _form_extraction_attempt=True,
            )
            if isinstance(match_result, dict):
                canonical_id = match_result.get("canonical_id")
                if (
                    canonical_id
                    and match_result.get("match_status") != "FORM_UNMAPPED"
                    and match_result.get("match_tier") in {"exact", "normalized"}
                    and not match_result.get("match_ambiguity_candidates")
                ):
                    return self._quality_match_scoring_canonical(
                        match_result, quality_map
                    )
            preferred = identity_registry.resolve_verified_preferred(candidate)
            return preferred[0] if preferred else None

        return resolve

    def _current_canonical_identity_registry(self):
        if getattr(self, "_canonical_identity_databases", None) is not self.databases:
            self._canonical_identity_registry = build_canonical_identity_registry(
                self.databases
            )
            self._canonical_identity_databases = self.databases
        return self._canonical_identity_registry

    @staticmethod
    def _quality_match_scoring_canonical(
        match_result: Optional[Dict], quality_map: Dict
    ) -> Optional[str]:
        """Project a specific IQM match to its declared scoring parent."""
        if not isinstance(match_result, dict):
            return None
        matched_id = match_result.get("canonical_id")
        if not isinstance(matched_id, str) or not matched_id:
            return None
        matched_entry = quality_map.get(matched_id)
        match_rules = (
            matched_entry.get("match_rules")
            if isinstance(matched_entry, dict)
            else None
        )
        target_id = (
            match_rules.get("target_id")
            if isinstance(match_rules, dict)
            else None
        )
        if isinstance(target_id, str) and target_id in quality_map:
            return target_id
        return matched_id

    def _identity_parent_predicate(self, quality_map: Dict):
        relationship_document = self.databases.get("canonical_equivalences")
        if (
            getattr(self, "_identity_parent_quality_map", None) is not quality_map
            or getattr(self, "_identity_parent_relationship_document", None)
            is not relationship_document
        ):
            children: Dict[str, set[str]] = {}
            for canonical_id, entry in quality_map.items():
                if canonical_id == "_metadata" or not isinstance(entry, dict):
                    continue
                match_rules = entry.get("match_rules")
                parent_id = (
                    match_rules.get("parent_id")
                    if isinstance(match_rules, dict)
                    else None
                )
                if isinstance(parent_id, str) and parent_id in quality_map:
                    children.setdefault(parent_id, set()).add(canonical_id)
                for relationship in entry.get("relationships") or []:
                    if not isinstance(relationship, dict):
                        continue
                    target_id = relationship.get("target_id")
                    if (
                        relationship.get("type") == "category_for"
                        and isinstance(target_id, str)
                        and target_id in quality_map
                    ):
                        children.setdefault(canonical_id, set()).add(target_id)

            for parent_id, child_id in validated_canonical_parent_relationships(
                self.databases
            ):
                children.setdefault(parent_id, set()).add(child_id)

            descendants: Dict[str, set[str]] = {}
            for canonical_id in children:
                pending = list(children[canonical_id])
                resolved = set()
                while pending:
                    child = pending.pop()
                    if child in resolved:
                        continue
                    resolved.add(child)
                    pending.extend(children.get(child, ()))
                descendants[canonical_id] = resolved
            self._identity_parent_quality_map = quality_map
            self._identity_parent_relationship_document = relationship_document
            self._identity_parent_descendants = descendants

        descendants = self._identity_parent_descendants
        return lambda parent, child: child in descendants.get(parent, ())

    def _resolve_iqd_identity(
        self,
        ingredient: Dict,
        match_result: Optional[Dict],
        quality_map: Dict,
        *,
        allow_unscoreable_taxonomy_only: bool = False,
        authoritative_context_override: bool = False,
    ) -> Tuple[IdentityDecision, Optional[Dict], bool]:
        supplied_canonical_id = (
            self._quality_match_scoring_canonical(match_result, quality_map)
            if isinstance(match_result, dict)
            else ingredient.get("canonical_id")
        )
        taxonomy_coherent = self._identity_taxonomy_coherent(
            ingredient, match_result, quality_map
        )
        resolve_candidate = self._identity_candidate_resolver(
            quality_map,
            supplied_canonical_id=supplied_canonical_id,
        )
        canonical_parent_of = self._identity_parent_predicate(quality_map)
        if (
            taxonomy_coherent
            and self._is_reviewed_context_override_match(match_result)
        ):
            reviewed_canonical_id = match_result.get("canonical_id")

            def resolve_candidate(candidate: str) -> Optional[str]:
                return reviewed_canonical_id

        if authoritative_context_override and supplied_canonical_id:
            # A deliberate product-context MARKER override (e.g. a kelp-source row
            # whose product is a standardized "Fucoidan 70%" supplement) has already
            # replaced the raw-row identity with the clinically-correct scoring
            # marker. The raw source taxonomy it is CORRECTING (kelp) must not then be
            # used to "repair" the marker back to its generic source, so the override
            # canonical is authoritative for re-resolution and the gate confirms it
            # rather than reverting it. Genuine cross-identity mislabels are still
            # gated upstream by _is_blocked_botanical_source_marker_match.
            authoritative_canonical_id = supplied_canonical_id

            def resolve_candidate(candidate: str) -> Optional[str]:
                return authoritative_canonical_id

        decision = resolve_identity(
            ingredient,
            supplied_canonical_id,
            resolve_candidate,
            taxonomy_coherent=taxonomy_coherent,
            allow_unscoreable_taxonomy_only=allow_unscoreable_taxonomy_only,
            canonical_parent_of=canonical_parent_of,
        )

        if decision.disposition == "repaired" and decision.canonical_id:
            approved_name = decision.source_label_name or decision.label_display_name or ""
            match_result = self._match_quality_map(
                approved_name,
                approved_name,
                quality_map,
                cleaned_forms=ingredient.get("forms") or [],
                cleaner_canonical_id=decision.canonical_id,
            )
            taxonomy_coherent = self._identity_taxonomy_coherent(
                ingredient, match_result, quality_map
            )
            if (
                not taxonomy_coherent
                or not isinstance(match_result, dict)
                or self._quality_match_scoring_canonical(match_result, quality_map)
                != decision.canonical_id
            ):
                match_result = None

        return decision, match_result, taxonomy_coherent

    def _stamp_iqd_identity(
        self,
        entry: Dict,
        ingredient: Dict,
        decision: IdentityDecision,
        match_result: Optional[Dict],
        taxonomy_coherent: bool,
    ) -> None:
        final_canonical_id = decision.canonical_id_after
        key_ingredient = ingredient
        supplied_source_label_key = ingredient.get("source_label_key")
        if not (
            isinstance(supplied_source_label_key, str)
            and supplied_source_label_key.strip()
        ):
            key_ingredient = dict(ingredient)
            key_ingredient["canonical_id"] = final_canonical_id
        coherent_quality_match = bool(
            isinstance(match_result, dict)
            and match_result.get("match_status") != "FORM_UNMAPPED"
            and self._quality_match_scoring_canonical(
                match_result, self.databases.get("ingredient_quality_map", {})
            )
            == final_canonical_id
        )
        entry.update(
            {
                "source_label_key": self._rda_source_label_key(key_ingredient),
                "source_label_name": decision.source_label_name,
                "source_label_form": decision.source_label_form,
                "label_display_name": decision.label_display_name,
                "label_display_form": decision.label_display_form,
                "identity_disposition": decision.disposition,
                "canonical_id_before": decision.canonical_id_before,
                "canonical_id_after": final_canonical_id,
                "canonical_id": final_canonical_id,
                "identity_evidence": json.dumps(
                    [
                        {"field": item.field, "value": item.value, "kind": item.kind}
                        for item in decision.evidence
                    ],
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "identity_resolution_rationale": decision.rationale,
                "identity_taxonomy_coherent": taxonomy_coherent,
                "scoreable_identity": bool(
                    is_identity_scoreable(decision.disposition)
                    and final_canonical_id
                    and coherent_quality_match
                ),
            }
        )

    @staticmethod
    def _project_repaired_identity_to_active_row(
        active_row: Dict,
        entry: Dict,
        decision: IdentityDecision,
        match_result: Optional[Dict],
    ) -> None:
        if (
            decision.disposition != "repaired"
            or entry.get("scoreable_identity") is not True
            or not isinstance(match_result, dict)
        ):
            return
        active_row.update(
            {
                "canonical_id": entry.get("canonical_id"),
                "canonical_source_db": "ingredient_quality_map",
                "standardName": entry.get("standard_name"),
                "form_id": entry.get("form_id"),
                "matched_form": entry.get("matched_form"),
                "source_label_key": entry.get("source_label_key"),
                "source_label_name": entry.get("source_label_name"),
                "source_label_form": entry.get("source_label_form"),
                "label_display_name": entry.get("label_display_name"),
                "label_display_form": entry.get("label_display_form"),
                "identity_disposition": entry.get("identity_disposition"),
                "canonical_id_before": entry.get("canonical_id_before"),
                "canonical_id_after": entry.get("canonical_id_after"),
                "identity_evidence": entry.get("identity_evidence"),
                "identity_resolution_rationale": entry.get(
                    "identity_resolution_rationale"
                ),
                "scoreable_identity": entry.get("scoreable_identity"),
            }
        )

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

        # Track classification results. Contract semantics:
        # - ingredients_scorable: scoring/taxonomy inputs only.
        # - ingredients_recognized_non_scorable: recognized transparency rows.
        # - ingredients_skipped: every evaluated row excluded from scoring.
        ingredients_scorable = []
        ingredients_recognized_non_scorable = []
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
        product_activity_text = self._get_all_product_text(product)
        for source_ingredient in active_ingredients:
            ingredient = source_ingredient
            if product_activity_text:
                ingredient = dict(ingredient)
                ingredient.setdefault("_product_activity_text", product_activity_text)
            # Use branded_token_extracted for matching if present AND it differs from name.
            # When branded_token_extracted == name the clean stage collapsed the full label
            # to just the brand prefix (e.g. "Albion" from "Albion Magnesium Bisglycinate Chelate").
            # In that case prefer raw_source_text so IQM alias matching can resolve the full form.
            # Otherwise prefer cleaned `name` to avoid carrying known text artifacts from raw label.
            _bte = ingredient.get('branded_token_extracted', '')
            _raw = ingredient.get('name', '')
            _raw_source = ingredient.get('raw_source_text') or _raw
            if _bte and _bte != _raw:
                ing_name = _bte
            elif _bte:
                ing_name = _raw_source
            else:
                ing_name = _raw or _raw_source
            std_name = ingredient.get('standardName', '') or ing_name
            if not _bte:
                _bte = self._product_context_branded_token_for_ingredient(
                    ingredient.get("_product_activity_text", ""),
                    ingredient,
                    ing_name,
                    std_name,
                ) or ""
            quantity = ingredient.get('quantity', 0)
            unit = ingredient.get('unit', '')
            hierarchy_type = ingredient.get('hierarchyType')
            pre_context_match_reason = self._product_context_iqm_match_reason(ingredient, ing_name, std_name)

            skip_reason = (
                self._cleaner_skip_reason(ingredient)
                or self._should_skip_from_scoring(
                    ingredient,
                    quality_map,
                    botanicals_db,
                )
            )
            if pre_context_match_reason:
                skip_reason = None
            # 2026-05-24: defense-in-depth. _should_skip_from_scoring already
            # short-circuits on context_override_applied at its top, but if
            # _cleaner_skip_reason or any future skip predicate fires for an
            # overridden row, the call-site bypass keeps the row on the
            # scoring path so the override consumer at line 2748+ can run.
            if ingredient.get("context_override_applied") is True:
                skip_reason = None

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
                skipped_entry = {
                    # LABEL NAME PRESERVATION:
                    "name": ing_name,  # Label-facing name
                    "raw_source_text": raw_source_text,  # Exact label text (provenance)
                    "standard_name": std_name,
                    # Identity_bioactivity_split: preserve cleaner-set canonical
                    # so _compute_delivers_markers can look up source-botanical
                    # marker contributions even on non-scorable rows.
                    "canonical_id": ingredient.get("canonical_id"),
                    "canonical_source_db": ingredient.get("canonical_source_db"),
                    # Sprint 1.1: preserve cleaner-side match method (UNII /
                    # alternateNames) so the downstream ledger emission can
                    # attribute correctly even on the skipped/recognized-
                    # non-scorable path.
                    "cleaner_match_method": ingredient.get("cleaner_match_method"),
                    "matched_form": None,
                    "matched_forms": [],
                    "extracted_forms": [],
                    "skip_reason": skip_reason,
                    "bio_score": None,
                    "natural": None,
                    "score": None,
                    "notes": None,
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
                    "recognition_source": (recognition_info or {}).get("recognition_source"),
                    "recognition_reason": (recognition_info or {}).get("recognition_reason"),
                    "recognition_type": (recognition_info or {}).get("recognition_type"),
                    "recognized_entry_id": (recognition_info or {}).get("matched_entry_id"),
                    "recognized_entry_name": (recognition_info or {}).get("matched_entry_name"),
                    "mapped": bool(recognition_info) or bool(is_excipient),
                    "mapped_identity": bool(recognition_info) or bool(is_excipient),
                    "scoreable_identity": False,
                    "role_classification": "inactive_non_scorable",
                    "identity_confidence": 1.0 if (recognition_info or is_excipient) else 0.0,
                    "identity_decision_reason": skip_reason,
                    "safety_hits": [],
                    "certificates": [],
                    "source_section": ingredient.get("source_section") or "active",
                    "raw_source_path": ingredient.get("raw_source_path", "activeIngredients"),
                    "cleaner_row_role": ingredient.get("cleaner_row_role") or skip_reason,
                    "score_eligible_by_cleaner": bool(ingredient.get("score_eligible_by_cleaner", False)),
                    "score_exclusion_reason": ingredient.get("score_exclusion_reason") or skip_reason,
                    "dose_class": ingredient.get("dose_class"),
                    "raw_taxonomy": ingredient.get("raw_taxonomy"),
                    "hierarchyType": hierarchy_type,
                    "form_extraction_used": False,
                    "is_dual_form": False,
                    "original_label": raw_source_text,
                    "unmapped_forms": [],
                    "aggregation_method": None,
                    "final_form_bio_score": None,
                    "additional_forms": [],
                    "form_source": None,
                    "form_id": None,
                    "form_unmapped": False,
                    "matched_alias": None,
                    "matched_target": None,
                    "match_tier": None,
                    "fallback_class": "clinical_fail_safe",
                    "fallback_reason": skip_reason,
                    "normalized_key": ingredient.get("normalized_key") or norm_module.make_normalized_key(raw_source_text),
                }
                if isinstance(ingredient.get("dose_data_quality"), dict):
                    skipped_entry["dose_data_quality"] = dict(ingredient["dose_data_quality"])
                self._mark_cleaner_contract_fallback(
                    skipped_entry,
                    self._missing_cleaner_contract_fields(ingredient),
                )
                identity_decision, identity_match, taxonomy_coherent = (
                    self._resolve_iqd_identity(
                        ingredient,
                        None,
                        quality_map,
                        allow_unscoreable_taxonomy_only=True,
                    )
                )
                self._stamp_iqd_identity(
                    skipped_entry,
                    ingredient,
                    identity_decision,
                    identity_match,
                    taxonomy_coherent,
                )
                if (
                    recognition_info
                    and recognition_info.get("recognition_source")
                    == "banned_recalled_ingredients"
                    and ingredient.get("canonical_id")
                    and ingredient.get("canonical_source_db")
                    not in {"banned_recalled_ingredients", "harmful_additives"}
                ):
                    # Safety classification is orthogonal to identity. Retain
                    # the cleaner's non-safety canonical while carrying the
                    # safety-table identity in its own field.
                    skipped_entry["canonical_id"] = ingredient.get("canonical_id")
                    skipped_entry["canonical_source_db"] = ingredient.get(
                        "canonical_source_db"
                    )
                    skipped_entry["safety_identity_id"] = recognition_info.get(
                        "matched_entry_id"
                    )
                    skipped_entry["mapped_identity"] = True
                    skipped_entry["scoreable_identity"] = False
                    skipped_entry["identity_decision_reason"] = (
                        "safety_identity_excluded_from_scoring"
                    )
                ingredients_skipped.append(skipped_entry)
                all_quality_data.append(skipped_entry)
                if recognition_info:
                    skipped_entry["recognized_non_scorable"] = True
                    skipped_entry["skip_reason"] = SKIP_REASON_RECOGNIZED_NON_SCORABLE
                    self._append_unique_iqd_row(ingredients_recognized_non_scorable, skipped_entry)
                # DO NOT track as unmapped - these are intentionally not scored
                continue

            # Scorable ingredient - try to match against quality map
            # Pass cleaned forms[] to enable form-aware matching (P0 form-loss fix)
            ingredient_forms = ingredient.get('forms') or []
            # Phase 3: forward the cleaner's IQM canonical_id as a hard
            # constraint so text-inferred cross-parent matches cannot win.
            # Only passed when the cleaner resolved via IQM — botanical /
            # other / harmful canonicals route through their own DBs.
            _cleaner_iqm_cid = (
                ingredient.get('canonical_id')
                if ingredient.get('canonical_source_db') == 'ingredient_quality_map'
                else None
            )
            # 2026-05-24: BEFORE normal IQM matching, check for a
            # reviewer-signed cleaner-stamped context override. If present
            # AND the (parent + preferred form) resolve in quality_map, use
            # the synthetic match_result that forces the exact form choice
            # (the form text in the row itself cannot disambiguate, e.g.
            # BioCell hydrolyzed vs UC-II undenatured for the row
            # "Chicken Sternum Collagen extract"). Fail-safe on form-key
            # miss falls through to normal matching with a logged warning;
            # never silently scores with the unspecified form. Spec:
            # reports/not_scored_triage/cleaner_side_context_routing_spec.md
            match_result = self._apply_context_canonical_override_match(
                ingredient, quality_map
            )
            if match_result is None:
                match_result = self._match_quality_map(
                    ing_name, std_name, quality_map, cleaned_forms=ingredient_forms,
                    branded_token=_bte, cleaner_canonical_id=_cleaner_iqm_cid,
                )
            context_match_reason = pre_context_match_reason
            if context_match_reason == "kelp_fucoidan_marker_context":
                context_match = self._match_quality_map(
                    "Fucoidan extract",
                    "Fucoidan",
                    quality_map,
                    cleaned_forms=ingredient_forms,
                )
                if context_match:
                    match_result = context_match
            blocked_botanical_marker_match = (
                self._is_blocked_botanical_source_marker_match(
                    ingredient, match_result
                )
            )
            if blocked_botanical_marker_match:
                match_result = None
                context_match_reason = None
            identity_decision, match_result, taxonomy_coherent = (
                self._resolve_iqd_identity(
                    ingredient,
                    match_result,
                    quality_map,
                    authoritative_context_override=(
                        context_match_reason == "kelp_fucoidan_marker_context"
                        and isinstance(match_result, dict)
                    ),
                )
            )
            quality_entry = self._build_quality_entry(
                ingredient, match_result, hierarchy_type, source_section="active"
            )
            self._stamp_iqd_identity(
                quality_entry,
                ingredient,
                identity_decision,
                match_result,
                taxonomy_coherent,
            )
            if blocked_botanical_marker_match:
                # The botanical remains the lineage authority, but a marker
                # form (for example Green Tea / Caffeine) cannot be promoted
                # into either a marker score or a repaired extract score.
                source_id = ingredient.get("canonical_id")
                quality_entry.update({
                    "canonical_id": source_id,
                    "canonical_id_after": source_id,
                    "canonical_source_db": ingredient.get("canonical_source_db"),
                    "scoreable_identity": False,
                    "recognized_non_scorable": True,
                    "mapped": True,
                    "mapped_identity": True,
                    "role_classification": "recognized_non_scorable",
                    "recognition_source": ingredient.get("canonical_source_db"),
                    "recognition_type": "botanical_marker_lineage",
                    "recognition_reason": "botanical_marker_is_secondary_metadata",
                    "identity_decision_reason": "botanical_marker_is_secondary_metadata",
                })
                self._tag_fallback_decision(
                    quality_entry,
                    "clinical_fail_safe",
                    "botanical_marker_is_secondary_metadata",
                )
                recognized_non_scorable_count += 1
                self._route_non_scorable_iqd_row(
                    quality_entry,
                    ingredients_skipped,
                    ingredients_recognized_non_scorable,
                    skip_reason=SKIP_REASON_RECOGNIZED_NON_SCORABLE,
                )
                all_quality_data.append(quality_entry)
                continue
            self._project_repaired_identity_to_active_row(
                source_ingredient,
                quality_entry,
                identity_decision,
                match_result,
            )
            if context_match_reason and match_result:
                quality_entry["identity_decision_reason"] = "product_label_marker_context_match"
                self._tag_fallback_decision(quality_entry, "clinical_fail_safe", context_match_reason)
            # 2026-05-24: when the match came from a curated context override
            # (BioCell hydrolyzed / DAO / barley_grass disambiguation), tag
            # the quality_entry with the override-specific identity reason
            # AND the override id so downstream audits can reconcile every
            # fire against the JSON file. The override id is the slug from
            # product_context_canonical_overrides.json.
            if (
                isinstance(match_result, dict)
                and match_result.get("context_override_applied") is True
            ):
                quality_entry["identity_decision_reason"] = (
                    "curated_context_canonical_override"
                )
                quality_entry["context_override_id"] = match_result.get(
                    "context_override_id"
                )
                quality_entry["context_override_applied"] = True
                quality_entry["cleaner_canonical_id_pre_override"] = (
                    ingredient.get("cleaner_canonical_id_pre_override")
                )
            self._preserve_cleaner_safety_canonical(ingredient, quality_entry)
            self._preserve_cleaner_botanical_canonical(ingredient, quality_entry)
            is_quality_match = bool(
                match_result
                and isinstance(match_result, dict)
                and match_result.get("match_status") != "FORM_UNMAPPED"
                and quality_entry.get("scoreable_identity") is True
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
                # D2.7.1 (medical-grade): when the cleaner resolved this row to
                # proprietary_blends.json (Velositol, MyoTor, Tesnor, Metabolaid,
                # etc. — branded matrices with no individual-component evidence),
                # treat it as RECOGNIZED-BUT-NOT-SCORABLE rather than unmapped.
                # The blend-transparency penalty (B5) still tracks it; but it
                # no longer blocks the coverage gate on products that happen to
                # contain one exotic branded blend alongside otherwise-scorable
                # vitamins/minerals. Matches the existing policy for
                # oils/fibers/excipients in other_ingredients.
                _canonical_src = ingredient.get('canonical_source_db')
                _canonical_id = ingredient.get('canonical_id')
                if _canonical_src == 'proprietary_blends' and _canonical_id:
                    quality_entry['recognized_non_scorable'] = True
                    quality_entry['recognition_source'] = 'proprietary_blends'
                    quality_entry['recognition_reason'] = 'proprietary_blend_member'
                    quality_entry['recognition_type'] = 'blend_class'
                    quality_entry['matched_entry_id'] = _canonical_id
                    quality_entry['matched_entry_name'] = std_name or ing_name
                    quality_entry['mapped'] = True
                    quality_entry['mapped_identity'] = True
                    quality_entry['scoreable_identity'] = False
                    quality_entry['role_classification'] = 'recognized_non_scorable'
                    quality_entry['identity_confidence'] = 1.0
                    quality_entry['identity_decision_reason'] = 'proprietary_blend_member'
                    self._tag_fallback_decision(quality_entry, 'clinical_fail_safe', 'proprietary_blend_member')
                    self._restamp_recognized_non_scorable_identity(
                        quality_entry,
                        ingredient,
                        match_result,
                        quality_map,
                    )
                    recognized_non_scorable_count += 1
                    self._route_non_scorable_iqd_row(
                        quality_entry,
                        ingredients_skipped,
                        ingredients_recognized_non_scorable,
                        skip_reason=SKIP_REASON_RECOGNIZED_NON_SCORABLE,
                    )
                    all_quality_data.append(quality_entry)
                    continue

                # D2.10 (medical-grade): source-descriptor child rows. DSLD
                # sometimes emits a separate row whose ingredientName starts
                # with "from " to describe the source of the preceding actual
                # active (e.g. GNC Beyond Raw Re-Comp: a real "EGCG" row
                # followed by a "from Green Tea Leaf Extract" row). These are
                # NOT distinct actives — they annotate provenance of the row
                # above (the quantity may be nonzero and represents the
                # parent-extract amount that contains the upstream active's
                # stated dose). Route through recognized_non_scorable so the
                # coverage gate doesn't punish the product for a provenance
                # marker. Rationale: same as the proprietary-blend policy
                # above — the row is recognized as non-scorable metadata,
                # not unmapped. Safety: we only reach this branch when the
                # row already failed canonical/form quality-match, so
                # re-tagging as recognized_non_scorable has no effect on
                # A1/A2 scoring — it only exempts this provenance marker
                # from the coverage-gate denominator.
                _raw_text_lower = (ingredient.get('raw_source_text') or ing_name or '').strip().lower()
                if _raw_text_lower.startswith('from '):
                    quality_entry['recognized_non_scorable'] = True
                    quality_entry['recognition_source'] = 'dsld_schema'
                    quality_entry['recognition_reason'] = 'source_descriptor_child_row'
                    quality_entry['recognition_type'] = 'provenance_annotation'
                    quality_entry['matched_entry_id'] = None
                    quality_entry['matched_entry_name'] = ing_name
                    quality_entry['mapped'] = True
                    quality_entry['mapped_identity'] = True
                    quality_entry['scoreable_identity'] = False
                    quality_entry['role_classification'] = 'recognized_non_scorable'
                    quality_entry['identity_confidence'] = 1.0
                    quality_entry['identity_decision_reason'] = 'source_descriptor_child_row'
                    self._tag_fallback_decision(quality_entry, 'clinical_fail_safe', 'source_descriptor_child_row')
                    self._restamp_recognized_non_scorable_identity(
                        quality_entry,
                        ingredient,
                        match_result,
                        quality_map,
                    )
                    recognized_non_scorable_count += 1
                    self._route_non_scorable_iqd_row(
                        quality_entry,
                        ingredients_skipped,
                        ingredients_recognized_non_scorable,
                        skip_reason=SKIP_REASON_RECOGNIZED_NON_SCORABLE,
                    )
                    all_quality_data.append(quality_entry)
                    continue

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
                    self._tag_fallback_decision(
                        quality_entry,
                        'clinical_fail_safe',
                        recognition.get('recognition_reason') or 'recognized_non_scorable',
                    )
                    # Track for coverage metrics (separate from unmapped)
                    recognized_non_scorable_count += 1
                else:
                    if self._iqd_row_has_dose_evidence(quality_entry):
                        # Truly unmapped eligible row - track for coverage gates,
                        # but do not put it in the scoring/taxonomy input list.
                        unmapped_scorable_count += 1
                        legacy_unmapped_count += 1
                        self._track_unmapped(ing_name, 'active')
                    else:
                        quality_entry['score_exclusion_reason'] = 'no_dose_evidence'

            if quality_entry.get('recognized_non_scorable') is True:
                self._restamp_recognized_non_scorable_identity(
                    quality_entry,
                    ingredient,
                    match_result,
                    quality_map,
                )

            if self._is_contract_scorable_iqd_row(quality_entry):
                ingredients_scorable.append(quality_entry)
            else:
                if quality_entry.get('scoreable_identity') is True and not self._iqd_row_has_dose_evidence(quality_entry):
                    quality_entry['recognized_non_scorable'] = True
                    quality_entry['scoreable_identity'] = False
                    quality_entry['role_classification'] = 'recognized_non_scorable'
                    quality_entry['recognition_source'] = quality_entry.get('recognition_source') or 'iqd_contract'
                    quality_entry['recognition_type'] = quality_entry.get('recognition_type') or 'no_dose'
                    quality_entry['recognition_reason'] = quality_entry.get('recognition_reason') or 'no_dose_evidence'
                    quality_entry['identity_decision_reason'] = 'no_dose_evidence'
                    self._tag_fallback_decision(quality_entry, 'clinical_fail_safe', 'no_dose_evidence')
                    recognized_non_scorable_count += 1
                self._route_non_scorable_iqd_row(
                    quality_entry,
                    ingredients_skipped,
                    ingredients_recognized_non_scorable,
                    skip_reason=(
                        SKIP_REASON_RECOGNIZED_NON_SCORABLE
                        if quality_entry.get('recognized_non_scorable')
                        else quality_entry.get('score_exclusion_reason') or quality_entry.get('identity_decision_reason') or 'not_scorable'
                    ),
                )
            all_quality_data.append(quality_entry)

        # =================================================================
        # PASS 2: Rescue therapeutic actives from inactiveIngredients
        # =================================================================
        for ingredient in inactive_ingredients:
            # Same branded_token_extracted logic as Pass 1: prefer raw_source_text when
            # the token was collapsed to just the brand prefix (e.g., "Albion").
            _bte = ingredient.get('branded_token_extracted', '')
            _raw = ingredient.get('name', '')
            _raw_source = ingredient.get('raw_source_text') or _raw
            if _bte and _bte != _raw:
                ing_name = _bte
            elif _bte:
                ing_name = _raw_source
            else:
                ing_name = _raw or _raw_source
            std_name = ingredient.get('standardName', '') or ing_name
            if not _bte:
                _bte = self._product_context_branded_token_for_ingredient(
                    product_activity_text,
                    ingredient,
                    ing_name,
                    std_name,
                ) or ""
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
                # Phase 3: propagate cleaner IQM canonical_id (see Pass 1 note above).
                _cleaner_iqm_cid = (
                    ingredient.get('canonical_id')
                    if ingredient.get('canonical_source_db') == 'ingredient_quality_map'
                    else None
                )
                match_result = self._match_quality_map(
                    ing_name, std_name, quality_map, cleaned_forms=ingredient_forms,
                    branded_token=_bte, cleaner_canonical_id=_cleaner_iqm_cid,
                )
                if self._is_blocked_botanical_source_marker_match(ingredient, match_result):
                    match_result = None
                identity_decision, match_result, taxonomy_coherent = (
                    self._resolve_iqd_identity(ingredient, match_result, quality_map)
                )
                quality_entry = self._build_quality_entry(
                    ingredient, match_result, hierarchy_type,
                    source_section="inactive_promoted",
                    promotion_reason=promotion_reason,
                    promotion_confidence=promotion_confidence,
                    dose_present=dose_present
                )
                self._stamp_iqd_identity(
                    quality_entry,
                    ingredient,
                    identity_decision,
                    match_result,
                    taxonomy_coherent,
                )
                self._preserve_cleaner_safety_canonical(ingredient, quality_entry)
                self._preserve_cleaner_botanical_canonical(ingredient, quality_entry)
                is_quality_match = bool(
                    match_result
                    and isinstance(match_result, dict)
                    and match_result.get("match_status") != "FORM_UNMAPPED"
                    and quality_entry.get("scoreable_identity") is True
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
                        self._tag_fallback_decision(
                            quality_entry,
                            'clinical_fail_safe',
                            recognition.get('recognition_reason') or 'recognized_non_scorable',
                        )
                        recognized_non_scorable_count += 1
                    else:
                        if self._iqd_row_has_dose_evidence(quality_entry):
                            unmapped_scorable_count += 1
                            legacy_unmapped_count += 1
                            self._track_unmapped(ing_name, 'active_promoted')
                        else:
                            quality_entry['score_exclusion_reason'] = 'no_dose_evidence'

                if quality_entry.get('recognized_non_scorable') is True:
                    self._restamp_recognized_non_scorable_identity(
                        quality_entry,
                        ingredient,
                        match_result,
                        quality_map,
                    )

                if self._is_contract_scorable_iqd_row(quality_entry):
                    ingredients_scorable.append(quality_entry)
                else:
                    if quality_entry.get('scoreable_identity') is True and not self._iqd_row_has_dose_evidence(quality_entry):
                        quality_entry['recognized_non_scorable'] = True
                        quality_entry['scoreable_identity'] = False
                        quality_entry['role_classification'] = 'recognized_non_scorable'
                        quality_entry['recognition_source'] = quality_entry.get('recognition_source') or 'iqd_contract'
                        quality_entry['recognition_type'] = quality_entry.get('recognition_type') or 'no_dose'
                        quality_entry['recognition_reason'] = quality_entry.get('recognition_reason') or 'no_dose_evidence'
                        quality_entry['identity_decision_reason'] = 'no_dose_evidence'
                        self._tag_fallback_decision(quality_entry, 'clinical_fail_safe', 'no_dose_evidence')
                        recognized_non_scorable_count += 1
                    self._route_non_scorable_iqd_row(
                        quality_entry,
                        ingredients_skipped,
                        ingredients_recognized_non_scorable,
                        skip_reason=(
                            SKIP_REASON_RECOGNIZED_NON_SCORABLE
                            if quality_entry.get('recognized_non_scorable')
                            else quality_entry.get('score_exclusion_reason') or quality_entry.get('identity_decision_reason') or 'not_scorable'
                        ),
                    )
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
        # Mark dual-declaration compound rows ("Magnesium Glycinate" 400 mg
        # restating the bare "Magnesium" 60 mg elemental row) so scoring's
        # single-ingredient detection and floors see one active, not two.
        mark_compound_duplicate_rows(ingredients_scorable)

        # =================================================================
        # SPRINT E1.23 — ABSORPTION-ENHANCER SUB-THRESHOLD DEMOTION
        # =================================================================
        # Demote bioavailability aids (piperine ≤10 mg, etc.) from the
        # scorable list so they don't (a) drag down the A1 form-score
        # average and (b) bump a single-nutrient product into the
        # 'targeted' supp_type bucket (which would make it miss A6).
        #
        # Per-enhancer thresholds come from absorption_enhancers.json
        # (v5.1.0 adds optional ``non_scorable_when_sub_threshold`` field).
        # Only enhancers with no independent nutritional value are tagged
        # — never Vitamin C, Vitamin D, MK7, amino acids, etc.
        #
        # The ingredient stays in product["activeIngredients"] so synergy
        # cluster matching (e.g. curcumin_absorption fires on curcumin +
        # piperine pair) and interaction-rule analysis (piperine is a real
        # CYP modulator) remain intact.
        ingredients_scorable, all_quality_data, demoted_enhancers = (
            self._apply_absorption_enhancer_demotion(
                ingredients_scorable, all_quality_data, ingredients_skipped
            )
        )
        for row in all_quality_data:
            if isinstance(row, dict) and row.get('role_classification') == 'recognized_non_scorable':
                self._route_non_scorable_iqd_row(
                    row,
                    ingredients_skipped,
                    ingredients_recognized_non_scorable,
                    skip_reason=SKIP_REASON_RECOGNIZED_NON_SCORABLE,
                )

        # =================================================================
        # CURCUMIN C3 COMPLEX + BIOPERINE PAIRING UPGRADE
        # =================================================================
        # The IQM form matcher picks the FIRST form-name match by string
        # equality, so C3 Complex + Bioperine products land on
        # 'curcumin c3 complex' (bio_score=6) instead of the clinically
        # accurate 'curcumin c3 complex with bioperine' (bio_score=7).
        # When the product also contains a piperine/Bioperine row (active
        # scorable or recognized non-scorable absorption enhancer), upgrade
        # the curcumin row to the with-bioperine variant.
        self._apply_curcumin_c3_bioperine_pairing_upgrade(all_quality_data)

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

        # Scorable from pass 1 = active-source rows that remain in the strict
        # scorable contract. Promoted inactive rows and recognized transparency
        # rows are counted through their own buckets.
        scorable_from_pass1 = sum(
            1
            for row in ingredients_scorable
            if isinstance(row, dict) and row.get("source_section") == "active"
        )

        # Invariant check: all active records must end up classified
        # scorable_from_pass1 + skipped should equal total_records_seen
        unevaluated_records = total_records_seen - (scorable_from_pass1 + total_skipped)

        # Total evaluated = scorable + skipped (includes promoted in scorable)
        total_ingredients_evaluated = total_scorable + total_skipped

        # =================================================================
        # IDENTITY vs BIOACTIVITY SPLIT — attach delivers_markers per ingredient
        # =================================================================
        # For ingredients whose primary canonical_id is a source botanical with
        # marker contributions declared in botanical_marker_contributions.json,
        # compute and attach the marker contribution list. Empty for marker-
        # canonical ingredients or botanicals without contribution mappings.
        for ing_list in (all_quality_data, ingredients_scorable, ingredients_recognized_non_scorable, ingredients_skipped):
            for ing in ing_list or []:
                if not isinstance(ing, dict):
                    continue
                try:
                    markers = self._compute_delivers_markers(ing)
                except Exception as exc:
                    self.logger.warning(
                        "delivers_markers computation failed for canonical_id=%s: %s",
                        ing.get("canonical_id"), exc,
                    )
                    markers = []
                ing["delivers_markers"] = markers

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
            "ingredients_recognized_non_scorable": ingredients_recognized_non_scorable,
            "ingredients_skipped": ingredients_skipped,
            "unmapped_scorable_count": unmapped_scorable_count,
            "recognized_non_scorable_count": len(ingredients_recognized_non_scorable),
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
            # Sprint E1.23 — ingredients demoted from scorable because they
            # are sub-threshold absorption enhancers (e.g. BioPerine 5 mg).
            # Carried for audit; Flutter can surface them as info chips.
            "demoted_absorption_enhancers": demoted_enhancers,
        }

    def _product_context_iqm_match_reason(self, ingredient: Dict, ing_name: str, std_name: str) -> Optional[str]:
        """Narrow product-label marker disambiguation for generic source rows."""
        cleaner_cid = str(ingredient.get("canonical_id") or "").lower()
        cleaner_src = str(ingredient.get("canonical_source_db") or "").lower()
        raw_taxonomy = ingredient.get("raw_taxonomy") if isinstance(ingredient.get("raw_taxonomy"), dict) else {}
        forms = ingredient.get("forms") or raw_taxonomy.get("forms") or []
        forms_text = " ".join(
            str(form.get(key) or "")
            for form in forms
            if isinstance(form, dict)
            for key in ("name", "prefix", "percent", "ingredientGroup")
        )
        source_text = " ".join(
            str(value or "")
            for value in (
                ing_name,
                std_name,
                ingredient.get("raw_source_text"),
                ingredient.get("ingredientGroup"),
                raw_taxonomy.get("ingredientGroup"),
                ingredient.get("notes"),
                forms_text,
            )
        ).lower()
        product_text = str(ingredient.get("_product_activity_text") or "").lower()
        full_text = f"{source_text} {product_text}"
        is_kelp_source = (
            cleaner_src == "botanical_ingredients"
            and cleaner_cid in {"kelp_powder", "kombu", "wakame", "laminaria_digitata", "saccharina_latissima"}
        ) or any(term in source_text for term in ("kelp", "laminaria", "seaweed", "kombu", "wakame"))
        has_fucoidan_label_claim = "fucoidan" in product_text
        has_marker_percent = bool(re.search(r"\b70\s*%", full_text)) or "standardized to 70" in full_text
        if is_kelp_source and has_fucoidan_label_claim and has_marker_percent:
            return "kelp_fucoidan_marker_context"
        return None

    # -------------------------------------------------------------------------
    # Sprint E1.23 — Absorption-enhancer sub-threshold demotion
    # -------------------------------------------------------------------------
    def _apply_absorption_enhancer_demotion(
        self,
        ingredients_scorable: List[Dict],
        all_quality_data: List[Dict],
        ingredients_skipped: List[Dict],
    ) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """Demote absorption enhancers from the scorable list when their dose
        is at or below the enhancer's ``non_scorable_when_sub_threshold``.

        Returns: (filtered_scorable, updated_all_quality_data, demoted_list).

        Each demoted entry carries:
          - role_classification = "recognized_non_scorable"
          - score_included = False
          - demotion_reason = "absorption_enhancer_sub_threshold"
          - demotion_ref = "<enhancer_id> (@ <threshold_mg> mg)"

        The ingredient is NOT removed from product["activeIngredients"] —
        only from the scorable-count inputs. Synergy-cluster matching and
        drug-interaction analysis still see it.
        """
        enhancers_db = self.databases.get('absorption_enhancers', {}) or {}
        enhancers = enhancers_db.get('absorption_enhancers', []) if isinstance(enhancers_db, dict) else []

        # Build a normalized name -> (enhancer_id, threshold_mg, rationale)
        # lookup for enhancers that opt-in to sub-threshold demotion.
        lookup: Dict[str, Tuple[str, float, str]] = {}
        for entry in enhancers:
            if not isinstance(entry, dict):
                continue
            rule = entry.get('non_scorable_when_sub_threshold')
            if not isinstance(rule, dict):
                continue
            try:
                threshold_mg = float(rule.get('threshold_mg'))
            except (TypeError, ValueError):
                continue
            eid = entry.get('id', 'ENHANCER')
            rationale = rule.get('rationale', '')
            std_name = entry.get('standard_name', '')
            aliases = entry.get('aliases', []) or []
            terms = [std_name] + list(aliases)
            for term in terms:
                if isinstance(term, str) and term.strip():
                    lookup[self._normalize_text(term)] = (eid, threshold_mg, rationale)

        if not lookup:
            return ingredients_scorable, all_quality_data, []

        # mg-equivalent for dose comparison. Enhancers use mg only.
        def _dose_mg(row: Dict) -> Optional[float]:
            qty = row.get('quantity')
            unit = (row.get('unit') or '').strip().lower()
            if qty is None or unit == '':
                return None
            try:
                qty_f = float(qty)
            except (TypeError, ValueError):
                return None
            if unit in {'mg', 'milligram', 'milligrams'}:
                return qty_f
            if unit in {'g', 'gram', 'grams'}:
                return qty_f * 1000.0
            if unit in {'mcg', 'microgram', 'micrograms', 'ug', 'µg'}:
                return qty_f / 1000.0
            return None  # unsupported unit — be conservative, keep scorable

        def _match_enhancer(row: Dict) -> Optional[Tuple[str, float, str]]:
            for key in ('standard_name', 'name', 'raw_source_text'):
                v = row.get(key)
                if not isinstance(v, str) or not v.strip():
                    continue
                hit = lookup.get(self._normalize_text(v))
                if hit:
                    return hit
            return None

        demoted: List[Dict] = []
        filtered_scorable: List[Dict] = []
        for row in ingredients_scorable:
            hit = _match_enhancer(row)
            if not hit:
                filtered_scorable.append(row)
                continue
            eid, threshold_mg, rationale = hit
            dose = _dose_mg(row)
            if dose is None or dose > threshold_mg:
                # Above threshold OR unknown unit — keep scorable.
                filtered_scorable.append(row)
                continue

            # Demote. Mutate in place so all_quality_data sees it too.
            row['role_classification'] = 'recognized_non_scorable'
            row['score_included'] = False
            row['demotion_reason'] = 'absorption_enhancer_sub_threshold'
            row['demotion_ref'] = f"{eid} (@ \u2264 {threshold_mg} mg)"
            row['demotion_rationale'] = rationale
            row['recognized_non_scorable'] = True
            row['recognition_source'] = row.get('recognition_source') or 'absorption_enhancers'
            row['recognition_type'] = row.get('recognition_type') or 'threshold_demotion'
            row['recognition_reason'] = row.get('recognition_reason') or 'absorption_enhancer_sub_threshold'
            row['fallback_class'] = 'clinical_fail_safe'
            row['fallback_reason'] = 'absorption_enhancer_sub_threshold'
            demoted.append({
                'name': row.get('name'),
                'standard_name': row.get('standard_name'),
                'quantity': row.get('quantity'),
                'unit': row.get('unit'),
                'enhancer_id': eid,
                'threshold_mg': threshold_mg,
                'rationale': rationale,
            })

        # all_quality_data shares row refs with ingredients_scorable (same dicts)
        # so mutations above propagate. Return the updated structures.
        return filtered_scorable, all_quality_data, demoted

    # -------------------------------------------------------------------------
    # Curcumin C3 Complex + Bioperine pairing upgrade (Wave 6.Z, 2026-05-25)
    # -------------------------------------------------------------------------
    def _apply_curcumin_c3_bioperine_pairing_upgrade(
        self,
        all_quality_data: List[Dict],
    ) -> int:
        """Upgrade `curcumin c3 complex` matches to the with-bioperine variant
        when the product also discloses a piperine/Bioperine row.

        IQM has two adjacent forms under parent `curcumin`:
          - `curcumin c3 complex with bioperine` (bio_score=7)
          - `curcumin c3 complex`                (bio_score=6)

        The matcher selects the FIRST form-name match by string equality so
        C3 Complex + Bioperine products land on the unpaired form. This
        post-pass detects the pairing — any row with canonical_id='piperine'
        in the same product (scorable or absorption-enhancer demoted) —
        and rewrites matched_form/form_id/bio_score/score and the IQM-derived
        absorption/notes fields to the with-bioperine variant.

        Returns the number of rows upgraded (0 if no pairing signal or no
        C3 Complex match in this product).
        """
        TARGET_FORM_KEY = "curcumin c3 complex with bioperine"
        SOURCE_FORM_KEY = "curcumin c3 complex"

        has_piperine = any(
            isinstance(r, dict)
            and str(r.get("canonical_id") or "").strip().lower() == "piperine"
            for r in all_quality_data
        )
        if not has_piperine:
            return 0

        # Look up the upgrade target from IQM at runtime so this pass mirrors
        # whatever the data file currently asserts (notes, absorption_structured).
        iqm = self.databases.get("ingredient_quality_map") or {}
        curcumin_entry = iqm.get("curcumin") if isinstance(iqm, dict) else None
        forms = (
            curcumin_entry.get("forms")
            if isinstance(curcumin_entry, dict)
            else None
        )
        target_form = forms.get(TARGET_FORM_KEY) if isinstance(forms, dict) else None
        if not isinstance(target_form, dict):
            # Data shape unexpected; do not upgrade silently.
            return 0

        new_bio_score = target_form.get("bio_score", 7)
        new_absorption = target_form.get("absorption")
        new_notes = target_form.get("notes")
        new_absorption_structured = target_form.get("absorption_structured")
        new_dosage_importance = target_form.get("dosage_importance")

        upgraded = 0
        for row in all_quality_data:
            if not isinstance(row, dict):
                continue
            if str(row.get("canonical_id") or "").strip().lower() != "curcumin":
                continue
            current_form = str(row.get("form_id") or row.get("matched_form") or "").strip().lower()
            if current_form != SOURCE_FORM_KEY:
                continue

            row["matched_form"] = TARGET_FORM_KEY
            row["form_id"] = TARGET_FORM_KEY
            row["bio_score"] = new_bio_score
            # v3.6.0 sourcing-neutral contract: score mirrors bio_score.
            row["score"] = new_bio_score
            if new_absorption is not None:
                row["absorption"] = new_absorption
            if new_notes is not None:
                row["notes"] = new_notes
            if new_absorption_structured is not None:
                row["absorption_structured"] = new_absorption_structured
            if new_dosage_importance is not None:
                row["dosage_importance"] = new_dosage_importance
            row["pairing_upgrade_applied"] = "curcumin_c3_with_bioperine"
            upgraded += 1

        return upgraded

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

    _ENZYME_ACTIVITY_UNITS = frozenset({
        "spu", "hut", "fcc", "galu", "su", "du", "alu", "fip", "sapu", "cu", "fu"
    })
    _ENZYME_ACTIVITY_RE = re.compile(
        r"\b(\d[\d,]*(?:\.\d+)?)\s*(SAPU|SPU|HUT|FCC|GALU|ALU|FIP|DU|SU|CU|FU)\b",
        re.IGNORECASE,
    )

    def _extract_enzyme_activity_dose(self, ingredient: Dict) -> Tuple[Optional[float], Optional[str]]:
        """Extract enzyme activity dose from unit fields or raw label text."""
        quantity = ingredient.get("quantity")
        unit = self._normalize_unit_for_signal(ingredient.get("unit"))
        if unit in self._ENZYME_ACTIVITY_UNITS:
            try:
                qty = float(str(quantity).replace(",", ""))
                if qty > 0:
                    return qty, unit.upper()
            except (TypeError, ValueError):
                pass

        identity_text = " ".join(
            str(ingredient.get(key) or "").lower()
            for key in (
                "name", "standardName", "raw_source_text", "category",
                "ingredientGroup", "canonical_id"
            )
        )
        if not any(
            token in identity_text
            for token in (
                "enzyme", "serrapeptase", "serratiopeptidase", "nattokinase",
                "protease", "amylase", "lipase", "lactase", "cellulase",
                "bromelain", "papain"
            )
        ):
            return None, None

        text_parts = [
            ingredient.get("name"),
            ingredient.get("standardName"),
            ingredient.get("raw_source_text"),
            ingredient.get("notes"),
            ingredient.get("_product_activity_text"),
        ]
        text = " ".join(str(part) for part in text_parts if part)
        match = self._ENZYME_ACTIVITY_RE.search(text)
        if not match:
            return None, None
        try:
            return float(match.group(1).replace(",", "")), match.group(2).upper()
        except ValueError:
            return None, None

    _IQD_DOSE_EVIDENCE_CLASSES = frozenset({
        "therapeutic_mass",
        "enzyme_activity",
        "probiotic_cfu",
        "percent_dv_only",
    })
    _CLEANER_CONTRACT_FIELDS = frozenset({
        "source_section",
        "raw_source_path",
        "cleaner_row_role",
        "score_eligible_by_cleaner",
        "score_exclusion_reason",
        "dose_class",
        "raw_taxonomy",
    })

    @staticmethod
    def _append_unique_iqd_row(rows: List[Dict], row: Dict) -> None:
        if not any(existing is row for existing in rows):
            rows.append(row)

    @staticmethod
    def _tag_fallback_decision(row: Dict, fallback_class: str, fallback_reason: str) -> None:
        if fallback_class:
            row["fallback_class"] = fallback_class
        if fallback_reason:
            row["fallback_reason"] = fallback_reason

    def _missing_cleaner_contract_fields(self, ingredient: Dict) -> List[str]:
        return sorted(field for field in self._CLEANER_CONTRACT_FIELDS if field not in ingredient)

    def _mark_cleaner_contract_fallback(self, row: Dict, missing_fields: List[str]) -> None:
        if not missing_fields:
            return
        row["cleaner_contract_fallback_used"] = True
        row["cleaner_contract_missing_fields"] = missing_fields
        row["fallback_class"] = "old_batch_compatibility"
        row["fallback_reason"] = "missing_cleaner_contract_fields"

    def _iqd_row_has_dose_evidence(self, row: Dict) -> bool:
        """Return True when an IQD row has usable dose evidence for scoring."""
        dose_class = str(row.get("dose_class") or "").strip()
        if dose_class in {"enzyme_activity", "probiotic_cfu"}:
            return True
        if dose_class == "percent_dv_only":
            try:
                return float(str(
                    row.get("percent_daily_value")
                    or row.get("daily_value_percent")
                    or row.get("percent_dv")
                    or 0
                ).replace(",", "")) > 0
            except (TypeError, ValueError):
                return False
        if row.get("activity_quantity") not in (None, "") and row.get("activity_unit"):
            try:
                return float(str(row.get("activity_quantity")).replace(",", "")) > 0
            except (TypeError, ValueError):
                return True
        if row.get("has_dose") is True:
            return True
        quantity = row.get("quantity")
        unit = self._normalize_unit_for_signal(row.get("unit"))
        if not unit or unit in PSEUDO_UNITS_INVALID:
            return False
        try:
            return float(str(quantity).replace(",", "")) > 0
        except (TypeError, ValueError):
            return False

    def _is_contract_scorable_iqd_row(self, row: Dict) -> bool:
        """Strict IQD contract for rows allowed to feed scoring/taxonomy."""
        return (
            row.get("score_eligible_by_cleaner") is True
            and row.get("scoreable_identity") is True
            and str(row.get("role_classification") or "") == "active_scorable"
            and self._iqd_row_has_dose_evidence(row)
        )

    def _route_non_scorable_iqd_row(
        self,
        row: Dict,
        ingredients_skipped: List[Dict],
        ingredients_recognized_non_scorable: List[Dict],
        *,
        skip_reason: str,
    ) -> None:
        """Route a non-scorable evaluated row into explicit transparency buckets."""
        row["scoreable_identity"] = False
        row.setdefault("score_included", False)
        row["skip_reason"] = skip_reason
        row.setdefault("score_exclusion_reason", skip_reason)
        row.setdefault("fallback_class", "clinical_fail_safe")
        row.setdefault("fallback_reason", skip_reason)
        row.setdefault("mapped", bool(row.get("mapped_identity") or row.get("canonical_id")))
        row.setdefault(
            "normalized_key",
            norm_module.make_normalized_key(row.get("raw_source_text") or row.get("name") or ""),
        )
        if row.get("recognized_non_scorable") or row.get("role_classification") == "recognized_non_scorable":
            row["recognized_non_scorable"] = True
            row["role_classification"] = "recognized_non_scorable"
            self._append_unique_iqd_row(ingredients_recognized_non_scorable, row)
        self._append_unique_iqd_row(ingredients_skipped, row)

    def _restamp_recognized_non_scorable_identity(
        self,
        row: Dict,
        ingredient: Dict,
        match_result: Optional[Dict],
        quality_map: Dict,
    ) -> None:
        """Reconcile identity after a candidate becomes intentionally non-scorable."""
        decision, identity_match, taxonomy_coherent = self._resolve_iqd_identity(
            ingredient,
            match_result,
            quality_map,
            allow_unscoreable_taxonomy_only=True,
        )
        self._stamp_iqd_identity(
            row,
            ingredient,
            decision,
            identity_match,
            taxonomy_coherent,
        )
        row["scoreable_identity"] = False

    def _compute_excipient_flags(self, ingredient: Dict) -> Tuple[bool, Optional[str]]:
        """Determine excipient status for ingredient-level signals.

        Sprint E1.3.1 — honors the active-context therapeutic override:
        dual-use compounds (tocopherols, lecithin) that land here with
        isAdditive=True but carry a valid therapeutic dose AND are IQM-
        known should not be flagged excipient.
        """
        ing_name_raw = (ingredient.get('name', '') or '')
        ing_name = ing_name_raw.strip().lower()
        std_name = (ingredient.get('standardName', '') or ing_name_raw)
        quality_map = self.databases.get('ingredient_quality_map', {})
        botanicals_db = self.databases.get('botanical_ingredients', {})

        # Sprint E1.3.1 override — but NOT for ingredients nested under a
        # nutrition rollup (Total Carbohydrates, Total Fat, etc.).  Those
        # are genuinely additives broken out from the nutrition panel and
        # must keep skipping.  Real branded actives (KSM-66 in "Herbal
        # Blend") don't have a "Total X" parent, so they still override.
        has_dose_for_override, _ = self._has_valid_therapeutic_dose(ingredient)
        _parent_blend = (ingredient.get("parentBlend") or "").strip()
        _under_nutrition_rollup = bool(
            ingredient.get("isNestedIngredient")
            and _parent_blend
            and _parent_blend.lower().startswith("total ")
        )
        active_context_override = (
            has_dose_for_override
            and not _under_nutrition_rollup
            and self._is_known_therapeutic(ing_name_raw, std_name, quality_map, botanicals_db)
        )

        if ingredient.get('isAdditive', False) and not active_context_override:
            return True, SKIP_REASON_ADDITIVE

        additive_type = ingredient.get('additiveType', '')
        if (
            additive_type
            and additive_type.lower() in ADDITIVE_TYPES_SKIP_SCORING
            and not active_context_override
        ):
            return True, SKIP_REASON_ADDITIVE_TYPE

        # Check ingredient name only — DSLD standardName can misclassify active botanicals
        # (e.g. Elderberry/Turmeric → "natural colors"), causing false excipient gates.
        # isAdditive=True (genuine additives) is already handled above.
        if ing_name in EXCIPIENT_NEVER_PROMOTE:
            return True, "excipient_never_promote"

        for excipient in EXCIPIENT_NEVER_PROMOTE:
            if excipient in ing_name and re.search(r'\b' + re.escape(excipient) + r'\b', ing_name):
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
        # 2026-05-15: \d+ → \d+(?:\.\d+)? so the patterns match decimal
        # percentages like "less than 0.1%" — GNC Aloe Vera Juice (214221)
        # carried "less than 0.1%" as a bare inactive that previously slipped
        # past these guards (integer-only \d+) and got promoted, triggering
        # UNMAPPED_ACTIVE_INGREDIENT → NOT_SCORED.
        if re.match(r"^(contains|may also contain)\s*(less than|<)\s*\d+(?:\.\d+)?\s*%(\s*of)?", text):
            return SKIP_REASON_LABEL_PHRASE
        if re.match(r"^contains?\s+\d+(?:\.\d+)?\s*percent\s+or\s+less(\s+of)?", text):
            return SKIP_REASON_LABEL_PHRASE
        if re.match(r"^less than\s*\d+(?:\.\d+)?\s*%(\s*of)?", text):
            return SKIP_REASON_LABEL_PHRASE
        if re.match(r"^<\s*\d+(?:\.\d+)?\s*%(\s*of)?", text):
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

    def _cleaner_skip_reason(self, ingredient: Dict) -> Optional[str]:
        if ingredient.get("score_eligible_by_cleaner") is not False:
            return None
        role = str(
            ingredient.get("cleaner_row_role")
            or ingredient.get("score_exclusion_reason")
            or ""
        ).strip().lower()
        if role == "blend_header_total":
            return SKIP_REASON_BLEND_HEADER_WITH_WEIGHT
        if role in {"nested_display_only", "composition_leaf"}:
            return SKIP_REASON_NESTED_NON_THERAPEUTIC
        if role == "excipient":
            return SKIP_REASON_ADDITIVE
        if role == "label_header":
            return SKIP_REASON_LABEL_PHRASE
        if role == "nutrition_rollup":
            return SKIP_REASON_NUTRITION_FACT
        return role or SKIP_REASON_RECOGNIZED_NON_SCORABLE

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
        - Reviewer-signed curated context override stamped by the cleaner
          (context_override_applied=True). These overrides are an explicit
          per-product decision that this row should score as the override
          IQM identity regardless of name-based recognition. Bypasses ALL
          subsequent skip checks. Spec: reports/not_scored_triage/
          cleaner_side_context_routing_spec.md

        Returns skip_reason string if should skip, None if scorable.
        """
        # 2026-05-24: curated context-routing override is the highest-priority
        # scorability signal — it carries a PharmaGuide Clinician Team sign-off
        # tying a specific (dsld_id, raw_ingredient_text, product_name) tuple
        # to a specific IQM parent + form. Without this bypass, rows like
        # Pure Encapsulations 317962 "Porcine Kidney Extract" get caught by
        # _is_recognized_non_scorable matching PII_KIDNEY_TISSUE
        # (category="active_pending_relocation") and shunted to
        # ingredients_skipped before the curated override is consumed. The
        # check must run BEFORE any of the Z/A/B groups so the override is
        # never silently overridden by structural / additive / blend skips.
        if ingredient.get("context_override_applied") is True:
            return None
        ing_name = ingredient.get('name', '')
        std_name = ingredient.get('standardName', '') or ing_name
        name_lower = ing_name.lower().strip()
        std_lower = std_name.lower().strip()
        name_norm = self._normalize_exclusion_text(ing_name)
        std_norm = self._normalize_exclusion_text(std_name)
        raw_source = ingredient.get('raw_source_text', '')
        cleaner_declared_total = (
            ingredient.get("score_eligible_by_cleaner") is True
            and ingredient.get("dose_role") == "declared_total"
        )

        # Some branded delivery systems expose the true active as a single nested child
        # with its own dose. In those cases the parent quantity is the delivery matrix,
        # not the therapeutic dose, so only the child should score.
        if self._is_single_child_wrapper_parent(ingredient):
            has_dose_wrapper, _ = self._has_valid_therapeutic_dose(ingredient)
            return (
                SKIP_REASON_BLEND_HEADER_WITH_WEIGHT if has_dose_wrapper
                else SKIP_REASON_BLEND_HEADER_NO_DOSE
            )

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
            if exclusion_reason and not (
                cleaner_declared_total
                and exclusion_reason == SKIP_REASON_NUTRITION_FACT
            ):
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
        if ingredient_group_pre == 'header':
            return SKIP_REASON_BLEND_HEADER_NO_DOSE
        if isinstance(nested_pre, list) and nested_pre and 'blend' in ingredient_group_pre:
            has_dose_pre, _ = self._has_valid_therapeutic_dose(ingredient)
            return (
                SKIP_REASON_BLEND_HEADER_WITH_WEIGHT if has_dose_pre
                else SKIP_REASON_BLEND_HEADER_NO_DOSE
            )
        if (
            isinstance(nested_pre, list)
            and nested_pre
            and (
                ingredient.get('proprietaryBlend', False)
                or ingredient.get('isProprietaryBlend', False)
            )
        ):
            # Round 2 fix (2026-04-30): a "proprietary blend" by FDA/DSLD
            # convention has UNDISCLOSED individual amounts. When the parent
            # carries proprietaryBlend=True but ALL nested children expose
            # specific doses, the label is fully transparent and the parent
            # is a branded single-active (e.g., BioCell Collagen 1000mg with
            # nested 'hydrolyzed Collagen 600mg' disclosure, Turmeric blend
            # with disclosed extract+root amounts). Don't skip these — they
            # are real scorable actives, not opaque blends.
            _all_nested_have_dose = all(
                self._has_valid_therapeutic_dose(n)[0]
                for n in nested_pre if isinstance(n, dict)
            )
            if not _all_nested_have_dose:
                has_dose_pre, _ = self._has_valid_therapeutic_dose(ingredient)
                return (
                    SKIP_REASON_BLEND_HEADER_WITH_WEIGHT if has_dose_pre
                    else SKIP_REASON_BLEND_HEADER_NO_DOSE
            )
            # Else: fully-disclosed parent — fall through to scorable path.

        if ingredient.get('isNestedIngredient', False):
            parent_blend = ingredient.get('parentBlend', '')
            has_nested_dose, _ = self._has_valid_therapeutic_dose(ingredient)
            activity_qty, _activity_unit = self._extract_enzyme_activity_dose(ingredient)
            if parent_blend and not has_nested_dose and activity_qty is None:
                return SKIP_REASON_NESTED_NON_THERAPEUTIC

        # =================================================================
        # GROUP A: Structural flags from cleaning
        # These are product-level signals (isAdditive, additiveType) that
        # reflect how the ingredient is USED in this product.
        #
        # Sprint E1.3.1 (context-aware classifier): dual-use compounds
        # (tocopherols, lecithin, fatty acids) carry isAdditive=True by
        # default because DSLD hints at common additive usage. When the
        # same compound appears in the ACTIVE panel AND has a valid
        # therapeutic dose AND is IQM-known, the label itself is treating
        # it as an active — override the additive gate. Trace-dose or
        # inactive-panel variants still skip as additive.
        # =================================================================
        has_dose_for_override, _ = self._has_valid_therapeutic_dose(ingredient)
        _parent_blend = (ingredient.get("parentBlend") or "").strip()
        _under_nutrition_rollup = bool(
            ingredient.get("isNestedIngredient")
            and _parent_blend
            and _parent_blend.lower().startswith("total ")
        )
        active_context_override = (
            has_dose_for_override
            and not _under_nutrition_rollup
            and self._is_known_therapeutic(ing_name, std_name, quality_map, botanicals_db)
        )

        # A1: Check isAdditive flag (unless overridden by active-panel therapeutic context)
        if ingredient.get('isAdditive', False) and not active_context_override:
            return SKIP_REASON_ADDITIVE

        # A2: Check additiveType (same override)
        additive_type = ingredient.get('additiveType', '')
        if (
            additive_type
            and additive_type.lower() in ADDITIVE_TYPES_SKIP_SCORING
            and not active_context_override
        ):
            return SKIP_REASON_ADDITIVE_TYPE

        # =================================================================
        # THERAPEUTIC OVERRIDE: If known in quality map or botanicals, score.
        # This MUST run before recognition-based skips so that IQM-known
        # ingredients are never blocked by harmful_additives or banned_recalled
        # high_risk/watchlist entries.  IQM scoring (Section A) and safety
        # penalties (Section B) are independent concerns.
        # =================================================================
        if self._is_known_therapeutic(ing_name, std_name, quality_map, botanicals_db):
            return None

        recognized = self._is_recognized_non_scorable(ing_name, std_name)
        if self._recognition_blocks_scoring(recognized):
            return SKIP_REASON_RECOGNIZED_NON_SCORABLE

        # Deterministic role split: recognized non-scorable identities are skipped.
        # This prevents excipients/label technologies from inflating unmapped actives.
        if recognized:
            return SKIP_REASON_RECOGNIZED_NON_SCORABLE

        # OVERRIDE CHECK: If has potency markers in name, always score
        if self._has_potency_markers(ing_name):
            return None

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
        # or hierarchyType indicates summary/blend_header.
        #
        # Round 2 fix (2026-04-30): hierarchy_type='source' was previously
        # treated as blend evidence, but it just describes ingredient ORIGIN
        # ("Chicken Sternal Cartilage" for BioCell Collagen, "Curcuma longa"
        # for Turmeric). Source descriptors don't make a parent a blend.
        # Restrict to true blend-header signals: 'summary' and 'blend_header'.
        is_structural_blend = (
            ingredient.get('proprietaryBlend', False)
            or ingredient.get('isProprietaryBlend', False)
            or ('blend' in ingredient_group)
        )
        hierarchy_type_raw = ingredient.get('hierarchyType', '')
        hierarchy_type = (
            hierarchy_type_raw.get('type', '')
            if isinstance(hierarchy_type_raw, dict)
            else hierarchy_type_raw
        )
        is_header_hierarchy = hierarchy_type in ('summary', 'blend_header')

        if has_dose and (is_structural_blend or is_header_hierarchy):
            for pattern in BLEND_HEADER_PATTERNS_LOW_CONFIDENCE:
                if re.search(pattern, name_lower, re.IGNORECASE):
                    return SKIP_REASON_BLEND_HEADER_WITH_WEIGHT

        return None

    def _is_single_child_wrapper_parent(self, ingredient: Dict) -> bool:
        """Detect branded delivery-system parents that should defer to one nested active child."""
        if ingredient.get('isNestedIngredient', False):
            return False

        nested = ingredient.get('nestedIngredients') or []
        if not isinstance(nested, list) or len(nested) != 1 or not isinstance(nested[0], dict):
            return False

        child = nested[0]
        parent_has_dose, _ = self._has_valid_therapeutic_dose(ingredient)
        child_has_dose, _ = self._has_valid_therapeutic_dose(child)
        if not parent_has_dose or not child_has_dose:
            return False

        parent_group_norm = self._normalize_exclusion_text(ingredient.get('ingredientGroup', ''))
        child_group_norm = self._normalize_exclusion_text(child.get('ingredientGroup', ''))
        child_name_norm = self._normalize_exclusion_text(
            child.get('standardName') or child.get('name', '')
        )
        if not parent_group_norm or not (child_group_norm or child_name_norm):
            return False

        if parent_group_norm not in {child_group_norm, child_name_norm}:
            return False

        parent_name_norm = self._normalize_exclusion_text(ingredient.get('name', ''))
        wrapper_tokens = (
            'triglyceride',
            'tri glyceride',
            'liposomal',
            'liposome',
            'phytosome',
            'microencapsulated',
            'micro encapsulated',
        )
        return any(token in parent_name_norm for token in wrapper_tokens)

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
        cleaner_role = str(ingredient.get("cleaner_row_role") or "").strip().lower()
        if cleaner_role != "active_misfiled_in_inactive":
            return None
        if ingredient.get("score_eligible_by_cleaner") is not True:
            return None

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

        # Check for partial matches in excipient list (ing_name only).
        # Use word-boundary matching to prevent false positives like
        # "citric acid" matching inside "hydroxycitric acid".
        for excipient in EXCIPIENT_NEVER_PROMOTE:
            if excipient in name_lower and re.search(r'\b' + re.escape(excipient) + r'\b', name_lower):
                return None

        # RULE A: Known therapeutic ingredient (single factor - high confidence)
        # This MUST run before recognition-based blocking so IQM-known
        # ingredients are never prevented from promotion by harmful_additives
        # or banned_recalled high_risk/watchlist entries.
        is_known = self._is_known_therapeutic(
            ing_name, std_name, quality_map, botanicals_db
        )
        if is_known:
            return {
                "reason": PROMOTE_REASON_KNOWN_DB,
                "confidence": "HIGH"
            }

        # Block promotion for banned_recalled ingredients not in IQM
        recognized = self._is_recognized_non_scorable(ing_name, std_name)
        if self._recognition_blocks_scoring(recognized):
            return None

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

        # Deliberately do NOT fall through to `self.databases['absorption_enhancers']`
        # here. That data file contains a broader reference set including carrier
        # oils (coconut oil, olive oil), general nutrients (Vitamin C, Glycine),
        # and delivery technologies (liposomal, nanoemulsion). Treating all of
        # those as promotable bioavailability enhancers breaks the carrier-oil
        # hardening guarantees in test_scorable_classification.py.
        # ABSORPTION_ENHANCERS_PROMOTE_EXCEPTION (in scripts/constants.py) is the
        # curated allowlist for this specific narrow use case — expand it there,
        # not by broadening this loop.
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
        # Check quality map. This is an exploratory predicate — we only want
        # a yes/no answer, not a final match. Pass _form_extraction_attempt=True
        # so this call does NOT emit parent_fallback telemetry (which would
        # otherwise leak transient rows into parent_fallback_report.json when
        # the real ingredient enrichment later upgrades the match).
        quality_match = self._match_quality_map(
            ing_name, std_name, quality_map, _form_extraction_attempt=True
        )
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

    def _is_recognized_non_scorable(
        self, ing_name: str, std_name: str, raw_row: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Check if ingredient is recognized in non-scorable databases.

        TIERED MATCHING (per dev feedback):
        - Tier 0 (Sprint 1, NEW): raw_row.uniiCode → O(1) UNII index lookup
        - Tier 1: quality_map → scorable bioactive
        - Tier 2: botanicals → recognized (scorable if modeled)
        - Tier 3: other_ingredients → recognized_non_scorable (THIS METHOD)
        - Tier 4: excipient_list → recognized_non_scorable
        - Tier 5: unmatched

        This prevents oils, food powders, and carriers from counting as
        "unmapped ingredients" and inflating the unmapped count.

        Args:
            ing_name: ingredient name from cleaner output
            std_name: candidate standard_name (from cleaner mapping attempt)
            raw_row: optional full DSLD row dict with `uniiCode` and `forms[*]`
                     for Tier-0 UNII-anchored recognition (Sprint 1)

        Returns:
            Dict with recognition_source and reason if recognized, None otherwise.
        """
        # ── Sprint 1 Tier-0: UNII-anchored fast path ──
        if raw_row is not None and self._nonscorable_unii_index:
            raw_unii = _normalize_unii(raw_row.get("uniiCode"))
            if raw_unii and raw_unii in self._nonscorable_unii_index:
                return dict(self._nonscorable_unii_index[raw_unii])
            # Walk forms[*].uniiCode if top-level missed
            forms = raw_row.get("forms") or []
            if isinstance(forms, list):
                for form in forms:
                    if not isinstance(form, dict):
                        continue
                    form_unii = _normalize_unii(form.get("uniiCode"))
                    if form_unii and form_unii in self._nonscorable_unii_index:
                        return dict(self._nonscorable_unii_index[form_unii])

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
            # Iterative compound-prefix strip — handles DSLD label prefix combos
            # like "88% organic whole leaf Aloe vera" or "100% raw whole bark
            # Cinnamon" that chain percentage + sourcing-qualifier + preparation
            # in one string. Applies the strip rules in a loop so order doesn't
            # matter and partial matches don't block subsequent strips. Scope:
            # tier-3 recognition only (this _variants() runs inside
            # _is_recognized_non_scorable). The existing one-pass strips above
            # remain so this is purely additive — adds one more candidate per
            # base/pre form, never removes existing ones. Safe from false-
            # positive identity loss because the un-stripped variants are
            # still tried first against the lookup index. Added 2026-05-14.
            def _iter_strip_compound_prefix(text: str) -> str:
                prev = None
                while prev != text:
                    prev = text
                    text = re.sub(r'^\s*\d+(?:\.\d+)?%\s+', '', text)
                    text = re.sub(
                        r'^(?:certified\s+organic|fair[-\s]?trade|organic|natural|raw|pure)\s+',
                        '',
                        text,
                        flags=re.IGNORECASE,
                    )
                    text = re.sub(r'^(?:whole|raw)\s+', '', text, flags=re.IGNORECASE)
                return re.sub(r'\s+', ' ', text).strip()
            variants.add(_iter_strip_compound_prefix(base))
            variants.add(_iter_strip_compound_prefix(self._normalize_text(pre)))
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
                    "reference_notes": entry.get('notes', ''),
                    "reference_common_uses": entry.get('common_uses', []),
                    "reference_additive_type": entry.get('additive_type', ''),
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
        # Use word-boundary matching to prevent false positives like
        # "citric acid" matching inside "hydroxycitric acid".
        for excipient in EXCIPIENT_NEVER_PROMOTE:
            if excipient in name_lower and re.search(r'\b' + re.escape(excipient) + r'\b', name_lower):
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
            "b1", "b2", "b3", "b5", "b6", "b7", "b9", "b12",
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
        the canonical taxonomy gets useful category data instead of 'unknown'.
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
        activity_quantity, activity_unit = self._extract_enzyme_activity_dose(ingredient)
        if activity_quantity is not None:
            has_dose = True
        unit_normalized = self._normalize_unit_for_signal(unit)
        is_excipient, never_promote_reason = self._compute_excipient_flags(ingredient)
        blend_flags = self._compute_blend_flags(ingredient, None)
        missing_cleaner_contract_fields = self._missing_cleaner_contract_fields(ingredient)
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
                # Sprint E1.3.3 — normalized parent-blend mass (in mg) for
                # the scorer's fish-oil EPA/DHA fallback. E1.2.1 stamps
                # parentBlendMass + parentBlendUnit at flatten time; here
                # we unit-normalize so the scorer reads a single value.
                "parent_blend_mass_mg": _normalize_parent_blend_mg(
                    ingredient.get("parentBlendMass"),
                    ingredient.get("parentBlendUnit"),
                ),
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
            matched_canonical_id = match_result.get('canonical_id')
            quality_map = self.databases.get('ingredient_quality_map', {})
            canonical_id = self._quality_match_scoring_canonical(
                match_result, quality_map
            )
            matched_entry_id = match_result.get('matched_entry_id')
            canonical_redirect_from = match_result.get('canonical_redirect_from')
            canonical_redirect_source = match_result.get('canonical_redirect_source')
            if (
                matched_canonical_id
                and canonical_id != matched_canonical_id
                and canonical_redirect_from is None
            ):
                canonical_redirect_from = matched_canonical_id
                canonical_redirect_source = 'match_rules.target_id'
                matched_entry_id = matched_canonical_id
            # v3.6.0: `score` is now an alias of bio_score (no natural-source
            # bonus). The legacy formula `bio_score + 3 if natural` was retired
            # because A1/A2/A6 in the scorer now read bio_score directly, and
            # the natural-source signal moved to A5e where sourcing belongs.
            # The field is still emitted for backward compatibility during the
            # v3.6.x shadow window — older scorers reading `score` will get
            # the same answer as bio_score (sourcing-neutral).
            # Force sourcing-neutral. Ignore any legacy pre-computed `score`
            # value in the IQM data file (which still has natural+3 baked in
            # — see ingredient_quality_map.json). v3.6.0 contract: score == bio_score.
            score = bio_score
            used_form_fallback = match_result.get('match_status') == 'FORM_UNMAPPED_FALLBACK'

            # Track form fallbacks for audit report
            if used_form_fallback:
                unmapped_forms = match_result.get('unmapped_forms', [])
                fallback_form_name = match_result.get('form_name', '(unspecified)')
                # Look up the parent canonical's form count so the classifier
                # can short-circuit on single-form parents (structurally
                # unambiguous fallbacks are audit noise, not action items).
                parent_form_count: Optional[int] = None
                canonical_id = match_result.get('canonical_id')
                if canonical_id:
                    parent_entry = self.databases.get(
                        'ingredient_quality_map', {}
                    ).get(canonical_id, {})
                    parent_forms = parent_entry.get('forms', {}) or {}
                    if isinstance(parent_forms, dict):
                        parent_form_count = len(parent_forms)
                audit_classification = self._classify_form_fallback_audit(
                    ing_name,
                    match_result.get('standard_name', ''),
                    unmapped_forms,
                    fallback_form_name,
                    parent_form_count=parent_form_count,
                )
                self._form_fallback_details.append({
                    "ingredient_label": ing_name,
                    "raw_source_text": raw_source_text,
                    "canonical_id": match_result.get('canonical_id', ''),
                    "parent_name": match_result.get('standard_name', ''),
                    "unmapped_form_text": ', '.join(unmapped_forms) if unmapped_forms else ing_name,
                    "fallback_form": fallback_form_name,
                    "fallback_bio_score": bio_score,
                    "fallback_score": score,
                    "forms_differ": audit_classification["forms_differ"],
                    "audit_noise_reason": audit_classification["audit_noise_reason"],
                    "form_source": match_result.get('form_source', ''),
                    "source_section": source_section,
                })

            entry = {
                # LABEL NAME PRESERVATION:
                "name": ing_name,  # Label-facing name (user-visible)
                "raw_source_text": raw_source_text,  # Exact label text (provenance)
                "standard_name": match_result.get('standard_name', std_name),  # Canonical
                "matched_form": match_result.get('form_name', 'standard'),
                "canonical_id": canonical_id,
                "canonical_source_db": match_result.get('canonical_source_db') or "ingredient_quality_map",
                "matched_entry_id": matched_entry_id,
                "canonical_redirect_from": canonical_redirect_from,
                "canonical_redirect_source": canonical_redirect_source,
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
                "identity_confidence": self._quality_match_identity_confidence(match_result),
                "identity_decision_reason": "form_unmapped_fallback" if used_form_fallback else "quality_map_match",
                "safety_hits": [],
                "hierarchyType": hierarchy_type,
                "source_section": source_section,
                "is_nested_ingredient": bool(ingredient.get("isNestedIngredient", False)),
                "parent_blend": ingredient.get("parentBlend"),
                # Sprint E1.3.3 — normalized parent-blend mass (in mg) for
                # the scorer's fish-oil EPA/DHA fallback. E1.2.1 stamps
                # parentBlendMass + parentBlendUnit at flatten time; here
                # we unit-normalize so the scorer reads a single value.
                "parent_blend_mass_mg": _normalize_parent_blend_mg(
                    ingredient.get("parentBlendMass"),
                    ingredient.get("parentBlendUnit"),
                ),
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
                # Sprint E1.3.3 — normalized parent-blend mass (in mg) for
                # the scorer's fish-oil EPA/DHA fallback. E1.2.1 stamps
                # parentBlendMass + parentBlendUnit at flatten time; here
                # we unit-normalize so the scorer reads a single value.
                "parent_blend_mass_mg": _normalize_parent_blend_mg(
                    ingredient.get("parentBlendMass"),
                    ingredient.get("parentBlendUnit"),
                ),
                "is_parent_total": False,
                "form_extraction_used": False,
                "is_dual_form": False,
                "original_label": raw_source_text,
                "extracted_forms": [],
                "matched_forms": [],
                "unmapped_forms": [],
                "aggregation_method": None,
                "final_form_bio_score": None,
                "additional_forms": [],
                "form_source": None,
                "form_unmapped": False,
            }

        # Add promotion metadata if applicable
        if promotion_reason:
            entry["promotion_reason"] = promotion_reason
            entry["promotion_confidence"] = promotion_confidence
            entry["dose_present"] = dose_present

        cleaner_source = ingredient.get("source_section")
        if cleaner_source in {"active", "inactive", "nutrition", "label", "unknown"}:
            source_section = cleaner_source
        elif source_section == "inactive_promoted":
            source_section = "inactive"
        entry["source_section"] = source_section
        entry["raw_source_path"] = ingredient.get("raw_source_path") or (
            "inactiveIngredients" if source_section == "inactive" else "activeIngredients"
        )
        entry["cleaner_row_role"] = ingredient.get("cleaner_row_role") or (
            "active_scorable" if source_section == "active" else "inactive"
        )
        entry["score_eligible_by_cleaner"] = (
            bool(ingredient.get("score_eligible_by_cleaner"))
            if "score_eligible_by_cleaner" in ingredient
            else source_section == "active"
        )
        entry["score_exclusion_reason"] = ingredient.get("score_exclusion_reason")
        entry["dose_class"] = ingredient.get("dose_class")
        entry["raw_taxonomy"] = ingredient.get("raw_taxonomy")
        if activity_quantity is not None:
            entry["activity_quantity"] = int(activity_quantity) if activity_quantity.is_integer() else activity_quantity
            entry["activity_unit"] = activity_unit
            entry["has_dose"] = True
            entry["dose_class"] = "enzyme_activity"
        entry.setdefault("canonical_source_db", ingredient.get("canonical_source_db"))
        entry.setdefault("normalized_key", ingredient.get("normalized_key") or norm_module.make_normalized_key(raw_source_text))
        entry.setdefault("recognition_source", None)
        entry.setdefault("recognition_type", None)
        entry.setdefault("recognition_reason", None)
        entry.setdefault("form_id", None)
        entry.setdefault("form_source", None)
        entry.setdefault("form_unmapped", bool(is_form_unmapped))
        entry.setdefault("delivers_markers", [])
        entry.setdefault("fallback_class", None)
        entry.setdefault("fallback_reason", None)
        if entry.get("identity_decision_reason") == "form_unmapped_fallback":
            self._tag_fallback_decision(entry, "clinical_fail_safe", "form_unmapped_fallback")
        self._mark_cleaner_contract_fallback(entry, missing_cleaner_contract_fields)

        # Sprint 1.1: propagate cleaner-side match method (UNII / alternateNames)
        # so the downstream match_ledger emission can attribute it correctly.
        # When set on the input ingredient (by the cleaner), forward to the
        # quality_entry that flows into ingredient_quality_data.ingredients[],
        # which is what record_match / record_recognized_non_scorable read.
        cm = ingredient.get("cleaner_match_method")
        if cm:
            entry["cleaner_match_method"] = cm
        if isinstance(ingredient.get("dose_data_quality"), dict):
            entry["dose_data_quality"] = dict(ingredient["dose_data_quality"])

        # Phase 7.5 — stamp an authoritative collagen_subtype on collagen rows so
        # the scorer (and Flutter / audits) read it instead of re-deriving from
        # text. Row-only (strict) classification: assert a subtype only when THIS
        # row proves it; a generic "collagen" row is left 'unspecified' for the
        # scorer to resolve with product context. Single source of truth:
        # collagen_taxonomy.classify_collagen_subtype_strict.
        if str(entry.get("canonical_id") or "").strip().lower() == "collagen":
            row_text = " ".join(
                str(x) for x in (
                    entry.get("matched_form"), entry.get("name"),
                    entry.get("standard_name"), raw_source_text,
                ) if x
            )
            entry["collagen_subtype"] = (
                classify_collagen_subtype_strict(row_text) or _COLLAGEN_UNSPECIFIED
            )

        return entry

    def _normalize_form_fallback_audit_text(self, value: Optional[str]) -> str:
        """Normalize free-text form/source labels for fallback-audit comparison."""
        if not value:
            return ""

        normalized = self._normalize_text(value)
        normalized = normalized.replace("/", ",")
        normalized = re.sub(r"\s+", " ", normalized).strip(" ,")
        return normalized

    # Known source-material terms — animal tissues, plant species, yeast cultures,
    # marine species, mineral-source claims, and marketing blend labels that
    # DSLD surfaces as form text but are NOT actual IQM form aliases. These
    # correspond to DSLD forms[].category values like "animal part or source",
    # or to raw label text that names the ORIGIN of the nutrient rather than
    # its chemical form.
    _SOURCE_MATERIAL_TERMS: frozenset = frozenset({
        # Legacy marine/animal species
        "anchovy", "anchovies", "bamboo", "bovine", "chicken sternal cartilage",
        "crab", "herring", "jack", "mackerel", "pineapple", "salmon",
        "sardine", "sardines", "shrimp", "smelt", "squid", "tuna",
        # Animal tissues / glandular parts (pancreatin, glandular supplements)
        "pancreas", "pancreas extract", "pancreatic tissue", "pancreatic gland",
        "liver", "thymus", "spleen", "adrenal", "kidney", "heart",
        # Fish / marine species descriptors
        "fish", "cod", "cod fish", "pollock", "alaska pollock", "alaskan pollock",
        "wild-caught alaska pollock", "usa wild-caught alaska pollock",
        "wild-caught", "wild caught",
        # Plant / fruit whole-food sources surfaced as forms
        "cantaloupe", "cantaloupe melon", "melon",
        "amla", "emblic", "emblic fruit", "emblic fruit extract",
        "moringa",
        "broccoli", "broccoli flower", "broccoli stem", "broccoli sprout",
        "broccoli flower juice", "broccoli stem juice", "broccoli sprout concentrate",
        "broccoli whole plant concentrate",
        "peach", "peach fruit extract",
        "organic black elderberry juice concentrate",
        "eggshell",
        # Mineral-source marketing claims
        "algae", "algae minerals", "sea minerals", "sea mineral salt",
        "dead sea minerals", "algae dead sea minerals",
        "ionic minerals", "ionic plant based minerals", "plant based minerals",
        "plant minerals",
        "mineral complex", "trace mineral complex", "trace minerals",
        # Marketing blends that get surfaced as form text
        "organic immune blend", "organic food blend", "beauty blend",
        "organic immune system blend", "immune blend", "food blend",
        # Vitamin / mineral "complex" marketing labels — hybrid blends with no
        # single specific IQM form. Fallback to parent-unspecified is the
        # correct conservative answer.
        "vitamin k complex", "k complex", "k2 vitamin k complex",
        "vitamin b complex", "b complex", "vitamin d complex", "d complex",
        "vitamin e complex", "e complex",
        # Marker compounds / constituents (nutrient indicators, not forms)
        "polyphenols", "punicalagin", "polyphenols, punicalagin",
        "terpenes", "phytocannabinoids", "beta-caryophyllene",
        "beta-caryophyllene, phytocannabinoids, terpenes",
        "spm", "resolvins", "protectins", "spm, resolvins, protectins",
        "resolvins, protectins",
        "biologically active sterols", "biologically active sterols, fatty acids",
        "organic acids", "sterols", "fatty acids", "omega-3 fatty acids",
        "omega-6 fatty acids", "essential fatty acids",
    })

    # Known genus names for Latin binomial source descriptors. These prefix
    # two-or-more-word Latin species names in DSLD label text (e.g.
    # "Sus scrofa pancreas", "Carica papaya extract, dried, purified").
    _LATIN_GENUS_NAMES: frozenset = frozenset({
        # Animal genera
        "sus", "bos", "gallus",
        # Plant genera commonly used as DSLD source species
        "carica", "ananas", "brassica", "vitis", "panax", "camellia",
        "phyllanthus", "emblica", "moringa", "rosa", "sambucus", "cimicifuga",
        "paullinia", "withania", "lepidium", "cerasus", "vaccinium",
        "matricaria", "harpagophytum", "astragalus", "ginkgo", "echinacea",
        "curcuma", "zingiber", "allium", "trigonella", "silybum",
        "actaea", "rhodiola", "bacopa", "centella", "mentha", "passiflora",
        "scutellaria", "valeriana", "eleutherococcus", "paeonia", "crataegus",
        "hypericum", "tribulus", "foeniculum", "salvia", "ocimum",
        # Probiotic / yeast genera (strain-level source descriptors)
        "lactobacillus", "bifidobacterium", "streptococcus", "lactococcus",
        "saccharomyces", "bacillus",
    })

    # Tissue / plant-part suffix tokens that, when combined with a genus or
    # known plant name, indicate source material rather than a nutrient form.
    _SOURCE_PART_SUFFIXES: frozenset = frozenset({
        "root", "leaf", "seed", "fruit", "flower", "stem", "bark", "bulb",
        "rhizome", "whole plant", "sprout", "peel", "aerial parts",
        "pancreas", "liver", "tissue",
        "extract", "concentrate", "juice", "powder",
        "culture", "fermentation",
    })

    # Individual tokens that, when ALL words of a normalized text are drawn
    # from this set (plus prep qualifiers), indicate a source/marker descriptor.
    # This handles the reality that `_normalize_form_fallback_audit_text` loses
    # commas (the shared `_normalize_text` converts comma → space), so
    # multi-term phrases like "polyphenols, punicalagin" arrive here as
    # "polyphenols punicalagin".
    _SOURCE_WORD_TOKENS: frozenset = frozenset({
        # Marker constituents
        "polyphenols", "punicalagin", "terpenes", "phytocannabinoids",
        "beta-caryophyllene", "spm", "resolvins", "protectins",
        "sterols", "biologically", "active", "fatty", "acids",
        "omega-3", "omega-6", "essential",
        # Plant parts / preparations
        "flower", "stem", "leaf", "root", "seed", "fruit", "bark", "sprout",
        "juice", "concentrate", "extract", "powder", "whole", "plant",
        "culture", "fermentation", "dried", "purified", "aqueous",
        "liquid", "fresh", "standardized",
        # Whole-food sources
        "broccoli", "cantaloupe", "melon", "amla", "emblic", "moringa",
        "peach", "elderberry", "black",
        # Species / source descriptors
        "fish", "cod", "salmon", "sardine", "sardines", "anchovy", "anchovies",
        "pollock", "alaska", "alaskan", "wild-caught", "wild", "caught",
        "usa", "mackerel", "herring", "jack", "smelt", "squid", "crab",
        "shrimp", "tuna", "pineapple", "bamboo", "bovine",
        "pancreas", "pancreatic", "tissue", "gland",
        "liver", "thymus", "spleen", "adrenal", "kidney", "heart",
        "eggshell",
        # Mineral source claims — generic words only, not specific mineral names
        "algae", "sea", "dead", "ionic", "trace",
        "mineral", "minerals", "complex", "salt",
        # Dairy protein sources used as calcium carriers
        "casein", "whey", "protein",
        # Marketing blend words
        "immune", "food", "beauty", "system", "blend", "organic",
    })

    def _is_source_material_descriptor_for_fallback_audit(self, normalized_text: str) -> bool:
        """
        Return True when fallback text names a source material, not a missing
        IQM form.

        Covers four detection paths:
        1. Static allowlist (_SOURCE_MATERIAL_TERMS) — exact-match phrase or
           comma-separated tokens that are all source terms.
        2. Latin binomial genus-species pattern (_LATIN_GENUS_NAMES) — any
           comma-separated token starting with a known genus name is treated
           as a Linnaean source descriptor.
        3. Yeast culture pattern — "<genus-abbrev> cerevisiae culture" etc.
        4. Whitespace-token coverage — covers comma-lost phrases like
           "polyphenols punicalagin" (originally "polyphenols, punicalagin")
           by checking if every whitespace token is a known source/marker
           word in `_SOURCE_WORD_TOKENS`.

        Non-source forms (e.g. "calcium citrate", "phospholipid complex",
        "ferric saccharate") must NOT match any of these paths; they are real
        alias gaps handled elsewhere.
        """
        if not normalized_text:
            return False

        # Path 1: exact-phrase allowlist
        if normalized_text in self._SOURCE_MATERIAL_TERMS:
            return True

        # Path 1b: comma-separated tokens all in allowlist (preserved for
        # slash-originated inputs like "fish/salmon" → "fish, salmon")
        split_tokens = [part.strip() for part in normalized_text.split(",") if part.strip()]
        if split_tokens and all(
            token in self._SOURCE_MATERIAL_TERMS for token in split_tokens
        ):
            return True

        # Path 2 & 3: Latin binomial / genus-species in any comma-delimited token
        if split_tokens and all(
            self._token_is_latin_source_descriptor(token) for token in split_tokens
        ):
            return True

        # Path 4: every whitespace-token is a known source/marker word.
        # Requires ≥2 tokens to avoid matching generic single words like
        # "extract" (handled separately as generic_extract_token).
        whitespace_tokens = normalized_text.split()
        if (
            len(whitespace_tokens) >= 2
            and all(tok in self._SOURCE_WORD_TOKENS for tok in whitespace_tokens)
        ):
            return True

        return False

    def _token_is_latin_source_descriptor(self, token: str) -> bool:
        """
        Return True if a single comma-delimited token looks like a Latin
        binomial source descriptor (genus species [part] [preparation]).

        Examples that match:
            "sus scrofa pancreas extract"
            "carica papaya extract, dried, purified"  (as a single token:
             "carica papaya extract" — the comma-split handles the rest)
            "s. cerevisiae culture"
            "saccharomyces cerevisiae"
            "withania somnifera root extract"

        Examples that do NOT match:
            "calcium citrate"       (no genus token)
            "phospholipid complex"  (no genus token)
            "ferric saccharate"     (no genus token)
        """
        if not token:
            return False

        t = token.strip().lower()

        # Allow preparation qualifiers alone (dried, purified, aqueous, concentrate)
        # because they appear as trailing comma-split pieces next to a binomial.
        prep_words = {
            "dried", "purified", "aqueous", "concentrate", "extract",
            "powder", "juice", "culture", "fermentation", "liquid",
            "fresh", "whole", "standardized",
        }
        words = t.replace(".", " ").split()
        if not words:
            return False

        # Pure preparation-qualifier token (e.g. "dried", "purified")
        if all(w in prep_words for w in words):
            return True

        # Yeast-culture abbreviation pattern: "s cerevisiae culture",
        # "s. cerevisiae culture" → after "." removal words = ["s","cerevisiae","culture"]
        if len(words) >= 2 and len(words[0]) == 1 and words[1] in {
            "cerevisiae", "boulardii", "scrofa", "taurus",
        }:
            return True

        # Full genus in _LATIN_GENUS_NAMES
        if words[0] in self._LATIN_GENUS_NAMES:
            return True

        # Genus single-letter abbrev followed by a KNOWN species-name.
        # Narrow allowlist prevents false positives on vitamin/form shorthand
        # like "K Complex" or "D Supplement" that share the single-letter
        # prefix pattern but are not Linnaean names.
        known_species = {
            "subtilis", "coagulans", "clausii",
            "plantarum", "bulgaricus", "acidophilus", "casei", "rhamnosus",
            "reuteri", "fermentum", "paracasei", "brevis", "helveticus",
            "gasseri", "johnsonii", "salivarius",
            "lactis", "bifidum", "longum", "breve", "infantis", "animalis",
            "thermophilus",
        }
        if (
            len(words) >= 2
            and len(words[0]) == 1
            and words[1] in known_species
        ):
            return True

        return False

    def _is_standardization_marker_for_fallback_audit(self, normalized_text: str) -> bool:
        """Return True for standardized active-marker text that is not itself an IQM form."""
        if not normalized_text:
            return False

        marker_terms = {
            "8-prenylnaringenin",
            "8 prenylnaringenin",
        }
        return normalized_text in marker_terms

    def _classify_form_fallback_audit(
        self,
        ing_name: str,
        parent_name: str,
        unmapped_forms: List[str],
        fallback_form_name: str,
        parent_form_count: Optional[int] = None,
    ) -> Dict[str, Optional[str]]:
        """
        Classify form-fallback telemetry into actionable alias gaps vs audit noise.

        The report should surface unresolved chemical/form identities, not source
        materials like "Shrimp" or generic tokens like "extract".

        When parent_form_count == 1, the parent canonical has exactly one form in
        IQM, so any FORM_UNMAPPED_FALLBACK can only land on that single form by
        construction. This is applied as a fallback noise reason ONLY when the
        regular text-based classification would have otherwise flagged the row
        as action_needed — more specific reasons (e.g., ``standardization_marker``)
        still win.
        """
        normalized_fallback = self._normalize_form_fallback_audit_text(fallback_form_name)
        normalized_unmapped: List[str] = []
        for form in unmapped_forms or []:
            normalized = self._normalize_form_fallback_audit_text(form)
            if normalized:
                normalized_unmapped.append(normalized)

        if not normalized_unmapped:
            return {"forms_differ": False, "audit_noise_reason": "no_unmapped_form"}

        ingredient_norm = self._normalize_form_fallback_audit_text(ing_name)
        parent_norm = self._normalize_form_fallback_audit_text(parent_name)
        substantive_forms: List[str] = []
        audit_noise_reason: Optional[str] = None

        for form in normalized_unmapped:
            if form == "extract":
                audit_noise_reason = audit_noise_reason or "generic_extract_token"
                continue
            if self._is_source_material_descriptor_for_fallback_audit(form):
                audit_noise_reason = audit_noise_reason or "source_material_descriptor"
                continue
            if self._is_standardization_marker_for_fallback_audit(form):
                audit_noise_reason = audit_noise_reason or "standardization_marker"
                continue
            if form in {ingredient_norm, parent_norm}:
                audit_noise_reason = audit_noise_reason or "parent_label_restatement"
                continue
            substantive_forms.append(form)

        if not substantive_forms:
            return {
                "forms_differ": False,
                "audit_noise_reason": audit_noise_reason or "non_actionable_form_text",
            }

        # Existing text-based classification would return forms_differ=True
        # (an action_needed row). Apply the single-form-parent guard here as a
        # last-resort override: if the parent canonical has exactly one form in
        # IQM, any FORM_UNMAPPED_FALLBACK is structurally noise because there
        # is no alternate form to select.
        would_differ = normalized_fallback not in substantive_forms
        if would_differ and parent_form_count == 1:
            return {
                "forms_differ": False,
                "audit_noise_reason": "single_form_parent",
            }

        return {
            "forms_differ": would_differ,
            "audit_noise_reason": None,
        }

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
            if ing.get("source_section") != "active":
                continue
            if not bool(ing.get("mapped", False)):
                continue
            canonical_id = ing.get("canonical_id")
            if not canonical_id:
                continue
            canonical_groups.setdefault(str(canonical_id), []).append(ing)

        omega_parent_total_canonicals = {"fish_oil", "epa", "dha", "epa_dha"}

        def _is_total_omega_constituent_blend(value: Any) -> bool:
            text = self._normalize_text(value or "")
            if "total" not in text:
                return False
            return "omega" in text or ("epa" in text and "dha" in text)

        for group in canonical_groups.values():
            if len(group) <= 1:
                continue

            parent_blend_names = set()
            for ing in group:
                if not bool(ing.get("is_nested_ingredient", False)):
                    continue
                parent_blend = self._normalize_text(ing.get("parent_blend", "") or "")
                if parent_blend:
                    parent_blend_names.add(parent_blend)

            if not parent_blend_names:
                continue

            # Guard: only flag parent-total when at least one nested child
            # carries a usable individual dose.  Phytosome-style labels list
            # sub-components with qty=0 / unit=NP — the parent row is the
            # sole dose source and must NOT be excluded from A1.
            _dose_units = {"mg", "mcg", "ug", "µg", "g", "iu", "cfu", "billion cfu", "ml"}
            children_have_dose = False
            for ing in group:
                if not bool(ing.get("is_nested_ingredient", False)):
                    continue
                qty = ing.get("quantity", 0)
                unit = (ing.get("unit_normalized") or ing.get("unit") or "").strip().lower()
                if qty and float(qty) > 0 and unit in _dose_units:
                    children_have_dose = True
                    break

            if not children_have_dose:
                continue

            # Some DSLD labels repeat the exact same dosed row as a nested
            # child under a proprietary-blend wrapper even when the wrapper
            # name does not match the top-level nutrient name. Example:
            # "Vitamin C 500 mg" plus nested "Vitamin C 500 mg" under
            # "Polyphenol-C Proprietary Blend". This is a label restatement,
            # not two separate active sources. Keep this deliberately narrower
            # than canonical-id grouping: same normalized row name, same unit,
            # and same numeric quantity are all required so legitimate
            # multi-source cases like caffeine anhydrous + coffee-bean caffeine
            # continue to score as separate sources.
            for parent in group:
                if bool(parent.get("is_nested_ingredient", False)):
                    continue
                parent_name = self._normalize_text(parent.get("name", "") or "")
                if not parent_name:
                    continue
                parent_unit = (parent.get("unit_normalized") or parent.get("unit") or "").strip().lower()
                try:
                    parent_qty = float(parent.get("quantity") or 0)
                except (TypeError, ValueError):
                    parent_qty = 0.0
                if parent_qty <= 0 or not parent_unit:
                    continue
                for child in group:
                    if not bool(child.get("is_nested_ingredient", False)):
                        continue
                    child_name = self._normalize_text(child.get("name", "") or "")
                    child_unit = (child.get("unit_normalized") or child.get("unit") or "").strip().lower()
                    try:
                        child_qty = float(child.get("quantity") or 0)
                    except (TypeError, ValueError):
                        child_qty = 0.0
                    if (
                        child_name == parent_name
                        and child_unit == parent_unit
                        and child_qty > 0
                        and abs(child_qty - parent_qty) < 1e-9
                    ):
                        parent["is_parent_total"] = True
                        break

            # Omega labels often disclose a source-oil mass plus nested
            # total-omega / EPA-DHA constituents. The source oil is the
            # parent total for A1 purposes; the disclosed constituent row is
            # the clinically meaningful amount. Keep this narrower than
            # all fatty-acid rows so products with distinct oil sources
            # (fish oil plus borage/coffee/etc.) remain additive.
            group_canonical_id = str(group[0].get("canonical_id") or "").strip().lower()
            if group_canonical_id in omega_parent_total_canonicals:
                has_total_omega_child = any(
                    bool(child.get("is_nested_ingredient", False))
                    and _is_total_omega_constituent_blend(child.get("parent_blend"))
                    for child in group
                )
                if has_total_omega_child:
                    for parent in group:
                        if not bool(parent.get("is_nested_ingredient", False)):
                            parent["is_parent_total"] = True

            for ing in group:
                if bool(ing.get("is_nested_ingredient", False)):
                    continue
                ing_name = self._normalize_text(ing.get("name", "") or "")
                if ing_name and ing_name in parent_blend_names:
                    ing["is_parent_total"] = True

    def _match_multi_form(self, form_info: Dict, quality_map: Dict,
                          cleaner_canonical_id: Optional[str] = None) -> Optional[Dict]:
        """
        Match multiple extracted forms and aggregate scores using weighted average.

        Multi-Form Contract:
        - extracted_forms: list of form info dicts from extraction
        - matched_forms: list of {form_key, bio_score, natural, match_method, percent_share}
        - unmapped_forms: list of raw strings that failed to match
        - aggregation_method: 'weighted' | 'equal' | 'single'
        - final_form_bio_score: numeric (0-15) - the aggregated score

        Phase 3: when ``cleaner_canonical_id`` names an IQM parent, each
        per-form recursive lookup is constrained to that parent so a form
        alias (e.g., "phospholipid complex" → lecithin) cannot win over
        the cleaner's parent decision (milk_thistle via the silybin /
        siliphos / silipide reverse-index hit).

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
        # If the cleaner has already resolved an IQM parent, it beats the
        # base-name inference (Phase 3 authority).
        if (
            cleaner_canonical_id
            and isinstance(cleaner_canonical_id, str)
            and cleaner_canonical_id in quality_map
            and not cleaner_canonical_id.startswith("_")
        ):
            preferred_parent = cleaner_canonical_id

        matched_forms = []
        unmapped_forms = []
        generic_form_tokens = []
        cleaner_canonical_enforced_by_form = False
        cleaner_canonical_fallback_by_form = False
        _non_epa_dha_source_re = re.compile(
            r"\b("
            r"mct|medium\s+chain\s+triglycerides?|coconut|caprylic|capric|palm|"
            r"flax(?:seed)?|linseed|alpha[-\s]?linolenic|ala|chia|hemp|"
            r"evening\s+primrose|borage|gamma[-\s]?linolenic|gla|"
            r"conjugated\s+linoleic|cla|omega[-\s]?6|omega[-\s]?9|"
            r"fiber|fibre|seed\s+blend|super\s+seed"
            r")\b",
            re.IGNORECASE,
        )
        _epa_dha_source_re = re.compile(
            r"\b(epa|dha|eicosapentaenoic|docosahexaenoic)\b",
            re.IGNORECASE,
        )
        _omega_form_parent_keys = {"epa", "dha", "epa_dha", "fish_oil", "omega_3"}
        _source_identity_blob = " ".join(
            str(value or "")
            for value in (
                form_info.get("original"),
                form_info.get("base_name"),
            )
        )
        _has_non_epa_dha_source_context = bool(_non_epa_dha_source_re.search(_source_identity_blob))
        _has_epa_dha_source_context = bool(_epa_dha_source_re.search(_source_identity_blob))

        def _reject_false_omega_form_match(form_match: Optional[Dict]) -> bool:
            if not form_match:
                return False
            parent_key = str(form_match.get("canonical_id") or "").strip().lower()
            return (
                parent_key in _omega_form_parent_keys
                and _has_non_epa_dha_source_context
                and not _has_epa_dha_source_context
            )

        for form_data in extracted_forms:
            match_candidates = form_data.get('match_candidates', [])
            percent_share = form_data.get('percent_share', 1.0 / max(1, len(extracted_forms)))
            raw_form_text = form_data.get('raw_form_text', '')

            # Phase 2: Short-circuit on DSLD structural signals.
            # When the cleaner preserved `forms[].category` from raw DSLD and
            # it indicates a SOURCE DESCRIPTOR (animal tissue, plant part) or
            # the prefix marks the form as a source/culture reference, skip
            # the form-alias match entirely. These forms name the ORIGIN of
            # the nutrient, not its chemical form — forcing them through the
            # matcher produces false fallbacks and audit noise.
            _dsld_category = (form_data.get('dsld_category') or '').lower().strip()
            _dsld_prefix = (form_data.get('dsld_prefix') or '').lower().strip()
            # Exception: "from"-prefix forms that are actually DELIVERY
            # TECHNOLOGIES (MicroActive cyclodextrin, phytosome, liposome,
            # chelate, etc.) are real form identifiers even though DSLD
            # tagged them with prefix="from". Don't short-circuit those.
            _is_delivery_tech_from_prefix = (
                _dsld_prefix == 'from'
                and self._should_keep_from_prefixed_form_as_actual(raw_form_text)
            )
            if (
                (
                    _dsld_category in _SOURCE_DESCRIPTOR_FORM_CATEGORIES
                    or _dsld_prefix in _SOURCE_DESCRIPTOR_FORM_PREFIXES
                )
                and not _is_delivery_tech_from_prefix
            ):
                # Treat as a generic/source descriptor — do not enter the
                # unmapped_forms pool; this prevents the form_fallback_audit
                # from flagging it as actionable.
                generic_form_tokens.append(raw_form_text)
                continue

            # Try each match candidate until one succeeds
            form_match = None
            matched_candidate = None
            matched_unspecified = False
            for candidate in match_candidates:
                form_match = self._match_quality_map(
                    candidate, candidate, quality_map, _form_extraction_attempt=True,
                    preferred_parent=preferred_parent,
                    cleaner_canonical_id=cleaner_canonical_id,
                )
                if form_match:
                    if form_match.get("cleaner_canonical_enforced"):
                        cleaner_canonical_enforced_by_form = True
                    if form_match.get("cleaner_canonical_fallback"):
                        cleaner_canonical_fallback_by_form = True
                    if _reject_false_omega_form_match(form_match):
                        form_match = None
                        continue
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
                # v3.6.0: force sourcing-neutral. Ignore any legacy
                # pre-computed `score` (IQM data still has natural+3
                # baked in — see ingredient_quality_map.json). Contract:
                # score == bio_score.
                score = bio_score
                matched_forms.append({
                    'form_key': form_match.get('form_id'),
                    'canonical_id': form_match.get('canonical_id'),
                    'bio_score': bio_score,
                    'natural': natural,
                    'score': score,  # v3.6.0: deprecated alias of bio_score
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
                    'cleaner_canonical_enforced': cleaner_canonical_enforced_by_form,
                    'cleaner_canonical_fallback': cleaner_canonical_fallback_by_form,
                    'cleaner_canonical_id': cleaner_canonical_id,
                }
            return None

        # Determine aggregation method
        if len(matched_forms) == 1:
            aggregation_method = 'single'
        elif any(f.get('percent_share') != matched_forms[0].get('percent_share') for f in matched_forms):
            aggregation_method = 'weighted'
        else:
            aggregation_method = 'equal'

        # Calculate against the full authored composition. Any unmatched or
        # undeclared share retains conservative unspecified-form quality (5)
        # instead of being silently redistributed across matched forms.
        matched_weight = sum(f['percent_share'] for f in matched_forms)
        declared_weight = sum(
            float(f.get('percent_share') or 0.0) for f in extracted_forms
        )
        if declared_weight <= 1.0:
            unmatched_weight = max(0.0, 1.0 - matched_weight)
        else:
            unmatched_weight = max(0.0, declared_weight - matched_weight)
        total_weight = matched_weight + unmatched_weight
        if total_weight > 0:
            final_bio_score = sum(
                f['bio_score'] * f['percent_share'] for f in matched_forms
            )
            final_bio_score = (
                final_bio_score + (5.0 * unmatched_weight)
            ) / total_weight
            final_score = sum(
                f['score'] * f['percent_share'] for f in matched_forms
            )
            final_score = (final_score + (5.0 * unmatched_weight)) / total_weight
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
            'matched_percent_total': matched_weight,
            'unmatched_percent_total': unmatched_weight,

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

        for key in (
            "cleaner_canonical_id",
            "cleaner_canonical_enforced",
            "cleaner_canonical_fallback",
            "cleaner_canonical_cross_parent_allowed",
        ):
            if key in primary_match:
                result[key] = primary_match[key]

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

        # Biological origin/culture prefixes: these describe the fermentation or
        # growth substrate (e.g. "Lactobacillus bulgaricus" with prefix
        # "from culture of").  They must be skipped entirely — do NOT promote
        # their names as source candidates, because S. cerevisiae / L. bulgaricus
        # would override the ingredient's correct canonical_id (e.g. whole-food
        # vitamins → probiotics false mapping seen in Garden-of-Life products).
        _CULTURE_PREFIXES = frozenset({
            'from culture of',
            'and culture of',
            'culture of',
            'naturally occurring from',
            'derived from',
        })

        # YEAST-CULTURE FORM INJECTION: "Thiamine from S. cerevisiae culture"
        # encodes the fermentation organism as a form descriptor. Cross-parent
        # alias uniqueness prevents IQM alias addition for this text, so the
        # enricher injects the ingredient-specific IQM yeast alias as a virtual
        # form. Only covers vitamins with a known yeast IQM form (B1, B2, B9).
        _CEREVISIAE_CULTURE_RE = re.compile(
            r'\b(?:S\.?\s*cerevisiae|Saccharomyces\s+cerevisiae)'
            r'(?:\s+(?:culture|extract))?\b',
            re.IGNORECASE,
        )
        # ing_name substring (lower) → IQM alias string in the yeast form
        _CEREVISIAE_YEAST_ALIAS: Dict[str, str] = {
            'thiamine':   "brewer's yeast thiamine",
            'vitamin b1': "brewer's yeast thiamine",
            'riboflavin': 'yeast riboflavin',
            'vitamin b2': 'yeast riboflavin',
            'biotin':     'yeast biotin',
            'vitamin b7': 'yeast biotin',
            'folate':     'yeast folate',
            'vitamin b9': 'yeast folate',
            'folic acid': 'yeast folate',
            'vitamin k':  'yeast vitamin k2',
            'vitamin k2': 'yeast vitamin k2',
        }

        # Chemical salt/chelate qualifier words: when DSLD forms[] provides only
        # a bare qualifier (e.g., {name: "citrate"} from "Magnesium Citrate"),
        # the full ingredient label IS the form descriptor.  Prepend ing_name as
        # the first match candidate so IQM aliases like "magnesium citrate" resolve.
        _SALT_QUALIFIERS = frozenset({
            'acetate', 'anhydrous', 'arginate', 'ascorbate', 'aspartate',
            'bisglycinate', 'bromide', 'butyrate', 'carbonate', 'chelate',
            'chelated', 'chloride', 'citrate', 'dihydrate', 'fluoride',
            'fumarate', 'gluconate', 'glycinate', 'hcl', 'hydrochloride',
            'iodide', 'lactate', 'malate', 'maleate', 'monohydrate', 'nitrate',
            'orotate', 'oxide', 'palmitate', 'phosphate', 'picolinate',
            'propionate', 'stearate', 'succinate', 'sulfate', 'taurate',
            'tartrate', 'threonate',
        })

        # Adjective/certification words that appear as bare form tokens: these are
        # DSLD parsing artifacts (e.g., {name: "organic"} from "organic Maca").
        # They carry no form information — skip entirely.
        _ADJECTIVE_QUALIFIERS = frozenset({
            'bioactive', 'bioactives', 'certified', 'deodorized', 'fermented',
            'extract', 'natural', 'non-gmo', 'organic', 'pure', 'raw',
            'standardized', 'wild',
        })

        from_source_map: Dict[int, str] = {}  # index → source name
        for i, form in enumerate(cleaned_forms):
            prefix = (form.get('prefix') or '').strip()
            keep_as_form = self._should_keep_from_prefixed_form_as_actual(form.get('name', ''))
            if prefix in _FROM_PREFIXES and i > 0 and not keep_as_form:
                src = (form.get('name') or '').strip()
                if src:
                    from_source_map[i - 1] = src

        extracted_forms = []
        for i, form in enumerate(cleaned_forms):
            prefix = (form.get('prefix') or '').strip()
            keep_from_prefixed_form = (
                prefix in _FROM_PREFIXES
                and self._should_keep_from_prefixed_form_as_actual(form.get('name', ''))
            )
            # Skip biological culture/origin descriptors entirely — these name
            # the fermentation substrate or organism, not the ingredient's form.
            if prefix in _CULTURE_PREFIXES:
                continue
            # Skip forms that are source descriptors (prefix "from"):
            # their names are already inserted as priority candidates for the
            # preceding form via from_source_map.
            if prefix in _FROM_PREFIXES and not keep_from_prefixed_form:
                # YEAST-CULTURE INJECTION: if this "from"-sourced form names a
                # S. cerevisiae culture, translate it to the ingredient-specific
                # IQM yeast alias so the yeast form is reached without violating
                # cross-parent alias uniqueness.
                candidate_name = (form.get('name') or '').strip()
                if candidate_name and _CEREVISIAE_CULTURE_RE.search(candidate_name):
                    ing_lower = ing_name.lower()
                    yeast_alias = next(
                        (alias for key, alias in _CEREVISIAE_YEAST_ALIAS.items()
                         if key in ing_lower),
                        None,
                    )
                    if yeast_alias:
                        extracted_forms.append({
                            'raw_form_text': candidate_name,
                            'match_candidates': [yeast_alias],
                            'display_form': candidate_name,
                            'percent_share': None,
                        })
                continue

            form_name = form.get('name', '')
            if not form_name or not form_name.strip():
                continue

            # Skip adjective/certification qualifiers — DSLD parsing artifacts
            # (e.g., {name: "organic"} split from "organic Maca").  These carry
            # no form information and would pollute match_candidates.
            if form_name.strip().lower() in _ADJECTIVE_QUALIFIERS:
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

            # SALT QUALIFIER RESOLUTION: when DSLD forms[] provides only a bare
            # chemical qualifier (e.g., "citrate" from "Magnesium Citrate"), the
            # full ingredient label is the actual form descriptor.  Prepend it so
            # IQM aliases like "magnesium citrate" are tried first.
            form_name_lower = form_name.strip().lower()
            if form_name_lower in _SALT_QUALIFIERS:
                ing_stripped = ing_name.strip()
                if ing_stripped and ing_stripped not in match_candidates:
                    match_candidates.insert(0, ing_stripped)

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
            #
            # GUARD: Skip when form_name is already a word/suffix in ing_name.
            # Prevents "Milk Thistle Extract" + "extract" → "Milk Thistle Extract extract".
            form_name_norm = form_name_lower.strip()
            ing_name_lower = ing_name.lower()
            form_already_in_name = bool(
                re.search(r'(?<![a-z])' + re.escape(form_name_norm) + r'(?![a-z])', ing_name_lower)
            )
            if not form_already_in_name:
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
                # Phase 2: preserve DSLD structural signals from the cleaner
                # so `_match_multi_form` can short-circuit source descriptors
                # without relying on text heuristics.
                'dsld_category': form.get('category'),
                'dsld_prefix': form.get('prefix'),
                'dsld_ingredient_group': form.get('ingredientGroup'),
                'dsld_unii_code': form.get('uniiCode'),
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

    def _should_keep_from_prefixed_form_as_actual(self, form_name: str) -> bool:
        """
        Some DSLD rows use prefix='from' for delivery systems rather than source materials.

        Example: "Coenzyme Q10 (Form: from MicroActive Q10-Cyclodextrin Complex)".
        Those should remain matchable forms; true provenance rows like "from Pineapple"
        should continue to be skipped.
        """
        if not form_name:
            return False

        normalized = self._normalize_text(form_name)
        delivery_tokens = (
            'cyclodextrin',
            'microactive',
            'phytosome',
            'liposome',
            'liposomal',
            'vesisorb',
            'sustained release',
            'sustained-release',
            'phospholipid complex',
            # Chelate delivery class: DSLD tags mineral chelate forms with prefix='from'
            # (e.g. "Chromium (from Brown Rice Chelate)") — the chelate IS the form,
            # not a source material.  Matches "chelate", "chelated", "chelation", etc.
            'chelate',
        )
        return any(token in normalized for token in delivery_tokens)

    def _match_quality_map(self, ing_name: str, std_name: str, quality_map: Dict,
                           _form_extraction_attempt: bool = False,
                           cleaned_forms: Optional[List[Dict]] = None,
                           preferred_parent: Optional[str] = None,
                           branded_token: Optional[str] = None,
                           cleaner_canonical_id: Optional[str] = None) -> Optional[Dict]:
        """Memoizing wrapper around :meth:`_match_quality_map_impl`.

        The match result is a pure function of these arguments plus the static
        (within a run) quality_map, so repeated ingredient labels — ubiquitous in
        real catalogs — are matched once instead of re-running the full
        exact→alias→token→fuzzy cascade per occurrence. The key includes EVERY
        result-affecting argument (notably ``cleaner_canonical_id``, which
        hard-constrains the matched parent) plus ``id(quality_map)`` so a custom
        map passed to the same instance can't return a stale result. Returns a
        deep copy so callers may freely mutate the result without poisoning the
        cache. Telemetry counters/trackers updated inside the impl are
        intentionally NOT re-incremented on a cache hit — they are diagnostic,
        not part of the scored output.
        """
        try:
            key = json.dumps(
                [
                    ing_name, std_name, _form_extraction_attempt, cleaned_forms,
                    preferred_parent, branded_token, cleaner_canonical_id,
                    id(quality_map),
                ],
                sort_keys=True, default=str,
            )
        except (TypeError, ValueError):
            # Unserializable argument (rare) → correctness over speed: bypass cache.
            return self._match_quality_map_impl(
                ing_name, std_name, quality_map, _form_extraction_attempt,
                cleaned_forms, preferred_parent, branded_token,
                cleaner_canonical_id,
            )

        if key in self._match_quality_cache:
            return copy.deepcopy(self._match_quality_cache[key])

        result = self._match_quality_map_impl(
            ing_name, std_name, quality_map, _form_extraction_attempt,
            cleaned_forms, preferred_parent, branded_token, cleaner_canonical_id,
        )
        # Store an isolated copy (defends against any impl-side aliasing) and
        # hand every caller its own isolated copy — the cache entry is immutable.
        self._match_quality_cache[key] = copy.deepcopy(result)
        return copy.deepcopy(result)

    def _match_quality_map_impl(self, ing_name: str, std_name: str, quality_map: Dict,
                                _form_extraction_attempt: bool = False,
                                cleaned_forms: Optional[List[Dict]] = None,
                                preferred_parent: Optional[str] = None,
                                branded_token: Optional[str] = None,
                                cleaner_canonical_id: Optional[str] = None) -> Optional[Dict]:
        """
        Match ingredient against quality map using explicit precedence rules.

        Precedence (highest to lowest):
        1. Configured match_rules priority
        2. Exact, normalized, then bounded pattern/contains tier
        3. Raw-label, standard-name, then base-name source

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
            branded_token: Optional branded token extracted at cleaning stage
                           (e.g., "KSM-66", "Leucoselect") used as final
                           fallback when form extraction fails
            cleaner_canonical_id: Authoritative IQM parent key resolved by the
                           cleaner (via the 17k-entry reverse index). When
                           supplied AND it's a top-level key in quality_map,
                           it HARD-CONSTRAINS the candidate pool to that parent
                           — text-inferred cross-parent matches can no longer
                           win. If the constrained pool is empty, we fall
                           back to a parent-level (unspecified-form) match
                           under the cleaner's canonical rather than silently
                           choosing the wrong parent. This is the Phase 3
                           medical-accuracy fix: Silybin Phytosome products
                           score as milk_thistle (not lecithin via the
                           "phospholipid complex" alias), and DCP-sourced
                           Phosphorus rows score as phosphorus (not calcium
                           via the DCP alias). Pass None for rows with no
                           cleaner-resolved IQM canonical.

        Logs structured warnings when multiple candidates exist in the winning tier.
        """
        def _try_branded_token_fallback() -> Optional[Dict]:
            """Last-resort fallback before returning FORM_UNMAPPED."""
            if _form_extraction_attempt:
                return None
            if not branded_token or not isinstance(branded_token, str):
                return None

            token = branded_token.strip()
            if not token:
                return None

            token_match = self._match_quality_map(
                token,
                std_name,
                quality_map,
                _form_extraction_attempt=True,
            )
            if not token_match:
                return None
            if isinstance(token_match, dict) and token_match.get("match_status") == "FORM_UNMAPPED":
                return None

            resolved = dict(token_match)
            resolved["branded_token_fallback_used"] = True
            resolved["branded_token"] = token
            resolved["original_label"] = ing_name
            return resolved

        generic_form_only_descriptors = {
            "molecular distilled",
            "triglyceride form",
            "phospholipid form",
        }
        ing_norm = self._normalize_text(ing_name)
        std_norm = self._normalize_text(std_name)
        if ing_norm in generic_form_only_descriptors and std_norm in generic_form_only_descriptors:
            return None

        # Phase 3: resolve the cleaner's IQM canonical_id up-front so every
        # downstream branch (multi-form fast-path, combined-forms lookup,
        # parent fallback, final tier sort) can reference it without having
        # to pass the raw arg through every code path. The variable is None
        # when the cleaner did not resolve an IQM parent (e.g., botanical
        # canonicals, unresolved rows, or internal recursive calls).
        cleaner_iqm_canonical: Optional[str] = None
        if (
            cleaner_canonical_id
            and isinstance(cleaner_canonical_id, str)
            and cleaner_canonical_id in quality_map
            and not cleaner_canonical_id.startswith("_")
        ):
            cleaner_iqm_canonical = cleaner_canonical_id
        cleaner_form_constraint_enforced = False
        cleaner_form_constraint_fallback = False

        # MULTI-FORM MATCHING: Try structured cleaned_forms first, then fall back
        # to label text extraction. This fixes the "form loss" issue where cleaning
        # already parsed "Vitamin A (as Retinyl Palmitate)" into forms[] but the
        # enricher was only seeing "Vitamin A".
        if not _form_extraction_attempt:
            # PRIORITY 1: Use cleaned_forms[] from cleaning stage (structured, reliable)
            if cleaned_forms and isinstance(cleaned_forms, list) and len(cleaned_forms) > 0:
                form_info = self._build_form_info_from_cleaned(ing_name, cleaned_forms)
                if form_info and form_info.get('form_extraction_success'):
                    multi_form_result = self._match_multi_form(
                        form_info, quality_map,
                        cleaner_canonical_id=cleaner_iqm_canonical,
                    )
                    if multi_form_result:
                        if multi_form_result.get("cleaner_canonical_enforced"):
                            cleaner_form_constraint_enforced = True
                        if multi_form_result.get("cleaner_canonical_fallback"):
                            cleaner_form_constraint_fallback = True
                        if not multi_form_result.get('all_forms_generic'):
                            # Branded tokens (KSM-66, Sensoril, etc.) are more specific than
                            # DSLD sub-form labels like "Ashwagandha Root Extract". If the
                            # branded token resolves to a higher bio_score form, prefer it.
                            if branded_token:
                                branded_match = _try_branded_token_fallback()
                                if (branded_match
                                        and branded_match.get('form_id')
                                        and 'unspecified' not in branded_match.get('form_id', '').lower()
                                        and branded_match.get('bio_score', 0) > multi_form_result.get('bio_score', 0)):
                                    return branded_match
                            return multi_form_result

                    # If form evidence exists but ALL forms failed to match
                    if form_info.get('has_form_evidence') and not (
                        multi_form_result and multi_form_result.get('all_forms_generic')
                    ):
                        # PRIORITY 1.5: Try combined forms text as a single lookup.
                        # DSLD labels like "Camellia sinensis extract, Phospholipid complex"
                        # are split into individual forms by the parser, but the IQM alias
                        # may cover the full combined text (e.g., phytosome descriptors).
                        combined_forms = ", ".join(
                            f.get('raw_form_text', '') for f in form_info.get('extracted_forms', [])
                            if f.get('raw_form_text')
                        )
                        if combined_forms:
                            combined_match = self._match_quality_map(
                                combined_forms, std_name, quality_map, _form_extraction_attempt=True,
                                preferred_parent=preferred_parent if 'preferred_parent' in dir() else None,
                                cleaner_canonical_id=cleaner_iqm_canonical,
                            )
                            if combined_match and combined_match.get('form_id') and 'unspecified' not in combined_match.get('form_id', '').lower():
                                combined_match['combined_form_match'] = True
                                combined_match['original_label'] = ing_name
                                return combined_match

                        # Fallback: try parent/base matching so product can still score
                        # conservatively while preserving form-unmapped telemetry.
                        fallback_base = form_info.get('base_name') or ing_name
                        fallback_match = self._match_quality_map(
                            fallback_base, std_name, quality_map, _form_extraction_attempt=True,
                            cleaner_canonical_id=cleaner_iqm_canonical,
                        )
                        if fallback_match:
                            # Try branded token before accepting a conservative (unspecified) match.
                            # This fixes branded extracts like Sensoril/KSM-66 whose form aliases
                            # exist in IQM but are never reached because the base parent match
                            # (→ unspecified) returns first.
                            branded_match = _try_branded_token_fallback()
                            if (branded_match and branded_match.get('form_id')
                                    and 'unspecified' not in branded_match.get('form_id', '').lower()):
                                return branded_match
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
                        branded_match = _try_branded_token_fallback()
                        if branded_match:
                            return branded_match
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
                multi_form_result = self._match_multi_form(
                    form_info, quality_map,
                    cleaner_canonical_id=cleaner_iqm_canonical,
                )
                if multi_form_result:
                    if multi_form_result.get("cleaner_canonical_enforced"):
                        cleaner_form_constraint_enforced = True
                    if multi_form_result.get("cleaner_canonical_fallback"):
                        cleaner_form_constraint_fallback = True
                    if not multi_form_result.get('all_forms_generic'):
                        # Branded tokens are more specific than label-extracted form text.
                        # If branded token resolves to a higher bio_score form, prefer it.
                        if branded_token:
                            branded_match = _try_branded_token_fallback()
                            if (branded_match
                                    and branded_match.get('form_id')
                                    and 'unspecified' not in branded_match.get('form_id', '').lower()
                                    and branded_match.get('bio_score', 0) > multi_form_result.get('bio_score', 0)):
                                return branded_match
                        return multi_form_result

                # If form evidence exists but ALL forms failed to match, mark as FORM_UNMAPPED
                if form_info['has_form_evidence'] and not (
                    multi_form_result and multi_form_result.get('all_forms_generic')
                ):
                    fallback_base = form_info.get('base_name') or ing_name
                    fallback_match = self._match_quality_map(
                        fallback_base, std_name, quality_map, _form_extraction_attempt=True,
                        cleaner_canonical_id=cleaner_iqm_canonical,
                    )
                    if fallback_match:
                        # Try branded token before accepting a conservative (unspecified) match.
                        branded_match = _try_branded_token_fallback()
                        if (branded_match and branded_match.get('form_id')
                                and 'unspecified' not in branded_match.get('form_id', '').lower()):
                            return branded_match
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
                    branded_match = _try_branded_token_fallback()
                    if branded_match:
                        return branded_match
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
                # First strip dosage with units (including probiotic CFU counts like "10 Billion CFU")
                stripped = re.sub(
                    r'\s+\d+(?:\.\d+)?\s*(?:billion|million)\s*(?:cfu|cfus|organisms|live\s+cultures?)?\s*$',
                    '', base_name, flags=re.IGNORECASE
                ).strip()
                stripped = re.sub(
                    r'\s+\d+(?:\.\d+)?\s*(?:mg|mcg|ug|µg|g|kg|ml|l|iu|cfu)\s*$',
                    '', stripped, flags=re.IGNORECASE
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
            if any(token in blob for token in compound_tokens):
                context_blob = " ".join(x for x in (std_norm_value, base_norm_value or "") if x)
                if re.search(r"\b(niacin|vitamin b3)\b", context_blob):
                    return "vitamin_b3_niacin"
                if re.search(r"\b(vitamin c|ascorbic acid|ascorbate)\b", context_blob):
                    return "vitamin_c"

                # Default when context is missing or mixed.
                return "vitamin_c"

            if "life's dha" in blob or "lifes dha" in blob:
                return "dha"

            if "concentrated fish oil" in blob:
                return "fish_oil"

            if "alpha linolenic" in blob or re.search(r"\bala\b", blob):
                return "alpha_linolenic_acid"
            if "flaxseed" in blob or "flax seed" in blob or "linseed" in blob:
                return "flaxseed"
            if "evening primrose" in blob:
                return "evening_primrose_oil"
            if "gamma linolenic" in blob or re.search(r"\bgla\b", blob):
                return "gamma_linolenic_acid"
            if "hemp seed" in blob:
                return "hemp_seed_oil"

            return None

        # Phase 3: the cleaner's authoritative IQM parent (resolved up-front
        # as ``cleaner_iqm_canonical``) beats text-inferred parent context —
        # it saw the DSLD ingredientGroup, full raw text, and
        # label_nutrient_context. Below, after candidates are built, it
        # also acts as a hard filter on the candidate pool so aliases
        # that cross parents (silybin phytosome → lecithin, DCP → calcium)
        # cannot win.
        if cleaner_iqm_canonical and not preferred_parent:
            preferred_parent = cleaner_iqm_canonical

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
        candidate_by_resolution: Dict[Tuple[str, Optional[str]], Dict] = {}
        _non_epa_dha_source_re = re.compile(
            r"\b("
            r"mct|medium\s+chain\s+triglycerides?|coconut|caprylic|capric|palm|"
            r"flax(?:seed)?|linseed|alpha[-\s]?linolenic|ala|chia|hemp|"
            r"evening\s+primrose|borage|gamma[-\s]?linolenic|gla|"
            r"conjugated\s+linoleic|cla|omega[-\s]?6|omega[-\s]?9|"
            r"fiber|fibre|seed\s+blend|super\s+seed"
            r")\b",
            re.IGNORECASE,
        )
        _epa_dha_source_re = re.compile(
            r"\b(epa|dha|eicosapentaenoic|docosahexaenoic)\b",
            re.IGNORECASE,
        )
        _false_omega_source_blob = " ".join(
            str(value or "")
            for value in (ing_name, std_name, base_name, ing_norm, std_norm, base_norm)
        )

        def _blocks_false_omega_parent(parent_key: str) -> bool:
            if parent_key not in {"epa", "dha", "epa_dha", "fish_oil", "omega_3"}:
                return False
            return (
                bool(_non_epa_dha_source_re.search(_false_omega_source_blob))
                and not bool(_epa_dha_source_re.search(_false_omega_source_blob))
            )

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
            # v3.6.0: force sourcing-neutral. Ignore legacy IQM `score` field
            # (still has natural+3 baked in). Contract: score == bio_score.
            # Natural signal is consumed by A5e in the scorer.
            score = bio_score

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

        def _resolved_candidate_form_id(candidate: Dict) -> Optional[str]:
            return (
                candidate.get("form_key")
                or candidate.get("fallback_form_name")
                or (candidate.get("match_data") or {}).get("form_id")
            )

        def _candidate_sort_key(candidate: Dict) -> Tuple:
            # Prefer candidate whose parent matches the base ingredient context.
            # This resolves compound forms like "calcium ascorbate" appearing under
            # both vitamin_c and calcium — when the base ingredient is "Vitamin C",
            # vitamin_c wins; when it's "Calcium", calcium wins.
            parent_pref = 0 if (preferred_parent and candidate["parent_key"] == preferred_parent) else 1
            return (
                candidate.get("priority", 1),           # 1. Configured priority (0 > 1 > 2)
                candidate["tier"],                      # 2. Tier (exact > normalized > contains/pattern)
                candidate.get("match_source", 1),       # 3. Match source (raw > std > base)
                parent_pref,                            # 4. Prefer parent matching base ingredient
                -candidate["alias_len"],                # 5. Longer alias wins within same priority
                0 if candidate["form_key"] else 1,      # 6. Form-level beats parent-level
                candidate["parent_key"],                # 7. Alphabetical parent key
                candidate["form_key"] or "",            # 8. Alphabetical form key
            )

        def _candidate_resolution_key(candidate: Dict) -> Tuple[str, Optional[str]]:
            return (
                str(candidate.get("parent_key") or ""),
                _resolved_candidate_form_id(candidate),
            )

        def add_candidate(candidate: Dict):
            if _blocks_false_omega_parent(str(candidate.get("parent_key") or "")):
                return

            # Multiple aliases often describe the same scoring identity
            # (canonical parent + resolved form). Collapse those paths here so
            # alias duplication cannot become warning-level ambiguity later.
            key = _candidate_resolution_key(candidate)
            existing = candidate_by_resolution.get(key)
            if existing is None:
                candidate_by_resolution[key] = candidate
                candidates.append(candidate)
                return

            if _candidate_sort_key(candidate) < _candidate_sort_key(existing):
                candidate_by_resolution[key] = candidate
                for idx, current in enumerate(candidates):
                    if current is existing:
                        candidates[idx] = candidate
                        break

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
                    if (_pd.get("match_rules") or {}).get("deprecated_in_favor_of"):
                        continue
                    if _pd.get('contains_aliases') or _pd.get('pattern_aliases'):
                        _candidate_parent_keys.add(_pk)

        for parent_key, parent_data in quality_map.items():
            if parent_key.startswith("_") or not isinstance(parent_data, dict):
                continue
            if (parent_data.get("match_rules") or {}).get("deprecated_in_favor_of"):
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

        # Phase 3 hard constraint — the cleaner's reverse-index decision wins.
        # Filter to candidates under the cleaner's IQM canonical_id so
        # text-inferred cross-parent matches (e.g., "phospholipid complex"
        # under lecithin when the cleaner resolved milk_thistle via the
        # silybin/siliphos/silipide aliases) are dropped before sort.
        cleaner_canonical_enforced = False
        cleaner_canonical_fallback = False
        cleaner_canonical_cross_parent_allowed = False

        def _is_allowed_cleaner_canonical_cross_parent(candidate: Dict) -> bool:
            if not cleaner_iqm_canonical:
                return False
            target_parent = candidate.get("parent_key")
            allowed_aliases = IQM_CANONICAL_CROSS_PARENT_ALLOWLIST.get(
                (cleaner_iqm_canonical, target_parent)
            )
            if not allowed_aliases:
                return False

            alias_blob = " ".join(
                str(value or "")
                for value in (
                    candidate.get("matched_alias"),
                    candidate.get("form_key"),
                    candidate.get("fallback_form_name"),
                )
            )
            if (cleaner_iqm_canonical, target_parent) == ("turmeric", "curcumin"):
                # Clinical-review policy: turmeric only upgrades to curcumin
                # when the form text explicitly declares curcuminoids or 95%
                # standardization. Plain "curcumin" / branded-token text is
                # not enough to overwrite the botanical parent.
                return (
                    "curcuminoid" in alias_blob.lower()
                    or re.search(r"\b95\s*%", alias_blob, flags=re.IGNORECASE) is not None
                )
            alias_blob_norm = self._normalize_text(alias_blob)
            return any(
                self._normalize_text(alias) in alias_blob_norm
                for alias in allowed_aliases
            )

        if cleaner_iqm_canonical and candidates:
            constrained = [c for c in candidates if c["parent_key"] == cleaner_iqm_canonical]
            if constrained:
                # Drop off-canonical candidates so they cannot win the tie-break.
                if len(constrained) != len(candidates):
                    cleaner_canonical_enforced = True
                candidates = constrained
            else:
                allowed_cross_parent = [
                    c for c in candidates
                    if _is_allowed_cleaner_canonical_cross_parent(c)
                ]
                if allowed_cross_parent:
                    cleaner_canonical_enforced = True
                    cleaner_canonical_cross_parent_allowed = True
                    candidates = allowed_cross_parent
                else:
                    # The cleaner resolved an IQM parent, but every form-text
                    # candidate pointed somewhere else. Treat that as no
                    # candidate so the existing parent fallback preserves the
                    # cleaner's canonical instead of silently crossing parents.
                    cleaner_canonical_enforced = True
                    cleaner_canonical_fallback = True
                    candidates = []

        if not candidates:
            # Cleaner emitted an IQM canonical but text match produced zero
            # candidates (or the hard-filter eliminated all) — fall back to a
            # parent-level match under the cleaner's canonical rather than
            # letting branded-token-fallback or FORM_UNMAPPED win. Prevents
            # the regression where a cleaner-resolved silybin row would
            # degrade to branded fallback if no silybin form matched.
            if cleaner_iqm_canonical:
                parent_data = quality_map.get(cleaner_iqm_canonical) or {}
                parent_match, fallback_selected, fallback_form = build_parent_match_data(
                    cleaner_iqm_canonical, parent_data
                )
                parent_match["canonical_id"] = cleaner_iqm_canonical
                parent_match["form_id"] = fallback_form
                parent_match["match_tier"] = "cleaner_canonical_parent"
                parent_match["matched_alias"] = cleaner_iqm_canonical
                parent_match["matched_target"] = "cleaner_canonical_id"
                parent_match["match_ambiguity_candidates"] = []
                parent_match["cleaner_canonical_enforced"] = True
                parent_match["cleaner_canonical_fallback"] = True
                parent_match["cleaner_canonical_id"] = cleaner_iqm_canonical
                parent_match["fallback_form_selected"] = fallback_selected
                parent_match["fallback_form_name"] = fallback_form
                return parent_match

            branded_match = _try_branded_token_fallback()
            if branded_match:
                return branded_match
            return None

        candidates.sort(key=_candidate_sort_key)
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
                        "resolved_form_id": _resolved_candidate_form_id(c),
                    }
                    for c in winning_candidates
                ],
                "chosen": {
                    "canonical_id": best["parent_key"],
                    "form_key": best["form_key"],
                    "resolved_form_id": _resolved_candidate_form_id(best),
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
        if cleaner_iqm_canonical:
            best["match_data"]["cleaner_canonical_id"] = cleaner_iqm_canonical
            best["match_data"]["cleaner_canonical_enforced"] = (
                cleaner_canonical_enforced or cleaner_form_constraint_enforced
            )
            if cleaner_canonical_cross_parent_allowed:
                best["match_data"]["cleaner_canonical_cross_parent_allowed"] = True
            if cleaner_canonical_fallback or cleaner_form_constraint_fallback:
                best["match_data"]["cleaner_canonical_fallback"] = True

        if match_tier == "pattern":
            self.match_counters["pattern_match_wins_count"] += 1
        elif match_tier == "contains":
            self.match_counters["contains_match_wins_count"] += 1

        if best["fallback_form_selected"]:
            # Only count + emit telemetry for top-level calls. Internal
            # recursive calls (form extraction attempts, branded-token fallback,
            # multi-form candidate resolution) and exploratory predicates like
            # _is_known_therapeutic pass _form_extraction_attempt=True; their
            # "best" is a transient intermediate, not the final enriched
            # outcome. Counting them produced spurious parent_fallback_report
            # rows where the final matched_form was actually a real form
            # (e.g., Pure Encapsulations Devil's Claw → harpagoside-standardized
            # form would leak a devil's claw (unspecified) fallback row).
            if not _form_extraction_attempt:
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
        physical_state = product.get('physicalState', {}).get('langualCodeDescription', '').lower()

        evidence_sources: List[Tuple[str, str]] = []
        for field in ("name", "fullName", "productName"):
            value = product.get(field)
            if isinstance(value, str) and value.strip():
                evidence_sources.append((field, value))
        for index, ingredient in enumerate(
            self._primary_active_ingredients_for_enrichment(product)
        ):
            if not isinstance(ingredient, dict):
                continue
            row_text = " ".join(
                str(ingredient.get(field) or "")
                for field in ("name", "raw_source_text", "standardName", "notes")
            ).strip()
            if row_text:
                evidence_sources.append((f"activeIngredients[{index}]", row_text))

        # Structured DSLD label statements are product-authored evidence. Keep
        # them separate from the broad synthesized product text, which also
        # contains reference notes and can manufacture delivery matches. An
        # untyped/free-form statement is deliberately not trusted here.
        trusted_statement_types = {
            "Formulation re: Other",
            "Suggested/Recommended/Usage/Directions",
            "FDA Statement of Identity",
        }
        for index, statement in enumerate(product.get("statements", [])):
            if not isinstance(statement, dict):
                continue
            if statement.get("type") not in trusted_statement_types:
                continue
            notes = statement.get("notes")
            if isinstance(notes, str) and notes.strip():
                evidence_sources.append((f"statements[{index}]", notes))

        matched_systems = []

        for delivery_name, delivery_data in delivery_db.items():
            if delivery_name.startswith("_") or not isinstance(delivery_data, dict):
                continue

            delivery_lower = delivery_name.lower().strip()
            pattern = re.compile(
                r"(?<![a-z0-9])" + re.escape(delivery_lower) + r"(?![a-z0-9])",
                flags=re.IGNORECASE,
            )

            match_source = None
            matched_text = None
            physical_match = pattern.search(physical_state)
            if physical_match:
                match_source = "physical_state"
                matched_text = physical_match.group(0)
            else:
                for source_path, source_text in evidence_sources:
                    row_match = pattern.search(source_text)
                    if row_match:
                        match_source = source_path
                        matched_text = row_match.group(0)
                        break

            if match_source:
                matched_systems.append({
                    # LABEL NAME PRESERVATION:
                    "name": delivery_name,  # Canonical from DB (used for scoring)
                    "canonical_name": delivery_name,  # Explicit canonical field
                    "raw_source_text": matched_text,
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

        # v3.0 scoring contract: enhancer pairing is ACTIVE-ONLY and must
        # follow the same primary-active contract used by Section A scoring.
        all_ingredients = self._primary_active_ingredients_for_enrichment(product)

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

        active_ingredients = self._primary_active_ingredients_for_enrichment(product)
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
                    # v3.7.0: UNIT-AWARE thresholds + tiered (0-4) standardization
                    # credit + per-entry bonus_class. min_threshold is only a
                    # PERCENT when standardization_unit is percent/empty; non-percent
                    # thresholds (GDU/g, mg_per_dose) must NOT be compared as "%".
                    std_unit = (botanical.get("standardization_unit") or "percent").strip().lower()
                    is_percent_unit = std_unit in ("", "percent", "%")

                    # bonus_class: an explicit data `bonus_class` wins (lets the
                    # file honestly mark non-botanicals — e.g. berberine/beta-glucans
                    # as isolated_compound — so category guessing can't grant them
                    # the full botanical tier). Else prefer standardization_basis,
                    # else derive from category. Downstream per-class caps then keep
                    # non-botanicals below the botanical_standardization tier.
                    explicit_class = (botanical.get("bonus_class") or "").strip().lower()
                    basis = (botanical.get("standardization_basis") or "").strip().lower()
                    cat = (botanical.get("category") or "").strip().lower()
                    if explicit_class:
                        bonus_class = explicit_class
                    elif basis in ("marker_percent", "mushroom_fraction", "branded_extract"):
                        bonus_class = basis
                    elif cat in ("mineral", "mineral_chelate", "mineral_complex"):
                        bonus_class = "branded_form"
                    elif cat in ("active_compound", "enzyme"):
                        bonus_class = "enzyme_activity"
                    elif cat in ("amino_acid", "nootropic", "tripeptide",
                                 "fatty_acid_amide", "hormone_analog",
                                 "structural_protein", "polysaccharide", "algal_oil"):
                        bonus_class = "isolated_compound"
                    elif bool(botanical.get("branded_form")):
                        bonus_class = "branded_form"
                    else:
                        bonus_class = "botanical_standardization"

                    evidence_source = "none"
                    tier = "none"
                    ratio = 0.0
                    is_branded = bool(botanical.get("branded_form"))
                    if is_branded:
                        # Branded standardized extracts (KSM-66, Cran-Max, FloraGLO,
                        # Meriva, ...) guarantee standardization by trademark.
                        evidence_source = "branded_form"
                        tier = "full"
                    elif min_threshold is not None and is_percent_unit:
                        if percentage > 0:
                            ratio = (percentage / min_threshold) if min_threshold else 0.0
                            evidence_source = f"percentage_{percentage_source}"
                            if ratio >= 1.0:
                                tier = "full"
                            elif ratio >= 0.75:
                                tier = "near_75"
                            elif ratio >= 0.5:
                                tier = "near_50"
                            else:
                                tier = "identity_only"
                        elif self._has_marker_word_match(markers, marker_text):
                            evidence_source = "marker_word_match"
                            tier = "identity_only"
                    elif min_threshold is not None and not is_percent_unit:
                        # Non-percent threshold (e.g. GDU/g, mg_per_dose): never
                        # compare as a percentage. Credit only via marker-word
                        # identity here (branded form already handled above).
                        if self._has_marker_word_match(markers, marker_text):
                            evidence_source = "marker_word_match"
                            tier = "identity_only"
                    else:
                        # No threshold and not branded — identity/marker only.
                        if percentage > 0:
                            evidence_source = f"percentage_{percentage_source}"
                            tier = "identity_only"
                        elif self._has_marker_word_match(markers, marker_text):
                            evidence_source = "marker_word_only"
                            tier = "identity_only"

                    # meets_threshold kept for backward-compat consumers: True when
                    # the marker reaches >=75% of the standardization target.
                    meets_threshold = tier in ("full", "near_75")

                    found_botanicals.append({
                        "name": ing_name,
                        "botanical_id": botanical.get('id', ''),
                        "standard_name": bot_name,
                        "markers": markers,
                        "percentage_found": percentage,
                        "percentage_source": percentage_source if percentage > 0 else None,
                        "min_threshold": min_threshold,
                        "standardization_unit": std_unit,
                        "threshold_ratio": round(ratio, 3),
                        "tier": tier,
                        "bonus_class": bonus_class,
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

    # -------------------------------------------------------------------------
    # Solution B — Product-name fallback synthesizer
    # -------------------------------------------------------------------------
    # Strict allowlist of (regex, canonical_name, default_unit) for products
    # whose name unambiguously declares a clinical headline nutrient + dose.
    # MUST be biochem-specific. NEVER add generic marketing terms ("support",
    # "complex", "blend", "formula", "boost"). Anything ending in those is
    # rejected by the synthesizer as ambiguous.
    _NAME_FALLBACK_PATTERNS: List[Tuple[str, str, str]] = [
        (r'\bDHA\s+([\d,]+\.?\d*)\s*(mg|g)\b',           'DHA',           'mg'),
        (r'\bEPA\s+([\d,]+\.?\d*)\s*(mg|g)\b',           'EPA',           'mg'),
        (r'\bMagnesium\s+([\d,]+\.?\d*)\s*(mg|g)\b',     'Magnesium',     'mg'),
        (r'\bCalcium\s+([\d,]+\.?\d*)\s*(mg|g)\b',       'Calcium',       'mg'),
        (r'\bIron\s+([\d,]+\.?\d*)\s*(mg|mcg)\b',        'Iron',          'mg'),
        (r'\bZinc\s+([\d,]+\.?\d*)\s*(mg|mcg)\b',        'Zinc',          'mg'),
        (r'\bVitamin\s+C\s+([\d,]+\.?\d*)\s*(mg|g)\b',   'Vitamin C',     'mg'),
        (r'\bVitamin\s+D[3]?\s+([\d,]+\.?\d*)\s*(iu|mcg|mg)\b', 'Vitamin D3', 'IU'),
        (r'\bVitamin\s+B[\s-]*12\s+([\d,]+\.?\d*)\s*(mcg|mg)\b', 'Vitamin B12', 'mcg'),
        (r'\bCoQ[\s-]?10\s+([\d,]+\.?\d*)\s*(mg|g)\b',   'CoQ10',         'mg'),
        (r'\bMelatonin\s+([\d.,]+)\s*(mg|mcg)\b',        'Melatonin',     'mg'),
        (r'\bBiotin\s+([\d,]+\.?\d*)\s*(mcg|mg)\b',      'Biotin',        'mcg'),
        (r'\bCreatine\s+([\d.,]+)\s*(g|mg)\b',           'Creatine',      'g'),
        (r'\bCollagen\s+([\d,]+\.?\d*)\s*(mg|g)\b',      'Collagen',      'mg'),
        (r'\bAshwagandha\s+([\d,]+\.?\d*)\s*(mg|g)\b',   'Ashwagandha',   'mg'),
        (r'\bTurmeric\s+([\d,]+\.?\d*)\s*(mg|g)\b',      'Turmeric',      'mg'),
        (r'\bCurcumin\s+([\d,]+\.?\d*)\s*(mg|g)\b',      'Curcumin',      'mg'),
    ]

    # Marketing/composition words that signal an ambiguous product (multi-
    # ingredient blend, marketing-positioned). When the product name ends
    # with one of these, we do NOT synthesize even if a pattern matches.
    _NAME_FALLBACK_BLOCK_SUFFIXES: Tuple[str, ...] = (
        'support', 'complex', 'blend', 'formula', 'boost', 'matrix',
        'system', 'pack', 'bundle', 'kit',
    )

    def _synthesize_ingredients_from_name(
        self,
        product: Dict,
        active_ingredients: List[Dict],
    ) -> Tuple[List[Dict], List[Dict]]:
        """Solution B — Inject a synthetic active ingredient when the product
        name declares an unambiguous biochem nutrient + dose AND the parser
        clearly missed it (sparse activeIngredients).

        Gates (ALL must hold):
          1. ``len(active_ingredients) <= 2``  (sparse parse signal)
          2. Product name contains a strict-allowlist nutrient + dose pattern
          3. The matched canonical nutrient is NOT already in activeIngredients
             (under any spelling)
          4. Product name does not end in a marketing/composition word
             ('Complex', 'Support', 'Blend', etc.)
          5. Single-pattern cap when actives>0 (only synthesize the FIRST
             named nutrient if some actives already exist; avoids stacking
             inferred + parsed for compound products like
             "Calcium 600 mg + D Plus Minerals")

        Returns (synthetic_active_ingredients, synthetic_display_entries).
        Each synthetic ingredient carries ``provenance="product_name_fallback"``
        and ``confidence="inferred_high"`` for downstream audit.
        """
        if len(active_ingredients) > 2:
            return [], []

        # Read the product display name. The raw cleaned input uses DSLD's
        # camelCase fields (productName / fullName) — the enricher renames
        # fullName -> product_name on the `enriched` dict at line ~12234, but
        # _collect_synergy_data is called with the RAW `product` dict, which
        # still carries the original field names. Check all three so the
        # synthesizer fires regardless of call site (enrich_product pipeline,
        # or direct _collect_synergy_data invocation from tests/canaries).
        name = (
            product.get('product_name')
            or product.get('fullName')
            or product.get('productName')
            or ''
        ).strip()
        if not name:
            return [], []

        # Block ambiguous marketing names (rule #4)
        name_lower = name.lower()
        for blocker in self._NAME_FALLBACK_BLOCK_SUFFIXES:
            if name_lower.endswith(' ' + blocker) or name_lower.endswith(' ' + blocker + 's'):
                return [], []

        # Build the set of canonical nutrient names already present in actives
        # (under ANY spelling we know). We check (a) exact normalize matches,
        # (b) cluster aliases.
        alias_db = self.databases.get('cluster_ingredient_aliases', {}) or {}
        alias_map = alias_db.get('aliases', {}) if isinstance(alias_db, dict) else {}
        # canonical_norm → set of variant_norm (including canonical itself)
        all_known_terms_for_canon: Dict[str, set] = {}
        for canon, variants in alias_map.items():
            if not isinstance(canon, str): continue
            terms = {self._normalize_text(canon)}
            if isinstance(variants, list):
                for v in variants:
                    if isinstance(v, str):
                        terms.add(self._normalize_text(v))
            all_known_terms_for_canon[self._normalize_text(canon)] = terms

        existing_norm: set = set()
        for ing in active_ingredients:
            for k in ('standardName', 'name'):
                v = ing.get(k)
                if v:
                    existing_norm.add(self._normalize_text(v))

        def _already_present(canonical_norm: str) -> bool:
            # direct match
            for en in existing_norm:
                if canonical_norm == en or canonical_norm in en or en in canonical_norm:
                    return True
            # alias-aware match
            terms = all_known_terms_for_canon.get(canonical_norm, {canonical_norm})
            for term in terms:
                if not term: continue
                for en in existing_norm:
                    if term == en or term in en or en in term:
                        return True
            return False

        synthetic_actives: List[Dict] = []
        synthetic_display: List[Dict] = []
        single_pattern_cap = len(active_ingredients) > 0  # rule #5

        for pattern, canonical_name, default_unit in self._NAME_FALLBACK_PATTERNS:
            m = re.search(pattern, name, re.IGNORECASE)
            if not m:
                continue
            try:
                qty = float(m.group(1).replace(',', ''))
            except (ValueError, AttributeError):
                continue
            unit = (m.group(2) or default_unit).lower()
            # Normalize IU/mcg/mg cosmetics
            if unit == 'iu':
                unit = 'IU'

            canonical_norm = self._normalize_text(canonical_name)
            if _already_present(canonical_norm):
                continue

            synthetic_actives.append({
                'name':         canonical_name,
                'standardName': canonical_name,
                'quantity':     qty,
                'unit':         unit,
                'provenance':   'product_name_fallback',
                'confidence':   'inferred_high',
                'inferred_from': name,
            })
            synthetic_display.append({
                'raw_source_text': name,
                'display_name':    canonical_name,
                'source_section':  DISPLAY_LEDGER_SOURCE_PRODUCT_NAME,
                'display_type':    'inferred_from_name',
                'resolution_type': 'product_name_fallback',
                'score_included':  False,
                'mapped_to': {
                    'standard_name':  canonical_name,
                    'source_section': 'inferred',
                    'raw_source_path': 'product_name',
                },
                'confidence': 'inferred_high',
            })

            # Single-pattern cap (rule #5): if actives existed pre-synthesis,
            # only inject the FIRST matched headline. For empty-actives
            # products, inject up to 2 to handle dual-named products like
            # "Calcium 600 mg + Vitamin D3 1000 IU" — but no more than 2.
            if single_pattern_cap:
                break
            if len(synthetic_actives) >= 2:
                break

        return synthetic_actives, synthetic_display

    def _collect_synergy_data(self, product: Dict) -> List[Dict]:
        """Collect synergy cluster data"""
        synergy_db = self.databases.get('synergy_cluster', {})
        clusters = synergy_db.get('synergy_clusters', [])
        # Per-nutrient unit for each min_effective_dose threshold (single source of
        # truth; default "mg"). Thresholds are authored in native units — most mg,
        # but methylcobalamin/folate/B12/biotin/iodine/chromium/selenium/K2 in mcg,
        # vitamin D in IU, probiotics in CFU. Used to convert the product amount to
        # the threshold's unit before the adequacy comparison.
        dose_units = synergy_db.get('min_effective_dose_units', {}) or {}

        # Cluster-ingredient alias map (Solution A): canonical-form → variants
        # used by supplement labels in the wild. Recovers products where DSLD
        # parser writes "coenzyme q10" but the cluster ingredient is "coq10".
        # Loaded from scripts/data/cluster_ingredient_aliases.json.
        alias_db = self.databases.get('cluster_ingredient_aliases', {})
        alias_map_raw = alias_db.get('aliases', {}) if isinstance(alias_db, dict) else {}
        # Pre-normalize: {canonical_norm → frozenset(variant_norm,...)}
        alias_map_norm = {
            self._normalize_text(canon): frozenset(
                self._normalize_text(v) for v in variants if isinstance(v, str)
            )
            for canon, variants in alias_map_raw.items()
            if isinstance(canon, str) and isinstance(variants, list)
        }

        active_ingredients = self._primary_active_ingredients_for_enrichment(product)

        # Solution B: product-name fallback. When activeIngredients is sparse
        # (≤2 entries) and the product name contains an unambiguous biochem
        # nutrient + dose pattern, synthesize a virtual ingredient with
        # provenance flag. Recovers products like "DHA 1,000 mg Lemon Flavor"
        # whose actives only contain DPA because the parser missed the
        # carrier-derived DHA.
        #
        # IMPORTANT — scoring isolation: synthetic ingredients are used ONLY
        # for the synergy cluster + goal matching path below. They are NOT
        # written back into ``product["activeIngredients"]`` because the
        # ingredient_quality scorer (Section A) uses the same field, and we
        # don't want product-name-derived ingredients to count toward A1
        # core-quality scoring. The dev review explicitly warned: "avoid
        # contaminating scoring blindly". Provenance lives in the
        # display_ingredients audit channel for QA visibility.
        synthetic_ingredients, synthetic_display_entries = (
            self._synthesize_ingredients_from_name(product, active_ingredients)
        )
        if synthetic_ingredients:
            # Local-only union for cluster matching
            active_ingredients = list(active_ingredients) + synthetic_ingredients
            existing_display = product.get('display_ingredients') or []
            if isinstance(existing_display, list):
                product['display_ingredients'] = existing_display + synthetic_display_entries

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
            # Track which product ingredients have already been counted against
            # this cluster. Prevents a single product ingredient (e.g.
            # "Magnesium 17 mg") from satisfying the synergy gate by matching
            # multiple cluster-ingredient variants ("magnesium", "magnesium
            # glycinate"). Each product ingredient counts at most once per
            # cluster. See CANARY report, whey+trace-mineral false positive.
            matched_product_keys: set = set()

            # Resolve the strictest known min_effective_dose for a cluster
            # ingredient, inheriting from shorter keys when variants aren't
            # explicitly dosed (e.g. "magnesium glycinate" inherits
            # min_dose from "magnesium"). Falls back to 0 when no dose is
            # defined anywhere.
            def _resolve_min_dose(cluster_ing_norm: str, cluster_ing_raw: str):
                """Return (min_dose, matched_key) for a cluster ingredient.

                The matched key selects the threshold's unit from ``dose_units``.
                """
                # 1) exact normalized key
                if cluster_ing_norm in min_doses:
                    return min_doses[cluster_ing_norm], cluster_ing_norm
                # 2) exact raw key (legacy compat)
                if cluster_ing_raw in min_doses:
                    return min_doses[cluster_ing_raw], cluster_ing_raw
                # 3) longest prefix match from available dose keys
                best = 0
                best_key = None
                best_key_len = 0
                for k, v in min_doses.items():
                    if not isinstance(k, str):
                        continue
                    k_norm = self._normalize_text(k)
                    if k_norm and k_norm in cluster_ing_norm and len(k_norm) > best_key_len:
                        best = v
                        best_key = k
                        best_key_len = len(k_norm)
                return best, best_key

            for cluster_ing in cluster_ingredients:
                cluster_ing_norm = self._normalize_text(cluster_ing)
                # Resolve aliases for this cluster ingredient (Solution A).
                # The match attempt below tries the cluster ingredient itself
                # first, then each alias if no direct match. Aliases catch
                # parser/spelling mismatches (CoQ10 vs coenzymeq10) without
                # touching the IQM scoring path.
                cluster_ing_aliases = alias_map_norm.get(cluster_ing_norm, frozenset())

                # Check if this cluster ingredient is in product
                for ing_key, ing_data in ingredient_info.items():
                    if ing_key in matched_product_keys:
                        continue  # already counted via another cluster variant

                    # Prefer exact match to avoid false positives (e.g. "EPA" in "HEPATIC")
                    is_match = False
                    if cluster_ing_norm == ing_key:
                        is_match = True
                    # Loose substring match for long terms (>= 6 chars).
                    elif len(cluster_ing_norm) >= 6 and len(ing_key) >= 6:
                        if cluster_ing_norm in ing_key or ing_key in cluster_ing_norm:
                            is_match = True
                    # Word-boundary match for short biochemistry abbreviations
                    # (DHA, EPA, NAC, GLA, ALA, MK7, CoQ10, etc.). Essential
                    # because product names routinely pair the abbreviation
                    # with an expansion in parens — "DHA (Docosahexaenoic
                    # Acid)" must match cluster ingredient "dha". Word
                    # boundaries (\b) prevent EPA from matching HEPATIC.
                    elif len(cluster_ing_norm) >= 3 and len(ing_key) >= 3:
                        import re as _re
                        if _re.search(
                            r'\b' + _re.escape(cluster_ing_norm) + r'\b',
                            ing_key,
                        ):
                            is_match = True

                    # Alias fallback (Solution A): if no direct match, check
                    # if any alias matches the product ingredient. Each alias
                    # is checked the same three ways (exact, loose substring,
                    # word boundary) — alias resolution doesn't relax the
                    # match rigor, only the canonical form.
                    if not is_match and cluster_ing_aliases:
                        import re as _re
                        for alias_norm in cluster_ing_aliases:
                            if not alias_norm:
                                continue
                            if alias_norm == ing_key:
                                is_match = True
                                break
                            if (
                                len(alias_norm) >= 6
                                and len(ing_key) >= 6
                                and (alias_norm in ing_key or ing_key in alias_norm)
                            ):
                                is_match = True
                                break
                            if (
                                len(alias_norm) >= 3
                                and len(ing_key) >= 3
                                and _re.search(
                                    r'\b' + _re.escape(alias_norm) + r'\b',
                                    ing_key,
                                )
                            ):
                                is_match = True
                                break

                    if is_match:
                        # Found match
                        quantity = ing_data['quantity']
                        min_dose, min_dose_key = _resolve_min_dose(cluster_ing_norm, cluster_ing)
                        # The threshold's own unit (default mg; see dose_units above).
                        min_dose_unit = dose_units.get(min_dose_key, "mg") if min_dose_key else "mg"
                        target_unit = self._normalize_threshold_unit(min_dose_unit) or "mg"

                        # Adequacy gate:
                        #   - If a min_dose is defined (>0): require quantity >= min_dose
                        #   - If no min_dose: require quantity > 0 (excludes
                        #     products listing nutrient names with qty=0/NP unit,
                        #     e.g. malformed Soy Protein label with calcium=0)
                        try:
                            qty_num = float(quantity) if quantity is not None else 0.0
                        except (TypeError, ValueError):
                            qty_num = 0.0
                        evaluated_quantity = qty_num
                        evaluated_unit = self._normalize_threshold_unit(ing_data['unit'])
                        dose_evaluable = qty_num > 0
                        if min_dose > 0:
                            # Compare in the THRESHOLD's unit (mg/mcg/IU/CFU), never a
                            # forced mg: forcing mg mis-scaled every non-mg threshold
                            # (methylcobalamin mcg, vitamin d IU, probiotics CFU) and
                            # dropped ~19/58 clusters' synergy bonus.
                            converted, _conversion_reason = self._convert_amount_to_target_unit(
                                amount=qty_num,
                                from_unit=ing_data['unit'],
                                target_unit=target_unit,
                                ingredient_name=ing_data['name'],
                                standard_name=ing_key,
                            )
                            if converted is not None:
                                evaluated_quantity, evaluated_unit = converted, target_unit
                                dose_evaluable = True
                                meets_min = converted >= min_dose
                            else:
                                # Unbridgeable unit (a CFU threshold, or a product unit
                                # with no conversion rule) → compare in the threshold's
                                # native scale; never drop the credit on a convention we
                                # cannot convert.
                                evaluated_quantity, evaluated_unit = qty_num, target_unit
                                dose_evaluable = qty_num > 0
                                meets_min = qty_num >= min_dose
                        else:
                            meets_min = qty_num > 0

                        matched_ings.append({
                            "ingredient": ing_data['name'],
                            "cluster_ingredient": cluster_ing,
                            "quantity": quantity,
                            "unit": ing_data['unit'],
                            "min_effective_dose": min_dose,
                            "min_effective_dose_unit": target_unit if min_dose > 0 else None,
                            "evaluated_quantity": evaluated_quantity,
                            "evaluated_unit": evaluated_unit,
                            "dose_evaluable": dose_evaluable,
                            "meets_minimum": meets_min
                        })
                        doses_adequate.append(meets_min)
                        matched_product_keys.add(ing_key)
                        break

            # Determine whether this cluster qualifies. Default rule: need
            # at least 2 matched ingredients (classic synergy). Override:
            # when the cluster has `allow_single_ingredient: true` and the
            # sole matched ingredient is in `primary_ingredients`, a single
            # hit is enough (e.g. magnesium-only → sleep_stack, DHA-only →
            # prenatal_pregnancy_support, calcium-only → bone_health).
            qualifies = False
            single_ingredient_match = False
            underdosed_single = False

            if len(matched_ings) >= 2:
                qualifies = True
            elif (
                len(matched_ings) == 1
                and cluster.get("allow_single_ingredient") is True
            ):
                primary_ings_raw = cluster.get("primary_ingredients") or []
                primary_norm = {
                    self._normalize_text(p)
                    for p in primary_ings_raw
                    if isinstance(p, str) and p.strip()
                }
                sole = matched_ings[0]
                matched_term = self._normalize_text(
                    sole.get("cluster_ingredient", "")
                )
                # Single-ingredient override, two outcomes (both require the
                # matched term to be a PRIMARY ingredient for this cluster):
                #   (a) adequate dose -> a real solo synergy match (e.g.
                #       magnesium >= 200 mg earning sleep_stack). single_ingredient_match.
                #   (b) present-but-underdosed (>= 50% of the effective dose but
                #       below it) -> emitted as underdosed_single so goal matching
                #       surfaces "partially supported" instead of dropping to
                #       "Unaddressed". The synergy DISPLAY and the A5c bonus both
                #       skip it (build filters underdosed_single; the bonus needs
                #       match_count >= 2). Below 50% is trace and stays dropped —
                #       17 mg of magnesium must never claim to support sleep.
                if matched_term and matched_term in primary_norm:
                    if bool(sole.get("meets_minimum", False)):
                        qualifies = True
                        single_ingredient_match = True
                    else:
                        try:
                            sole_qty = float(sole.get("evaluated_quantity") or 0)
                        except (TypeError, ValueError):
                            sole_qty = 0.0
                        try:
                            sole_min = float(sole.get("min_effective_dose") or 0)
                        except (TypeError, ValueError):
                            sole_min = 0.0
                        if sole_min > 0 and sole_qty >= 0.5 * sole_min:
                            qualifies = True
                            underdosed_single = True

            if qualifies:
                sources = cluster.get("sources", [])
                if not isinstance(sources, list):
                    sources = []
                # Extract PMIDs from sources for Flutter display
                pmids = []
                for src in sources:
                    if isinstance(src, dict) and src.get("pmid"):
                        pmids.append(src["pmid"])

                matched_clusters.append({
                    "cluster_id": cluster.get('id', ''),
                    "cluster_name": cluster.get('standard_name', ''),
                    "evidence_tier": cluster.get('evidence_tier', 4),
                    "evidence_label": {
                        1: "Proven synergy",
                        2: "Supported co-nutrients",
                        3: "Promising combination",
                        4: "Popular combination",
                    }.get(cluster.get('evidence_tier', 4), "Popular combination"),
                    "synergy_mechanism": cluster.get("synergy_mechanism", ""),
                    "synergy_benefit_short": cluster.get("synergy_benefit_short", ""),
                    "note": cluster.get("note") or "",
                    "sources": sources,
                    "pmids": pmids,
                    "matched_ingredients": matched_ings,
                    "match_count": len(matched_ings),
                    "doses_adequate": doses_adequate,
                    "all_adequate": all(doses_adequate) if doses_adequate else False,
                    "single_ingredient_match": single_ingredient_match,
                    # True only for a present-but-underdosed sole primary match
                    # (>= 50% of the effective dose). Suppressed from the synergy
                    # display; consumed by goal matching's presence path to mark
                    # the goal "partially supported" rather than "Unaddressed".
                    "underdosed_single": underdosed_single,
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
        # Tag each ingredient with its source section so downstream
        # scoring can apply context-aware penalties (active ingredients
        # that match harmful_additives get suppressed for low/moderate
        # severity — the IQM quality score is the correct signal there).
        active_tagged = [
            {**ing, '_source_section': 'active', '_source_index': idx}
            for idx, ing in enumerate(product.get('activeIngredients', []))
        ]
        inactive_tagged = [
            {**ing, '_source_section': 'inactive', '_source_index': idx}
            for idx, ing in enumerate(product.get('inactiveIngredients', []))
        ]
        all_ingredients = active_tagged + inactive_tagged

        banned_substances = self._check_banned_substances(all_ingredients, product)
        self._attach_banned_safety_flags_to_ingredients(product, banned_substances)

        return {
            "banned_substances": banned_substances,
            "harmful_additives": self._check_harmful_additives(all_ingredients),
            "allergens": self._check_allergens(all_ingredients, product)
        }

    def _attach_banned_safety_flags_to_ingredients(
        self,
        product: Dict[str, Any],
        banned_substances: Dict[str, Any],
    ) -> None:
        """Project canonical banned/recalled safety flags onto ingredient rows."""
        for section_key in ("activeIngredients", "inactiveIngredients"):
            for ing in product.get(section_key, []) or []:
                if isinstance(ing, dict):
                    ing.setdefault("safety_flags", [])

        for hit in (banned_substances or {}).get("substances", []) or []:
            if not isinstance(hit, dict) or not isinstance(hit.get("safety_flag"), dict):
                continue
            source_section = hit.get("source_section")
            source_index = hit.get("ingredient_index")
            section_key = {
                "active": "activeIngredients",
                "inactive": "inactiveIngredients",
            }.get(source_section)
            if section_key is None or not isinstance(source_index, int):
                continue
            rows = product.get(section_key, []) or []
            if source_index < 0 or source_index >= len(rows):
                continue
            target = rows[source_index]
            if not isinstance(target, dict):
                continue
            flags = target.setdefault("safety_flags", [])
            if not isinstance(flags, list):
                flags = []
                target["safety_flags"] = flags

            flag = hit["safety_flag"]
            flag_key = (
                flag.get("entry_id"),
                flag.get("source_db"),
                flag.get("evidence_text"),
                flag.get("match_type"),
            )
            if not any(
                isinstance(existing, dict)
                and (
                    existing.get("entry_id"),
                    existing.get("source_db"),
                    existing.get("evidence_text"),
                    existing.get("match_type"),
                ) == flag_key
                for existing in flags
            ):
                flags.append(flag)

    def _check_banned_substances(self, ingredients: List[Dict], product: Optional[Dict] = None) -> Dict[str, Any]:
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

        # Entity types that should be matched against ingredient labels.
        # Class entities (policy watchlists) expose specific molecule aliases
        # and must match via strict exact/alias only — token_bounded fuzzy
        # matching is explicitly blocked for classes below.
        # Threats remain excluded entirely.
        # Products are matched via brand-qualified aliases + negative_match_terms.
        MATCHABLE_ENTITY_TYPES = {'ingredient', 'contaminant', 'product', 'class', None, ''}

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
            # Source section tag set by _evaluate_safety_data wrapper (active vs inactive).
            # Untagged ingredients default to 'active' so legacy callers preserve behavior.
            ing_source_section = ingredient.get('_source_section', 'active')

            for section_key, banned_item in banned_items_with_category:
                if not isinstance(banned_item, dict):
                    continue

                # P0: Filter by entity_type - skip products/classes/threats
                entity_type = banned_item.get('entity_type', 'ingredient')
                if entity_type not in MATCHABLE_ENTITY_TYPES:
                    continue

                # P0b: Filter by match_mode - skip disabled/historical entries
                match_rules = banned_item.get('match_rules', {}) or {}
                match_mode = banned_item.get('match_mode') or match_rules.get('match_mode', 'active')
                if match_mode in ('disabled', 'historical'):
                    continue

                # P0c: Active/inactive role gate (v3.5.2 — per-entry policy).
                # Substances flagged with match_mode='active' (the default)
                # split into three policy classes for inactive-section matches:
                #
                #   inactive_policy='excipient_acceptable' (TiO2/Talc/Docusate):
                #     SKIP — these have legitimate FDA-approved excipient
                #     use; firing B0 on every capsule would produce ~2,000+
                #     FPs. Warning visibility remains via the resolver layer
                #     in build_final_db (commit 3e4f9d6).
                #
                #   inactive_policy='penalize_anyway' (heavy metals, hormones,
                #     hepatotoxic botanicals, controlled substances, watchlist
                #     contaminants): FALL THROUGH — these have no legitimate
                #     inactive use; appearing in the inactive panel is a
                #     labeling defect or hidden-active risk and must penalize.
                #
                #   inactive_policy='review_required' (Cascara, synthetic
                #     food acids):
                #     SKIP for now — borderline classification; do not
                #     penalize until a human reviewer decides. Warning still
                #     visible via the build-layer resolver.
                #
                # Fallback: when inactive_policy is absent (e.g., 'banned'/
                # 'recalled' entries that escape directly to UNSAFE/BLOCKED
                # verdicts), preserve the original v3.5.0 suppression so
                # the legacy behavior is unchanged for those.
                #
                # Product entries (entity_type='product') bypass this gate
                # entirely — they're matched against product identity, not
                # ingredient sections.
                if entity_type != 'product' and match_mode == 'active' and ing_source_section == 'inactive':
                    inactive_policy = banned_item.get('inactive_policy')
                    if inactive_policy == 'penalize_anyway':
                        # fall through and fire B0 — never-acceptable inactive
                        pass
                    elif inactive_policy == 'excipient_acceptable':
                        continue
                    elif inactive_policy == 'review_required':
                        continue  # human review pending; preserve current score
                    else:
                        # No explicit policy — default to suppression so
                        # banned/recalled (which never need this gate) and
                        # any future entries keep the v3.5.0 behavior.
                        continue

                # Product-level recalls/bans should match product identity
                # (full name / brand), not ingredient labels.
                candidate_ing_name = ing_name
                candidate_std_name = std_name
                allow_product_token_bounded = True
                if entity_type == 'product':
                    if ing_idx > 0:
                        continue
                    recall_scope = banned_item.get('recall_scope')
                    has_recall_scope = bool(recall_scope)
                    candidate_ing_name = product_name or ing_name
                    # Precision guard: product-scoped recalls should match
                    # product identity only (fullName/product_name), not brand.
                    # Brand fallback remains allowed for unscoped brand-level
                    # bans where recall_scope is absent.
                    if has_recall_scope and product_name:
                        candidate_std_name = ""
                    else:
                        candidate_std_name = brand_name or std_name
                    # Product recalls are high-stakes; avoid token-bounded
                    # product-name partial hits that can over-block.
                    allow_product_token_bounded = False
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
                negative_terms = match_rules.get('negative_match_terms', [])
                if negative_terms and (
                    self._has_negative_match_term(candidate_ing_name_lower, negative_terms)
                    or (
                        not banned_item.get("requires_explicit_form_evidence")
                        and self._has_negative_match_term(candidate_std_name_lower, negative_terms)
                    )
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

                # Class entities: strict exact/alias only, never token_bounded.
                # This preserves the original intent of blocking fuzzy class matches
                # (which would over-block generic chemistry terms) while still
                # allowing the specific molecule aliases under a class to match.
                if not match_method and allow_product_token_bounded and entity_type != 'class':
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
                    if banned_item.get("requires_explicit_form_evidence"):
                        evidence = has_explicit_form_evidence(
                            self._banned_form_evidence_values(ingredient, candidate_ing_name, product_name),
                            banned_item.get("form_evidence_patterns") or [],
                        )
                        if not evidence:
                            continue
                        match_method = "explicit_form_evidence"
                        matched_variant = matched_variant or evidence

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
                        "explicit_form_evidence": 0.95,
                        "token_bounded": 0.7
                    }

                    derived_severity = self._derive_banned_severity(banned_item)

                    safety_flag = safety_flag_from_banned_match(
                        banned_item,
                        match_type=match_type,
                        matched_variant=matched_variant,
                        evidence_text=candidate_ing_name,
                    ).to_dict()
                    jurisdiction = safety_jurisdiction_projection(banned_item)
                    safety_flag.update(jurisdiction)

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
                        "safety_flag": safety_flag,
                        "source_section": ing_source_section,
                        "ingredient_index": ingredient.get("_source_index"),
                        "allowlist_id": allowlist_id,
                        "allowlist_version": allowlist_version if allowlist_id else None,
                        "entity_type": entity_type,
                        "legal_status_enum": banned_item.get('legal_status_enum'),
                        "clinical_risk_enum": banned_item.get('clinical_risk_enum'),
                        "regulatory_date": banned_item.get('regulatory_date'),
                        "regulatory_date_label": banned_item.get('regulatory_date_label'),
                        "references_structured": banned_item.get('references_structured'),
                        # D5.4: Dr Pham's user-facing authored copy must
                        # propagate from the banned_recalled data file
                        # through to the detail-blob warning so the
                        # Flutter InteractionWarning.fromJson fallback chain
                        # picks them up as alertHeadline/alertBody. Without
                        # these, high_risk_ingredient / banned_substance
                        # / recalled_ingredient / watchlist_substance
                        # warnings render with technical jargon only.
                        "safety_warning": banned_item.get('safety_warning'),
                        "safety_warning_one_liner": banned_item.get('safety_warning_one_liner'),
                        "ban_context": banned_item.get('ban_context'),
                        **jurisdiction,
                    })

        return {
            "found": len(found) > 0,
            "substances": found,
            "safety_flags": [
                s["safety_flag"]
                for s in found
                if isinstance(s, dict) and isinstance(s.get("safety_flag"), dict)
            ],
        }

    def _banned_form_evidence_values(
        self,
        ingredient: Dict[str, Any],
        candidate_ing_name: str,
        product_name: str = "",
    ) -> List[Any]:
        values: List[Any] = [
            ingredient.get("raw_source_text"),
            ingredient.get("name"),
            ingredient.get("ingredientGroup"),
            candidate_ing_name,
        ]
        if product_name:
            values.append(product_name)
        for form in ingredient.get("forms") or []:
            if isinstance(form, dict):
                values.extend([form.get("name"), form.get("prefix"), form.get("label")])
            elif form:
                values.append(form)
        return values

    def _derive_banned_severity(self, banned_item: Dict[str, Any]) -> str:
        """Derive severity from current banned DB policy fields."""
        status = banned_item.get("status")
        if status in {"banned", "recalled"}:
            return "critical"
        if status == "high_risk":
            legal_status = banned_item.get("legal_status_enum")
            clinical_risk = banned_item.get("clinical_risk_enum")
            if legal_status in {"banned_federal", "banned_state", "controlled_substance", "adulterant", "not_lawful_as_supplement"}:
                if clinical_risk in {"critical", "high"}:
                    return clinical_risk
            return "moderate"
        if status == "watchlist":
            clinical_risk = banned_item.get("clinical_risk_enum")
            return clinical_risk if clinical_risk in {"moderate", "high", "critical"} else "low"

        legal_status = banned_item.get("legal_status_enum")
        if legal_status in {"high_risk", "restricted", "under_review"}:
            return {
                "high_risk": "moderate",
                "restricted": "moderate",
                "under_review": "low",
            }[legal_status]

        clinical_risk = banned_item.get("clinical_risk_enum")
        if clinical_risk:
            return clinical_risk

        return "critical"

    def _has_negative_match_term(self, text: str, negative_terms: List[Any]) -> bool:
        """Check if text contains any negative match terms (case-insensitive).

        Used to filter out false positives like 'ephedra-free', 'kava-free', etc.
        """
        text_lower = (text or "").lower()
        text_norm = re.sub(r"\s+", " ", text_lower).strip()
        for item in negative_terms:
            if isinstance(item, dict):
                term = str(item.get("term") or "").lower()
                match_mode = str(item.get("match_mode") or "substring").lower()
            else:
                term = str(item or "").lower()
                match_mode = "substring"
            term_norm = re.sub(r"\s+", " ", term).strip()
            if not term_norm:
                continue
            if match_mode == "exact" and text_norm == term_norm:
                return True
            if match_mode != "exact" and term_norm in text_norm:
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

        Each ingredient dict may carry a ``_source_section`` key (``"active"``
        or ``"inactive"``) set by ``_collect_contaminant_data``.  The value is
        forwarded into every match record as ``source_section`` so the scorer
        can suppress precautionary (low/moderate) penalties for ingredients
        that appear in the Supplement Facts panel — their IQM quality score
        is the correct signal, not an additive penalty.

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
                additive_entity_type = additive.get('entity_type')
                additive_match_mode = (
                    additive.get('match_mode')
                    or additive.get('match_rules', {}).get('match_mode', 'alias_and_fuzzy')
                )

                # Routing-only umbrella entries should remain available in the DB
                # but must not score directly during enrichment.
                if additive_entity_type == 'class' or additive_match_mode in {'disabled', 'historical'}:
                    continue

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
                        "classification_evidence": classification_evidence if classification_evidence else None,
                        # Reference data for user-facing display
                        "notes": additive.get('notes', ''),
                        "mechanism_of_harm": additive.get('mechanism_of_harm', ''),
                        "population_warnings": additive.get('population_warnings', []),
                        "regulatory_status": additive.get('regulatory_status', {}),
                        # Source section for context-aware scoring:
                        # "active" = from Supplement Facts, "inactive" = from Other Ingredients.
                        # Scorer suppresses low/moderate penalties for active-source matches
                        # because the IQM quality score is the correct signal for actives.
                        "source_section": ingredient.get('_source_section', 'unknown'),
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
                            "evidence": f"Contains: {allergen_text.strip().title()}",
                            "matched_text": allergen_text,
                            "severity_level": allergen.get('severity_level', 'low'),
                            "regulatory_status": allergen.get('regulatory_status', ''),
                            "general_handling": allergen.get('general_handling', 'flag_only'),
                            "notes": allergen.get('notes', ''),
                            "supplement_context": allergen.get('supplement_context', ''),
                            "prevalence": allergen.get('prevalence', ''),
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
        text_lower = text.lower().strip()

        # Scope negation to its own clause. A product can legitimately say
        # "Made without gluten. Contains milk"; the first clause must not erase
        # the independent positive declaration in the second.
        clauses = [
            clause.strip()
            for clause in re.split(r'(?<=[.!?])\s+|;\s*|\s+\bbut\b\s+', text_lower)
            if clause.strip()
        ]
        if len(clauses) > 1:
            for clause in clauses:
                self._parse_allergen_statement(
                    clause, allergen_lookup, found, source
                )
            return

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
                    "general_handling": allergen.get('general_handling', 'flag_only'),
                    "notes": allergen.get('notes', ''),
                    "supplement_context": allergen.get('supplement_context', ''),
                    "prevalence": allergen.get('prevalence', ''),
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

                    # NEVER apply negation to structured ingredient-list matches.
                    # If "Milk Protein" is in the ingredient list, it IS an allergen
                    # regardless of any "dairy-free" claim in marketing text.
                    # See _is_negated() docstring for the safety contract.

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
                        "category": allergen.get('category', ''),
                        "notes": allergen.get('notes', ''),
                        "supplement_context": allergen.get('supplement_context', ''),
                        "prevalence": allergen.get('prevalence', '')
                    })

        # Deduplicate by allergen_id, keeping highest precedence
        deduplicated = {}
        for item in all_found:
            allergen_id = item.get('allergen_id', '')
            if not allergen_id:
                # Use allergen_name as fallback key so entries without id aren't dropped
                allergen_id = item.get('allergen_name', '').lower().strip()
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
                # Limit to 60 chars between negation word and allergen term
                # to prevent cross-sentence false matches like:
                # "No artificial flavors. ... soy lecithin" matching as negated soy
                if re.search(pattern + r'.{0,60}' + re.escape(term), text):
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

        # Resolve detected allergens once. Used twice below: first to seed
        # `conflicts` and then again as a hard gate after Stage-2 evidence
        # promotion (so a soy-lecithin product whose claim was promoted by
        # `CLAIM_SOY_FREE` still gets disqualified by the ingredient-level
        # detection — closes the sequencing gap that the now-removed
        # 'lecithin' proximity entry used to mask).
        if contaminant_data is None:
            contaminant_data = self._collect_contaminant_data(product)
        detected_allergens = contaminant_data['allergens']['allergens']
        detected_lower_names = [
            str(a.get('allergen_name', '')).lower() for a in detected_allergens
        ]

        def _allergen_in_detected(*tokens: str) -> bool:
            return any(any(t in n for t in tokens) for n in detected_lower_names)

        # Initial conflict pass (Stage-1-only). Stays here so the
        # `conflicts` list is populated as soon as the targetGroups text
        # match fires, even if Stage-2 promotion later toggles a flag.
        conflicts = []
        if dairy_free and _allergen_in_detected('milk', 'dairy'):
            conflicts.append("dairy-free claim conflicts with detected dairy")
        if soy_free and _allergen_in_detected('soy'):
            conflicts.append("soy-free claim conflicts with detected soy")
        if gluten_free and _allergen_in_detected('wheat', 'gluten'):
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

        # Promote evidence-based detections to the canonical compliance flags.
        # All three concerns now match on `rule_id` for consistency — gluten
        # was already explicit (handles the GFCO certified variant); dairy
        # and soy previously matched on `dedupe_key`, which was functionally
        # equivalent today but would silently miss any future certified
        # variant (e.g. CLAIM_DAIRY_FREE_CERTIFIED) added with a different
        # dedupe_key. Use a rule_id set per concern so adding a variant is
        # a one-line change.
        gluten_free = gluten_free or any(
            ev.get('rule_id') in {'CLAIM_GLUTEN_FREE', 'CLAIM_GLUTEN_FREE_GFCO'}
            for ev in eligible_allergen_evidence
        )
        dairy_free = dairy_free or any(
            ev.get('rule_id') in {'CLAIM_DAIRY_FREE'}
            for ev in eligible_allergen_evidence
        )
        soy_free = soy_free or any(
            ev.get('rule_id') in {'CLAIM_SOY_FREE'}
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

        # POST-PROMOTION HARD GATE — detected allergens trump any claim
        # source. Without this, a label that says "Soy-Free" but lists
        # soy lecithin in ingredients would slip through Stage-2
        # promotion (the rule_id match fires, evidence is eligible at
        # the first-layer because the surviving 'soy' proximity token
        # is suppressed by the 'soy-free'/'soy free' escape clause).
        # Pre-2026-05-09 the now-removed 'lecithin' proximity entry
        # masked this sequencing gap; the gate makes the safety
        # invariant explicit instead.
        #
        # Each gate is also recorded into `conflicts` if not already
        # there, so downstream scoring (`score_supplements.py:1934`)
        # sees the disagreement.
        def _record_conflict(msg: str) -> None:
            if msg not in conflicts:
                conflicts.append(msg)

        if dairy_free and _allergen_in_detected('milk', 'dairy'):
            dairy_free = False
            _record_conflict("dairy-free claim conflicts with detected dairy")
        if soy_free and _allergen_in_detected('soy'):
            soy_free = False
            _record_conflict("soy-free claim conflicts with detected soy")
        if gluten_free and _allergen_in_detected('wheat', 'gluten'):
            gluten_free = False
            _record_conflict("gluten-free claim conflicts with detected gluten/wheat")

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
            # Match the full source path so nested product-label fields such as
            # labelText.parsed.certifications[0] can satisfy their explicit
            # product-level allowlist entry. Root-only matching incorrectly
            # reduced those paths to "labelText" and marked them out of scope.
            normalized_source = re.sub(r'\[[^\]]+\]', '', source_field or '')
            in_approved_scope = any(
                normalized_source == field
                or normalized_source.startswith(f'{field}.')
                for field in approved_fields
            )
            if not in_approved_scope:
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

        # NOTE: Top-level `qualityFeatures` and `certifications` loops were removed
        # 2026-04 — the cleaner nests that data at `labelText.parsed.qualityFeatures`
        # and `labelText.parsed.certifications` (enhanced_normalizer.py lines 3550/3562),
        # and the labelText.parsed iteration below (~line 6747) captures it with the
        # correct path. The `product_level_fields` scope group in cert_claim_rules.json
        # includes both the top-level and nested paths, so scope validation still passes.

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

        # NOTE: Top-level `otherIngredients` loop was removed 2026-04 — the cleaner
        # does not emit this at top level (raw DSLD otherIngredients text is processed
        # into `inactiveIngredients` by enhanced_normalizer.py around line 3123). The
        # `ingredient_fields` scope group in cert_claim_rules.json accepts either
        # `otherIngredients` or `inactiveIngredients`, and the inactiveIngredients loop
        # above already covers ingredient-scoped claims.

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
        except re.error as exc:
            self.logger.warning(
                "Failed to extract context snippet for matched_text=%r: %s",
                matched_text,
                exc,
            )
            return matched_text
        except (AttributeError, TypeError, KeyError) as exc:
            self.logger.warning(
                "Failed to extract context snippet for matched_text=%r: %s",
                matched_text,
                exc,
            )
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

        v4 three-tier cert split (P0.1b, 2026-05-18):
          - `third_party_programs.programs` — regex + rules-db hits from the
            label and product text. DISPLAY ONLY. Was the source of the v3
            overcredit bug because the scorer trusted it for points.
          - `manufacturer_cert_signals` — brand/manufacturer-level evidence
            from `top_manufacturers_data.json`. **Rerouted out of
            third_party_programs** so brand-level claims no longer leak into
            per-SKU scoring. DISPLAY ONLY.
          - `verified_cert_programs` — resolver output: for each claimed/
            manufacturer-signal program, ask the public cert registry
            whether THIS SKU is listed. Only entries with scope ∈
            {sku, product_line} and recency_status != scoring_blocked
            actually score B4a points. SCORES POINTS.

        Also derives safety verification flags from certifications.
        """
        all_text = self._get_all_product_text(product)

        # LEGACY: Collect using old patterns for backward compatibility
        third_party = self._collect_third_party_certs(all_text)
        gmp = self._collect_gmp_data(all_text)
        traceability = self._collect_traceability_data(all_text)

        # ENHANCED (v1.0.0): Collect using rules database with evidence objects
        third_party_evidence = self._collect_claims_from_rules_db(product, 'third_party_programs')
        gmp_evidence = self._collect_claims_from_rules_db(product, 'gmp_certifications')
        batch_evidence = self._collect_claims_from_rules_db(product, 'batch_traceability')
        traceability = self._merge_evidence_batch_traceability(traceability, batch_evidence)

        # Merge evidence-based third-party detections into the regex-derived
        # third_party_programs. This is the CLAIMED set — labels + rules-db
        # only. Manufacturer-level evidence does NOT go here in v4.
        third_party = self._merge_evidence_third_party_programs(third_party, third_party_evidence)

        # Manufacturer-level cert evidence — was previously merged into
        # third_party_programs (the v3 overcredit bug). v4 reroutes this to
        # its own field, display-only, never scored. The function below now
        # returns a separate dict instead of mutating third_party.
        manufacturer_cert_signals = self._collect_manufacturer_cert_signals(product, gmp)

        # Cert resolver: ask the public registry whether THIS SKU is verified
        # for any of the claimed-or-manufacturer-signaled programs. Output is
        # the only thing the v4 B4a scorer reads.
        verified_cert_programs = self._resolve_verified_cert_programs(
            product=product,
            third_party_programs=third_party,
            manufacturer_signals=manufacturer_cert_signals,
        )

        # Derive safety flags from certifications (uses claimed set — display
        # signals like "tested for heavy metals" still come from the regex/
        # rules-db detection, not from registry verification).
        safety_flags = self._derive_safety_flags(third_party, product)

        return {
            # Legacy format for backward compatibility (DISPLAY ONLY post-v4)
            "third_party_programs": third_party,
            "gmp": gmp,
            "batch_traceability": traceability,
            # v4 three-tier cert split (P0.1b)
            "manufacturer_cert_signals": manufacturer_cert_signals,
            "verified_cert_programs": verified_cert_programs,
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
            "CERT_NSF_CONTENTS": "NSF Contents Certified",
            "CERT_NSF_ANSI_455": "NSF/ANSI 455 Dietary Supplement",
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

    _LABEL_ASSERTED_B4A_PROGRAMS = {
        "usp verified",
        "informed choice",
        "informed sport",
        "bscg",
    }
    _LABEL_ASSERTED_OMEGA_ONLY_PROGRAMS = {
        "ifos",
    }

    def _collect_manufacturer_cert_signals(
        self, product: Dict, gmp: Dict
    ) -> List[Dict]:
        """v4 (P0.1b 2026-05-18): Returns brand/manufacturer-level cert evidence
        as a SEPARATE list, no longer mutates ``third_party.programs``.

        This was previously named ``_inject_manufacturer_certs`` and was the
        source of the cert overcredit bug — it injected company-level certs
        like "Thorne has NSF Sport on file" into every Thorne SKU's
        third_party_programs, which then scored as if each SKU were
        individually certified. The fix is to keep the signal (it's still
        useful trust metadata) but route it to its own field so the scorer
        cannot grant B4a points from it.

        GMP evidence is still side-effected into the ``gmp`` dict — that's a
        separate B4b concern, not the B4a bug we're fixing.
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
            return []

        # Find the matching manufacturer entry to get evidence strings.
        top_db = self.databases.get("top_manufacturers_data", {})
        top_list = top_db.get("top_manufacturers", [])
        evidence_strings: List[str] = []
        matched_id = top_match.get("manufacturer_id", "")
        for entry in top_list:
            if entry.get("id") == matched_id:
                evidence_strings = entry.get("evidence", []) or []
                break

        if not evidence_strings:
            return []

        signals: List[Dict] = []
        seen: set = set()
        for ev_str in evidence_strings:
            for pattern, cert_name in self._MANUFACTURER_CERT_PATTERNS:
                if not pattern.search(ev_str):
                    continue
                if cert_name is None:
                    # GMP — still side-effected into the gmp dict (B4b, not B4a)
                    if not gmp.get("nsf_gmp") and not gmp.get("claimed"):
                        gmp["claimed"] = True
                        gmp["source"] = "manufacturer_evidence"
                    continue
                key = self._normalize_text(cert_name)
                if key in seen:
                    continue
                seen.add(key)
                signals.append({
                    "program": cert_name,
                    "evidence": ev_str,
                    "source": "top_manufacturers_data.json",
                    "manufacturer_id": matched_id,
                    "_note": "brand-level cert signal — display/trust metadata only, does NOT score B4a; resolver decides per-SKU verification",
                })
                break  # one cert per evidence string
        return signals

    def _inject_manufacturer_certs(
        self, third_party: Dict, product: Dict, gmp: Dict
    ) -> Dict:
        """DEPRECATED (P0.1b): kept for any external callers; do not call from
        within enrichment. v4 uses _collect_manufacturer_cert_signals which
        returns a separate list instead of mutating third_party. This shim
        delegates to the new function and adds nothing to third_party so
        existing tests against `programs` content don't accidentally pass."""
        # Side-effect GMP only; do not touch third_party.programs.
        _ = self._collect_manufacturer_cert_signals(product, gmp)
        return third_party

    def _resolve_verified_cert_programs(
        self,
        product: Dict,
        third_party_programs: Dict,
        manufacturer_signals: List[Dict],
    ) -> List[Dict]:
        """Ask the cert registry which claimed cert programs are SKU-verified
        for THIS product. Returns a list of resolved entries (one per program
        the resolver decided on). Only entries with scope in {sku, product_line}
        AND no scoring_blocked_reason will earn B4a points in the scorer.
        """
        # Lazy-load the resolver registry once per enricher instance.
        if not hasattr(self, "_cert_registry_cache"):
            try:
                from cert_resolver import CertRegistry  # local import to avoid hard dep at module load
                self._cert_registry_cache = CertRegistry.load()
            except Exception as exc:  # registry missing or malformed → empty
                self.logger.warning("cert_resolver unavailable: %s (verified_cert_programs will be empty)", exc)
                self._cert_registry_cache = None

        registry = self._cert_registry_cache
        if registry is None:
            return []

        from cert_resolver import discover_verified_programs, resolve  # local import (kept colocated with usage)

        brand = product.get("brandName", "") or ""
        product_name = (
            product.get("productName")
            or product.get("fullName")
            or ""
        )

        # Union of claimed (label/rules-db) + manufacturer signals. Track
        # product-label provenance separately for P0.1d provisional scoring:
        # unsupported scrapers may emit a low `label_asserted_product` scope,
        # but manufacturer evidence must never earn that provisional credit.
        claimed_programs: List[str] = []
        seen: set = set()
        label_claims_by_name: Dict[str, Dict] = {}
        manufacturer_claim_names: set = set()
        for prog in (third_party_programs or {}).get("programs", []) or []:
            name = prog.get("name") if isinstance(prog, dict) else prog
            if name and name not in seen:
                seen.add(name)
                claimed_programs.append(name)
            if name:
                label_claims_by_name[self._normalize_text(name)] = prog if isinstance(prog, dict) else {"name": name}
        for sig in manufacturer_signals or []:
            name = sig.get("program")
            if name and name not in seen:
                seen.add(name)
                claimed_programs.append(name)
            if name:
                manufacturer_claim_names.add(self._normalize_text(name))

        product_dsld_id = (
            product.get("dsld_id")
            or product.get("id")
            or product.get("dsldId")
            or product.get("productId")
        )
        resolutions = (
            resolve(
                brand,
                product_name,
                claimed_programs,
                registry,
                dsld_id=str(product_dsld_id) if product_dsld_id is not None else None,
            )
            if claimed_programs
            else []
        )
        discovered_resolutions = discover_verified_programs(
            brand,
            product_name,
            registry,
            dsld_id=str(product_dsld_id) if product_dsld_id is not None else None,
        )
        if discovered_resolutions:
            by_program = {
                self._normalize_text(resolution.program): resolution
                for resolution in resolutions
            }
            for resolution in discovered_resolutions:
                key = self._normalize_text(resolution.program)
                current = by_program.get(key)
                if current is None or (
                    not current.scores_points() and resolution.scores_points()
                ):
                    by_program[key] = resolution
            resolutions = list(by_program.values())
        covered_programs = {
            self._normalize_text(program)
            for program in getattr(registry, "records_by_program", {}).keys()
            if program
        }

        out: List[Dict] = []
        for resolution in resolutions:
            row = resolution.to_dict()
            program = row.get("program") or ""
            program_key = self._normalize_text(program)

            # P0.1d provisional bridge: if a program has no live registry
            # loaded yet and the product label explicitly claims it, emit a
            # low-credit label_asserted_product scope for the scorer. Do not
            # apply this to covered registries (NSF Sport/NSF 173) because a
            # no-hit there is meaningful. Do not apply to manufacturer-only
            # evidence, needs_review, or brand_only.
            if (
                row.get("scope") == "claimed_only"
                and program_key in label_claims_by_name
                and program_key not in covered_programs
                and (
                    program_key in self._LABEL_ASSERTED_B4A_PROGRAMS
                    or program_key in self._LABEL_ASSERTED_OMEGA_ONLY_PROGRAMS
                )
            ):
                source_claim = label_claims_by_name.get(program_key) or {}
                row["scope"] = "label_asserted_product"
                row["evidence_source"] = "product_label"
                row["provisional"] = True
                row["provisional_reason"] = "product-level label claim; live scraper not loaded for this program"
                if isinstance(source_claim, dict):
                    row["claim_source"] = source_claim.get("source") or "label"
            out.append(row)

        return out

    def _collect_third_party_certs(self, text: str) -> List[Dict]:
        """Collect third-party testing certifications"""
        certs = []

        # Priority certification patterns (named quality/testing programs only).
        # Generic "NSF Certified" is intentionally excluded: labels such as
        # "NSF Certified Gluten-Free" certify a dietary claim, not supplement
        # contents, contaminants, or potency. Quality flags require a specific
        # quality program such as NSF Contents/ANSI 173, NSF Sport, or NSF/ANSI 455.
        cert_checks = [
            ("NSF Sport", r'\bNSF\b.*certified(?:\s*for)?\s*sport\b|\bNSF[-\s]?sport\b'),
            ("NSF Contents Certified", r'\bNSF\s+Contents\s+Certified\b|\bContents\s+Certified\s+NSF\b|\bNSF/ANSI\s*173\b|\bNSF\s+173\b'),
            ("NSF/ANSI 455 Dietary Supplement", r'\bNSF[\s/]*ANSI\s*455\b|\bNSF\s+455\b|\bNSF\s+Dietary\s+Supplement\s+Certified\b'),
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
            "gmp_certified_or_compliant": gmp_found,
            "nsf_gmp": nsf_gmp,
            "fda_registered": fda_registered,
            "text_matched": "NSF GMP" if nsf_gmp else "FDA Registered" if fda_registered else "GMP" if gmp_found else ""
        }

    def _collect_traceability_data(self, text: str) -> Dict:
        """Collect batch traceability data"""
        has_coa = bool(self.compiled_patterns['coa'].search(text))
        has_qr = bool(self.compiled_patterns['qr_code'].search(text))
        # A QR code is the lookup mechanism for many labels. Keep the explicit
        # QR flag for display, but also roll it into the canonical lookup flag
        # so nested and top-level scoring contracts agree.
        has_batch_lookup = bool(self.compiled_patterns['batch_lookup'].search(text) or has_qr)

        return {
            "has_coa": has_coa,
            "has_qr_code": has_qr,
            "has_batch_lookup": has_batch_lookup,
            "qualifies": has_coa or has_qr or has_batch_lookup
        }

    def _merge_evidence_batch_traceability(self, traceability: Dict, evidence_list: List[Dict]) -> Dict:
        """Promote eligible rules-db traceability evidence into scoring fields.

        The rules database carries stronger context checks than the legacy
        regexes. Only actionable, score-eligible evidence with positive points
        is promoted. Weak claims such as "batch tested" remain display-only.
        """
        merged = dict(traceability or {})
        merged.setdefault("has_coa", False)
        merged.setdefault("has_qr_code", False)
        merged.setdefault("has_batch_lookup", False)

        for evidence in evidence_list or []:
            if not isinstance(evidence, dict):
                continue
            if not evidence.get("score_eligible"):
                continue
            if (evidence.get("points_if_eligible") or 0) <= 0:
                continue
            if evidence.get("evidence_strength") not in {"strong", "medium"}:
                continue

            rule_id = evidence.get("rule_id")
            dedupe_key = evidence.get("dedupe_key")
            if rule_id == "TRACE_COA" or dedupe_key == "traceability:coa":
                merged["has_coa"] = True
            elif rule_id == "TRACE_QR" or dedupe_key == "traceability:qr":
                merged["has_qr_code"] = True
                merged["has_batch_lookup"] = True
            elif rule_id == "TRACE_TRANSPARENCY" or dedupe_key == "traceability:transparency":
                merged["has_batch_lookup"] = True

        merged["has_batch_lookup"] = bool(merged.get("has_batch_lookup") or merged.get("has_qr_code"))
        merged["qualifies"] = bool(
            merged.get("has_coa") or merged.get("has_qr_code") or merged.get("has_batch_lookup")
        )
        return merged

    QUALITY_CERT_CAPABILITIES = {
        # Contents / potency / contaminant programs.
        "nsf sport": {"purity_verified", "heavy_metal_tested", "label_accuracy_verified"},
        "nsf certified for sport": {"purity_verified", "heavy_metal_tested", "label_accuracy_verified"},
        "nsf contents certified": {"purity_verified", "heavy_metal_tested", "label_accuracy_verified"},
        "nsf ansi 173": {"purity_verified", "heavy_metal_tested", "label_accuracy_verified"},
        "nsf 173": {"purity_verified", "heavy_metal_tested", "label_accuracy_verified"},
        "nsf ansi 455": {"purity_verified", "heavy_metal_tested", "label_accuracy_verified"},
        "nsf ansi 455 dietary supplement": {"purity_verified", "heavy_metal_tested", "label_accuracy_verified"},
        "usp verified": {"purity_verified", "heavy_metal_tested", "label_accuracy_verified"},
        "consumerlab": {"purity_verified", "heavy_metal_tested", "label_accuracy_verified"},
        "consumerlab approved": {"purity_verified", "heavy_metal_tested", "label_accuracy_verified"},
        "labdoor tested": {"purity_verified", "heavy_metal_tested", "label_accuracy_verified"},
        # Contaminant / banned-substance programs. These are valuable but do
        # not universally prove supplement-facts potency.
        "ifos": {"purity_verified", "heavy_metal_tested"},
        "goed certified": {"purity_verified", "heavy_metal_tested", "label_accuracy_verified"},
        "clean label project certified": {"purity_verified", "heavy_metal_tested"},
        "informed sport": {"purity_verified"},
        "informed choice": {"purity_verified"},
        "bscg": {"purity_verified"},
    }

    @classmethod
    def _quality_cert_capabilities(cls, program_name: str) -> set:
        key = re.sub(r"[^a-z0-9]+", " ", str(program_name or "").lower()).strip()
        return cls.QUALITY_CERT_CAPABILITIES.get(key, set())

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

        capabilities = set()
        for name in program_names:
            capabilities.update(self._quality_cert_capabilities(name))

        purity_verified = "purity_verified" in capabilities
        heavy_metal_tested = "heavy_metal_tested" in capabilities
        label_accuracy_verified = "label_accuracy_verified" in capabilities

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

        # Chemical-identity resolution handles for the branded single-active
        # escape below (same databases the scorer's skip logic trusts via
        # `_is_known_therapeutic`).
        quality_map = self.databases.get('ingredient_quality_map', {})
        botanicals_db = self.databases.get('standardized_botanicals', {})

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
            # The cleaner owns structural disclosure on the parent header.
            # Flattened children carry the relationship, but their own
            # disclosureLevel describes the child (or is absent) and must not
            # replace the parent blend's tier or provenance.
            parent_headers: Dict[str, Dict[str, Any]] = {}
            for header_idx, candidate in enumerate(ingredient_list):
                if not isinstance(candidate, dict):
                    continue
                if candidate.get("isNestedIngredient"):
                    continue
                candidate_name = (candidate.get("name", "") or "").strip()
                if not candidate_name:
                    continue
                if not (
                    candidate.get("proprietaryBlend", False)
                    or candidate.get("isProprietaryBlend", False)
                ):
                    continue
                parent_headers[self._normalize_exclusion_text(candidate_name)] = {
                    "disclosure_level": candidate.get("disclosureLevel"),
                    "quantity": candidate.get("quantity"),
                    "unit": candidate.get("unit", "") or "",
                    "source_field": f"{source_name}[{header_idx}]",
                }

            for idx, ingredient in enumerate(ingredient_list):
                is_nested = bool(ingredient.get('isNestedIngredient', False))
                parent_blend = (ingredient.get('parentBlend', '') or '').strip()
                is_blend = (
                    ingredient.get('proprietaryBlend', False) or
                    ingredient.get('isProprietaryBlend', False)
                )
                # The cleaner assigns blend ownership to the parent header.
                # Flattened display-only members deliberately remain
                # ``proprietaryBlend=False`` and carry the structural relation
                # through ``isNestedIngredient`` + ``parentBlend`` instead.
                # Keep those linked children so opacity evidence is not lost.
                if not is_blend and not (is_nested and parent_blend):
                    continue

                disclosure = ingredient.get('disclosureLevel', 'none')
                nested = ingredient.get('nestedIngredients', [])
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

                # Branded single-active escape (B5 opacity root fix).
                # A marketing suffix token ("Complex"/"Matrix"/"Formula"/...) in
                # an ingredient name is not, by itself, evidence of a proprietary
                # blend. When the entry lists NO sub-ingredients, is NOT a member
                # of a blend, and RESOLVES TO ONE known canonical therapeutic
                # ingredient (the chemical-identity test), it is a branded single
                # active (EpiCor=yeast fermentate, Curcumin C3 Complex=curcumin,
                # Clarinol CLA, Boron Complex=boron, Citrus Bioflavonoid Complex)
                # that hides nothing — not an opaque blend. Genuine multi-
                # ingredient blends ("Proprietary Blend", "Super Greens Blend",
                # "Probiotic & Microbiome Blend") do NOT resolve to a single
                # canonical ingredient, so they fall through and keep the B5
                # opacity penalty.
                if (
                    not has_nested_children
                    and not has_parent
                    and self._is_known_therapeutic(
                        name,
                        (ingredient.get('standardName', '') or name),
                        quality_map,
                        botanicals_db,
                    )
                ):
                    continue

                # Roll nested rows under parent blend key when available.
                if is_nested and parent_blend:
                    # Parent aggregates like "Total Cultures"/"Total Omega-3s"
                    # are never proprietary blends — skip them outright.
                    if parent_is_non_proprietary_aggregate:
                        continue
                    # D3: a parent whose name lacks a blend keyword may STILL be a
                    # proprietary blend (e.g. "Organic Alkalizing Green Juice
                    # Powder"). Aggregate it here; the finalization opacity gate
                    # below keeps a keyword-less group ONLY when it proves OPAQUE
                    # (every child amount withheld). `_keyword_blend` records
                    # whether the name matched so disclosed keyword-less
                    # aggregates drop out.
                    parent_header = parent_headers.get(
                        self._normalize_exclusion_text(parent_blend)
                    )
                    parent_disclosure = (
                        parent_header.get("disclosure_level")
                        if parent_header
                        else None
                    )
                    if parent_disclosure in {"none", "partial", "full"}:
                        disclosure = parent_disclosure

                    group_key = (parent_blend.lower(), disclosure)
                    group = nested_parent_groups.get(group_key)
                    if not group:
                        parent_source_field = (
                            parent_header.get("source_field")
                            if parent_header
                            else source_field
                        )
                        group = {
                            "name": parent_blend,
                            "disclosure_level": disclosure,
                            "nested_count": 0,
                            "total_weight": 0.0,
                            "unit": "",
                            "hidden_count": 0,
                            "source_field": parent_source_field,
                            "source_path": parent_source_field,
                            "sources": ["cleaning"],
                            "_keyword_blend": parent_looks_like_blend,
                            "_parent_source_field": parent_source_field,
                            "_source_fields": set(),
                            "_children_with_amounts": [],
                            "_children_without_amounts": set(),
                        }
                        nested_parent_groups[group_key] = group

                    group["_source_fields"].add(source_field)
                    if parent_header and parent_header.get("source_field"):
                        group["_source_fields"].add(parent_header["source_field"])
                    child_name = (ingredient.get('name', '') or '').strip()
                    child_qty = ingredient.get('quantity')
                    child_unit = ingredient.get('unit', '') or ''
                    if isinstance(child_qty, (int, float)) and child_qty > 0 and child_name:
                        group["_children_with_amounts"].append(
                            {"name": child_name, "amount": float(child_qty), "unit": child_unit}
                        )
                    elif child_name:
                        group["_children_without_amounts"].add(child_name)

                    # Sprint E1.2.1: when the cleaner flattened a parent
                    # container, it stashed the parent's mass onto each
                    # child as parentBlendMass / parentBlendUnit. Recover
                    # total_weight from there — member quantities on
                    # flattened NP children are almost always zero.
                    parent_blend_mass = ingredient.get("parentBlendMass")
                    parent_blend_unit = ingredient.get("parentBlendUnit") or ""
                    if (
                        isinstance(parent_blend_mass, (int, float))
                        and parent_blend_mass > 0
                        and parent_blend_mass > group["total_weight"]
                    ):
                        group["total_weight"] = float(parent_blend_mass)
                        group["unit"] = parent_blend_unit

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
            keyword_blend = group.pop("_keyword_blend", True)
            # D3 opacity gate: a keyword-less parent is a proprietary blend only
            # when OPAQUE — total weight shown, every child amount withheld. Any
            # disclosed child makes it a transparent aggregate, not a blend, so
            # B5 must not fire on it. (Keyword-named blends are kept regardless.)
            is_opaque = bool(without_amounts) and not with_amounts
            if not keyword_blend and not is_opaque:
                continue
            source_fields = sorted(group.pop("_source_fields", set()))
            parent_source_field = group.pop("_parent_source_field", None)
            group["source_fields"] = source_fields
            if parent_source_field:
                group["source_field"] = parent_source_field
                group["source_path"] = parent_source_field
            elif source_fields:
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
        - disclosure/amount/children: prefer the cleaner's structured parent
          ownership when present
        - classification: preserve detector_group from the detector
        - blend_name: prefer cleaning (better UI display, label-facing)
        - detector_group: preserve detector's classification category
        - sources: union of both

        AUDIT CLARITY:
        - `name`: Label-facing blend name (from cleaning when available)
        - `detector_group`: Detector's classification (e.g., "General Proprietary Blends")
        This preserves both the human-readable label name and the detector category.
        """
        merged = {}

        def label_identity(blend: Dict) -> str:
            evidence = blend.get("evidence") or {}
            matched_text = evidence.get("matched_text")
            return str(matched_text or blend.get("name") or "").lower().strip()

        def dedupe_key(blend: Dict) -> tuple:
            """Generate deduplication key matching B4 scoring logic.

            Keeps nested_count so genuinely-distinct same-name disclosed blends
            stay separate; the header/body split is collapsed by the post-merge
            consolidation pass below, not here.
            """
            name = label_identity(blend)
            mg = blend.get("total_weight")
            # 5mg bucket to tolerate parsing variance
            mg_bucket = int(round(mg / 5.0) * 5) if mg and mg > 0 else None
            nested = blend.get("nested_count", 0)
            return (name, mg_bucket, nested)

        def blend_source_paths(blend: Dict) -> set[str]:
            paths = {
                str(path)
                for path in blend.get("source_fields", [])
                if path
            }
            if blend.get("source_field"):
                paths.add(str(blend["source_field"]))
            return paths

        def same_source_detector_alias(detector: Dict, cleaner: Dict) -> bool:
            if not (blend_source_paths(detector) & blend_source_paths(cleaner)):
                return False
            detector_evidence = detector.get("evidence") or {}
            matched_text = self._normalize_exclusion_text(
                str(detector_evidence.get("matched_text") or "")
            )
            cleaner_name = self._normalize_exclusion_text(
                str(cleaner.get("name") or "")
            )
            if not matched_text or not cleaner_name:
                return False
            return bool(
                re.search(
                    r"(?<![a-z0-9])" + re.escape(matched_text) + r"(?![a-z0-9])",
                    cleaner_name,
                )
            )

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

            if key not in merged:
                alias_key = next(
                    (
                        existing_key
                        for existing_key, existing in merged.items()
                        if existing.get("detector_group") is not None
                        and same_source_detector_alias(existing, cleaning_blend)
                    ),
                    None,
                )
                if alias_key is not None:
                    key = alias_key

            if key in merged:
                # Blend exists from detector - merge sources and prefer cleaning name
                existing = merged[key]
                # Union sources
                existing_sources = set(existing.get("sources", []))
                existing_sources.add("cleaning")
                existing["sources"] = list(existing_sources)
                # Preserve source field provenance.
                merged_source_paths = set(existing.get("source_fields", []))
                if existing.get("source_field"):
                    merged_source_paths.add(existing["source_field"])
                if cleaning_blend.get("source_field"):
                    merged_source_paths.add(cleaning_blend["source_field"])
                for path in cleaning_blend.get("source_fields", []):
                    if path:
                        merged_source_paths.add(path)
                existing["source_fields"] = sorted(merged_source_paths)
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
                    if cleaning_blend.get("disclosure_level") in {"none", "partial", "full"}:
                        existing["disclosure_level"] = cleaning_blend["disclosure_level"]
                    for field in ("nested_count", "total_weight", "unit"):
                        if cleaning_blend.get(field) is not None:
                            existing[field] = cleaning_blend[field]
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

        # Post-merge consolidation of the header/body split.
        # The single-pass cleaning extractor emits one blend TWICE — a 0-child
        # header row AND the aggregated nested-children body — with distinct
        # dedupe keys (different nested_count), so both survive here and B5 then
        # double-penalizes the blend (this list feeds enriched["proprietary_blends"]).
        # Within a (name, mg_bucket) group: keep every DISCLOSED entry (so two
        # genuinely-distinct same-name disclosed blends stay separate — the
        # B4-parity case in test_blend_merge_pipeline), drop 0-child headers when a
        # disclosed body exists, and collapse all-opaque duplicates to one.
        def _consol_bucket(b: Dict):
            mg = b.get("total_weight")
            return int(round(mg / 5.0) * 5) if mg and mg > 0 else None

        groups: Dict[tuple, List[Dict]] = {}
        order: List[tuple] = []
        for b in merged.values():
            gkey = (label_identity(b), _consol_bucket(b))
            groups.setdefault(gkey, [])
            if gkey not in order:
                order.append(gkey)
            groups[gkey].append(b)

        def _has_children(b: Dict) -> bool:
            return bool(b.get("child_ingredients")) or (int(b.get("nested_count") or 0) > 0)

        consolidated: List[Dict] = []
        for gkey in order:
            group = groups[gkey]
            disclosed = [b for b in group if _has_children(b)]
            if disclosed:
                consolidated.extend(disclosed)  # drop 0-child header(s)
            else:
                consolidated.append(group[0])  # collapse all-opaque duplicates to one
        return consolidated

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
        # Legacy display field: kept for UI + back-compat. Source is now CLAIMED
        # only (label regex + rules-db). Manufacturer-level signals no longer
        # land here — they live in certification_data.manufacturer_cert_signals.
        enriched["named_cert_programs"] = named_programs

        # v4 P0.1b: project verified_cert_programs to top-level so the scorer
        # reads it directly. Only these score B4a points (sku/product_line +
        # not stale). Other fields are display-only.
        enriched["verified_cert_programs"] = certification_data.get("verified_cert_programs", []) or []
        enriched["manufacturer_cert_signals"] = certification_data.get("manufacturer_cert_signals", []) or []

        gmp_data = certification_data.get("gmp", {}) or {}
        if bool(
            gmp_data.get("nsf_gmp")
            or gmp_data.get("gmp_certified_or_compliant")
            or (
                gmp_data.get("claimed")
                and not gmp_data.get("fda_registered")
            )
        ):
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

        ingredients = ingredient_quality_data.get("ingredients_scorable", []) or []
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

    @staticmethod
    def _clinical_ui_evidence_scope(evidence_level: Any) -> str:
        level = str(evidence_level or "").strip().lower()
        if level == "product-human":
            return "product"
        if level == "branded-rct":
            return "branded_ingredient"
        if level in {"ingredient-human", "strain-clinical"}:
            return "ingredient"
        return "indirect"

    def _collect_evidence_data(
        self, product: Dict, ingredient_quality_data: Optional[Dict] = None
    ) -> Dict:
        """
        Collect clinical evidence data for scoring Section C.

        When ``ingredient_quality_data`` is supplied (post-Phase 4 of
        identity_bioactivity_split), the matcher ALSO walks each ingredient's
        ``delivers_markers[]`` and adds marker-via-ingredient clinical matches.
        Each marker match carries ``marker_via_ingredient`` (the source
        canonical) and ``marker_confidence_scale`` (0.0–1.0) so the scorer
        can apply the appropriate Section C confidence weighting.
        """
        clinical_db = self.databases.get('backed_clinical_studies', {})
        studies = clinical_db.get('backed_clinical_studies', [])

        active_ingredients = self._primary_active_ingredients_for_enrichment(
            product,
            ingredient_quality_data=ingredient_quality_data,
        )
        matches = []
        product_text = self._get_all_product_text(product)

        quality_rows = []
        if isinstance(ingredient_quality_data, dict):
            quality_rows = [
                row
                for row in (
                    ingredient_quality_data.get("ingredients_scorable")
                    or ingredient_quality_data.get("ingredients")
                    or []
                )
                if isinstance(row, dict)
            ]

        def _identity_key_values(row: Dict, fields: Tuple[str, ...]) -> set:
            out = set()
            for field in fields:
                value = row.get(field)
                if not value:
                    continue
                normalized = norm_module.make_normalized_key(str(value))
                if normalized:
                    out.add(normalized)
            return out

        def _same_quantity_unit(left: Dict, right: Dict) -> bool:
            left_qty = left.get("quantity")
            right_qty = right.get("quantity")
            if not isinstance(left_qty, (int, float)) or not isinstance(right_qty, (int, float)):
                return True
            try:
                if abs(float(left_qty) - float(right_qty)) > 1e-9:
                    return False
            except (TypeError, ValueError):
                return True
            left_unit = str(left.get("unit") or "").strip().lower()
            right_unit = str(right.get("unit") or "").strip().lower()
            return not left_unit or not right_unit or left_unit == right_unit

        def _quality_rows_for_ingredient(ingredient: Dict) -> List[Dict]:
            ingredient_keys = _identity_key_values(
                ingredient,
                ("name", "standardName", "standard_name", "raw_source_text"),
            )
            if not ingredient_keys:
                return []

            rows: List[Dict] = []
            for row in quality_rows:
                if str(row.get("source_section") or "active").lower() != "active":
                    continue
                row_keys = _identity_key_values(
                    row,
                    ("name", "standard_name", "raw_source_text", "original_label"),
                )
                if ingredient_keys.intersection(row_keys) and _same_quantity_unit(ingredient, row):
                    rows.append(row)
            return rows

        def _clinical_form_candidates(ingredient: Dict, quality_matches: List[Dict]) -> List[str]:
            """Structured form labels can carry the clinical product identity.

            Example: DSLD stores PureWay-C under activeIngredients[].forms while
            the row name remains just "Vitamin C". Evidence matching must see
            that form text, but source/provenance forms such as "from Acerola"
            should not become independent clinical identities.
            """
            out: List[str] = []
            for form in ingredient.get("forms") or []:
                if not isinstance(form, dict):
                    continue
                name = str(form.get("name") or "").strip()
                if not name:
                    continue
                if self._is_source_descriptor_form(form, parent_row=ingredient):
                    continue
                out.append(name)

            # Quality-map rows carry the normalized form identity.
            # Evidence matching needs that identity too; raw DSLD text can say
            # "TRAACS Magnesium Bisglycinate Chelate" while the verified
            # clinical entry is keyed as "Magnesium Glycinate".
            for quality_row in quality_matches:
                for field in ("matched_form", "form_id", "matched_alias", "branded_token_extracted"):
                    value = str(quality_row.get(field) or "").strip()
                    if value:
                        out.append(value)
                for matched_form in quality_row.get("matched_forms") or []:
                    if not isinstance(matched_form, dict):
                        continue
                    for field in ("form_key", "matched_candidate", "raw_form_text"):
                        value = str(matched_form.get(field) or "").strip()
                        if value:
                            out.append(value)
                for extracted_form in quality_row.get("extracted_forms") or []:
                    if not isinstance(extracted_form, dict):
                        continue
                    for field in ("raw_form_text", "display_form"):
                        value = str(extracted_form.get(field) or "").strip()
                        if value:
                            out.append(value)
                    for candidate in extracted_form.get("match_candidates") or []:
                        value = str(candidate or "").strip()
                        if value:
                            out.append(value)
            return out

        for ingredient in active_ingredients:
            ing_name = ingredient.get('name', '')
            std_name = ingredient.get('standardName', '') or ing_name
            quality_matches = _quality_rows_for_ingredient(ingredient)
            candidate_names = [
                ing_name,
                std_name,
                ingredient.get("raw_source_text", ""),
            ]
            candidate_names.extend(_clinical_form_candidates(ingredient, quality_matches))
            branded_token = ingredient.get("branded_token_extracted") or self._product_context_branded_token_for_ingredient(
                product_text,
                ingredient,
                ing_name,
                std_name,
            )
            if branded_token:
                candidate_names.append(branded_token)
            seen_study_ids = set()

            for study in studies:
                study_name = study.get('standard_name', '')
                study_aliases = self._collect_clinical_aliases(study)
                matched = self._clinical_study_match(candidate_names, study)

                if matched:

                    # For brand-specific studies, check brand mention
                    study_id = study.get('id', '')
                    if study_id.startswith('BRAND_'):
                        # A row-level exact standard-name match is itself an
                        # explicit label mention of the branded ingredient
                        # (e.g. "KSM-66" active row). Alias-only matches still
                        # require broader product-text confirmation because
                        # some BRAND_ aliases are generic ingredient names.
                        row_level_brand_match = matched.get("method") in {
                            "standard_name",
                            "standard_name_key",
                        }
                        if (
                            not row_level_brand_match
                            and not self._brand_mentioned(
                                study_name,
                                study_aliases,
                                product,
                                brand_tokens=study.get("brand_tokens"),
                            )
                        ):
                            continue

                    if study_id in seen_study_ids:
                        continue
                    seen_study_ids.add(study_id)

                    evidence_level = study.get('evidence_level', 'ingredient-human')
                    match_payload = {
                        "ingredient": ing_name,
                        "standard_name": study_name,
                        "id": study_id,
                        "study_id": study_id,
                        "study_name": study_name,
                        "match_method": matched.get("method"),
                        "matched_term": matched.get("matched_term"),
                        "evidence_level": evidence_level,
                        "ui_evidence_scope": self._clinical_ui_evidence_scope(evidence_level),
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
                        "effect_direction",
                        "effect_direction_rationale",
                        "effect_direction_confidence",
                        "total_enrollment",
                        "published_studies",
                        "published_studies_count",
                        "published_rct_count",
                        "published_meta_review_count",
                        "registry_completed_trials_count",
                        "primary_outcome",
                        "endpoint_relevance_tags",
                        "notes",
                        "notable_studies",
                        "references_structured",
                    ]
                    for field in optional_fields:
                        if field in study and study.get(field) is not None:
                            match_payload[field] = study.get(field)

                    matches.append(match_payload)

        # =====================================================================
        # Identity vs Bioactivity Split — secondary marker matches
        # =====================================================================
        # Walk delivers_markers[] on each enriched ingredient. For markers with
        # confidence_scale > 0, add clinical matches that the marker triggers
        # but stamp them with marker_via_ingredient + marker_confidence_scale
        # so the scorer can apply confidence scaling and avoid double-credit
        # with primary canonical matches.
        existing_study_ids = {
            (m.get("study_id") or m.get("id"))
            for m in matches if (m.get("study_id") or m.get("id"))
        }
        ingredients_with_markers = []
        if isinstance(ingredient_quality_data, dict):
            ingredients_with_markers = (
                ingredient_quality_data.get("ingredients_scorable")
                or ingredient_quality_data.get("ingredients")
                or []
            )
        for ing in ingredients_with_markers:
            if not isinstance(ing, dict):
                continue
            primary_canonical = ing.get("canonical_id")
            for marker_entry in ing.get("delivers_markers", []) or []:
                if not isinstance(marker_entry, dict):
                    continue
                confidence = marker_entry.get("confidence_scale")
                try:
                    confidence_f = float(confidence) if confidence is not None else 0.0
                except (TypeError, ValueError):
                    confidence_f = 0.0
                if confidence_f <= 0:
                    continue
                marker_id = marker_entry.get("marker_canonical_id")
                if not marker_id:
                    continue
                marker_candidate_names = [marker_id, marker_id.replace("_", " ")]
                for study in studies:
                    study_id = study.get("id", "")
                    if not study_id or study_id in existing_study_ids:
                        continue
                    study_name = study.get("standard_name", "") or ""
                    study_aliases = self._collect_clinical_aliases(study)
                    matched = self._clinical_study_match(marker_candidate_names, study)
                    if not matched:
                        continue
                    # Skip brand-specific studies for marker-via path
                    if study_id.startswith("BRAND_"):
                        continue
                    evidence_level = study.get("evidence_level", "ingredient-human")
                    match_payload = {
                        "ingredient": ing.get("name") or ing.get("raw_source_text"),
                        "standard_name": study_name,
                        "id": study_id,
                        "study_id": study_id,
                        "study_name": study_name,
                        "match_method": matched.get("method"),
                        "matched_term": matched.get("matched_term"),
                        "evidence_level": evidence_level,
                        "ui_evidence_scope": self._clinical_ui_evidence_scope(evidence_level),
                        "study_type": study.get("study_type", "rct_single"),
                        "score_contribution": study.get("score_contribution", "tier_3"),
                        "health_goals_supported": study.get("health_goals_supported", []),
                        "key_endpoints": study.get("key_endpoints", []),
                        # Identity vs Bioactivity provenance
                        "marker_via_ingredient": primary_canonical,
                        "marker_confidence_scale": confidence_f,
                        "marker_estimation_method": marker_entry.get("estimation_method"),
                        "marker_estimated_dose_mg": marker_entry.get("estimated_dose_mg"),
                        "marker_evidence_id": marker_entry.get("evidence_id"),
                    }
                    optional_fields = [
                        "min_clinical_dose", "dose_unit", "typical_effective_dose", "dose_range",
                        "base_points", "multiplier", "computed_score", "effect_direction",
                        "effect_direction_rationale", "effect_direction_confidence",
                        "total_enrollment", "published_studies", "published_studies_count",
                        "published_rct_count", "published_meta_review_count",
                        "registry_completed_trials_count", "primary_outcome",
                        "endpoint_relevance_tags", "notes", "notable_studies",
                        "references_structured",
                    ]
                    for field in optional_fields:
                        if field in study and study.get(field) is not None:
                            match_payload[field] = study.get(field)
                    matches.append(match_payload)
                    existing_study_ids.add(study_id)

        # Check for unsubstantiated claims
        all_text = self._get_all_product_text(product)
        unsubstantiated = self._check_unsubstantiated_claims(all_text)

        return {
            "clinical_matches": matches,
            "match_count": len(matches),
            "unsubstantiated_claims": unsubstantiated
        }

    def _brand_mentioned(
        self,
        study_name: str,
        aliases: List[str],
        product: Dict,
        brand_tokens: Optional[List[str]] = None,
    ) -> bool:
        """Return whether the label explicitly names the studied brand.

        ``aliases`` remains the identity-discovery surface and may legitimately
        contain a generic ingredient name. A BRAND_ study instead gates on its
        curated ``brand_tokens`` when present. Older records fall back to their
        study name/aliases, with every match token bounded.
        """
        all_text = self._get_all_product_text_lower(product)
        terms = brand_tokens if brand_tokens else [study_name, *aliases]
        for term in terms:
            normalized = str(term or "").strip().lower()
            if normalized and re.search(
                rf"(?<!\w){re.escape(normalized)}(?!\w)", all_text
            ):
                return True
        return False

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

        top_manufacturer = self._check_top_manufacturer(brand_name, manufacturer)
        return {
            "brand_name": brand_name,
            "manufacturer": manufacturer,
            "top_manufacturer": top_manufacturer,
            "violations": self._check_violations(brand_name, manufacturer),
            "country_of_origin": self._extract_country(product, top_manufacturer),
            "bonus_features": self._collect_bonus_features(product)
        }

    def _enrich_display_ingredients(self, enriched: Dict) -> List[Dict]:
        """Attach canonical references to display rows without changing scoring behavior."""
        display_rows = enriched.get("display_ingredients")
        if not isinstance(display_rows, list):
            return display_rows or []

        ingredient_lookup: Dict[str, Dict[str, str]] = {}

        def _register_lookup(ingredient: Dict, source_key: str) -> None:
            raw_text = ingredient.get("raw_source_text") or ingredient.get("name")
            standard_name = (
                ingredient.get("standardName")
                or ingredient.get("standard_name")
                or ingredient.get("name")
            )
            if not raw_text or not standard_name:
                return
            ingredient_lookup.setdefault(
                raw_text,
                {
                    "standard_name": standard_name,
                    "source_section": "active" if source_key == "activeIngredients" else "inactive",
                    "raw_source_path": ingredient.get("raw_source_path", source_key),
                },
            )

        for source_key in ("activeIngredients", "inactiveIngredients"):
            for ingredient in enriched.get(source_key, []) or []:
                if isinstance(ingredient, dict):
                    _register_lookup(ingredient, source_key)

        annotated_rows: List[Dict] = []
        for row in display_rows:
            if not isinstance(row, dict):
                annotated_rows.append(row)
                continue
            row_copy = dict(row)
            if row_copy.get("display_type") in ("mapped_ingredient", "inactive_ingredient"):
                raw_text = row_copy.get("raw_source_text")
                mapped_target = ingredient_lookup.get(raw_text)
                if mapped_target:
                    row_copy["mapped_to"] = dict(mapped_target)
            annotated_rows.append(row_copy)

        return annotated_rows

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
            brand_family_exact = self._brand_family_exact_match(brand, std_name, aliases)
            mfr_family_exact = self._brand_family_exact_match(manufacturer, std_name, aliases)

            if brand_exact or mfr_exact or brand_family_exact or mfr_family_exact:
                # Determine which input matched (AC2)
                matched_source = "brandName" if (brand_exact or brand_family_exact) else "manufacturer"
                matched_raw = brand if (brand_exact or brand_family_exact) else manufacturer
                matched_normalized = brand_normalized if (brand_exact or brand_family_exact) else mfr_normalized

                return {
                    "found": True,
                    "manufacturer_id": top_mfr.get('id', ''),
                    "name": std_name,
                    "match_type": "exact",
                    "match_detail": "brand_family_prefix" if (brand_family_exact or mfr_family_exact) else "exact_or_alias",
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

    def _brand_family_exact_match(self, value: str, target_name: str, aliases: List[str]) -> bool:
        """
        Treat explicit brand-family prefixes as exact manufacturer matches.

        This covers labels such as "GNC Beyond Raw" and "GNC Pro Performance".
        They are not fuzzy matches: the first token is the trusted brand itself,
        with the remaining text being a product line or sub-brand.
        """
        value_norm = self._normalize_company_name(value)
        if not value_norm:
            return False

        family_candidates = [target_name] + list(aliases or [])
        for candidate in family_candidates:
            candidate_norm = self._normalize_company_name(candidate)
            if not candidate_norm:
                continue
            if len(candidate_norm) < 3:
                continue
            if value_norm.startswith(f"{candidate_norm} "):
                return True
        return False

    def _check_violations(self, brand: str, manufacturer: str) -> Dict:
        """
        Check for manufacturer violations using deterministic company matching.

        Safety policy:
        - Violation penalties must NEVER be driven by fuzzy name similarity.
        - Only exact matches (after company normalization) are eligible.
        - Optional approved aliases can be supplied per violation record.
        """
        violations_db = self.databases.get('manufacturer_violations', {})
        violations_list = violations_db.get('manufacturer_violations', [])
        brand_norm = self._normalize_company_name(brand)
        manufacturer_norm = self._normalize_company_name(manufacturer)

        found = []
        for violation in violations_list:
            mfr_name = violation.get('manufacturer', '')
            if not mfr_name:
                continue

            approved_aliases = []
            for field in ("aliases", "manufacturer_aliases"):
                value = violation.get(field)
                if isinstance(value, list):
                    approved_aliases.extend([str(alias).strip() for alias in value if str(alias).strip()])

            match_source = None
            matched_candidate = None
            for candidate in [mfr_name] + approved_aliases:
                candidate_norm = self._normalize_company_name(candidate)
                if not candidate_norm:
                    continue
                if manufacturer_norm and manufacturer_norm == candidate_norm:
                    match_source = "manufacturer"
                    matched_candidate = candidate
                    break
                if brand_norm and brand_norm == candidate_norm:
                    match_source = "brandName"
                    matched_candidate = candidate
                    break

            if not match_source:
                continue

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
                "match_confidence": 1.0,
                "match_method": "exact_company_normalized",
                "match_source": match_source,
                "matched_manufacturer": mfr_name,
                "matched_alias": matched_candidate if matched_candidate and matched_candidate != mfr_name else None,
                # Path C authored field — user-facing brand-trust summary.
                "brand_trust_summary": violation.get("brand_trust_summary"),
                "reason": violation.get("reason"),
                "user_facing_note": violation.get("user_facing_note"),
                "manufacturer_id": violation.get('manufacturer_id', ''),
                "manufacturer_family_id": violation.get('manufacturer_family_id', ''),
                "manufacturer_family_name": violation.get('manufacturer_family_name', ''),
                "manufacturer_family_aliases": violation.get('manufacturer_family_aliases', []),
                "related_brand_cluster_id": violation.get('related_brand_cluster_id', ''),
                "related_brand_cluster_name": violation.get('related_brand_cluster_name', ''),
                "related_brand_cluster_aliases": violation.get('related_brand_cluster_aliases', []),
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

    def _extract_country(self, product: Dict, top_manufacturer: Optional[Dict] = None) -> Dict:
        """Extract country of origin data.

        Detection order:
        1. Regex scan of label text ("made in USA", etc.)
        2. Structured contacts[].contactDetails.country for Manufacturer contacts
        3. Verified country of an EXACT top-manufacturer match (manufacturer HQ /
           regulatory jurisdiction from top_manufacturers_data.json). Most labels
           print no "made in" text and carry no manufacturer-country contact, so
           without this ~78% of products had no country and silently lost the
           manufacturer-trust high-standard-region (D4) point even for known
           USA/EU/CA/etc. brands. The label/contact signals above still take
           precedence (they describe the actual product), with the manufacturer
           jurisdiction as the fallback.
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
                country = eu_match.group(3)

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

        country_source = "label_or_contact" if country else ""

        # Final fallback: verified country of an exact top-manufacturer match.
        if not country and isinstance(top_manufacturer, dict) and top_manufacturer.get("found"):
            mfr_country = (self._top_manufacturer_country(top_manufacturer.get("manufacturer_id")) or "").strip()
            if mfr_country:
                country = mfr_country
                country_source = "top_manufacturer_jurisdiction"
                if mfr_country.lower() in self._HIGH_REG_COUNTRIES:
                    high_reg = True

        return {
            "detected": country != "",
            "country": country,
            "high_regulation_country": high_reg,
            "source": country_source,
        }

    def _top_manufacturer_country(self, manufacturer_id: Optional[str]) -> str:
        """Verified `country` for a manufacturer id from top_manufacturers_data.json
        (only the research-verified records carry one; unverified ones do not, so
        they correctly yield no country)."""
        if not manufacturer_id:
            return ""
        if getattr(self, "_top_mfr_country_cache", None) is None:
            top_db = self.databases.get("top_manufacturers_data", {}) or {}
            self._top_mfr_country_cache = {
                str(row.get("id")): str(row.get("country") or "")
                for row in top_db.get("top_manufacturers", [])
                if isinstance(row, dict) and row.get("id")
            }
        return self._top_mfr_country_cache.get(str(manufacturer_id), "")

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

    # Branded / marketing survivability markers. Canonical delivery
    # technologies (spore-based, microencapsulated, acid-resistant,
    # delayed-release, enteric-coated) live in
    # scripts/data/form_keywords_vocab.json under the
    # ``probiotic_delivery`` category — the canonical-form match runs
    # through form_vocab.matches_probiotic_delivery() at use sites.
    # This list captures branded names (BIO-tract, LiveBac, DRcaps) and
    # marketing copy ("survives stomach acid") that aren't chemistry
    # forms but still indicate survivability technology on the label.
    SURVIVABILITY_BRAND_MARKERS = [
        "bio-tract", "biotract", "livebac",
        "dr caps", "drcaps",
        "survives stomach acid", "stomach acid resistant",
        "patented delivery", "targeted release",
        "bacillus coagulans", "bacillus subtilis",  # inherently spore-forming species
        "protected by an outer layer", "protected by patented",
        "outer protective layer", "proprietary coating",
        "acid-resistant coating",
        "protective coating", "survives digestive tract",
        "survives gi tract", "gastric bypass",
        "protected strain", "protected probiotic",
    ]

    # P0.5 — fallback prebiotic vocabulary used when scoring_config.json is
    # unavailable. Must stay byte-equal to the scorer's fallback in
    # score_supplements.py _compute_probiotic_category_bonus so the two paths
    # agree even without config. The authoritative list lives in
    # scoring_config.section_A_ingredient_quality.probiotic_bonus.prebiotic_terms;
    # _get_prebiotic_terms() prefers config and falls back here.
    _PREBIOTIC_TERMS_FALLBACK = [
        "inulin", "fos", "gos", "chicory", "acacia",
        "beta-glucan", "beta glucan", "pea fiber", "lactulose",
        "fructooligosaccharide", "galactooligosaccharide",
        "xos", "xylooligosaccharide", "raftiline", "raftilose",
        "preforpro", "bacteriophage", "bacteriophages",
    ]

    def _get_prebiotic_terms(self) -> list:
        """Single source of truth for prebiotic substring vocabulary.

        Reads scripts/config/scoring_config.json section
        `section_A_ingredient_quality.probiotic_bonus.prebiotic_terms` so
        the enricher's display-side detection stays aligned with the
        scorer's credit-side detection. Cached on the enricher instance
        to avoid re-reading on every product.
        """
        cached = getattr(self, "_prebiotic_terms_cache", None)
        if cached is not None:
            return cached
        terms: list = []
        try:
            from pathlib import Path as _Path
            import json as _json
            cfg_path = _Path(__file__).resolve().parent / "config" / "scoring_config.json"
            cfg = _json.loads(cfg_path.read_text(encoding="utf-8"))
            pro_cfg = (
                cfg.get("section_A_ingredient_quality", {})
                   .get("probiotic_bonus", {})
            )
            cfg_terms = pro_cfg.get("prebiotic_terms")
            if isinstance(cfg_terms, list) and cfg_terms:
                terms = [str(t).strip().lower() for t in cfg_terms if t]
        except (OSError, ValueError, KeyError):
            terms = []
        if not terms:
            terms = list(self._PREBIOTIC_TERMS_FALLBACK)
        self._prebiotic_terms_cache = terms
        return terms

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

        # Extract product-level CFU statement ONCE to avoid per-strain overcounting
        statement_parts: List[str] = []
        statement_paths: List[str] = []
        for idx, statement in enumerate(product.get('statements', []) or []):
            if isinstance(statement, dict):
                text = statement.get('notes', '') or statement.get('text', '') or ""
            elif isinstance(statement, str):
                text = statement
            else:
                continue
            if text:
                statement_parts.append(str(text))
                statement_paths.append(f"statements[{idx}]")
        product_statements_text = ' '.join(statement_parts)
        product_cfu_source_path = statement_paths[0] if len(statement_paths) == 1 else ("statements" if statement_paths else None)
        product_level_cfu = self._extract_cfu(
            product_statements_text,
            source_path=product_cfu_source_path,
            evidence_scope="product_level",
        )
        if not product_level_cfu.get("has_cfu"):
            for field_name in ("product_name", "fullName", "bundleName"):
                field_text = str(product.get(field_name) or "").strip()
                if not field_text:
                    continue
                field_cfu = self._extract_cfu(
                    field_text,
                    source_path=field_name,
                    evidence_scope="product_level",
                )
                if field_cfu.get("has_cfu"):
                    field_cfu["source"] = "product_identity"
                    product_level_cfu = field_cfu
                    break

        # Check if this is a probiotic product
        probiotic_blends = []
        total_strains = 0
        all_nested_strains = []

        def _row_path(row: Dict) -> str:
            return str(row.get("raw_source_path") or "").strip()

        def _parent_path(path: str) -> str:
            marker = ".nestedRows["
            return path.split(marker, 1)[0] if marker in path else ""

        def _is_probiotic_identity(ingredient: Dict) -> bool:
            ing_name = str(ingredient.get('name', '') or '').lower()
            std_name = str(ingredient.get('standardName', '') or '').lower()
            category = str(ingredient.get('category', '') or '').lower()
            return (
                bool(_PROBIOTIC_IDENTITY_RE.search(f"{ing_name} {std_name}"))
                or 'probiotic' in category
                or 'bacteria' in category
            )

        def _is_blend_header_total(ingredient: Dict) -> bool:
            role = str(ingredient.get("cleaner_row_role") or "").lower()
            hierarchy = str(ingredient.get("hierarchyType") or "").lower()
            reason = str(ingredient.get("score_exclusion_reason") or "").lower()
            dose_class = str(ingredient.get("dose_class") or "").lower()
            return (
                role == "blend_header_total"
                or hierarchy == "blend_header"
                or reason == "blend_header_total"
                or dose_class == "blend_total_weight"
            )

        flattened_child_parent_paths = {
            _parent_path(_row_path(ingredient))
            for ingredient in active_ingredients
            if _parent_path(_row_path(ingredient)) and _is_probiotic_identity(ingredient)
        }

        for ingredient in active_ingredients:
            # Check for probiotic indicators (including abbreviated forms and
            # strain names) using bounded terms. Substring matching made
            # "casein decapeptide" look like L. casei and polluted route
            # classification with false probiotic_data.
            ingredient_source_path = ingredient.get("raw_source_path") or "activeIngredients"
            is_probiotic = _is_probiotic_identity(ingredient) or (
                _is_blend_header_total(ingredient)
                and ingredient_source_path in flattened_child_parent_paths
            )

            if is_probiotic:
                nested = ingredient.get('nestedIngredients', [])
                harvest = ingredient.get('harvestMethod', '') or ''
                notes = ingredient.get('notes', '') or ''

                # P1.1: Extract CFU from per-strain text only (not product statements)
                cfu_text = harvest + ' ' + notes
                cfu_data = self._extract_cfu(
                    cfu_text,
                    ingredient=ingredient,
                    source_path=ingredient_source_path,
                    evidence_scope="row_level",
                )

                self.logger.debug(
                    "CFU extraction for ingredient %s -> %s",
                    ingredient.get('name', ''),
                    cfu_data,
                )

                header_has_flattened_children = (
                    _is_blend_header_total(ingredient)
                    and ingredient_source_path in flattened_child_parent_paths
                )
                strain_names = (
                    [n.get('name', '') for n in nested]
                    if nested
                    else ([] if header_has_flattened_children else [ingredient.get('name', '')])
                )
                strain_identity_texts = [
                    " ".join(
                        str(piece).strip()
                        for piece in (
                            n.get("name", ""),
                            n.get("standardName", ""),
                            n.get("standard_name", ""),
                            n.get("ingredientGroup", ""),
                            n.get("notes", ""),
                            " ".join(
                                str(form.get("name") if isinstance(form, dict) else form).strip()
                                for form in (n.get("forms") or [])
                            ),
                        )
                        if str(piece or "").strip()
                    )
                    for n in nested
                ] if nested else ([] if header_has_flattened_children else [ingredient.get('name', '')])

                probiotic_blends.append({
                    "name": ingredient.get('name', ''),
                    "strain_count": len(strain_names),
                    "strains": strain_names,
                    "strain_identity_texts": strain_identity_texts,
                    "cfu_data": cfu_data,
                    "raw_source_path": ingredient_source_path,
                    "is_blend_header_total": header_has_flattened_children,
                })

                total_strains += len(strain_names)
                all_nested_strains.extend(strain_names)

        if not probiotic_blends:
            return {"is_probiotic_product": False}

        # Check for clinically relevant strains
        strains_db = self.databases.get('clinically_relevant_strains', {})
        clinical_strains = strains_db.get('clinically_relevant_strains', [])

        found_clinical_strains = []
        # Sprint E1.3.2 — iterate blends instead of flat strain list so we
        # can attach per-strain CFU context to each match. Single-strain
        # blends use the blend's CFU directly; multi-strain blends don't
        # attach a per-strain CFU (per dev rule: "No blend-total inference
        # for probiotics"). When cfu_per_day is None the adequacy tier is
        # also None — downstream downgrade handles it gracefully.
        # Lazy-import code-level constants (clinician decision 2026-05-01).
        # BLOCKED → reject (S. uberis KJ2, S. oralis JH145).
        # HOLD    → defer (S. rattus JH145, S. oralis KJ3) — same handling
        #           as BLOCKED for now.
        try:
            from constants import BLOCKED_PROBIOTIC_STRAINS, HOLD_PROBIOTIC_STRAINS
        except ImportError:  # pragma: no cover - defensive
            BLOCKED_PROBIOTIC_STRAINS = set()
            HOLD_PROBIOTIC_STRAINS = set()
        _BLOCKED_OR_HOLD = (BLOCKED_PROBIOTIC_STRAINS | HOLD_PROBIOTIC_STRAINS)

        # Postbiotic / inactivated-form detection. Patterns sourced from
        # scripts/data/form_keywords_vocab.json (postbiotic_keywords
        # category). These products do NOT contain live probiotic
        # content; CFU thresholds do not apply and bio_score class
        # differs (cell-wall fragments interact with gut immune cells
        # locally). Per dev review 2026-05-01.
        def _is_postbiotic(strain_text: str, blend_text: str = "") -> bool:
            haystack = f"{strain_text} {blend_text}"
            return _form_vocab.matches_postbiotic(haystack)

        for blend in probiotic_blends:
            blend_strains = blend.get("strains") or []
            blend_strain_identities = blend.get("strain_identity_texts") or blend_strains
            blend_name = blend.get("name", "") or blend.get("blend_name", "") or ""
            blend_cfu = (blend.get("cfu_data") or {}).get("cfu_count")
            per_strain_cfu = (
                float(blend_cfu)
                if isinstance(blend_cfu, (int, float)) and blend_cfu > 0 and len(blend_strains) == 1
                else None
            )
            for idx, strain in enumerate(blend_strains):
                strain_identity = (
                    blend_strain_identities[idx]
                    if idx < len(blend_strain_identities)
                    else strain
                )
                strain_str = str(strain).strip().lower()
                # Hard block: clinician-decided REJECT/HOLD strains never
                # enter the clinical_strains pool (no CFU credit, no
                # scoring contribution). Surface as a flag for visibility.
                if any(b in strain_str for b in _BLOCKED_OR_HOLD):
                    found_clinical_strains.append({
                        "strain": strain,
                        "clinical_id": "BLOCKED_OR_HOLD",
                        "evidence_level": "rejected",
                        "cfu_per_day": None,
                        "adequacy_tier": None,
                        "clinical_support_level": None,
                        "indication_primary": None,
                        "is_blocked": True,
                        "block_reason": "Clinician REJECT/HOLD strain (CLINICAL_DECISIONS_LOG.md 2026-05-01)",
                        "cfu_confidence": "low",
                        "dose_basis": "inferred",
                        "ui_copy_hint": "blend_not_individually_disclosed",
                    })
                    continue
                postbiotic = _is_postbiotic(str(strain_identity), blend_name)
                for clinical in clinical_strains:
                    clin_name = clinical.get('standard_name', '')
                    clin_aliases = clinical.get('aliases', [])
                    if self._strain_match(strain_identity, clin_name, clin_aliases):
                        thresholds = clinical.get("cfu_thresholds") or {}
                        tiers = thresholds.get("tiers_cfu_per_day") or {}
                        adequacy_tier = _compute_strain_cfu_tier(per_strain_cfu, tiers)
                        support_level = _derive_clinical_support_level(clinical)
                        # Sprint E1.3.2.b — hybrid confidence layer.
                        hybrid = _compute_probiotic_confidence_hybrid(
                            per_strain_cfu,
                            adequacy_tier,
                            support_level,
                            threshold_dose_basis=thresholds.get("dose_basis"),
                        )
                        entry = {
                            "strain": strain,
                            "clinical_id": clinical.get('id', ''),
                            "evidence_level": clinical.get('evidence_level', 'moderate'),
                            # Sprint E1.3.2 additions — carry per-strain
                            # adequacy data for the build-time ingredient
                            # adapter to attach to the blob ingredient.
                            "cfu_per_day": per_strain_cfu,
                            "adequacy_tier": adequacy_tier,
                            "clinical_support_level": support_level,
                            "indication_primary": thresholds.get("indication_primary"),
                            # E1.3.2.b descriptive-only fields.
                            "cfu_confidence": hybrid["cfu_confidence"],
                            "dose_basis": hybrid["dose_basis"],
                            "ui_copy_hint": hybrid["ui_copy_hint"],
                        }
                        # Postbiotic / inactivated form — CFU scoring does
                        # not apply (different mechanism). Scorer hard-gates
                        # on is_inactivated to skip CFU credit.
                        if postbiotic:
                            entry["is_inactivated"] = True
                            entry["is_postbiotic"] = True
                            entry["postbiotic_note"] = (
                                "Heat-killed / inactivated form detected. "
                                "Different mechanism from live probiotic; CFU "
                                "thresholds do not apply."
                            )
                        found_clinical_strains.append(entry)
                        break

        # Check for prebiotic pairing
        prebiotics_data = strains_db.get('prebiotics', {}).get('ingredients', [])
        prebiotic_found = False
        prebiotic_name = ""

        prebiotic_candidates = []
        for ing in all_ingredients:
            ing_name = ing.get('name', '')
            std_name = ing.get('standardName', '') or ing_name
            group = ing.get("ingredientGroup", "")
            notes = ing.get("notes", "")
            prebiotic_candidates.append((ing_name, " ".join(str(v) for v in (std_name, group, notes) if v)))

            # Include nested blend children so prebiotic rows inside proprietary
            # blends are not silently missed.
            for nested_ing in ing.get('nestedIngredients', []) or []:
                if not isinstance(nested_ing, dict):
                    continue
                nested_name = nested_ing.get('name', '')
                nested_std = nested_ing.get('standardName', '') or nested_name
                nested_group = nested_ing.get("ingredientGroup", "")
                nested_notes = nested_ing.get("notes", "")
                prebiotic_candidates.append((
                    nested_name,
                    " ".join(str(v) for v in (nested_std, nested_group, nested_notes) if v),
                ))

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

        # P0.5 fallback: substring-match against the same prebiotic_terms list
        # the scorer uses (`section_A_ingredient_quality.probiotic_bonus.
        # prebiotic_terms` in scoring_config.json). Catches names the strict
        # exact-match path misses, e.g. 'organic Acacia Fiber' (DSLD 274081
        # GoL prenatal), 'FOS (Fructooligosaccharides)' with parentheticals,
        # 'Pea Fiber', 'Raftiline'. Without this, scorer credits prebiotic
        # but probiotic_detail.prebiotic_present stayed false — Codex's
        # split-brain contract finding on the 2026-05-19 RC.
        if not prebiotic_found:
            prebiotic_terms = self._get_prebiotic_terms()
            for ing_name, std_name in prebiotic_candidates:
                ing_norm = (ing_name or '').lower()
                std_norm = (std_name or '').lower()
                for term in prebiotic_terms:
                    if term and (term in ing_norm or term in std_norm):
                        prebiotic_found = True
                        # Prefer the (non-empty) ingredient label over the
                        # bare term so the display field reads naturally.
                        prebiotic_name = std_name or ing_name or term
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

        # Two-pass survivability check: canonical chemistry forms come
        # from the shared form vocab (single source of truth); branded
        # markers stay local because they're product-specific copy, not
        # canonical chemistry.
        if _form_vocab.matches_probiotic_delivery(combined_text):
            has_survivability_coating = True
            survivability_reason = "canonical_delivery_form"
        else:
            for keyword in self.SURVIVABILITY_BRAND_MARKERS:
                if keyword in combined_text:
                    has_survivability_coating = True
                    survivability_reason = keyword
                    break

        # Calculate aggregate CFU data from blends
        total_cfu = 0
        has_cfu = False
        guarantee_type = None
        total_billion_count = 0.0
        cfu_source = None
        cfu_raw_source_path = None
        cfu_evidence_scope = None
        cfu_linked_rows: List[str] = []

        header_blends = {
            str(blend.get("raw_source_path") or ""): blend
            for blend in probiotic_blends
            if blend.get("is_blend_header_total")
        }
        child_blends_by_parent: Dict[str, List[Dict]] = {}
        for blend in probiotic_blends:
            parent = _parent_path(str(blend.get("raw_source_path") or ""))
            if parent and parent in header_blends:
                child_blends_by_parent.setdefault(parent, []).append(blend)

        def _add_cfu_source(cfu_data: Dict, blend: Dict) -> None:
            nonlocal has_cfu, guarantee_type, cfu_source, cfu_raw_source_path, cfu_evidence_scope
            if cfu_data.get('has_cfu'):
                has_cfu = True
                if not cfu_source:
                    cfu_source = cfu_data.get("source")
                if not cfu_raw_source_path:
                    cfu_raw_source_path = cfu_data.get("raw_source_path") or blend.get("raw_source_path")
                if not cfu_evidence_scope:
                    cfu_evidence_scope = cfu_data.get("evidence_scope") or "row_level"
                linked = cfu_data.get("linked_rows") or [blend.get("raw_source_path")]
                cfu_linked_rows.extend(str(path) for path in linked if path)
            if not guarantee_type and cfu_data.get('guarantee_type'):
                guarantee_type = cfu_data.get('guarantee_type')

        handled_child_paths = set()
        for header_path, header in header_blends.items():
            header_cfu = header.get('cfu_data', {}) or {}
            _add_cfu_source(header_cfu, header)
            header_count = header_cfu.get('cfu_count', 0) if header_cfu.get('has_cfu') else 0
            header_billion = header_cfu.get('billion_count', 0) if header_cfu.get('has_cfu') else 0

            child_count = 0
            child_billion = 0.0
            for child in child_blends_by_parent.get(header_path, []):
                handled_child_paths.add(child.get("raw_source_path"))
                child_cfu = child.get('cfu_data', {}) or {}
                _add_cfu_source(child_cfu, child)
                if child_cfu.get('has_cfu'):
                    child_count += child_cfu.get('cfu_count', 0)
                    child_billion += child_cfu.get('billion_count', 0)

            group_count = max(header_count or 0, child_count or 0)
            group_billion = max(header_billion or 0, child_billion or 0)
            total_cfu += group_count
            total_billion_count += group_billion

        for blend in probiotic_blends:
            if blend.get("is_blend_header_total") or blend.get("raw_source_path") in handled_child_paths:
                continue
            cfu_data = blend.get('cfu_data', {})
            if cfu_data.get('has_cfu'):
                total_cfu += cfu_data.get('cfu_count', 0)
                total_billion_count += cfu_data.get('billion_count', 0)
            _add_cfu_source(cfu_data, blend)

        # Use product-level CFU if it's a total claim and exceeds per-strain sum
        # (prevents overcounting when "50 Billion CFU" is a product total, not per-strain)
        if product_level_cfu.get('has_cfu'):
            product_billion = product_level_cfu.get('billion_count', 0)
            if product_billion > total_billion_count and total_billion_count > 0:
                total_cfu = product_level_cfu['cfu_count']
                total_billion_count = product_billion
                cfu_source = product_level_cfu.get("source")
                cfu_raw_source_path = product_level_cfu.get("raw_source_path")
                cfu_evidence_scope = product_level_cfu.get("evidence_scope")
                cfu_linked_rows = list(product_level_cfu.get("linked_rows") or [])
            elif not has_cfu:
                has_cfu = True
                total_cfu = product_level_cfu['cfu_count']
                total_billion_count = product_billion
                guarantee_type = product_level_cfu.get('guarantee_type') or guarantee_type
                cfu_source = product_level_cfu.get("source")
                cfu_raw_source_path = product_level_cfu.get("raw_source_path")
                cfu_evidence_scope = product_level_cfu.get("evidence_scope")
                cfu_linked_rows = list(product_level_cfu.get("linked_rows") or [])

        self.logger.debug(
            "Returning probiotic_data with has_cfu=%s, first_blend_cfu_data=%s",
            has_cfu,
            probiotic_blends[0]['cfu_data'] if probiotic_blends else None,
        )

        # Sprint 2026-05-01: product-level postbiotic detection.
        # Patterns sourced from form_keywords_vocab.json
        # (postbiotic_keywords category). Independent of clinical_strains
        # matching — scans every probiotic_blend's name + strains so
        # products carrying postbiotic content surface a flag for Flutter
        # even when the strain isn't in the clinical_strains DB.
        # extract_forms() returns the canonical names that matched, so
        # detected_postbiotic_patterns reports canonical tokens
        # (heat-killed / inactivated / lysate / postbiotic) instead of
        # the raw label strings — single canonical per concept.
        has_postbiotic_strains = False
        detected_postbiotic_patterns: List[str] = []
        for _b in probiotic_blends:
            if not isinstance(_b, dict):
                continue
            haystack_parts = [str(_b.get("name") or ""), str(_b.get("blend_name") or "")]
            haystack_parts.extend(str(s) for s in (_b.get("strains") or []))
            haystack = " ".join(haystack_parts)
            for canonical in _form_vocab.extract_forms(haystack, categories=["postbiotic_keywords"]):
                if canonical not in detected_postbiotic_patterns:
                    detected_postbiotic_patterns.append(canonical)
                    has_postbiotic_strains = True

        # Secondary scan: activeIngredients carries postbiotic qualifier in
        # structured fields when the cleaner stripped it from the surface
        # name. Sources scanned (in order):
        #   1. activeIngredients[].name / standardName (surface label)
        #   2. activeIngredients[].forms[].prefix (DSLD form qualifier,
        #      e.g. "heat-killed")
        #   3. ingredient_quality_data.ingredients[].matched_form (IQM
        #      form key — already encodes "(heat-killed/postbiotic)" for
        #      L. plantarum L-137 etc.)
        # Scoped to structured fields only; we don't scan loose marketing
        # copy (e.g., "postbiotic benefits" claims).
        for _ai in (product.get("activeIngredients") or []):
            if not isinstance(_ai, dict):
                continue
            _ai_name = str(_ai.get("name") or _ai.get("standardName") or "").lower()
            for _f in (_ai.get("forms") or []):
                if isinstance(_f, dict):
                    _ai_name += " " + str(_f.get("prefix") or "").lower()
                    _ai_name += " " + str(_f.get("form_key") or "").lower()
            if not _ai_name.strip():
                continue
            for canonical in _form_vocab.extract_forms(_ai_name, categories=["postbiotic_keywords"]):
                if canonical not in detected_postbiotic_patterns:
                    detected_postbiotic_patterns.append(canonical)
                    has_postbiotic_strains = True

        for _iq in ((product.get("ingredient_quality_data") or {}).get("ingredients") or []):
            if not isinstance(_iq, dict):
                continue
            _matched = str(_iq.get("matched_form") or _iq.get("form_id") or "").lower()
            if not _matched:
                continue
            for canonical in _form_vocab.extract_forms(_matched, categories=["postbiotic_keywords"]):
                if canonical not in detected_postbiotic_patterns:
                    detected_postbiotic_patterns.append(canonical)
                    has_postbiotic_strains = True

        postbiotic_metabolite_present = False
        postbiotic_metabolite_name = ""
        for _ai in (product.get("activeIngredients") or []):
            if not isinstance(_ai, dict):
                continue
            _meta_text = " ".join(
                str(value or "")
                for value in (
                    _ai.get("canonical_id"),
                    _ai.get("name"),
                    _ai.get("standardName"),
                    _ai.get("ingredientGroup"),
                    _ai.get("notes"),
                )
            ).lower()
            if any(term in _meta_text for term in ("butyric_acid", "tributyrin", "butyrate", "postbiotic")):
                postbiotic_metabolite_present = True
                postbiotic_metabolite_name = _ai.get("standardName") or _ai.get("name") or "postbiotic metabolite"
                break

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
            "cfu_source": cfu_source,
            "cfu_raw_source_path": cfu_raw_source_path,
            "cfu_evidence_scope": cfu_evidence_scope,
            "cfu_linked_rows": sorted(set(cfu_linked_rows)),
            # Clinical and other data
            "clinical_strains": found_clinical_strains,
            "clinical_strain_count": len(found_clinical_strains),
            "prebiotic_present": prebiotic_found,
            "prebiotic_name": prebiotic_name,
            "has_survivability_coating": has_survivability_coating,
            "survivability_reason": survivability_reason,
            # Product-level postbiotic indicator (Sprint 2026-05-01).
            # True when ANY probiotic_blend name/strain text contains a
            # postbiotic pattern. Independent of clinical_strain matching;
            # CFU credit still gated by per-strain is_inactivated flag in
            # clinical_strains[].
            "has_postbiotic_strains": has_postbiotic_strains,
            "detected_postbiotic_patterns": detected_postbiotic_patterns,
            "postbiotic_metabolite_present": postbiotic_metabolite_present,
            "postbiotic_metabolite_name": postbiotic_metabolite_name,
        }

    def _collect_product_scoring_evidence(self, enriched: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Emit enrichment-owned product-level scoring evidence."""
        evidence: List[Dict[str, Any]] = [
            item for item in derive_product_scoring_evidence(enriched)
            if item.get("evidence_type") != "probiotic_cfu"
        ]
        probiotic_data = enriched.get("probiotic_data") if isinstance(enriched.get("probiotic_data"), dict) else {}
        try:
            total_cfu_value = float(probiotic_data.get("total_cfu") or 0)
        except (TypeError, ValueError):
            total_cfu_value = 0.0
        if total_cfu_value <= 0:
            return evidence

        taxonomy = enriched.get("supplement_taxonomy") if isinstance(enriched.get("supplement_taxonomy"), dict) else {}
        primary_type = str(taxonomy.get("primary_type") or "").strip().lower()
        raw_source_path = probiotic_data.get("cfu_raw_source_path")
        linked_rows = [str(path) for path in (probiotic_data.get("cfu_linked_rows") or []) if path]
        if raw_source_path and raw_source_path not in linked_rows:
            linked_rows.append(str(raw_source_path))
        iqd = enriched.get("ingredient_quality_data") if isinstance(enriched.get("ingredient_quality_data"), dict) else {}
        strict_rows = [row for row in (iqd.get("ingredients_scorable") or []) if isinstance(row, dict)]
        probiotic_blends = [row for row in (probiotic_data.get("probiotic_blends") or []) if isinstance(row, dict)]
        has_probiotic_row_identity = bool(probiotic_blends) and int(probiotic_data.get("total_strain_count") or 0) > 0
        has_non_probiotic_strict_active = self._has_non_probiotic_active_for_cfu_evidence(enriched)
        for row in strict_rows:
            row_text = " ".join(str(row.get(key) or "") for key in ("canonical_id", "name", "standard_name")).lower()
            if any(term in row_text for term in ("probiotic", "lactobacillus", "bifidobacterium", "saccharomyces", "bacillus")):
                continue
            if self._is_probiotic_cfu_support_row(row):
                continue
            if str(row.get("dose_class") or "").lower() == "probiotic_cfu":
                continue
            has_non_probiotic_strict_active = True
            break
        # Wave 6.Z gate (2026-05-29): supplement_taxonomy.primary_type drives
        # scoreable product-level CFU evidence with a narrow "taxonomy lagging"
        # carve-out so genuinely probiotic products whose taxonomy hasn't been
        # classified yet (primary_type empty or "general_supplement") can still
        # earn credit via probiotic row identity. Any OTHER concrete primary_type
        # (fiber_digestive, mineral, omega_3, ...) actively classifies the
        # product as non-probiotic and disqualifies CFU regardless of row
        # identity — only blended/unknown taxonomies get the row-identity bridge.
        # See test_probiotic_cfu_provenance_2026_05_26 and
        # test_enrichment_regressions::TestProbioticDataStructureRegressionLock.
        TAXONOMY_LAGGING_VALUES = {"", "general_supplement"}
        taxonomy_is_probiotic = primary_type == "probiotic"
        taxonomy_is_lagging = (not primary_type) or primary_type in TAXONOMY_LAGGING_VALUES
        identity_proven = (
            (taxonomy_is_probiotic or (taxonomy_is_lagging and has_probiotic_row_identity))
            and bool(probiotic_data.get("is_probiotic_product"))
            and has_probiotic_row_identity
            and not has_non_probiotic_strict_active
        )
        if taxonomy_is_probiotic:
            accepted_reason = "product_level_cfu_with_probiotic_identity"
        elif taxonomy_is_lagging and has_probiotic_row_identity:
            accepted_reason = "product_level_cfu_with_probiotic_row_identity"
        else:
            accepted_reason = "product_level_cfu_rejected_by_taxonomy"

        base = {
            "evidence_type": "probiotic_cfu",
            "scoreable_identity": identity_proven,
            "score_eligible_by_cleaner": bool(probiotic_data.get("is_probiotic_product")),
            "dose_class": "probiotic_cfu",
            "dose_value": total_cfu_value,
            "dose_unit": "CFU",
            "source": probiotic_data.get("cfu_source") or "probiotic_data.total_cfu",
            "raw_source_path": raw_source_path,
            "evidence_scope": probiotic_data.get("cfu_evidence_scope") or "product_level",
            "linked_rows": linked_rows,
            "confidence": "high" if identity_proven and raw_source_path and linked_rows else "low",
            "reason": accepted_reason,
            "name": "Total Probiotic CFU",
            "canonical_id": "probiotic_cfu_total",
            "clean_identity_id": None,
            "scoring_parent_id": "probiotic_cfu_total",
            "evidence_canonical_id": "probiotic_cfu_total",
            "canonical_source_db": "probiotic_data",
            "evidence_origin": "native_enrichment",
            "source_section": "product",
        }

        rejection_reason = None
        if has_non_probiotic_strict_active:
            # Strict-active check takes precedence: a non-probiotic active
            # ingredient (e.g. zinc, CBD, Vitamin C, fiber-primary product)
            # makes CFU evidence accessory regardless of taxonomy or row signals.
            rejection_reason = "non_probiotic_strict_active_present"
        elif not taxonomy_is_probiotic and not taxonomy_is_lagging:
            # Taxonomy actively classifies as non-probiotic (e.g. fiber_digestive,
            # mineral, omega_3). Row identity does NOT bridge a CONCRETE
            # non-probiotic taxonomy — only blanks / general_supplement.
            rejection_reason = "product_taxonomy_not_probiotic"
        elif not identity_proven or not probiotic_data.get("is_probiotic_product"):
            rejection_reason = "product_identity_not_probiotic"
        elif not raw_source_path:
            rejection_reason = "missing_raw_source_path"
        elif not linked_rows:
            rejection_reason = "missing_linked_rows"

        if rejection_reason:
            base.update({
                "scoreable": False,
                "scoreable_identity": False,
                "score_eligible_by_cleaner": False,
                "confidence": "low",
                "reason": "probiotic_cfu_rejected_by_identity_or_provenance_gate",
                "rejection_reason": rejection_reason,
            })
        else:
            base.update({
                "scoreable": True,
                "scoreable_identity": True,
                "score_eligible_by_cleaner": True,
            })
        evidence.append(base)
        return evidence

    def _collect_product_scoring_classification(self, enriched: Dict[str, Any]) -> Dict[str, Any]:
        """Emit native ScoringClassification v1 using the shared builder."""
        try:
            return build_scoring_classification(
                enriched,
                classification_origin="native_enrichment",
            )
        except Exception as exc:  # pragma: no cover - builder is total; belt/suspenders
            self.logger.warning("Scoring classification emit failed: %s", exc)
            return build_scoring_classification(
                {},
                classification_origin="native_enrichment",
            )

    def apply_taxonomy_projection(self, enriched: Dict[str, Any]) -> Dict[str, Any]:
        """Classify with the canonical taxonomy and emit everything derived from it.

        Single owner of the taxonomy -> derived-field projection. `enrich_product`
        calls this, and so does the temporary consolidation drift harness, so a
        preview can never diverge from what the pipeline would actually write.
        Mutates and returns `enriched`.

        PRECONDITION (ordering invariant, do not reorder): `ingredient_quality_data`
        and `probiotic_data` must already be populated. `classify_supplement`
        consumes `probiotic_data` (is_probiotic_product / total_cfu /
        total_strain_count) for its NP-exemption gate on probiotic strains, and
        `_collect_product_scoring_evidence` in turn reads the taxonomy's
        primary_type to decide whether product-level CFU evidence is scoreable.
        """
        taxonomy = classify_supplement(enriched)
        enriched["supplement_taxonomy"] = taxonomy
        enriched["primary_type"] = taxonomy["primary_type"]
        enriched["secondary_type"] = taxonomy["secondary_type"]
        # Compatibility surface only.  This is a projection of the taxonomy,
        # never an independently computed type.  It remains in enriched blobs
        # until downstream old-artifact adapters are retired, and the final DB
        # keeps its scalar ``supplement_type`` column for Flutter/dashboard.
        raw_active_count = taxonomy.get("quantified_active_row_count", 0)
        inactive_rows = enriched.get("inactiveIngredients")
        inactive_count = len(inactive_rows) if isinstance(inactive_rows, list) else 0
        enriched["supplement_type"] = {
            "type": taxonomy["primary_type"],
            "active_count": taxonomy.get("quantified_label_active_count", 0),
            "raw_active_count": raw_active_count,
            "total_count": raw_active_count + inactive_count,
            "category_breakdown": dict(taxonomy.get("category_breakdown") or {}),
            "source": "supplement_taxonomy",
            "confidence": taxonomy.get("classification_confidence"),
            "classification_reason_codes": list(
                taxonomy.get("classification_reason_codes") or []
            ),
        }
        enriched["product_scoring_evidence"] = self._collect_product_scoring_evidence(enriched)
        enriched["product_scoring_classification"] = self._collect_product_scoring_classification(enriched)
        return enriched

    @staticmethod
    def _has_probiotic_identity_text(row: Dict[str, Any]) -> bool:
        text = " ".join(
            str(row.get(key) or "")
            for key in ("name", "standardName", "standard_name", "canonical_id", "raw_source_text", "category")
        )
        return bool(_PROBIOTIC_IDENTITY_RE.search(text))

    @staticmethod
    def _is_probiotic_cfu_support_row(row: Dict[str, Any]) -> bool:
        """Rows like dietary fiber/prebiotics support probiotic formulas; they do not make CFU accessory."""
        cid = str(row.get("canonical_id") or "").strip().lower()
        if cid in {"fiber", "prebiotics"}:
            return True
        text = " ".join(
            str(row.get(key) or "").lower()
            for key in ("name", "standardName", "standard_name", "raw_source_text", "category")
        )
        return any(term in text for term in ("dietary fiber", "prebiotic", "inulin", "fructooligosaccharide"))

    @staticmethod
    def _is_fiber_primary_with_accessory_probiotics(product: Dict[str, Any]) -> bool:
        """Detect fiber-primary labels where probiotics are secondary/add-on."""
        product_name = " ".join(
            str(product.get(key) or "").lower()
            for key in ("product_name", "fullName", "bundleName")
        )
        has_fiber_primary_signal = any(
            term in product_name
            for term in ("super fiber", "fiber formula", "fiber supplement", "clear mixing fiber")
        )
        return has_fiber_primary_signal and any(
            term in product_name for term in ("with probiotic", "with probiotics")
        )

    def _has_non_probiotic_active_for_cfu_evidence(self, product: Dict[str, Any]) -> bool:
        """Detect cleaner-eligible non-probiotic actives that make CFU evidence accessory."""
        fiber_primary_with_accessory_probiotics = self._is_fiber_primary_with_accessory_probiotics(product)
        for row in product.get("activeIngredients") or []:
            if not isinstance(row, dict):
                continue
            if row.get("score_eligible_by_cleaner") is not True:
                continue
            cleaner_role = str(row.get("cleaner_row_role") or "").strip()
            if cleaner_role and cleaner_role != "active_scorable":
                continue
            if self._has_probiotic_identity_text(row):
                continue
            if self._is_probiotic_cfu_support_row(row):
                cid = str(row.get("canonical_id") or "").strip().lower()
                if not (cid == "fiber" and fiber_primary_with_accessory_probiotics):
                    continue
            cid = str(row.get("canonical_id") or "").strip()
            unit = self._normalize_unit_for_signal(row.get("unit"))
            try:
                has_positive_dose = float(str(row.get("quantity")).replace(",", "")) > 0 and unit not in PSEUDO_UNITS_INVALID
            except (TypeError, ValueError):
                has_positive_dose = False
            if cid or has_positive_dose:
                return True
        return False

    # CFU-equivalent unit patterns — must match the ENTIRE unit string
    # (re.fullmatch). Earlier version used re.search with generic patterns
    # like \bprobiotic, \bbacteria, \borganism and \bcell(s)?, which caused
    # label strings such as "probiotic blend", "bacteria count", or
    # "organism-based" to be misread as CFU measurement units. Patterns here
    # are tight: they only describe actual measurement units used on
    # supplement labels. \s* allows both spaced ("live cell(s)") and compact
    # ("livecell(s)") forms.
    CFU_EQUIVALENT_PATTERNS = [
        r'viable\s*cell(?:s)?(?:\([^)]*\))?',
        r'live\s*cell(?:s)?(?:\([^)]*\))?',
        r'active\s*cell(?:s)?(?:\([^)]*\))?',
        r'cfu(?:s)?(?:\([^)]*\))?',
        r'colony\s*forming\s*unit(?:s)?(?:\([^)]*\))?',
        # Round 2 fix (2026-04-30): "Organism(s)" is the DSLD-standard unit
        # for probiotic CFU on many products (e.g., GNC Probiotic Complex
        # 1 declares 1,000,000,000 Organism(s) = 1 billion CFU). Without
        # this pattern, 22+ probiotic products lost their CFU bonus.
        r'organism(?:s)?(?:\([^)]*\))?',
    ]

    def _is_cfu_equivalent_unit(self, unit: str) -> bool:
        """
        Check if a unit string represents CFU-equivalent measurement using
        anchored regex patterns. Full-string match only — descriptive
        labels that merely contain CFU-related words (e.g. "probiotic blend")
        must NOT match.
        """
        if not unit:
            return False

        unit_lower = unit.lower().strip()

        import re
        for pattern in self.CFU_EQUIVALENT_PATTERNS:
            if re.fullmatch(pattern, unit_lower, re.IGNORECASE):
                return True

        return False

    def _parse_cfu_text_count(self, text: str) -> Optional[float]:
        """Return the first label-declared CFU count from supported notation."""
        candidates: List[Tuple[int, float]] = []
        for pattern_key, multiplier in (
            ("cfu_billion", 1e9),
            ("cfu_billion_abbrev", 1e9),
            ("cfu_million", 1e6),
        ):
            match = self.compiled_patterns[pattern_key].search(text)
            if match:
                candidates.append((match.start(), float(match.group(1)) * multiplier))

        scientific = self.compiled_patterns["cfu_scientific"].search(text)
        if scientific:
            raw_exponent = scientific.group("ascii_exponent") or scientific.group("e_exponent")
            if raw_exponent is None:
                superscript_digits = "⁰¹²³⁴⁵⁶⁷⁸⁹"
                raw_exponent = scientific.group("superscript_exponent").translate(
                    str.maketrans(superscript_digits, "0123456789")
                )
            exponent = int(raw_exponent)
            # CFU labels are whole-cell counts. Reject negative exponents and
            # absurd magnitudes before exponentiation so malformed OCR cannot
            # crash enrichment or fabricate an infinite dose.
            if 0 <= exponent <= 18:
                count = float(scientific.group("coefficient")) * (10 ** exponent)
                if math.isfinite(count):
                    candidates.append((scientific.start(), count))

        if not candidates:
            return None
        return min(candidates, key=lambda item: item[0])[1]

    def _extract_cfu(
        self,
        text: str,
        ingredient: Optional[Dict] = None,
        source_path: Optional[str] = None,
        evidence_scope: Optional[str] = None,
    ) -> Dict:
        """
        Extract CFU information from text and ingredient quantity.

        P1.1: Recognizes "Viable Cell(s)" as CFU-equivalent unit.
        """
        result = {
            "has_cfu": False,
            "cfu_count": 0,
            "billion_count": 0,
            "guarantee_type": None,  # 'at_manufacture' or 'at_expiration'
            "source": None,
            "raw_source_path": None,
            "evidence_scope": evidence_scope,
            "linked_rows": [],
        }

        def _mark_source(source: str, raw_source_path: Optional[str], scope: Optional[str]) -> None:
            result["source"] = source
            result["raw_source_path"] = raw_source_path
            result["evidence_scope"] = scope or result.get("evidence_scope")
            if raw_source_path:
                result["linked_rows"] = [raw_source_path]

        self.logger.debug("Extracting CFU data from text; ingredient_present=%s", bool(ingredient))
        if ingredient:
            quantity = ingredient.get('quantity', 0)
            unit = (ingredient.get('unit', '') or '')

            if unit and self._is_cfu_equivalent_unit(unit):
                if quantity and quantity > 0:
                    result["has_cfu"] = True
                    result["cfu_count"] = quantity
                    result["billion_count"] = quantity / 1e9
                    _mark_source("activeIngredients.quantity_unit", source_path or ingredient.get("raw_source_path"), evidence_scope or "row_level")

        self.logger.debug("CFU extraction result: %s", result)

        # Also check row-local text for CFU mentions through one parser.
        if text:
            count_from_text = self._parse_cfu_text_count(text)
            if count_from_text is not None and (
                not result["has_cfu"] or count_from_text > result["cfu_count"]
            ):
                result["has_cfu"] = True
                result["cfu_count"] = count_from_text
                result["billion_count"] = count_from_text / 1e9
                _mark_source(
                    "activeIngredients.notes" if ingredient else "statements",
                    source_path or (ingredient or {}).get("raw_source_path"),
                    evidence_scope or ("row_level" if ingredient else "product_level"),
                )

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
    def _decorate_percentile_category(self, enriched: Dict[str, Any]) -> Dict[str, Any]:
        """Project the canonical taxonomy's percentile cohort onto the artifact.

        NOT a decider. `classify_supplement` owns product class; this only
        restates its `percentile_category` plus the compatibility fields older
        consumers read. Every value here is derived from the taxonomy — never
        from a product name, ingredient list, or form factor.

        This replaced an independent inference engine that scored name tokens
        and ingredients against data/percentile_categories.json. That config
        knows 9 categories while the taxonomy map has 20, so everything it could
        not express (herbal_botanical, amino_acid, single_vitamin, ...) fell back
        to `general_supplement`: the two disagreed on 7,975/14,193 products
        (56.2%). Neither the export (build_final_db.py) nor the scorer
        (score_supplements._resolve_percentile_category, "SP-2.8: taxonomy is the
        source of truth") ever trusted it, so retiring it aligns the artifact
        with what already ships rather than moving the shipped cohort.

        PRECONDITION: run AFTER apply_taxonomy_projection (plan §5).
        """
        taxonomy = enriched.get("supplement_taxonomy")
        taxonomy = taxonomy if isinstance(taxonomy, dict) else {}
        category = str(taxonomy.get("percentile_category") or "").strip()

        if not category:
            # Truthful zero rather than an invented cohort (plan TRAP 3).
            return {
                "percentile_category": None,
                "percentile_category_label": None,
                "percentile_category_source": "taxonomy_unavailable",
                "percentile_category_confidence": 0.0,
                "percentile_category_signals": ["no_taxonomy_percentile_category"],
            }

        reasons = taxonomy.get("classification_reasons")
        return {
            "percentile_category": category,
            "percentile_category_label": percentile_label_for(category),
            "percentile_category_source": "taxonomy_v2",
            "percentile_category_confidence": taxonomy.get("classification_confidence"),
            "percentile_category_signals": (
                [str(item) for item in reasons if item is not None]
                if isinstance(reasons, list) else []
            ),
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

    def _collect_nutrition_summary(self, product: Dict) -> Dict:
        """
        Extract the five macro-nutrient values from nutritionalInfo for
        transparency surfacing.  Calories are in kcal; carbs/fat/protein/fiber
        are in grams.  Units are passed through verbatim — the cleaner already
        normalises them.  Missing or zero-amount fields are emitted as None so
        the Flutter side can distinguish "not declared" from "zero".

        This is ADDITIVE — it does not replace dietary_sensitivity_data
        (sugar/sodium).  Scoring does not consume this field.
        """
        ni = product.get("nutritionalInfo") or {}

        def _amount(key: str):
            entry = ni.get(key)
            if not isinstance(entry, dict):
                return None
            val = entry.get("amount")
            if val is None:
                return None
            try:
                fval = float(val)
            except (TypeError, ValueError):
                return None
            return fval if fval != 0.0 else None

        return {
            "calories_per_serving": _amount("calories"),
            "total_carbohydrates_g": _amount("totalCarbohydrates"),
            "total_fat_g": _amount("totalFat"),
            "protein_g": _amount("protein"),
            "dietary_fiber_g": _amount("dietaryFiber"),
            "total_sugars_g": _amount("sugars"),
        }

    def _normalize_serving_unit_label(self, unit: Any) -> str:
        """Canonicalize dose-form unit labels used in serving-size math."""
        raw = str(unit or '').lower().strip()
        raw = raw.replace('(ies)', '')
        raw = raw.replace('(s)', '')
        raw = raw.replace('(es)', '')
        raw = re.sub(r'\([^)]*$', '', raw).strip()
        mapped = SERVING_UNIT_NORMALIZATION_MAP.get(raw)
        if mapped:
            return mapped
        for token in (
            'capsule', 'tablet', 'gummy', 'softgel', 'lozenge',
            'scoop', 'drop', 'packet', 'stick', 'spray', 'teaspoon',
        ):
            if token in raw:
                return token
        return raw

    def _derive_serving_size_from_container(self, product: Dict, basis_unit: Any) -> Optional[float]:
        """Use net contents / servings per container when DSLD split the dose row.

        Example: 30 capsules and 10 servings means the Supplement Facts serving
        is 3 capsules, even if servingSizes[] exposes a one-capsule row.
        """
        try:
            servings_per_container = float(
                product.get('servingsPerContainer') or product.get('servings_per_container')
            )
        except (TypeError, ValueError):
            return None
        if servings_per_container <= 0:
            return None

        canonical_basis_unit = self._normalize_serving_unit_label(basis_unit)
        net_contents = product.get('netContents') or product.get('net_contents') or []
        if isinstance(net_contents, dict):
            net_contents = [net_contents]
        if not isinstance(net_contents, list):
            return None

        for item in net_contents:
            if not isinstance(item, dict):
                continue
            try:
                quantity = float(item.get('quantity'))
            except (TypeError, ValueError):
                continue
            if quantity <= 0:
                continue
            net_unit = self._normalize_serving_unit_label(
                item.get('unit') or item.get('display') or item.get('name')
            )
            if canonical_basis_unit and net_unit and canonical_basis_unit != net_unit:
                continue
            derived = quantity / servings_per_container
            if 0 < derived <= 24:
                return derived
        return None

    def _serving_units_to_servings(self, units: Any, basis_count: Any) -> Optional[float]:
        try:
            unit_count = float(units)
            serving_size = float(basis_count)
        except (TypeError, ValueError):
            return None
        if unit_count <= 0 or serving_size <= 0:
            return None
        return unit_count / serving_size

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
        basis_reason = "default"

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
                    basis_unit = self._normalize_serving_unit_label(basis_unit)

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

                derived_basis_count = self._derive_serving_size_from_container(product, basis_unit)
                try:
                    current_basis_count = float(basis_count) if basis_count is not None else None
                except (TypeError, ValueError):
                    current_basis_count = None
                if (
                    derived_basis_count is not None
                    and (
                        current_basis_count is None
                        or derived_basis_count > current_basis_count
                    )
                ):
                    basis_count = derived_basis_count
                    canonical_serving_size_qty = derived_basis_count
                    basis_reason = "net_contents_servings_per_container"
                    if min_servings_per_day is not None:
                        min_servings_per_day = self._serving_units_to_servings(
                            min_servings_per_day, basis_count
                        )
                    if max_servings_per_day is not None:
                        max_servings_per_day = self._serving_units_to_servings(
                            max_servings_per_day, basis_count
                        )

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
                min_servings_per_day = self._serving_units_to_servings(
                    min_recommended, basis_count
                )
                max_servings_per_day = self._serving_units_to_servings(
                    max_recommended, basis_count
                )
                servings_per_day_source = "directions"

        # Determine selection policy
        selection_policy = "first_serving"
        selected_from = "servingSizes"

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
                    if basis_reason == "default":
                        basis_reason = "adult_default_from_userGroups"
                    break

        # SP-3 (2026-05-21): canonical form_factor for downstream consumers.
        # Reads the DSLD langual code as the most authoritative signal, then
        # the description text. This is the single normalization stage —
        # v4 / score / final_db / Flutter should consume `form_factor_canonical`,
        # not re-derive from raw `physicalState`. The legacy `form_factor`
        # field is kept additive so pre-2026-05-21 consumers still work.
        form_factor_canonical = canonicalize_form_factor(
            langual_desc,
            langual_code=physical_state.get('langualCode') if isinstance(physical_state, dict) else None,
        )

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
            "form_factor": form_factor,
            "form_factor_canonical": form_factor_canonical,
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
            numeric_qty = self._to_float_safe(qty)
            if numeric_qty is not None and numeric_qty > max_qty:
                max_qty = numeric_qty
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

        # Precaution ceilings are safety instructions, not recommended intake.
        # Remove only the affected clause so an independent positive direction
        # in the same label remains available ("Take 2... Do not exceed 6").
        clauses = re.split(r"(?<=[.!?;,])\s+|[\r\n]+", text_lower)
        precaution = re.compile(
            r"\b(?:(?:do|should|must)\s+not\s+exceed|not\s+to\s+exceed)\b"
        )
        text_lower = " ".join(
            clause for clause in clauses if clause.strip() and not precaution.search(clause)
        )
        if not text_lower:
            return None

        # First convert word numbers to digits for easier parsing
        for word, num in self.WORD_TO_NUM.items():
            text_lower = re.sub(rf'\b{word}\b', str(num), text_lower)

        frequency = 1
        frequency_patterns = [
            (r'\btwice\s+(?:daily|a day|per day)\b', 2),
            (r'\bonce\s+(?:daily|a day|per day)\b', 1),
            (r'\b(\d+)\s+times\s+(?:daily|a day|per day)\b', None),
        ]
        for pattern, fixed in frequency_patterns:
            match = re.search(pattern, text_lower)
            if match:
                frequency = fixed if fixed is not None else int(match.group(1))
                break

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
                    return {"min": child_dose * frequency, "max": adult_dose * frequency}
                return {"min": adult_dose * frequency, "max": adult_dose * frequency}

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
                    return {"min": int(groups[0]) * frequency, "max": int(groups[1]) * frequency}
                elif len(groups) >= 1:
                    return {"min": int(groups[0]) * frequency, "max": int(groups[0]) * frequency}

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

        # Normalize to grams via the single mass-conversion authority
        # (_normalize_threshold_unit → canonicalize_mass_unit → _convert_mass).
        # C7.2: substring unit detection ('mg' in unit) left spelled-out and
        # mcg units unconverted — "5 Milligram(s)" stayed 5 g → false High
        # Sugar. Unknown/empty units fall back to the panel default (g).
        amount_g = float(amount) if amount else 0.0
        converted = self._convert_mass(
            amount_g, self._normalize_threshold_unit(unit), "g"
        )
        if converted is not None:
            amount_g = converted

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

        # Normalize to mg via the single mass-conversion authority
        # (_normalize_threshold_unit → canonicalize_mass_unit → _convert_mass).
        # C7.2: substring unit detection ('g' in / 'mg' not in) mis-scaled
        # spelled-out and mcg units 1000x — "55 Milligram(s)" → 55,000 mg →
        # false High Sodium / hypertension. Unknown/empty units fall back to
        # the panel default (mg), leaving the value unchanged.
        amount_mg = float(amount) if amount else 0.0
        converted = self._convert_mass(
            amount_mg, self._normalize_threshold_unit(unit), "mg"
        )
        if converted is not None:
            amount_mg = converted

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
        raw = str(unit or "").strip()
        mass_unit = norm_module.canonicalize_mass_unit(raw)
        if mass_unit in {"mcg", "mg", "g"}:
            return mass_unit
        text = raw.lower().replace(" ", "").replace("_", "")
        alias_map = {
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

    def _evaluate_min_effective_dose(
        self,
        min_effective_dose: Optional[Dict[str, Any]],
        ingredient: Dict[str, Any],
        servings_per_day_max: float,
    ) -> Optional[str]:
        """Dose-floor status vs an authored ``min_effective_dose``.

        Returns ``"below"`` when the product's daily dose is under the clinical
        floor (interaction immaterial at this amount), ``"at_or_above"`` when it
        meets/exceeds it, ``"form_mismatch"`` when a confirmed form is outside a
        form-scoped rule, or ``None`` when no floor is authored, the dose/form is
        unknown, or the unit is not convertible. ``None`` is FAIL-OPEN — callers
        must treat it as "fires", never suppress on missing evidence (mirrors the
        dose-threshold contract and the app's ``_isFullyGated``).
        """
        if not isinstance(min_effective_dose, dict):
            return None
        # Form-gate (G1): a form-scoped floor may SUPPRESS only against a
        # LABEL-CONFIRMED form. Confirmed nonmatching forms are not affected by
        # that rule; unknown, missing, AND inferred/unspecified forms fail open
        # (fire). No form_scope = form-agnostic.
        #
        # F2 (2026-07-08): `matched_form` is populated even for a FALLBACK form
        # — a generic "Vitamin B3" label with no "(as ...)" resolves to a
        # '<parent>_unspecified' form_id and a fallback matched_form. Gating on
        # matched_form alone treated that inferred form as "confirmed" and
        # emitted form_mismatch, SUPPRESSING a genuine nicotinic-acid
        # flush/hepatotoxicity warning — a generic B3 could BE nicotinic acid,
        # so that is an under-warn. Require a confirmed form, mirroring the
        # matcher's own test (`form_id and 'unspecified' not in form_id`).
        form_scope = min_effective_dose.get("form_scope")
        if isinstance(form_scope, list) and form_scope:
            ingredient_form = str(ingredient.get("matched_form") or "").strip().lower()
            form_id = str(ingredient.get("form_id") or "").strip().lower()
            form_confirmed = bool(form_id) and "unspecified" not in form_id
            allowed = {str(f).strip().lower() for f in form_scope if str(f).strip()}
            if not ingredient_form or not form_confirmed:
                return None
            if ingredient_form not in allowed:
                return "form_mismatch"
        floor_value = self._to_float_safe(min_effective_dose.get("value"))
        floor_unit = self._normalize_threshold_unit(min_effective_dose.get("unit"))
        basis = str(min_effective_dose.get("basis") or "per_day").strip().lower()
        if basis not in ("per_day", "per_serving"):
            return None  # unknown basis (authoring typo) -> fail open, never suppress
        if floor_value is None or not floor_unit:
            return None
        quantity = self._to_float_safe(ingredient.get("quantity"))
        unit = self._normalize_threshold_unit(ingredient.get("unit"))
        if quantity is None or quantity <= 0 or not unit:
            return None
        amount_basis = quantity * (servings_per_day_max if basis == "per_day" else 1.0)
        ingredient_name = str(ingredient.get("raw_source_text") or ingredient.get("name") or "")
        standard_name = str(ingredient.get("standard_name") or "")
        converted_amount, _reason = self._convert_amount_to_target_unit(
            amount=amount_basis,
            from_unit=unit,
            target_unit=floor_unit,
            ingredient_name=ingredient_name,
            standard_name=standard_name,
        )
        if converted_amount is None:
            return None
        return "below" if converted_amount < floor_value else "at_or_above"

    @staticmethod
    def _floor_status_for_emission(
        dose_floor_status: Optional[str], severity: Optional[str]
    ) -> Optional[str]:
        """Defense-in-depth for the SUPPRESSING floor statuses.

        The app never dose-suppresses a hard severity (its
        ``doseSuppressionGuardsPass`` / ``Severity.isHard`` guardrail fires the
        warning regardless of ``dose_floor_status``). Mirror that at the source:
        never EMIT a suppressing status ("below" / "form_mismatch") for an
        ``avoid`` / ``contraindicated`` rule — fail open (None) instead. Today
        the app already fails safe, so this is behavior-neutral on-device; it
        exists so a future/second consumer of ``dose_floor_status`` that lacks
        the ``isHard`` guard cannot under-warn on a hard rule. "at_or_above"
        (which fires) and None pass through unchanged.
        """
        if dose_floor_status in ("below", "form_mismatch") and str(
            severity or ""
        ).strip().lower() in ("avoid", "contraindicated"):
            return None
        return dose_floor_status

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
        raw_ingredients = iqd.get("ingredients", [])
        raw_skipped = iqd.get("ingredients_skipped", [])
        scorable = iqd.get("ingredients_scorable")
        if not isinstance(raw_ingredients, list):
            raw_ingredients = []
        if not isinstance(raw_skipped, list):
            raw_skipped = []
        if isinstance(scorable, list):
            ingredients = [row for row in scorable if isinstance(row, dict)]
            skipped = []
        else:
            ingredients = [row for row in raw_ingredients if isinstance(row, dict)]
            skipped = [row for row in raw_skipped if isinstance(row, dict)]

        rows_to_clear = list(raw_ingredients) + list(raw_skipped) + list(ingredients)
        for ingredient in rows_to_clear:
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
                    min_effective_dose = cond_rule.get("min_effective_dose")
                    dose_floor_status = self._floor_status_for_emission(
                        self._evaluate_min_effective_dose(
                            min_effective_dose, ingredient, servings_per_day_max
                        ),
                        severity,
                    )
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
                        "alert_headline": cond_rule.get("alert_headline"),
                        "alert_body": cond_rule.get("alert_body"),
                        "informational_note": cond_rule.get("informational_note"),
                        "warning_type": cond_rule.get("warning_type"),
                        "direction": cond_rule.get("direction"),
                        "materiality": cond_rule.get("materiality"),
                        "min_effective_dose": min_effective_dose,
                        "dose_floor_status": dose_floor_status,
                        "profile_gate": cond_rule.get("profile_gate"),
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
                                "alert_headline": pregnancy_block.get("alert_headline"),
                                "alert_body": pregnancy_block.get("alert_body"),
                                "informational_note": pregnancy_block.get("informational_note"),
                                "warning_type": pregnancy_block.get("warning_type"),
                                "direction": pregnancy_block.get("direction"),
                                "materiality": pregnancy_block.get("materiality"),
                                "profile_gate": pregnancy_block.get("profile_gate"),
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
                    min_effective_dose = drug_rule.get("min_effective_dose")
                    dose_floor_status = self._floor_status_for_emission(
                        self._evaluate_min_effective_dose(
                            min_effective_dose, ingredient, servings_per_day_max
                        ),
                        severity,
                    )
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
                        "alert_headline": drug_rule.get("alert_headline"),
                        "alert_body": drug_rule.get("alert_body"),
                        "informational_note": drug_rule.get("informational_note"),
                        "warning_type": drug_rule.get("warning_type"),
                        "direction": drug_rule.get("direction"),
                        "materiality": drug_rule.get("materiality"),
                        "min_effective_dose": min_effective_dose,
                        "dose_floor_status": dose_floor_status,
                        "profile_gate": drug_rule.get("profile_gate"),
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
            **self._rda_reference_stamp,
            "ingredients_with_rda": [],
            "analyzed_ingredients": [],
            "count": 0,
            "adequacy_results": [],
            "conversion_evidence": [],
            "safety_flags": [],
            "ul_review_flags": [],
            "has_over_ul": False,
            "reference_profile": dict(_RDA_REFERENCE_PROFILE),
            "collection_enabled": False,
            "collection_reason": reason
        }

    def _rda_source_label_key(self, ingredient: Dict[str, Any]) -> str:
        """Return a stable key for one label-declared nutrient row."""
        supplied = ingredient.get("source_label_key")
        if isinstance(supplied, str) and supplied.strip():
            return supplied

        canonical = self._normalize_text(
            ingredient.get("canonical_id")
            or ingredient.get("standardName")
            or ingredient.get("name")
            or "unknown"
        )
        label_name = self._normalize_text(
            ingredient.get("raw_source_text") or ingredient.get("name") or "unknown"
        )
        try:
            quantity = float(ingredient.get("quantity") or 0)
        except (TypeError, ValueError):
            quantity = 0.0
        quantity_key = format(quantity, ".12g")
        unit = self._normalize_text(ingredient.get("unit") or "unknown")
        return f"label:{canonical}:{label_name}:{quantity_key}:{unit}"

    def _declared_folate_dfe_totals(
        self, active_ingredients: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Find explicit label Folate DFE totals before form conversion.

        A label such as ``Folate 667 mcg DFE (400 mcg L-5-MTHF)`` declares
        one dose. The MTHF amount is component context, not an additional
        folate source. This is deliberately narrow: it does not collapse
        separate declared folate forms or any other multi-form nutrient.
        """
        totals: List[Dict[str, Any]] = []
        for ingredient in active_ingredients:
            canonical = self._normalize_text(
                ingredient.get("canonical_id")
                or ingredient.get("standardName")
                or ingredient.get("name")
                or ""
            )
            label_name = self._normalize_text(ingredient.get("name") or "")
            unit = self._normalize_text(ingredient.get("unit") or "")
            try:
                quantity = float(ingredient.get("quantity") or 0)
            except (TypeError, ValueError):
                continue
            if (
                canonical in {"folate", "vitamin_b9_folate"}
                and label_name == "folate"
                and "dfe" in unit
                and quantity > 0
            ):
                totals.append(
                    {
                        "source_label_key": self._rda_source_label_key(ingredient),
                        "quantity": quantity,
                    }
                )
        return totals

    def _rda_dose_lineage(
        self,
        ingredient: Dict[str, Any],
        *,
        converted_amount: float,
        converted_unit: str,
        conversion_evidence: Dict[str, Any],
        declared_folate_totals: List[Dict[str, Any]],
    ) -> Dict[str, Optional[str]]:
        """Classify an emitted RDA/UL row as a total or label sub-component."""
        source_label_key = self._rda_source_label_key(ingredient)
        lineage: Dict[str, Optional[str]] = {
            "source_label_key": source_label_key,
            "dose_role": "declared_total",
            "parent_label_key": None,
        }
        if not declared_folate_totals:
            return lineage

        canonical = self._normalize_text(
            ingredient.get("canonical_id")
            or ingredient.get("standardName")
            or ingredient.get("name")
            or ""
        )
        label_name = self._normalize_text(ingredient.get("name") or "")
        original_unit = self._normalize_text(ingredient.get("unit") or "")
        converted_unit_key = self._normalize_text(converted_unit)
        factor = conversion_evidence.get("conversion_factor")
        try:
            factor_value = float(factor)
        except (TypeError, ValueError):
            factor_value = 0.0

        # Require an actual form-derived conversion rather than another DFE
        # line. The named MTHF guard prevents unrelated folate forms from
        # being discarded merely because their converted doses are similar.
        if (
            canonical not in {"folate", "vitamin_b9_folate"}
            or label_name == "folate"
            or "dfe" in original_unit
            or "dfe" not in converted_unit_key
            or factor_value <= 1.0
            or not ("mthf" in label_name or "methylfolate" in label_name)
        ):
            return lineage

        for declared in declared_folate_totals:
            declared_amount = float(declared["quantity"])
            tolerance = max(0.5, declared_amount * 0.025)
            if abs(converted_amount - declared_amount) <= tolerance:
                lineage["dose_role"] = "form_component"
                lineage["parent_label_key"] = declared["source_label_key"]
                return lineage
        return lineage

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
        active_ingredients = self._primary_active_ingredients_for_enrichment(product)
        # Dual-declaration dedupe: the compound-weight restatement of a bare
        # elemental row must not contribute to UL totals (60+400=460 mg
        # would falsely breach the 350 mg magnesium UL).
        mark_compound_duplicate_rows(active_ingredients)
        declared_folate_totals = self._declared_folate_dfe_totals(active_ingredients)
        rda_data = []
        adequacy_results = []
        safety_flags = []
        ul_review_flags = []
        conversion_evidence = []
        try:
            servings_min = float(min_servings_per_day) if min_servings_per_day is not None else None
        except (TypeError, ValueError):
            servings_min = None
        try:
            servings_max = float(max_servings_per_day) if max_servings_per_day is not None else None
        except (TypeError, ValueError):
            servings_max = None

        servings_estimated = False
        if servings_min is None or servings_min <= 0:
            servings_min = 1
            servings_estimated = True
        if servings_max is None or servings_max <= 0:
            servings_max = servings_min

        # D4.3: per-canonical aggregation buckets. A product declaring
        # multiple forms of the same nutrient (e.g., Vitamin A from
        # Beta-Carotene + Retinyl Palmitate) exposes the consumer to the
        # SUM of those rows. Per-row UL checks alone miss this
        # aggregation risk — a 200% UL exposure split across two rows
        # at 100% UL each would clear per-row checks and never flag.
        # After the main per-row pass, we re-check the UL on the summed
        # total per canonical_id and emit an aggregated safety_flag,
        # suppressing the per-row flags that would otherwise double-count.
        _staged_row_flags: List[Tuple[Optional[str], Dict[str, Any]]] = []
        _per_canonical_totals: Dict[str, Dict[str, Any]] = {}

        # Use new modules if available
        if self.unit_converter and self.rda_calculator:
            try:
                for ingredient in active_ingredients:
                    ing_name = ingredient.get('name', '')
                    std_name = ingredient.get('standardName', '') or ing_name
                    # P0-1b: dailyValue present ⟹ elemental mass (corpus-validated
                    # across 13,753 mineral rows). Rows without it (e.g. Magtein
                    # 2000 mg magnesium L-threonate, which states COMPOUND mass) are
                    # NOT eligible for the UL VERDICT gate — comparing compound mass
                    # to an elemental UL yields a false over-UL.
                    _dv_present = ingredient.get('dailyValue') is not None
                    quantity = ingredient.get('quantity', 0)
                    unit = ingredient.get('unit', '')

                    # Convert quantity to float safely
                    try:
                        quantity_float = float(quantity) if quantity else 0
                    except (ValueError, TypeError):
                        continue

                    if quantity_float == 0:
                        continue
                    dose_data_quality = (
                        dict(ingredient["dose_data_quality"])
                        if isinstance(ingredient.get("dose_data_quality"), dict)
                        else None
                    )

                    # The IQM matcher already resolved the canonical form
                    # (e.g. "retinyl palmitate") via alias matching, but
                    # `unit_converter._detect_vitamin_a_form` runs an
                    # independent regex over the bare ingredient_name.
                    # When DSLD has stripped the form into a separate
                    # field — e.g. label "Vitamin A 25,000 IU" comes
                    # through as `name="Vitamin A"`, `matched_form=
                    # "retinyl palmitate"` — the converter sees only
                    # "Vitamin A", misses retinol_patterns, and falls
                    # through to vitamin_a_unknown → skip_ul_check.
                    # Forwarding the IQM-resolved form lets the regex
                    # hit. Skipped when matched_form is empty or the
                    # placeholder default 'standard'.
                    matched_form = (ingredient.get('matched_form') or '').strip()
                    form_hint_name = (
                        f"{ing_name} {matched_form}"
                        if matched_form and matched_form.lower() != 'standard'
                        else ing_name
                    )

                    # Step 1: Convert units with form detection
                    conversion = self.unit_converter.convert_nutrient(
                        nutrient=std_name,
                        amount=quantity_float,
                        from_unit=unit,
                        ingredient_name=form_hint_name
                    )

                    conv_evidence = conversion.to_dict()
                    conv_evidence["ingredient"] = ing_name
                    if dose_data_quality:
                        conv_evidence["dose_data_quality"] = dose_data_quality
                    conversion_evidence.append(conv_evidence)

                    # Step 2: Compute adequacy with converted amount
                    rule_id = (conversion.conversion_rule_id or '').lower()
                    form_detected = (conversion.form_detected or '').lower()
                    _canonical_for_ul = self._normalize_text(
                        ingredient.get("canonical_id") or std_name
                    )
                    _folate_label_text = self._normalize_text(" ".join(
                        str(value or "")
                        for value in (
                            ing_name,
                            matched_form,
                            ingredient.get("raw_source_text"),
                        )
                    ))
                    _is_folate = _canonical_for_ul in {
                        "folate", "vitamin b9 folate", "vitamin_b9_folate"
                    }
                    _folate_form = norm_module.classify_folate_form(_folate_label_text)
                    _explicit_folic_acid = (
                        _folate_form == norm_module.FOLATE_FORM_FOLIC_ACID
                    )
                    _explicit_non_folic_folate = _folate_form in {
                        norm_module.FOLATE_FORM_METHYLFOLATE,
                        norm_module.FOLATE_FORM_FOLINIC,
                        norm_module.FOLATE_FORM_FOOD,
                    }
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
                    _nutrient_record = (
                        self.rda_calculator._find_nutrient(std_name) or {}
                    )
                    if conversion_failed:
                        unit_key = _rda_mass_unit_key(unit)
                        reference_unit_key = _rda_mass_unit_key(_nutrient_record.get("unit"))
                        if unit_key and reference_unit_key and unit_key == reference_unit_key:
                            conversion_failed = False
                            if conv_evidence.get("error"):
                                conv_evidence["original_error"] = conv_evidence.pop("error")
                            conv_evidence["confidence"] = "not_applicable"
                            conv_evidence["nonfatal_reason"] = (
                                "no_official_ul_reference"
                                if _has_no_official_ul_reference(_nutrient_record)
                                else "reference_unit_already_normalized"
                            )
                    converted_amount = conversion.converted_value or float(quantity)
                    converted_unit = conversion.converted_unit or unit
                    dose_lineage = self._rda_dose_lineage(
                        ingredient,
                        converted_amount=converted_amount,
                        converted_unit=converted_unit,
                        conversion_evidence=conv_evidence,
                        declared_folate_totals=declared_folate_totals,
                    )
                    conv_evidence.update(dose_lineage)
                    skip_ul_check = False
                    skip_ul_reason = None
                    ul_only_skip = False
                    if dose_lineage["dose_role"] == "form_component":
                        # The label-declared DFE total owns this form-derived
                        # conversion. Retain the row for label context but do
                        # not create a second UL or stack dose.
                        skip_ul_check = True
                        skip_ul_reason = "form_component_of_declared_total"
                    elif ingredient.get('is_compound_duplicate'):
                        # The bare elemental sibling row carries the true
                        # dose; checking/summing this row double-counts.
                        skip_ul_check = True
                        skip_ul_reason = "compound_duplicate_row"
                    elif _is_folate and not _explicit_folic_acid:
                        # This pipeline applies the folic-acid UL only to an
                        # identified folic-acid contribution. Preserve adequacy
                        # only when conversion produced verified DFE lineage;
                        # suppress an unsupported UL conclusion independently.
                        skip_ul_check = True
                        ul_only_skip = True
                        skip_ul_reason = (
                            "non_folic_acid_folate_ul_basis"
                            if _explicit_non_folic_folate
                            else "unknown_folate_form_lineage"
                        )
                    elif unknown_form:
                        skip_ul_check = True
                        skip_ul_reason = "unknown_vitamin_form"
                    elif conversion_failed:
                        skip_ul_check = True
                        skip_ul_reason = "conversion_failed"

                    per_day_min = converted_amount * servings_min
                    per_day_max = converted_amount * servings_max
                    amount_for_ul = per_day_max or per_day_min or converted_amount
                    folate_ul_screening = None
                    if (
                        _is_folate
                        and not _explicit_folic_acid
                        and not _explicit_non_folic_folate
                    ):
                        folate_ul_screening = _unknown_folate_ul_screening(
                            quantity_float,
                            unit,
                            ingredient.get("dailyValue"),
                        )
                        if folate_ul_screening:
                            folate_ul_screening["screening_amount"] *= servings_max
                            folate_ul_screening["potential_pct_ul"] = (
                                folate_ul_screening["screening_amount"]
                                / _FOLIC_ACID_ADULT_UL_MCG
                                * 100.0
                            )
                    adequacy = self.rda_calculator.compute_nutrient_adequacy(
                        nutrient=std_name,
                        amount=per_day_min or converted_amount,
                        unit=converted_unit,
                        age_group=_RDA_REFERENCE_PROFILE["age_range"],
                        sex="adult_neutral",
                    )
                    safety = self.rda_calculator.compute_nutrient_adequacy(
                        nutrient=std_name,
                        amount=amount_for_ul,
                        unit=converted_unit,
                        age_group=_RDA_REFERENCE_PROFILE["age_range"],
                        sex="adult_neutral",
                    )

                    adequacy_dict = adequacy.to_dict()
                    adequacy_dict.update({
                        "ul": safety.ul,
                        "ul_status": safety.ul_status,
                        "pct_ul": safety.pct_ul,
                        "over_ul": safety.over_ul,
                        "over_ul_amount": safety.over_ul_amount,
                        "warnings": safety.warnings,
                        "adequacy_exposure": {
                            "per_day": per_day_min,
                            "unit": converted_unit,
                        },
                        "safety_exposure": {
                            "per_day": per_day_max,
                            "unit": converted_unit,
                        },
                        "reference_profile": dict(_RDA_REFERENCE_PROFILE),
                        "data_by_group": list(_nutrient_record.get("data") or []),
                    })
                    if skip_ul_check and ul_only_skip:
                        is_indeterminate_folate = (
                            skip_ul_reason == "unknown_folate_form_lineage"
                        )
                        potential_pct_ul = (
                            folate_ul_screening.get("potential_pct_ul")
                            if folate_ul_screening
                            else None
                        )
                        potential_ul_concern = bool(
                            potential_pct_ul is not None and potential_pct_ul >= 100.0
                        )
                        adequacy_dict.update({
                            "ul": None,
                            "ul_status": (
                                f"indeterminate_{skip_ul_reason}"
                                if is_indeterminate_folate
                                else f"not_applicable_{skip_ul_reason}"
                            ),
                            "pct_ul": None,
                            "over_ul": False,
                            "over_ul_amount": None,
                            "warnings": (
                                [
                                    "Folate UL assessment is indeterminate because "
                                    "the synthetic folic-acid contribution is not identified."
                                ]
                                if is_indeterminate_folate
                                else []
                            ),
                            "skip_ul_check": True,
                            "skip_ul_reason": skip_ul_reason,
                            "ul_assessment_status": (
                                "indeterminate"
                                if is_indeterminate_folate
                                else "not_applicable"
                            ),
                            "potential_ul_concern": potential_ul_concern,
                        })
                        if (
                            is_indeterminate_folate
                            and folate_ul_screening
                            and folate_ul_screening.get("screening_basis")
                            == "bare_mass_worst_case"
                        ):
                            # A legacy bare-mass Folate declaration does not say
                            # whether the mass is total folate or folic acid.
                            # Do not let the converter's fallback guess adequacy.
                            adequacy_dict.update({
                                "rda_ai": None,
                                "rda_ai_source": "unknown",
                                "pct_rda": None,
                                "adequacy_band": "unknown",
                                "scoring_eligible": False,
                                "point_recommendation": 0,
                            })
                        elif _explicit_non_folic_folate and conversion_failed:
                            # A known non-folic identity does not authorize a
                            # guessed DFE factor. Bare-mass folinic/folinate/
                            # leucovorin therefore keeps its UL disposition but
                            # cannot earn adequacy credit.
                            adequacy_dict.update({
                                "rda_ai": None,
                                "rda_ai_source": "unknown",
                                "pct_rda": None,
                                "adequacy_band": "unknown",
                                "scoring_eligible": False,
                                "point_recommendation": 0,
                                "notes": [
                                    *list(adequacy_dict.get("notes") or []),
                                    "Adequacy not assessed: no verified conversion "
                                    "from the declared folate mass to mcg DFE."
                                ],
                            })
                        if is_indeterminate_folate and potential_ul_concern:
                            ul_review_flags.append({
                                "nutrient": "Folate",
                                "assessment_status": "indeterminate",
                                "reason": skip_ul_reason,
                                **folate_ul_screening,
                                "review_required": True,
                            })
                    elif skip_ul_check:
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
                    adequacy_dict.update(dose_lineage)
                    adequacy_dict["per_day_min"] = per_day_min
                    adequacy_dict["per_day_max"] = per_day_max
                    adequacy_dict["servings_per_day_min"] = servings_min
                    adequacy_dict["servings_per_day_max"] = servings_max
                    adequacy_dict["is_servings_estimated"] = servings_estimated
                    if dose_data_quality:
                        adequacy_dict["dose_data_quality"] = dose_data_quality
                    adequacy_results.append(adequacy_dict)

                    # D4.3: STAGE safety flags for later aggregation pass.
                    # Don't append directly — we may replace per-row flags
                    # with a single aggregated flag if multiple forms of
                    # the same canonical combine to exceed UL.
                    _row_canonical = ingredient.get('canonical_id')
                    if not skip_ul_check and safety.over_ul:
                        pct_ul_val = safety.pct_ul or 0
                        over_ul_amount = safety.over_ul_amount or 0
                        _staged_row_flags.append((
                            _row_canonical,
                            {
                                "nutrient": ing_name,
                                "amount": amount_for_ul,
                                "unit": converted_unit,
                                "ul": safety.ul,
                                "pct_ul": pct_ul_val,
                                "over_amount": over_ul_amount,
                                "warning": f"Exceeds UL by {over_ul_amount:.1f}",
                                "severity": "critical" if pct_ul_val >= 200 else "warning",
                                "ul_gate_eligible": _dv_present,
                                "ul_gate_ineligible_reason": (
                                    None if _dv_present
                                    else ("compound_mass_not_elemental"
                                          if self._normalize_text(ing_name) != self._normalize_text(std_name)
                                          else "no_daily_value_anchor")
                                ),
                            }
                        ))

                    # D4.3: Track per-canonical totals for aggregation pass.
                    # Only track rows that were actually UL-checked (skip
                    # unknown-form / conversion-failed rows). Requires a
                    # canonical_id; rows without one can't be grouped.
                    if not skip_ul_check and _row_canonical:
                        group = _per_canonical_totals.setdefault(
                            _row_canonical,
                            {
                                "std_name": std_name,
                                "unit": converted_unit,
                                "total_amount": 0.0,
                                "rows": [],
                                "incompatible_units": False,
                                "ul": safety.ul,  # from first row; all rows share canonical so UL is same
                            },
                        )
                        if group["unit"] != converted_unit:
                            # Two rows for the same canonical but the
                            # unit_converter produced different units
                            # (e.g., one IU-based, one mg-based). Cannot
                            # safely sum — skip aggregation for this
                            # canonical; per-row flags will still emit.
                            group["incompatible_units"] = True
                        else:
                            group["total_amount"] += amount_for_ul
                            group["rows"].append({
                                "ingredient": ing_name,
                                "amount": amount_for_ul,
                                "unit": converted_unit,
                                "pct_ul_individual": safety.pct_ul,
                                "dv_present": _dv_present,
                            })

                    # Sprint E1.5.X-4 — ALWAYS emit `highest_ul` from the RDA
                    # file into the blob, even when the pipeline's own UL check
                    # is skipped (form ambiguous, conversion failed, etc.).
                    # Flutter uses this as the last-resort UL for anonymous
                    # users (see lib/services/fit_score/e1_dosage_calculator.dart
                    # and lib/services/stack/stack_ul_checker.dart). Nullifying
                    # it here silently broke Flutter's fallback on ~57% of
                    # catalog entries. The `skip_ul_check` flag remains — it
                    # now correctly means "pipeline's product-level verdict
                    # skipped" rather than "no UL data available."
                    file_highest_ul = _nutrient_record.get("highest_ul")
                    if isinstance(file_highest_ul, str):
                        try:
                            file_highest_ul = float(file_highest_ul)
                        except (TypeError, ValueError):
                            file_highest_ul = None

                    # Legacy format for backward compatibility
                    rda_data.append({
                        "ingredient": ing_name,
                        "standard_name": std_name,
                        "quantity": quantity,
                        "unit": unit,
                        "converted_quantity": converted_amount,
                        "converted_unit": converted_unit,
                        **dose_lineage,
                        "per_day_min": per_day_min,
                        "per_day_max": per_day_max,
                        "servings_per_day_min": servings_min,
                        "servings_per_day_max": servings_max,
                        "skip_ul_check": skip_ul_check,
                        "skip_ul_reason": skip_ul_reason,
                        "nutrient_unit": adequacy.unit,
                        # Sprint E1.5.X-4: always populated from the RDA file
                        # — never None when the nutrient exists in the table.
                        # Flutter's anonymous-user fallback relies on this.
                        "highest_ul": file_highest_ul,
                        # Sprint E1.5.X-4: adequacy.ul is the age/sex-specific
                        # UL (default profile 19-30 / both). Exposed separately
                        # so consumers can distinguish "profile-specific UL"
                        # from "conservative absolute UL".
                        "ul_for_default_profile": (
                            None if skip_ul_check else safety.ul
                        ),
                        "optimal_range": f"{adequacy.optimal_min}-{adequacy.optimal_max}" if adequacy.optimal_min else "",
                        "pct_rda": None if skip_ul_check else adequacy.pct_rda,
                        "adequacy_band": "unknown" if skip_ul_check else adequacy.adequacy_band,
                        "warnings": [] if skip_ul_check else safety.warnings,
                        "data_by_group": list(_nutrient_record.get("data") or []),
                        "reference_profile": dict(_RDA_REFERENCE_PROFILE),
                        "conversion_evidence": conv_evidence,  # Per-item evidence for coverage gate
                        "is_servings_estimated": servings_estimated,
                    })
                    if dose_data_quality:
                        rda_data[-1]["dose_data_quality"] = dose_data_quality

                # D4.3 AGGREGATION PASS: per-canonical dose summing + UL check.
                # When a product declares multiple forms of the same nutrient,
                # per-row UL checks miss the aggregate exposure. Re-check each
                # canonical's TOTAL dose against its UL; emit one aggregated
                # safety_flag when the sum exceeds UL. Per-row flags for that
                # canonical are suppressed to prevent double-penalty in B7.
                _aggregated_canonicals: set = set()
                for cid, group in _per_canonical_totals.items():
                    if group.get("incompatible_units"):
                        # Unit mismatch within canonical — per-row flags
                        # still emit below; log for audit.
                        self.logger.debug(
                            "UL aggregation skipped for canonical %r: "
                            "incompatible converted units across rows",
                            cid,
                        )
                        continue
                    if len(group["rows"]) < 2:
                        # Single-row canonical — no aggregation needed, per-row
                        # flag (if any) is sufficient.
                        continue
                    try:
                        agg_adequacy = self.rda_calculator.compute_nutrient_adequacy(
                            nutrient=group["std_name"],
                            amount=group["total_amount"],
                            unit=group["unit"],
                            age_group=_RDA_REFERENCE_PROFILE["age_range"],
                            sex="adult_neutral",
                        )
                    except Exception as agg_err:
                        self.logger.debug(
                            "UL aggregation re-check failed for %r: %s",
                            cid, agg_err,
                        )
                        continue

                    if agg_adequacy.over_ul:
                        pct_ul_val = agg_adequacy.pct_ul or 0.0
                        over_ul_amount = agg_adequacy.over_ul_amount or 0.0
                        # Aggregated flag is gate-eligible only if EVERY contributing
                        # row is elemental-confirmed (has a dailyValue).
                        _agg_dv = all(r.get("dv_present") for r in group["rows"])
                        safety_flags.append({
                            "nutrient": group["std_name"],
                            "amount": group["total_amount"],
                            "unit": group["unit"],
                            "ul": agg_adequacy.ul,
                            "pct_ul": pct_ul_val,
                            "over_amount": over_ul_amount,
                            "warning": (
                                f"Aggregated across {len(group['rows'])} forms "
                                f"exceeds UL by {over_ul_amount:.1f} {group['unit']} "
                                f"({pct_ul_val:.0f}% UL)"
                            ),
                            "severity": "critical" if pct_ul_val >= 200 else "warning",
                            "aggregation": "canonical_sum",
                            "canonical_id": cid,
                            "contributing_rows": group["rows"],
                            "ul_gate_eligible": _agg_dv,
                            "ul_gate_ineligible_reason": (None if _agg_dv else "compound_mass_not_elemental"),
                        })
                        _aggregated_canonicals.add(cid)

                # D4.3: Emit per-row flags ONLY for canonicals that were NOT
                # aggregated (dedup). A canonical whose sum exceeded UL already
                # has an aggregated flag above; adding per-row flags for the
                # same canonical would double-count the B7 penalty.
                for row_cid, row_flag in _staged_row_flags:
                    if row_cid and row_cid in _aggregated_canonicals:
                        continue
                    safety_flags.append(row_flag)

                return {
                    **self._rda_reference_stamp,
                    "ingredients_with_rda": rda_data,
                    "analyzed_ingredients": rda_data,  # AC3: Canonical field name for scoring
                    "count": len(rda_data),
                    # Enhanced evidence fields
                    "adequacy_results": adequacy_results,
                    "conversion_evidence": conversion_evidence,
                    "safety_flags": safety_flags,
                    "ul_review_flags": ul_review_flags,
                    "has_over_ul": len(safety_flags) > 0,
                    "is_servings_estimated": servings_estimated,
                    "reference_profile": dict(_RDA_REFERENCE_PROFILE),
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
            **self._rda_reference_stamp,
            "ingredients_with_rda": rda_data,
            "analyzed_ingredients": rda_data,  # AC3: Canonical field name for scoring
            "count": len(rda_data),
            "safety_flags": [],
            "ul_review_flags": [],
            "has_over_ul": False,
            "is_servings_estimated": servings_estimated,
            "reference_profile": dict(_RDA_REFERENCE_PROFILE),
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
            manual_source_type = str(product.get("source_type") or product.get("_source") or "").strip().lower()
            if manual_source_type == "external_manual" or product.get("manual_product_provenance"):
                enriched["source_type"] = manual_source_type or "external_manual"
                enriched["manual_product_provenance"] = dict(product.get("manual_product_provenance") or {})
                if product.get("src"):
                    enriched["manual_product_provenance"].setdefault("source_path", product.get("src"))

            # Strip PII: contacts contain phone, address, email
            # Manufacturer name is already extracted to manufacturer_data
            if 'contacts' in enriched:
                del enriched['contacts']

            # Drop dead passthrough fields — zero downstream consumers, reduces record size.
            # Audit 2026-04: these cleaner fields ride through to the scored record and into
            # the final DB's detail_blob unchanged, but nothing in enrich/score/build_final_db
            # reads them. Pre-cleaning tools (dsld_api_client, dsld_validator) consume some of
            # them on RAW DSLD input, which is upstream of this point. See
            # scripts/tests/test_enrichment_regressions.py::TestEnricherDropsDeadPassthroughFields
            # for the locked contract.
            enriched.pop("src", None)
            enriched.pop("nhanesId", None)
            enriched.pop("brandIpSymbol", None)
            enriched.pop("productVersionCode", None)
            enriched.pop("pdf", None)  # redundant with imageUrl (image_is_pdf flag)
            enriched.pop("thumbnail", None)  # redundant with imageUrl
            enriched.pop("percentDvFootnote", None)
            enriched.pop("hasOuterCarton", None)
            enriched.pop("upcValid", None)
            # Preserve DSLD productType for taxonomy cross-validation before popping
            _raw_pt = enriched.get("productType")
            if isinstance(_raw_pt, dict) and _raw_pt.get("langualCodeDescription"):
                enriched["dsld_product_type_raw"] = _raw_pt
            enriched.pop("productType", None)
            enriched.pop("events", None)  # only "Off Market"/"Date entered", no safety signal
            enriched.pop("labelRelationships", None)
            enriched.pop("metadata", None)  # mappingStats/transparencyMetrics recomputed via match_ledger
            enriched.pop("images", None)  # imageUrl is the consumed field

            # Map DSLD field names to scoring-expected names for consistency
            if 'id' in enriched and 'dsld_id' not in enriched:
                enriched['dsld_id'] = enriched['id']
            if 'fullName' in enriched and 'product_name' not in enriched:
                enriched['product_name'] = enriched['fullName']
            if 'brandName' in enriched and 'brand_name' not in enriched:
                enriched['brand_name'] = enriched['brandName']

            # Add enrichment metadata
            enriched["enrichment_version"] = self.VERSION
            enriched["compatible_scoring_versions"] = self.COMPATIBLE_SCORING_VERSIONS
            enriched["enriched_date"] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            enriched["reference_versions"] = self.reference_versions  # Track data file versions for auditability

            # Section A: Ingredient Quality
            enriched["ingredient_quality_data"] = self._collect_ingredient_quality_data(product)

            enriched["delivery_data"] = self._collect_delivery_data(product)
            enriched["absorption_data"] = self._collect_absorption_data(enriched)
            enriched["formulation_data"] = self._collect_formulation_data(enriched)

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
            # Pass ingredient_quality_data so delivers_markers can drive
            # marker-via-ingredient clinical matches (identity_bioactivity_split
            # Phase 4 + Phase 5).
            enriched["evidence_data"] = self._collect_evidence_data(
                enriched, ingredient_quality_data=enriched.get("ingredient_quality_data")
            )

            # Section D: Brand Trust
            manufacturer_data = self._collect_manufacturer_data(product)
            enriched["manufacturer_data"] = manufacturer_data

            # P1.3: Add manufacturer_normalized at top-level for stable matching
            manufacturer_raw = manufacturer_data.get('manufacturer', '') or manufacturer_data.get('brand_name', '')
            enriched["manufacturer_normalized"] = self._normalize_company_name(manufacturer_raw)

            # P0.4: Serving basis and form factor for deterministic prescore
            # SP-3 (2026-05-21): also emit canonical form_factor for downstream
            # consumers. Legacy `form_factor` is kept additive.
            serving_data = self._collect_serving_basis_data(product)
            enriched["serving_basis"] = serving_data["serving_basis"]
            enriched["form_factor"] = serving_data["form_factor"]
            enriched["form_factor_canonical"] = serving_data.get(
                "form_factor_canonical", "unknown"
            )

            # Section E: User Profile Data (for device-side scoring)
            collect_rda_ul_data = self.config.get("processing_config", {}).get("collect_rda_ul_data", True)
            if collect_rda_ul_data:
                servings_min = serving_data["serving_basis"].get("min_servings_per_day")
                servings_max = serving_data["serving_basis"].get("max_servings_per_day")
                enriched["rda_ul_data"] = self._collect_rda_ul_data(
                    enriched,
                    min_servings_per_day=servings_min,
                    max_servings_per_day=servings_max
                )
                if isinstance(enriched["rda_ul_data"], dict):
                    enriched["rda_ul_data"]["collection_enabled"] = True
            else:
                enriched["rda_ul_data"] = self._empty_rda_ul_payload("disabled_by_config")

            # Probiotic-specific data
            enriched["probiotic_data"] = self._collect_probiotic_data(product)

            # Canonical taxonomy classification (v2) — NP-filtered, expanded types
            # — plus every field derived from it. MUST run AFTER probiotic_data
            # so the NP exemption gate for probiotic strains (is_probiotic_product)
            # can fire correctly. See apply_taxonomy_projection's precondition.
            self.apply_taxonomy_projection(enriched)

            # Percentile category (cohort ranking). MUST run AFTER the taxonomy:
            # this projects the canonical classification, it does not compete
            # with it. See _decorate_percentile_category and plan §5/§6.
            enriched.update(self._decorate_percentile_category(enriched))

            # Dietary sensitivity data (sugar/sodium for diabetes/hypertension users)
            enriched["dietary_sensitivity_data"] = self._collect_dietary_sensitivity_data(product)

            # Nutrition summary (all five macros — additive, does not replace sugar/sodium)
            enriched["nutrition_summary"] = self._collect_nutrition_summary(product)

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
            enriched["display_ingredients"] = self._enrich_display_ingredients(enriched)

            # P0.2: Dosage normalization with unit conversion evidence
            if self.dosage_normalizer:
                try:
                    dosage_result = self.dosage_normalizer.normalize_product_dosages(product)
                    enriched["dosage_normalization"] = dosage_result.to_dict()
                except Exception as e:
                    self.logger.warning(f"Dosage normalization failed: {e}")
                    enriched["dosage_normalization"] = {"success": False, "error": str(e)}

            export_contract_issues = self._validate_export_contract_fields(enriched)
            if export_contract_issues:
                issues.extend([f"export_contract: {issue}" for issue in export_contract_issues])
                self.logger.error(
                    "Product %s: export contract validation failed - %s",
                    product_id,
                    export_contract_issues[:10],
                )

            # Enrichment metadata (version lock for scoring compatibility)
            enriched["enrichment_metadata"] = {
                "enrichment_version": self.VERSION,
                "scoring_compatibility": self.COMPATIBLE_SCORING_VERSIONS,
                "generated_by": "SupplementEnricherV3",
                "generated_at": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                "data_completeness": self._calculate_completeness(enriched),
                "ready_for_scoring": True,
                "unmapped_active_count": enriched.get("ingredient_quality_data", {}).get("unmapped_count", 0),
                "export_contract_valid": len(export_contract_issues) == 0,
                "export_contract_issues": export_contract_issues,
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
            # Data structure issues - log and zero out all enrichment sections
            # BEFORE returning. Without this, a mid-enrichment KeyError could
            # leave ingredient_quality_data populated but compliance_data or
            # contaminant_data missing, causing the scorer to produce scores
            # without safety checks. Matches the broad Exception handler below.
            self.logger.error(f"Product {product_id}: Data structure error: {e}")
            issues.append(f"Data structure error: {str(e)}")
            product.update(copy.deepcopy(self.EMPTY_ENRICHMENT_SCHEMA))
            product["enrichment_version"] = self.VERSION
            product["enriched_date"] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            product["enrichment_status"] = "failed"
            product["enrichment_error"] = f"Data structure error: {str(e)}"
            return product, issues
        except (ValueError, AttributeError) as e:
            # Value/attribute issues - log and zero out all enrichment sections
            # BEFORE returning. See note in (KeyError, TypeError) handler above.
            self.logger.error(f"Product {product_id}: Value error: {e}")
            issues.append(f"Value error: {str(e)}")
            product.update(copy.deepcopy(self.EMPTY_ENRICHMENT_SCHEMA))
            product["enrichment_version"] = self.VERSION
            product["enriched_date"] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            product["enrichment_status"] = "failed"
            product["enrichment_error"] = f"Value error: {str(e)}"
            return product, issues
        except Exception as e:
            # Unexpected error - log with traceback for debugging, but don't crash batch
            self.logger.error(f"Product {product_id}: Unexpected enrichment error: {e}", exc_info=True)
            issues.append(f"Enrichment error: {str(e)}")

            # Zero out all enrichment sections to prevent partial data from leaking
            # to the scorer. Without this, a crash mid-enrichment could leave
            # ingredient_quality_data populated but compliance_data missing,
            # causing the scorer to produce scores without safety checks.
            product.update(copy.deepcopy(self.EMPTY_ENRICHMENT_SCHEMA))
            product["enrichment_version"] = self.VERSION
            product["enriched_date"] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
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
            bool(enriched.get("supplement_taxonomy", {}).get("primary_type")),
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
                # Parent-context identity is punctuation-insensitive: DSLD
                # routinely emits ``Alpha-GPC`` while the IQM parent is
                # ``Alpha GPC``.  The general text normalizer deliberately
                # preserves hyphens for form matching, so use the stable key
                # canonicalizer at this identity-only boundary.
                normed = norm_module.make_normalized_key(str(raw or ""))
                if normed and normed not in index:
                    index[normed] = parent_key
        return index

    def _infer_preferred_parent_from_context_cached(
        self, context_name: Optional[str], quality_map: Dict
    ) -> Optional[str]:
        """Infer preferred parent via cached normalized context index."""
        context_norm = norm_module.make_normalized_key(str(context_name or ""))
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
                # Sprint 1.1: cleaner-side UNII / alternateNames match overrides
                # the default tier mapping. When the cleaner resolved this
                # ingredient via Tier-0 UNII match or via alternateNames
                # fallback, it stashed the method on `cleaner_match_method`.
                # That attribution must reach the final match_ledger so audit
                # tooling can prove WHY the match happened (UNII vs name).
                cleaner_method_str = ing.get("cleaner_match_method")
                cleaner_method = _CLEANER_MATCH_METHOD_MAP.get(cleaner_method_str)
                if cleaner_method is not None:
                    method = cleaner_method
                else:
                    # Map match_tier to method (original cleaner-name-based path)
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
                        canonical_id=ing.get("matched_entry_id"),
                        normalized_key=normalized_key,
                    )
                elif ing.get("recognized_non_scorable"):
                    # Sprint 1.1: surface cleaner-side UNII/alternateNames
                    # attribution even on the recognized-non-scorable path.
                    _cm = ing.get("cleaner_match_method")
                    cleaner_method = _CLEANER_MATCH_METHOD_MAP.get(_cm) if _cm else None
                    ledger.record_recognized_non_scorable(
                        domain=DOMAIN_INGREDIENTS,
                        raw_source_text=raw_text,
                        raw_source_path=source_path,
                        recognition_source=ing.get("recognition_source") or "rule_based",
                        recognition_reason=ing.get("recognition_reason") or "recognized_non_scorable",
                        canonical_id=ing.get("matched_entry_id"),
                        matched_to_name=ing.get("matched_entry_name") or std_name or raw_text,
                        normalized_key=normalized_key,
                        cleaner_match_method=cleaner_method,
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
                        canonical_id=ing.get("recognized_entry_id") or ing.get("matched_entry_id"),
                        normalized_key=normalized_key,
                    )
                else:
                    # Sprint 1.1: surface cleaner-side UNII/alternateNames
                    # attribution on the skipped/recognized path too.
                    _cm = ing.get("cleaner_match_method")
                    cleaner_method = _CLEANER_MATCH_METHOD_MAP.get(_cm) if _cm else None
                    ledger.record_recognized_non_scorable(
                        domain=DOMAIN_INGREDIENTS,
                        raw_source_text=raw_text,
                        raw_source_path=source_path,
                        recognition_source=recognition_source or "rule_based",
                        recognition_reason=recognition_reason or "recognized_non_scorable",
                        canonical_id=ing.get("recognized_entry_id") or ing.get("matched_entry_id"),
                        matched_to_name=recognized_entry_name,
                        normalized_key=normalized_key,
                        cleaner_match_method=cleaner_method,
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
        # CLAIMS DOMAIN
        # =====================================================================
        # Claims are auditable label assertions, not scorable ingredient
        # identities. Record each one as recognized/non-scorable so coverage is
        # based on inspected source claims instead of a vacuous empty domain.
        for index, claim in enumerate(product.get("claims", []) or []):
            if isinstance(claim, str):
                raw_text = claim.strip()
            elif isinstance(claim, dict):
                raw_text = str(
                    claim.get("text")
                    or claim.get("langualCodeDescription")
                    or claim.get("notes")
                    or ""
                ).strip()
            else:
                raw_text = ""
            if not raw_text:
                continue

            ledger.record_recognized_non_scorable(
                domain=DOMAIN_CLAIMS,
                raw_source_text=raw_text,
                raw_source_path=f"claims[{index}]",
                recognition_source="claim_scope_audit",
                recognition_reason="label_claim_audited_not_identity_scorable",
                canonical_id="label_claim",
                matched_to_name=raw_text,
                normalized_key=norm_module.make_normalized_key(raw_text),
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

    def process_all(
        self,
        input_path: str,
        output_dir: str,
        run_id: Optional[str] = None,
    ) -> Dict:
        """Process all files in input path"""
        effective_run_id = ensure_run_id(run_id)
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
                str(path)
                for path in select_stage_input_files(
                    Path(input_path),
                    "clean",
                    patterns=(input_pattern,),
                )
            ]
        else:
            raise FileNotFoundError(f"Input path not found: {input_path}")

        # Sort for deterministic processing order (reproducible runs)
        input_files.sort()

        if not input_files:
            raise ValueError(f"No JSON files found in: {input_path}")

        self.logger.info(f"Found {len(input_files)} files to process")

        # Process all files
        start_time = datetime.now(timezone.utc)
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
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        summary = {
            "processing_info": {
                "version": self.VERSION,
                "run_id": effective_run_id,
                "files_processed": len(input_files),
                "duration_seconds": round(duration, 2),
                "timestamp": end_time.isoformat().replace("+00:00", "Z")
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
            reports_dir = str(report_run_directory(
                Path(output_dir) / reports_folder,
                effective_run_id,
            ))

            summary_file = os.path.join(
                reports_dir,
                f"{report_prefix}.json",
            )

            # Atomic write: prevents partial files on crash
            self._atomic_write_json(summary_file, summary)

            # Save parent fallback report — always overwrite to prevent stale files
            fallback_file = os.path.join(reports_dir, "parent_fallback_report.json")
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
                self._atomic_write_json(fallback_file, fallback_report)
                self.logger.info(
                    f"Parent fallback report saved: {fallback_file} "
                    f"({len(seen_fallbacks)} unique, {len(self._parent_fallback_details)} total)"
                )
            else:
                fallback_report = {
                    "total_fallback_count": 0,
                    "unique_fallback_count": 0,
                    "note": "No parent fallback issues — all ingredients matched specific form aliases.",
                    "fallbacks": [],
                }
                self._atomic_write_json(fallback_file, fallback_report)
                self.logger.info(f"Parent fallback report: 0 fallbacks ({fallback_file})")

            # Save FORM_UNMAPPED_FALLBACK audit report — always overwrite to prevent stale files
            form_fb_file = os.path.join(reports_dir, "form_fallback_audit_report.json")
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
                    "generated_at": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
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
                self._atomic_write_json(form_fb_file, form_fallback_report)
                self.logger.info(
                    f"Form fallback audit report saved: {form_fb_file} "
                    f"({len(differs)} differ, {len(same)} same, "
                    f"{len(self._form_fallback_details)} total occurrences)"
                )
            else:
                form_fallback_report = {
                    "generated_at": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                    "total_form_fallback_count": 0,
                    "unique_form_fallback_count": 0,
                    "forms_differ_count": 0,
                    "forms_same_count": 0,
                    "note": "No form fallback issues — all ingredients matched specific form aliases.",
                    "action_needed_differs": [],
                    "likely_ok_same": [],
                }
                self._atomic_write_json(form_fb_file, form_fallback_report)
                self.logger.info(f"Form fallback audit report: 0 fallbacks ({form_fb_file})")
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



def _resolve_cli_paths(args: argparse.Namespace, config: Dict[str, Any]) -> Tuple[str, str]:
    """Resolve input/output overrides independently instead of all-or-nothing."""
    paths = config.get("paths", {})
    input_path = args.input_dir or paths.get(
        "input_directory", "output_Lozenges/cleaned"
    )
    output_dir = args.output_dir or paths.get(
        "output_directory", "output_Lozenges_enriched"
    )
    return input_path, output_dir


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
    parser.add_argument('--run-id', help='Path-safe pipeline run identifier')

    args = parser.parse_args()

    # GUARD: Verify working directory before anything else
    _verify_working_directory(args.config)

    try:
        # Initialize enricher
        enricher = SupplementEnricherV3(args.config)

        input_path, output_dir = _resolve_cli_paths(args, enricher.config)

        if args.dry_run:
            enricher.logger.info("DRY RUN MODE")
            enricher.logger.info(f"Would process files from: {input_path}")
            enricher.logger.info(f"Would output to: {output_dir}")
            return

        # Process all files
        enricher.process_all(input_path, output_dir, run_id=args.run_id)

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
