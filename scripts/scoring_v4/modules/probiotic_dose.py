"""v4 Probiotic Dose dimension — P2.2.

Scores probiotic dose quality against the 25-point rubric in
SCORING_V4_PROPOSAL §6:

  - per-strain CFU disclosure: 15
  - CFU adequacy: 10, preserving v3's tier × support-level math and
    scaling the v3 5-point cap to the v4 10-point budget

This module intentionally does not infer per-strain CFU from aggregate
blend totals. A product can disclose a strong total CFU count and still
score 0 here if the label does not attach CFU values to individual
strains; that gap is handled later in Transparency/confidence, not by
fabricating dose adequacy.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Set


PHASE_MARKER = "P2.2_probiotic_dose"
CAP_DOSE = 25.0
CAP_PER_STRAIN_CFU_DISCLOSURE = 15.0
CAP_CFU_ADEQUACY = 10.0
V3_CFU_ADEQUACY_CAP = 5.0

TIER_POINTS = {
    "low": 0.0,
    "adequate": 1.0,
    "good": 2.0,
    "excellent": 3.0,
}

SUPPORT_LEVEL_CAPS = {
    "high": 1.0,
    "moderate": 0.75,
    "weak": 0.5,
}


def score_dose(product: Any) -> Dict[str, Any]:
    """Return the probiotic Dose dimension payload.

    Per-strain disclosure is proportional to the number of named strains
    with an individual CFU value. CFU adequacy mirrors v3's
    `_compute_probiotic_cfu_adequacy_points` arithmetic, then scales the
    capped v3 total from /5 to /10.
    """
    product = product if isinstance(product, dict) else {}
    pdata = _probiotic_payload(product)
    clinical_strains = _safe_list(pdata.get("clinical_strains"))

    total_strain_count = _total_strain_count(pdata, clinical_strains)
    disclosed_keys = _per_strain_cfu_disclosed_keys(pdata, clinical_strains)
    disclosed_count = min(len(disclosed_keys), total_strain_count) if total_strain_count else 0
    disclosure_score = _score_per_strain_cfu_disclosure(disclosed_count, total_strain_count)

    adequacy = _compute_cfu_adequacy(clinical_strains)
    cfu_adequacy_v3 = adequacy["v3_points"]
    cfu_adequacy_scaled = min(CAP_CFU_ADEQUACY, cfu_adequacy_v3 * 2.0)

    components = {
        "per_strain_cfu_disclosure": round(disclosure_score, 2),
        "cfu_adequacy": round(cfu_adequacy_scaled, 2),
    }
    raw_score = sum(components.values())
    score = max(0.0, min(CAP_DOSE, raw_score))

    return {
        "score": round(score, 2),
        "max": CAP_DOSE,
        "components": components,
        "penalties": {},
        "metadata": {
            "phase": PHASE_MARKER,
            "raw_score": round(raw_score, 4),
            "total_strain_count": total_strain_count,
            "per_strain_cfu_disclosed_count": disclosed_count,
            "cfu_adequacy_v3_points": round(cfu_adequacy_v3, 4),
            "cfu_adequacy_scaled_points": round(cfu_adequacy_scaled, 4),
            "cfu_adequacy_contributions": adequacy["strain_contributions"],
            "window_proxy_reason": _disclosure_reason(pdata, total_strain_count, disclosed_count),
        },
    }


def _compute_cfu_adequacy(clinical_strains: Iterable[Any]) -> Dict[str, Any]:
    contributions: List[Dict[str, Any]] = []
    total = 0.0

    for item in clinical_strains or []:
        strain = _safe_dict(item)
        if not strain:
            continue

        tier = _norm(strain.get("adequacy_tier"))
        support_raw = strain.get("clinical_support_level")
        support = _norm(support_raw) or "weak"
        cfu = strain.get("cfu_per_day")

        if strain.get("is_inactivated") or strain.get("is_postbiotic"):
            contributions.append({
                "tier": tier or strain.get("adequacy_tier"),
                "support": support_raw,
                "cfu_per_day": cfu,
                "points": 0.0,
                "skipped_reason": "postbiotic_inactivated_no_cfu_credit",
            })
            continue

        if tier is None or cfu is None:
            contributions.append({
                "tier": tier or strain.get("adequacy_tier"),
                "support": support_raw,
                "cfu_per_day": cfu,
                "points": 0.0,
            })
            continue

        base = TIER_POINTS.get(tier, 0.0)
        mult = SUPPORT_LEVEL_CAPS.get(support, SUPPORT_LEVEL_CAPS["weak"])
        points = base * mult
        total += points
        contributions.append({
            "tier": tier,
            "support": support,
            "cfu_per_day": cfu,
            "points": round(points, 4),
        })

    total = min(V3_CFU_ADEQUACY_CAP, total)
    return {
        "v3_points": total,
        "strain_contributions": contributions,
    }


def _score_per_strain_cfu_disclosure(disclosed_count: int, total_strain_count: int) -> float:
    if total_strain_count <= 0 or disclosed_count <= 0:
        return 0.0
    ratio = min(1.0, disclosed_count / total_strain_count)
    return CAP_PER_STRAIN_CFU_DISCLOSURE * ratio


def _per_strain_cfu_disclosed_keys(
    pdata: Dict[str, Any],
    clinical_strains: Iterable[Any],
) -> Set[str]:
    keys: Set[str] = set()

    for item in clinical_strains or []:
        strain = _safe_dict(item)
        if strain.get("cfu_per_day") is not None:
            key = _strain_key(strain)
            if key:
                keys.add(key)

    for blend_item in _safe_list(pdata.get("probiotic_blends")):
        blend = _safe_dict(blend_item)
        strains = [str(s).strip() for s in _safe_list(blend.get("strains")) if str(s).strip()]
        if len(strains) != 1:
            continue
        cfu_data = _safe_dict(blend.get("cfu_data"))
        if _cfu_data_has_individual_cfu(cfu_data):
            keys.add(_canonical_key(strains[0]))

    return {key for key in keys if key}


def _cfu_data_has_individual_cfu(cfu_data: Dict[str, Any]) -> bool:
    if not cfu_data.get("has_cfu"):
        return False
    # Disclosure credit is about label structure: a single-strain row with
    # `has_cfu=True` has per-strain CFU disclosed even if the numeric parser
    # did not preserve the count. Adequacy math still requires cfu_per_day.
    return True


def _total_strain_count(pdata: Dict[str, Any], clinical_strains: Iterable[Any]) -> int:
    declared = _as_int(pdata.get("total_strain_count"), 0)
    if declared > 0:
        return declared

    seen: Set[str] = set()
    for blend_item in _safe_list(pdata.get("probiotic_blends")):
        blend = _safe_dict(blend_item)
        for strain in _safe_list(blend.get("strains")):
            key = _canonical_key(str(strain))
            if key:
                seen.add(key)
    for item in clinical_strains or []:
        key = _strain_key(_safe_dict(item))
        if key:
            seen.add(key)
    return len(seen)


def _strain_key(strain: Dict[str, Any]) -> str:
    for field in ("clinical_id", "strain", "name", "standard_name"):
        value = strain.get(field)
        key = _canonical_key(str(value)) if value is not None else ""
        if key:
            return key
    return ""


def _disclosure_reason(pdata: Dict[str, Any], total_strain_count: int, disclosed_count: int) -> str | None:
    if disclosed_count > 0:
        return None
    if total_strain_count <= 0:
        return "no_strain_data"
    if pdata.get("has_cfu") or _as_float(pdata.get("total_billion_count"), 0.0) > 0:
        return "aggregate_cfu_not_per_strain"
    return "per_strain_cfu_missing"


def _canonical_key(value: str) -> str:
    text = value.strip().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _probiotic_payload(product: Dict[str, Any]) -> Dict[str, Any]:
    """Read enriched-input `probiotic_data` and final-blob `probiotic_detail`."""
    return _safe_dict(product.get("probiotic_data") or product.get("probiotic_detail"))


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


def _norm(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).strip().lower()
