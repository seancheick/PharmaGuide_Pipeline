"""v4 Probiotic Formulation dimension — P2.1.

Scores probiotic-specific formulation quality against a 15-point
raw rubric. This module is intentionally focused
on formulation signals only; per-strain CFU adequacy belongs to P2.2
Dose and strain-clinical evidence belongs to P2.3 Evidence.
"""

from __future__ import annotations

import math
from typing import Any, Dict

from scoring_v4.modules.generic_formulation import shared_formulation_penalty_detail
from probiotic_measurements import declared_total_cfu, probiotic_label_identity_summary


PHASE_MARKER = "P2.1_probiotic_formulation"
from scoring_v4.quality_score_config import block as _cfg_block

_FVM = _cfg_block("formulation_variant_magnitudes", "probiotic")["probiotic"]


CAP_FORMULATION = _FVM["cap_formulation"]
CAP_TOTAL_POTENCY_DISCLOSURE = _FVM["cap_total_potency_disclosure"]
CAP_EXACT_IDENTITY_COMPLETENESS = _FVM["cap_exact_identity_completeness"]
CAP_DELIVERY_SURVIVABILITY = _FVM["cap_delivery_survivability"]


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or isinstance(value, bool):
            return default
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError, OverflowError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    return int(_as_float(value, default))


def score_formulation(product: Any) -> Dict[str, Any]:
    """Return the probiotic Formulation dimension payload.

    Components:
      - total CFU disclosed: 4
      - exact label-owned identity completeness: 8 * exact / total
      - delivery/survivability: 3

    An exact reviewed whole-formula AFU assessment uses these same component
    budgets for native potency, studied strain identity and delivery. It does
    not claim a CFU amount or independent research for each constituent.
    """
    product = product if isinstance(product, dict) else {}
    pdata = _probiotic_payload(product)

    total_billion = _total_billion_count(pdata)
    identities = probiotic_label_identity_summary(product)
    strain_count = identities["total_strain_count"]
    identity_count = identities["identified_strain_count"]

    components = {
        "total_cfu_disclosed": _score_total_cfu_disclosed(total_billion),
        "exact_identity_completeness": CAP_EXACT_IDENTITY_COMPLETENESS * identity_count / strain_count if strain_count else 0.0,
        "delivery_survivability": _score_delivery_survivability(product, pdata),
    }
    from studied_formulas import assess_studied_formula
    formula = assess_studied_formula(product)
    if formula["status"] == "assessed_studied_formula":
        # Same four component budgets, assessed in the study's native unit.
        # Do not feed AFU into the CFU size tiers or call formula evidence an
        # independent clinical trial for every constituent strain.
        components.pop("total_cfu_disclosed")
        components.pop("exact_identity_completeness")
        components.update(native_potency_disclosed=CAP_TOTAL_POTENCY_DISCLOSURE,
                          studied_formula_strain_identity=CAP_EXACT_IDENTITY_COMPLETENESS,
                          delivery_survivability=CAP_DELIVERY_SURVIVABILITY)
    shared_penalties = shared_formulation_penalty_detail(product)
    penalties = dict(shared_penalties["penalties"])
    penalty_magnitude = sum(abs(float(value or 0.0)) for value in penalties.values())
    raw_score = sum(components.values())
    score = max(0.0, min(CAP_FORMULATION, raw_score - penalty_magnitude))
    metadata = {
        "phase": PHASE_MARKER,
        "raw_score": round(raw_score, 4),
        "pre_penalty_score": round(raw_score, 4),
        "total_billion_count": total_billion,
        "total_strain_count": strain_count,
        "identified_strain_count": identity_count,
        "cap_applied": raw_score > CAP_FORMULATION,
    }
    metadata.update(shared_penalties["metadata"])
    if formula["status"] == "assessed_studied_formula":
        metadata["studied_formula_assessment"] = formula
    return {
        "score": round(score, 2),
        "max": CAP_FORMULATION,
        "components": components,
        "penalties": penalties,
        "metadata": metadata,
    }


def _total_billion_count(pdata: Dict[str, Any]) -> float:
    return declared_total_cfu(pdata) / 1e9


def _score_total_cfu_disclosed(total_billion: float) -> float:
    return CAP_TOTAL_POTENCY_DISCLOSURE if total_billion > 0 else 0.0


def _score_delivery_survivability(product: Dict[str, Any], pdata: Dict[str, Any]) -> float:
    if pdata.get("has_survivability_coating"):
        return CAP_DELIVERY_SURVIVABILITY

    tier = product.get("delivery_tier")
    if tier is None:
        tier = _safe_dict(product.get("delivery_data")).get("highest_tier")
    tier_int = _as_int(tier, 0)
    return {1: CAP_DELIVERY_SURVIVABILITY, 2: 2.5, 3: 1.5}.get(tier_int, 0.0)


def _probiotic_payload(product: Dict[str, Any]) -> Dict[str, Any]:
    """Read enriched-input `probiotic_data` and final-blob `probiotic_detail`.

    The v4 pipeline scores enriched rows, but canary/debug tools often
    call the module directly against shipped detail blobs.
    """
    return _safe_dict(product.get("probiotic_data") or product.get("probiotic_detail"))
