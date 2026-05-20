"""v4 Probiotic Formulation dimension — P2.1.

Scores probiotic-specific formulation quality against the 25-point
rubric in SCORING_V4_PROPOSAL §6. This module is intentionally focused
on formulation signals only; per-strain CFU adequacy belongs to P2.2
Dose and strain-clinical evidence belongs to P2.3 Evidence.
"""

from __future__ import annotations

from typing import Any, Dict


PHASE_MARKER = "P2.1_probiotic_formulation"
CAP_FORMULATION = 25.0


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def score_formulation(product: Any) -> Dict[str, Any]:
    """Return the probiotic Formulation dimension payload.

    Components:
      - total CFU disclosed: 4
      - CFU amount tier: 4
      - named species diversity: 4
      - exact clinical strain codes: 4
      - delivery/survivability: 4
      - prebiotic complement: 5
    """
    product = product if isinstance(product, dict) else {}
    pdata = _safe_dict(product.get("probiotic_data"))

    total_billion = _total_billion_count(pdata)
    strain_count = _total_strain_count(pdata)
    clinical_count = _clinical_strain_count(pdata)

    components = {
        "total_cfu_disclosed": _score_total_cfu_disclosed(total_billion),
        "cfu_amount": _score_cfu_amount(total_billion),
        "named_species_diversity": _score_named_species_diversity(strain_count),
        "clinical_strain_codes": _score_clinical_strain_codes(clinical_count),
        "delivery_survivability": _score_delivery_survivability(product, pdata),
        "prebiotic_complement": 5.0 if pdata.get("prebiotic_present") else 0.0,
    }
    raw_score = sum(components.values())
    score = max(0.0, min(CAP_FORMULATION, raw_score))
    return {
        "score": round(score, 2),
        "max": CAP_FORMULATION,
        "components": components,
        "penalties": {},
        "metadata": {
            "phase": PHASE_MARKER,
            "raw_score": round(raw_score, 4),
            "total_billion_count": total_billion,
            "total_strain_count": strain_count,
            "clinical_strain_count": clinical_count,
            "cap_applied": raw_score > CAP_FORMULATION,
        },
    }


def _total_billion_count(pdata: Dict[str, Any]) -> float:
    total = _as_float(pdata.get("total_billion_count"), 0.0)
    if total > 0:
        return total
    for blend in _safe_list(pdata.get("probiotic_blends")):
        cfu_data = _safe_dict(_safe_dict(blend).get("cfu_data"))
        total += _as_float(cfu_data.get("billion_count"), 0.0)
    return max(0.0, total)


def _total_strain_count(pdata: Dict[str, Any]) -> int:
    count = _as_int(pdata.get("total_strain_count"), 0)
    if count > 0:
        return count
    strains = set()
    for blend in _safe_list(pdata.get("probiotic_blends")):
        blend = _safe_dict(blend)
        for strain in _safe_list(blend.get("strains")):
            key = str(strain or "").strip().lower()
            if key:
                strains.add(key)
    return len(strains)


def _clinical_strain_count(pdata: Dict[str, Any]) -> int:
    count = _as_int(pdata.get("clinical_strain_count"), 0)
    if count > 0:
        return count
    seen = set()
    for strain in _safe_list(pdata.get("clinical_strains")):
        strain = _safe_dict(strain)
        key = str(strain.get("clinical_id") or strain.get("strain") or "").strip().lower()
        if key:
            seen.add(key)
    return len(seen)


def _score_total_cfu_disclosed(total_billion: float) -> float:
    return 4.0 if total_billion > 0 else 0.0


def _score_cfu_amount(total_billion: float) -> float:
    if total_billion >= 50:
        return 4.0
    if total_billion >= 10:
        return 3.0
    if total_billion > 1:
        return 2.0
    if total_billion > 0:
        return 1.0
    return 0.0


def _score_named_species_diversity(strain_count: int) -> float:
    if strain_count >= 10:
        return 4.0
    if strain_count >= 6:
        return 3.0
    if strain_count >= 3:
        return 2.0
    if strain_count > 0:
        return 1.0
    return 0.0


def _score_clinical_strain_codes(clinical_count: int) -> float:
    if clinical_count >= 5:
        return 4.0
    if clinical_count >= 3:
        return 3.0
    if clinical_count >= 1:
        return 2.0
    return 0.0


def _score_delivery_survivability(product: Dict[str, Any], pdata: Dict[str, Any]) -> float:
    if pdata.get("has_survivability_coating"):
        return 4.0

    tier = product.get("delivery_tier")
    if tier is None:
        tier = _safe_dict(product.get("delivery_data")).get("highest_tier")
    tier_int = _as_int(tier, 0)
    return {1: 4.0, 2: 3.0, 3: 2.0}.get(tier_int, 0.0)
