"""v4 fiber/digestive formulation adapter."""

from __future__ import annotations

from typing import Any, Dict, List

from scoring_v4.modules.fiber_digestive_helpers import (
    canonical,
    fiber_rows,
    has_fiber_context,
    nutrition_fiber_grams,
    product_name_text,
    row_text,
)
from scoring_v4.modules.generic_formulation import (
    score_formulation as score_generic_formulation,
    shared_formulation_penalty_detail,
)
from scoring_v4.modules.generic_helpers import _safe_dict, _safe_list, get_active_ingredients


DIMENSION_CAP = 30.0
PHASE_MARKER = "P1.8_fiber_digestive_formulation_v1"
STIMULANT_LAXATIVE_CANONICALS = {"senna", "cascara_sagrada", "aloe_latex", "aloe_emodin"}


def score_formulation(product: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(product, dict):
        product = {}

    rows = fiber_rows(product)
    if not rows and not has_fiber_context(product):
        return score_generic_formulation(product)

    all_rows = get_active_ingredients(product)
    source_quality, source_class = _source_quality(rows, product)
    disclosure = _fiber_disclosure(rows, product)
    focus = _fiber_focus(all_rows, rows)
    clean_daily = _clean_daily_use(product)
    practicality = _practicality(product)

    components: Dict[str, float] = {
        "fiber_source_quality": round(source_quality, 4),
        "fiber_disclosure": round(disclosure, 4),
        "fiber_formula_focus": round(focus, 4),
        "fiber_clean_daily_use": round(clean_daily, 4),
        "fiber_practicality": round(practicality, 4),
    }

    shared = shared_formulation_penalty_detail(product)
    penalties: Dict[str, float] = dict(shared["penalties"])
    penalties.update(_fiber_penalties(product, all_rows))

    positive = sum(components.values())
    penalty_total = sum(abs(float(v or 0.0)) for v in penalties.values())
    score = max(0.0, min(DIMENSION_CAP, positive - penalty_total))

    return {
        "score": round(score, 4),
        "max": DIMENSION_CAP,
        "components": components,
        "penalties": penalties,
        "phase": PHASE_MARKER,
        "metadata": {
            "phase": PHASE_MARKER,
            "fiber_profile_applied": True,
            "fiber_source_class": source_class,
            "fiber_rows_evaluated": len(rows),
            "dietary_sugar": shared["metadata"].get("dietary_sugar"),
        },
    }


def _source_quality(rows: List[Dict[str, Any]], product: Dict[str, Any]) -> tuple[float, str]:
    text = " ".join(row_text(row) for row in rows) + " " + product_name_text(product)
    canons = {canonical(row) for row in rows}
    if {"psyllium", "psyllium_husk"} & canons or "psyllium" in text:
        return 12.0, "psyllium"
    if any(term in text for term in ("acacia", "partially hydrolyzed guar", "guar", "glucomannan", "konjac", "beta glucan")):
        return 10.0, "viscous_or_gel_fiber"
    if any(term in text for term in ("inulin", "prebiotic", "resistant starch")):
        return 9.0, "prebiotic_fiber"
    if rows:
        return 7.0, "generic_fiber"
    return 3.0, "fiber_claim_without_mapped_fiber"


def _fiber_disclosure(rows: List[Dict[str, Any]], product: Dict[str, Any]) -> float:
    has_grams = nutrition_fiber_grams(product) is not None or any(row.get("quantity") for row in rows)
    has_named_type = bool(rows)
    if has_grams and has_named_type:
        return 6.0
    if has_grams:
        return 4.0
    if has_named_type:
        return 3.0
    return 0.0


def _fiber_focus(all_rows: List[Dict[str, Any]], rows: List[Dict[str, Any]]) -> float:
    if _has_stimulant_laxative(all_rows):
        return 1.0
    if not all_rows:
        return 2.0
    if len(all_rows) <= max(2, len(rows) + 1):
        return 5.0
    return 3.0


def _clean_daily_use(product: Dict[str, Any]) -> float:
    dietary = _safe_dict((product or {}).get("dietary_sensitivity_data"))
    sugar = _safe_dict(dietary.get("sugar"))
    sweeteners = _safe_dict(dietary.get("sweeteners"))
    score = 5.0
    if sugar.get("has_added_sugar") or float(sugar.get("amount_g") or 0.0) >= 3.0:
        score -= 2.5
    if _safe_list(sweeteners.get("high_glycemic")):
        score -= 1.0
    if _safe_list(sweeteners.get("artificial")):
        score -= 0.75
    if _safe_list(sweeteners.get("sugar_alcohols")):
        score -= 0.75
    return max(0.0, score)


def _practicality(product: Dict[str, Any]) -> float:
    text = product_name_text(product)
    if any(term in text for term in ("gummy", "chew", "candy")):
        return 0.5
    if any(term in text for term in ("cleanse", "detox")):
        return 0.5
    return 2.0


def _fiber_penalties(product: Dict[str, Any], rows: List[Dict[str, Any]]) -> Dict[str, float]:
    text = product_name_text(product)
    penalties: Dict[str, float] = {}
    if any(term in text for term in ("gummy", "chew", "candy")):
        penalties["fiber_gummy_delivery_penalty"] = -3.0
    if any(term in text for term in ("cleanse", "detox")):
        penalties["fiber_cleanse_detox_penalty"] = -3.0
    if _has_stimulant_laxative(rows):
        penalties["fiber_stimulant_laxative_penalty"] = -8.0
    return penalties


def _has_stimulant_laxative(rows: List[Dict[str, Any]]) -> bool:
    for row in rows:
        cid = canonical(row)
        text = row_text(row)
        if cid in STIMULANT_LAXATIVE_CANONICALS:
            return True
        if any(term in text for term in ("senna", "cascara", "aloe latex", "aloe-emodin")):
            return True
    return False
