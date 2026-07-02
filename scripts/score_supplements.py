#!/usr/bin/env python3
"""PharmaGuide scoring engine (v3.1 spec, data schema v5.0).

This scorer is arithmetic-only: matching and NLP are expected to be performed
in cleaning/enrichment. The scorer consumes enriched canonical fields.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Optional tqdm import for progress bars
try:
    from tqdm import tqdm

    TQDM_AVAILABLE = True
except Exception:
    tqdm = None
    TQDM_AVAILABLE = False


# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from constants import LOG_DATE_FORMAT, LOG_FORMAT
from audit_evidence_utils import derive_non_gmo_audit
from inactive_ingredient_resolver import InactiveIngredientResolver
from identity.safety import (
    normalize_safety_source,
    safety_flag_matches_status,
)
from scoring_input_contract import (
    get_scoring_ingredients,
    is_nutrition_only_product,
)

try:
    from match_ledger import (
        SCORING_STATUS_BLOCKED,
        SCORING_STATUS_NOT_APPLICABLE,
        SCORING_STATUS_SCORED,
        SCORE_BASIS_BIOACTIVES,
        SCORE_BASIS_NO_SCORABLE,
        SCORE_BASIS_SAFETY_BLOCK,
        SCORE_BASIS_SCORING_ERROR,
    )
except ImportError:
    SCORING_STATUS_BLOCKED = "blocked"
    SCORING_STATUS_NOT_APPLICABLE = "not_applicable"
    SCORING_STATUS_SCORED = "scored"
    SCORE_BASIS_BIOACTIVES = "bioactives_scored"
    SCORE_BASIS_NO_SCORABLE = "no_scorable_ingredients"
    SCORE_BASIS_SAFETY_BLOCK = "safety_block"
    SCORE_BASIS_SCORING_ERROR = "scoring_error"

# Sprint E1.7 — Bucket C divert. DSLD upstream gap (whey/protein/casein/
# meal-replacement powders) where ingredientRows captures only the
# nutrition panel + minerals, not the protein itself. These products
# previously got NOT_SCORED (signaling "real supplement, mapping failed")
# which masked the upstream data gap. NUTRITION_ONLY signals "food-shape
# product, no bioactive scoring — banned/harmful flags still apply".
SCORE_BASIS_NUTRITION_ONLY = "nutrition_only_food_shape"

# Track A.1 — Standardized Botanical Anchor (spec:
# reports/not_scored_triage/track_A1_standardized_botanical_anchor_spec.md).
# Products with empty ingredients_scorable but a dosed row that identity-matches
# a meets_threshold=True standardized botanical get a conservative capped
# scoring path with a verdict ceiling (never SAFE).
SCORE_BASIS_BOTANICAL_ANCHOR = "standardized_botanical_anchor"
FLAG_STANDARDIZED_BOTANICAL_ANCHOR = "SCORED_VIA_STANDARDIZED_BOTANICAL_ANCHOR"
ANCHOR_NON_DOSE_UNITS = {"", "np", "n/a", "na", "none", "unspecified", "0"}

# Track A.2a — Bucket A blend-header anchor (spec:
# reports/not_scored_triage/track_A2_blend_header_anchor_spec.md).
# Narrow eligibility: products with empty ingredients_scorable, NOT
# Track-A.1-eligible, but with a dosed blend_header row whose canonical_id
# is a real single-compound or named-curated IQM/botanical entry (not generic
# BLEND_*/PII_* and not in the class-level denylist). Class-level scoring
# for the remaining reserved cids (prebiotics, probiotics, whey_protein,
# collagen) still needs dedicated slices (CFU provenance, fiber/protein
# rubric) and is excluded here. Wave 6.Z A.2b landed digestive_enzymes
# via the same anchor path plus a nested-child usable-dose guard
# (see _has_blend_header_anchor below + spec at
# reports/blend_header_subtype_inventory.md).
SCORE_BASIS_BLEND_HEADER_ANCHOR = "blend_header_anchor"
FLAG_BLEND_HEADER_ANCHOR = "SCORED_VIA_BLEND_HEADER_ANCHOR"
BLEND_HEADER_ANCHOR_CANONICAL_DENYLIST = frozenset({
    "prebiotics",
    "probiotics",
    "whey_protein",
    "collagen",
})
BLEND_HEADER_ANCHOR_ALLOWED_DBS = frozenset({
    "ingredient_quality_map",
    "botanical_ingredients",
})

_OPAQUE_OMEGA3_BLEND_PATTERN = re.compile(
    r"(?:\bomega|\bfish\s*oil\b|\bkrill\b|\bmarine\s*lipid\b|\bepa\b|\bdha\b|\bn-?3\b|\bfatty\s*acid\b)s?",
    re.IGNORECASE,
)

# Premium-form recognition for EPA/DHA. When EPA/DHA dose is disclosed but
# the haystack contains none of the canonical forms from the
# ``omega3_molecular_forms`` vocab category, the A2 premium-delivery credit
# is not awarded. UI then explains: "EPA/DHA dose is disclosed, but omega-3
# form is not specified on the label, so no premium-form credit was
# awarded." Sourced from scripts/data/form_keywords_vocab.json — single
# source of truth shared with the cleaner and enricher.
import form_vocab as _form_vocab  # noqa: E402

# Food-shape product_name keywords. Substring match, case-insensitive.
# Curated from real Bucket C examples in the 20-brand corpus.
_FOOD_SHAPE_NAME_KEYWORDS = (
    "whey",
    "casein",
    "pea protein",
    "soy protein",
    "rice protein",
    "hemp protein",
    "plant protein",
    "plant-based protein",
    "protein powder",
    "protein shake",
    "protein blend",
    "meal replacement",
    "mass gainer",
    "weight gainer",
    "smoothie mix",
)


def clamp(low: float, high: float, value: float) -> float:
    return max(low, min(high, value))


def as_float(value: Any, default: Optional[float] = 0.0) -> Optional[float]:
    if value is None:
        return default
    try:
        result = float(value)
        if not math.isfinite(result):
            return default
        return result
    except (TypeError, ValueError):
        return default


def norm_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def canon_key(value: Any) -> str:
    text = norm_text(value)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


# Sprint E1.3.4 — enzyme recognition credit.
# Known enzyme names for the `require_named_enzyme` gate. Case-folded
# substrings; an ingredient qualifies when any entry is a whole-word
# match in its name or standard_name.
_KNOWN_ENZYMES = frozenset({
    "amylase", "protease", "lipase", "cellulase", "lactase",
    "bromelain", "papain", "pepsin", "rennin", "trypsin", "chymotrypsin",
    "serrapeptase", "alpha-galactosidase", "alpha galactosidase",
    "hemicellulase", "invertase", "maltase", "sucrase",
    "xylanase", "beta-glucanase", "phytase", "pectinase",
    "catalase", "superoxide dismutase", "sod",
    "nattokinase",
})


def _is_known_enzyme_name(ing: Dict[str, Any]) -> Optional[str]:
    """Return a canonical enzyme key if the ingredient matches one from
    _KNOWN_ENZYMES; else None. Case-insensitive whole-word match over
    name and standard_name. Also accepts category == 'enzyme' only as a
    secondary signal when combined with a matched name — category alone
    does NOT qualify (dev rule: require named enzyme)."""
    name = (ing.get("name") or "").strip().lower()
    std = (ing.get("standard_name") or "").strip().lower()
    for enzyme in _KNOWN_ENZYMES:
        if re.search(r"\b" + re.escape(enzyme) + r"\b", name) or \
           re.search(r"\b" + re.escape(enzyme) + r"\b", std):
            return enzyme
    return None


def _has_valid_enzyme_activity(ing: Dict[str, Any], gate_cfg: Dict[str, Any]) -> bool:
    """Check if enzyme ingredient has a numeric activity value in an
    allowed unit (DU, HUT, FIP, ALU, CU, SKB, etc.). Used only when
    min_activity_gate.enabled is True."""
    allowed = [u.upper() for u in (gate_cfg.get("allowed_units") or [])]
    min_value = float(gate_cfg.get("min_value") or 0.0)
    unit = (ing.get("unit") or "").strip().upper()
    if unit not in allowed:
        return False
    try:
        qty = float(ing.get("quantity") or 0)
    except (TypeError, ValueError):
        return False
    return qty >= min_value


def _compute_enzyme_recognition_bonus(
    ingredients: List[Dict[str, Any]],
    cfg: Dict[str, Any],
) -> Dict[str, Any]:
    """Config-gated enzyme recognition credit. Conservative, capped,
    deduplicated by canonical enzyme name. No credit when config is
    disabled / missing. Does not mutate input.
    """
    if not cfg or not cfg.get("enabled", False):
        return {
            "enzyme_recognition_points": 0.0,
            "recognized_enzymes_count": 0,
            "recognized_enzymes": [],
        }

    per_enzyme = float(cfg.get("per_enzyme_points", 0.0) or 0.0)
    max_points = float(cfg.get("max_points", 0.0) or 0.0)
    require_named = bool(cfg.get("require_named_enzyme", True))
    gate_cfg = cfg.get("min_activity_gate") or {}
    gate_enabled = bool(gate_cfg.get("enabled", False))

    seen: set = set()
    recognized_names: List[str] = []
    for ing in ingredients or []:
        if not isinstance(ing, dict):
            continue
        canonical = _is_known_enzyme_name(ing) if require_named else (
            (ing.get("name") or "").strip().lower() or None
        )
        if not canonical:
            continue
        if gate_enabled and not _has_valid_enzyme_activity(ing, gate_cfg):
            continue
        if canonical in seen:
            continue
        seen.add(canonical)
        recognized_names.append(canonical)

    total = min(max_points, per_enzyme * len(seen)) if max_points > 0 else per_enzyme * len(seen)
    return {
        "enzyme_recognition_points": total,
        "recognized_enzymes_count": len(seen),
        "recognized_enzymes": sorted(recognized_names),
    }


# Sprint E1.3.2.c — probiotic CFU-adequacy point uplift.
# Config-driven (section_A_ingredient_quality.probiotic_cfu_adequacy):
#   tier_points           {low,adequate,good,excellent}   → base points
#   support_level_caps    {high,moderate,weak}           → multipliers
#   per_product_max_uplift                               → hard cap
#
# Hard gates (return 0 for that strain's contribution):
#   adequacy_tier is None             — no tier match / not in DB
#   cfu_per_day is None               — multi-strain blend (per-member CFU unknowable)
#   clinical_support_level missing    — default to weak cap (0.5)
#
# Dev rule pinned in docstring: "Points follow confidence — not just
# presence." NEVER infer per-member CFU from blend totals.
def _compute_probiotic_cfu_adequacy_points(
    clinical_strains: List[Dict[str, Any]],
    cfg: Dict[str, Any],
) -> Dict[str, Any]:
    """Compute per-strain adequacy points + summed + capped uplift.

    Returns:
      {
        "probiotic_cfu_adequacy_points": float (capped per product),
        "strain_contributions": [{"tier","support","cfu_per_day","points"}, ...],
      }
    """
    if not cfg or not cfg.get("enabled", False):
        return {"probiotic_cfu_adequacy_points": 0.0, "strain_contributions": []}

    tier_points = cfg.get("tier_points") or {}
    support_caps = cfg.get("support_level_caps") or {}
    per_product_max = float(cfg.get("per_product_max_uplift", 0.0) or 0.0)

    contributions: List[Dict[str, Any]] = []
    total = 0.0
    for strain in clinical_strains or []:
        if not isinstance(strain, dict):
            continue
        # Hard gate: postbiotic / heat-killed / tyndallized / paraprobiotic
        # forms are NOT live probiotics. They have a different mechanism
        # (cell-wall fragments interact with gut immune cells locally) and
        # CFU dosing thresholds do not apply. Per dev review 2026-05-01:
        # is_inactivated → no CFU scoring contribution.
        if strain.get("is_inactivated") or strain.get("is_postbiotic"):
            contributions.append({
                "tier": strain.get("adequacy_tier"),
                "support": strain.get("clinical_support_level"),
                "cfu_per_day": strain.get("cfu_per_day"),
                "points": 0.0,
                "skipped_reason": "postbiotic_inactivated_no_cfu_credit",
            })
            continue
        tier = strain.get("adequacy_tier")
        cfu = strain.get("cfu_per_day")
        # Hard gates: tier missing or cfu missing (multi-strain) → 0.
        if tier is None or cfu is None:
            contributions.append({
                "tier": tier, "support": strain.get("clinical_support_level"),
                "cfu_per_day": cfu, "points": 0.0,
            })
            continue
        base = float(tier_points.get(tier, 0.0) or 0.0)
        # Default to weak cap when support level is missing / unknown.
        support = (strain.get("clinical_support_level") or "weak").strip().lower()
        mult = float(support_caps.get(support, support_caps.get("weak", 0.5)) or 0.0)
        pts = base * mult
        total += pts
        contributions.append({
            "tier": tier, "support": support, "cfu_per_day": cfu, "points": pts,
        })

    # Per-product hard cap.
    if per_product_max > 0:
        total = min(total, per_product_max)

    return {
        "probiotic_cfu_adequacy_points": total,
        "strain_contributions": contributions,
    }


class SupplementScorer:
    """Main scorer implementing the v3.0 quality score specification."""

    COMPATIBLE_ENRICHMENT_VERSIONS = [
        "3.0.0",
        "3.0.1",
        "3.1.0",
        "3.2.0",
        "3.3.0",
        "3.4.0",
    ]

    REQUIRED_ENRICHED_FIELDS = ["dsld_id", "product_name", "enrichment_version"]
    _CATEGORY_PERCENTILE_MIN_COHORT = 5

    def __init__(self, config_path: str = "config/scoring_config.json"):
        self.logger = self._setup_logging()
        self.config = self._load_config(config_path)

        self.VERSION = self.config.get("_documentation", {}).get("version", "3.0.0")
        self.OUTPUT_SCHEMA_VERSION = self.config.get("_documentation", {}).get(
            "output_schema_version", self.VERSION
        )

        self.feature_gates = self.config.get("feature_gates", {})
        self.paths = self.config.get("paths", {})
        self._parent_total_warned = False
        self._branded_blend_anchors = self._load_branded_blend_anchors()
        self._inactive_resolver: Optional[InactiveIngredientResolver] = None

    def _get_inactive_resolver(self) -> InactiveIngredientResolver:
        if self._inactive_resolver is None:
            self._inactive_resolver = InactiveIngredientResolver()
        return self._inactive_resolver

    def _load_branded_blend_anchors(self) -> List[Dict[str, Any]]:
        """Load exact-match curated branded-blend anchor overrides.

        This is intentionally data-driven.  Generic BLEND_*/PII_* rows remain
        fail-closed unless an exact branded header alias is listed in
        scripts/data/branded_blend_anchor_overrides.json with verified evidence.
        """
        data_file = Path(__file__).parent / "data" / "branded_blend_anchor_overrides.json"
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

        anchors: List[Dict[str, Any]] = []
        for entry in safe_list(raw.get("anchors")):
            if not isinstance(entry, dict):
                continue
            aliases = {norm_text(a) for a in safe_list(entry.get("aliases")) if norm_text(a)}
            if not aliases:
                continue
            anchors.append({
                "id": norm_text(entry.get("id") or ""),
                "aliases": aliases,
                "allowed_source_dbs": {
                    norm_text(v) for v in safe_list(entry.get("allowed_source_dbs")) if norm_text(v)
                },
                "allowed_canonical_ids": {
                    norm_text(v) for v in safe_list(entry.get("allowed_canonical_ids")) if norm_text(v)
                },
            })
        return anchors

    def _setup_logging(self) -> logging.Logger:
        logging.basicConfig(
            level=logging.INFO,
            format=LOG_FORMAT,
            datefmt=LOG_DATE_FORMAT,
            handlers=[logging.StreamHandler(sys.stdout)],
        )
        return logging.getLogger(__name__)

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        try:
            if not os.path.isabs(config_path):
                config_path = str(Path(__file__).parent / config_path)
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            self.logger.warning("Using default config due to load error: %s", exc)
            return self._default_config()

    def _default_config(self) -> Dict[str, Any]:
        return {
            "_documentation": {
                "version": "3.1.0",
                "description": "Fallback v3.1 scorer config",
                "last_updated": "2026-02-25",
            },
            "feature_gates": {
                "require_full_mapping": False,
                "probiotic_extended_scoring": False,
                "allow_non_probiotic_probiotic_bonus_with_strict_gate": True,
                "enable_non_gmo_bonus": False,
                "enable_hypoallergenic_bonus": False,
                "enable_d1_middle_tier": False,
            },
            "paths": {
                "input_directory": "output_Lozenges_enriched/enriched",
                "output_directory": "output_Lozenges_scored",
            },
            "processing": {
                "show_progress_bar": True,
            },
        }

    @staticmethod
    def validate_enriched_product(product: Dict[str, Any]) -> Tuple[bool, List[str]]:
        issues: List[str] = []
        if not isinstance(product, dict):
            return False, ["Product must be a dictionary"]

        has_id = bool(product.get("dsld_id"))
        has_name = bool(product.get("product_name"))
        if not has_id:
            issues.append("Missing product ID (dsld_id)")
        if not has_name:
            issues.append("Missing product name (product_name)")

        if not (product.get("enrichment_version") or product.get("enriched_date")):
            issues.append("Missing enrichment version metadata")

        # Reject products where enrichment failed — safety data is unreliable.
        # Without this gate, a product with a banned substance whose enrichment
        # crashed would appear SAFE (empty contaminant_data passes B0 gate).
        enrichment_status = product.get("enrichment_status")
        if enrichment_status in {"failed", "error", "validation_failed"}:
            return False, [
                f"Enrichment status is '{enrichment_status}' — "
                f"cannot score safely: {product.get('enrichment_error', 'unknown error')}"
            ]

        return len([i for i in issues if "Missing product" in i]) == 0, issues

    def _feature_on(self, key: str, default: bool = False) -> bool:
        return bool(self.feature_gates.get(key, default))

    def _section_max(self, section: str, default: float) -> float:
        section_key = norm_text(section)
        section_maximums = self.config.get("section_maximums", {}) or {}
        mapping = {
            "a": (
                self.config.get("section_A_ingredient_quality", {}).get("_max"),
                section_maximums.get("A_ingredient_quality"),
            ),
            "b": (
                self.config.get("section_B_safety_purity", {}).get("_max"),
                section_maximums.get("B_safety_purity"),
            ),
            "c": (
                self.config.get("section_C_evidence_research", {}).get("_max"),
                section_maximums.get("C_evidence_research"),
            ),
            "d": (
                self.config.get("section_D_brand_trust", {}).get("_max"),
                section_maximums.get("D_brand_trust"),
            ),
            "e": (
                self.config.get("section_E_dose_adequacy", {}).get("_max"),
                section_maximums.get("E_dose_adequacy"),
            ),
        }
        candidates = mapping.get(section_key, ())
        for value in candidates:
            numeric = as_float(value, None)
            if numeric is not None:
                return numeric
        return default

    # ---------------------------------------------------------------------
    # Classifier + mapping gate
    # ---------------------------------------------------------------------

    # Taxonomy primary_type → legacy scoring-behavior mapping.
    # Scoring logic checks against these sets — not raw primary_type strings.
    _SINGLE_TYPES = frozenset({
        "single", "single_nutrient",
        "single_vitamin", "single_mineral",
        "herbal_botanical", "amino_acid", "collagen",
    })
    _MULTI_TYPES = frozenset({"multivitamin"})
    _PROBIOTIC_TYPES = frozenset({"probiotic"})

    def _classify_supplement_type(self, product: Dict[str, Any]) -> str:
        """Resolve supplement type for scoring — always returns taxonomy primary_type.

        Current enriched products should provide supplement_taxonomy. Legacy
        supplement_type fallback is retained only for old batches and is
        surfaced through scoring diagnostics/audits.
        """
        taxonomy = product.get("supplement_taxonomy") or {}
        primary_type = norm_text(taxonomy.get("primary_type"))
        if primary_type:
            return primary_type

        # Pre-taxonomy products (no supplement_taxonomy field at all)
        st = product.get("supplement_type", {})
        if isinstance(st, str):
            return norm_text(st) or "unknown"
        if isinstance(st, dict):
            return norm_text(st.get("type")) or "unknown"
        return "unknown"

    def _scoring_input(self, product: Dict[str, Any]):
        return get_scoring_ingredients(product, strict=True, allow_legacy_fallback=False)

    def _unmapped_active_names(self, product: Dict[str, Any]) -> List[str]:
        return self._scoring_input(product).unmapped_actives

    def _banned_exact_alias_name_keys(self, product: Dict[str, Any]) -> set[str]:
        names: set[str] = set()
        substances = safe_list(
            product.get("contaminant_data", {})
            .get("banned_substances", {})
            .get("substances", [])
        )
        for substance in substances:
            match_type = self._normalize_match_type(
                substance.get("match_type") or substance.get("match_method")
            )
            if match_type not in {"exact", "alias"}:
                continue
            for field in ("ingredient", "banned_name", "matched_variant", "name"):
                key = canon_key(substance.get(field))
                if key:
                    names.add(key)
        return names

    def _split_unmapped_kpis(self, product: Dict[str, Any]) -> Dict[str, Any]:
        unmapped_all = self._unmapped_active_names(product)
        banned_exact_alias_keys = self._banned_exact_alias_name_keys(product)

        banned_exact_alias_unmapped = [
            name for name in unmapped_all if canon_key(name) in banned_exact_alias_keys
        ]
        unmapped_excluding_banned = [
            name for name in unmapped_all if canon_key(name) not in banned_exact_alias_keys
        ]

        return {
            "unmapped_actives_all": unmapped_all,
            "unmapped_actives_excluding_banned_exact_alias": unmapped_excluding_banned,
            "unmapped_actives_banned_exact_alias": banned_exact_alias_unmapped,
        }

    def _has_standardized_botanical_anchor(self, product: Dict[str, Any]) -> bool:
        """Track A.1 strict eligibility check.

        Returns True iff:
          1. ingredient_quality_data.ingredients_scorable is empty
          2. formulation_data.standardized_botanicals has at least one
             meets_threshold=True entry
          3. At least one row in the active panel carries a real dose
             (quantity > 0, unit not in ANCHOR_NON_DOSE_UNITS) AND
             identity-matches a meets_threshold botanical via one of:
               a. row.canonical_source_db == "standardized_botanicals", OR
               b. row.canonical_id exactly matches a non-empty anchor canonical_id, OR
               c. row.standard_name exactly matches a non-empty anchor std_name, OR
               d. row.name exactly matches a non-empty anchor name

        Strict equality (after norm_text) — NOT token intersection — so shared
        generic words ("extract", "root", "complex", "blend", "oil") do not
        produce false positives. See test
        test_anchor_identity_match_is_strict_not_token_intersection.

        Spec: reports/not_scored_triage/track_A1_standardized_botanical_anchor_spec.md
        """
        iqd = product.get("ingredient_quality_data") or {}
        if iqd.get("ingredients_scorable"):
            return False

        formulation = product.get("formulation_data") or {}
        std_bots = formulation.get("standardized_botanicals") or []

        anchor_names: set[str] = set()
        anchor_std_names: set[str] = set()
        anchor_canon_ids: set[str] = set()
        for sb in std_bots:
            if not isinstance(sb, dict) or sb.get("meets_threshold") is not True:
                continue
            n = norm_text(sb.get("name") or "")
            if n:
                anchor_names.add(n)
            s = norm_text(sb.get("standard_name") or "")
            if s:
                anchor_std_names.add(s)
            c = norm_text(sb.get("canonical_id") or "")
            if c:
                anchor_canon_ids.add(c)
        if not (anchor_names or anchor_std_names or anchor_canon_ids):
            return False

        active_rows = (
            safe_list(iqd.get("ingredients_skipped"))
            + safe_list(iqd.get("ingredients"))
            + safe_list(iqd.get("ingredients_recognized_non_scorable"))
        )
        for row in active_rows:
            if not isinstance(row, dict):
                continue
            q = row.get("quantity")
            try:
                qf = float(q) if q is not None else 0.0
            except (TypeError, ValueError):
                qf = 0.0
            if qf <= 0:
                continue
            unit_norm = norm_text(row.get("unit") or "")
            if unit_norm in ANCHOR_NON_DOSE_UNITS:
                continue
            # identity match — strict exact, no token intersection
            if norm_text(row.get("canonical_source_db") or "") == "standardized_botanicals":
                return True
            row_canon = norm_text(row.get("canonical_id") or "")
            if row_canon and row_canon in anchor_canon_ids:
                return True
            row_std = norm_text(row.get("standard_name") or "")
            if row_std and row_std in anchor_std_names:
                return True
            row_name = norm_text(row.get("name") or "")
            if row_name and row_name in anchor_names:
                return True

        return False

    @staticmethod
    def _row_has_usable_anchor_dose(row: Dict[str, Any]) -> bool:
        q = row.get("quantity")
        try:
            qf = float(q) if q is not None else 0.0
        except (TypeError, ValueError):
            qf = 0.0
        if qf <= 0:
            return False
        return norm_text(row.get("unit") or "") not in ANCHOR_NON_DOSE_UNITS

    @staticmethod
    def _proprietary_child_has_usable_dose(child: Dict[str, Any]) -> bool:
        amount = child.get("amount")
        try:
            qf = float(amount) if amount is not None else 0.0
        except (TypeError, ValueError):
            qf = 0.0
        if qf <= 0:
            return False
        return norm_text(child.get("unit") or "") not in ANCHOR_NON_DOSE_UNITS

    def _has_dosed_proprietary_blend_children(self, product: Dict[str, Any]) -> bool:
        """Return True if blend detector evidence exposes individually dosed children.

        A.2 anchors are only for total-dose headers whose children are hidden
        or display-only.  Some DSLD rows carry child activity units inside
        proprietary_blends evidence rather than ingredient_quality_data; this
        guard keeps those future/current cases from being header-credited.
        """
        for blend in safe_list(product.get("proprietary_blends")):
            if not isinstance(blend, dict):
                continue
            for child in safe_list(blend.get("child_ingredients")):
                if isinstance(child, dict) and self._proprietary_child_has_usable_dose(child):
                    return True
        return False

    def _row_matches_curated_branded_blend_anchor(self, row: Dict[str, Any]) -> bool:
        """Exact-match curated branded-blend override check."""
        if not self._branded_blend_anchors:
            return False

        names = {
            norm_text(row.get("name") or ""),
            norm_text(row.get("standard_name") or ""),
        }
        names.discard("")
        if not names:
            return False

        src_db = norm_text(row.get("canonical_source_db") or "")
        cid = norm_text(row.get("canonical_id") or "")
        for anchor in self._branded_blend_anchors:
            aliases = anchor.get("aliases") or set()
            if not (names & aliases):
                continue

            allowed_source_dbs = anchor.get("allowed_source_dbs") or set()
            if allowed_source_dbs and src_db not in allowed_source_dbs:
                continue

            allowed_canonical_ids = anchor.get("allowed_canonical_ids") or set()
            if allowed_canonical_ids and cid not in allowed_canonical_ids:
                continue

            return True
        return False

    def _has_blend_header_anchor(self, product: Dict[str, Any]) -> bool:
        """Track A.2a strict eligibility check.

        Returns True iff:
          1. ingredient_quality_data.ingredients_scorable is empty
          2. Track A.1 standardized-botanical-anchor does NOT fire (A.1 wins)
          3. At least one blend_header row in ingredients_skipped satisfies:
              * is_blend_header / blend_total_weight_only / score_exclusion_reason=='blend_header_total'
              * quantity > 0, unit not in ANCHOR_NON_DOSE_UNITS
              * either:
                - a curated branded-blend override exact-matches row name /
                  standard_name with verified evidence, OR
                - canonical_id is non-empty, NOT starting with 'BLEND_' or
                  'PII_', NOT in BLEND_HEADER_ANCHOR_CANONICAL_DENYLIST, and
                  canonical_source_db is in BLEND_HEADER_ANCHOR_ALLOWED_DBS
                  (ingredient_quality_map or botanical_ingredients)

        Spec: reports/not_scored_triage/track_A2_blend_header_anchor_spec.md
        """
        iqd = product.get("ingredient_quality_data") or {}
        if iqd.get("ingredients_scorable"):
            return False
        # Track A.1 precedence — if the standardized-botanical anchor would
        # fire, that path wins and this one stands down.
        if self._has_standardized_botanical_anchor(product):
            return False
        if self._has_dosed_proprietary_blend_children(product):
            return False

        # Wave 6.Z A.2b child-dose guard — if any non-header skipped row
        # carries a usable individual dose (quantity > 0 with a real mass
        # unit), the blend has disclosed children. Score the children, not
        # the header — otherwise we double-count or invent precision.
        #
        # This is conservative (product-wide, no parentBlend linkage check)
        # because the contract we care about is simpler and safer: if the
        # product has no strict scorable rows yet does have any dosed
        # non-header skipped component, the header should not get anchor
        # credit. None of the 10 corpus A.2b candidates today match this
        # shape (all nested children are display-only qty=0/NP), but the
        # guard is required to keep every future blend-header anchor slice
        # safe at 100K+ products.
        for row in safe_list(iqd.get("ingredients_skipped")):
            if not isinstance(row, dict):
                continue
            is_header = (
                bool(row.get("is_blend_header"))
                or bool(row.get("blend_total_weight_only"))
                or row.get("score_exclusion_reason") == "blend_header_total"
            )
            if is_header:
                continue
            if self._row_has_usable_anchor_dose(row):
                return False

        for row in safe_list(iqd.get("ingredients_skipped")):
            if not isinstance(row, dict):
                continue
            # must be a blend header
            is_header = (
                bool(row.get("is_blend_header"))
                or bool(row.get("blend_total_weight_only"))
                or row.get("score_exclusion_reason") == "blend_header_total"
            )
            if not is_header:
                continue
            # dose check
            if not self._row_has_usable_anchor_dose(row):
                continue
            if self._row_matches_curated_branded_blend_anchor(row):
                return True
            # canonical_id checks (strict)
            cid_raw = (row.get("canonical_id") or "").strip()
            if not cid_raw:
                continue
            cid_lower = cid_raw.lower()
            if cid_lower.startswith("blend_") or cid_lower.startswith("pii_"):
                continue
            if cid_lower in BLEND_HEADER_ANCHOR_CANONICAL_DENYLIST:
                continue
            # source DB allowlist
            src_db = norm_text(row.get("canonical_source_db") or "")
            if src_db not in BLEND_HEADER_ANCHOR_ALLOWED_DBS:
                continue
            return True

        return False

    def _not_scorable_evidence_rows(self, product: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return de-duplicated rows that explain a zero-strict-scorable product."""
        iqd = product.get("ingredient_quality_data") or {}
        rows: List[Dict[str, Any]] = []
        seen: set[Tuple[Any, ...]] = set()
        for bucket_name in ("ingredients_skipped", "ingredients_recognized_non_scorable"):
            for row in safe_list(iqd.get(bucket_name)):
                if not isinstance(row, dict):
                    continue
                key = (
                    row.get("name"),
                    row.get("standard_name"),
                    row.get("canonical_id"),
                    row.get("quantity"),
                    row.get("unit"),
                    row.get("skip_reason"),
                    row.get("recognition_reason"),
                )
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
        return rows

    def _specific_not_scorable_reason(self, product: Dict[str, Any]) -> Optional[str]:
        """Classify known fail-closed NOT_SCORED shapes without changing scoring.

        This only names patterns already evidenced by explicit enrichment fields.
        Ambiguous botanical or blend scoring-anchor gaps keep the generic strict
        contract reason until their own scoring-design slices land.
        """
        rows = self._not_scorable_evidence_rows(product)
        if not rows:
            return None

        def haystack(row: Dict[str, Any]) -> str:
            fields = (
                row.get("skip_reason"),
                row.get("score_exclusion_reason"),
                row.get("recognition_source"),
                row.get("recognition_reason"),
                row.get("recognition_type"),
                row.get("demotion_reason"),
                row.get("canonical_source_db"),
                row.get("category"),
                row.get("name"),
                row.get("standard_name"),
            )
            return " ".join(norm_text(v) for v in fields if v is not None)

        row_texts = [haystack(row) for row in rows]

        has_blend_header = any(
            "blend_header_total" in text
            or "blend_header_total_weight_only" in text
            or bool(row.get("is_blend_header"))
            or bool(row.get("blend_total_weight_only"))
            for row, text in zip(rows, row_texts)
        )
        has_absorption_enhancer = any(
            "absorption_enhancer_sub_threshold" in text
            for text in row_texts
        )
        if has_blend_header and has_absorption_enhancer:
            return "blend_header_primary_with_absorption_enhancer_only"

        if all("absorption_enhancer_sub_threshold" in text for text in row_texts):
            return "absorption_enhancer_sub_threshold_only"

        has_carrier_oil = any("carrier_oil" in text for text in row_texts)
        if has_carrier_oil and all(
            ("carrier_oil" in text)
            or ("excluded_nutrition_fact" in text)
            or ("nutrition_fact" in text)
            for text in row_texts
        ):
            return "carrier_oil_only"

        if all(
            ("banned" in text)
            or ("banned_recalled" in text)
            or ("recalled" in text)
            for text in row_texts
        ):
            return "safety_flagged_substance_only"

        if all(
            ("excipient" in text)
            or ("known_excipient" in text)
            for text in row_texts
        ):
            return "excipient_only_no_active"

        # ── Step 3b: expanded reporting-only vocab ─────────────────────────
        # No scoring change; the verdict is still NOT_SCORED. These reasons
        # refine the 440-product residual that previously fell into
        # 'strict_contract_all_candidates_rejected'. Precedence rationale
        # documented in test_not_scored_truthful_diagnostics.py
        # TestStep3bExpandedReasonVocab.

        # 3b.1 — standardized botanical anchor (product-level, highest signal).
        # Wave-6 "Standardized Botanical Anchor" scoring slice target.
        formulation = product.get("formulation_data") or {}
        std_bots = formulation.get("standardized_botanicals") or []
        if any(
            isinstance(sb, dict) and sb.get("meets_threshold") is True
            for sb in std_bots
        ):
            return "standardized_botanical_no_scorable_anchor"

        # 3b.2 — source DB explicitly marked the row as needing IQM relocation.
        # Small-IQM-batch candidate.
        if any(
            row.get("recognition_reason") == "active_pending_relocation"
            for row in rows
        ):
            return "active_pending_relocation_iqm_gap"

        # 3b.3 — Tocotrienols 50 mg / 203189 pattern. Product name carries the
        # dose, label row has unit=NP.
        if any(
            row.get("skip_reason") == "blend_header_without_dosage"
            or "blend_header_without_dosage" in text
            for row, text in zip(rows, row_texts)
        ):
            return "blend_dose_in_product_name_only"

        # 3b.4 — Glucomannan / Fiber Fusion / Whey Protein: macro/nutrition
        # fact rollups. Some labels also carry a structural blend header and
        # undosed display-only children describing the fiber/collagen blend.
        # Those rows are not recoverable bioactive anchors; the truthful
        # diagnostic remains macro_only_product.
        def _is_macro_row(text: str) -> bool:
            return ("excluded_nutrition_fact" in text) or ("nutrition_fact" in text)

        def _is_structural_blend_context(row: Dict[str, Any], text: str) -> bool:
            if (
                bool(row.get("is_blend_header"))
                or bool(row.get("blend_total_weight_only"))
                or "blend_header_total" in text
            ):
                return True
            if (
                "nested_under_non_therapeutic_parent" in text
                or "nested_display_only" in text
            ):
                q = row.get("quantity")
                try:
                    qf = float(q) if q is not None else 0
                except (TypeError, ValueError):
                    qf = 0
                unit_norm = norm_text(row.get("unit") or row.get("unit_normalized") or "")
                return qf <= 0 or unit_norm in {"", "np", "n/a", "na", "none", "0", "unspecified"}
            return False

        if any(_is_macro_row(text) for text in row_texts) and all(
            _is_macro_row(text) or _is_structural_blend_context(row, text)
            for row, text in zip(rows, row_texts)
        ):
            return "macro_only_product"

        # 3b.5 / 3b.6 — blend header with vs without identity.
        # A header carrying a real canonical_id / standard_name (e.g.
        # "Turmeric") is a Bucket-A scoring-slice target. A generic
        # "Proprietary Blend" header without identity is genuinely opaque.
        GENERIC_BLEND_NAMES = {
            "",
            "proprietary blend",
            "blend",
            "complex",
            "matrix",
            "formula",
            "proprietary",
        }

        def _is_header(row: Dict[str, Any], text: str) -> bool:
            return (
                bool(row.get("is_blend_header"))
                or bool(row.get("blend_total_weight_only"))
                or "blend_header_total" in text
            )

        if any(_is_header(r, t) for r, t in zip(rows, row_texts)):
            for row, text in zip(rows, row_texts):
                if not _is_header(row, text):
                    continue
                canon = norm_text(row.get("canonical_id") or "")
                std = norm_text(row.get("standard_name") or "")
                if canon:
                    return "blend_header_primary_active_not_scored"
                if std and std not in GENERIC_BLEND_NAMES:
                    return "blend_header_primary_active_not_scored"
            return "blend_total_no_scorable_identity"

        # 3b.7 — every row is recognized as a plant by part (root/leaf/herb/…)
        # via botanical_ingredients or standardized_botanicals, without IQM
        # rule and without meets_threshold (the anchor case is handled above).
        # Wave-6 plain-botanical scoring-design candidate.
        def _is_botanical(row: Dict[str, Any]) -> bool:
            src = norm_text(row.get("recognition_source") or "")
            db = norm_text(row.get("canonical_source_db") or "")
            return (
                "botanical_ingredients" in src
                or "standardized_botanicals" in src
                or "botanical_ingredients" in db
                or "standardized_botanicals" in db
            )

        if all(_is_botanical(row) for row in rows):
            return "plain_botanical_no_iqm_rule"

        # 3b.8 — gummy multivit pattern. Every row has no usable dose
        # (qty <= 0 or unit in {NP, unspecified, n/a, none, ""}).
        NON_DOSE_UNITS = {"", "np", "n/a", "na", "none", "0", "unspecified"}

        def _row_has_no_dose(row: Dict[str, Any]) -> bool:
            q = row.get("quantity")
            try:
                qf = float(q) if q is not None else 0
            except (TypeError, ValueError):
                qf = 0
            unit_norm = norm_text(row.get("unit") or row.get("unit_normalized") or "")
            return qf <= 0 or unit_norm in NON_DOSE_UNITS

        if all(_row_has_no_dose(row) for row in rows):
            return "label_dose_not_declared"

        return None

    def _mapping_gate(self, product: Dict[str, Any]) -> Dict[str, Any]:
        scoring_input = self._scoring_input(product)
        kpis = self._split_unmapped_kpis(product)
        unmapped_all_candidates = kpis["unmapped_actives_all"]
        unmapped_excluding_candidates = kpis["unmapped_actives_excluding_banned_exact_alias"]
        unmapped_banned_exact_alias_candidates = kpis["unmapped_actives_banned_exact_alias"]

        # Derive mapping-gate counts from gate-eligible ingredient rows, not legacy enrichment counters.
        # This prevents structural blend containers from silently blocking scoring.
        unmapped_banned_exact_alias = list(unmapped_banned_exact_alias_candidates)
        unmapped_excluding_banned = list(unmapped_excluding_candidates)
        unmapped_count_raw = len(unmapped_all_candidates)
        unmapped_count_excluding_banned = len(unmapped_excluding_banned)
        active_total = scoring_input.mapped_count + unmapped_count_excluding_banned

        if active_total <= 0:
            # Track A.1 — Standardized Botanical Anchor short-circuit.
            # Before tripping the gate, check whether this product qualifies
            # for the conservative anchor scoring path. If so: return
            # stop=False, letting the sections run (A1/A2/A6 naturally compute
            # 0 with empty ingredients_scorable; A5b credits the standardized
            # botanical; B/C/D read product-level signals). The cap and verdict
            # ceiling are applied downstream in score_product / _derive_verdict.
            if self._has_standardized_botanical_anchor(product):
                return {
                    "stop": False,
                    "reason": None,
                    "not_scorable_reason": None,
                    "mapped_coverage": scoring_input.mapped_coverage or 0.0,
                    "unmapped_actives": [],
                    "unmapped_actives_total": 0,
                    "unmapped_actives_excluding_banned_exact_alias": 0,
                    "unmapped_actives_banned_exact_alias": [],
                    "flags": [FLAG_STANDARDIZED_BOTANICAL_ANCHOR],
                    "scoring_input_contract": scoring_input.diagnostics(),
                    "standardized_botanical_anchor": True,
                }

            # Track A.2a — Bucket A blend-header anchor (narrow). Lower
            # precedence than A.1: only fires if A.1 didn't. Same conservative
            # pattern (let sections compute → A1 stays 0 via blend-skip → cap
            # at 60/100 → verdict ceiling CAUTION).
            if self._has_blend_header_anchor(product):
                return {
                    "stop": False,
                    "reason": None,
                    "not_scorable_reason": None,
                    "mapped_coverage": scoring_input.mapped_coverage or 0.0,
                    "unmapped_actives": [],
                    "unmapped_actives_total": 0,
                    "unmapped_actives_excluding_banned_exact_alias": 0,
                    "unmapped_actives_banned_exact_alias": [],
                    "flags": [FLAG_BLEND_HEADER_ANCHOR],
                    "scoring_input_contract": scoring_input.diagnostics(),
                    "blend_header_anchor": True,
                }

            # Distinguish "no actives at all" (DSLD authoring gap) from "enricher
            # saw actives but the strict scoring contract rejected them all"
            # (the dominant 460-of-470 corpus pattern as of 2026-05-23). The
            # legacy NO_ACTIVES_DETECTED flag conflated the two and lied to
            # downstream gates. See reports/not_scored_triage/SUMMARY.md.
            iqd = product.get("ingredient_quality_data") or {}
            # Safe coercion: a diagnostic path must never crash a scoring run
            # on a malformed total_active. Any non-numeric / negative value
            # degrades to 0 → emit the safer NO_ACTIVES_DETECTED label.
            raw_total_active = iqd.get("total_active")
            try:
                enriched_active_count = int(float(raw_total_active))
            except (TypeError, ValueError):
                enriched_active_count = 0
            if enriched_active_count < 0:
                enriched_active_count = 0
            if enriched_active_count > 0:
                reason = "NO_STRICT_SCORING_CANDIDATES"
                not_scorable_reason = (
                    self._specific_not_scorable_reason(product)
                    or "strict_contract_all_candidates_rejected"
                )
            else:
                reason = "NO_ACTIVES_DETECTED"
                not_scorable_reason = "no_actives_detected"
            return {
                "stop": True,
                "reason": reason,
                "not_scorable_reason": not_scorable_reason,
                "mapped_coverage": scoring_input.mapped_coverage or 0.0,
                "unmapped_actives": [],
                "unmapped_actives_total": 0,
                "unmapped_actives_excluding_banned_exact_alias": 0,
                "unmapped_actives_banned_exact_alias": [],
                "flags": [reason, "SCORING_INPUT_CONTRACT_GAP"],
                "scoring_input_contract": scoring_input.diagnostics(),
            }

        active_mapped = scoring_input.mapped_count
        mapped_coverage = active_mapped / active_total if active_total else 0.0

        flags: List[str] = []
        if not scoring_input.strict_contract_passed:
            flags.append("SCORING_INPUT_CONTRACT_GAP")
        match_ledger = product.get("match_ledger", {})
        ledger_entries = safe_list(match_ledger.get("domains", {}).get("ingredients", {}).get("entries"))
        has_unmapped_inactive = any(
            (
                "inactive" in norm_text(e.get("raw_source_path"))
                and e.get("decision") in {"unmatched", "rejected"}
            )
            for e in ledger_entries
        )
        if has_unmapped_inactive:
            flags.append("UNMAPPED_INACTIVE_INGREDIENT")

        if self._feature_on("require_full_mapping", default=True) and mapped_coverage < 1.0:
            flags.append("UNMAPPED_ACTIVE_INGREDIENT")
            return {
                "stop": True,
                "reason": "UNMAPPED_ACTIVE_INGREDIENT",
                "mapped_coverage": mapped_coverage,
                "unmapped_actives": unmapped_excluding_banned,
                "unmapped_actives_total": unmapped_count_raw,
                "unmapped_actives_excluding_banned_exact_alias": unmapped_count_excluding_banned,
                "unmapped_actives_banned_exact_alias": unmapped_banned_exact_alias,
                "flags": flags,
                "scoring_input_contract": scoring_input.diagnostics(),
            }

        return {
            "stop": False,
            "reason": None,
            "mapped_coverage": mapped_coverage,
            "unmapped_actives": unmapped_excluding_banned,
            "unmapped_actives_total": unmapped_count_raw,
            "unmapped_actives_excluding_banned_exact_alias": unmapped_count_excluding_banned,
            "unmapped_actives_banned_exact_alias": unmapped_banned_exact_alias,
            "flags": flags,
            "scoring_input_contract": scoring_input.diagnostics(),
        }

    # ---------------------------------------------------------------------
    # B0 immediate fail
    # ---------------------------------------------------------------------

    def _normalize_match_type(self, value: Any) -> str:
        text = norm_text(value)
        if text in {"exact", "alias", "token_bounded"}:
            return text
        if text.startswith("exact"):
            return "exact"
        if "alias" in text:
            return "alias"
        if "token" in text:
            return "token_bounded"
        return text

    def _iter_resolver_safety_hits(self, product: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return banned-recalled hits from the shared resolver.

        The enricher's contaminant_data is still the primary active-path
        signal. This resolver pass closes the product-level gap for inactives
        and direct alias matches that only build_final_db previously saw.
        """
        try:
            resolver = self._get_inactive_resolver()
        except Exception as exc:
            self.logger.warning("Inactive resolver unavailable during scoring: %s", exc)
            return []

        hits: List[Dict[str, Any]] = []
        for source_key, role in (
            ("activeIngredients", "active"),
            ("inactiveIngredients", "inactive"),
        ):
            for ingredient in safe_list(product.get(source_key)):
                if not isinstance(ingredient, dict):
                    continue
                raw_name = (
                    ingredient.get("name")
                    or ingredient.get("raw_source_text")
                    or ingredient.get("standardName")
                )
                if not raw_name:
                    continue
                res = resolver.resolve(
                    raw_name=str(raw_name),
                    standard_name=ingredient.get("standardName"),
                )
                if res.matched_source != "banned_recalled":
                    continue
                if not (res.is_safety_concern or res.is_banned):
                    continue
                hits.append({
                    "name": res.display_label or str(raw_name),
                    "status": res.regulatory_status,
                    "inactive_policy": res.inactive_policy,
                    "role": role,
                    "matched_rule_id": res.matched_rule_id,
                })
        return hits

    @staticmethod
    def _safety_hit_key(name: Any, status: Any) -> tuple[str, str]:
        return (canon_key(name), norm_text(status))

    def _evaluate_safety_gate(self, product: Dict[str, Any]) -> Dict[str, Any]:
        contaminant_data = product.get("contaminant_data") or {}
        banned_substances = contaminant_data.get("banned_substances", {})
        substances = safe_list(banned_substances.get("substances", []))
        canonical_safety_flags = [
            f for f in safe_list(banned_substances.get("safety_flags")) if isinstance(f, dict)
        ]
        for substance in substances:
            if isinstance(substance, dict) and isinstance(substance.get("safety_flag"), dict):
                canonical_safety_flags.append(substance["safety_flag"])

        flags: List[str] = []
        moderate_penalty = 0
        blocked = False
        unsafe = False
        reason = None
        matched_substance_name = None
        review_needed = False
        seen_hits: set[tuple[str, str]] = set()

        for safety_flag in canonical_safety_flags:
            if (
                normalize_safety_source(
                    safety_flag.get("source_db") or safety_flag.get("matched_source")
                )
                != "banned_recalled_ingredients"
            ):
                continue
            match_type = self._normalize_match_type(safety_flag.get("match_type"))
            status = norm_text(safety_flag.get("status"))
            name = (
                safety_flag.get("matched_variant")
                or safety_flag.get("evidence_text")
                or safety_flag.get("entry_id")
                or "unknown"
            )
            seen_hits.add(self._safety_hit_key(name, status))

            if match_type not in {"exact", "alias", "explicit_form_evidence", "legacy_projection"}:
                review_needed = True
                continue

            if safety_flag_matches_status(safety_flag, ("banned",)):
                blocked = True
                reason = f"Banned substance ({name})"
                matched_substance_name = name
            elif safety_flag_matches_status(safety_flag, ("recalled",)):
                unsafe = True
                reason = f"Recalled ingredient ({name})"
                matched_substance_name = name
            elif safety_flag_matches_status(safety_flag, ("high_risk",)):
                b0_cfg = self.config.get(
                    "section_B_safety_purity", {}
                ).get("B0_immediate_fail", {})
                moderate_penalty += as_float(
                    b0_cfg.get("high_risk_penalty"), 10.0
                ) or 10.0
                flags.append("B0_HIGH_RISK_SUBSTANCE")
            elif safety_flag_matches_status(safety_flag, ("watchlist",)):
                b0_cfg = self.config.get(
                    "section_B_safety_purity", {}
                ).get("B0_immediate_fail", {})
                moderate_penalty += as_float(
                    b0_cfg.get("watchlist_penalty"), 5.0
                ) or 5.0
                flags.append("B0_WATCHLIST_SUBSTANCE")

        for substance in substances:
            match_type = self._normalize_match_type(
                substance.get("match_type") or substance.get("match_method")
            )
            status = norm_text(substance.get("status") or substance.get("recall_status"))
            severity = norm_text(substance.get("severity_level"))
            name = (
                substance.get("banned_name")
                or substance.get("ingredient")
                or substance.get("name")
                or "unknown"
            )
            key = self._safety_hit_key(name, status)
            if key in seen_hits:
                continue
            seen_hits.add(key)

            # Interim behavior: non exact/alias hits are review-only.
            if match_type not in {"exact", "alias"}:
                review_needed = True
                continue

            # Status-based logic (v5.0 schema)
            # BLOCKED = banned (harshest: score=None, product must never be shown)
            # UNSAFE = recalled (score=0, shown with strong warning)
            if status == "banned":
                blocked = True
                reason = f"Banned substance ({name})"
                matched_substance_name = name
            elif status == "recalled":
                unsafe = True
                reason = f"Recalled ingredient ({name})"
                matched_substance_name = name
            elif status == "high_risk":
                # L3 (2026-04): penalty magnitude is now config-driven
                # via section_B_safety_purity.B0_immediate_fail.
                # high_risk_penalty. Default 10 preserves pre-refactor
                # behavior.
                b0_cfg = self.config.get(
                    "section_B_safety_purity", {}
                ).get("B0_immediate_fail", {})
                moderate_penalty += as_float(
                    b0_cfg.get("high_risk_penalty"), 10.0
                ) or 10.0
                flags.append("B0_HIGH_RISK_SUBSTANCE")
            elif status == "watchlist":
                # L3 (2026-04): config-driven via
                # section_B_safety_purity.B0_immediate_fail.
                # watchlist_penalty. Default 5 preserves pre-refactor
                # behavior.
                b0_cfg = self.config.get(
                    "section_B_safety_purity", {}
                ).get("B0_immediate_fail", {})
                moderate_penalty += as_float(
                    b0_cfg.get("watchlist_penalty"), 5.0
                ) or 5.0
                flags.append("B0_WATCHLIST_SUBSTANCE")
            else:
                # Fallback for pre-5.0 enriched data (severity-based)
                if severity in {"critical", "high"}:
                    unsafe = True
                    reason = f"Banned/high-risk substance ({name})"
                    matched_substance_name = name
                    break
                elif severity == "moderate":
                    moderate_penalty += 10
                    flags.append("B0_MODERATE_SUBSTANCE")
                elif severity == "low":
                    flags.append("B0_LOW_SUBSTANCE")

        for hit in self._iter_resolver_safety_hits(product):
            status = norm_text(hit.get("status"))
            name = hit.get("name") or "unknown"
            key = self._safety_hit_key(name, status)
            if key in seen_hits:
                continue
            seen_hits.add(key)

            role = norm_text(hit.get("role"))
            inactive_policy = norm_text(hit.get("inactive_policy"))

            if status == "banned":
                blocked = True
                reason = f"Banned substance ({name})"
                matched_substance_name = name
            elif status == "recalled":
                unsafe = True
                reason = f"Recalled ingredient ({name})"
                matched_substance_name = name
            elif status == "high_risk":
                if role == "inactive" and inactive_policy == "excipient_acceptable":
                    flags.append("B0_HIGH_RISK_EXCIPIENT_WARNING_ONLY")
                    continue
                b0_cfg = self.config.get(
                    "section_B_safety_purity", {}
                ).get("B0_immediate_fail", {})
                moderate_penalty += as_float(
                    b0_cfg.get("high_risk_penalty"), 10.0
                ) or 10.0
                flags.append("B0_HIGH_RISK_SUBSTANCE")
            elif status == "watchlist":
                if role == "inactive" and inactive_policy == "excipient_acceptable":
                    flags.append("B0_WATCHLIST_EXCIPIENT_WARNING_ONLY")
                    continue
                b0_cfg = self.config.get(
                    "section_B_safety_purity", {}
                ).get("B0_immediate_fail", {})
                moderate_penalty += as_float(
                    b0_cfg.get("watchlist_penalty"), 5.0
                ) or 5.0
                flags.append("B0_WATCHLIST_SUBSTANCE")

        # If a hard fail was triggered, moderate/low advisory flags are not relevant.
        if blocked or unsafe:
            moderate_penalty = 0
            flags = [f for f in flags if f not in {
                "B0_MODERATE_SUBSTANCE", "B0_LOW_SUBSTANCE",
                "B0_HIGH_RISK_SUBSTANCE", "B0_WATCHLIST_SUBSTANCE"
            }]

        if review_needed and not (blocked or unsafe):
            moderate_penalty += 5
        moderate_penalty = min(moderate_penalty, 25)
        if review_needed:
            flags.append("BANNED_MATCH_REVIEW_NEEDED")

        return {
            "blocked": blocked,
            "unsafe": unsafe,
            "reason": reason,
            "substance": matched_substance_name,
            "moderate_penalty": moderate_penalty,
            "flags": sorted(set(flags)),
        }

    # ---------------------------------------------------------------------
    # Section A
    # ---------------------------------------------------------------------

    def _get_active_ingredients(self, product: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._scoring_input(product).rows

    def _iqd_contract_diagnostics(self, product: Dict[str, Any]) -> Dict[str, Any]:
        diagnostics = self._scoring_input(product).diagnostics()
        diagnostics["ingredients_legacy_count"] = len(
            safe_list(product.get("ingredient_quality_data", {}).get("ingredients"))
        )
        return diagnostics

    def _compute_bioavailability_score(self, product: Dict[str, Any], supp_type: str) -> float:
        ingredients = self._get_active_ingredients(product)
        if not ingredients:
            return 0.0

        # Warn once per scoring run when enriched data pre-dates parent-total dedup
        if (not self._parent_total_warned
                and ingredients
                and "is_parent_total" not in ingredients[0]):
            self.logger.warning(
                "Enriched data missing 'is_parent_total' field — "
                "parent-total dedup inactive. Re-enrich to enable A1/A2 dedup."
            )
            self._parent_total_warned = True

        is_single = supp_type in self._SINGLE_TYPES
        # Pre-compute: count of NON-blend candidates that would otherwise
        # contribute to A1. If any exist, blend parents are excluded
        # (the disclosed children/siblings are the real signal). If NONE
        # exist, the blend parent IS the dose-bearer and must be scored
        # (e.g. Thorne I3C/DIM Complex 200mg — single-row "complex" named
        # ingredient with no children, treated as proprietary by name
        # pattern but is actually the only thing on the label). Without
        # this exemption ~3+ products silently score A=0.
        _non_blend_candidates = sum(
            1 for ing in ingredients
            if not ing.get("is_proprietary_blend")
            and not ing.get("is_parent_total")
            and self._has_usable_individual_dose(ing)
        )

        weighted_values: List[Tuple[float, float]] = []
        for ing in ingredients:
            # Blend containers are opacity signals, not quality signals.
            # Their cost is captured by B5; including them in A1 would
            # double-penalise and pollute the quality average with a
            # meaningless "unspecified form" score of 5.
            #
            # Round 2 fix (2026-04-30): skip blend parent when EITHER
            # (a) there is another non-blend candidate to fall back to, OR
            # (b) the blend parent is not mapped to a real IQM form
            #     (opaque marketing blends with no IQM identity).
            # Only score the blend parent when it IS the sole candidate
            # AND it maps to a known IQM form (e.g., Thorne I3C/DIM Complex
            # 200mg mapped to DIM, or BioCell Collagen Complex mapped to
            # Collagen). This preserves the opacity-blocking intent for
            # genuine black-box blends while restoring legitimate
            # single-row branded actives that happen to be flagged
            # is_proprietary_blend by name pattern.
            if ing.get("is_proprietary_blend") and (
                _non_blend_candidates > 0 or not ing.get("mapped", False)
            ):
                continue
            # Parent nutrient totals are informational rows when nested forms
            # are present; include child forms only to avoid double-counting.
            if ing.get("is_parent_total"):
                continue
            # A1 is dose-anchored quality. Rows without an individual usable
            # dose (common for opaque blend children) do not contribute.
            if not self._has_usable_individual_dose(ing):
                continue
            mapped = bool(ing.get("mapped", False))
            if mapped:
                # v3.6.0: A1 reads pure bio_score (0-15, form quality only).
                # Natural-source bonus moved to A5e where sourcing belongs.
                # The legacy `score` field (= bio_score + 3*natural; 0-18) is
                # accepted as a fallback during the v3.6.x shadow window for
                # blobs enriched by older versions of the pipeline; new blobs
                # emit `score == bio_score` so the fallback yields the same
                # result.
                raw_score = as_float(ing.get("bio_score"), None)
                if raw_score is None:
                    raw_score = as_float(ing.get("score"), None)
                s_i = raw_score if raw_score is not None else 9.0
                raw_weight = as_float(ing.get("dosage_importance"), None)
                w_i = raw_weight if raw_weight is not None else 1.0
            else:
                s_i = 9.0
                w_i = 1.0
            if is_single:
                w_i = 1.0
            weighted_values.append((s_i, w_i))

        denom = sum(w for _, w in weighted_values)
        if denom <= 0:
            return 0.0

        avg_raw = sum(s * w for s, w in weighted_values) / denom
        a1_cfg = self.config.get("section_A_ingredient_quality", {}).get("A1_bioavailability_form", {})
        if supp_type in self._MULTI_TYPES:
            smoothing = as_float(a1_cfg.get("multivitamin_smoothing_factor"), 0.7)
            if smoothing is None or smoothing < 0.0 or smoothing > 1.0:
                smoothing = 0.7
            floor = as_float(a1_cfg.get("multivitamin_floor"), 9.0)
            if floor is None:
                floor = 9.0
            avg_raw = smoothing * avg_raw + (1.0 - smoothing) * floor

        max_points = as_float(
            a1_cfg.get("max"),
            18.0,
        ) or 18.0
        # v3.6.0 default: range_score_field is "0-15" (bio_score scale).
        # A1 budget rescales (avg_bio_score / 15) * 18 to preserve the
        # per-product budget while reading the cleaner field.
        range_score_field = str(a1_cfg.get("range_score_field", "0-15"))
        range_match = re.search(r"(\d+(?:\.\d+)?)\s*$", range_score_field)
        range_max = as_float(range_match.group(1), 15.0) if range_match else 15.0
        if range_max is None or range_max <= 0:
            range_max = 15.0
        return clamp(0.0, max_points, (avg_raw / range_max) * max_points)

    def _compute_premium_forms_bonus(self, product: Dict[str, Any]) -> float:
        a2_cfg = (
            self.config.get("section_A_ingredient_quality", {})
            .get("A2_premium_forms", {})
            or {}
        )
        # v3.6.0: A2 reads pure bio_score (0-15) instead of legacy `score`
        # (which inflated mid-tier natural forms — e.g. food-folate at
        # bio_score=11, score=14 — into the "premium" count). Default
        # threshold dropped 14→12 to match the same percentile on the
        # cleaner field (12 on /15 = 80% = Flutter UI Excellent tier).
        threshold_score = as_float(a2_cfg.get("threshold_score"), 12.0) or 12.0
        points_per_form = as_float(
            a2_cfg.get("points_per_additional_premium_form"), 0.5
        )
        if points_per_form is None:
            points_per_form = 0.5
        a2_max = as_float(a2_cfg.get("max"), 3.0) or 3.0
        skip_first = bool(a2_cfg.get("skip_first_premium_form", True))

        premium_keys = set()
        for ing in self._get_active_ingredients(product):
            # Keep A2 aligned with A1/A6 dose-anchored separation:
            # proprietary blend containers do not receive quality credit.
            if ing.get("is_proprietary_blend"):
                continue
            if ing.get("is_parent_total"):
                continue
            if not self._has_usable_individual_dose(ing):
                continue
            # Read bio_score (form quality, 0-15). Fall back to legacy
            # `score` field for blobs enriched by older pipelines —
            # v3.6.0+ enricher emits score == bio_score so the fallback
            # yields identical results.
            score = as_float(ing.get("bio_score"), None)
            if score is None:
                score = as_float(ing.get("score"), None)
            if score is None:
                continue
            if score >= threshold_score:
                key = canon_key(ing.get("canonical_id") or ing.get("standard_name") or ing.get("name"))
                if key:
                    premium_keys.add(key)

        count_premium = len(premium_keys)
        effective = max(0, count_premium - 1) if skip_first else count_premium
        return clamp(0.0, a2_max, points_per_form * effective)

    def _compute_delivery_score(self, product: Dict[str, Any]) -> float:
        tier = product.get("delivery_tier")
        if tier is None:
            tier = product.get("delivery_data", {}).get("highest_tier")
        tier_int = int(as_float(tier, 0) or 0)
        a3_cfg = (
            self.config.get("section_A_ingredient_quality", {})
            .get("A3_delivery_system", {})
            or {}
        )
        tier_points = a3_cfg.get("tier_points") or {}
        # Config stores tier_points with string keys ("1", "2", "3")
        pts = as_float(
            tier_points.get(str(tier_int), tier_points.get(tier_int)),
            None,
        )
        if pts is None:
            # Fallback to legacy default if config has no tier_points entry
            pts = {1: 3.0, 2: 2.0, 3: 1.0}.get(tier_int, 0.0)
        a3_max = as_float(a3_cfg.get("max"), 3.0) or 3.0
        return clamp(0.0, a3_max, float(pts))

    def _compute_absorption_bonus(self, product: Dict[str, Any]) -> float:
        a4_cfg = (
            self.config.get("section_A_ingredient_quality", {})
            .get("A4_absorption_enhancer", {})
            or {}
        )
        points_if_paired = as_float(a4_cfg.get("points_if_paired"), 3.0) or 3.0
        if "absorption_enhancer_paired" in product:
            return float(points_if_paired) if bool(product.get("absorption_enhancer_paired")) else 0.0
        qualifies = bool(product.get("absorption_data", {}).get("qualifies_for_bonus", False))
        return float(points_if_paired) if qualifies else 0.0

    def _synergy_cluster_qualified(self, product: Dict[str, Any]) -> float:
        """Return the best synergy bonus based on evidence tier.

        Checks all matched synergy clusters. Returns the highest tiered bonus
        from any qualifying cluster (2+ matched ingredients with adequate doses).

        Tier bonuses (from scoring_config.json):
          Tier 1 (PROVEN synergy):       1.0
          Tier 2 (SUPPORTED co-nutrients): 0.75
          Tier 3 (PROMISING):            0.5
          Tier 4 (POPULAR):              0.25

        Returns 0.0 if no cluster qualifies.
        """
        # Legacy boolean override from enricher
        if "synergy_cluster_qualified" in product:
            if bool(product.get("synergy_cluster_qualified")):
                # Legacy path — no tier info, give tier 2 default
                return 0.75
            return 0.0

        # Read tier bonuses from config
        a5_cfg = self.config.get("section_A_ingredient_quality", {}).get(
            "A5_formulation_excellence", {}
        )
        synergy_cfg = a5_cfg.get("synergy_cluster", {})
        if isinstance(synergy_cfg, (int, float)):
            # Old config format (single number) — use as flat bonus
            tier_bonuses = {1: float(synergy_cfg), 2: float(synergy_cfg),
                           3: float(synergy_cfg), 4: float(synergy_cfg)}
        else:
            tier_bonuses = {
                1: as_float(synergy_cfg.get("tier_1_proven"), 1.0),
                2: as_float(synergy_cfg.get("tier_2_supported"), 0.75),
                3: as_float(synergy_cfg.get("tier_3_promising"), 0.5),
                4: as_float(synergy_cfg.get("tier_4_popular"), 0.25),
            }

        best_bonus = 0.0

        clusters = safe_list(product.get("formulation_data", {}).get("synergy_clusters", []))
        for cluster in clusters:
            matched_ingredients = safe_list(cluster.get("matched_ingredients"))
            match_count = int(as_float(cluster.get("match_count"), len(matched_ingredients)) or 0)
            if match_count < 2:
                continue

            checkable = [
                item
                for item in matched_ingredients
                if as_float(item.get("min_effective_dose"), 0.0) and as_float(item.get("min_effective_dose"), 0.0) > 0
            ]
            if not checkable:
                continue

            dosed = [item for item in checkable if bool(item.get("meets_minimum", False))]
            if len(dosed) >= math.ceil(len(checkable) / 2):
                tier = int(as_float(cluster.get("evidence_tier"), 4))
                bonus = tier_bonuses.get(tier, 0.25)
                best_bonus = max(best_bonus, bonus)

        return best_bonus

    def _compute_formulation_bonus(self, product: Dict[str, Any]) -> Dict[str, float]:
        formulation = product.get("formulation_data", {})

        organic_data = formulation.get("organic")
        if isinstance(organic_data, dict):
            is_organic = bool(organic_data.get("usda_verified") or (organic_data.get("claimed") and not organic_data.get("exclusion_matched")))
        else:
            is_organic = bool(organic_data)

        # v3.7.0: tiered, unit-aware, class-capped standardized-botanical bonus
        # (replaces the old binary 0/0.5/1.0). Enrich writes per-item `tier`
        # (full / near_75 / near_50 / identity_only / none) computed unit-aware
        # from marker% vs threshold or branded/marker evidence, plus `bonus_class`.
        # Scorer maps tier -> points via config and caps by class so non-botanicals
        # (minerals, enzymes, isolated compounds) cannot earn the full botanical
        # tier. Best-qualifying ingredient wins (max, not first-match).
        a5_cfg_local = self.config.get("section_A_ingredient_quality", {}).get(
            "A5_formulation_excellence", {}
        )
        std_cfg = a5_cfg_local.get("standardized_botanical", {})
        if isinstance(std_cfg, (int, float)):
            # Legacy flat config — emulate the old binary full-credit behavior.
            _flat = float(std_cfg)
            tier_points = {"full": _flat, "near_75": _flat, "near_50": _flat,
                           "identity_only": _flat, "none": 0.0}
            class_caps = {}
            std_max = _flat
        else:
            tier_points = std_cfg.get("tier_points", {}) or {}
            class_caps = std_cfg.get("class_caps", {}) or {}
            std_max = as_float(std_cfg.get("max"), 4.0)

        def _tier_pts(t: str) -> float:
            return as_float(tier_points.get(t), 0.0)

        std_bonus = 0.0
        std = safe_list(formulation.get("standardized_botanicals", []))
        for item in std:
            if not isinstance(item, dict):
                continue
            tier = item.get("tier")
            if tier is None:
                # Backward-compat: derive tier from legacy meets_threshold/evidence_source.
                if item.get("meets_threshold"):
                    ev = item.get("evidence_source", "")
                    if ev in ("branded_form", "percentage_local", "percentage_context"):
                        tier = "full"
                    elif ev == "marker_word_only":
                        tier = "identity_only"
                    else:
                        tier = "full"
                else:
                    tier = "none"
            pts = _tier_pts(tier)
            bclass = item.get("bonus_class")
            if bclass and bclass in class_caps:
                pts = min(pts, as_float(class_caps.get(bclass), pts))
            std_bonus = max(std_bonus, pts)
        # Fallback: top-level boolean grants identity-only credit when the
        # detailed per-item list is absent (older enriched payloads).
        if std_bonus == 0.0 and bool(product.get("has_standardized_botanical", False)):
            std_bonus = min(_tier_pts("identity_only") or 1.0, std_max)
        std_bonus = min(std_bonus, std_max)

        synergy_bonus = self._synergy_cluster_qualified(product)

        non_gmo_audit = derive_non_gmo_audit(product)
        non_gmo_verified = bool(non_gmo_audit.get("project_verified"))

        a5d = 0.5 if (self._feature_on("enable_non_gmo_bonus", default=True) and non_gmo_verified) else 0.0

        # v3.6.0: A5e natural-source bonus (moved from A1 where it was
        # +3 inflating per-ingredient form/absorption claims). Detection
        # uses majority rule across active scorable ingredients — a
        # single trace ingredient shouldn't earn the badge. Tiebreaker,
        # not tier: +1 in A5 vs the old +3 in A1.
        a5e_cfg = (
            self.config.get("section_A_ingredient_quality", {})
            .get("A5_formulation_excellence", {})
            or {}
        )
        natural_pts = as_float(a5e_cfg.get("natural_source"), 1.0) or 1.0
        natural_count = 0
        scorable_count = 0
        for ing in self._get_active_ingredients(product):
            if ing.get("is_proprietary_blend") or ing.get("is_parent_total"):
                continue
            if not self._has_usable_individual_dose(ing):
                continue
            scorable_count += 1
            if bool(ing.get("natural", False)):
                natural_count += 1
        majority_natural = (
            scorable_count > 0 and natural_count * 2 >= scorable_count
        )
        a5e = float(natural_pts) if majority_natural else 0.0

        return {
            "A5a_organic": 1.0 if is_organic else 0.0,
            "A5b_standardized_botanical": round(std_bonus, 1),
            "A5c_synergy_cluster": round(synergy_bonus, 2),
            "A5d_non_gmo_verified": a5d,
            "A5e_natural_source": a5e,
        }

    def _compute_single_efficiency_bonus(self, product: Dict[str, Any], supp_type: str) -> float:
        a6_cfg = (
            self.config.get("section_A_ingredient_quality", {})
            .get("A6_single_ingredient_efficiency", {})
            or {}
        )
        single_types = set(a6_cfg.get("single_types") or []) | self._SINGLE_TYPES
        if supp_type not in single_types:
            return 0.0

        candidates = []
        for ing in self._get_active_ingredients(product):
            if ing.get("is_proprietary_blend"):
                continue
            if not self._has_usable_individual_dose(ing):
                continue
            candidates.append(ing)

        # A6 is "single-nutrient premium form" — it must require EXACTLY one
        # dosed standalone active, not merely "at least one". A D3+K2 product (2
        # candidates) or a 1-active-plus-disclosed-blend product must not earn it.
        # Mirrors the v4 guard in scoring_v4/modules/generic_formulation.py.
        if len(candidates) != 1:
            return 0.0

        ing = candidates[0]
        # v3.6.0: A6 reads pure bio_score (0-15). Old tiers (>=16/14/12)
        # were calibrated to legacy 0-18 score where 16+ was reachable
        # only via natural-source bonus. New tiers (>=14/12/10 → 3/2/1)
        # preserve granularity within bio_score's achievable range.
        # Falls back to legacy `score` field for blobs from older pipelines.
        form_score = as_float(ing.get("bio_score"), None)
        if form_score is None:
            form_score = as_float(ing.get("score"), None)
        if form_score is None:
            return 0.0

        # Tiers come from config — keys are strings like ">=14", ">=12", ">=10".
        # Parse each "op threshold" key into a (threshold, points) pair and
        # walk them in descending threshold order.
        tiers_cfg = a6_cfg.get("tiers") or {">=14": 3.0, ">=12": 2.0, ">=10": 1.0}
        parsed_tiers: List[Tuple[float, float]] = []
        for key, pts in tiers_cfg.items():
            # Accept ">=N", "N", or bare numeric — default to >= semantics.
            text = str(key).strip()
            num_text = text.lstrip(">=").strip() if text.startswith(">=") else text
            try:
                threshold = float(num_text)
            except ValueError:
                continue
            pts_val = as_float(pts, None)
            if pts_val is None:
                continue
            parsed_tiers.append((threshold, float(pts_val)))
        parsed_tiers.sort(key=lambda kv: kv[0], reverse=True)

        a6_max = as_float(a6_cfg.get("max"), 3.0) or 3.0

        for threshold, pts in parsed_tiers:
            if form_score >= threshold:
                return clamp(0.0, a6_max, pts)
        return 0.0

    @staticmethod
    def _probiotic_bonus_zero(eligibility: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "probiotic_bonus": 0.0,
            "cfu": 0.0,
            "diversity": 0.0,
            "prebiotic": 0.0,
            "clinical_strains": 0.0,
            "survivability": 0.0,
        }
        if eligibility is not None:
            payload["eligibility"] = eligibility
        return payload

    def _non_probiotic_probiotic_gate(
        self,
        product: Dict[str, Any],
        pdata: Dict[str, Any],
        total_billion: float,
        strain_count: int,
        ingredient_names: List[str],
    ) -> Tuple[bool, Dict[str, Any]]:
        cfg = (
            self.config.get("section_A_ingredient_quality", {})
            .get("probiotic_bonus", {})
            .get("non_probiotic_strict_gate", {})
        )

        require_viable_cfu = bool(cfg.get("require_viable_cfu", True))
        min_total_billion = as_float(cfg.get("min_total_billion_count"), 1.0) or 1.0
        require_strain_identity = bool(cfg.get("require_strain_level_identity", True))
        min_clinical_strain_count = int(as_float(cfg.get("min_clinical_strain_count"), 1) or 1)
        min_strain_id_count = int(as_float(cfg.get("min_strain_id_count"), 1) or 1)
        require_cfu_guarantee = bool(cfg.get("require_cfu_guarantee", True))
        accepted_guarantee_types = {
            norm_text(v) for v in safe_list(cfg.get("accepted_guarantee_types", ["at_expiration"])) if norm_text(v)
        }
        require_explicit_intent = bool(cfg.get("require_explicit_intent", True))
        explicit_intent_terms = [
            norm_text(v)
            for v in safe_list(
                cfg.get(
                    "explicit_intent_terms",
                    ["probiotic", "probiotics", "live cultures", "cfu", "gut flora", "microbiome"],
                )
            )
            if norm_text(v)
        ]

        has_viable_cfu = bool(pdata.get("has_cfu")) and total_billion > 0
        meets_dose_context = total_billion >= min_total_billion

        clinical_strain_count = int(as_float(pdata.get("clinical_strain_count"), 0) or 0)
        strain_id_count = int(
            as_float(
                product.get("product_signals", {})
                .get("label_disclosure_signals", {})
                .get("strain_id_count"),
                0,
            )
            or 0
        )
        has_strain_identity = (
            clinical_strain_count >= min_clinical_strain_count
            or strain_id_count >= min_strain_id_count
        )

        guarantee_type = norm_text(pdata.get("guarantee_type"))
        guarantee_ok = (
            (not require_cfu_guarantee)
            or (bool(accepted_guarantee_types) and guarantee_type in accepted_guarantee_types)
        )

        text_parts = [
            product.get("product_name", ""),
            product.get("fullName", ""),
            product.get("labelText", ""),
            " ".join(ingredient_names),
        ]
        explicit_intent = True
        if require_explicit_intent:
            searchable = norm_text(" ".join(str(v) for v in text_parts if v))
            explicit_intent = any(term in searchable for term in explicit_intent_terms)

        checks = {
            "require_viable_cfu": not require_viable_cfu or has_viable_cfu,
            "dose_context": meets_dose_context,
            "strain_identity": (not require_strain_identity) or has_strain_identity,
            "cfu_guarantee": guarantee_ok,
            "explicit_intent": explicit_intent,
        }

        supp_type_payload = product.get("supplement_type", {})
        supp_type_value = (
            supp_type_payload.get("type")
            if isinstance(supp_type_payload, dict)
            else supp_type_payload
        )

        allowed = all(checks.values())
        details = {
            "strict_gate_checks": checks,
            "strict_gate_inputs": {
                "supp_type": norm_text(supp_type_value),
                "is_probiotic_product": bool(pdata.get("is_probiotic_product")),
                "total_billion_count": round(total_billion, 6),
                "total_strain_count": strain_count,
                "clinical_strain_count": clinical_strain_count,
                "strain_id_count": strain_id_count,
                "guarantee_type": guarantee_type or None,
            },
        }
        return allowed, details

    def _should_promote_probiotic_dominant_formula(
        self,
        product: Dict[str, Any],
        pdata: Dict[str, Any],
        ingredient_names: List[str],
        gate_details: Dict[str, Any],
    ) -> bool:
        if not pdata.get("is_probiotic_product"):
            return False

        checks = gate_details.get("strict_gate_checks", {})
        if not (
            checks.get("require_viable_cfu")
            and checks.get("dose_context")
            and checks.get("strain_identity")
        ):
            return False

        probiotic_terms = (
            "probiotic", "lactobacillus", "bifidobacterium",
            "streptococcus", "bacillus", "saccharomyces",
            "limosilactobacillus", "lacticaseibacillus",
        )
        probiotic_like_count = sum(
            1 for ing_name in ingredient_names
            if any(term in ing_name for term in probiotic_terms)
        )
        ingredient_count = max(len([name for name in ingredient_names if name]), 1)
        dominant_formula = probiotic_like_count >= max(2, ingredient_count)

        supp_type_payload = product.get("supplement_type", {})
        active_count = (
            supp_type_payload.get("active_count")
            if isinstance(supp_type_payload, dict)
            else None
        )
        if active_count in (0, None):
            active_count = ingredient_count

        composition_dominant = dominant_formula or probiotic_like_count >= max(2, int(active_count * 0.6))
        explicit_intent = bool(checks.get("explicit_intent"))

        # Promotion exists to prevent silent false negatives when product naming
        # or guarantee metadata is weak but the ingredient composition clearly
        # describes a probiotic-dominant formula.
        return composition_dominant or explicit_intent

    def _compute_probiotic_category_bonus(self, product: Dict[str, Any], supp_type: str) -> Dict[str, float]:
        pro_cfg = self.config.get("section_A_ingredient_quality", {}).get("probiotic_bonus", {})
        pdata = product.get("probiotic_data", {})
        probiotic_flag = bool(pdata.get("is_probiotic_product"))

        ingredients = self._get_active_ingredients(product)
        ingredient_names = [norm_text(i.get("name") or i.get("standard_name") or "") for i in ingredients]

        total_billion = as_float(pdata.get("total_billion_count"), None)
        if total_billion is None:
            total_billion = 0.0
            for blend in safe_list(pdata.get("probiotic_blends")):
                total_billion += as_float(blend.get("cfu_data", {}).get("billion_count"), 0.0) or 0.0

        strain_count = int(as_float(pdata.get("total_strain_count"), 0) or 0)
        if strain_count == 0:
            strains = set()
            for blend in safe_list(pdata.get("probiotic_blends")):
                for strain in safe_list(blend.get("strains")):
                    strains.add(canon_key(strain))
            strain_count = len([s for s in strains if s])

        eligibility: Optional[Dict[str, Any]] = None

        if supp_type not in self._PROBIOTIC_TYPES:
            if not probiotic_flag:
                return self._probiotic_bonus_zero(
                    {
                        "mode": "non_probiotic",
                        "eligible": False,
                        "reason": "no_probiotic_signal",
                    }
                )
            if not self._feature_on("allow_non_probiotic_probiotic_bonus_with_strict_gate", default=True):
                return self._probiotic_bonus_zero(
                    {
                        "mode": "non_probiotic",
                        "eligible": False,
                        "reason": "strict_gate_disabled",
                    }
                )

            allowed, gate_details = self._non_probiotic_probiotic_gate(
                product=product,
                pdata=pdata,
                total_billion=total_billion or 0.0,
                strain_count=strain_count,
                ingredient_names=ingredient_names,
            )
            if not allowed and self._should_promote_probiotic_dominant_formula(
                product=product,
                pdata=pdata,
                ingredient_names=ingredient_names,
                gate_details=gate_details,
            ):
                eligibility = {
                    "mode": "probiotic",
                    "eligible": True,
                    "reason": "promoted_probiotic_dominant",
                    **gate_details,
                }
                allowed = True
            if not allowed:
                return self._probiotic_bonus_zero(
                    {
                        "mode": "non_probiotic",
                        "eligible": False,
                        "reason": "strict_gate_failed",
                        **gate_details,
                    }
                )
            if eligibility is None:
                eligibility = {
                    "mode": "non_probiotic",
                    "eligible": True,
                    "reason": "strict_gate_passed",
                    **gate_details,
                }
        else:
            eligibility = {
                "mode": "probiotic",
                "eligible": True,
                "reason": "supplement_type_probiotic",
            }

        # Prebiotic terms are config-driven so the list can be expanded
        # without code changes. Default fallback covers the three most
        # common short terms; config should carry the full vocabulary.
        prebiotic_terms_cfg = pro_cfg.get("prebiotic_terms")
        if not prebiotic_terms_cfg:
            prebiotic_terms_cfg = [
                "inulin", "fos", "gos", "chicory", "acacia",
                "beta-glucan", "beta glucan", "pea fiber", "lactulose",
                "fructooligosaccharide", "galactooligosaccharide",
                "xos", "xylooligosaccharide", "raftiline", "raftilose",
            ]
        prebiotic_terms_norm = [norm_text(t) for t in prebiotic_terms_cfg if t]
        prebiotic_hits = sum(
            1 for term in prebiotic_terms_norm
            if term and any(term in ing for ing in ingredient_names)
        )
        # Enrichment may detect prebiotics from nested blend children that are not
        # present as top-level scorable ingredients.
        if pdata.get("prebiotic_present"):
            prebiotic_hits = max(prebiotic_hits, 1)

        # Bug C fix: source clinical strains and survivability from the
        # enricher (pdata) rather than hardcoding 0.0 in default mode or
        # using a duplicate hardcoded substring list in extended mode.
        # Single source of truth is clinically_relevant_strains.json, matched
        # by the enricher in _collect_probiotic_data.
        clinical_strain_count = int(as_float(pdata.get("clinical_strain_count"), 0) or 0)
        has_survivability = bool(pdata.get("has_survivability_coating"))

        if self._feature_on("probiotic_extended_scoring", default=False):
            if total_billion >= 50:
                cfu = 4.0
            elif total_billion >= 10:
                cfu = 3.0
            elif total_billion > 1:
                cfu = 2.0
            elif total_billion > 0:
                cfu = 1.0
            else:
                cfu = 0.0

            if strain_count >= 10:
                diversity = 4.0
            elif strain_count >= 6:
                diversity = 3.0
            elif strain_count >= 3:
                diversity = 2.0
            elif strain_count > 0:
                diversity = 1.0
            else:
                diversity = 0.0

            if clinical_strain_count >= 5:
                clinical_strains = 3.0
            elif clinical_strain_count >= 3:
                clinical_strains = 2.0
            elif clinical_strain_count >= 1:
                clinical_strains = 1.0
            else:
                clinical_strains = 0.0

            prebiotic = float(min(3, prebiotic_hits))

            survivability = 2.0 if has_survivability else 0.0

            extended_cap = as_float(pro_cfg.get("extended_max"), 10.0)
            total = min(extended_cap, cfu + diversity + clinical_strains + prebiotic + survivability)
            return {
                "probiotic_bonus": total,
                "cfu": cfu,
                "diversity": diversity,
                "prebiotic": prebiotic,
                "clinical_strains": clinical_strains,
                "survivability": survivability,
                "eligibility": eligibility,
            }

        cfu = 1.0 if total_billion > 1 else 0.0
        diversity = 1.0 if strain_count >= 3 else 0.0
        prebiotic = 1.0 if prebiotic_hits > 0 else 0.0
        clinical_strains = 1.0 if clinical_strain_count >= 1 else 0.0
        survivability = 1.0 if has_survivability else 0.0
        default_cap = as_float(pro_cfg.get("default_max"), 3.0)
        total = min(default_cap, cfu + diversity + prebiotic + clinical_strains + survivability)

        # Sprint E1.3.2.c — per-strain CFU-adequacy uplift (additive,
        # config-gated, independent from the aggregate bonus cap above).
        # Hard gates enforced inside the helper: multi-strain blends and
        # missing-tier strains contribute 0.
        adequacy_cfg = self.config.get("section_A_ingredient_quality", {}).get("probiotic_cfu_adequacy", {})
        adequacy_result = _compute_probiotic_cfu_adequacy_points(
            safe_list(pdata.get("clinical_strains")),
            adequacy_cfg,
        )
        adequacy_points = adequacy_result.get("probiotic_cfu_adequacy_points", 0.0) or 0.0
        total = total + adequacy_points

        return {
            "probiotic_bonus": total,
            "cfu": cfu,
            "diversity": diversity,
            "prebiotic": prebiotic,
            "clinical_strains": clinical_strains,
            "survivability": survivability,
            "eligibility": eligibility,
            "cfu_adequacy_points": adequacy_points,
            "cfu_adequacy_contributions": adequacy_result.get("strain_contributions", []),
        }

    def _compute_omega3_dose_bonus(self, product: Dict[str, Any], flags: List[str]) -> Dict[str, Any]:
        """Omega-3 dose adequacy category bonus (max 2.0).

        Applicable only to products with explicit per-unit EPA and/or DHA amounts.
        Formerly standalone Section E, now a category bonus inside Ingredient Quality.
        """
        a_cfg = self.config.get("section_A_ingredient_quality", {})
        o3_cfg = a_cfg.get("omega3_dose_bonus", {}) or {}

        # Fallback to legacy section_E_dose_adequacy config for backward compat
        if not o3_cfg.get("bands"):
            o3_cfg = self.config.get("section_E_dose_adequacy", {}) or {}

        bonus_max = as_float(o3_cfg.get("max"), 2.0)
        bands = list(o3_cfg.get("bands", []) or [])

        dose_data = self._compute_epa_dha_per_day(product)

        if not dose_data.get("has_explicit_dose"):
            # No EPA/DHA detected. If an opaque omega blend is present,
            # surface the cause (informational only — no score change).
            result = {
                "omega3_dose_bonus": 0.0,
                "applicable": False,
            }
            if self._has_opaque_omega3_blend(product):
                result["bonus_missed_due_to_opacity"] = True
                result["bonus_missed_reason"] = (
                    "EPA/DHA breakdown not disclosed (ingredient appears in a "
                    "proprietary blend without per-component amounts)."
                )
                if "OMEGA3_BONUS_MISSED_OPAQUE_BLEND" not in flags:
                    flags.append("OMEGA3_BONUS_MISSED_OPAQUE_BLEND")
            return result

        per_day = as_float(dose_data.get("per_day_mid"), 0.0) or 0.0
        bonus_score = 0.0
        dose_band_label = "below_efsa_ai"
        prescription_dose = False

        sorted_bands = sorted(bands, key=lambda b: as_float(b.get("min_mg_day"), 0) or 0, reverse=True)
        for band in sorted_bands:
            threshold = as_float(band.get("min_mg_day"), 0) or 0.0
            if per_day >= threshold:
                bonus_score = min(bonus_max, as_float(band.get("score"), 0.0) or 0.0)
                dose_band_label = band.get("label") or dose_band_label
                band_flag = band.get("flag")
                if band_flag:
                    prescription_dose = True
                    if band_flag not in flags:
                        flags.append(band_flag)
                break

        # Premium-form disclosure check: if EPA/DHA dose is disclosed but
        # the molecular form (rTG/EE/PL/...) is not specified on the label,
        # the scorer cannot award A2 premium-delivery credit. Surface the
        # reason informationally so the UI explains why.
        form_disclosed = self._is_omega3_form_disclosed(product)

        result = {
            "omega3_dose_bonus": round(bonus_score, 2),
            "max": round(bonus_max, 2),
            "applicable": True,
            "dose_band": dose_band_label,
            "per_day_mid_mg": dose_data.get("per_day_mid"),
            "per_day_min_mg": dose_data.get("per_day_min"),
            "per_day_max_mg": dose_data.get("per_day_max"),
            "epa_mg_per_unit": dose_data.get("epa_mg_per_unit"),
            "dha_mg_per_unit": dose_data.get("dha_mg_per_unit"),
            "prescription_dose": prescription_dose,
            "form_disclosed": form_disclosed,
        }
        if not form_disclosed:
            result["a2_no_premium_form_credit_reason"] = (
                "EPA/DHA dose is disclosed, but the omega-3 molecular form "
                "(rTG / re-esterified triglyceride / ethyl ester / phospholipid) "
                "is not specified on the label, so no premium-form credit was awarded."
            )
            if "OMEGA3_FORM_NOT_DISCLOSED" not in flags:
                flags.append("OMEGA3_FORM_NOT_DISCLOSED")

        # Partial-disclosure opacity flag (informational, no score change):
        # Some EPA/DHA was labeled but per_day is below the smallest scoring
        # band (250 mg) AND an opaque omega-class blend is present. Catches
        # the "Real Krill" pattern: 63 mg labeled + hidden Antarctic Krill
        # Oil Complex. The B5 transparency penalty already handles the
        # opacity scoring side; this flag only explains WHY the bonus is 0
        # so the UI distinguishes "below threshold" from "below threshold AND
        # undisclosed amounts hidden in opaque blend". We want to be accurate
        # without being harsh on real products — strict trigger so products
        # earning ANY partial credit (efsa_ai_zone 0.5+) do NOT trigger.
        if bonus_score == 0.0 and self._has_opaque_omega3_blend(product):
            result["bonus_missed_due_to_opacity"] = True
            result["bonus_missed_reason"] = (
                "Labeled EPA+DHA below scoring threshold; additional omega-3 "
                "amounts may be in an undisclosed proprietary blend."
            )
            if "OMEGA3_BONUS_MISSED_OPAQUE_BLEND" not in flags:
                flags.append("OMEGA3_BONUS_MISSED_OPAQUE_BLEND")

        return result

    def _build_section_a_zero_diagnostic(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Build diagnostic detail when Section A scores 0.0.

        Returns a dict with:
        - total_active_ingredients: count from enriched data
        - scorable_count: how many made it into ingredients_scorable
        - skipped_ingredients: list of dicts per skipped ingredient with
          name, category, skip_reason, recognition_source, recognition_type,
          is_active, quantity, unit
        - summary: human-readable reason string
        """
        iqd = product.get("ingredient_quality_data", {})
        scorable = safe_list(iqd.get("ingredients_scorable"))
        skipped = safe_list(iqd.get("ingredients_skipped"))
        all_ings = safe_list(iqd.get("ingredients"))

        skipped_detail = []
        for ing in skipped:
            skipped_detail.append({
                "name": ing.get("name", ""),
                "category": ing.get("dsld_category", ing.get("category", "")),
                "skip_reason": ing.get("skip_reason", "unknown"),
                "recognition_source": ing.get("recognition_source", ""),
                "recognition_type": ing.get("recognition_type", ""),
                "is_active": ing.get("source_section") == "active",
                "quantity": ing.get("quantity"),
                "unit": ing.get("unit_normalized", ing.get("unit", "")),
                "is_botanical": "botanical" in (ing.get("recognition_type") or "").lower()
                    or "botanical" in (ing.get("dsld_category") or ing.get("category") or "").lower(),
                "iqm_gap": ing.get("skip_reason") == "recognized_non_scorable"
                    and ing.get("recognition_type") in ("botanical_unscored", "non_scorable"),
            })

        # Also check scorable ingredients that have no usable dose
        no_dose_scorable = []
        for ing in scorable:
            if not self._has_usable_individual_dose(ing):
                no_dose_scorable.append({
                    "name": ing.get("name", ""),
                    "quantity": ing.get("quantity"),
                    "unit": ing.get("unit_normalized", ing.get("unit", "")),
                    "reason": "no_usable_individual_dose",
                })

        # Build summary
        reasons = {}
        for s in skipped_detail:
            r = s["skip_reason"]
            reasons[r] = reasons.get(r, 0) + 1
        reason_parts = [f"{cnt} {reason}" for reason, cnt in sorted(reasons.items(), key=lambda x: -x[1])]
        summary = f"{len(scorable)} scorable, {len(skipped)} skipped"
        if reason_parts:
            summary += f" ({', '.join(reason_parts)})"
        if no_dose_scorable:
            summary += f", {len(no_dose_scorable)} scorable but no usable dose"

        return {
            "total_active_ingredients": iqd.get("total_active", len(all_ings)),
            "scorable_count": len(scorable),
            "skipped_count": len(skipped),
            "no_dose_scorable_count": len(no_dose_scorable),
            "skipped_ingredients": skipped_detail,
            "no_dose_scorable": no_dose_scorable,
            "summary": summary,
        }

    def _compute_ingredient_quality_score(self, product: Dict[str, Any], supp_type: str,
                         flags: Optional[List[str]] = None) -> Dict[str, Any]:
        a_cfg = self.config.get("section_A_ingredient_quality", {})
        section_max = self._section_max("a", 25.0)
        a1 = self._compute_bioavailability_score(product, supp_type)
        a2 = self._compute_premium_forms_bonus(product)
        a3 = self._compute_delivery_score(product)
        a4 = self._compute_absorption_bonus(product)
        a5_parts = self._compute_formulation_bonus(product)
        # v3.6.0: A5.max raised 3→4 to absorb new A5e_natural_source signal
        # (moved from A1). Default updated to match new config.
        a5_cap = as_float(a_cfg.get("A5_formulation_excellence", {}).get("max"), 4.0)
        a5 = min(a5_cap, sum(a5_parts.values()))
        a6 = self._compute_single_efficiency_bonus(product, supp_type)
        probiotic = self._compute_probiotic_category_bonus(product, supp_type)
        probiotic_bonus = probiotic["probiotic_bonus"]

        # Category bonus pool: bonuses enhance, not define quality.
        # Core quality components always dominate.
        omega3_result = self._compute_omega3_dose_bonus(product, flags if flags is not None else [])
        omega3_bonus = omega3_result["omega3_dose_bonus"]

        # Sprint E1.3.4 — enzyme recognition credit.
        enzyme_cfg = a_cfg.get("enzyme_recognition", {}) or {}
        enzyme_result = _compute_enzyme_recognition_bonus(
            self._get_active_ingredients(product), enzyme_cfg,
        )
        enzyme_bonus = enzyme_result.get("enzyme_recognition_points", 0.0) or 0.0

        pool_cfg = a_cfg.get("category_bonus_pool", {})
        max_bonus_contribution = as_float(pool_cfg.get("max_contribution"), 5.0)
        category_bonus_total = min(
            max_bonus_contribution,
            probiotic_bonus + omega3_bonus + enzyme_bonus,
        )

        core_quality = a1 + a2 + a3 + a4 + a5 + a6
        total = min(section_max, core_quality + category_bonus_total)
        return {
            "score": round(total, 2),
            "max": round(section_max, 2),
            "core_quality": round(core_quality, 2),
            "category_bonus_total": round(category_bonus_total, 2),
            "category_bonus_pool_cap": round(max_bonus_contribution, 2),
            "A1": round(a1, 2),
            "A2": round(a2, 2),
            "A3": round(a3, 2),
            "A4": round(a4, 2),
            "A5": round(a5, 2),
            "A5a": round(a5_parts["A5a_organic"], 2),
            "A5b": round(a5_parts["A5b_standardized_botanical"], 2),
            "A5c": round(a5_parts["A5c_synergy_cluster"], 2),
            "A5d": round(a5_parts.get("A5d_non_gmo_verified", 0.0), 2),
            "A5e": round(a5_parts.get("A5e_natural_source", 0.0), 2),
            "A6": round(a6, 2),
            "probiotic_bonus": round(probiotic_bonus, 2),
            "probiotic_breakdown": probiotic,
            "omega3_dose_bonus": round(omega3_bonus, 2),
            "omega3_breakdown": omega3_result,
        }

    # ---------------------------------------------------------------------
    # Section B
    # ---------------------------------------------------------------------

    def _compute_harmful_additives_penalty(
        self,
        product: Dict[str, Any],
        b_cfg: Dict[str, Any] = None,
        flags: Optional[List[str]] = None,
        evidence: Optional[List[Dict[str, Any]]] = None,
    ) -> float:
        if b_cfg is None:
            b_cfg = self.config.get("section_B_safety_purity", {})
        b1_cfg = b_cfg.get("B1_harmful_additives", {})
        additives = safe_list(
            product.get("contaminant_data", {})
            .get("harmful_additives", {})
            .get("additives", product.get("harmful_additives", []))
        )
        risk_map = {"critical": 3.0, "high": 2.0, "moderate": 1.0, "low": 0.5, "none": 0.0}
        config_risk = b1_cfg.get("risk_points", {})
        if isinstance(config_risk, dict):
            for key, value in config_risk.items():
                numeric = as_float(value, None)
                if numeric is not None:
                    risk_map[norm_text(key)] = numeric
        # Deduplicate by additive_id — keep highest severity penalty per ID.
        # Context-aware routing: skip precautionary (low/moderate) penalties
        # for ingredients sourced from the Supplement Facts (active) panel.
        # Active-source ingredients are already quality-scored via IQM;
        # applying an additive penalty on top would double-count.  High and
        # critical severity still fire for actives (genuine safety concern
        # overrides section context — e.g., chronic senna risk).
        seen_ids: Dict[str, float] = {}
        # Per-additive applied severity tier (post-exemption), keyed by additive id.
        # build_final_db reads this to color the 'Other ingredients' dot by the
        # penalty B1 ACTUALLY applied (display_tone) rather than file severity —
        # an exempted/unmatched additive is absent here, so its dot reads green.
        applied_tier: Dict[str, str] = {}
        for item in additives:
            source = item.get("source_section", "unknown")
            sev_text = norm_text(item.get("severity_level"))
            if source == "active" and sev_text in ("low", "moderate"):
                continue  # suppress — IQM quality score is the correct signal
            aid = item.get("additive_id") or item.get("id") or f"_anon_{id(item)}"
            sev = risk_map.get(sev_text, 0.0)
            if sev > seen_ids.get(aid, 0.0):
                applied_tier[aid] = sev_text
            seen_ids[aid] = max(seen_ids.get(aid, 0.0), sev)
        named_penalty = sum(seen_ids.values())
        if isinstance(product, dict):
            product["_inactive_b1_applied_tier"] = applied_tier
        b1_cap = as_float(b1_cfg.get("cap"), 8.0)

        # --- Dietary sugar level penalty (layered on top of named-sweetener penalty) ---
        sugar_cfg = b_cfg.get("B1_dietary_sugar_penalty", {})
        sugar_enabled = sugar_cfg.get("enabled", True)
        sugar_level_penalty = 0.0
        if sugar_enabled:
            moderate_pts = as_float(sugar_cfg.get("moderate_penalty"), 0.5)
            high_pts = as_float(sugar_cfg.get("high_penalty"), 1.5)
            sugar_cap = as_float(sugar_cfg.get("cap"), 1.5)
            if moderate_pts is None:
                moderate_pts = 0.5
            if high_pts is None:
                high_pts = 1.5
            if sugar_cap is None:
                sugar_cap = 1.5

            sugar_data = (
                product.get("dietary_sensitivity_data", {}) or {}
            ).get("sugar", {}) or {}
            sugar_level = norm_text(sugar_data.get("level", ""))
            amount_g = as_float(sugar_data.get("amount_g"), 0.0) or 0.0

            if sugar_level == "moderate":
                sugar_level_penalty = clamp(0.0, sugar_cap, moderate_pts)
                if flags is not None and "SUGAR_LEVEL_MODERATE" not in flags:
                    flags.append("SUGAR_LEVEL_MODERATE")
                if evidence is not None:
                    evidence.append({
                        "type": "dietary_sugar",
                        "level": "moderate",
                        "amount_g": amount_g,
                        "penalty": sugar_level_penalty,
                    })
            elif sugar_level == "high":
                sugar_level_penalty = clamp(0.0, sugar_cap, high_pts)
                if flags is not None and "SUGAR_LEVEL_HIGH" not in flags:
                    flags.append("SUGAR_LEVEL_HIGH")
                if evidence is not None:
                    evidence.append({
                        "type": "dietary_sugar",
                        "level": "high",
                        "amount_g": amount_g,
                        "penalty": sugar_level_penalty,
                    })

        penalty = named_penalty + sugar_level_penalty
        return clamp(0.0, b1_cap, penalty)

    # Fallback tokens used if cert_claim_rules.json is missing or has no
    # product_scope field. Kept as a safety net only — the authoritative list
    # is the data file's third_party_programs entries with product_scope="marine".
    _MARINE_CERTS_FALLBACK: frozenset[str] = frozenset(
        {"ifos", "friend of the sea", "msc", "goed"}
    )

    def _get_marine_cert_tokens(self) -> frozenset[str]:
        """Return a frozenset of normalized token substrings that identify
        marine-scope certifications. Sourced from cert_claim_rules.json
        (third_party_programs entries where product_scope=="marine"), falling
        back to a hardcoded baseline if the data file is missing or unparseable.

        Result is cached on the scorer instance after first call.
        """
        cached = getattr(self, "_marine_cert_tokens_cache", None)
        if cached is not None:
            return cached

        tokens: set[str] = set()
        try:
            import json as _json
            from pathlib import Path as _Path
            rules_path = _Path(__file__).parent / "data" / "cert_claim_rules.json"
            if rules_path.exists():
                with open(rules_path, "r", encoding="utf-8") as fp:
                    data = _json.load(fp)
                programs = (
                    data.get("rules", {})
                    .get("third_party_programs", {})
                )
                for key, entry in programs.items():
                    if key.startswith("_"):
                        continue
                    if not isinstance(entry, dict):
                        continue
                    if norm_text(entry.get("product_scope")) != "marine":
                        continue
                    # Collect any string the cert might appear as on a label.
                    display = norm_text(entry.get("display_name"))
                    if display:
                        tokens.add(display)
                    key_norm = norm_text(key.replace("_", " "))
                    if key_norm:
                        tokens.add(key_norm)
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.warning(
                "Failed to load marine cert scope from cert_claim_rules.json: %s", exc
            )

        if not tokens:
            tokens = set(self._MARINE_CERTS_FALLBACK)

        self._marine_cert_tokens_cache = frozenset(tokens)
        return self._marine_cert_tokens_cache

    def _compute_allergen_penalty(self, product: Dict[str, Any], b_cfg: Dict[str, Any] = None) -> float:
        if b_cfg is None:
            b_cfg = self.config.get("section_B_safety_purity", {})
        b2_cfg = b_cfg.get("B2_allergen_presence", {})
        allergens = safe_list(
            product.get("contaminant_data", {})
            .get("allergens", {})
            .get("allergens", product.get("allergen_hits", []))
        )
        risk_map = {"high": 2.0, "moderate": 1.5, "low": 1.0}
        config_sev = b2_cfg.get("severity_points", {})
        if isinstance(config_sev, dict):
            for key, value in config_sev.items():
                numeric = as_float(value, None)
                if numeric is not None:
                    risk_map[norm_text(key)] = numeric
        seen_allergens: Dict[str, float] = {}
        penalty = 0.0
        for item in allergens:
            sev = risk_map.get(norm_text(item.get("severity_level")), 0.0)
            allergen_key = norm_text(
                item.get("allergen_id")
                or item.get("allergen_type")
                or item.get("allergen_name")
                or item.get("allergen")
                or item.get("name")
            )
            if allergen_key:
                seen_allergens[allergen_key] = max(seen_allergens.get(allergen_key, 0.0), sev)
            else:
                penalty += sev
        penalty += sum(seen_allergens.values())
        b2_cap = as_float(b2_cfg.get("cap"), 2.0)
        return clamp(0.0, b2_cap, penalty)

    def _derive_claim_validations(self, product: Dict[str, Any], b2_penalty: float) -> Tuple[bool, bool, bool, List[str]]:
        flags: List[str] = []

        explicit_allergen = product.get("claim_allergen_free_validated")
        explicit_gluten = product.get("claim_gluten_free_validated")
        explicit_vegan = product.get("claim_vegan_validated")

        if explicit_allergen is not None and explicit_gluten is not None and explicit_vegan is not None:
            return bool(explicit_allergen), bool(explicit_gluten), bool(explicit_vegan), flags

        compliance = product.get("compliance_data", {})
        conflicts = [norm_text(x) for x in safe_list(compliance.get("conflicts"))]
        has_may_contain = bool(compliance.get("has_may_contain_warning", False))

        if explicit_allergen is None:
            allergen_claims = safe_list(compliance.get("allergen_free_claims"))
            contradiction = has_may_contain or any(
                any(term in c for term in ["allergen", "dairy", "soy", "egg", "gluten", "wheat", "shellfish", "nut"])
                for c in conflicts
            )
            allergen_valid = bool(allergen_claims) and not contradiction and b2_penalty == 0.0
        else:
            allergen_valid = bool(explicit_allergen)

        if explicit_gluten is None:
            gluten_claim = bool(compliance.get("gluten_free", False))
            contradiction = has_may_contain or any(
                ("gluten" in c) or ("wheat" in c) for c in conflicts
            )
            gluten_valid = gluten_claim and not contradiction
        else:
            gluten_valid = bool(explicit_gluten)

        if explicit_vegan is None:
            vegan_claim = bool(compliance.get("vegan", False) or compliance.get("vegetarian", False))
            contradiction = any(
                any(term in c for term in ["gelatin", "bovine", "porcine", "vegan", "vegetarian"]) for c in conflicts
            )
            vegan_valid = vegan_claim and not contradiction
        else:
            vegan_valid = bool(explicit_vegan)

        if (bool(compliance.get("allergen_free_claims")) or bool(compliance.get("gluten_free")) or bool(compliance.get("vegan"))) and conflicts:
            flags.append("LABEL_CONTRADICTION_DETECTED")

        return allergen_valid, gluten_valid, vegan_valid, flags

    # v4 P0.1b (2026-05-18): scope-aware diminishing returns for B4a.
    # See docs/plans/SCORING_V4_PROPOSAL.md §10 and §16. Only sku/product_line
    # resolutions score. brand_only routes to manufacturer trust (D), not B4a.
    # claimed_only and needs_review score zero until reviewers triage.
    #
    # P0.1d (2026-05-18): provisional `label_asserted_product` tier closes the
    # undercredit gap for whitelisted programs (USP / Informed Choice /
    # Informed Sport / BSCG) with strong product-LABEL evidence, while their
    # live scrapers are not yet built. Capped low (3) so a false-positive on
    # the label can never bypass real SKU-level verification.
    _B4A_SCOPE_POINTS = {
        "sku":                    [8, 4, 2],
        "product_line":           [6, 3, 1],
        "label_asserted_product": [2, 1, 0],  # P0.1d provisional (label-only)
        "brand_only":             [0, 0, 0],  # display/trust metadata only (lives on D)
        "needs_review":           [0, 0, 0],  # held until reviewer triages
        "claimed_only":           [0, 0, 0],  # regex/manufacturer claim, no registry proof
    }
    # B4a hard cap (v4): tighter than the v3 cap (15) because the dimension
    # cap (testing/trust = 15) must accommodate B4b GMP + B4c batch as well.
    _B4A_CAP = 12

    # P0.1d label_asserted whitelist (strong testing/purity certs only).
    # Programs outside this set never get the provisional 2/1/0 — even with
    # label evidence. Sustainability / source-quality / regulatory certs
    # (Friend of the Sea, MSC, GOED, Health Canada NPN, Labdoor) route to
    # other v4 dimensions, not B4a.
    _B4A_LABEL_ASSERTED_WHITELIST = frozenset({
        "usp verified",
        "informed choice",
        "informed sport",
        "bscg",
    })
    # IFOS scores label_asserted ONLY when the product is omega-like.
    # Marine/omega-specific cert gate is enforced just below the whitelist
    # check in _compute_certifications_bonus.
    _B4A_LABEL_ASSERTED_OMEGA_ONLY_WHITELIST = frozenset({
        "ifos",
    })
    _B4A_SCOPE_STRENGTH = {
        "sku": 3,
        "product_line": 2,
        "label_asserted_product": 1,
    }

    def _compute_certifications_bonus(self, product: Dict[str, Any], supp_type: str) -> Dict[str, float]:
        cert = product.get("certification_data", {})
        b4_cfg = self.config.get("section_B_safety_purity", {}).get("B4_quality_certifications", {})

        # v4 B4a: read verified_cert_programs (resolver-produced) — never the
        # raw claimed/manufacturer-injected list. This is the integrity fix.
        verified = product.get("verified_cert_programs")
        if verified is None:
            # Fall back to the nested location written by _collect_certification_data
            verified = (cert or {}).get("verified_cert_programs")
        if not isinstance(verified, list):
            verified = []

        # Marine/omega-specific certs: only count when product contains omega-3 /
        # marine ingredients. (Same gate as v3, applied to verified entries.)
        marine_cert_tokens = self._get_marine_cert_tokens()
        omega_like = supp_type in {"specialty", "omega_3"} or any(
            any(term in norm_text(i.get("name") or i.get("standard_name"))
                for term in ("omega", "fish oil", "krill", "cod liver", "marine", "dha", "epa"))
            for i in self._get_active_ingredients(product)
        )

        # Group SCORING-ELIGIBLE entries by scope. An entry scores only if:
        #   (1) scope in {sku, product_line, label_asserted_product}
        #   (2) recency status is not scoring_blocked
        #   (3) no scoring_blocked_reason set (covers unknown-recency too)
        # The resolver writes scoring_blocked_reason whenever the snapshot is
        # too stale to credit; we honor that here without re-deriving recency.
        #
        # P0.1d adds `label_asserted_product` for whitelisted programs only,
        # with extra evidence-source + omega gates so manufacturer-injected
        # claims and off-topic certs can't bypass the gate.
        # Program-level dedupe is required because the enricher can see the
        # same product-label cert through multiple paths (label cert list,
        # raw label text, rules-db). Count each normalized program once and
        # keep the strongest scoreable scope for that program.
        best_scope_by_program: Dict[str, str] = {}
        for entry in verified:
            if not isinstance(entry, dict):
                continue
            scope = entry.get("scope") or ""
            if scope not in ("sku", "product_line", "label_asserted_product"):
                continue
            if entry.get("scoring_blocked_reason"):
                continue
            program = norm_text(entry.get("program") or "")
            if not program:
                continue

            # P0.1d gates: label_asserted_product only credits when
            #   (a) evidence is product-label (never manufacturer-injection)
            #   (b) program is in the testing/purity whitelist OR the
            #       omega-only whitelist + product is omega-like.
            if scope == "label_asserted_product":
                if entry.get("evidence_source") != "product_label":
                    continue
                in_main_wl = program in self._B4A_LABEL_ASSERTED_WHITELIST
                in_omega_wl = (
                    program in self._B4A_LABEL_ASSERTED_OMEGA_ONLY_WHITELIST
                    and omega_like
                )
                if not (in_main_wl or in_omega_wl):
                    continue

            # Marine cert gate (also applies to sku/product_line)
            if any(mc in program for mc in marine_cert_tokens) and not omega_like:
                continue

            existing = best_scope_by_program.get(program)
            if existing is None or self._B4A_SCOPE_STRENGTH[scope] > self._B4A_SCOPE_STRENGTH[existing]:
                best_scope_by_program[program] = scope

        from collections import defaultdict
        scope_counts: Dict[str, int] = defaultdict(int)
        for scope in best_scope_by_program.values():
            scope_counts[scope] += 1

        # Apply diminishing returns: SKU first, then product_line, then the
        # provisional label_asserted tier. Each scope has its own rung list;
        # the overall B4a cap (12) wins at the end.
        b4a_raw = 0.0
        for scope in ("sku", "product_line", "label_asserted_product"):
            n = scope_counts[scope]
            if n <= 0:
                continue
            rungs = self._B4A_SCOPE_POINTS[scope]
            for i in range(min(n, len(rungs))):
                b4a_raw += float(rungs[i])

        b4a = clamp(0.0, float(self._B4A_CAP), b4a_raw)

        b4b_cfg = b4_cfg.get("B4b_gmp", {}) if isinstance(b4_cfg, dict) else {}
        b4b_certified = as_float(b4b_cfg.get("certified"), 4.0) or 4.0
        b4b_fda_registered = as_float(b4b_cfg.get("fda_registered"), 2.0) or 2.0

        gmp_level = norm_text(product.get("gmp_level"))
        gmp = cert.get("gmp", {})
        if gmp_level == "certified" or bool(gmp.get("nsf_gmp") or gmp.get("claimed")):
            b4b = float(b4b_certified)
        elif gmp_level == "fda_registered" or bool(gmp.get("fda_registered")):
            b4b = float(b4b_fda_registered)
        else:
            b4b = 0.0

        b4c_cfg = b4_cfg.get("B4c_batch_traceability", {}) if isinstance(b4_cfg, dict) else {}
        b4c_coa_points = as_float(b4c_cfg.get("coa"), 1.0) or 1.0
        b4c_batch_lookup_points = as_float(b4c_cfg.get("batch_lookup"), 1.0) or 1.0

        has_coa = bool(product.get("has_coa", cert.get("batch_traceability", {}).get("has_coa", False)))
        has_batch_lookup = bool(
            product.get(
                "has_batch_lookup",
                cert.get("batch_traceability", {}).get("has_batch_lookup", False)
                or cert.get("batch_traceability", {}).get("has_qr_code", False),
            )
        )
        b4c = float(
            (b4c_coa_points if has_coa else 0.0)
            + (b4c_batch_lookup_points if has_batch_lookup else 0.0)
        )

        return {
            "B4a": b4a,
            "B4b": b4b,
            "B4c": b4c,
            "named_program_count": float(len(best_scope_by_program)),
            "_verified_programs_scored": sorted(best_scope_by_program.keys()),
            "_verified_scope_counts": {k: v for k, v in scope_counts.items() if v > 0},
        }

    def _sum_total_active_mg(self, product: Dict[str, Any]) -> float:
        total = 0.0
        for ing in self._get_active_ingredients(product):
            qty = as_float(ing.get("quantity"), None)
            unit = norm_text(ing.get("unit_normalized") or ing.get("unit"))
            if qty is None:
                continue
            if unit in {"mg", "milligram", "milligrams"}:
                total += qty
            elif unit in {"mcg", "ug", "microgram", "micrograms"}:
                total += qty / 1000.0
            elif unit in {"g", "gram", "grams"}:
                total += qty * 1000.0
        return total

    def _has_usable_individual_dose(self, ingredient: Dict[str, Any]) -> bool:
        if ingredient.get("scoring_input_kind") == "product_level_evidence":
            # Product-level contracts feed only sections that explicitly
            # support that evidence type. They are not ingredient form-quality
            # rows and should not receive generic A1/A6 credit.
            return False
        qty = as_float(ingredient.get("quantity"), None)
        if qty is None or qty <= 0:
            return False
        unit = norm_text(ingredient.get("unit_normalized") or ingredient.get("unit"))
        if not unit:
            return bool(ingredient.get("has_dose", False))
        # Enricher emits unit_normalized with whitespace stripped ("livecell(s)"),
        # but raw unit fields normalize via norm_text to the spaced form
        # ("live cell(s)"). Check both against the whitelist so either source
        # matches.
        unit_compact = unit.replace(" ", "")
        whitelist = {
            "mg",
            "milligram",
            "milligrams",
            "milligram(s)",
            "mcg",
            "ug",
            "µg",
            "microgram",
            "micrograms",
            "microgram(s)",
            "g",
            "gram",
            "grams",
            "gram(s)",
            "iu",
            "cfu",
            "cfu(s)",
            "cfus",
            "billion cfu",
            "million cfu",
            "colony forming unit",
            "colony forming units",
            "colony forming unit(s)",
            "colonyformingunit",
            "colonyformingunits",
            "colonyformingunit(s)",
            # Probiotic CFU-equivalent unit labels seen in DSLD. The enricher
            # treats these as CFU-equivalent; the scorer must accept them so
            # IQM quality scores on probiotic rows flow into Section A. Include
            # both spaced and compact forms — enricher's unit_normalized strips
            # whitespace, raw unit goes through norm_text which keeps it.
            "live cell",
            "live cells",
            "live cell(s)",
            "livecell",
            "livecells",
            "livecell(s)",
            "viable cell",
            "viable cells",
            "viable cell(s)",
            "viablecell",
            "viablecells",
            "viablecell(s)",
            "active cell",
            "active cells",
            "active cell(s)",
            "activecell",
            "activecells",
            "activecell(s)",
            # FDA DFE (Dietary Folate Equivalents) units
            "mcgdfe",
            "mgdfe",
        }
        return unit in whitelist or unit_compact in whitelist

    def _get_disclosure_blends(self, product: Dict[str, Any]) -> List[Dict[str, Any]]:
        blends = safe_list(product.get("proprietary_blends"))
        if blends:
            return blends
        return safe_list(product.get("proprietary_data", {}).get("blends", []))

    def _has_full_disclosure(self, product: Dict[str, Any]) -> bool:
        if "has_full_disclosure" in product:
            return bool(product.get("has_full_disclosure"))

        ingredients = self._get_active_ingredients(product)
        has_missing_dose = any(
            (not bool(i.get("is_proprietary_blend"))) and (not self._has_usable_individual_dose(i))
            for i in ingredients
        )
        blends = self._get_disclosure_blends(product)
        has_hidden_blends = any(norm_text(b.get("disclosure_level")) in {"none", "partial"} for b in blends)
        return (not has_missing_dose) and (not has_hidden_blends)

    # B5 formula constants — hidden-mass transparency model.
    _B5_BASE = {"full": 0.0, "partial": 1.0, "none": 2.0}
    _B5_PROP_COEF = {"full": 0.0, "partial": 3.0, "none": 5.0}
    _B5_CAP = 10.0

    # P0.2 (2026-05-18): class-aware opacity multipliers. See
    # docs/plans/SCORING_V4_PROPOSAL.md §5. Defaults are overridden by
    # config.section_B_safety_purity.B5_proprietary_blends.class_multipliers.
    _B5_CLASS_MULTIPLIERS_DEFAULT = {
        "probiotic": 0.4,           # strain-named + aggregate CFU is industry norm
        "multi_or_prenatal": 1.3,   # each vitamin has a known RDA
        "sports_active": 1.5,       # opaque blends hide stimulant / amino doses
        "generic": 1.0,             # v3 behavior preserved
    }
    # Product-name keyword matchers for class routing.  Used only when the
    # supp_type classifier did not already assign a strong class.
    _B5_PRENATAL_KEYWORDS = re.compile(
        r"\b(prenatal|pregnancy|pre-natal|expecting|maternal|gestation)\b",
        re.IGNORECASE,
    )
    _B5_SPORTS_KEYWORDS = re.compile(
        r"\b(pre[-\s]?workout|post[-\s]?workout|intra[-\s]?workout|"
        r"bcaa|eaa|creatine|beta[-\s]?alanine|nitric[-\s]?oxide|"
        r"energy\s+matrix|pump|stim\s+stack|thermogenic|fat\s+burner|"
        r"whey|casein|"
        r"protein\s+(?:isolate|blend|complex|matrix|powder|concentrate|hydrolysate))\b",
        re.IGNORECASE,
    )
    _B5_GENERIC_OVERRIDE_KEYWORDS = re.compile(
        r"\b(dha|epa|omega[-\s]?3|fish\s+oil|krill|cod\s+liver|"
        r"enzyme|enzymes|glucosamine|chondroitin|msm|collagen)\b",
        re.IGNORECASE,
    )
    _B5_GENERIC_OVERRIDE_PRIMARY_CATEGORIES = {
        # DB canonical (underscore form): what build_final_db stores in
        # products_core.primary_category — must take precedence so the
        # override fires for shipped products. Added 2026-05-23.
        "omega_3",
        "protein_powder",
        "collagen",
        "joint_support",
        "fiber_digestive",
        # Legacy / display forms (hyphen + space): kept for backcompat with
        # older enriched batches that haven't been re-built yet.
        "omega-3",
        "omega 3",
        "protein",
        "enzyme",
        "enzymes",
    }

    def _b5_class_for_product(self, product: Dict[str, Any]) -> str:
        """Route a product to one of the B5 opacity classes:
        probiotic / multi_or_prenatal / sports_active / generic.

        SP-2.7 (2026-05-21): taxonomy-first. Reads
        `supplement_taxonomy.primary_type` (the canonical signal emitted by
        the enricher post-2026-05-20) before falling back to the legacy
        supplement_type / primary_category / name-keyword heuristics. Old
        enriched batches without taxonomy keep the original v3 routing
        intact — none of the legacy paths were removed, only a higher-
        priority taxonomy check was added.

        Priority order:
          1. probiotic (taxonomy primary_type OR legacy supp_type).
          2. Sports name keyword overlay (pre-workout / BCAA / creatine
             stacks have their own 1.5x opacity tier; beats multi).
          3. GENERIC_OVERRIDE (legacy v3 safety net for products that
             carry a broad category signal but are not RDA-panel multis —
             omega / enzyme / joint / collagen / protein). Kept active
             across both taxonomy and legacy paths because it protects
             against any future taxonomy mis-classification.
          4. Taxonomy primary_type in {multivitamin, b_complex} -> multi.
          5. Prenatal name keyword -> multi (catches Prenatal DHA where
             taxonomy might classify as omega_3).
          6. Legacy fallback (taxonomy absent or non-multi-class):
                supp_type in _MULTI_TYPES                  -> multi
                primary_category == multivitamin           -> multi
                (GoL MyKind Men's/Women's Multi pattern)
          7. Fallback: generic.

        Taxonomy primary_type in {omega_3, collagen, joint_support, ...}
        naturally falls through to generic at step 7 — B5 has no separate
        opacity tier for omega; fish oil uses the 1.0x generic multiplier.
        """
        primary_type = self._primary_type_from_product(product)

        st_payload = product.get("supplement_type", {})
        supp_type = (
            st_payload.get("type") if isinstance(st_payload, dict) else st_payload
        ) or product.get("supp_type") or ""
        supp_type = str(supp_type).strip().lower()

        # Priority 1: probiotic (taxonomy first, legacy fallback, then
        # product-level probiotic evidence). The product-level path is a
        # narrow rescue for probiotic-dominant products whose taxonomy falls
        # back to general_supplement because only the prebiotic carrier row is
        # scorable after strict-contract filtering; it must not override a
        # strong non-probiotic taxonomy class such as greens_powder.
        if (
            primary_type == "probiotic"
            or supp_type in self._PROBIOTIC_TYPES
            or self._has_b5_probiotic_product_signal(product)
        ):
            return "probiotic"

        name_text = " ".join(
            str(product.get(k) or "")
            for k in ("product_name", "fullName", "brand_name", "bundleName")
        )

        # Priority 2: sports keyword overlay beats multivitamin routing.
        if self._B5_SPORTS_KEYWORDS.search(name_text):
            return "sports_active"

        primary_category = str(product.get("primary_category") or "").strip().lower()

        # Priority 3: GENERIC_OVERRIDE safety net. Routes products with a
        # narrow primary identity (omega / protein / collagen / joint /
        # enzyme / fiber) to the 1.0x generic opacity tier.
        #
        # The `not _B5_PRENATAL_KEYWORDS` suppression on the keyword path
        # is INTENTIONAL: a genuine "Prenatal Multivitamin DHA" should
        # match Priority 6 (primary_category=multivitamin) below, not be
        # short-circuited to generic by the DHA keyword. Single-active
        # "Prenatal DHA"-style products instead match via the
        # primary_category set ('omega_3', etc., now in DB format) — that
        # branch is NOT suppressed by the prenatal keyword.
        if (
            primary_category in self._B5_GENERIC_OVERRIDE_PRIMARY_CATEGORIES
            or (
                self._B5_GENERIC_OVERRIDE_KEYWORDS.search(name_text)
                and not self._B5_PRENATAL_KEYWORDS.search(name_text)
            )
        ):
            return "generic"

        # Priority 4: taxonomy multivitamin / b_complex -> multi.
        if primary_type in ("multivitamin", "b_complex"):
            return "multi_or_prenatal"

        # Priority 5 (RETIRED 2026-05-23): the prenatal-keyword-only
        # override ("if name has 'prenatal' → multi_or_prenatal") was
        # retired by product policy. It mis-routed probiotic-marketed-as-
        # prenatal (274081 Garden Once Daily Prenatal, has product-level
        # CFU evidence and no multi panel) and single-active prenatal
        # omegas (74124 Nordic Prenatal DHA, where B5 has no blends).
        # Genuine prenatal multivitamins carry primary_category=
        # multivitamin and are still caught by Priority 6 below.
        # Locked by test_v4_canary_coverage::test_canary_expected_b5_class_matches_router
        # and test_v3_b5_class_taxonomy_migration::test_prenatal_dha_keeps_omega_3_b5_class.

        # Priority 6: legacy fallback for old batches without taxonomy.
        if supp_type in self._MULTI_TYPES:
            return "multi_or_prenatal"
        if primary_category == "multivitamin":
            return "multi_or_prenatal"

        return "generic"

    @staticmethod
    def _truthy_catalog_flag(value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y"}
        return bool(value)

    @classmethod
    def _has_b5_probiotic_product_signal(cls, product: Dict[str, Any]) -> bool:
        """Return True for explicit product-level probiotic identity.

        This is intentionally narrower than "contains any probiotic token".
        Mixed products can contain probiotic strains without being a probiotic
        product for B5 opacity semantics; require either enriched
        ``probiotic_data.is_probiotic_product`` with CFU/strain evidence or
        the shipped catalog's boolean product flags.
        """
        primary_type = cls._primary_type_from_product(product)
        st_payload = product.get("supplement_type", {})
        supp_type = (
            st_payload.get("type") if isinstance(st_payload, dict) else st_payload
        ) or product.get("supp_type") or ""
        supp_type = str(supp_type).strip().lower()
        primary_category = str(product.get("primary_category") or "").strip().lower()
        if primary_type and primary_type not in ("general_supplement", "probiotic"):
            return False
        if (
            primary_type in ("multivitamin", "b_complex")
            or supp_type in cls._MULTI_TYPES
            or primary_category == "multivitamin"
        ):
            return False
        if primary_category and primary_category not in ("general_supplement", "probiotic"):
            return False

        pdata = product.get("probiotic_data") or product.get("probiotic_detail")
        if isinstance(pdata, dict) and cls._truthy_catalog_flag(pdata.get("is_probiotic_product")):
            has_evidence = any(
                pdata.get(key)
                for key in (
                    "total_cfu",
                    "total_billion_count",
                    "total_strain_count",
                    "probiotic_blends",
                    "clinical_strains",
                )
            )
            if has_evidence:
                return True

        return (
            cls._truthy_catalog_flag(product.get("is_probiotic"))
            and cls._truthy_catalog_flag(product.get("contains_probiotics"))
        )

    @staticmethod
    def _primary_type_from_product(product: Dict[str, Any]) -> str:
        """Read the canonical `primary_type` from an enriched product.

        Prefers the top-level `primary_type` field (set by
        `enrich_supplements_v3` post-2026-05-20), then nested
        `supplement_taxonomy.primary_type`. Returns "" when the taxonomy
        is absent (old enriched batches).
        """
        direct = product.get("primary_type") if isinstance(product, dict) else None
        if isinstance(direct, str) and direct.strip():
            return direct.strip().lower()
        taxonomy = (product or {}).get("supplement_taxonomy")
        if isinstance(taxonomy, dict):
            nested = taxonomy.get("primary_type")
            if isinstance(nested, str) and nested.strip():
                return nested.strip().lower()
        return ""

    def _blend_quantity_to_mg(self, amount: Any, unit: Any) -> Tuple[Optional[float], bool]:
        qty = as_float(amount, None)
        if qty is None:
            return None, False
        unit_norm = norm_text(unit)
        if not unit_norm or unit_norm in {"mg", "milligram", "milligrams"}:
            return qty, False
        converted = self._convert_unit(qty, unit_norm, "mg")
        if converted is None:
            return None, True
        return converted, False

    def _blend_child_payload(self, blend: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
        children_with_amounts: List[Dict[str, Any]] = []
        children_without_amounts: List[str] = []

        for child in safe_list(blend.get("child_ingredients")):
            name = child.get("name") or child.get("ingredient") or ""
            amount = as_float(child.get("amount"), None)
            if amount is None or amount <= 0:
                if name:
                    children_without_amounts.append(name)
                continue
            children_with_amounts.append(
                {
                    "name": name,
                    "amount": amount,
                    "unit": child.get("unit") or child.get("unit_normalized") or "mg",
                }
            )

        evidence = blend.get("evidence") or {}
        for child in safe_list(evidence.get("ingredients_with_amounts")):
            name = child.get("name") or child.get("ingredient") or ""
            amount = as_float(child.get("amount"), None)
            if amount is None or amount <= 0:
                continue
            children_with_amounts.append(
                {
                    "name": name,
                    "amount": amount,
                    "unit": child.get("unit") or child.get("unit_normalized") or "mg",
                }
            )
        for child in safe_list(evidence.get("ingredients_without_amounts")):
            if isinstance(child, dict):
                name = child.get("name") or child.get("ingredient") or ""
            else:
                name = str(child or "")
            if name:
                children_without_amounts.append(name)

        # Deduplicate while preserving order.
        seen_with = set()
        deduped_with: List[Dict[str, Any]] = []
        for child in children_with_amounts:
            key = (canon_key(child.get("name")), as_float(child.get("amount"), 0.0), norm_text(child.get("unit")))
            if key in seen_with:
                continue
            seen_with.add(key)
            deduped_with.append(child)

        seen_without = set()
        deduped_without: List[str] = []
        for name in children_without_amounts:
            key = canon_key(name)
            if not key or key in seen_without:
                continue
            seen_without.add(key)
            deduped_without.append(name)

        return deduped_with, deduped_without

    def _blend_dedupe_fingerprint(self, blend: Dict[str, Any]) -> Tuple[str, Tuple[str, ...], str, str]:
        name_key = canon_key(blend.get("name"))
        children_with, children_without = self._blend_child_payload(blend)
        child_names = sorted(
            {
                canon_key(item.get("name"))
                for item in children_with
                if canon_key(item.get("name"))
            }
            | {
                canon_key(name)
                for name in children_without
                if canon_key(name)
            }
        )
        amount_value = (
            blend.get("blend_total_mg")
            if blend.get("blend_total_mg") is not None
            else blend.get("total_weight")
        )
        amount_unit = "mg" if blend.get("blend_total_mg") is not None else blend.get("unit")
        blend_total_mg, _ = self._blend_quantity_to_mg(amount_value, amount_unit)
        blend_total_key = "" if blend_total_mg is None else f"{round(blend_total_mg, 3):.3f}"
        evidence = blend.get("evidence") or {}
        source_path = norm_text(
            blend.get("source_path")
            or blend.get("source_field")
            or evidence.get("source_field")
            or ""
        )
        return (name_key, tuple(child_names), blend_total_key, source_path)

    def _looks_like_blend_container_name(self, value: Any) -> bool:
        text = norm_text(value)
        if not text:
            return False
        return any(token in text for token in ("blend", "complex", "matrix", "formula", "proprietary"))

    def _is_b5_scoreable_blend(self, blend: Dict[str, Any]) -> bool:
        source_path = norm_text(blend.get("source_path") or blend.get("source_field") or "")
        source_prefix = source_path.split("[", 1)[0]
        sources = {norm_text(item) for item in safe_list(blend.get("sources")) if norm_text(item)}
        detector_only = bool(sources) and sources == {"detector"}

        children_with_amounts, children_without_amounts = self._blend_child_payload(blend)
        has_child_evidence = bool(children_with_amounts or children_without_amounts)
        hidden_count = int(as_float(blend.get("hidden_count"), 0) or 0)
        nested_count = int(as_float(blend.get("nested_count"), 0) or 0)

        blend_total_raw = (
            blend.get("blend_total_mg")
            if blend.get("blend_total_mg") is not None
            else blend.get("total_weight")
        )
        if blend_total_raw is not None and (not isinstance(blend_total_raw, (int, float)) or blend_total_raw <= 0):
            blend_total_raw = None
        blend_total_unit = "mg" if blend.get("blend_total_mg") is not None else blend.get("unit")
        blend_total_mg, _ = self._blend_quantity_to_mg(blend_total_raw, blend_total_unit)
        has_total_amount = blend_total_mg is not None and blend_total_mg > 0

        if source_prefix == "activeingredients":
            return (
                self._looks_like_blend_container_name(blend.get("name"))
                or has_total_amount
                or has_child_evidence
                or hidden_count > 0
                or nested_count > 0
            )

        if detector_only and source_prefix in {"statements", "inactiveingredients"}:
            return has_total_amount or has_child_evidence

        return True

    def _compute_proprietary_blend_penalty(self, product: Dict[str, Any], flags: List[str], b_cfg: Dict[str, Any] = None) -> float:
        if b_cfg is None:
            b_cfg = self.config.get("section_B_safety_purity", {})
        b5_cfg = b_cfg.get("B5_proprietary_blends", {})
        proprietary = product.get("proprietary_data", {})
        blends = safe_list(product.get("proprietary_blends"))
        if not blends:
            blends = safe_list(proprietary.get("blends", []))

        self._last_b5_blend_evidence: List[Dict[str, Any]] = []
        if not blends:
            return 0.0

        flags.append("PROPRIETARY_BLEND_PRESENT")

        dedup_keys: set[Tuple[str, Tuple[str, ...], str, str]] = set()
        deduped: List[Dict[str, Any]] = []
        for blend in blends:
            if not self._is_b5_scoreable_blend(blend):
                continue
            key = self._blend_dedupe_fingerprint(blend)
            if key in dedup_keys:
                continue
            dedup_keys.add(key)
            deduped.append(blend)

        if not deduped:
            return 0.0

        total_active_mg = as_float(proprietary.get("total_active_mg"), None)
        if total_active_mg is None:
            total_active_mg = self._sum_total_active_mg(product)

        total_active_count = int(
            as_float(proprietary.get("total_active_ingredients"), 0)
            or as_float(product.get("ingredient_quality_data", {}).get("total_active"), 0)
            or len(self._get_active_ingredients(product))
            or 0
        )

        cfg_presence = b5_cfg.get("presence_penalty", {})
        cfg_prop_coef = b5_cfg.get("proportional_coef", {})
        b5_base = {k: as_float(v, self._B5_BASE.get(k, 2.0)) for k, v in cfg_presence.items()} if cfg_presence else dict(self._B5_BASE)
        for k, v in self._B5_BASE.items():
            b5_base.setdefault(k, v)
        b5_prop = {k: as_float(v, self._B5_PROP_COEF.get(k, 5.0)) for k, v in cfg_prop_coef.items()} if cfg_prop_coef else dict(self._B5_PROP_COEF)
        for k, v in self._B5_PROP_COEF.items():
            b5_prop.setdefault(k, v)
        b5_cap = as_float(b5_cfg.get("cap"), self._B5_CAP)
        count_denom_min = int(as_float(b5_cfg.get("count_share_min_denominator_constant"), 8))

        # P0.2: class-aware opacity multiplier.  Reads config overrides on
        # top of the in-code defaults so a future tweak (e.g., raising sports
        # to 1.7) doesn't require a code change.
        cfg_multipliers = b5_cfg.get("class_multipliers") or {}
        class_multipliers = dict(self._B5_CLASS_MULTIPLIERS_DEFAULT)
        for k, v in cfg_multipliers.items():
            mv = as_float(v, class_multipliers.get(k, 1.0))
            if mv is not None:
                class_multipliers[k] = float(mv)
        blend_class = self._b5_class_for_product(product)
        class_mult = float(class_multipliers.get(blend_class, 1.0))

        penalty_sum = 0.0
        for blend in deduped:
            level = norm_text(blend.get("disclosure_level"))
            base = b5_base.get(level, b5_base["none"])
            prop_coef = b5_prop.get(level, b5_prop["none"])
            evidence_payload = blend.get("evidence")
            evidence_dict = evidence_payload if isinstance(evidence_payload, dict) else {}
            source_raw = blend.get("source_field") or evidence_dict.get("source_field") or ""
            source_path = str(source_raw).strip() if source_raw is not None else ""
            source_field = source_path.split("[", 1)[0] if source_path else ""

            children_with_amounts, children_without_amounts = self._blend_child_payload(blend)

            blend_total_raw = (
                blend.get("blend_total_mg")
                if blend.get("blend_total_mg") is not None
                else blend.get("total_weight")
            )
            # Treat zero/falsy total_weight as no declared total.
            if blend_total_raw is not None and (not isinstance(blend_total_raw, (int, float)) or blend_total_raw <= 0):
                blend_total_raw = None
            blend_total_unit = "mg" if blend.get("blend_total_mg") is not None else blend.get("unit")
            blend_total_mg, blend_unit_fail = self._blend_quantity_to_mg(blend_total_raw, blend_total_unit)

            disclosed_child_mg_sum = 0.0
            child_unit_fail = False
            for child in children_with_amounts:
                child_mg, child_fail = self._blend_quantity_to_mg(child.get("amount"), child.get("unit"))
                if child_fail:
                    child_unit_fail = True
                if child_mg is not None and child_mg > 0:
                    disclosed_child_mg_sum += child_mg

            hidden_mass_mg = None
            impact_source = "count_share"
            impact_floor_applied = False
            unit_conversion_failed = bool(blend_unit_fail or child_unit_fail)

            # Prefer mg-share when blend mass and active total are usable.
            if blend_total_mg is not None and total_active_mg and total_active_mg > 0:
                disclosed_clamped = min(disclosed_child_mg_sum, blend_total_mg)
                hidden_mass_mg = max(blend_total_mg - disclosed_clamped, 0.0)
                impact = clamp(0.0, 1.0, hidden_mass_mg / total_active_mg)
                if hidden_mass_mg > 0 and impact < 0.1:
                    impact = 0.1
                    impact_floor_applied = True
                impact_source = "mg_share"
                disclosed_child_mg_sum = disclosed_clamped
            else:
                hidden_count = int(as_float(blend.get("hidden_count"), 0) or 0)
                if hidden_count <= 0:
                    hidden_count = len(children_without_amounts)
                if hidden_count <= 0:
                    hidden_count = int(as_float(blend.get("nested_count"), 0) or 0)
                # Deterministic count-share denominator constant for small formulas.
                denom = max(total_active_count, count_denom_min)
                impact = clamp(0.0, 1.0, hidden_count / max(denom, 1))

            blend_penalty_raw = 0.0
            if level != "full":
                blend_penalty_raw = base + (prop_coef * impact)
            # P0.2: scale by class multiplier before accumulating.  `full`
            # blends stay 0 (anything × 0 = 0), so the multiplier is a no-op
            # on transparent blends regardless of class.
            blend_penalty = blend_penalty_raw * class_mult
            penalty_sum += blend_penalty

            evidence = {
                "blend_name": blend.get("name") or "",
                "disclosure_tier": level or "none",
                "blend_class": blend_class,
                "class_multiplier_applied": round(class_mult, 4),
                "blend_total_mg": None if blend_total_mg is None else round(blend_total_mg, 4),
                "disclosed_child_mg_sum": round(disclosed_child_mg_sum, 4),
                "hidden_mass_mg": None if hidden_mass_mg is None else round(hidden_mass_mg, 4),
                "impact_ratio": round(impact, 6),
                "impact_source": impact_source,
                "impact_floor_applied": bool(impact_floor_applied),
                "presence_penalty": round(base, 4),
                "proportional_coef": round(prop_coef, 4),
                "base_penalty_formula": (
                    "full: 0"
                    if level == "full"
                    else ("partial: -(1 + 3*impact)" if level == "partial" else "none: -(2 + 5*impact)")
                ),
                "computed_blend_penalty": round(-blend_penalty, 4),
                "computed_blend_penalty_magnitude": round(blend_penalty, 4),
                "dedupe_fingerprint": (
                    lambda fp: f"{fp[0]}|{','.join(fp[1])}|{fp[2]}|{fp[3]}"
                )(self._blend_dedupe_fingerprint(blend)),
                "source_field": source_field,
                "source_path": source_path,
                "unit_conversion_failed": bool(unit_conversion_failed),
                "children_with_amount_count": len(children_with_amounts),
                "children_without_amount_count": len(children_without_amounts),
            }
            self._last_b5_blend_evidence.append(evidence)

        return clamp(0.0, b5_cap, penalty_sum)

    def _compute_disease_claims_penalty(self, product: Dict[str, Any], flags: List[str], b_cfg: Dict[str, Any] = None) -> float:
        if b_cfg is None:
            b_cfg = self.config.get("section_B_safety_purity", {})
        has_claims = bool(product.get("has_disease_claims", False))
        if not has_claims:
            has_claims = bool(product.get("product_signals", {}).get("has_disease_claims", False))
        if not has_claims:
            has_claims = bool(
                product.get("evidence_data", {})
                .get("unsubstantiated_claims", {})
                .get("found", False)
            )
        if has_claims:
            flags.append("DISEASE_CLAIM_DETECTED")
            penalty = as_float(b_cfg.get("B6_marketing_penalty", {}).get("penalty"), 5.0)
            return penalty
        return 0.0

    def _compute_dose_safety_penalty(
        self,
        product: Dict[str, Any],
        flags: List[str],
        config: Optional[Dict[str, Any]] = None,
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """B7: Dose safety penalty for products exceeding highest UL by 150%+.

        Reads over_ul flags from rda_ul_data.safety_flags (computed by the
        enricher).  Only penalises when pct_ul >= 150% — below that threshold,
        UL enforcement is a personalisation concern handled on-device (Section
        E1 in the Flutter app).

        Returns (penalty, evidence_list).
        """
        b7_cfg = (config or {}).get("B7_dose_safety", {})
        threshold_pct = as_float(b7_cfg.get("threshold_pct"), 150.0)
        single_penalty = as_float(b7_cfg.get("single_penalty"), 2.0)
        cap = as_float(b7_cfg.get("cap"), 3.0)

        rda_ul = product.get("rda_ul_data") or {}
        safety_flags = rda_ul.get("safety_flags") or []
        if not safety_flags:
            return 0.0, []

        evidence: List[Dict[str, Any]] = []
        total_penalty = 0.0

        for sf in safety_flags:
            pct = as_float(sf.get("pct_ul"), 0.0)
            if pct >= threshold_pct:
                nutrient = sf.get("nutrient", "unknown")
                amount = sf.get("amount", 0)
                ul = sf.get("ul", 0)
                evidence.append({
                    "nutrient": nutrient,
                    "amount": amount,
                    "ul": ul,
                    "pct_ul": round(pct, 1),
                    "penalty": single_penalty,
                })
                total_penalty += single_penalty
                if f"OVER_UL_{nutrient}" not in flags:
                    flags.append(f"OVER_UL_{nutrient}")

        total_penalty = min(total_penalty, cap)
        return total_penalty, evidence

    def _compute_safety_purity_score(
        self,
        product: Dict[str, Any],
        supp_type: str,
        b0_moderate_penalty: float,
        flags: List[str],
    ) -> Dict[str, Any]:
        section_b_cfg = self.config.get("section_B_safety_purity", {}) or {}
        max_points = as_float(section_b_cfg.get("_max"), 30.0) or 30.0
        base_score = as_float(section_b_cfg.get("base_score"), 25.0) or 25.0
        bonus_pool_cap = as_float(section_b_cfg.get("bonus_pool_cap"), 5.0) or 5.0

        b1_evidence: List[Dict[str, Any]] = []
        b1 = self._compute_harmful_additives_penalty(
            product, section_b_cfg, flags=flags, evidence=b1_evidence
        )
        b2 = self._compute_allergen_penalty(product, section_b_cfg)

        allergen_valid, gluten_valid, vegan_valid, claim_flags = self._derive_claim_validations(product, b2)
        for f in claim_flags:
            if f not in flags:
                flags.append(f)

        b3_cfg = section_b_cfg.get("B3_claim_compliance", {}) or {}
        b3_allergen_pts = as_float(b3_cfg.get("allergen_free"), 2.0) or 2.0
        b3_gluten_pts = as_float(b3_cfg.get("gluten_free"), 1.0) or 1.0
        b3_vegan_pts = as_float(b3_cfg.get("vegan_vegetarian"), 1.0) or 1.0
        b3 = float(
            (b3_allergen_pts if allergen_valid else 0.0)
            + (b3_gluten_pts if gluten_valid else 0.0)
            + (b3_vegan_pts if vegan_valid else 0.0)
        )
        b3_cap = as_float(b3_cfg.get("cap"), 4.0) or 4.0
        b3 = clamp(0.0, b3_cap, b3)

        b_hypoallergenic = 0.0
        if self._feature_on("enable_hypoallergenic_bonus", default=False):
            compliance = product.get("compliance_data", {})
            has_may_contain = bool(compliance.get("has_may_contain_warning", False))
            contradiction = "LABEL_CONTRADICTION_DETECTED" in flags
            hypo_flag = bool(product.get("claim_hypoallergenic_validated", False))
            if not hypo_flag:
                hypo_flag = bool(compliance.get("hypoallergenic", False))
            if hypo_flag and b2 == 0.0 and not has_may_contain and not contradiction and (allergen_valid or gluten_valid):
                b_hypoallergenic = 0.5

        b4 = self._compute_certifications_bonus(product, supp_type)
        b4a, b4b, b4c = b4["B4a"], b4["B4b"], b4["B4c"]

        b5 = self._compute_proprietary_blend_penalty(product, flags, section_b_cfg)
        b6 = self._compute_disease_claims_penalty(product, flags, section_b_cfg)
        b7, b7_evidence = self._compute_dose_safety_penalty(product, flags, section_b_cfg)

        bonuses = min(bonus_pool_cap, b3 + b4a + b4b + b4c + b_hypoallergenic)
        penalties = b1 + b2 + b5 + b6 + b7 + b0_moderate_penalty

        b_raw = base_score + bonuses - penalties
        total = clamp(0.0, max_points, b_raw)

        return {
            "score": round(total, 2),
            "max": round(max_points, 2),
            "B0_moderate_penalty": round(float(b0_moderate_penalty), 2),
            "B1_penalty": round(b1, 2),
            "B1_evidence": b1_evidence,
            "B2_penalty": round(b2, 2),
            "B3": round(b3, 2),
            "B4a": round(b4a, 2),
            "B4b": round(b4b, 2),
            "B4c": round(b4c, 2),
            "B_hypoallergenic": round(b_hypoallergenic, 2),
            "B5_penalty": round(b5, 2),
            "B5_blend_evidence": self._last_b5_blend_evidence,
            "B6_penalty": round(b6, 2),
            "B7_penalty": round(b7, 2),
            "B7_dose_safety_evidence": b7_evidence,
            "bonuses": round(bonuses, 2),
            "penalties": round(penalties, 2),
            "raw": round(b_raw, 2),
        }

    # Backward-compatible alias used by internal diagnostics scripts.
    def _score_b4_proprietary(
        self,
        product: Dict[str, Any],
        proprietary_data: Optional[Dict[str, Any]],
        _config: Optional[Dict[str, Any]] = None,
    ) -> Tuple[float, List[str], Dict[str, Any]]:
        flags: List[str] = []
        tmp_product = dict(product)
        if proprietary_data is not None:
            tmp_product["proprietary_data"] = proprietary_data
        penalty = self._compute_proprietary_blend_penalty(tmp_product, flags)
        notes = [f"B5 proprietary blend penalty magnitude={round(penalty, 2)}"]
        details = {
            "blends_detected_count": len(
                safe_list((proprietary_data or {}).get("blends", []))
            ),
            "use_mg_share": True,
            "reason": "v3_0_penalty",
            "flags": flags,
        }
        # Legacy method returns negative penalty in old tooling.
        return -penalty, notes, details

    # ---------------------------------------------------------------------
    # Section C
    # ---------------------------------------------------------------------

    def _study_base_points(self, study_type: str) -> float:
        mapping = {
            "systematic_review_meta": 6.0,
            "rct_multiple": 5.0,
            "rct_single": 4.0,
            "clinical_strain": 4.0,
            "observational": 2.0,
            "animal_study": 2.0,
            "in_vitro": 1.0,
        }
        config_mapping = (
            self.config.get("section_C_evidence_research", {}).get("study_type_base_points", {}) or {}
        )
        if isinstance(config_mapping, dict):
            for key, value in config_mapping.items():
                numeric = as_float(value, None)
                if numeric is not None:
                    mapping[norm_text(key)] = numeric
        return mapping.get(norm_text(study_type), 0.0)

    def _evidence_multiplier(self, level: str) -> float:
        mapping = {
            "product-human": 1.0,
            "product_human": 1.0,
            "product-rct": 1.0,
            "product_rct": 1.0,
            "product": 1.0,
            "branded-rct": 0.8,
            "branded_rct": 0.8,
            "ingredient-human": 0.65,
            "ingredient_human": 0.65,
            "strain-clinical": 0.6,
            "strain_clinical": 0.6,
            "preclinical": 0.3,
        }
        config_mapping = (
            self.config.get("section_C_evidence_research", {}).get("evidence_level_multipliers", {}) or {}
        )
        if isinstance(config_mapping, dict):
            for key, value in config_mapping.items():
                numeric = as_float(value, None)
                if numeric is not None:
                    key_norm = norm_text(key)
                    mapping[key_norm] = numeric
                    mapping[key_norm.replace("-", "_")] = numeric
        return mapping.get(norm_text(level), 0.0)

    def _dose_map(self, product: Dict[str, Any]) -> Dict[str, Tuple[float, str]]:
        doses: Dict[str, Tuple[float, str]] = {}
        for ing in self._get_active_ingredients(product):
            qty = as_float(ing.get("quantity"), None)
            if qty is None:
                continue
            unit = norm_text(ing.get("unit_normalized") or ing.get("unit"))
            names = [
                ing.get("standard_name"),
                ing.get("name"),
                ing.get("raw_source_text"),
                ing.get("canonical_id"),
            ]
            for n in names:
                key = canon_key(n)
                if key:
                    if key not in doses or qty > doses[key][0]:
                        doses[key] = (qty, unit)
        return doses

    def _convert_unit(self, quantity: float, from_unit: str, to_unit: str) -> Optional[float]:
        from_u = norm_text(from_unit)
        to_u = norm_text(to_unit)

        if from_u == to_u:
            return quantity

        mass_factor = {
            "mcg": 0.001,
            "ug": 0.001,
            "microgram": 0.001,
            "micrograms": 0.001,
            "mg": 1.0,
            "milligram": 1.0,
            "milligrams": 1.0,
            "g": 1000.0,
            "gram": 1000.0,
            "grams": 1000.0,
        }

        if from_u in mass_factor and to_u in mass_factor:
            mg = quantity * mass_factor[from_u]
            return mg / mass_factor[to_u]

        # IU and CFU are not safely convertible to mass without nutrient-specific rules.
        return None

    def _published_study_count(self, entry: Dict[str, Any]) -> Optional[float]:
        """Return the numeric clinical-study count used for depth bonus when available."""
        explicit_count = as_float(entry.get("published_studies_count"), None)
        if explicit_count is not None:
            return explicit_count

        legacy_value = entry.get("published_studies")
        if isinstance(legacy_value, (int, float)):
            return as_float(legacy_value, None)

        return None

    def _compute_evidence_score(self, product: Dict[str, Any], flags: List[str]) -> Dict[str, Any]:
        section_c_cfg = self.config.get("section_C_evidence_research", {}) or {}
        cap_per_ingredient = as_float(section_c_cfg.get("cap_per_ingredient"), 7.0) or 7.0
        cap_total = as_float(section_c_cfg.get("cap_total"), 20.0) or 20.0
        supra_multiple = as_float(section_c_cfg.get("supra_clinical_multiple"), 3.0) or 3.0
        matches = safe_list(product.get("evidence_data", {}).get("clinical_matches", []))

        # Top-N diminishing returns weights: best match at 100%, second at 50%, third at 25%.
        # Configurable via scoring_config.json.  Remaining matches beyond top-N are ignored.
        top_n_weights = section_c_cfg.get("top_n_weights", [1.0, 0.5, 0.25])
        if not isinstance(top_n_weights, list) or not top_n_weights:
            top_n_weights = [1.0, 0.5, 0.25]

        # Effect direction multipliers: scale score by whether the evidence is positive or null.
        effect_direction_multipliers = section_c_cfg.get("effect_direction_multipliers", {}) or {}
        _default_effect_dir = {
            "positive_strong": 1.0,
            "positive_weak": 0.85,
            "mixed": 0.6,
            "null": 0.25,
            "negative": 0.0,
        }
        for k, v in _default_effect_dir.items():
            if k not in effect_direction_multipliers:
                effect_direction_multipliers[k] = v

        ingredient_points: Dict[str, float] = defaultdict(float)
        matched_entry_ids = set()
        dose_map = self._dose_map(product)
        # T7A: track which canonical ingredients triggered the sub-clinical
        # dose guard so the build_final_db layer can flag the matching
        # analyzed_ingredients rows with below_clinical_dose=true. Drives
        # Flutter's "Low dose" chip on per-ingredient rows. Distinct from
        # the product-level SUB_CLINICAL_DOSE_DETECTED flag (which fires
        # if ANY ingredient is below clinical dose).
        sub_clinical_canonicals: set[str] = set()

        for entry in matches:
            entry_id = (
                entry.get("id")
                or entry.get("study_id")
                or f"{canon_key(entry.get('study_name') or entry.get('ingredient'))}:{norm_text(entry.get('study_type'))}:{norm_text(entry.get('evidence_level'))}"
            )
            if entry_id in matched_entry_ids:
                continue
            matched_entry_ids.add(entry_id)

            study_type = entry.get("study_type")
            evidence_level = entry.get("evidence_level")

            # Optional schema support: explicit base/multiplier from clinical DB entries.
            base_points = as_float(entry.get("base_points"), None)
            multiplier = as_float(entry.get("multiplier"), None)
            if base_points is None:
                base_points = self._study_base_points(study_type)
            if multiplier is None:
                multiplier = self._evidence_multiplier(evidence_level)

            raw = base_points * multiplier
            if raw <= 0:
                continue

            # Effect direction multiplier (defaults to positive_strong=1.0 if absent).
            effect_dir = norm_text(entry.get("effect_direction") or "positive_strong")
            effect_dir_mult = as_float(
                effect_direction_multipliers.get(effect_dir),
                1.0,
            )
            raw *= effect_dir_mult
            if raw <= 0:
                continue

            # Enrollment quality multiplier — only for RCTs and meta-analyses.
            # Larger, well-powered trials get a modest boost; pilots get a penalty.
            # Bands: <50 → 0.6x, 50-199 → 0.8x, 200-499 → 1.0x, 500-999 → 1.1x, 1000+ → 1.2x
            enrollment = as_float(entry.get("total_enrollment"), None)
            enrollment_eligible_types = {
                "systematic_review_meta", "rct_multiple", "rct_single",
            }
            if enrollment is not None and norm_text(study_type) in enrollment_eligible_types:
                enrollment_bands = section_c_cfg.get("enrollment_quality_bands", [
                    [50, 0.6], [200, 0.8], [500, 1.0], [1000, 1.1],
                ])
                enroll_mult = 1.2  # default for 1000+
                for threshold, mult in enrollment_bands:
                    if enrollment < threshold:
                        enroll_mult = mult
                        break
                raw *= enroll_mult

            # Clinical dose guard (optional field).
            min_clinical_dose = as_float(entry.get("min_clinical_dose"), None)
            if min_clinical_dose is not None:
                dose_unit = norm_text(entry.get("dose_unit") or "mg")
                lookup_name = (
                    entry.get("standard_name")
                    or entry.get("study_name")
                    or entry.get("ingredient")
                    or ""
                )
                lookup_key = canon_key(lookup_name)
                product_dose = dose_map.get(lookup_key)
                if product_dose is not None:
                    converted = self._convert_unit(product_dose[0], product_dose[1], dose_unit)
                    if converted is not None and converted < min_clinical_dose:
                        raw *= 0.25
                        if "SUB_CLINICAL_DOSE_DETECTED" not in flags:
                            flags.append("SUB_CLINICAL_DOSE_DETECTED")
                        # T7A: per-canonical tracker — surfaces below_clinical_dose
                        # flag on the matching analyzed_ingredients row in the
                        # final blob. Use the canonical_id when available so
                        # build_final_db can match exactly; fall back to
                        # lookup_key (already canonicalized via canon_key).
                        _entry_canonical = (
                            entry.get("canonical_id")
                            or entry.get("ingredient_canonical")
                            or lookup_key
                        )
                        if _entry_canonical:
                            sub_clinical_canonicals.add(canon_key(_entry_canonical))
                    max_studied_dose = as_float(
                        entry.get("max_studied_clinical_dose")
                        or entry.get("max_clinical_dose")
                        or entry.get("max_studied_dose"),
                        None,
                    )
                    if (
                        converted is not None
                        and max_studied_dose is not None
                        and max_studied_dose > 0
                        and converted > (supra_multiple * max_studied_dose)
                    ):
                        if "SUPRA_CLINICAL_DOSE" not in flags:
                            flags.append("SUPRA_CLINICAL_DOSE")

            # Identity vs Bioactivity Split — apply confidence scaling when this
            # match is a marker-via-ingredient secondary credit. confidence_scale
            # ranges 0.4 (provenance-only) – 1.0 (explicit standardization dose).
            marker_confidence = entry.get("marker_confidence_scale")
            if marker_confidence is not None:
                try:
                    raw *= float(marker_confidence)
                except (TypeError, ValueError):
                    pass

            canonical = canon_key(
                entry.get("standard_name") or entry.get("study_name") or entry.get("ingredient")
            )
            if canonical:
                ingredient_points[canonical] += raw

        # Top-N aggregation with diminishing returns.
        # Cap each ingredient, sort descending, then apply positional weights.
        capped_scores = sorted(
            (min(cap_per_ingredient, pts) for pts in ingredient_points.values()),
            reverse=True,
        )
        total = 0.0
        for i, pts in enumerate(capped_scores):
            if i >= len(top_n_weights):
                break
            total += pts * top_n_weights[i]

        # Depth bonus: reward large evidence bodies (many completed trials).
        # Uses the highest published_studies count from any matched entry.
        # Discrete bands: 0-19 trials → +0.0, 20-39 → +0.25, 40+ → +0.5
        depth_bands = section_c_cfg.get("depth_bonus_bands", [[20, 0.25], [40, 0.5]])
        max_trial_count = 0
        for entry in matches:
            tc = self._published_study_count(entry)
            if tc is not None and tc > max_trial_count:
                max_trial_count = tc
        depth = 0.0
        for threshold, bonus in sorted(depth_bands, key=lambda x: x[0]):
            if max_trial_count >= threshold:
                depth = bonus
        total += depth

        return {
            "score": round(clamp(0.0, cap_total, total), 2),
            "max": cap_total,
            "ingredient_points": {k: round(v, 2) for k, v in ingredient_points.items()},
            "matched_entries": len(matched_entry_ids),
            "top_n_applied": min(len(capped_scores), len(top_n_weights)),
            "depth_bonus": round(depth, 2),
            # T7A: canonical IDs that hit the clinical-dose guard. Sorted
            # for deterministic blob output.
            "sub_clinical_canonicals": sorted(sub_clinical_canonicals),
        }

    # ---------------------------------------------------------------------
    # Section D + violations
    # ---------------------------------------------------------------------

    def _compute_brand_trust_score(self, product: Dict[str, Any]) -> Dict[str, Any]:
        section_max = self._section_max("d", 5.0)
        md = product.get("manufacturer_data", {})
        section_d_cfg = self.config.get("section_D_brand_trust", {}) or {}

        # D1 values — trusted and mid-tier are config-driven. Mid-tier is enabled
        # by default via the feature gate in scoring_config.json; when OFF, only
        # fully trusted manufacturers receive D1 credit.
        d1_trusted_value = as_float(
            section_d_cfg.get("D1_manufacturer_reputation"), 2.0
        ) or 2.0
        d1_mid_tier_value = as_float(
            section_d_cfg.get("D1_mid_tier_reputation"), 1.0
        ) or 1.0

        d1 = 0.0
        if bool(product.get("is_trusted_manufacturer", False)):
            d1 = d1_trusted_value
        else:
            top = md.get("top_manufacturer", {})
            if bool(top.get("found", False)) and norm_text(top.get("match_type")) == "exact":
                d1 = d1_trusted_value
            elif self._feature_on("enable_d1_middle_tier", default=True):
                if self._has_verifiable_mid_tier_manufacturer_evidence(product):
                    d1 = d1_mid_tier_value

        has_full_disclosure = self._has_full_disclosure(product)
        d2 = 1.0 if has_full_disclosure else 0.0

        bonus_features = md.get("bonus_features", {})
        d3 = 0.5 if bool(product.get("claim_physician_formulated", bonus_features.get("physician_formulated", False))) else 0.0

        region = norm_text(product.get("manufacturing_region") or md.get("country_of_origin", {}).get("country"))

        # L2 (2026-04): D4 is now config-driven. Supports two shapes:
        #   1. Object: {"points": 1.0, "accepted_regions": ["usa", ...]}
        #   2. Legacy scalar: 1.0 (falls back to the default 12-country set)
        # The default set below is the baked-in fallback for legacy scalar
        # configs — it matches the pre-refactor hardcoded set exactly so
        # existing scores don't drift.
        default_high_std_regions = {
            "usa",
            "eu",
            "uk",
            "germany",
            "switzerland",
            "japan",
            "canada",
            "australia",
            "new zealand",
            "norway",
            "sweden",
            "denmark",
        }
        d4_cfg = self.config.get("section_D_brand_trust", {}).get(
            "D4_high_standard_region"
        )
        if isinstance(d4_cfg, dict):
            d4_value = as_float(d4_cfg.get("points"), 1.0) or 1.0
            configured_regions = d4_cfg.get("accepted_regions")
            if isinstance(configured_regions, list) and configured_regions:
                high_std_regions = {
                    norm_text(r) for r in configured_regions if r
                }
            else:
                high_std_regions = default_high_std_regions
        else:
            # Legacy scalar form
            d4_value = as_float(d4_cfg, 1.0) or 1.0
            high_std_regions = default_high_std_regions

        d4 = 0.0
        if bool(md.get("country_of_origin", {}).get("high_regulation_country", False)):
            d4 = d4_value
        elif region in high_std_regions:
            d4 = d4_value

        d5 = 0.5 if bool(product.get("has_sustainable_packaging", bonus_features.get("sustainability_claim", False))) else 0.0

        tail_cap = as_float(
            self.config.get("section_D_brand_trust", {}).get("D3_D4_D5_combined_cap"),
            2.0,
        ) or 2.0
        tail = min(tail_cap, d3 + d4 + d5)
        total = min(section_max, d1 + d2 + tail)

        return {
            "score": round(total, 2),
            "max": round(section_max, 2),
            "D1": round(d1, 2),
            "D2": round(d2, 2),
            "D3": round(d3, 2),
            "D4": round(d4, 2),
            "D5": round(d5, 2),
        }

    # ------------------------------------------------------------------
    # Section E – EPA+DHA Dose Adequacy
    # ------------------------------------------------------------------

    _EPA_DHA_CANONICAL_IDS: frozenset = frozenset({"epa", "dha", "epa_dha"})

    def _compute_epa_dha_per_day(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Compute total EPA+DHA mg per day from labelled per-serving amounts × servings/day.

        Amounts in ingredient_quality_data represent per-SERVING quantities as declared in
        the Supplement Facts panel (e.g. 360 mg EPA per 2-softgel serving).  We multiply
        by servings_per_day from serving_basis (enricher-computed) to get daily totals.
        Note: "serving" here is the full serving size unit (may be multiple softgels),
        not per individual pill.

        Returns a dict with keys:
          has_explicit_dose (bool)
          per_day_min  (float | None) – conservative estimate (min servings/day)
          per_day_max  (float | None) – liberal estimate    (max servings/day)
          per_day_mid  (float | None) – midpoint used for band lookup
          epa_mg_per_unit   (float)
          dha_mg_per_unit   (float)
          epa_dha_mg_per_unit (float)
          servings_per_day_min (float | None)
          servings_per_day_max (float | None)
        """
        ingredients = self._get_active_ingredients(product)
        epa_mg = 0.0
        dha_mg = 0.0
        has_dose = False

        for ing in ingredients:
            cid = norm_text(ing.get("canonical_id") or "")
            if cid not in self._EPA_DHA_CANONICAL_IDS:
                continue
            # Skip blend-level totals and parent-total duplicates
            if ing.get("is_proprietary_blend") or ing.get("is_blend_header"):
                continue
            if ing.get("is_parent_total"):
                continue

            qty = as_float(ing.get("quantity"), None)
            if qty is None or qty <= 0:
                continue
            unit = norm_text(ing.get("unit_normalized") or ing.get("unit") or "")

            # Convert quantity to mg
            if unit in {"mg", "milligram", "milligrams"}:
                mg_val = qty
            elif unit in {"g", "gram", "grams"}:
                mg_val = qty * 1000.0
            elif unit in {"mcg", "ug", "µg", "microgram", "micrograms"}:
                mg_val = qty / 1000.0
            else:
                # Unknown unit – skip to avoid nonsensical values
                continue

            has_dose = True
            if cid == "epa":
                epa_mg += mg_val
            elif cid == "dha":
                dha_mg += mg_val
            elif cid == "epa_dha":
                # Combined EPA/DHA row: the mg_val is the TOTAL of both.
                # Split evenly to avoid double-counting (500mg total → 250 EPA + 250 DHA).
                # Products listing EPA and DHA separately will hit the branches above.
                epa_mg += mg_val * 0.5
                dha_mg += mg_val * 0.5

        _empty = {
            "has_explicit_dose": False,
            "per_day_min": None,
            "per_day_max": None,
            "per_day_mid": None,
            "epa_mg_per_unit": 0.0,
            "dha_mg_per_unit": 0.0,
            "epa_dha_mg_per_unit": 0.0,
            "servings_per_day_min": None,
            "servings_per_day_max": None,
        }

        # RETIRED 2026-05-23: the fish-oil parent-mass fallback (Sprint E1.3.3,
        # `fish_oil_parent_mass_fallback` config) is removed by product policy.
        # Parent fish-oil / krill-oil mass must NEVER be used to infer EPA+DHA:
        # a "Fish Oil 1000 mg" label is not equivalent to "EPA+DHA 1000 mg",
        # and inferring otherwise overstates the disclosed clinical evidence.
        # If EPA/DHA are not explicitly labelled, the product scores as
        # not-dose-evaluable (no omega-3 dose bonus, no implicit credit).
        # The config key is retained as `enabled: false` for backward-
        # compatible config files; any value is now ignored at runtime.
        # See test_fish_oil_nested_propagation.py for the no-op regression.

        if not has_dose:
            return _empty

        # -- Resolve servings-per-day --
        # Primary: serving_basis (richer, enricher-computed)
        sb = product.get("serving_basis") or {}
        spd_min = as_float(sb.get("min_servings_per_day"), None)
        spd_max = as_float(sb.get("max_servings_per_day"), None)

        # Fallback: dosage_normalization.serving_basis
        # Important: only fill in the *missing* value so we don't clobber a good value
        # that was already resolved from serving_basis above (e.g. DSLD provides
        # minDailyServings but not maxDailyServings → spd_min=3, spd_max=None).
        if spd_min is None or spd_max is None:
            dn_sb = ((product.get("dosage_normalization") or {}).get("serving_basis") or {})
            if spd_min is None:
                spd_min = as_float(dn_sb.get("servings_per_day_min"), None)
            if spd_max is None:
                spd_max = as_float(dn_sb.get("servings_per_day_max"), None)

        # Guard: default to 1 serving/day if still missing or non-positive
        if not spd_min or spd_min <= 0:
            spd_min = 1.0
        if not spd_max or spd_max <= 0:
            spd_max = spd_min

        total_per_unit = epa_mg + dha_mg
        per_day_min = total_per_unit * spd_min
        per_day_max = total_per_unit * spd_max
        per_day_mid = (per_day_min + per_day_max) / 2.0

        return {
            "has_explicit_dose": True,
            "per_day_min": round(per_day_min, 1),
            "per_day_max": round(per_day_max, 1),
            "per_day_mid": round(per_day_mid, 1),
            "epa_mg_per_unit": round(epa_mg, 1),
            "dha_mg_per_unit": round(dha_mg, 1),
            "epa_dha_mg_per_unit": round(total_per_unit, 1),
            "servings_per_day_min": spd_min,
            "servings_per_day_max": spd_max,
        }

    @classmethod
    def _is_omega3_form_disclosed(cls, product: Dict[str, Any]) -> bool:
        """Return True when the omega molecular form is disclosed anywhere
        the v4 omega scorer recognizes it.

        Used to emit form_disclosed=False on the omega3_breakdown so the UI
        can explain why no premium-form credit (A2) was awarded even though
        EPA/DHA dose is disclosed.
        """
        from scoring_v4.modules.omega_formulation import _detect_form

        # v4 is the production source of truth for omega form detection. It
        # reads product names, label text, statements, and companion ingredient
        # rows; the fallback below preserves legacy unit-test shapes that only
        # provide activeIngredients/active_ingredients.
        if _detect_form(product if isinstance(product, dict) else {}) != "undefined":
            return True

        iqd = product.get("ingredient_quality_data") if isinstance(product, dict) else None
        ingredients = []
        for source in (
            product.get("activeIngredients") if isinstance(product, dict) else None,
            product.get("active_ingredients") if isinstance(product, dict) else None,
            iqd.get("ingredients_scorable") if isinstance(iqd, dict) else None,
            iqd.get("ingredients") if isinstance(iqd, dict) else None,
        ):
            ingredients.extend(safe_list(source))
        for ing in ingredients:
            if not isinstance(ing, dict):
                continue
            cid = norm_text(ing.get("canonical_id") or "")
            if cid not in cls._EPA_DHA_CANONICAL_IDS:
                continue
            # Build a haystack from any free-text form descriptors on the entry
            haystack_parts = [
                ing.get("matched_form") or "",
                ing.get("form") or "",
                ing.get("source") or "",
            ]
            for form in safe_list(ing.get("forms")):
                if isinstance(form, dict):
                    haystack_parts.append(form.get("name") or "")
                    haystack_parts.append(form.get("ingredientGroup") or "")
                elif isinstance(form, str):
                    haystack_parts.append(form)
            haystack = " ".join(p for p in haystack_parts if p)
            if _form_vocab.matches_premium_omega3_form(haystack):
                return True
        return False

    @staticmethod
    def _has_opaque_omega3_blend(product: Dict[str, Any]) -> bool:
        """Detect if the product carries an opaque proprietary blend
        (`disclosure_level=none`) whose name OR child ingredients suggest
        omega-3 content. Used to flag bonus_missed_due_to_opacity in two
        cases:

        1. Zero EPA/DHA detected at all — bonus would be 0 anyway.
        2. Some EPA/DHA detected but per_day below the smallest scoring
           band (250 mg) — could be undisclosed amounts buried in the blend.

        Per executive principle 2026-05-01: this DETECTS the opacity, it
        does NOT estimate the dose. UI surfaces the cause without inflating
        the score.
        """
        blends = (
            safe_list(product.get("proprietary_blends"))
            or safe_list((product.get("proprietary_data") or {}).get("blends"))
            or []
        )
        for b in blends:
            if not isinstance(b, dict):
                continue
            if b.get("disclosure_level") != "none":
                continue
            blend_name = b.get("name") or ""
            if _OPAQUE_OMEGA3_BLEND_PATTERN.search(blend_name):
                return True
            # Or any child ingredient is omega-3-class
            for child in (
                b.get("ingredients") or b.get("subIngredients")
                or b.get("components") or []
            ):
                if not isinstance(child, dict):
                    continue
                cname = child.get("name") or ""
                if _OPAQUE_OMEGA3_BLEND_PATTERN.search(cname):
                    return True
        return False

    def _compute_legacy_section_e(self, product: Dict[str, Any], flags: List[str]) -> Dict[str, Any]:
        """Section E – EPA+DHA Dose Adequacy (up to 2.0 bonus points).

        Applicable only to products with explicit per-unit EPA and/or DHA amounts.
        Band thresholds anchored to primary clinical sources (see scoring_config.json
        section_E_dose_adequacy._band_sources).
        """
        section_max = self._section_max("e", 2.0)
        e_cfg = self.config.get("section_E_dose_adequacy", {}) or {}
        bands = list(e_cfg.get("bands", []) or [])

        dose_data = self._compute_epa_dha_per_day(product)

        if not dose_data.get("has_explicit_dose"):
            # Transparency flag: when EPA/DHA bonus is 0 because the
            # ingredient is buried in an opaque proprietary blend, surface
            # the reason so the UI can distinguish "doesn't contain omega-3"
            # from "contains omega-3 but undisclosed". Per executive feedback
            # 2026-05-01: do NOT estimate the dose (would violate the
            # deterministic principle); only flag the cause.
            opaque_omega3_blend = self._has_opaque_omega3_blend(product)

            result = {
                "score": 0.0,
                "max": 0.0,       # 0 max signals "not applicable" to callers / display
                "applicable": False,
            }
            if opaque_omega3_blend:
                result["bonus_missed_due_to_opacity"] = True
                result["bonus_missed_reason"] = (
                    "EPA/DHA breakdown not disclosed (ingredient appears in a "
                    "proprietary blend without per-component amounts)."
                )
                if "OMEGA3_BONUS_MISSED_OPAQUE_BLEND" not in flags:
                    flags.append("OMEGA3_BONUS_MISSED_OPAQUE_BLEND")
            return result

        # Use midpoint of min/max daily range for band lookup
        per_day = as_float(dose_data.get("per_day_mid"), 0.0) or 0.0

        e_score = 0.0
        dose_band_label = "below_efsa_ai"
        prescription_dose = False

        # Evaluate bands highest-threshold first
        sorted_bands = sorted(bands, key=lambda b: as_float(b.get("min_mg_day"), 0) or 0, reverse=True)
        for band in sorted_bands:
            threshold = as_float(band.get("min_mg_day"), 0) or 0.0
            if per_day >= threshold:
                e_score = min(section_max, as_float(band.get("score"), 0.0) or 0.0)
                dose_band_label = band.get("label") or dose_band_label
                band_flag = band.get("flag")
                if band_flag:
                    prescription_dose = True
                    if band_flag not in flags:
                        flags.append(band_flag)
                break

        result = {
            "score": round(e_score, 2),
            "max": round(section_max, 2),
            "applicable": True,
            "dose_band": dose_band_label,
            "per_day_mid_mg": dose_data.get("per_day_mid"),
            "per_day_min_mg": dose_data.get("per_day_min"),
            "per_day_max_mg": dose_data.get("per_day_max"),
            "epa_mg_per_unit": dose_data.get("epa_mg_per_unit"),
            "dha_mg_per_unit": dose_data.get("dha_mg_per_unit"),
            "prescription_dose": prescription_dose,
        }

        # Partial-disclosure opacity flag (extension 2026-05-01):
        # Fire OMEGA3_BONUS_MISSED_OPAQUE_BLEND when SOME EPA/DHA was
        # detected but per_day is below the smallest scoring band (250 mg)
        # AND an opaque omega-class blend is present. This catches the
        # "Real Krill" pattern: 63 mg labeled + hidden Antarctic Krill Oil
        # Complex. The flag is INFORMATIONAL (no score change) — it only
        # explains WHY the bonus is 0 so the UI can distinguish "below
        # threshold" from "below threshold AND undisclosed amounts hidden
        # in opaque blend". Product is NOT penalized further (B5 penalty
        # already handles the opacity scoring side); we want to be
        # accurate without being harsh on real products.
        #
        # Strict trigger:
        #   - e_score == 0 (no omega-3 bonus earned at all)
        #   - has_explicit_dose=True (some EPA/DHA labeled, just sub-threshold)
        #   - opaque omega blend present
        # Products that earned ANY partial credit (efsa_ai_zone 0.5+) do
        # NOT trigger this flag.
        if e_score == 0.0 and self._has_opaque_omega3_blend(product):
            result["bonus_missed_due_to_opacity"] = True
            result["bonus_missed_reason"] = (
                "Labeled EPA+DHA below scoring threshold; additional omega-3 "
                "amounts may be in an undisclosed proprietary blend."
            )
            if "OMEGA3_BONUS_MISSED_OPAQUE_BLEND" not in flags:
                flags.append("OMEGA3_BONUS_MISSED_OPAQUE_BLEND")

        return result

    @staticmethod
    def _build_legacy_section_e(section_a: Dict[str, Any]) -> Dict[str, Any]:
        """Build backward-compatible Section E breakdown from the omega3 category bonus.

        Downstream consumers (tests, Flutter, exports) that read breakdown["E"]
        get the same shape they expect, but the score now comes from A's
        omega3_dose_bonus rather than a standalone section.
        """
        o3 = section_a.get("omega3_breakdown", {})
        applicable = o3.get("applicable", False)
        # Read max from omega3_breakdown (embedded by _compute_omega3_dose_bonus)
        # so legacy display stays in sync with the canonical config max. Falls
        # back to 2.0 (current canonical cap) when not present.
        bonus_max = o3.get("max", 2.0) if applicable else 0.0
        result: Dict[str, Any] = {
            "score": section_a.get("omega3_dose_bonus", 0.0),
            "max": bonus_max,
            "applicable": applicable,
            "_note": "Legacy compat — omega-3 dose is now a category bonus inside Ingredient Quality",
        }
        if applicable:
            for key in ("dose_band", "per_day_mid_mg", "per_day_min_mg", "per_day_max_mg",
                        "epa_mg_per_unit", "dha_mg_per_unit", "prescription_dose"):
                if key in o3:
                    result[key] = o3[key]
        # Always propagate transparency fields if set (apply equally to
        # not-applicable + applicable-but-zero-score cases)
        for key in ("bonus_missed_due_to_opacity", "bonus_missed_reason"):
            if key in o3:
                result[key] = o3[key]
        return result

    # ---------------------------------------------------------------------
    # Legacy scorer method aliases
    # ---------------------------------------------------------------------

    # Keep the old private method surface during the semantic rename rollout.
    # Several tests and downstream utilities still call these methods directly.
    def _evaluate_b0(self, product: Dict[str, Any]) -> Dict[str, Any]:
        return self._evaluate_safety_gate(product)

    def _score_a1(self, product: Dict[str, Any], supp_type: str) -> float:
        return self._compute_bioavailability_score(product, supp_type)

    def _score_a2(self, product: Dict[str, Any]) -> float:
        return self._compute_premium_forms_bonus(product)

    def _score_a3(self, product: Dict[str, Any]) -> float:
        return self._compute_delivery_score(product)

    def _score_a4(self, product: Dict[str, Any]) -> float:
        return self._compute_absorption_bonus(product)

    def _score_a5(self, product: Dict[str, Any]) -> Dict[str, float]:
        return self._compute_formulation_bonus(product)

    def _score_a6(self, product: Dict[str, Any], supp_type: str) -> float:
        return self._compute_single_efficiency_bonus(product, supp_type)

    def _score_probiotic_bonus(self, product: Dict[str, Any], supp_type: str) -> Dict[str, float]:
        return self._compute_probiotic_category_bonus(product, supp_type)

    def _score_section_a(
        self,
        product: Dict[str, Any],
        supp_type: str,
        flags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return self._compute_ingredient_quality_score(product, supp_type, flags=flags)

    def _score_b1(self, product: Dict[str, Any], b_cfg: Dict[str, Any] = None) -> float:
        return self._compute_harmful_additives_penalty(product, b_cfg)

    def _score_b2(self, product: Dict[str, Any], b_cfg: Dict[str, Any] = None) -> float:
        return self._compute_allergen_penalty(product, b_cfg)

    def _score_b4(self, product: Dict[str, Any], supp_type: str) -> Dict[str, float]:
        return self._compute_certifications_bonus(product, supp_type)

    def _score_b5(self, product: Dict[str, Any], flags: List[str], b_cfg: Dict[str, Any] = None) -> float:
        return self._compute_proprietary_blend_penalty(product, flags, b_cfg)

    def _score_b6(self, product: Dict[str, Any], flags: List[str], b_cfg: Dict[str, Any] = None) -> float:
        return self._compute_disease_claims_penalty(product, flags, b_cfg)

    def _score_b7(
        self,
        product: Dict[str, Any],
        flags: List[str],
        b_cfg: Dict[str, Any] = None,
    ) -> Tuple[float, List[Dict[str, Any]]]:
        return self._compute_dose_safety_penalty(product, flags, b_cfg)

    def _score_section_b(
        self,
        product: Dict[str, Any],
        supp_type: str,
        b0_moderate_penalty: float,
        flags: List[str],
    ) -> Dict[str, Any]:
        return self._compute_safety_purity_score(product, supp_type, b0_moderate_penalty, flags)

    def _score_section_c(self, product: Dict[str, Any], flags: List[str]) -> Dict[str, Any]:
        return self._compute_evidence_score(product, flags)

    def _score_section_d(self, product: Dict[str, Any]) -> Dict[str, Any]:
        return self._compute_brand_trust_score(product)

    def _score_section_e(self, product: Dict[str, Any], flags: List[str]) -> Dict[str, Any]:
        return self._compute_legacy_section_e(product, flags)

    def _manufacturer_violation_penalty(self, product: Dict[str, Any]) -> float:
        return self._compute_manufacturer_violation_penalty(product)

    def _build_badges(self, product: Dict[str, Any], verdict: str) -> List[Dict[str, str]]:
        badges: List[Dict[str, str]] = []
        if verdict in {"BLOCKED", "UNSAFE", "NOT_SCORED", "NUTRITION_ONLY"}:
            return badges
        if self._has_full_disclosure(product):
            badges.append(
                {
                    "id": "FULL_DISCLOSURE",
                    "label": "FULL DISCLOSURE",
                    "description": "This product lists exact amounts for every active ingredient.",
                }
            )
        return badges

    def _resolve_percentile_category(
        self,
        product: Dict[str, Any],
        scored: Dict[str, Any],
    ) -> Tuple[str, str, str, Optional[float], List[str]]:
        def _stable_key(value: str) -> str:
            return re.sub(r"[^a-z0-9]+", "_", norm_text(value)).strip("_")

        # SP-2.8 (2026-05-21): taxonomy is the source of truth for product
        # class. Prefer `supplement_taxonomy.percentile_category` over the
        # legacy explicit field — keeps the scorer aligned with the export
        # path (build_final_db) and the taxonomy classifier itself.
        # Legacy paths remain as fallback for old enriched batches.
        taxonomy = product.get("supplement_taxonomy")
        if isinstance(taxonomy, dict):
            tax_category = norm_text(taxonomy.get("percentile_category"))
            if tax_category:
                category_key = _stable_key(tax_category)
                category_label = re.sub(r"[_-]+", " ", tax_category).strip().title()
                confidence = as_float(taxonomy.get("classification_confidence"), None)
                reasons = taxonomy.get("classification_reasons")
                signals = (
                    [str(item) for item in reasons if item is not None]
                    if isinstance(reasons, list)
                    else []
                )
                return category_key, category_label, "taxonomy_v2", confidence, signals

        explicit_category = norm_text(product.get("percentile_category"))
        explicit_label = str(product.get("percentile_category_label") or "").strip()
        explicit_source = norm_text(product.get("percentile_category_source"))
        explicit_confidence = as_float(product.get("percentile_category_confidence"), None)
        explicit_signals_raw = product.get("percentile_category_signals")
        explicit_signals = (
            [str(item) for item in explicit_signals_raw if item is not None]
            if isinstance(explicit_signals_raw, list)
            else []
        )

        if explicit_category:
            category_key = _stable_key(explicit_category)
            category_label = explicit_label or re.sub(r"[_-]+", " ", explicit_category).strip().title()
            source = explicit_source or "explicit"
            return category_key, category_label, source, explicit_confidence, explicit_signals

        category = ""
        supplement_type = product.get("supplement_type", {})
        if isinstance(supplement_type, dict):
            for key in ("category", "subtype", "sub_type", "type"):
                value = norm_text(supplement_type.get(key))
                if value:
                    category = value
                    break
        else:
            category = norm_text(supplement_type)

        if not category:
            for key in ("product_category", "category", "primary_category"):
                value = norm_text(product.get(key))
                if value:
                    category = value
                    break

        if not category:
            category = norm_text(scored.get("supp_type")) or "all supplements"

        form = ""
        for key in ("dosage_form", "form", "product_form", "serving_form"):
            value = norm_text(product.get(key))
            if value:
                form = value
                break

        category_label = re.sub(r"[_-]+", " ", category).strip()
        if form:
            form_label = re.sub(r"[_-]+", " ", form).strip()
            if form_label.endswith("s"):
                category_label = f"{category_label} {form_label}"
            else:
                category_label = f"{category_label} {form_label}s"

        category_label = category_label.strip() or "supplements"
        category_key = _stable_key(category_label)
        return category_key, category_label, "fallback_scorer", None, []

    def _attach_category_percentiles(
        self,
        products: List[Dict[str, Any]],
        scored_products: List[Dict[str, Any]],
    ) -> None:
        if not products or len(products) != len(scored_products):
            return

        cohorts: Dict[str, List[Tuple[int, float, str, str, Optional[float], List[str]]]] = defaultdict(list)
        for idx, (product, scored) in enumerate(zip(products, scored_products)):
            score_100 = as_float(scored.get("score_100_equivalent"), None)
            if score_100 is None:
                continue
            category_key, category_label, category_source, category_confidence, category_signals = (
                self._resolve_percentile_category(product, scored)
            )
            if not category_key:
                continue
            cohorts[category_key].append(
                (
                    idx,
                    score_100,
                    category_label,
                    category_source,
                    category_confidence,
                    category_signals,
                )
            )

        for category_key, entries in cohorts.items():
            cohort_size = len(entries)
            if cohort_size < self._CATEGORY_PERCENTILE_MIN_COHORT:
                for idx, _, category_label, category_source, category_confidence, category_signals in entries:
                    scored_products[idx]["category_percentile"] = {
                        "available": False,
                        "reason": "insufficient_cohort_size",
                        "category_key": category_key,
                        "category_label": category_label,
                        "category_source": category_source,
                        "category_confidence": category_confidence,
                        "category_signals": category_signals,
                        "cohort_size": cohort_size,
                    }
                continue

            scores = [score for _, score, _, _, _, _ in entries]
            for idx, score, category_label, category_source, category_confidence, category_signals in entries:
                higher_count = sum(1 for value in scores if value > score)
                equal_count = sum(1 for value in scores if value == score)
                rank = higher_count + ((equal_count + 1.0) / 2.0)
                top_percent = round(clamp(0.0, 100.0, (rank / cohort_size) * 100.0), 1)
                percentile_rank = round(100.0 - top_percent, 1)
                scored_products[idx]["category_percentile"] = {
                    "available": True,
                    "category_key": category_key,
                    "category_label": category_label,
                    "category_source": category_source,
                    "category_confidence": category_confidence,
                    "category_signals": category_signals,
                    "cohort_size": cohort_size,
                    "top_percent": top_percent,
                    "percentile_rank": percentile_rank,
                    "text": f"Among {category_label}: Top {top_percent}%",
                }
                scored_products[idx]["category_percentile_text"] = (
                    f"Among {category_label}: Top {top_percent}%"
                )

    def _has_verifiable_mid_tier_manufacturer_evidence(self, product: Dict[str, Any]) -> bool:
        cert_data = product.get("certification_data", {}) or {}
        gmp = cert_data.get("gmp", {}) or {}
        if bool(gmp.get("nsf_gmp", False)) or bool(gmp.get("fda_registered", False)):
            return True

        named_programs = safe_list(product.get("named_cert_programs"))
        if not named_programs:
            programs = cert_data.get("third_party_programs", {}).get("programs", [])
            if isinstance(programs, list):
                named_programs = [p.get("name") if isinstance(p, dict) else p for p in programs]

        for program in named_programs:
            text = norm_text(program)
            if not text:
                continue
            if "usp" in text:
                return True
            if "nsf" in text:
                return True
            if "gmp" in text and "cert" in text:
                return True

        return False

    # Graduated aggregate cap per manufacture_deduction_expl.json v2.2 (Phase 2,
    # 2026-05-14). The default -25 cap is too lenient for repeat Class-I
    # drug-spike actors. See docs/handoff/2026-05-14_phase2_graduated_cap_impact.md.
    #
    # These constants are the canonical Python-side source. They MUST match
    # scripts/data/manufacture_deduction_expl.json::total_deduction_cap_graduated;
    # drift is caught by test_manufacture_deduction_expl_contract.py +
    # test_graduated_cap_score_movements.py.
    _MFG_CAP_DEFAULT = -25.0
    _MFG_CAP_TWO_CLASS_I = -35.0
    _MFG_CAP_THREE_OR_MORE_CLASS_I = -50.0
    _CLASS_I_LOOKBACK_DAYS = 3 * 365  # 3-year window

    @staticmethod
    def _count_class_i_in_3_years(items: List[Dict[str, Any]], today=None) -> int:
        """Count Class-I (severity='critical') violations within the last 3 years.

        Used to resolve the per-manufacturer aggregate cap. The graduated cap
        intensifies as a manufacturer accrues repeat Class-I recalls — the
        lookback is fixed at 3 years per the framework's recency-modifier
        ranges (see manufacture_deduction_expl.json::modifiers.RECENCY)."""
        from datetime import date as _date
        if today is None:
            today = _date.today()
        count = 0
        for item in items or []:
            if not isinstance(item, dict):
                continue
            if (item.get("severity_level") or "").lower() != "critical":
                continue
            d = item.get("date") or ""
            try:
                dt = _date.fromisoformat(str(d))
            except (TypeError, ValueError):
                continue
            if (today - dt).days <= SupplementScorer._CLASS_I_LOOKBACK_DAYS:
                count += 1
        return count

    @classmethod
    def _resolve_manufacturer_cap(cls, class_i_count_3y: int) -> float:
        """Map Class-I-in-3yr count to the appropriate aggregate cap floor.

        Source of truth: manufacture_deduction_expl.json::total_deduction_cap_graduated.
        Mirrored here for backwards-compat with older enrichment outputs that
        don't carry deduction_expl context."""
        if class_i_count_3y >= 3:
            return cls._MFG_CAP_THREE_OR_MORE_CLASS_I
        if class_i_count_3y >= 2:
            return cls._MFG_CAP_TWO_CLASS_I
        return cls._MFG_CAP_DEFAULT

    def _compute_manufacturer_violation_penalty(self, product: Dict[str, Any]) -> float:
        violations = product.get("manufacturer_data", {}).get("violations", {})

        deduction: Optional[float] = None
        items: List[Dict[str, Any]] = []
        if isinstance(violations, dict):
            deduction = as_float(violations.get("total_deduction_applied"), None)
            items = safe_list(violations.get("violations"))
            if deduction is None and items:
                # Backward-compatible fallback for older enrichment outputs.
                if len(items) == 1:
                    deduction = as_float(
                        items[0].get("total_deduction_applied", items[0].get("total_deduction")),
                        None,
                    )
                else:
                    total = 0.0
                    for item in items:
                        total += as_float(
                            item.get("total_deduction_applied", item.get("total_deduction")),
                            0.0,
                        ) or 0.0
                    deduction = total
        elif isinstance(violations, list):
            items = list(violations)
            total = 0.0
            for item in violations:
                total += as_float(
                    item.get("total_deduction_applied", item.get("total_deduction")),
                    0.0,
                ) or 0.0
            deduction = total

        if deduction is None:
            return 0.0

        # Apply the graduated aggregate cap (v2.2). Manufacturers with 0-1
        # Class-I in 3yr stay at the default -25 floor; 2 in 3yr → -35;
        # 3+ in 3yr → -50. Stored as negative, added directly after section sum.
        class_i_3y = self._count_class_i_in_3_years(items)
        cap = self._resolve_manufacturer_cap(class_i_3y)
        return max(float(deduction), cap)

    # ---------------------------------------------------------------------
    # Output helpers
    # ---------------------------------------------------------------------

    _DEFAULT_GRADE_SCALE: List[Tuple[str, float]] = [
        ("Exceptional", 90.0),
        ("Excellent", 80.0),
        ("Good", 70.0),
        ("Fair", 60.0),
        ("Below Avg", 50.0),
        ("Low", 32.0),
        ("Very Poor", 0.0),
    ]

    def _grade_word(self, score_100_equivalent: float, verdict: str) -> Optional[str]:
        if verdict in {"BLOCKED", "UNSAFE", "NOT_SCORED", "NUTRITION_ONLY"}:
            return None

        # Build (label, min) pairs from config, descending by min, with a safe
        # fallback to the hardcoded default if the config block is missing.
        grade_scale_cfg = self.config.get("grade_scale", {}) or {}
        pairs: List[Tuple[str, float]] = []
        for label, spec in grade_scale_cfg.items():
            if label.startswith("_"):
                continue
            if not isinstance(spec, dict):
                continue
            min_val = as_float(spec.get("min"), None)
            if min_val is None:
                continue
            pairs.append((label, float(min_val)))

        if not pairs:
            pairs = list(self._DEFAULT_GRADE_SCALE)

        pairs.sort(key=lambda kv: kv[1], reverse=True)

        for label, min_val in pairs:
            if score_100_equivalent >= min_val:
                return label
        # Fall through if nothing matches (shouldn't happen with a 0-min entry)
        return pairs[-1][0] if pairs else None

    @staticmethod
    def _is_food_shape_product(product: Dict[str, Any]) -> bool:
        """Sprint E1.7 — Bucket C discriminator.

        Returns True when the product_name contains a food-shape keyword
        (whey/casein/protein-powder/meal-replacement/etc.). Used by the
        verdict deriver to divert NOT_SCORED → NUTRITION_ONLY when DSLD
        upstream fails to capture the active ingredient (protein itself
        is not encoded in `ingredientRows` for many of these products).

        Substring match against the keyword list — case-insensitive,
        product_name-only. Form_factor is unreliable in DSLD (often
        None) so we don't depend on it.
        """
        name = norm_text(product.get("product_name"))
        if not name:
            return False
        return any(kw in name for kw in _FOOD_SHAPE_NAME_KEYWORDS)

    def _derive_verdict(
        self,
        b0: Dict[str, Any],
        mapping_gate: Dict[str, Any],
        flags: List[str],
        quality_score: Optional[float],
        product: Optional[Dict[str, Any]] = None,
    ) -> str:
        if b0.get("blocked"):
            return "BLOCKED"
        if b0.get("unsafe"):
            return "UNSAFE"
        if product is not None and is_nutrition_only_product(product):
            return "NUTRITION_ONLY"
        if mapping_gate.get("stop"):
            return "NOT_SCORED"
        if "BANNED_MATCH_REVIEW_NEEDED" in flags:
            return "CAUTION"
        if any(f in flags for f in ("B0_MODERATE_SUBSTANCE", "B0_HIGH_RISK_SUBSTANCE",
                                     "B0_WATCHLIST_SUBSTANCE")):
            return "CAUTION"
        poor_threshold = as_float(
            self.config.get("verdict_logic", {}).get("poor_threshold_quality_score"),
            32.0,
        )
        if poor_threshold is None:
            poor_threshold = 32.0
        if quality_score is not None and quality_score < poor_threshold:
            return "POOR"
        # Track A.1 / A.2a verdict ceiling — anchor products are never SAFE.
        # If the math would otherwise verdict SAFE, force CAUTION so the
        # downstream UI/user is signaled that this score came from a
        # limited-evidence (standardized-botanical or blend-header anchor) path.
        if (
            FLAG_STANDARDIZED_BOTANICAL_ANCHOR in flags
            or FLAG_BLEND_HEADER_ANCHOR in flags
        ):
            return "CAUTION"
        return "SAFE"

    @staticmethod
    def _derive_blocking_reason_from_scoring_gate(
        verdict: str,
        b0: Dict[str, Any],
        flags: List[str],
    ) -> Optional[str]:
        if b0.get("blocked"):
            return "banned_ingredient"
        if b0.get("unsafe"):
            reason = norm_text(b0.get("reason"))
            if "banned" in reason:
                return "banned_ingredient"
            if "recall" in reason:
                return "recalled_ingredient"
            return "safety_block"
        if verdict == "CAUTION" and "B0_HIGH_RISK_SUBSTANCE" in flags:
            return "high_risk_ingredient"
        return None

    def _build_core_output(
        self,
        product: Dict[str, Any],
        quality_score: Optional[float],
        verdict: str,
        breakdown: Dict[str, Any],
        flags: List[str],
        supp_type: str,
        unmapped_actives: List[str],
        unmapped_actives_total: int,
        unmapped_actives_excluding_banned_exact_alias: int,
        mapped_coverage: float,
        reason: Optional[str] = None,
        blocking_reason: Optional[str] = None,
        not_scorable_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        product_id = product.get("dsld_id", "unknown")
        product_name = product.get("product_name", "Unknown Product")
        section_a_max = self._section_max("a", 25.0)
        section_b_max = self._section_max("b", 30.0)
        section_c_max = self._section_max("c", 20.0)
        section_d_max = self._section_max("d", 5.0)
        section_e_max = self._section_max("e", 2.0)

        if quality_score is None:
            score_100_equivalent = None
            display = "N/A"
            display_100 = "N/A"
        else:
            score_100_equivalent = round((quality_score / 80.0) * 100.0, 1)
            display = f"{round(quality_score, 1)}/80"
            display_100 = f"{score_100_equivalent}/100"

        if verdict in {"BLOCKED", "UNSAFE"}:
            scoring_status = SCORING_STATUS_BLOCKED
            score_basis = SCORE_BASIS_SAFETY_BLOCK
        elif verdict == "NOT_SCORED":
            scoring_status = SCORING_STATUS_NOT_APPLICABLE
            score_basis = SCORE_BASIS_NO_SCORABLE
        elif verdict == "NUTRITION_ONLY":
            # Bucket C — DSLD upstream gap (food-shape product). No bioactive
            # score, but flags array still surfaces banned/harmful warnings.
            scoring_status = SCORING_STATUS_NOT_APPLICABLE
            score_basis = SCORE_BASIS_NUTRITION_ONLY
        else:
            scoring_status = SCORING_STATUS_SCORED
            # Track A.1 / A.2a — anchor-scored products get a dedicated
            # score_basis so downstream consumers (build_final_db, Flutter UI,
            # audits) can distinguish full-IQM-evidence scores from
            # conservative anchor-path scores. The two anchor paths are kept
            # distinct because they signal different evidence shapes:
            # standardized-botanical anchor implies validated marker evidence;
            # blend-header anchor only implies a real canonical_id at the
            # blend total dose.
            if FLAG_STANDARDIZED_BOTANICAL_ANCHOR in flags:
                score_basis = SCORE_BASIS_BOTANICAL_ANCHOR
            elif FLAG_BLEND_HEADER_ANCHOR in flags:
                score_basis = SCORE_BASIS_BLEND_HEADER_ANCHOR
            else:
                score_basis = SCORE_BASIS_BIOACTIVES

        # Backward-compatible safety_verdict for downstream scripts.
        if verdict == "POOR":
            safety_verdict = "SAFE"
        elif verdict == "NOT_SCORED":
            safety_verdict = "CAUTION"
        elif verdict == "NUTRITION_ONLY":
            # Same as NOT_SCORED for legacy consumers — flags still steer UI.
            safety_verdict = "CAUTION"
        else:
            safety_verdict = verdict

        iqd_contract_diagnostics = self._iqd_contract_diagnostics(product)
        mapped_coverage_applicable = verdict != "NUTRITION_ONLY"
        mapped_coverage_output = None if not mapped_coverage_applicable else round(mapped_coverage, 4)
        strict_scoring_contract = iqd_contract_diagnostics.get("strict_scoring_contract") or {
            "passed": iqd_contract_diagnostics.get("strict_contract_passed", False),
            "findings": iqd_contract_diagnostics.get("contract_findings", []),
            "zero_scorable_reason": iqd_contract_diagnostics.get("zero_scorable_reason"),
            "mapped_coverage_applicable": mapped_coverage_applicable,
        }
        if FLAG_STANDARDIZED_BOTANICAL_ANCHOR in flags:
            findings = list(safe_list(strict_scoring_contract.get("findings")))
            if "scored_via_standardized_botanical_anchor_path" not in findings:
                findings.append("scored_via_standardized_botanical_anchor_path")
            strict_scoring_contract = {
                **strict_scoring_contract,
                "findings": findings,
            }
        if FLAG_BLEND_HEADER_ANCHOR in flags:
            findings = list(safe_list(strict_scoring_contract.get("findings")))
            if "scored_via_blend_header_anchor_path" not in findings:
                findings.append("scored_via_blend_header_anchor_path")
            strict_scoring_contract = {
                **strict_scoring_contract,
                "findings": findings,
            }
        if verdict == "NUTRITION_ONLY":
            strict_scoring_contract = {
                **strict_scoring_contract,
                "passed": True,
                "reason": "nutrition_only_product_no_bioactive_scoring",
                "mapped_coverage_applicable": False,
            }
        output = {
            "dsld_id": product_id,
            "product_name": product_name,
            "brand_name": product.get("brand_name") or product.get("brandName", ""),
            "quality_score": round(quality_score, 1) if quality_score is not None else None,
            "score_80": round(quality_score, 1) if quality_score is not None else None,
            "score_100_equivalent": score_100_equivalent,
            "display": display,
            "display_100": display_100,
            "grade": self._grade_word(score_100_equivalent or 0.0, verdict),
            "verdict": verdict,
            "safety_verdict": safety_verdict,
            "blocking_reason": blocking_reason,
            "badges": self._build_badges(product, verdict),
            "category_percentile": None,
            "category_percentile_text": None,
            "percentile_category": (
                product.get("supplement_taxonomy", {}).get("percentile_category")
                or product.get("percentile_category")
            ),
            "percentile_category_label": product.get("percentile_category_label"),
            "percentile_category_source": (
                "taxonomy_v2" if product.get("supplement_taxonomy", {}).get("percentile_category")
                else product.get("percentile_category_source")
            ),
            "percentile_category_confidence": (
                product.get("supplement_taxonomy", {}).get("classification_confidence")
                or product.get("percentile_category_confidence")
            ),
            "percentile_category_signals": (
                product.get("supplement_taxonomy", {}).get("classification_reasons")
                or product.get("percentile_category_signals")
            ),
            "output_schema_version": self.OUTPUT_SCHEMA_VERSION,
            "scoring_status": scoring_status,
            "score_basis": score_basis,
            # Nullable diagnostic. Always emitted on the scored output for shape
            # consistency with sibling fields (blocking_reason, category_percentile);
            # None means "this product was scored" or "no diagnostic applies".
            # build_final_db decides whether to forward to the Flutter export.
            "not_scorable_reason": not_scorable_reason,
            "evaluation_stage": "safety" if verdict in {"BLOCKED", "UNSAFE"} else "scoring",
            "breakdown": breakdown,
            # Per-additive B1 applied-penalty tier (post-exemption) → build_final_db
            # colors the 'Other ingredients' dot (display_tone) by penalty applied.
            "_inactive_b1_applied_tier": product.get("_inactive_b1_applied_tier") or {},
            "flags": sorted(set(flags)),
            "supp_type": supp_type,
            "primary_type": product.get("primary_type") or product.get("supplement_taxonomy", {}).get("primary_type"),
            "secondary_type": product.get("secondary_type") or product.get("supplement_taxonomy", {}).get("secondary_type"),
            "supplement_taxonomy": product.get("supplement_taxonomy", {}),
            "unmapped_actives": unmapped_actives,
            "unmapped_actives_total": int(unmapped_actives_total),
            "unmapped_actives_excluding_banned_exact_alias": int(
                unmapped_actives_excluding_banned_exact_alias
            ),
            "mapped_coverage": mapped_coverage_output,
            "mapped_coverage_applicable": mapped_coverage_applicable,
            "scoring_metadata": {
                "scoring_version": self.VERSION,
                "output_schema_version": self.OUTPUT_SCHEMA_VERSION,
                "scored_date": datetime.now(timezone.utc).isoformat(),
                "enrichment_version": product.get("enrichment_version"),
                "scoring_status": scoring_status,
                "score_basis": score_basis,
                "verdict": verdict,
                "flags": sorted(set(flags)),
                "unmapped_actives_total": int(unmapped_actives_total),
                "unmapped_actives_excluding_banned_exact_alias": int(
                    unmapped_actives_excluding_banned_exact_alias
                ),
                "mapped_coverage": mapped_coverage_output,
                "mapped_coverage_applicable": mapped_coverage_applicable,
                "reason": reason,
                "blocking_reason": blocking_reason,
                "iqd_contract_diagnostics": iqd_contract_diagnostics,
                "scoring_ingredients_source": iqd_contract_diagnostics.get("scoring_ingredients_source"),
                "scoring_fallbacks_used": iqd_contract_diagnostics.get("scoring_fallbacks_used", []),
                "strict_scoring_contract": strict_scoring_contract,
            },
            "iqd_contract_diagnostics": iqd_contract_diagnostics,
            "scoring_ingredients_source": iqd_contract_diagnostics.get("scoring_ingredients_source"),
            "scoring_fallbacks_used": iqd_contract_diagnostics.get("scoring_fallbacks_used", []),
            "strict_scoring_contract": strict_scoring_contract,
            "section_scores": {
                "A_ingredient_quality": {
                    "score": breakdown.get("A", {}).get("score"),
                    "max": section_a_max,
                    "core_quality": breakdown.get("A", {}).get("core_quality"),
                    "category_bonus_total": breakdown.get("A", {}).get("category_bonus_total"),
                    "category_bonus_pool_cap": breakdown.get("A", {}).get("category_bonus_pool_cap"),
                },
                "B_safety_purity": {
                    "score": breakdown.get("B", {}).get("score"),
                    "max": section_b_max,
                },
                "C_evidence_research": {
                    "score": breakdown.get("C", {}).get("score"),
                    "max": section_c_max,
                },
                "D_brand_trust": {
                    "score": breakdown.get("D", {}).get("score"),
                    "max": section_d_max,
                },
                # Legacy E_dose_adequacy kept for backward compatibility with existing consumers.
                # Score contribution now comes from A's omega3_dose_bonus category bonus.
                "E_dose_adequacy": {
                    "score": breakdown.get("E", {}).get("score", 0.0),
                    "max": section_e_max,
                    "applicable": breakdown.get("E", {}).get("applicable", False),
                    "_deprecated": "Moved to A_ingredient_quality.omega3_dose_bonus in v3.3",
                },
            },
        }

        if product.get("match_ledger"):
            output["match_ledger"] = product["match_ledger"]
        if product.get("source_type"):
            output["source_type"] = product.get("source_type")
        if product.get("manual_product_provenance"):
            output["manual_product_provenance"] = product.get("manual_product_provenance")

        return output

    # ---------------------------------------------------------------------
    # Main scoring
    # ---------------------------------------------------------------------

    def score_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        product_id = product.get("dsld_id", "unknown")
        product_name = product.get("product_name", "Unknown Product")

        is_valid, issues = self.validate_enriched_product(product)
        if not is_valid:
            msg = f"Validation failed: {'; '.join(issues)}"
            self.logger.error("Product %s: %s", product_id, msg)
            return self._create_failed_score(product_id, product_name, msg)

        for issue in issues:
            self.logger.warning("Product %s: %s", product_id, issue)

        try:
            flags: List[str] = []
            existing_supp_type = ""
            raw_supp_type = product.get("supplement_type", {})
            if isinstance(raw_supp_type, dict):
                existing_supp_type = norm_text(raw_supp_type.get("type"))
            elif isinstance(raw_supp_type, str):
                existing_supp_type = norm_text(raw_supp_type)
            supp_type = self._classify_supplement_type(product)
            if existing_supp_type and existing_supp_type != norm_text(supp_type):
                flags.append("SUPPLEMENT_TYPE_REINFERRED")

            # Step 1: B0 immediate fail
            b0 = self._evaluate_safety_gate(product)
            section_a_max = self._section_max("a", 25.0)
            section_b_max = self._section_max("b", 30.0)
            section_c_max = self._section_max("c", 20.0)
            section_d_max = self._section_max("d", 5.0)
            section_e_max = self._section_max("e", 2.0)
            for flag in b0.get("flags", []):
                if flag not in flags:
                    flags.append(flag)

            # Compute mapping KPIs once so every output path reports consistent semantics.
            mapping_gate = self._mapping_gate(product)
            guard_overlap = mapping_gate.get("unmapped_actives_banned_exact_alias", [])
            if guard_overlap and not (b0.get("blocked") or b0.get("unsafe")):
                # Fail-safe: unmatched + banned exact/alias must never flow to SAFE/CAUTION.
                b0["unsafe"] = True
                b0["reason"] = (
                    "Unmapped active ingredient matched banned exact/alias: "
                    + ", ".join(sorted(set(guard_overlap)))
                )
                flags.append("UNMAPPED_BANNED_EXACT_ALIAS_GUARD")

            if b0.get("blocked"):
                breakdown = {
                    "A": {"score": 0.0, "max": section_a_max},
                    "B": {
                        "score": 0.0,
                        "max": section_b_max,
                        "B0": "BLOCKED",
                        "reason": b0.get("reason"),
                    },
                    "C": {"score": 0.0, "max": section_c_max},
                    "D": {"score": 0.0, "max": section_d_max},
                    "E": {"score": 0.0, "max": 0.0, "applicable": False},
                    "violation_penalty": 0.0,
                }
                return self._build_core_output(
                    product,
                    quality_score=None,
                    verdict="BLOCKED",
                    breakdown=breakdown,
                    flags=flags,
                    supp_type=supp_type,
                    unmapped_actives=mapping_gate.get("unmapped_actives", []),
                    unmapped_actives_total=mapping_gate.get("unmapped_actives_total", 0),
                    unmapped_actives_excluding_banned_exact_alias=mapping_gate.get(
                        "unmapped_actives_excluding_banned_exact_alias", 0
                    ),
                    mapped_coverage=mapping_gate.get("mapped_coverage", 0.0),
                    reason=b0.get("reason"),
                    blocking_reason="banned_ingredient",
                )

            if b0.get("unsafe"):
                breakdown = {
                    "A": {"score": 0.0, "max": section_a_max},
                    "B": {
                        "score": 0.0,
                        "max": section_b_max,
                        "B0": "UNSAFE",
                        "reason": b0.get("reason"),
                    },
                    "C": {"score": 0.0, "max": section_c_max},
                    "D": {"score": 0.0, "max": section_d_max},
                    "E": {"score": 0.0, "max": 0.0, "applicable": False},
                    "violation_penalty": 0.0,
                }
                return self._build_core_output(
                    product,
                    quality_score=0.0,
                    verdict="UNSAFE",
                    breakdown=breakdown,
                    flags=flags,
                    supp_type=supp_type,
                    unmapped_actives=mapping_gate.get("unmapped_actives", []),
                    unmapped_actives_total=mapping_gate.get("unmapped_actives_total", 0),
                    unmapped_actives_excluding_banned_exact_alias=mapping_gate.get(
                        "unmapped_actives_excluding_banned_exact_alias", 0
                    ),
                    mapped_coverage=mapping_gate.get("mapped_coverage", 0.0),
                    reason=b0.get("reason"),
                    blocking_reason=self._derive_blocking_reason_from_scoring_gate("UNSAFE", b0, flags),
                )

            # Step 2/3: type + mapping gate
            for flag in mapping_gate.get("flags", []):
                if flag not in flags:
                    flags.append(flag)

            if mapping_gate.get("stop"):
                verdict = self._derive_verdict(b0, mapping_gate, flags, None, product)
                breakdown = {
                    "A": {"score": 0.0, "max": section_a_max},
                    "B": {"score": 0.0, "max": section_b_max},
                    "C": {"score": 0.0, "max": section_c_max},
                    "D": {"score": 0.0, "max": section_d_max},
                    "E": {"score": 0.0, "max": 0.0, "applicable": False},
                    "violation_penalty": 0.0,
                }
                return self._build_core_output(
                    product,
                    quality_score=None,
                    verdict=verdict,
                    breakdown=breakdown,
                    flags=flags,
                    supp_type=supp_type,
                    unmapped_actives=mapping_gate.get("unmapped_actives", []),
                    unmapped_actives_total=mapping_gate.get("unmapped_actives_total", 0),
                    unmapped_actives_excluding_banned_exact_alias=mapping_gate.get(
                        "unmapped_actives_excluding_banned_exact_alias", 0
                    ),
                    mapped_coverage=mapping_gate.get("mapped_coverage", 0.0),
                    reason=mapping_gate.get("reason"),
                    not_scorable_reason=mapping_gate.get("not_scorable_reason"),
                )

            # Step 4: sections
            # Note: Section A now includes category bonuses (probiotic, omega-3 dose)
            # so it needs access to flags for the PRESCRIPTION_DOSE_OMEGA3 flag.
            section_a = self._compute_ingredient_quality_score(product, supp_type, flags=flags)

            # Section A zero-score diagnostic: when score=0, capture why
            if section_a["score"] == 0.0:
                section_a["zero_score_diagnostic"] = self._build_section_a_zero_diagnostic(product)
                if section_a["zero_score_diagnostic"]["skipped_ingredients"]:
                    flags.append("SECTION_A_ZERO_NO_SCORABLE_INGREDIENTS")
            section_b = self._compute_safety_purity_score(
                product,
                supp_type,
                b0_moderate_penalty=float(b0.get("moderate_penalty", 0.0) or 0.0),
                flags=flags,
            )
            section_c = self._compute_evidence_score(product, flags)
            section_d = self._compute_brand_trust_score(product)

            # Legacy Section E call kept for shadow comparison / backward compat output.
            # The actual scoring contribution now comes from section_a's omega3_dose_bonus.
            section_e_legacy = self._compute_legacy_section_e(product, [])  # isolated flags list

            quality_raw = (
                section_a["score"]
                + section_b["score"]
                + section_c["score"]
                + section_d["score"]
            )

            violation_penalty = self._compute_manufacturer_violation_penalty(product)
            if violation_penalty < 0:
                flags.append("MANUFACTURER_VIOLATION")
            quality_raw += violation_penalty
            quality_score = clamp(0.0, 80.0, quality_raw)

            # Track A.1 / A.2a — defensive cap for anchor-scored products.
            # Live-corpus simulation shows natural anchor scores land 22-53/100,
            # so the cap is mostly a safety net against unusual high-B + high-C
            # + high-D combinations. Default display_cap = 60.0 (= 48.0/80).
            # Both anchor paths share the same cap value.
            if (
                FLAG_STANDARDIZED_BOTANICAL_ANCHOR in flags
                or FLAG_BLEND_HEADER_ANCHOR in flags
            ):
                anchor_cfg_key = (
                    "standardized_botanical_anchor"
                    if FLAG_STANDARDIZED_BOTANICAL_ANCHOR in flags
                    else "blend_header_anchor"
                )
                anchor_cfg = (
                    self.config.get("section_A_ingredient_quality", {})
                    .get(anchor_cfg_key, {})
                    or {}
                )
                display_cap = as_float(anchor_cfg.get("display_cap"), 60.0) or 60.0
                quality_cap = (display_cap / 100.0) * 80.0
                if quality_score > quality_cap:
                    quality_score = quality_cap

            verdict = self._derive_verdict(b0, mapping_gate, flags, quality_score, product)
            blocking_reason = self._derive_blocking_reason_from_scoring_gate(verdict, b0, flags)

            breakdown = {
                "A": section_a,
                "B": section_b,
                "C": section_c,
                "D": section_d,
                # E kept for backward compat — score contribution now comes from A's omega3_dose_bonus
                "E": self._build_legacy_section_e(section_a),
                "violation_penalty": round(violation_penalty, 2),
                "quality_raw": round(quality_raw, 2),
            }

            return self._build_core_output(
                product,
                quality_score=quality_score,
                verdict=verdict,
                breakdown=breakdown,
                flags=flags,
                supp_type=supp_type,
                unmapped_actives=mapping_gate.get("unmapped_actives", []),
                unmapped_actives_total=mapping_gate.get("unmapped_actives_total", 0),
                unmapped_actives_excluding_banned_exact_alias=mapping_gate.get(
                    "unmapped_actives_excluding_banned_exact_alias", 0
                ),
                mapped_coverage=mapping_gate.get("mapped_coverage", 1.0),
                blocking_reason=blocking_reason,
            )

        except Exception as exc:
            self.logger.error("Product %s scoring error: %s", product_id, exc, exc_info=True)
            return self._create_failed_score(product_id, product_name, str(exc))

    def _create_failed_score(self, product_id: str, product_name: str, error_msg: str) -> Dict[str, Any]:
        """Create a failed score output with the SAME field set as _build_core_output.

        This ensures downstream consumers (build_final_db.py, Flutter) never crash
        on KeyError when accessing fields like section_scores or breakdown.
        """
        empty_breakdown = {
            "A": {"score": 0.0, "max": self._section_max("a", 25.0)},
            "B": {"score": 0.0, "max": self._section_max("b", 30.0)},
            "C": {"score": 0.0, "max": self._section_max("c", 20.0)},
            "D": {"score": 0.0, "max": self._section_max("d", 5.0)},
            "E": {"score": 0.0, "max": 0.0, "applicable": False},
            "violation_penalty": 0.0,
        }
        return {
            "dsld_id": product_id,
            "product_name": product_name,
            "brand_name": "",
            "quality_score": None,
            "score_80": None,
            "score_100_equivalent": None,
            "display": "Error",
            "display_100": "Error",
            "grade": None,
            "verdict": "NOT_SCORED",
            "safety_verdict": "UNKNOWN",
            "badges": [],
            "category_percentile": None,
            "category_percentile_text": None,
            "percentile_category": None,
            "percentile_category_label": None,
            "percentile_category_source": None,
            "percentile_category_confidence": None,
            "percentile_category_signals": [],
            "output_schema_version": self.OUTPUT_SCHEMA_VERSION,
            "scoring_status": "error",
            "score_basis": SCORE_BASIS_SCORING_ERROR,
            "evaluation_stage": "scoring",
            "breakdown": empty_breakdown,
            "flags": ["SCORING_ERROR"],
            "supp_type": "unknown",
            "unmapped_actives": [],
            "unmapped_actives_total": 0,
            "unmapped_actives_excluding_banned_exact_alias": 0,
            "mapped_coverage": 0.0,
            "error": error_msg,
            "section_scores": {
                "A_ingredient_quality": {"score": 0.0, "max": self._section_max("a", 25.0)},
                "B_safety_purity": {"score": 0.0, "max": self._section_max("b", 30.0)},
                "C_evidence_research": {"score": 0.0, "max": self._section_max("c", 20.0)},
                "D_brand_trust": {"score": 0.0, "max": self._section_max("d", 5.0)},
            },
            "scoring_metadata": {
                "scoring_version": self.VERSION,
                "output_schema_version": self.OUTPUT_SCHEMA_VERSION,
                "scored_date": datetime.now(timezone.utc).isoformat(),
                "scoring_status": "error",
                "score_basis": SCORE_BASIS_SCORING_ERROR,
                "error_details": error_msg,
            },
        }

    # ---------------------------------------------------------------------
    # Batch processing
    # ---------------------------------------------------------------------

    def process_batch(self, input_file: str, output_dir: str) -> Dict[str, Any]:
        with open(input_file, "r", encoding="utf-8") as f:
            products = json.load(f)
        if not isinstance(products, list):
            products = [products]

        scored_products: List[Dict[str, Any]] = []
        verdict_distribution: Dict[str, int] = defaultdict(int)

        for product in products:
            scored = self.score_product(product)
            scored_products.append(scored)
            verdict_distribution[scored.get("verdict", "UNKNOWN")] += 1

        # Percentiles require cohort context, so assign after batch scoring.
        self._attach_category_percentiles(products, scored_products)

        base_name = os.path.splitext(os.path.basename(input_file))[0]
        if base_name.startswith("enriched_"):
            base_name = base_name[9:]

        scored_dir = os.path.join(output_dir, "scored")
        os.makedirs(scored_dir, exist_ok=True)

        import tempfile

        output_file = os.path.join(scored_dir, f"scored_{base_name}.json")
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=scored_dir, suffix='.tmp', prefix='scored_'
        )
        try:
            with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
                json.dump(scored_products, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, output_file)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

        numeric_scores = [p["score_80"] for p in scored_products if p.get("score_80") is not None]
        avg_80 = sum(numeric_scores) / len(numeric_scores) if numeric_scores else 0.0
        error_count = sum(1 for p in scored_products if p.get("scoring_status") == "error")

        return {
            "total_products": len(products),
            "scored": len(numeric_scores),
            "errors": error_count,
            "blocked_or_not_scored": len(products) - len(numeric_scores) - error_count,
            "average_score_80": round(avg_80, 2),
            "average_score_100": round((avg_80 / 80.0) * 100.0, 2) if numeric_scores else 0.0,
            "verdict_distribution": dict(verdict_distribution),
            "output_file": output_file,
        }

    def process_all(self, input_path: str, output_dir: str) -> Dict[str, Any]:
        script_dir = Path(__file__).parent

        if not os.path.isabs(input_path):
            input_path = str(script_dir / input_path)
        if not os.path.isabs(output_dir):
            output_dir = str(script_dir / output_dir)

        input_files: List[str] = []
        if os.path.isfile(input_path):
            input_files = [input_path]
        elif os.path.isdir(input_path):
            input_files = [
                os.path.join(input_path, filename)
                for filename in os.listdir(input_path)
                if filename.endswith(".json") and not filename.startswith(".")
            ]
            input_files.sort()
        else:
            raise FileNotFoundError(f"Input path not found: {input_path}")

        if not input_files:
            raise ValueError(f"No JSON files found in: {input_path}")

        start_time = datetime.now(timezone.utc)

        verdict_distribution: Dict[str, int] = defaultdict(int)
        total_products = 0
        total_score_80 = 0.0

        use_progress = (
            self.config.get("processing", {}).get("show_progress_bar", True)
            and len(input_files) > 1
            and TQDM_AVAILABLE
        )
        iterator = tqdm(input_files, desc="Scoring files", unit="file") if use_progress else input_files

        total_scored = 0
        for input_file in iterator:
            batch_stats = self.process_batch(input_file, output_dir)
            total_products += batch_stats["total_products"]
            batch_scored = batch_stats.get("scored", batch_stats["total_products"])
            total_scored += batch_scored
            # Weight average by actually-scored products, not total (avoids inflating
            # the average when batches contain BLOCKED/NOT_SCORED products with None scores)
            total_score_80 += batch_stats["average_score_80"] * batch_scored
            for verdict, count in batch_stats.get("verdict_distribution", {}).items():
                verdict_distribution[verdict] += count

        overall_avg_80 = total_score_80 / total_scored if total_scored else 0.0
        overall_avg_100 = (overall_avg_80 / 80.0) * 100.0 if total_products else 0.0

        summary = {
            "processing_info": {
                "scoring_version": self.VERSION,
                "files_processed": len(input_files),
                "duration_seconds": round((datetime.now(timezone.utc) - start_time).total_seconds(), 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "stats": {
                "total_products": total_products,
                "total_scored": total_scored,
                "scorable_ratio": round(total_scored / total_products, 4) if total_products else 0.0,
                "average_score_80": round(overall_avg_80, 2),
                "average_score_100": round(overall_avg_100, 2),
                "verdict_distribution": dict(verdict_distribution),
            },
            "scoring_rules": {
                "max_section_A": self._section_max("a", 25.0),
                "max_section_B": self._section_max("b", 30.0),
                "max_section_C": self._section_max("c", 20.0),
                "max_section_D": self._section_max("d", 5.0),
                "max_total": 80,
                "fit_score_location": "client-side only",
            },
        }

        reports_dir = os.path.join(output_dir, "reports")
        os.makedirs(reports_dir, exist_ok=True)

        summary_file = os.path.join(
            reports_dir,
            "scoring_summary.json",
        )
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        self.logger.info("Scoring complete: %s products", total_products)
        self.logger.info("Average quality: %.2f/80", overall_avg_80)
        self.logger.info("Verdicts: %s", dict(verdict_distribution))
        self.logger.info("Summary saved: %s", summary_file)

        return summary


def generate_impact_report(
    current_results: List[Dict[str, Any]],
    baseline_results: Optional[List[Dict[str, Any]]] = None,
    threshold_score_change: float = 2.0,
    threshold_pct_change: float = 10.0,
    threshold_verdict_change: bool = True,
) -> Dict[str, Any]:
    """Generate score/verdict drift report between two runs."""

    report: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_products": len(current_results),
        "baseline_available": baseline_results is not None,
        "thresholds": {
            "score_change": threshold_score_change,
            "pct_change": threshold_pct_change,
            "track_verdict_changes": threshold_verdict_change,
        },
        "score_changes": [],
        "verdict_changes": [],
        "summary_statistics": {},
        "pass_gate": True,
        "gate_failures": [],
    }

    current_scores = [p.get("score_80", 0) for p in current_results if p.get("score_80") is not None]
    current_verdicts = [p.get("verdict") or p.get("safety_verdict", "SAFE") for p in current_results]

    report["summary_statistics"]["current_run"] = {
        "total_products": len(current_results),
        "score_mean": round(sum(current_scores) / len(current_scores), 2) if current_scores else 0.0,
        "score_min": min(current_scores) if current_scores else 0.0,
        "score_max": max(current_scores) if current_scores else 0.0,
        "verdict_distribution": {
            verdict: current_verdicts.count(verdict) for verdict in sorted(set(current_verdicts))
        },
    }

    if not baseline_results:
        return report

    baseline_lookup = {p.get("dsld_id", "unknown"): p for p in baseline_results}

    for current in current_results:
        product_id = current.get("dsld_id", "unknown")
        baseline = baseline_lookup.get(product_id)
        if not baseline:
            continue

        cur_score = current.get("score_80")
        base_score = baseline.get("score_80")
        if cur_score is not None and base_score is not None:
            delta = cur_score - base_score
            if abs(delta) >= threshold_score_change:
                report["score_changes"].append(
                    {
                        "product_id": product_id,
                        "product_name": current.get("product_name", "Unknown"),
                        "baseline_score": base_score,
                        "current_score": cur_score,
                        "change": round(delta, 2),
                        "change_pct": round((delta / base_score) * 100.0, 2) if base_score else 0.0,
                    }
                )

        if threshold_verdict_change:
            cur_verdict = current.get("verdict") or current.get("safety_verdict", "SAFE")
            base_verdict = baseline.get("verdict") or baseline.get("safety_verdict", "SAFE")
            if cur_verdict != base_verdict:
                report["verdict_changes"].append(
                    {
                        "product_id": product_id,
                        "product_name": current.get("product_name", "Unknown"),
                        "baseline_verdict": base_verdict,
                        "current_verdict": cur_verdict,
                    }
                )
                if cur_verdict == "UNSAFE" and base_verdict != "UNSAFE":
                    report["gate_failures"].append(
                        f"Product {product_id} changed to UNSAFE from {base_verdict}"
                    )
                if cur_verdict == "BLOCKED" and base_verdict != "BLOCKED":
                    report["gate_failures"].append(
                        f"Product {product_id} changed to BLOCKED from {base_verdict}"
                    )

    changed_pct = (len(report["score_changes"]) / len(current_results) * 100.0) if current_results else 0.0
    if changed_pct >= threshold_pct_change:
        report["gate_failures"].append(
            f"{changed_pct:.1f}% of products exceed score-change threshold"
        )

    report["summary_statistics"]["changes"] = {
        "score_changes_flagged": len(report["score_changes"]),
        "verdict_changes_flagged": len(report["verdict_changes"]),
        "new_unsafe_verdicts": sum(
            1
            for item in report["verdict_changes"]
            if item["current_verdict"] == "UNSAFE" and item["baseline_verdict"] != "UNSAFE"
        ),
        "new_blocked_verdicts": sum(
            1
            for item in report["verdict_changes"]
            if item["current_verdict"] == "BLOCKED" and item["baseline_verdict"] != "BLOCKED"
        ),
    }

    report["pass_gate"] = len(report["gate_failures"]) == 0
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PharmaGuide score engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--config", default="config/scoring_config.json", help="Scoring config path")
    parser.add_argument("--input-dir", help="Input file or directory")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved paths and exit")
    parser.add_argument("--impact-report", action="store_true", help="Generate impact report")
    parser.add_argument("--baseline-dir", help="Baseline scored directory for impact comparison")
    parser.add_argument("--impact-threshold", type=float, default=2.0)
    parser.add_argument("--impact-pct-threshold", type=float, default=10.0)

    args = parser.parse_args()

    scorer = SupplementScorer(args.config)

    input_path = args.input_dir or scorer.paths.get("input_directory", "output_Lozenges_enriched/enriched")
    output_dir = args.output_dir or scorer.paths.get("output_directory", "output_Lozenges_scored")

    if args.dry_run:
        scorer.logger.info("DRY RUN")
        scorer.logger.info("Input: %s", input_path)
        scorer.logger.info("Output: %s", output_dir)
        return

    if args.impact_report:
        current_results: List[Dict[str, Any]] = []
        input_p = Path(input_path)
        for json_file in sorted(input_p.glob("*.json")):
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            products = data if isinstance(data, list) else [data]
            current_results.extend([scorer.score_product(product) for product in products])

        baseline_results: Optional[List[Dict[str, Any]]] = None
        if args.baseline_dir:
            baseline_results = []
            for json_file in sorted(Path(args.baseline_dir).glob("**/*.json")):
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                products = data if isinstance(data, list) else [data]
                baseline_results.extend(products)

        report = generate_impact_report(
            current_results,
            baseline_results=baseline_results,
            threshold_score_change=args.impact_threshold,
            threshold_pct_change=args.impact_pct_threshold,
        )

        report_dir = Path(output_dir) / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_file = report_dir / "impact_report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        scorer.logger.info("Impact report saved: %s", report_file)
        scorer.logger.info("Gate status: %s", "PASS" if report["pass_gate"] else "FAIL")

        if not report["pass_gate"]:
            sys.exit(2)
        return

    scorer.process_all(input_path, output_dir)


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as exc:
        logging.error("File not found: %s", exc)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        logging.error("Invalid JSON: %s", exc)
        sys.exit(1)
    except KeyboardInterrupt:
        logging.info("Interrupted")
        sys.exit(130)
    except Exception as exc:
        logging.error("Fatal error: %s", exc, exc_info=True)
        sys.exit(1)
