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
    unbenchmarked_dose_credit,
    _norm_text,
    _row_quantity_mg,
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

    for active, canonicals in (
        ("melatonin", MELATONIN_CANONICALS),
        ("5_htp", FIVE_HTP_CANONICALS),
    ):
        daily_mg = active_daily_mg(product, canonicals)
        if daily_mg is not None:
            # The daily exposure is descriptive; no clinical window follows
            # from the isolated sleep regimens reviewed in this batch.
            top_mg = active_daily_mg(product, canonicals, top=True)
            score, label = unbenchmarked_dose_credit(), "no_benchmark_neutral"
            payload = _payload(active, daily_mg, score, label)
            payload["daily_mg_max"] = round(top_mg, 4)
            return payload

    return None


def score_sleep_purpose_dose(
    product: Dict[str, Any], row: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Assess one declared sleep-active purpose on the shared 0..22 scale."""
    if not is_sleep_support_product(product):
        return None
    for active, canonicals in (
        ("melatonin", MELATONIN_CANONICALS),
        ("5_htp", FIVE_HTP_CANONICALS),
    ):
        canonical_set = {_norm_text(value) for value in canonicals}
        if not _row_matches(row, canonical_set):
            continue
        mg = _row_quantity_mg(row)
        if mg is None:
            return None
        daily_mg = mg * _daily_serving_multiplier(product)
        daily_mg_max = mg * daily_serving_range(product)[1]
        score, label = unbenchmarked_dose_credit(), "no_benchmark_neutral"
        payload = _payload(active, daily_mg, score, label)
        payload["daily_mg_max"] = round(daily_mg_max, 4)
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


def _daily_serving_multiplier(product: Dict[str, Any]) -> float:
    return daily_serving_multiplier(product)
