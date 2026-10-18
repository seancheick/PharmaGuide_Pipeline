"""v4 fiber/digestive dose adapter."""

from __future__ import annotations

from typing import Any, Dict
from dataclasses import asdict

from scoring_v4.exposure import row_exposure
from scoring_input_contract import dose_disclosure_status

from scoring_v4.modules.fiber_digestive_helpers import (
    fiber_rows,
    has_fiber_context,
    is_fiber_row,
    nutrition_fiber_exposure,
)
from scoring_v4.modules.generic_dose import (
    score_dose as score_generic_dose,
    _score_declared_purpose_window,
    _unread_declared_purpose_rows,
    _row_identity_keys,
)
from scoring_v4.modules.generic_helpers import (
    archetype_dose_reference,
    dose_reference_scope,
    unbenchmarked_dose_credit,
    _norm_text,
)


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
    nutrition_exposure = nutrition_fiber_exposure(product)
    # A marketing title cannot establish fiber mass or a fiber benchmark.
    # Nonfiber digestive preparations use the existing ingredient Dose owner.
    if not rows and not (has_fiber_context(product) and nutrition_exposure is not None):
        with dose_reference_scope(archetype_dose_reference("fiber_digestive")):
            return score_generic_dose(product)
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
    unread = (nutrition_exposure is None and any(
        exposure.benchmark_amount is None and dose_disclosure_status(row) != "not_disclosed_blend"
        for row, exposure in zip(rows, exposures)))
    hidden = (nutrition_exposure is None and any(
        exposure.benchmark_amount is None and dose_disclosure_status(row) == "not_disclosed_blend"
        for row, exposure in zip(rows, exposures)))
    # V4.1 Step 4: fiber-type and amount-printed bonuses are retired;
    # Transparency owns disclosure and Dose owns the effective amount.
    effective = unbenchmarked_dose_credit() if hidden else _fiber_effective_dose_points(daily_amount)
    # Keep the original product for source-role classification: an incidental
    # co-ingredient does not become a purpose when fiber rows are removed.
    # Every physical fiber row belongs to the one existing aggregate vote.
    fiber_keys = set()
    for row in rows:
        fiber_keys.update(_row_identity_keys(row))
        fiber_keys.add(_norm_text(row.get("raw_source_path") or row.get("source_row_ref")))
    peers = [entry for entry in _score_declared_purpose_window(product)[7]
             if _norm_text(entry.get("ingredient")) not in fiber_keys]
    unread = unread or any(not is_fiber_row(row) for row in _unread_declared_purpose_rows(product))
    unread = unread or any(entry.get("assessment") == "unresolved_source_quantity" for entry in peers)
    contributions = [{"ingredient": "fiber", "assessment": "hidden_amount_neutral" if hidden else "no_benchmark_neutral",
                      "credit_raw": round(effective, 4)}, *peers]
    count = len(contributions)
    components = {"fiber_effective_dose": round(effective / count, 4)}
    if peers:
        components["supplemental_window_proxy"] = round(sum(entry["credit_raw"] for entry in peers) / count, 4)
    score = max(0.0, min(DIMENSION_CAP, sum(components.values())))

    return {
        "score": None if unread else round(score, 4),
        "max": DIMENSION_CAP,
        "components": components,
        "penalties": {},
        "phase": PHASE_MARKER,
        "metadata": {
            **({"assessment_status": "incomplete", "reason_code": "unresolved_source_quantity"} if unread else {}),
            "phase": PHASE_MARKER,
            "method": "fiber_effective_dose_v1",
            "dose_participation_basis": "declared_purpose_equal_weight" if peers else "fiber_aggregate",
            "dose_contributions": contributions,
            "fiber_dose_source": source,
            "fiber_grams_per_serving": round(grams, 4),
            "fiber_rows_evaluated": len(rows),
            "fiber_amount_kind": "total_dietary_fiber" if nutrition_exposure is not None else "ingredient_mass",
            "fiber_grams_daily_minimum": daily_minimum,
            "fiber_grams_daily_maximum": daily_maximum,
            "fiber_grams_daily_benchmark": round(daily_amount, 4),
            "benchmark_exposures": [asdict(e) for e in exposures],
            "daily_interval_selection": "minimum_directed_use",
            **({"exposure_uncertainty": next((e.uncertainty for e in exposures if not e.exact), "fiber_amount_missing")} if not exact else {}),
        },
    }


def _fiber_effective_dose_points(grams: float) -> float:
    """Completed review: generic fiber mass establishes no clinical curve."""
    return unbenchmarked_dose_credit() if grams > 0 else 0.0
