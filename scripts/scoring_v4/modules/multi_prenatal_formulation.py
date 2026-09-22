"""v4 multi/prenatal Formulation dimension (P3.1).

Formulation for multis and prenatals is panel-aware:

  - Score average form quality across dose-bearing micronutrients. The IQM
    bio_score is the one form-quality owner.
  - Apply the neutral value as a true floor without reducing panels whose
    sourced form quality is already higher.
  - Credit panel-wide individual dose disclosure.
  - Premium-form counts and preferred-form name rankings are not scored
    (quality_score 1.7.0): they re-ranked the same IQM rating, so panel size
    and form wording add nothing at equal form quality.
  - Dosage form earns or loses nothing by itself. A gummy's real consequences
    (sugar through the shared penalty; missing/low doses and prenatal-critical
    coverage in P3.2 Dose) are scored where they belong.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from scoring_v4.modules.generic_helpers import (
    bio_score_of,
    get_active_ingredients,
    has_usable_individual_dose,
    is_scorable,
    restates_label_row,
    _as_float,
)
from scoring_v4.modules.generic_formulation import (
    apply_formulation_presence_floor,
    shared_formulation_penalty_detail,
)


from scoring_v4.quality_score_config import block as _cfg_block

_FVM = _cfg_block("formulation_variant_magnitudes", "multi_prenatal")["multi_prenatal"]


CAP_FORMULATION = _FVM["cap_formulation"]
FORMULATION_PRESENCE_FLOOR = _FVM["formulation_presence_floor"]
CAP_PANEL_FORM_QUALITY = _FVM["cap_panel_form_quality"]
CAP_PANEL_DISCLOSURE_STRUCTURE = _FVM["cap_panel_disclosure_structure"]

PANEL_FORM_NEUTRAL_FLOOR = _FVM["panel_form_neutral_floor"]
BIO_SCORE_MAX = _FVM["bio_score_max"]

PHASE_MARKER = "P3.1_multi_prenatal_formulation"


def _clamp(low: float, high: float, value: float) -> float:
    return max(low, min(high, value))


def _round(value: float) -> float:
    return round(float(value), 2)


def _active_ingredients(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    return get_active_ingredients(product)


def _scorable_ingredients(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = _active_ingredients(product)
    return [ing for ing in rows if is_scorable(ing) and not restates_label_row(ing, rows)]


def _score_panel_form_quality(product: Dict[str, Any]) -> tuple[float, float | None, float | None]:
    """Panel-wide A1 analogue with a non-decreasing neutral floor."""
    rows = _scorable_ingredients(product)
    if not rows:
        return 0.0, None, None

    weighted: List[tuple[float, float]] = []
    for ing in rows:
        score = bio_score_of(ing)
        if score is None:
            score = PANEL_FORM_NEUTRAL_FLOOR if ing.get("mapped") else 0.0
        weight = _as_float(ing.get("dosage_importance"), 1.0) or 1.0
        if weight <= 0:
            weight = 1.0
        weighted.append((_clamp(0.0, BIO_SCORE_MAX, score), weight))

    denom = sum(weight for _, weight in weighted)
    if denom <= 0:
        return 0.0, None, None
    avg = sum(score * weight for score, weight in weighted) / denom
    effective = max(avg, PANEL_FORM_NEUTRAL_FLOOR)
    contribution = _clamp(0.0, CAP_PANEL_FORM_QUALITY, (effective / BIO_SCORE_MAX) * CAP_PANEL_FORM_QUALITY)
    return _round(contribution), _round(avg), _round(effective)


def _dose_coverage(rows: Iterable[Dict[str, Any]]) -> float:
    rows_list = [row for row in rows if isinstance(row, dict)]
    if not rows_list:
        return 0.0
    dose_count = sum(1 for row in rows_list if has_usable_individual_dose(row))
    return round(dose_count / len(rows_list), 4)


def _score_panel_disclosure_structure(product: Dict[str, Any]) -> tuple[float, float]:
    rows = _active_ingredients(product)
    coverage = _dose_coverage(rows)
    if coverage >= 0.9:
        return 2.0, coverage
    if coverage >= 0.6:
        return 1.0, coverage
    return 0.0, coverage


def score_formulation(product: Any) -> Dict[str, Any]:
    """Score the multi/prenatal Formulation dimension (cap from config).

    Returns a payload shaped like the other v4 dimension scorers. Never
    raises on malformed input.
    """
    if not isinstance(product, dict):
        product = {}

    components: Dict[str, float] = {}
    penalties: Dict[str, float] = {}
    metadata: Dict[str, Any] = {"phase": PHASE_MARKER}

    panel_score, avg_bio_score, smoothed_bio_score = _score_panel_form_quality(product)
    components["panel_form_quality"] = panel_score
    metadata["avg_bio_score"] = avg_bio_score
    metadata["smoothed_bio_score"] = smoothed_bio_score

    disclosure_score, coverage = _score_panel_disclosure_structure(product)
    components["panel_disclosure_structure"] = disclosure_score
    metadata["dose_coverage"] = coverage

    shared_penalties = shared_formulation_penalty_detail(product)
    penalties.update(shared_penalties["penalties"])

    positive = sum(components.values())
    penalty_magnitude = sum(abs(value) for value in penalties.values())
    score, presence_floor_applied, pre_floor_score = apply_formulation_presence_floor(
        product,
        positive,
        penalty_magnitude,
        floor=FORMULATION_PRESENCE_FLOOR,
        cap=CAP_FORMULATION,
    )
    score = _round(score)
    metadata["presence_floor"] = {
        "target": FORMULATION_PRESENCE_FLOOR,
        "pre_floor_score": _round(pre_floor_score),
        "applied": presence_floor_applied,
    }
    metadata.update(shared_penalties["metadata"])

    return {
        "score": score,
        "components": components,
        "penalties": penalties,
        "metadata": metadata,
    }
