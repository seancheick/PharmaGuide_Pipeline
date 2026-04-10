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
from supplement_type_utils import infer_supplement_type

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

    def _classify_supplement_type(self, product: Dict[str, Any]) -> str:
        st = product.get("supplement_type", {})
        if isinstance(st, str):
            existing = norm_text(st) or st
        elif isinstance(st, dict):
            existing = norm_text(st.get("type"))
        else:
            existing = ""

        inferred = infer_supplement_type(product)
        inferred_type = norm_text(inferred.get("type")) or "unknown"

        if existing:
            if existing == "single":
                return "single"
            if existing not in {"unknown", "specialty"}:
                return existing
            if inferred_type not in {"unknown", "specialty"}:
                return inferred_type
            return existing

        if inferred_type:
            return inferred_type

        if isinstance(st, str):
            return st
        if not isinstance(st, dict):
            st = {}

        active_count = int(as_float(st.get("active_count"), 0) or 0)
        if not active_count:
            active_count = len(safe_list(product.get("ingredient_quality_data", {}).get("ingredients")))

        if active_count == 1:
            return "single_nutrient"
        if active_count >= 6:
            return "multivitamin"
        if 2 <= active_count <= 5:
            return "targeted"
        return "unknown"

    def _unmapped_active_names(self, product: Dict[str, Any]) -> List[str]:
        ingredients = safe_list(product.get("ingredient_quality_data", {}).get("ingredients"))

        def _is_unmapped_gate_candidate(ing: Dict[str, Any]) -> bool:
            # Blend containers/headers are opacity signals handled by B5, not mapping blockers.
            if bool(ing.get("is_proprietary_blend")):
                return False
            if bool(ing.get("is_blend_header")) or bool(ing.get("blend_total_weight_only")):
                return False
            role = norm_text(ing.get("role_classification"))
            if role in {"recognized_non_scorable", "inactive_non_scorable"}:
                return False
            return True

        return [
            ing.get("name") or ing.get("standard_name") or ing.get("raw_source_text") or "unknown"
            for ing in ingredients
            if _is_unmapped_gate_candidate(ing) and not bool(ing.get("mapped", False))
        ]

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

    def _mapping_gate(self, product: Dict[str, Any]) -> Dict[str, Any]:
        iqd = product.get("ingredient_quality_data", {})
        ingredients = safe_list(iqd.get("ingredients"))
        kpis = self._split_unmapped_kpis(product)
        unmapped_all_candidates = kpis["unmapped_actives_all"]
        unmapped_excluding_candidates = kpis["unmapped_actives_excluding_banned_exact_alias"]
        unmapped_banned_exact_alias_candidates = kpis["unmapped_actives_banned_exact_alias"]

        active_total = int(as_float(iqd.get("total_active"), 0) or 0)
        if active_total <= 0:
            active_total = len(ingredients)

        # Derive mapping-gate counts from gate-eligible ingredient rows, not legacy enrichment counters.
        # This prevents structural blend containers from silently blocking scoring.
        unmapped_banned_exact_alias = list(unmapped_banned_exact_alias_candidates)
        unmapped_excluding_banned = list(unmapped_excluding_candidates)
        unmapped_count_raw = len(unmapped_all_candidates)
        unmapped_count_excluding_banned = len(unmapped_excluding_banned)

        if active_total <= 0:
            return {
                "stop": True,
                "reason": "NO_ACTIVES_DETECTED",
                "mapped_coverage": 0.0,
                "unmapped_actives": [],
                "unmapped_actives_total": 0,
                "unmapped_actives_excluding_banned_exact_alias": 0,
                "unmapped_actives_banned_exact_alias": [],
                "flags": ["NO_ACTIVES_DETECTED"],
            }

        active_mapped = max(0, active_total - unmapped_count_excluding_banned)
        mapped_coverage = active_mapped / active_total if active_total else 0.0

        flags: List[str] = []
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

        if self._feature_on("require_full_mapping", default=False) and mapped_coverage < 1.0:
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

    def _evaluate_safety_gate(self, product: Dict[str, Any]) -> Dict[str, Any]:
        contaminant_data = product.get("contaminant_data") or {}
        substances = safe_list(
            contaminant_data
            .get("banned_substances", {})
            .get("substances", [])
        )

        flags: List[str] = []
        moderate_penalty = 0
        blocked = False
        unsafe = False
        reason = None
        matched_substance_name = None
        review_needed = False

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
                moderate_penalty += 10
                flags.append("B0_HIGH_RISK_SUBSTANCE")
            elif status == "watchlist":
                moderate_penalty += 5
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
        iqd = product.get("ingredient_quality_data", {})
        ingredients = safe_list(iqd.get("ingredients_scorable"))
        if not ingredients:
            # Only fall back if the full list contains genuine mapped actives,
            # not just fillers/excipients that enrichment couldn't classify.
            fallback = safe_list(iqd.get("ingredients"))
            if any((ing.get("mapped") or ing.get("canonical_id")) and not ing.get("is_filler") for ing in fallback):
                ingredients = fallback
        return ingredients

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

        is_single = supp_type in {"single", "single_nutrient"}
        weighted_values: List[Tuple[float, float]] = []
        for ing in ingredients:
            # Blend containers are opacity signals, not quality signals.
            # Their cost is captured by B5; including them in A1 would
            # double-penalise and pollute the quality average with a
            # meaningless "unspecified form" score of 5.
            if ing.get("is_proprietary_blend"):
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
        if supp_type == "multivitamin":
            smoothing = as_float(a1_cfg.get("multivitamin_smoothing_factor"), 0.7)
            if smoothing is None or smoothing < 0.0 or smoothing > 1.0:
                smoothing = 0.7
            floor = as_float(a1_cfg.get("multivitamin_floor"), 9.0)
            if floor is None:
                floor = 9.0
            avg_raw = smoothing * avg_raw + (1.0 - smoothing) * floor

        max_points = as_float(
            a1_cfg.get("max"),
            15.0,
        ) or 15.0
        range_score_field = str(a1_cfg.get("range_score_field", "0-18"))
        range_match = re.search(r"(\d+(?:\.\d+)?)\s*$", range_score_field)
        range_max = as_float(range_match.group(1), 18.0) if range_match else 18.0
        if range_max is None or range_max <= 0:
            range_max = 18.0
        return clamp(0.0, max_points, (avg_raw / range_max) * max_points)

    def _compute_premium_forms_bonus(self, product: Dict[str, Any]) -> float:
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
            score = as_float(ing.get("score"), None)
            if score is None:
                continue
            if score >= 14:
                key = canon_key(ing.get("canonical_id") or ing.get("standard_name") or ing.get("name"))
                if key:
                    premium_keys.add(key)

        count_premium = len(premium_keys)
        return clamp(0.0, 3.0, 0.5 * max(0, count_premium - 1))

    def _compute_delivery_score(self, product: Dict[str, Any]) -> float:
        tier = product.get("delivery_tier")
        if tier is None:
            tier = product.get("delivery_data", {}).get("highest_tier")
        tier_int = int(as_float(tier, 0) or 0)
        return {1: 3.0, 2: 2.0, 3: 1.0}.get(tier_int, 0.0)

    def _compute_absorption_bonus(self, product: Dict[str, Any]) -> float:
        if "absorption_enhancer_paired" in product:
            return 3.0 if bool(product.get("absorption_enhancer_paired")) else 0.0
        qualifies = bool(product.get("absorption_data", {}).get("qualifies_for_bonus", False))
        return 3.0 if qualifies else 0.0

    def _synergy_cluster_qualified(self, product: Dict[str, Any]) -> bool:
        if "synergy_cluster_qualified" in product:
            return bool(product.get("synergy_cluster_qualified"))

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
                # Keep scorer fallback behavior aligned with enrichment projection:
                # cluster matches without dose-anchored evidence do not qualify for A5c.
                continue

            dosed = [item for item in checkable if bool(item.get("meets_minimum", False))]
            if len(dosed) >= math.ceil(len(checkable) / 2):
                return True

        return False

    def _compute_formulation_bonus(self, product: Dict[str, Any]) -> Dict[str, float]:
        formulation = product.get("formulation_data", {})

        organic_data = formulation.get("organic")
        if isinstance(organic_data, dict):
            is_organic = bool(organic_data.get("usda_verified") or (organic_data.get("claimed") and not organic_data.get("exclusion_matched")))
        else:
            is_organic = bool(organic_data)

        has_std = bool(product.get("has_standardized_botanical", False))
        if not has_std:
            std = safe_list(formulation.get("standardized_botanicals", []))
            has_std = any(
                bool(item.get("meets_threshold"))
                or (
                    as_float(item.get("percentage_found"), None) is not None
                    and as_float(item.get("min_threshold"), None) is not None
                    and as_float(item.get("percentage_found"), 0.0) >= as_float(item.get("min_threshold"), 0.0)
                )
                for item in std
            )

        has_synergy = self._synergy_cluster_qualified(product)

        non_gmo_audit = derive_non_gmo_audit(product)
        non_gmo_verified = bool(non_gmo_audit.get("project_verified"))

        a5d = 0.5 if (self._feature_on("enable_non_gmo_bonus", default=False) and non_gmo_verified) else 0.0

        return {
            "A5a_organic": 1.0 if is_organic else 0.0,
            "A5b_standardized_botanical": 1.0 if has_std else 0.0,
            "A5c_synergy_cluster": 1.0 if has_synergy else 0.0,
            "A5d_non_gmo_verified": a5d,
        }

    def _compute_single_efficiency_bonus(self, product: Dict[str, Any], supp_type: str) -> float:
        if supp_type not in {"single", "single_nutrient"}:
            return 0.0

        candidates = []
        for ing in self._get_active_ingredients(product):
            if ing.get("is_proprietary_blend"):
                continue
            if not self._has_usable_individual_dose(ing):
                continue
            candidates.append(ing)

        if not candidates:
            return 0.0

        ing = candidates[0]
        # A6 tiers are calibrated to IQM form score ranges used by A1/A2.
        # Prefer score, then fall back to bio_score when score is unavailable.
        form_score = as_float(ing.get("score"), None)
        if form_score is None:
            form_score = as_float(ing.get("bio_score"), None)
        if form_score is None:
            return 0.0

        if form_score >= 16.0:
            return 3.0
        if form_score >= 14.0:
            return 2.0
        if form_score >= 12.0:
            return 1.0
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

        if supp_type != "probiotic":
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

        prebiotic_terms = ["inulin", "fos", "gos"]
        prebiotic_hits = sum(1 for term in prebiotic_terms if any(term in ing for ing in ingredient_names))
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

        return {
            "probiotic_bonus": total,
            "cfu": cfu,
            "diversity": diversity,
            "prebiotic": prebiotic,
            "clinical_strains": clinical_strains,
            "survivability": survivability,
            "eligibility": eligibility,
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
            return {
                "omega3_dose_bonus": 0.0,
                "applicable": False,
            }

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

        return {
            "omega3_dose_bonus": round(bonus_score, 2),
            "applicable": True,
            "dose_band": dose_band_label,
            "per_day_mid_mg": dose_data.get("per_day_mid"),
            "per_day_min_mg": dose_data.get("per_day_min"),
            "per_day_max_mg": dose_data.get("per_day_max"),
            "epa_mg_per_unit": dose_data.get("epa_mg_per_unit"),
            "dha_mg_per_unit": dose_data.get("dha_mg_per_unit"),
            "prescription_dose": prescription_dose,
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
        a5_cap = as_float(a_cfg.get("A5_formulation_excellence", {}).get("max"), 3.0)
        a5 = min(a5_cap, sum(a5_parts.values()))
        a6 = self._compute_single_efficiency_bonus(product, supp_type)
        probiotic = self._compute_probiotic_category_bonus(product, supp_type)
        probiotic_bonus = probiotic["probiotic_bonus"]

        # Category bonus pool: bonuses enhance, not define quality.
        # Core quality components always dominate.
        omega3_result = self._compute_omega3_dose_bonus(product, flags if flags is not None else [])
        omega3_bonus = omega3_result["omega3_dose_bonus"]

        pool_cfg = a_cfg.get("category_bonus_pool", {})
        max_bonus_contribution = as_float(pool_cfg.get("max_contribution"), 5.0)
        category_bonus_total = min(max_bonus_contribution, probiotic_bonus + omega3_bonus)

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
            "A6": round(a6, 2),
            "probiotic_bonus": round(probiotic_bonus, 2),
            "probiotic_breakdown": probiotic,
            "omega3_dose_bonus": round(omega3_bonus, 2),
            "omega3_breakdown": omega3_result,
        }

    # ---------------------------------------------------------------------
    # Section B
    # ---------------------------------------------------------------------

    def _compute_harmful_additives_penalty(self, product: Dict[str, Any], b_cfg: Dict[str, Any] = None) -> float:
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
        seen_ids: Dict[str, float] = {}
        for item in additives:
            aid = item.get("additive_id") or item.get("id") or f"_anon_{id(item)}"
            sev = risk_map.get(norm_text(item.get("severity_level")), 0.0)
            seen_ids[aid] = max(seen_ids.get(aid, 0.0), sev)
        penalty = sum(seen_ids.values())
        b1_cap = as_float(b1_cfg.get("cap"), 5.0)
        return clamp(0.0, b1_cap, penalty)

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

    def _compute_certifications_bonus(self, product: Dict[str, Any], supp_type: str) -> Dict[str, float]:
        cert = product.get("certification_data", {})
        b4_cfg = self.config.get("section_B_safety_purity", {}).get("B4_quality_certifications", {})
        b4a_cfg = b4_cfg.get("B4a_named_programs", {}) if isinstance(b4_cfg, dict) else {}
        b4a_points_per = as_float(
            b4a_cfg.get("points_per_program"),
            5.0,
        ) or 5.0
        b4a_cap = as_float(
            b4a_cfg.get("cap"),
            15.0,
        ) or 15.0

        named_programs = safe_list(product.get("named_cert_programs"))
        if not named_programs:
            programs = cert.get("third_party_programs", {}).get("programs", [])
            if isinstance(programs, list):
                named_programs = [p.get("name") if isinstance(p, dict) else p for p in programs]

        canonical_programs = []
        for p in named_programs:
            if not p:
                continue
            text = norm_text(p)
            if text:
                canonical_programs.append(text)

        # Marine/omega-specific certs: only count when product contains omega-3 / marine ingredients.
        _MARINE_CERTS = {"ifos", "friend of the sea", "msc", "marine stewardship", "goed"}
        if canonical_programs:
            omega_like = supp_type == "specialty" or any(
                any(term in norm_text(i.get("name") or i.get("standard_name"))
                    for term in ("omega", "fish oil", "krill", "cod liver", "marine", "dha", "epa"))
                for i in self._get_active_ingredients(product)
            )
            filtered = []
            for p in canonical_programs:
                if any(mc in p for mc in _MARINE_CERTS) and not omega_like:
                    continue
                filtered.append(p)
            canonical_programs = sorted(set(filtered))

        b4a = clamp(0.0, b4a_cap, float(len(canonical_programs) * b4a_points_per))

        gmp_level = norm_text(product.get("gmp_level"))
        gmp = cert.get("gmp", {})
        if gmp_level == "certified" or bool(gmp.get("nsf_gmp") or gmp.get("claimed")):
            b4b = 4.0
        elif gmp_level == "fda_registered" or bool(gmp.get("fda_registered")):
            b4b = 2.0
        else:
            b4b = 0.0

        has_coa = bool(product.get("has_coa", cert.get("batch_traceability", {}).get("has_coa", False)))
        has_batch_lookup = bool(
            product.get(
                "has_batch_lookup",
                cert.get("batch_traceability", {}).get("has_batch_lookup", False)
                or cert.get("batch_traceability", {}).get("has_qr_code", False),
            )
        )
        b4c = float((1 if has_coa else 0) + (1 if has_batch_lookup else 0))

        return {
            "B4a": b4a,
            "B4b": b4b,
            "B4c": b4c,
            "named_program_count": float(len(canonical_programs)),
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

            blend_penalty = 0.0
            if level != "full":
                blend_penalty = base + (prop_coef * impact)
                penalty_sum += blend_penalty

            evidence = {
                "blend_name": blend.get("name") or "",
                "disclosure_tier": level or "none",
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

        b1 = self._compute_harmful_additives_penalty(product, section_b_cfg)
        b2 = self._compute_allergen_penalty(product, section_b_cfg)

        allergen_valid, gluten_valid, vegan_valid, claim_flags = self._derive_claim_validations(product, b2)
        for f in claim_flags:
            if f not in flags:
                flags.append(f)

        b3 = float((2 if allergen_valid else 0) + (1 if gluten_valid else 0) + (1 if vegan_valid else 0))
        b3_cap = as_float(section_b_cfg.get("B3_claim_compliance", {}).get("cap"), 4.0)
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
        }

    # ---------------------------------------------------------------------
    # Section D + violations
    # ---------------------------------------------------------------------

    def _compute_brand_trust_score(self, product: Dict[str, Any]) -> Dict[str, Any]:
        section_max = self._section_max("d", 5.0)
        md = product.get("manufacturer_data", {})

        d1 = 0.0
        if bool(product.get("is_trusted_manufacturer", False)):
            d1 = 2.0
        else:
            top = md.get("top_manufacturer", {})
            if bool(top.get("found", False)) and norm_text(top.get("match_type")) == "exact":
                d1 = 2.0
            elif self._feature_on("enable_d1_middle_tier", default=False):
                if self._has_verifiable_mid_tier_manufacturer_evidence(product):
                    d1 = 1.0

        has_full_disclosure = self._has_full_disclosure(product)
        d2 = 1.0 if has_full_disclosure else 0.0

        bonus_features = md.get("bonus_features", {})
        d3 = 0.5 if bool(product.get("claim_physician_formulated", bonus_features.get("physician_formulated", False))) else 0.0

        region = norm_text(product.get("manufacturing_region") or md.get("country_of_origin", {}).get("country"))
        high_std_regions = {
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
        d4_value = as_float(
            self.config.get("section_D_brand_trust", {}).get("D4_high_standard_region"),
            1.0,
        ) or 1.0
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
            return {
                "score": 0.0,
                "max": 0.0,       # 0 max signals "not applicable" to callers / display
                "applicable": False,
            }

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

        return {
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

    @staticmethod
    def _build_legacy_section_e(section_a: Dict[str, Any]) -> Dict[str, Any]:
        """Build backward-compatible Section E breakdown from the omega3 category bonus.

        Downstream consumers (tests, Flutter, exports) that read breakdown["E"]
        get the same shape they expect, but the score now comes from A's
        omega3_dose_bonus rather than a standalone section.
        """
        o3 = section_a.get("omega3_breakdown", {})
        applicable = o3.get("applicable", False)
        result: Dict[str, Any] = {
            "score": section_a.get("omega3_dose_bonus", 0.0),
            "max": 2.0 if applicable else 0.0,
            "applicable": applicable,
            "_note": "Legacy compat — omega-3 dose is now a category bonus inside Ingredient Quality",
        }
        if applicable:
            for key in ("dose_band", "per_day_mid_mg", "per_day_min_mg", "per_day_max_mg",
                        "epa_mg_per_unit", "dha_mg_per_unit", "prescription_dose"):
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
        if verdict in {"BLOCKED", "UNSAFE", "NOT_SCORED"}:
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

    def _compute_manufacturer_violation_penalty(self, product: Dict[str, Any]) -> float:
        violations = product.get("manufacturer_data", {}).get("violations", {})

        deduction: Optional[float] = None
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
            total = 0.0
            for item in violations:
                total += as_float(
                    item.get("total_deduction_applied", item.get("total_deduction")),
                    0.0,
                ) or 0.0
            deduction = total

        if deduction is None:
            return 0.0

        # Stored as negative, add directly after section sum.
        return max(float(deduction), -25.0)

    # ---------------------------------------------------------------------
    # Output helpers
    # ---------------------------------------------------------------------

    def _grade_word(self, score_100_equivalent: float, verdict: str) -> Optional[str]:
        if verdict in {"BLOCKED", "UNSAFE", "NOT_SCORED"}:
            return None
        if score_100_equivalent >= 90:
            return "Exceptional"
        if score_100_equivalent >= 80:
            return "Excellent"
        if score_100_equivalent >= 70:
            return "Good"
        if score_100_equivalent >= 60:
            return "Fair"
        if score_100_equivalent >= 50:
            return "Below Avg"
        if score_100_equivalent >= 32:
            return "Low"
        return "Very Poor"

    def _derive_verdict(
        self,
        b0: Dict[str, Any],
        mapping_gate: Dict[str, Any],
        flags: List[str],
        quality_score: Optional[float],
    ) -> str:
        if b0.get("blocked"):
            return "BLOCKED"
        if b0.get("unsafe"):
            return "UNSAFE"
        if mapping_gate.get("stop"):
            return "NOT_SCORED"
        if "BANNED_MATCH_REVIEW_NEEDED" in flags:
            return "CAUTION"
        if any(f in flags for f in ("B0_MODERATE_SUBSTANCE", "B0_HIGH_RISK_SUBSTANCE",
                                     "B0_WATCHLIST_SUBSTANCE")):
            return "CAUTION"
        if quality_score is not None and quality_score < 32:
            return "POOR"
        return "SAFE"

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
        else:
            scoring_status = SCORING_STATUS_SCORED
            score_basis = SCORE_BASIS_BIOACTIVES

        # Backward-compatible safety_verdict for downstream scripts.
        if verdict == "POOR":
            safety_verdict = "SAFE"
        elif verdict == "NOT_SCORED":
            safety_verdict = "CAUTION"
        else:
            safety_verdict = verdict

        output = {
            "dsld_id": product_id,
            "product_name": product_name,
            "brand_name": product.get("brandName", ""),
            "quality_score": round(quality_score, 1) if quality_score is not None else None,
            "score_80": round(quality_score, 1) if quality_score is not None else None,
            "score_100_equivalent": score_100_equivalent,
            "display": display,
            "display_100": display_100,
            "grade": self._grade_word(score_100_equivalent or 0.0, verdict),
            "verdict": verdict,
            "safety_verdict": safety_verdict,
            "badges": self._build_badges(product, verdict),
            "category_percentile": None,
            "category_percentile_text": None,
            "percentile_category": product.get("percentile_category"),
            "percentile_category_label": product.get("percentile_category_label"),
            "percentile_category_source": product.get("percentile_category_source"),
            "percentile_category_confidence": product.get("percentile_category_confidence"),
            "percentile_category_signals": product.get("percentile_category_signals"),
            "output_schema_version": self.OUTPUT_SCHEMA_VERSION,
            "scoring_status": scoring_status,
            "score_basis": score_basis,
            "evaluation_stage": "safety" if verdict in {"BLOCKED", "UNSAFE"} else "scoring",
            "breakdown": breakdown,
            "flags": sorted(set(flags)),
            "supp_type": supp_type,
            "unmapped_actives": unmapped_actives,
            "unmapped_actives_total": int(unmapped_actives_total),
            "unmapped_actives_excluding_banned_exact_alias": int(
                unmapped_actives_excluding_banned_exact_alias
            ),
            "mapped_coverage": round(mapped_coverage, 4),
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
                "mapped_coverage": round(mapped_coverage, 4),
                "reason": reason,
            },
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
                )

            # Step 2/3: type + mapping gate
            for flag in mapping_gate.get("flags", []):
                if flag not in flags:
                    flags.append(flag)

            if mapping_gate.get("stop"):
                verdict = self._derive_verdict(b0, mapping_gate, flags, None)
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
                )

            # Step 4: sections
            # Note: Section A now includes category bonuses (probiotic, omega-3 dose)
            # so it needs access to flags for the PRESCRIPTION_DOSE_OMEGA3 flag.
            section_a = self._compute_ingredient_quality_score(product, supp_type, flags=flags)
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

            verdict = self._derive_verdict(b0, mapping_gate, flags, quality_score)

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
            f"scoring_summary_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json",
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
        report_file = report_dir / f"impact_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
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
