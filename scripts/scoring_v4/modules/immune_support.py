"""Immune-support calibration helpers for the generic v4 module.

Immune products still route through ``generic``. These helpers give the generic
module category-aware treatment for daily immune formulas without creating a new
public route contract.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from scoring_v4.modules.generic_helpers import (
    _as_float,
    _norm_text,
    _safe_dict,
    get_active_ingredients,
    primary_type_of,
)


IMMUNE_FORMULATION_BONUS_CAP = 12.0
IMMUNE_EVIDENCE_FLOOR_CAP = 16.5

_ALIASES = {
    "vitamin_c": ("vitamin_c", "ascorbic acid", "ascorbate", "ester-c", "vitamin c"),
    "vitamin_d": ("vitamin_d", "vitamin_d3", "cholecalciferol", "vitamin d", "vitamin d3"),
    "zinc": ("zinc",),
    "copper": ("copper",),
    "selenium": ("selenium",),
    "beta_glucan": ("beta_glucan", "beta glucan", "beta-glucan", "beta glucans"),
    "quercetin": ("quercetin",),
    "elderberry": ("elderberry", "sambucus"),
}

_HIGH_VARIABILITY_BOTANICALS = {
    "echinacea",
    "goldenseal",
    "astragalus",
    "ginseng",
    "panax ginseng",
    "andrographis",
    "oregano oil",
}


def is_immune_support_product(product: Dict[str, Any]) -> bool:
    return primary_type_of(product) == "immune_support"


def score_immune_support_dose(product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not is_immune_support_product(product):
        return None

    doses = immune_active_doses(product)
    if not doses:
        return None

    high_zinc = (doses.get("zinc_mg") or 0.0) > 40.0
    high_d = (doses.get("vitamin_d_mcg") or 0.0) > 100.0

    components = {
        "vitamin_c_daily_range": _range_score(doses.get("vitamin_c_mg"), 100.0, 1000.0, 3.0),
        "vitamin_d_daily_range": 0.0 if high_d else _range_score(doses.get("vitamin_d_mcg"), 15.0, 50.0, 3.0),
        "zinc_daily_range": 0.0 if high_zinc else _range_score(doses.get("zinc_mg"), 8.0, 25.0, 3.0),
        "copper_balance": _range_score(doses.get("copper_mg"), 0.5, 2.0, 1.5),
        "selenium_daily_range": _range_score(doses.get("selenium_mcg"), 45.0, 200.0, 1.5),
        "beta_glucan_disclosed": _range_score(doses.get("beta_glucan_mg"), 100.0, 250.0, 3.0),
        "quercetin_disclosed": _range_score(doses.get("quercetin_mg"), 250.0, 1000.0, 2.5),
        "elderberry_disclosed": _range_score(doses.get("elderberry_mg"), 100.0, 600.0, 2.5),
        "daily_use_discipline": 0.0 if (high_zinc or high_d) else 2.0,
    }

    score = min(22.0, sum(components.values()))
    return {
        "score": round(score, 4),
        "components": {k: round(v, 4) for k, v in components.items()},
        "metadata": {
            "active_doses": {k: round(v, 4) for k, v in doses.items()},
            "high_zinc": high_zinc,
            "high_vitamin_d": high_d,
        },
    }


def immune_support_formulation_adjustment(product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not is_immune_support_product(product):
        return None

    doses = immune_active_doses(product)
    if not doses:
        return None

    foundation_count = sum(
        1
        for key in ("vitamin_c_mg", "vitamin_d_mcg", "zinc_mg")
        if (doses.get(key) or 0.0) > 0
    )
    balance_count = sum(
        1 for key in ("copper_mg", "selenium_mcg") if (doses.get(key) or 0.0) > 0
    )
    targeted_count = sum(
        1
        for key in ("beta_glucan_mg", "quercetin_mg", "elderberry_mg")
        if (doses.get(key) or 0.0) > 0
    )

    high_zinc = (doses.get("zinc_mg") or 0.0) > 40.0
    form_text = _norm_text(
        f"{product.get('form_factor_canonical') or ''} {product.get('form_factor') or ''} {product.get('product_name') or ''}"
    )
    gummy_or_syrup = any(token in form_text for token in ("gummy", "gummies", "syrup"))
    herb_soup = _high_variability_botanical_count(product) >= 3

    components = {
        "immune_foundation_design": min(5.0, foundation_count * 1.7),
        "immune_mineral_balance": min(2.0, balance_count * 1.0),
        "immune_targeted_disclosure": min(3.0, targeted_count * 1.0),
        "immune_daily_clean_design": 2.0 if not (gummy_or_syrup or herb_soup or high_zinc) else 0.0,
    }
    bonus = min(IMMUNE_FORMULATION_BONUS_CAP, sum(components.values()))

    penalties: Dict[str, float] = {}
    if gummy_or_syrup:
        penalties["B1_immune_gummy_or_syrup"] = -2.0
    if high_zinc:
        penalties["B7_immune_high_zinc_daily_use"] = -2.0
    if herb_soup:
        penalties["immune_high_variability_botanical_stack"] = -3.0

    return {
        "bonus": round(bonus, 4),
        "components": {k: round(v, 4) for k, v in components.items()},
        "penalties": penalties,
        "metadata": {
            "profile_applied": True,
            "active_doses": {k: round(v, 4) for k, v in doses.items()},
            "gummy_or_syrup": gummy_or_syrup,
            "high_zinc": high_zinc,
            "high_variability_botanical_count": _high_variability_botanical_count(product),
        },
    }


def immune_support_evidence_floor(product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not is_immune_support_product(product):
        return None

    doses = immune_active_doses(product)
    if not doses:
        return None

    foundation = sum(
        1
        for key in ("vitamin_c_mg", "vitamin_d_mcg", "zinc_mg")
        if (doses.get(key) or 0.0) > 0
    )
    targeted = sum(
        1
        for key in ("beta_glucan_mg", "quercetin_mg", "elderberry_mg")
        if (doses.get(key) or 0.0) > 0
    )
    floor = 0.0
    if foundation >= 3:
        floor = 14.0
    elif foundation >= 2:
        floor = 12.0
    if foundation >= 3 and targeted >= 2:
        floor = 16.0
    if foundation >= 3 and targeted >= 3:
        floor = IMMUNE_EVIDENCE_FLOOR_CAP

    if floor <= 0.0:
        return None
    return {
        "floor": round(floor, 4),
        "components": {
            "immune_support_evidence_floor": round(floor, 4),
        },
        "metadata": {
            "foundation_count": foundation,
            "targeted_count": targeted,
        },
    }


def immune_support_evidence_cap(product: Dict[str, Any]) -> Optional[float]:
    if is_immune_support_product(product):
        return 17.0
    return None


def immune_active_doses(product: Dict[str, Any]) -> Dict[str, float]:
    daily_multiplier = _daily_serving_multiplier(product)
    out: Dict[str, float] = {}
    for row in get_active_ingredients(product):
        active = _active_id(row)
        if not active:
            continue
        amount = _row_amount(row, active)
        if amount is None or amount <= 0:
            continue
        key = {
            "vitamin_c": "vitamin_c_mg",
            "vitamin_d": "vitamin_d_mcg",
            "zinc": "zinc_mg",
            "copper": "copper_mg",
            "selenium": "selenium_mcg",
            "beta_glucan": "beta_glucan_mg",
            "quercetin": "quercetin_mg",
            "elderberry": "elderberry_mg",
        }[active]
        daily = amount * daily_multiplier
        out[key] = max(out.get(key, 0.0), daily)
    return out


def _active_id(row: Dict[str, Any]) -> Optional[str]:
    keys = _row_keys(row)
    text = " ".join(key.replace("_", " ") for key in keys)
    for active, aliases in _ALIASES.items():
        if _matches_any(keys, text, aliases):
            return active
    return None


def _row_keys(row: Dict[str, Any]) -> set[str]:
    fields = (
        row.get("canonical_id"),
        row.get("scoring_parent_id"),
        row.get("evidence_canonical_id"),
        row.get("standard_name"),
        row.get("name"),
        row.get("matched_form"),
        row.get("raw_source_text"),
    )
    keys = {_norm_text(value) for value in fields if _norm_text(value)}
    keys |= {key.replace("_", " ") for key in keys}
    return keys


def _matches_any(keys: set[str], text: str, aliases: Iterable[str]) -> bool:
    for alias in aliases:
        norm = _norm_text(alias)
        if norm in keys or norm.replace("_", " ") in keys:
            return True
        if norm and norm in text:
            return True
    return False


def _row_amount(row: Dict[str, Any], active: str) -> Optional[float]:
    quantity = _as_float(row.get("quantity"), None)
    if quantity is None or quantity <= 0:
        return None
    unit = _norm_text(row.get("unit_normalized") or row.get("unit"))
    compact = unit.replace(" ", "")
    if compact in {"mg", "milligram", "milligrams", "milligram(s)"}:
        return quantity
    if compact in {"g", "gram", "grams", "gram(s)"}:
        return quantity * 1000.0
    if compact in {"mcg", "ug", "microgram", "micrograms", "microgram(s)"}:
        return quantity if active in {"vitamin_d", "selenium"} else quantity / 1000.0
    if compact == "iu" and active == "vitamin_d":
        return quantity / 40.0
    return None


def _range_score(amount: Optional[float], low: float, high: float, cap: float) -> float:
    if amount is None or amount <= 0:
        return 0.0
    if low <= amount <= high:
        return cap
    if amount < low:
        return max(0.0, min(cap, (amount / low) * cap))
    return max(0.0, cap * 0.5)


def _daily_serving_multiplier(product: Dict[str, Any]) -> float:
    serving_basis = _safe_dict(product.get("serving_basis"))
    for key in ("max_servings_per_day", "min_servings_per_day"):
        value = _as_float(serving_basis.get(key), None)
        if value is not None and value > 0:
            return value
    return 1.0


def _high_variability_botanical_count(product: Dict[str, Any]) -> int:
    count = 0
    for row in get_active_ingredients(product):
        keys = _row_keys(row)
        text = " ".join(keys)
        if _matches_any(keys, text, _HIGH_VARIABILITY_BOTANICALS):
            count += 1
    return count
