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
    _safe_list,
    daily_serving_multiplier,
    get_active_ingredients,
    primary_type_of,
)
from scoring_input_contract import get_source_score_eligible_active_rows


from scoring_v4.quality_score_config import block as _cfg_block

_CM = _cfg_block("category_magnitudes", "immune_support")["immune_support"]


IMMUNE_EVIDENCE_CAP = _CM["evidence_cap"]
HIGH_VARIABILITY_BOTANICAL_STACK_MIN_COUNT = _CM["high_variability_botanical_stack_min_count"]
HIGH_VARIABILITY_BOTANICAL_STACK_PENALTY = _CM["high_variability_botanical_stack_penalty"]
IMMUNE_DOSE_CAP = _CM["dose_cap"]
IMMUNE_DOSE_BANDS = {key: dict(band) for key, band in _CM["dose_bands"].items()}
IMMUNE_DOSE_ABOVE_BAND_FRACTION = _CM["dose_above_band_fraction"]
IMMUNE_DAILY_USE_DISCIPLINE_POINTS = _CM["daily_use_discipline_points"]
HIGH_ZINC_THRESHOLD_MG = _CM["high_zinc_threshold_mg"]
HIGH_VITAMIN_D_THRESHOLD_MCG = _CM["high_vitamin_d_threshold_mcg"]

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

    design_flags = _immune_design_flags(product, doses)
    high_zinc = design_flags["high_zinc"]
    high_d = design_flags["high_vitamin_d"]

    components = {
        "vitamin_c_daily_range": _band_score(doses, "vitamin_c_mg"),
        "vitamin_d_daily_range": 0.0 if high_d else _band_score(doses, "vitamin_d_mcg"),
        "zinc_daily_range": 0.0 if high_zinc else _band_score(doses, "zinc_mg"),
        "copper_balance": _band_score(doses, "copper_mg"),
        "selenium_daily_range": _band_score(doses, "selenium_mcg"),
        "beta_glucan_disclosed": _band_score(doses, "beta_glucan_mg"),
        "quercetin_disclosed": _band_score(doses, "quercetin_mg"),
        "elderberry_disclosed": _band_score(doses, "elderberry_mg"),
        "daily_use_discipline": 0.0 if (high_zinc or high_d) else IMMUNE_DAILY_USE_DISCIPLINE_POINTS,
    }

    score = min(IMMUNE_DOSE_CAP, sum(components.values()))
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
    """Return immune-specific design diagnostics and true complexity penalties.

    Formulation quality is already owned by the generic IQM/form engine.  The
    presence, count, or disclosed dose of immune ingredients belongs to
    Dose/Evidence and must not manufacture additional Formulation credit.
    """
    if not is_immune_support_product(product):
        return None

    identities = {
        identity
        for row in get_source_score_eligible_active_rows(product)
        if (identity := _active_id(row))
    }
    doses = immune_active_doses(product)
    high_zinc = (doses.get("zinc_mg") or 0.0) > HIGH_ZINC_THRESHOLD_MG
    botanical_count = _high_variability_botanical_count(product)
    herb_soup = botanical_count >= HIGH_VARIABILITY_BOTANICAL_STACK_MIN_COUNT

    penalties: Dict[str, float] = {}
    if herb_soup:
        penalties["immune_high_variability_botanical_stack"] = -HIGH_VARIABILITY_BOTANICAL_STACK_PENALTY

    return {
        "penalties": penalties,
        "metadata": {
            "profile_applied": False,
            "design_audit_applied": True,
            "identified_actives": sorted(identities),
            "active_doses": {k: round(v, 4) for k, v in doses.items()},
            "gummy_or_syrup": _is_gummy_or_syrup(product),
            "high_zinc": high_zinc,
            "high_variability_botanical_count": botanical_count,
        },
    }


def immune_support_evidence_cap(product: Dict[str, Any]) -> Optional[float]:
    if is_immune_support_product(product):
        return IMMUNE_EVIDENCE_CAP
    return None


def _immune_design_flags(product: Dict[str, Any], doses: Dict[str, float]) -> Dict[str, bool]:
    return {
        "high_zinc": (doses.get("zinc_mg") or 0.0) > HIGH_ZINC_THRESHOLD_MG,
        "high_vitamin_d": (doses.get("vitamin_d_mcg") or 0.0) > HIGH_VITAMIN_D_THRESHOLD_MCG,
        "gummy_or_syrup": _is_gummy_or_syrup(product),
        "high_glycemic_sugar": _has_high_glycemic_sugar(product),
    }


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


def _band_score(doses: Dict[str, float], dose_key: str) -> float:
    band = IMMUNE_DOSE_BANDS[dose_key]
    return _range_score(doses.get(dose_key), band["low"], band["high"], band["points"])


def _range_score(amount: Optional[float], low: float, high: float, cap: float) -> float:
    if amount is None or amount <= 0:
        return 0.0
    if low <= amount <= high:
        return cap
    if amount < low:
        return max(0.0, min(cap, (amount / low) * cap))
    return max(0.0, cap * IMMUNE_DOSE_ABOVE_BAND_FRACTION)


def _daily_serving_multiplier(product: Dict[str, Any]) -> float:
    return daily_serving_multiplier(product)


def _is_gummy_or_syrup(product: Dict[str, Any]) -> bool:
    form_text = _norm_text(
        f"{product.get('form_factor_canonical') or ''} {product.get('form_factor') or ''} {product.get('product_name') or ''}"
    )
    return any(token in form_text for token in ("gummy", "gummies", "syrup"))


def _has_high_glycemic_sugar(product: Dict[str, Any]) -> bool:
    dietary = _safe_dict((product or {}).get("dietary_sensitivity_data"))
    sugar = _safe_dict(dietary.get("sugar"))
    sweeteners = _safe_dict(dietary.get("sweeteners"))
    level = _norm_text(sugar.get("level"))
    sugar_sources = _safe_list(sugar.get("sugar_sources"))
    high_glycemic = _safe_list(
        sweeteners.get("high_glycemic") or sweeteners.get("high_glycemic_sweeteners")
    )
    return (
        level == "high"
        or bool(high_glycemic)
        or any("syrup" in _norm_text(source) for source in sugar_sources)
    )


def _high_variability_botanical_count(product: Dict[str, Any]) -> int:
    matched: set[str] = set()
    for row in get_active_ingredients(product):
        botanical = _high_variability_botanical_id(row)
        if botanical:
            matched.add(botanical)
    return len(matched)


def _high_variability_botanical_id(row: Dict[str, Any]) -> Optional[str]:
    keys = _row_keys(row)
    text = " ".join(keys)
    for botanical in sorted(_HIGH_VARIABILITY_BOTANICALS, key=len, reverse=True):
        if _matches_any(keys, text, (botanical,)):
            return "ginseng" if botanical == "panax ginseng" else botanical
    return None
