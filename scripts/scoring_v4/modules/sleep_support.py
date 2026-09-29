"""Sleep-support calibration helpers for the generic v4 module.

Sleep products currently route through ``generic``. These helpers keep the
generic fallback intact while giving well-known sleep actives category-aware
dose and format treatment.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from scoring_v4.modules.generic_helpers import (
    daily_serving_multiplier,
    daily_serving_range,
    get_active_ingredients,
    primary_type_of,
    _as_float,
    _norm_text,
)


MELATONIN_CANONICALS = frozenset({"melatonin"})
FIVE_HTP_CANONICALS = frozenset({"5_htp", "5-htp", "5 hydroxytryptophan"})
SLEEP_CANONICALS = MELATONIN_CANONICALS | FIVE_HTP_CANONICALS




def is_sleep_support_product(product: Dict[str, Any]) -> bool:
    return primary_type_of(product) == "sleep_support"


def score_sleep_support_dose(product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return a sleep-specific dose score payload, or None when not applicable.

    The score is on the generic dose component's 0..22 supplemental-window scale.
    It intentionally avoids creating a new v4 module; sleep products remain
    generic unless a known sleep active needs category-aware calibration.
    """
    if not is_sleep_support_product(product):
        return None

    for active, canonicals, band in (
        ("melatonin", MELATONIN_CANONICALS, _melatonin_score),
        ("5_htp", FIVE_HTP_CANONICALS, _five_htp_sleep_score),
    ):
        daily_mg = active_daily_mg(product, canonicals)
        if daily_mg is not None:
            # Adequacy at the minimum directed use, the high-dose bands at the
            # maximum: the lower of the two.
            top_mg = active_daily_mg(product, canonicals, top=True)
            score, label = min(band(top_mg), band(daily_mg), key=lambda scored: scored[0])
            payload = _payload(active, daily_mg, score, label)
            payload["daily_mg_max"] = round(top_mg, 4)
            return payload

    return None


def active_daily_mg(product: Dict[str, Any], canonicals: Iterable[str], *, top: bool = False) -> Optional[float]:
    """Daily amount at the minimum directed use, or at the maximum (``top``)."""
    canonical_set = {_norm_text(c) for c in canonicals}
    daily_multiplier = daily_serving_range(product)[1] if top else _daily_serving_multiplier(product)
    best: Optional[float] = None
    for row in get_active_ingredients(product):
        if not _row_matches(row, canonical_set):
            continue
        mg = _row_quantity_mg(row)
        if mg is None:
            continue
        daily_mg = mg * daily_multiplier
        best = daily_mg if best is None else max(best, daily_mg)
    if best is None or best <= 0:
        return None
    return best


def _payload(active: str, daily_mg: float, score: float, band: str) -> Dict[str, Any]:
    return {
        "score": round(score, 4),
        "active": active,
        "daily_mg": round(daily_mg, 4),
        "band": band,
    }


def _melatonin_score(daily_mg: float) -> tuple[float, str]:
    if daily_mg < 0.3:
        return 8.0, "below_low_dose_range"
    if daily_mg <= 1.0:
        return 22.0, "low_dose_preferred"
    if daily_mg <= 3.0:
        return 20.0, "standard_dose"
    if daily_mg <= 5.0:
        return 17.0, "upper_common_dose"
    if daily_mg <= 10.0:
        return 11.0, "high_dose"
    if daily_mg <= 20.0:
        return 5.0, "very_high_dose"
    return 2.0, "extreme_dose"


def _five_htp_sleep_score(daily_mg: float) -> tuple[float, str]:
    if daily_mg < 50.0:
        return 8.0, "below_sleep_support_range"
    if daily_mg <= 300.0:
        return 16.0, "sleep_support_preliminary"
    if daily_mg <= 400.0:
        return 12.0, "high_sleep_support_dose"
    return 8.0, "very_high_sleep_support_dose"


def _row_matches(row: Dict[str, Any], canonical_set: set[str]) -> bool:
    fields = (
        row.get("canonical_id"),
        row.get("scoring_parent_id"),
        row.get("evidence_canonical_id"),
        row.get("standard_name"),
        row.get("name"),
        row.get("matched_form"),
    )
    text = " ".join(_norm_text(value).replace("_", " ") for value in fields)
    keys = {_norm_text(value) for value in fields if _norm_text(value)}
    keys |= {key.replace("_", " ") for key in keys}
    if keys & canonical_set:
        return True
    return any(key and key in text for key in canonical_set)


def _row_quantity_mg(row: Dict[str, Any]) -> Optional[float]:
    quantity = _as_float(row.get("quantity"), None)
    if quantity is None or quantity <= 0:
        return None
    unit = _norm_text(row.get("unit_normalized") or row.get("unit"))
    compact = unit.replace(" ", "")
    if unit in {"mg", "milligram", "milligrams", "milligram(s)"} or compact in {
        "mg",
        "milligram",
        "milligrams",
        "milligram(s)",
    }:
        return quantity
    if unit in {"g", "gram", "grams", "gram(s)"} or compact in {
        "g",
        "gram",
        "grams",
        "gram(s)",
    }:
        return quantity * 1000.0
    if unit in {"mcg", "ug", "microgram", "micrograms", "microgram(s)"} or compact in {
        "mcg",
        "ug",
        "microgram",
        "micrograms",
        "microgram(s)",
    }:
        return quantity / 1000.0
    return None


def _daily_serving_multiplier(product: Dict[str, Any]) -> float:
    return daily_serving_multiplier(product)
