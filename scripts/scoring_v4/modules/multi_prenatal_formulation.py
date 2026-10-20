"""v4 multi/prenatal Formulation dimension (P3.1).

Formulation for multis and prenatals is panel-aware:

  - Score average form quality across dose-bearing material rows (the shared
    role owner: panel micronutrients and the label's prominent actives). The
    IQM bio_score is the one form-quality owner.
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

from typing import Any, Dict, List

from scoring_v4.modules.generic_helpers import (
    bio_score_of,
    get_active_ingredients,
    is_scorable,
    restates_label_row,
    _as_float,
)
from scoring_v4.modules.generic_formulation import (
    UNRATED_FORM_NEUTRAL,
    apply_formulation_presence_floor,
    shared_formulation_penalty_detail,
)
from scoring_reference_resolver import parent_relative_form_quality
from scoring_input_contract import MATERIAL_ROLES, classify_ingredient_roles


from scoring_v4.quality_score_config import block as _cfg_block

_FVM = _cfg_block("formulation_variant_magnitudes", "multi_prenatal")["multi_prenatal"]


CAP_FORMULATION = _FVM["cap_formulation"]
FORMULATION_PRESENCE_FLOOR = _FVM["formulation_presence_floor"]
CAP_PANEL_FORM_QUALITY = _FVM["cap_panel_form_quality"]

BIO_SCORE_MAX = _FVM["bio_score_max"]

PHASE_MARKER = "P3.1_multi_prenatal_formulation"


def _clamp(low: float, high: float, value: float) -> float:
    return max(low, min(high, value))


def _round(value: float) -> float:
    return round(float(value), 2)


def _active_ingredients(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    return get_active_ingredients(product)


def _scorable_ingredients(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Dose-bearing material rows. An adjunct (an 85 mg fruit extract in a
    panel of grams) does not move the panel's form quality either way."""
    rows = _active_ingredients(product)
    roles = classify_ingredient_roles(product, module="multi_or_prenatal", rows=rows)
    return [
        ing for ing, role in zip(rows, roles)
        if role.get("role") in MATERIAL_ROLES and is_scorable(ing) and not restates_label_row(ing, rows)
    ]


def _score_panel_form_quality(
    product: Dict[str, Any],
) -> tuple[float, float | None, float | None, float]:
    """Panel-wide A1 analogue (V4.1 Step 4).

    A mapped row without a form rating keeps the shared unrated neutral; a rated
    row keeps its parent-relative rating, however low. There is no panel floor.
    Returns (contribution, raw average, parent-relative average, the share of
    the contribution that comes from unrated neutral rows).
    """
    rows = _scorable_ingredients(product)
    if not rows:
        return 0.0, None, None, 0.0

    weighted: List[tuple[float, float, float, bool]] = []
    for ing in rows:
        raw_score = bio_score_of(ing)
        unrated = raw_score is None
        if unrated:
            raw_score = UNRATED_FORM_NEUTRAL if ing.get("mapped") else 0.0
            score = raw_score
        else:
            score = parent_relative_form_quality(ing.get("canonical_id"), raw_score)
            if score is None:
                score = raw_score
        weight = _as_float(ing.get("dosage_importance"), 1.0) or 1.0
        if weight <= 0:
            weight = 1.0
        weighted.append((
            _clamp(0.0, BIO_SCORE_MAX, raw_score),
            _clamp(0.0, BIO_SCORE_MAX, score),
            weight,
            unrated and bool(ing.get("mapped")),
        ))

    denom = sum(weight for _, _, weight, _ in weighted)
    if denom <= 0:
        return 0.0, None, None, 0.0
    avg = sum(raw_score * weight for raw_score, _, weight, _ in weighted) / denom
    relative_avg = sum(score * weight for _, score, weight, _ in weighted) / denom
    neutral_avg = sum(score * weight for _, score, weight, neutral in weighted if neutral) / denom
    contribution = _clamp(0.0, CAP_PANEL_FORM_QUALITY, (relative_avg / BIO_SCORE_MAX) * CAP_PANEL_FORM_QUALITY)
    neutral_points = min(contribution, (neutral_avg / BIO_SCORE_MAX) * CAP_PANEL_FORM_QUALITY)
    return _round(contribution), _round(avg), _round(relative_avg), _round(neutral_points)


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

    panel_score, avg_bio_score, relative_bio_score, neutral_points = _score_panel_form_quality(product)
    components["panel_form_quality"] = panel_score
    metadata["avg_bio_score"] = avg_bio_score
    metadata["relative_bio_score"] = relative_bio_score
    metadata["panel_form_neutral_points"] = neutral_points

    # V4.1 Step 4: dose disclosure is a Transparency fact, not Formulation credit.

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
