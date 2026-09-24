"""v4 fiber/digestive dose adapter."""

from __future__ import annotations

from typing import Any, Dict
from dataclasses import asdict

from scoring_v4.exposure import row_exposure

from scoring_v4.modules.fiber_digestive_helpers import (
    fiber_rows,
    has_fiber_context,
    nutrition_fiber_exposure,
)
from scoring_v4.modules.generic_dose import score_dose as score_generic_dose


from scoring_v4.quality_score_config import block as _cfg_block

_DM = _cfg_block("dose_magnitudes", "fiber_digestive")["fiber_digestive"]


DIMENSION_CAP = _DM["dimension_cap"]
PHASE_MARKER = "P1.8_fiber_digestive_dose_v1"


def score_dose(product: Dict[str, Any]) -> Dict[str, Any]:
    """Score fiber dose from nutrition-facts fiber grams or fiber-row mass.

    Digestive enzyme products live in the same taxonomy bucket but do not have
    fiber grams; those fall back to the generic dose scorer, which already
    supports enzyme-activity dose units.
    """
    if not isinstance(product, dict):
        product = {}

    rows = fiber_rows(product)
    if not rows and not has_fiber_context(product):
        return score_generic_dose(product)

    nutrition_exposure = nutrition_fiber_exposure(product)
    # Preserve the distinction between
    # total dietary fiber and ingredient mass (neither implies soluble fiber).
    exposures = ([nutrition_exposure] if nutrition_exposure is not None else
                 [row_exposure(product, row, basis="daily", unit="g") for row in rows])
    grams = sum(e.per_serving_amount or 0.0 for e in exposures)
    source = "nutrition_facts" if nutrition_exposure is not None else "ingredient_rows"
    exact = bool(exposures) and all(e.exact for e in exposures)
    daily_minimum = sum(e.minimum for e in exposures) if exact else None
    daily_maximum = sum(e.maximum for e in exposures) if exact else None
    daily_amount = sum(e.benchmark_amount for e in exposures if e.benchmark_amount is not None)
    effective = _fiber_effective_dose_points(daily_amount)
    type_bonus = _fiber_type_bonus(rows)
    disclosure_bonus = 1.0 if grams > 0 else 0.0
    score = max(0.0, min(DIMENSION_CAP, effective + type_bonus + disclosure_bonus))

    return {
        "score": round(score, 4),
        "max": DIMENSION_CAP,
        "components": {
            "fiber_effective_dose": round(effective, 4),
            "fiber_type_specificity": round(type_bonus, 4),
            "fiber_dose_disclosure": round(disclosure_bonus, 4),
        },
        "penalties": {},
        "phase": PHASE_MARKER,
        "metadata": {
            "phase": PHASE_MARKER,
            "method": "fiber_effective_dose_v1",
            "fiber_dose_source": source,
            "fiber_grams_per_serving": round(grams, 4),
            "fiber_rows_evaluated": len(rows),
            "fiber_amount_kind": "total_dietary_fiber" if nutrition_exposure is not None else "ingredient_mass",
            "fiber_grams_daily_minimum": daily_minimum,
            "fiber_grams_daily_maximum": daily_maximum,
            "fiber_grams_daily_benchmark": round(daily_amount, 4),
            "benchmark_exposures": [asdict(e) for e in exposures],
            "daily_interval_selection": "maximum_directed_use",
            **({"exposure_uncertainty": next((e.uncertainty for e in exposures if not e.exact), "fiber_amount_missing")} if not exact else {}),
        },
    }


def _fiber_effective_dose_points(grams: float) -> float:
    if grams >= 7.0:
        return 22.0
    if grams >= 5.0:
        return 18.0
    if grams >= 3.0:
        return 13.0
    if grams >= 1.0:
        return 7.0
    if grams > 0.0:
        return max(1.0, grams * 4.0)
    return 0.0


def _fiber_type_bonus(rows: list[Dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    text = " ".join(str(row.get("canonical_id") or row.get("name") or "").lower() for row in rows)
    if any(term in text for term in ("psyllium", "acacia", "guar", "glucomannan", "beta_glucan")):
        return 2.0
    if any(term in text for term in ("inulin", "prebiotic", "fiber")):
        return 1.0
    return 0.0
