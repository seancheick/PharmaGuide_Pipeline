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
from scoring_v4.modules.generic_helpers import _safe_dict, _safe_list


# Phase 5: rebalanced +10 -> +4. Hygiene keeps ONLY the two non-overlapping
# clean-safety components (no banned/high-risk/watchlist, no recalled). The
# overdose / harmful-additive / manufacturer-violation passes were removed
# because each is already penalised by its own dimension (B7 / B1 /
# manufacturer_violations) — crediting "absence" here double-counted.
from scoring_v4.quality_score_config import block as _cfg_block

_CM = _cfg_block("category_magnitudes", "safety_hygiene")["safety_hygiene"]


SAFETY_HYGIENE_CAP = _CM["cap"]


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

    Pass components (Phase 5 — two non-overlapping only, +2 each, cap 4):
      - no banned/high-risk/watchlist safety match
      - no recalled match

    Overdose (B7), harmful additive (B1), and manufacturer violation are NOT
    components here — each is penalised by its own dimension, so crediting
    "absence" would double-count. They also no longer zero the hygiene base
    (that would double-penalise a product already docked elsewhere).

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

    # Phase 5: hard cleanliness failure is gated ONLY on the two retained
    # safety-status components. Overdose / harmful-additive / manufacturer
    # violation are handled by their own penalties and must NOT zero the
    # hygiene base (that would double-penalise).
    if not (b0_pass and recalled_pass):
        if not b0_pass:
            failed.append("banned_high_risk_or_watchlist_match_present")
        if not recalled_pass:
            failed.append("recalled_match_present")
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

    components["no_banned_high_risk_or_watchlist_match"] = 2.0
    components["no_recalled_match"] = 2.0

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
    if _safe_list(iqd.get("ingredients_scorable")):
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
