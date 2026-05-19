"""v4 generic-module manufacturer trust and violations (P1.3.6).

Manufacturer Trust is a small positive dimension (+5) ported from v3
Section D. Manufacturer Violations is a separate negative adjustment,
not part of Testing & Trust, with v3 parity for the graduated Class-I
aggregate cap.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from scoring_v4.modules.generic_helpers import (
    _as_float,
    _norm_text,
    _safe_dict,
    _safe_list,
    get_active_ingredients,
    has_usable_individual_dose,
)


MANUFACTURER_TRUST_CAP = 5.0
D1_TRUSTED = 2.0
D1_MID_TIER = 1.0
D2_DISCLOSURE = 1.0
D3_PHYSICIAN = 0.5
D4_HIGH_STANDARD_REGION = 1.0
D5_SUSTAINABILITY = 0.5
D3_D4_D5_CAP = 2.0

DEFAULT_HIGH_STANDARD_REGIONS = frozenset(
    {
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
)

MFG_CAP_DEFAULT = -25.0
MFG_CAP_TWO_CLASS_I = -35.0
MFG_CAP_THREE_OR_MORE_CLASS_I = -50.0
CLASS_I_LOOKBACK_DAYS = 3 * 365


def score_manufacturer_trust(product: Dict[str, Any]) -> Dict[str, Any]:
    """Compute the separate +5 Manufacturer Trust dimension."""
    if not isinstance(product, dict):
        product = {}

    md = _safe_dict(product.get("manufacturer_data"))
    d1, d1_source = _score_d1_reputation(product, md)
    d2 = D2_DISCLOSURE if _has_full_disclosure(product) else 0.0

    bonus_features = _safe_dict(md.get("bonus_features"))
    d3 = (
        D3_PHYSICIAN
        if bool(product.get("claim_physician_formulated", bonus_features.get("physician_formulated", False)))
        else 0.0
    )

    region = _norm_text(product.get("manufacturing_region") or _safe_dict(md.get("country_of_origin")).get("country"))
    d4 = 0.0
    if bool(_safe_dict(md.get("country_of_origin")).get("high_regulation_country", False)):
        d4 = D4_HIGH_STANDARD_REGION
    elif region in DEFAULT_HIGH_STANDARD_REGIONS:
        d4 = D4_HIGH_STANDARD_REGION

    d5 = (
        D5_SUSTAINABILITY
        if bool(product.get("has_sustainable_packaging", bonus_features.get("sustainability_claim", False)))
        else 0.0
    )

    tail_raw = d3 + d4 + d5
    tail = min(D3_D4_D5_CAP, tail_raw)
    total = min(MANUFACTURER_TRUST_CAP, d1 + d2 + tail)
    components = {
        "D1_manufacturer_reputation": round(d1, 4),
        "D2_disclosure_quality": round(d2, 4),
        "D3_physician_formulated": round(d3, 4),
        "D4_high_standard_region": round(d4, 4),
        "D5_sustainability": round(d5, 4),
    }

    return {
        "score": round(total, 4),
        "max": MANUFACTURER_TRUST_CAP,
        "components": components,
        "metadata": {
            "D1_source": d1_source,
            "D3_D4_D5_raw": round(tail_raw, 4),
            "D3_D4_D5_applied": round(tail, 4),
            "tail_cap_applied": tail_raw > D3_D4_D5_CAP,
            "region": region,
        },
    }


def score_manufacturer_violations(product: Dict[str, Any]) -> Dict[str, Any]:
    """Compute the separate manufacturer-violation deduction.

    Returns a negative score or 0.0. Uses v3's graduated aggregate cap:
    default -25, 2 recent Class-I violations -35, 3+ recent Class-I -50.
    """
    if not isinstance(product, dict):
        product = {}

    deduction, items = _extract_violation_deduction(product)
    class_i_count = _count_class_i_in_3_years(items)
    cap = _resolve_manufacturer_cap(class_i_count)
    if deduction is None:
        applied = 0.0
        raw = 0.0
    else:
        raw = float(deduction)
        applied = max(raw, cap)

    return {
        "score": round(applied, 4),
        "floor": cap,
        "components": {
            "manufacturer_violation_deduction": round(applied, 4),
        },
        "metadata": {
            "raw_deduction": round(raw, 4),
            "cap_applied": raw < cap,
            "class_i_count_3y": class_i_count,
            "violation_count": len(items),
        },
    }


def _score_d1_reputation(product: Dict[str, Any], md: Dict[str, Any]) -> Tuple[float, str]:
    if bool(product.get("is_trusted_manufacturer", False)):
        return D1_TRUSTED, "trusted_manufacturer_flag"

    top = _safe_dict(md.get("top_manufacturer"))
    if bool(top.get("found", False)) and _norm_text(top.get("match_type")) == "exact":
        return D1_TRUSTED, "top_manufacturer_exact"

    if _has_verifiable_mid_tier_manufacturer_evidence(product):
        return D1_MID_TIER, "mid_tier_verified_evidence"

    return 0.0, "none"


def _has_verifiable_mid_tier_manufacturer_evidence(product: Dict[str, Any]) -> bool:
    cert_data = _safe_dict(product.get("certification_data"))
    gmp = _safe_dict(cert_data.get("gmp"))
    if bool(gmp.get("nsf_gmp", False)) or bool(gmp.get("fda_registered", False)):
        return True

    named_programs = _safe_list(product.get("named_cert_programs"))
    if not named_programs:
        programs = _safe_dict(cert_data.get("third_party_programs")).get("programs", [])
        if isinstance(programs, list):
            named_programs = [
                p.get("name") if isinstance(p, dict) else p
                for p in programs
            ]

    for program in named_programs:
        text = _norm_text(program)
        if not text:
            continue
        if "usp" in text or "nsf" in text or ("gmp" in text and "cert" in text):
            return True
    return False


def _has_full_disclosure(product: Dict[str, Any]) -> bool:
    ingredients = get_active_ingredients(product)
    has_missing_dose = any(
        (not bool(i.get("is_proprietary_blend"))) and (not has_usable_individual_dose(i))
        for i in ingredients
    )
    blends = _safe_list(product.get("proprietary_blends"))
    if not blends:
        blends = _safe_list(_safe_dict(product.get("proprietary_data")).get("blends"))
    has_hidden_blends = any(
        _norm_text(b.get("disclosure_level")) in {"none", "partial"}
        for b in blends
        if isinstance(b, dict)
    )
    return (not has_missing_dose) and (not has_hidden_blends)


def _extract_violation_deduction(product: Dict[str, Any]) -> Tuple[Optional[float], List[Dict[str, Any]]]:
    violations = _safe_dict(product.get("manufacturer_data")).get("violations", {})
    deduction: Optional[float] = None
    items: List[Dict[str, Any]] = []

    if isinstance(violations, dict):
        deduction = _as_float(violations.get("total_deduction_applied"), None)
        items = [item for item in _safe_list(violations.get("violations")) if isinstance(item, dict)]
        if deduction is None and items:
            if len(items) == 1:
                deduction = _as_float(
                    items[0].get("total_deduction_applied", items[0].get("total_deduction")),
                    None,
                )
            else:
                total = 0.0
                for item in items:
                    total += _as_float(
                        item.get("total_deduction_applied", item.get("total_deduction")),
                        0.0,
                    ) or 0.0
                deduction = total
    elif isinstance(violations, list):
        items = [item for item in violations if isinstance(item, dict)]
        total = 0.0
        for item in items:
            total += _as_float(
                item.get("total_deduction_applied", item.get("total_deduction")),
                0.0,
            ) or 0.0
        deduction = total

    return deduction, items


def _count_class_i_in_3_years(items: List[Dict[str, Any]], today: date | None = None) -> int:
    today = today or date.today()
    count = 0
    for item in items or []:
        if not isinstance(item, dict):
            continue
        if _norm_text(item.get("severity_level")) != "critical":
            continue
        try:
            dt = date.fromisoformat(str(item.get("date") or ""))
        except (TypeError, ValueError):
            continue
        if (today - dt).days <= CLASS_I_LOOKBACK_DAYS:
            count += 1
    return count


def _resolve_manufacturer_cap(class_i_count_3y: int) -> float:
    if class_i_count_3y >= 3:
        return MFG_CAP_THREE_OR_MORE_CLASS_I
    if class_i_count_3y >= 2:
        return MFG_CAP_TWO_CLASS_I
    return MFG_CAP_DEFAULT
