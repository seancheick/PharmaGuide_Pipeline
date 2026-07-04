"""v4 multi/prenatal Formulation dimension (P3.1).

Formulation for multis and prenatals is panel-aware:

  - Score average form quality across dose-bearing micronutrients.
  - Smooth multivitamin bio_score toward the v3 neutral floor so products
    with many standard-but-acceptable nutrient forms are not punished too
    hard.
  - Cap premium-form diversity so stacked panels cannot inflate endlessly.
  - Credit a small set of key form signals (methylfolate, methyl-B12, D3,
    K2, chelated minerals) without treating dose adequacy as formulation.
  - Penalize gummy formulation limitations modestly; missing/low doses and
    prenatal-critical coverage land in P3.2 Dose.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

from scoring_v4.modules.generic_helpers import (
    bio_score_of,
    canonical_key,
    get_active_ingredients,
    has_usable_individual_dose,
    is_scorable,
    _as_float,
    _norm_text,
    _safe_dict,
    _safe_list,
)
from scoring_v4.modules.generic_formulation import shared_formulation_penalty_detail


from scoring_v4.quality_score_config import block as _cfg_block

_FVM = _cfg_block("formulation_variant_magnitudes", "multi_prenatal")["multi_prenatal"]


CAP_FORMULATION = _FVM["cap_formulation"]
FORMULATION_PRESENCE_FLOOR = _FVM["formulation_presence_floor"]
CAP_PANEL_FORM_QUALITY = _FVM["cap_panel_form_quality"]
CAP_PREMIUM_FORM_DIVERSITY = _FVM["cap_premium_form_diversity"]
CAP_KEY_FORM_SUPPORT = _FVM["cap_key_form_support"]
CAP_PANEL_DISCLOSURE_STRUCTURE = _FVM["cap_panel_disclosure_structure"]
CAP_DOSAGE_FORM_SUITABILITY = _FVM["cap_dosage_form_suitability"]

PANEL_FORM_SMOOTHING_FACTOR = _FVM["panel_form_smoothing_factor"]
PANEL_FORM_NEUTRAL_FLOOR = _FVM["panel_form_neutral_floor"]
BIO_SCORE_MAX = _FVM["bio_score_max"]
PREMIUM_FORM_THRESHOLD = _FVM["premium_form_threshold"]
PREMIUM_POINTS_PER_ADDITIONAL = _FVM["premium_points_per_additional"]

GUMMY_FORMULATION_PENALTY = _FVM["gummy_formulation_penalty"]

PHASE_MARKER = "P3.1_multi_prenatal_formulation"

FOLATE_CANONICALS = {"vitamin_b9_folate", "folate"}
B12_CANONICALS = {"vitamin_b12_cobalamin", "vitamin_b12", "b12"}
VITAMIN_D_CANONICALS = {"vitamin_d"}
VITAMIN_K_CANONICALS = {"vitamin_k", "vitamin_k2", "vitamin_k1"}
MINERAL_FORM_CANONICALS = {"iron", "zinc", "magnesium", "calcium", "selenium", "manganese", "copper"}

FOLATE_PREFERRED_RE = re.compile(r"\b(5[-\s]?mthf|l[-\s]?5[-\s]?mthf|methylfolate|folinic)\b")
FOLIC_ACID_RE = re.compile(r"\bfolic\s+acid\b")
B12_PREFERRED_RE = re.compile(r"\b(methylcobalamin|adenosylcobalamin|hydroxocobalamin|hydroxycobalamin)\b")
B12_STANDARD_RE = re.compile(r"\bcyanocobalamin\b")
VITAMIN_D3_RE = re.compile(r"\b(cholecalciferol|vitamin\s*d3|d3)\b")
VITAMIN_D2_RE = re.compile(r"\b(ergocalciferol|vitamin\s*d2|d2)\b")
VITAMIN_K2_RE = re.compile(r"\b(mk[-\s]?7|menaquinone[-\s]?7|vitamin\s*k2|menaquinone)\b")
VITAMIN_K1_RE = re.compile(r"\b(phytonadione|phylloquinone|vitamin\s*k1)\b")
CHELATED_MINERAL_RE = re.compile(
    r"\b(bisglycinate|glycinate|chelate|chelated|citrate|malate|picolinate|"
    r"glycinate\s+chelate|amino\s+acid\s+chelate)\b"
)
STANDARD_MINERAL_RE = re.compile(r"\b(sulfate|oxide|carbonate|fumarate|gluconate|chloride)\b")
GUMMY_RE = re.compile(r"\b(gummy|gummies|chewable)\b")


def _clamp(low: float, high: float, value: float) -> float:
    return max(low, min(high, value))


def _round(value: float) -> float:
    return round(float(value), 2)


def _has_mapped_formulation_active(product: Dict[str, Any]) -> bool:
    iqd = _safe_dict((product or {}).get("ingredient_quality_data"))
    for ing in _safe_list(iqd.get("ingredients_scorable")):
        if not is_scorable(ing):
            continue
        if bool(ing.get("mapped", False)) or canonical_key(ing):
            return True
    return False


def _ingredient_text(ingredient: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in (
        "name",
        "standard_name",
        "standardName",
        "raw_source_text",
        "matched_form",
        "form",
        "matched_candidate",
    ):
        value = ingredient.get(key)
        if value:
            parts.append(str(value))

    for form in ingredient.get("matched_forms") or []:
        if isinstance(form, dict):
            for key in ("form_key", "raw_form_text", "matched_candidate"):
                value = form.get(key)
                if value:
                    parts.append(str(value))

    for form in ingredient.get("extracted_forms") or []:
        if isinstance(form, dict):
            for key in ("display_form", "raw_form_text"):
                value = form.get(key)
                if value:
                    parts.append(str(value))

    return _norm_text(" ".join(parts))


def _form_factor_text(product: Dict[str, Any]) -> str:
    """Build a text blob for form-factor pattern matching (gummy detection,
    dosage-form suitability scoring).

    SP-3 (2026-05-21): also include `form_factor_canonical` so the canonical
    id (`gummy`, `softgel`, etc.) participates in the regex match. The
    legacy free-text fields and product name keep contributing because the
    GUMMY_RE pattern also catches "chewable gummy multivitamin" name text
    that the canonical field alone would miss.
    """
    parts = []
    for key in (
        "form_factor_canonical",
        "form_factor",
        "product_form",
        "dosage_form",
        "form",
        "product_name",
        "fullName",
    ):
        value = product.get(key)
        if value:
            parts.append(str(value))
    return _norm_text(" ".join(parts))


def _active_ingredients(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    return get_active_ingredients(product)


def _scorable_ingredients(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [ing for ing in _active_ingredients(product) if is_scorable(ing)]


def _score_panel_form_quality(product: Dict[str, Any]) -> tuple[float, float | None, float | None]:
    """Panel-wide A1 analogue. Mirrors v3's multivitamin smoothing:

        smoothed_avg = 0.7 * avg_bio_score + 0.3 * 9
        score = smoothed_avg / 15 * 12
    """
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
    smoothed = PANEL_FORM_SMOOTHING_FACTOR * avg + (1.0 - PANEL_FORM_SMOOTHING_FACTOR) * PANEL_FORM_NEUTRAL_FLOOR
    contribution = _clamp(0.0, CAP_PANEL_FORM_QUALITY, (smoothed / BIO_SCORE_MAX) * CAP_PANEL_FORM_QUALITY)
    return _round(contribution), _round(avg), _round(smoothed)


def _score_premium_form_diversity(product: Dict[str, Any]) -> tuple[float, int]:
    premium_keys = set()
    for ing in _active_ingredients(product):
        if not is_scorable(ing):
            continue
        score = bio_score_of(ing)
        if score is None or score < PREMIUM_FORM_THRESHOLD:
            continue
        key = canonical_key(ing)
        if key:
            premium_keys.add(key)
    count = len(premium_keys)
    effective = max(0, count - 1)
    return _round(_clamp(0.0, CAP_PREMIUM_FORM_DIVERSITY, effective * PREMIUM_POINTS_PER_ADDITIONAL)), count


def _score_key_form_for_ingredient(ingredient: Dict[str, Any]) -> float:
    canonical = _norm_text(ingredient.get("canonical_id"))
    text = _ingredient_text(ingredient)

    if canonical in FOLATE_CANONICALS:
        if FOLATE_PREFERRED_RE.search(text):
            return 1.25
        if FOLIC_ACID_RE.search(text):
            return 0.75
        return 0.5

    if canonical in B12_CANONICALS:
        if B12_PREFERRED_RE.search(text):
            return 1.0
        if B12_STANDARD_RE.search(text):
            return 0.5
        return 0.4

    if canonical in VITAMIN_D_CANONICALS:
        if VITAMIN_D3_RE.search(text):
            return 1.0
        if VITAMIN_D2_RE.search(text):
            return 0.5
        return 0.4

    if canonical in VITAMIN_K_CANONICALS:
        if VITAMIN_K2_RE.search(text):
            return 1.0
        if VITAMIN_K1_RE.search(text):
            return 0.5
        return 0.4

    if canonical in MINERAL_FORM_CANONICALS:
        if CHELATED_MINERAL_RE.search(text):
            return 1.0
        if STANDARD_MINERAL_RE.search(text):
            return 0.5
        return 0.3

    return 0.0


def _score_key_form_support(product: Dict[str, Any]) -> tuple[float, Dict[str, float]]:
    credits: Dict[str, float] = {}
    for ing in _active_ingredients(product):
        if not isinstance(ing, dict) or not has_usable_individual_dose(ing):
            continue
        canonical = canonical_key(ing)
        if not canonical or canonical in credits:
            continue
        credit = _score_key_form_for_ingredient(ing)
        if credit > 0:
            credits[canonical] = credit
    total = _clamp(0.0, CAP_KEY_FORM_SUPPORT, sum(credits.values()))
    return _round(total), {key: _round(value) for key, value in sorted(credits.items())}


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


def _is_gummy(product: Dict[str, Any]) -> bool:
    return bool(GUMMY_RE.search(_form_factor_text(product)))


def _score_dosage_form_suitability(product: Dict[str, Any]) -> float:
    text = _form_factor_text(product)
    if not text:
        return 1.0
    if GUMMY_RE.search(text):
        return 0.0
    return 2.0


def score_formulation(product: Any) -> Dict[str, Any]:
    """Score the multi/prenatal Formulation 25 dimension.

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

    premium_score, premium_count = _score_premium_form_diversity(product)
    components["premium_form_diversity"] = premium_score
    metadata["premium_form_count"] = premium_count

    key_form_score, key_form_details = _score_key_form_support(product)
    components["key_form_support"] = key_form_score
    metadata["key_form_details"] = key_form_details

    disclosure_score, coverage = _score_panel_disclosure_structure(product)
    components["panel_disclosure_structure"] = disclosure_score
    metadata["dose_coverage"] = coverage

    components["dosage_form_suitability"] = (
        _score_dosage_form_suitability(product)
        if _active_ingredients(product)
        else 0.0
    )

    if _is_gummy(product):
        penalties["gummy_formulation_limit"] = -GUMMY_FORMULATION_PENALTY
    shared_penalties = shared_formulation_penalty_detail(product)
    penalties.update(shared_penalties["penalties"])

    positive = sum(components.values())
    penalty_magnitude = sum(abs(value) for value in penalties.values())
    pre_floor_score = positive - penalty_magnitude
    presence_floor_applied = (
        _has_mapped_formulation_active(product)
        and positive > 0
        and penalty_magnitude > 0
        and pre_floor_score <= 0
    )
    score = _clamp(0.0, CAP_FORMULATION, pre_floor_score)
    if presence_floor_applied:
        score = max(score, FORMULATION_PRESENCE_FLOOR)
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
