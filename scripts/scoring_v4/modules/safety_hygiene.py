"""Shared v4 safety-hygiene base adjustment.

This restores the clean-product part of v3 Section B without putting
"absence of a problem" inside Testing & Trust. Trust remains evidence of
testing, certifications, GMP, and traceability. Hygiene is a separate,
named adjustment with explicit pass components and a hard cap.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from identity.safety import normalize_safety_signals
from scoring_v4.modules.generic_helpers import _as_float, _norm_text, _safe_dict, _safe_list


SAFETY_HYGIENE_CAP = 10.0


@dataclass
class SafetyHygieneResult:
    """Named, bounded clean-safety base.

    The score is an adjustment, not a hidden sixth class dimension. Final
    assembly still clamps the raw score to [0, 100] after all adjustments.
    """

    score: float = 0.0
    max: float = SAFETY_HYGIENE_CAP
    components: Dict[str, float] = field(default_factory=dict)
    failed_components: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": round(float(self.score), 4),
            "max": float(self.max),
            "components": dict(self.components),
            "failed_components": list(self.failed_components),
            "metadata": dict(self.metadata),
        }


def score_safety_hygiene_base(product: Dict[str, Any]) -> SafetyHygieneResult:
    """Return the bounded clean-product safety base for a scoreable product.

    Pass components:
      - no banned/high-risk/watchlist safety match
      - no recalled match
      - no B7 overdose flag (>=150% UL)
      - no harmful additive hit
      - no manufacturer violation deduction

    Products with no usable product payload receive no credit. That keeps
    direct defensive module calls from awarding points to empty dicts while
    preserving the base for real enriched products.
    """
    if not isinstance(product, dict) or not _has_product_payload(product):
        return SafetyHygieneResult(
            metadata={
                "phase": "safety_hygiene_base_v1",
                "not_evaluable_reason": "no_product_payload",
            }
        )

    components: Dict[str, float] = {}
    failed: List[str] = []

    b0_pass = _passes_no_b0_safety_match(product)
    recalled_pass = _passes_no_recalled_match(product)
    b7_pass = _passes_no_b7_overdose(product)
    manufacturer_pass = _passes_no_manufacturer_violation(product)

    # These are hard cleanliness failures. Do not award partial "clean base"
    # credit to products with safety-status hits, overdose flags, or a
    # manufacturer violation; the individual components are still reported
    # as failed for audit.
    if not (b0_pass and recalled_pass and b7_pass and manufacturer_pass):
        if not b0_pass:
            failed.append("banned_high_risk_or_watchlist_match_present")
        if not recalled_pass:
            failed.append("recalled_match_present")
        if not b7_pass:
            failed.append("b7_overdose_present")
        if not manufacturer_pass:
            failed.append("manufacturer_violation_present")
        return SafetyHygieneResult(
            score=0.0,
            failed_components=failed,
            metadata={
                "phase": "safety_hygiene_base_v1",
                "raw_score": 0.0,
                "cap_applied": False,
                "hard_cleanliness_failure": True,
            },
        )

    if b0_pass:
        components["no_banned_high_risk_or_watchlist_match"] = 2.0
    else:
        failed.append("banned_high_risk_or_watchlist_match_present")

    if recalled_pass:
        components["no_recalled_match"] = 2.0
    else:
        failed.append("recalled_match_present")

    if b7_pass:
        components["no_b7_overdose"] = 2.0
    else:
        failed.append("b7_overdose_present")

    if _passes_no_harmful_additive(product):
        components["no_harmful_additive"] = 2.0
    else:
        failed.append("harmful_additive_present")

    if manufacturer_pass:
        components["no_manufacturer_violation"] = 2.0
    else:
        failed.append("manufacturer_violation_present")

    raw = sum(components.values())
    score = max(0.0, min(SAFETY_HYGIENE_CAP, raw))
    return SafetyHygieneResult(
        score=round(score, 4),
        components=components,
        failed_components=failed,
        metadata={
            "phase": "safety_hygiene_base_v1",
            "raw_score": round(raw, 4),
            "cap_applied": raw > SAFETY_HYGIENE_CAP,
        },
    )


def _has_product_payload(product: Dict[str, Any]) -> bool:
    if product.get("dsld_id") or product.get("product_name") or product.get("fullName"):
        return True
    iqd = _safe_dict(product.get("ingredient_quality_data"))
    if _safe_list(iqd.get("ingredients")) or _safe_list(iqd.get("ingredients_scorable")):
        return True
    return False


def _passes_no_b0_safety_match(product: Dict[str, Any]) -> bool:
    for sig in normalize_safety_signals(product):
        if not (sig.policy_eligible or sig.review_required):
            continue
        if sig.status in {"banned", "high_risk", "watchlist"}:
            return False
    return True


def _passes_no_recalled_match(product: Dict[str, Any]) -> bool:
    for sig in normalize_safety_signals(product):
        if not (sig.policy_eligible or sig.review_required):
            continue
        if sig.status == "recalled":
            return False
    return True


def _passes_no_b7_overdose(product: Dict[str, Any]) -> bool:
    rda_ul = _safe_dict(product.get("rda_ul_data"))
    for flag in _safe_list(rda_ul.get("safety_flags")):
        if not isinstance(flag, dict):
            continue
        pct_ul = _as_float(flag.get("pct_ul"), 0.0) or 0.0
        if pct_ul >= 150.0:
            return False
    return True


def _passes_no_harmful_additive(product: Dict[str, Any]) -> bool:
    contaminant = _safe_dict(product.get("contaminant_data"))
    harmful = _safe_dict(contaminant.get("harmful_additives"))
    additives = _safe_list(harmful.get("additives"))
    if not additives:
        additives = _safe_list(product.get("harmful_additives"))
    for additive in additives:
        if not isinstance(additive, dict):
            continue
        severity = _norm_text(additive.get("severity_level") or additive.get("severity"))
        if severity in {"critical", "high", "moderate"}:
            return False
    return True


def _passes_no_manufacturer_violation(product: Dict[str, Any]) -> bool:
    violations = _safe_dict(_safe_dict(product.get("manufacturer_data")).get("violations"))
    deduction = _as_float(violations.get("total_deduction_applied"), 0.0) or 0.0
    if deduction < 0:
        return False
    items = [item for item in _safe_list(violations.get("violations")) if isinstance(item, dict)]
    return len(items) == 0
