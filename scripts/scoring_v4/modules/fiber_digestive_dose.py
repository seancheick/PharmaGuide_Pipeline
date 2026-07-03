"""v4 fiber/digestive dose adapter."""

from __future__ import annotations

from typing import Any, Dict

from scoring_v4.modules.fiber_digestive_helpers import (
    fiber_rows,
    has_fiber_context,
    nutrition_fiber_grams,
    total_fiber_grams,
)
from scoring_v4.modules.generic_dose import score_dose as score_generic_dose


DIMENSION_CAP = 25.0
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

    label_grams = nutrition_fiber_grams(product)
    row_grams = total_fiber_grams(rows)
    grams = label_grams if label_grams is not None else row_grams
    source = "nutrition_facts" if label_grams is not None else "ingredient_rows"

    effective = _fiber_effective_dose_points(grams)
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
