"""v4 generic-module Evidence dimension (P1.3.3).

Per `docs/plans/SCORING_V4_PROPOSAL.md` §6 generic rubric, Evidence 20
preserves the Section C multiplicative pipeline:

    study_type × evidence_level × effect_direction × enrollment × dose_guard
    → cap per ingredient → top-N diminishing returns → depth bonus → cap 20

This is a v4-owned implementation. It intentionally does not import the
v3 scorer, but it reads the same enriched `evidence_data.clinical_matches`
contract so shadow comparisons stay explainable.
"""

from __future__ import annotations

from collections import defaultdict
import re
from typing import Any, Dict, List, Optional, Tuple

from scoring_v4.modules.generic_helpers import (
    _as_float,
    _norm_text,
    _safe_dict,
    _safe_list,
    get_active_ingredients,
)


PHASE_MARKER = "P1.3.3_evidence_pipeline"

CAP_TOTAL = 20.0
CAP_PER_INGREDIENT = 7.0
SUPRA_CLINICAL_MULTIPLE = 3.0
SUB_CLINICAL_DOSE_GUARD_MULTIPLIER = 0.25

STUDY_TYPE_BASE_POINTS: Dict[str, float] = {
    "systematic_review_meta": 6.0,
    "rct_multiple": 5.0,
    "rct_single": 4.0,
    "clinical_strain": 4.0,
    "observational": 2.0,
    "animal_study": 2.0,
    "in_vitro": 1.0,
}

EVIDENCE_LEVEL_MULTIPLIERS: Dict[str, float] = {
    "product-human": 1.0,
    "product_human": 1.0,
    "product-rct": 1.0,
    "product_rct": 1.0,
    "product": 1.0,
    "branded-rct": 0.9,
    "branded_rct": 0.9,
    "ingredient-human": 0.8,
    "ingredient_human": 0.8,
    "strain-clinical": 0.65,
    "strain_clinical": 0.65,
    "preclinical": 0.3,
}

EFFECT_DIRECTION_MULTIPLIERS: Dict[str, float] = {
    "positive_strong": 1.0,
    "positive_weak": 0.85,
    "mixed": 0.6,
    "null": 0.25,
    "negative": 0.0,
}

ENROLLMENT_ELIGIBLE_STUDY_TYPES = frozenset(
    {"systematic_review_meta", "rct_multiple", "rct_single"}
)
ENROLLMENT_QUALITY_BANDS = (
    (50.0, 0.6),
    (200.0, 0.8),
    (500.0, 1.0),
    (1000.0, 1.1),
)
ENROLLMENT_DEFAULT_MULTIPLIER = 1.2

TOP_N_WEIGHTS = (1.0, 0.7, 0.5, 0.3)
DEPTH_BONUS_BANDS = ((20.0, 0.25), (40.0, 0.5))


def score_evidence(product: Dict[str, Any]) -> Dict[str, Any]:
    """Compute the generic-module Evidence dimension.

    Returns a dimension payload compatible with
    `GenericModuleResult.dimensions["evidence"]`.
    """
    if not isinstance(product, dict):
        product = {}

    matches = _safe_list(_safe_dict(product.get("evidence_data")).get("clinical_matches"))
    dose_map = _dose_map(product)
    ingredient_points: Dict[str, float] = defaultdict(float)
    matched_entry_ids: set[str] = set()
    flags: List[str] = []
    sub_clinical_canonicals: set[str] = set()

    for entry in matches:
        if not isinstance(entry, dict):
            continue
        entry_id = _entry_id(entry)
        if entry_id in matched_entry_ids:
            continue
        matched_entry_ids.add(entry_id)

        raw = _entry_raw_points(entry)
        if raw <= 0:
            continue

        converted_dose, lookup_key = _converted_product_dose(entry, dose_map)
        min_clinical_dose = _as_float(entry.get("min_clinical_dose"), None)
        if (
            min_clinical_dose is not None
            and converted_dose is not None
            and converted_dose < min_clinical_dose
        ):
            raw *= SUB_CLINICAL_DOSE_GUARD_MULTIPLIER
            _append_once(flags, "SUB_CLINICAL_DOSE_DETECTED")
            canonical = _canonical_from_entry(entry) or lookup_key
            if canonical:
                sub_clinical_canonicals.add(canonical)

        max_studied_dose = _as_float(
            entry.get("max_studied_clinical_dose")
            or entry.get("max_clinical_dose")
            or entry.get("max_studied_dose"),
            None,
        )
        if (
            converted_dose is not None
            and max_studied_dose is not None
            and max_studied_dose > 0
            and converted_dose > (SUPRA_CLINICAL_MULTIPLE * max_studied_dose)
        ):
            _append_once(flags, "SUPRA_CLINICAL_DOSE")

        marker_confidence = entry.get("marker_confidence_scale")
        if marker_confidence is not None:
            scale = _as_float(marker_confidence, None)
            if scale is not None:
                raw *= scale

        canonical = _canonical_from_entry(entry)
        if canonical:
            ingredient_points[canonical] += raw

    capped_scores = sorted(
        (min(CAP_PER_INGREDIENT, pts) for pts in ingredient_points.values()),
        reverse=True,
    )

    pipeline_total = 0.0
    for idx, points in enumerate(capped_scores):
        if idx >= len(TOP_N_WEIGHTS):
            break
        pipeline_total += points * TOP_N_WEIGHTS[idx]

    depth_bonus = _depth_bonus(matches)
    total = _clamp(0.0, CAP_TOTAL, pipeline_total + depth_bonus)

    components = {
        "clinical_evidence_pipeline": round(pipeline_total, 4),
        "depth_bonus": round(depth_bonus, 4),
    }

    return {
        "score": round(total, 4),
        "max": CAP_TOTAL,
        "components": components,
        "penalties": {},
        "phase": PHASE_MARKER,
        "metadata": {
            "phase": PHASE_MARKER,
            "ingredient_points": {k: round(v, 4) for k, v in sorted(ingredient_points.items())},
            "matched_entries": len(matched_entry_ids),
            "top_n_applied": min(len(capped_scores), len(TOP_N_WEIGHTS)),
            "sub_clinical_canonicals": sorted(sub_clinical_canonicals),
            "flags": flags,
        },
    }


def _entry_raw_points(entry: Dict[str, Any]) -> float:
    base = _as_float(entry.get("base_points"), None)
    if base is None:
        base = STUDY_TYPE_BASE_POINTS.get(_norm_text(entry.get("study_type")), 0.0)

    multiplier = _as_float(entry.get("multiplier"), None)
    if multiplier is None:
        multiplier = EVIDENCE_LEVEL_MULTIPLIERS.get(_norm_text(entry.get("evidence_level")), 0.0)

    raw = base * multiplier
    if raw <= 0:
        return 0.0

    effect = _norm_text(entry.get("effect_direction") or "positive_strong")
    raw *= EFFECT_DIRECTION_MULTIPLIERS.get(effect, 1.0)
    if raw <= 0:
        return 0.0

    study_type = _norm_text(entry.get("study_type"))
    enrollment = _as_float(entry.get("total_enrollment"), None)
    if enrollment is not None and study_type in ENROLLMENT_ELIGIBLE_STUDY_TYPES:
        raw *= _enrollment_multiplier(enrollment)

    return raw


def _entry_id(entry: Dict[str, Any]) -> str:
    explicit = entry.get("id") or entry.get("study_id")
    if explicit:
        return str(explicit)
    return ":".join(
        [
            _canonical_text(entry.get("study_name") or entry.get("ingredient")),
            _norm_text(entry.get("study_type")),
            _norm_text(entry.get("evidence_level")),
        ]
    )


def _canonical_from_entry(entry: Dict[str, Any]) -> str:
    return _canonical_text(entry.get("standard_name") or entry.get("study_name") or entry.get("ingredient"))


def _canonical_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _norm_text(value)).strip()


def _enrollment_multiplier(enrollment: float) -> float:
    for threshold, multiplier in ENROLLMENT_QUALITY_BANDS:
        if enrollment < threshold:
            return multiplier
    return ENROLLMENT_DEFAULT_MULTIPLIER


def _dose_map(product: Dict[str, Any]) -> Dict[str, Tuple[float, str]]:
    doses: Dict[str, Tuple[float, str]] = {}
    for ing in get_active_ingredients(product):
        quantity = _as_float(ing.get("quantity"), None)
        if quantity is None:
            continue
        unit = _norm_text(ing.get("unit_normalized") or ing.get("unit"))
        for name in (
            ing.get("standard_name"),
            ing.get("name"),
            ing.get("raw_source_text"),
            ing.get("canonical_id"),
        ):
            key = _canonical_text(name)
            if not key:
                continue
            if key not in doses or quantity > doses[key][0]:
                doses[key] = (quantity, unit)
    return doses


def _converted_product_dose(
    entry: Dict[str, Any],
    dose_map: Dict[str, Tuple[float, str]],
) -> tuple[Optional[float], str]:
    lookup_name = entry.get("standard_name") or entry.get("study_name") or entry.get("ingredient") or ""
    lookup_key = _canonical_text(lookup_name)
    product_dose = dose_map.get(lookup_key)
    if product_dose is None:
        return None, lookup_key
    dose_unit = _norm_text(entry.get("dose_unit") or "mg")
    return _convert_unit(product_dose[0], product_dose[1], dose_unit), lookup_key


def _convert_unit(quantity: float, from_unit: str, to_unit: str) -> Optional[float]:
    from_u = _norm_text(from_unit)
    to_u = _norm_text(to_unit)
    if from_u == to_u:
        return quantity

    mass_factor = {
        "mcg": 0.001,
        "ug": 0.001,
        "microgram": 0.001,
        "micrograms": 0.001,
        "mg": 1.0,
        "milligram": 1.0,
        "milligrams": 1.0,
        "g": 1000.0,
        "gram": 1000.0,
        "grams": 1000.0,
    }
    if from_u in mass_factor and to_u in mass_factor:
        mg = quantity * mass_factor[from_u]
        return mg / mass_factor[to_u]
    return None


def _published_study_count(entry: Dict[str, Any]) -> Optional[float]:
    explicit = _as_float(entry.get("published_studies_count"), None)
    if explicit is not None:
        return explicit
    legacy = entry.get("published_studies")
    if isinstance(legacy, (int, float)):
        return _as_float(legacy, None)
    return None


def _depth_bonus(matches: List[Any]) -> float:
    max_count = 0.0
    for entry in matches:
        if not isinstance(entry, dict):
            continue
        count = _published_study_count(entry)
        if count is not None and count > max_count:
            max_count = count

    bonus = 0.0
    for threshold, value in DEPTH_BONUS_BANDS:
        if max_count >= threshold:
            bonus = value
    return bonus


def _append_once(items: List[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _clamp(lo: float, hi: float, value: float) -> float:
    return max(lo, min(hi, value))
