"""v4 multi/prenatal Transparency dimension (P3.5).

Transparency for broad panels should answer a simple question: can the user
and scorer see what each panel nutrient is and how much is present?

Positive components:
  - panel ingredient identities disclosed   4
  - panel individual doses disclosed        7
  - B3 claim_compliance bonus               up to 4

Penalties reuse the v4 generic Transparency implementation, including the
class-aware B5 multiplier where multi/prenatal proprietary opacity is more
serious than probiotic opacity.

Per §13 architecture lock, this module does not import from
`score_supplements.py` (v3).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from scoring_v4.modules.generic_helpers import (
    _as_float,
    _norm_text,
    _safe_dict,
    _safe_list,
    has_usable_individual_dose,
)
from scoring_v4.modules.generic_transparency import (
    B5_SAFETY_RELEVANT_BLEND_PATTERN,
    _derive_claim_validations,
    _score_b2_false_allergen_claim_penalty,
    _score_b3_claim_compliance,
    _score_b5_proprietary_blend_penalty,
    _score_b6_disease_claim_penalty,
)
from scoring_v4.modules.multi_prenatal_formulation import _active_ingredients


PHASE_MARKER = "P3.5_multi_prenatal_transparency"

from scoring_v4.quality_score_config import block as _cfg_block

_TM = _cfg_block("transparency_magnitudes", "multi_prenatal")["multi_prenatal"]


DIMENSION_CAP = _TM["dimension_cap"]
CAP_PANEL_IDENTITY_DISCLOSURE = _TM["cap_panel_identity_disclosure"]
CAP_PANEL_INDIVIDUAL_DOSE_DISCLOSURE = _TM["cap_panel_individual_dose_disclosure"]
ADJUNCT_BLEND_PANEL_DISCLOSURE_THRESHOLD = _TM["adjunct_blend_panel_disclosure_threshold"]
ADJUNCT_BLEND_B5_CAP = _TM["adjunct_blend_b5_cap"]

PANEL_MINERAL_CANONICALS = frozenset(
    {
        "boron",
        "calcium",
        "chromium",
        "copper",
        "iodine",
        "iron",
        "magnesium",
        "manganese",
        "molybdenum",
        "potassium",
        "selenium",
        "zinc",
    }
)
PANEL_NUTRIENT_PATTERN = re.compile(
    r"\b("
    r"vitamin|folate|folic\s+acid|methylfolate|thiamin|thiamine|riboflavin|"
    r"niacin|biotin|pantothenic|cobalamin|b12|b6|"
    r"iron|iodine|zinc|selenium|manganese|chromium|copper|calcium|"
    r"magnesium|molybdenum|potassium|boron|choline|dha|epa"
    r")\b",
    re.IGNORECASE,
)
ADJUNCT_SOURCE_PATTERN = re.compile(
    r"\b("
    r"apple|acerola|alfalfa|amla|barley|beet|berry|berries|bilberry|"
    r"blackberry|blueberry|broccoli|carrot|cabbage|cauliflower|celery|"
    r"cherry|cranberry|currant|fruit|garlic|ginger|grape|greens?|kale|"
    r"lemon|mango|orange|parsley|peppermint|pineapple|pomegranate|"
    r"raspberry|rice|spinach|spirulina|sprout|strawberry|tomato|vegetable|"
    r"watercress|whole\s+food|food\s+blend"
    r")\b",
    re.IGNORECASE,
)
BLEND_CONTAINER_PATTERN = re.compile(r"\b(blend|complex|matrix|formula|proprietary)\b", re.IGNORECASE)
HIDDEN_PANEL_BLEND_PATTERN = re.compile(r"\b(prenatal|multi|multivitamin|nutrient|vitamin|mineral)\b", re.IGNORECASE)
ADJUNCT_BLEND_NAME_PATTERN = re.compile(
    r"\b(food|fruit|vegetable|greens?|stomach|soothing|digestive|enzyme|"
    r"probiotic|botanical|herbal|herb|flower|root|seed|fiber|whole\s+food)\b",
    re.IGNORECASE,
)
LOW_VALUE_ADJUNCT_BLEND_NAME_PATTERN = re.compile(
    r"\b(food|fruit|vegetable|greens?|stomach|soothing|fiber|whole\s+food)\b",
    re.IGNORECASE,
)
VALUE_RELEVANT_BLEND_NAME_PATTERN = re.compile(
    r"\b("
    r"adaptogen|amino|antioxidant|brain|cognitive|energy|enzyme|immune|"
    r"metabolism|metabolic|omega|protein|stress|thermo|thermogenic|"
    r"weight|ripped|pump|pre[-\s]?workout|post[-\s]?workout|muscle"
    r")\b",
    re.IGNORECASE,
)


def score_transparency(product: Any) -> Dict[str, Any]:
    """Compute multi/prenatal Transparency.

    Returns the standard v4 dimension payload and never raises on malformed
    input.
    """
    if not isinstance(product, dict):
        product = {}

    flags: list[str] = []
    b2, b2_meta = _score_b2_false_allergen_claim_penalty(product)
    allergen_valid, gluten_valid, vegan_valid, claim_flags = _derive_claim_validations(product, b2)
    flags.extend(claim_flags)
    b3 = _score_b3_claim_compliance(
        allergen_free=allergen_valid,
        gluten_free=gluten_valid,
        vegan_or_vegetarian=vegan_valid,
    )
    b5, b5_evidence = _score_b5_proprietary_blend_penalty(product, flags)
    b6 = _score_b6_disease_claim_penalty(product, flags)

    identity_score, identity_meta = _score_panel_identity_disclosure(product)
    dose_score, dose_meta = _score_panel_individual_dose_disclosure(product)
    b5, b5_adjunct_meta = _cap_b5_for_disclosed_panel_adjunct_blends(
        product,
        b5_penalty=b5,
        b5_evidence=b5_evidence,
        panel_dose_coverage=float(dose_meta.get("panel_dose_coverage", 0.0)),
    )

    components = {
        "panel_identity_disclosure": round(identity_score, 4),
        "panel_individual_dose_disclosure": round(dose_score, 4),
        "B3_claim_compliance": round(b3, 4),
    }
    penalties = {
        "B2_false_allergen_free_claim": _neg_or_zero(b2),
        "B5_proprietary_blend_opacity": _neg_or_zero(b5),
        "B6_marketing_claims": _neg_or_zero(b6),
    }
    raw_total = (
        sum(float(value) for value in components.values())
        - sum(abs(float(value)) for value in penalties.values())
    )
    score = _clamp(0.0, DIMENSION_CAP, raw_total)

    metadata = {
        "phase": PHASE_MARKER,
        "raw_score": round(raw_total, 4),
        "cap_applied": raw_total > DIMENSION_CAP,
        "floor_applied": raw_total < 0.0,
        "claim_validations": {
            "allergen_free": bool(allergen_valid),
            "gluten_free": bool(gluten_valid),
            "vegan_or_vegetarian": bool(vegan_valid),
        },
        "flags": sorted(set(flags)),
        "B2_raw_before_cap": round(b2_meta["raw_before_cap"], 4),
        "B2_seen_allergens": b2_meta["seen_allergens"],
        "B5_blend_evidence": b5_evidence,
        "B5_blend_count": len(b5_evidence),
        **b5_adjunct_meta,
        **identity_meta,
        **dose_meta,
    }

    return {
        "score": round(score, 4),
        "max": DIMENSION_CAP,
        "components": components,
        "penalties": penalties,
        "phase": PHASE_MARKER,
        "metadata": metadata,
    }


def _score_panel_identity_disclosure(product: Dict[str, Any]) -> tuple[float, Dict[str, Any]]:
    rows, row_meta = _panel_transparency_rows(product)
    if not rows:
        return 0.0, {
            "panel_active_count": 0,
            "panel_named_count": 0,
            "panel_identity_coverage": 0.0,
            **row_meta,
        }

    named_count = sum(1 for row in rows if _has_panel_identity(row))
    coverage = min(1.0, named_count / len(rows))
    return round(CAP_PANEL_IDENTITY_DISCLOSURE * coverage, 4), {
        "panel_active_count": len(rows),
        "panel_named_count": named_count,
        "panel_identity_coverage": round(coverage, 4),
        **row_meta,
    }


def _score_panel_individual_dose_disclosure(product: Dict[str, Any]) -> tuple[float, Dict[str, Any]]:
    rows, row_meta = _panel_transparency_rows(product)
    if not rows:
        return 0.0, {
            "panel_dose_count": 0,
            "panel_dose_coverage": 0.0,
            **row_meta,
        }

    dose_count = sum(1 for row in rows if has_usable_individual_dose(row))
    coverage = min(1.0, dose_count / len(rows))
    return round(CAP_PANEL_INDIVIDUAL_DOSE_DISCLOSURE * coverage, 4), {
        "panel_dose_count": dose_count,
        "panel_dose_coverage": round(coverage, 4),
        **row_meta,
    }


def _panel_transparency_rows(product: Dict[str, Any]) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    candidate_rows = [row for row in _active_ingredients(product) if isinstance(row, dict)]
    included: List[Dict[str, Any]] = []
    excluded: List[Dict[str, Any]] = []
    for row in candidate_rows:
        if _is_panel_transparency_row(row):
            included.append(row)
        else:
            excluded.append(row)

    return included, {
        "panel_candidate_count": len(candidate_rows),
        "panel_excluded_adjunct_count": len(excluded),
    }


def _is_panel_transparency_row(row: Dict[str, Any]) -> bool:
    if not isinstance(row, dict):
        return False
    if row.get("is_parent_total") or row.get("is_proprietary_blend"):
        return False
    if _looks_like_adjunct_source_row(row):
        return False
    if _has_daily_value(row):
        return True
    if _has_direct_panel_nutrient_identity(row):
        return True
    return _category_is_panel_nutrient(row)


def _has_panel_identity(row: Dict[str, Any]) -> bool:
    if not isinstance(row, dict):
        return False
    for field in ("canonical_id", "standard_name", "standardName", "name"):
        if _norm_text(row.get(field)):
            return True
    return False


def _has_daily_value(row: Dict[str, Any]) -> bool:
    for key in (
        "daily_value",
        "dailyValue",
        "daily_value_percent",
        "dailyValuePercent",
        "percent_daily_value",
        "percentDailyValue",
        "dv_percent",
    ):
        value = row.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return True
    return False


def _has_direct_panel_nutrient_identity(row: Dict[str, Any]) -> bool:
    canonical = _canon_key(row.get("canonical_id") or row.get("parent_key") or row.get("mapped_parent"))
    if canonical.startswith("vitamin_") or canonical in PANEL_MINERAL_CANONICALS:
        return True
    text = _row_display_text(row)
    return bool(PANEL_NUTRIENT_PATTERN.search(text))


def _category_is_panel_nutrient(row: Dict[str, Any]) -> bool:
    text = " ".join(
        _norm_text(row.get(key))
        for key in ("category", "ingredient_category", "nutrient_category", "nutrient_type", "class")
    )
    return any(term in text for term in ("vitamin", "mineral", "prenatal nutrient", "essential nutrient"))


def _looks_like_adjunct_source_row(row: Dict[str, Any]) -> bool:
    text = _row_display_text(row)
    if not text:
        return False
    if PANEL_NUTRIENT_PATTERN.search(text):
        return False
    dose_status = _norm_text(row.get("dose_status") or row.get("disclosure_status"))
    lacks_dose = not has_usable_individual_dose(row)
    if (dose_status in {"not_disclosed_blend", "hidden_blend", "not_disclosed"} or lacks_dose) and (
        ADJUNCT_SOURCE_PATTERN.search(text) or BLEND_CONTAINER_PATTERN.search(text)
    ):
        return True
    return False


def _cap_b5_for_disclosed_panel_adjunct_blends(
    product: Dict[str, Any],
    *,
    b5_penalty: float,
    b5_evidence: List[Dict[str, Any]],
    panel_dose_coverage: float,
) -> tuple[float, Dict[str, Any]]:
    meta = {
        "B5_adjunct_blend_cap_applied": False,
        "B5_raw_before_adjunct_cap": round(b5_penalty, 4),
        "B5_adjunct_blend_cap": None,
        "B5_adjunct_blend_cap_reason": "",
    }
    if b5_penalty <= ADJUNCT_BLEND_B5_CAP:
        meta["B5_adjunct_blend_cap_reason"] = "below_cap"
        return b5_penalty, meta
    if not b5_evidence:
        meta["B5_adjunct_blend_cap_reason"] = "no_b5_evidence"
        return b5_penalty, meta
    if panel_dose_coverage < ADJUNCT_BLEND_PANEL_DISCLOSURE_THRESHOLD:
        meta["B5_adjunct_blend_cap_reason"] = "panel_not_sufficiently_disclosed"
        return b5_penalty, meta
    if _has_hidden_panel_payload(product):
        meta["B5_adjunct_blend_cap_reason"] = "hidden_panel_payload"
        return b5_penalty, meta
    if _has_safety_relevant_blend_payload(product):
        meta["B5_adjunct_blend_cap_reason"] = "safety_relevant_blend_payload"
        return b5_penalty, meta
    if not _b5_blends_are_low_value_adjuncts(b5_evidence):
        meta["B5_adjunct_blend_cap_reason"] = "value_relevant_blend_payload"
        return b5_penalty, meta

    meta.update(
        {
            "B5_adjunct_blend_cap_applied": True,
            "B5_adjunct_blend_cap": ADJUNCT_BLEND_B5_CAP,
            "B5_adjunct_blend_cap_reason": "disclosed_panel_adjunct_blends",
        }
    )
    return min(b5_penalty, ADJUNCT_BLEND_B5_CAP), meta


def _b5_blends_are_low_value_adjuncts(b5_evidence: List[Dict[str, Any]]) -> bool:
    scoreable_names: List[str] = []
    for evidence in b5_evidence:
        magnitude = _as_float(evidence.get("computed_blend_penalty_magnitude"), 0.0) or 0.0
        if magnitude <= 0:
            continue
        name = str(evidence.get("blend_name") or "")
        if name:
            scoreable_names.append(name)
    if not scoreable_names:
        return False

    for name in scoreable_names:
        if VALUE_RELEVANT_BLEND_NAME_PATTERN.search(name):
            return False
        if not LOW_VALUE_ADJUNCT_BLEND_NAME_PATTERN.search(name):
            return False
    return True


def _has_hidden_panel_payload(product: Dict[str, Any]) -> bool:
    for blend in _blend_rows(product):
        name = str(blend.get("name") or "")
        if _blend_name_suggests_hidden_panel_payload(name):
            return True
        for child_name in _hidden_blend_child_names(blend):
            if _is_direct_hidden_panel_name(child_name):
                return True
    return False


def _has_safety_relevant_blend_payload(product: Dict[str, Any]) -> bool:
    for blend in _blend_rows(product):
        names = [str(blend.get("name") or "")]
        names.extend(_hidden_blend_child_names(blend))
        if B5_SAFETY_RELEVANT_BLEND_PATTERN.search(" ".join(names)):
            return True
    return False


def _blend_rows(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    blends = [blend for blend in _safe_list(product.get("proprietary_blends")) if isinstance(blend, dict)]
    if blends:
        return blends
    return [
        blend
        for blend in _safe_list(_safe_dict(product.get("proprietary_data")).get("blends"))
        if isinstance(blend, dict)
    ]


def _hidden_blend_child_names(blend: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    for child in _safe_list(blend.get("child_ingredients")):
        if not isinstance(child, dict):
            continue
        amount = _as_float(child.get("amount"), None)
        if amount is not None and amount > 0:
            continue
        name = child.get("name") or child.get("ingredient")
        if name:
            names.append(str(name))

    evidence = _safe_dict(blend.get("evidence"))
    for child in _safe_list(evidence.get("ingredients_without_amounts")):
        if isinstance(child, dict):
            name = child.get("name") or child.get("ingredient")
        else:
            name = child
        if name:
            names.append(str(name))
    return names


def _blend_name_suggests_hidden_panel_payload(name: str) -> bool:
    text = _norm_text(name)
    if not text:
        return False
    if ADJUNCT_BLEND_NAME_PATTERN.search(text):
        return False
    return bool(HIDDEN_PANEL_BLEND_PATTERN.search(text))


def _is_direct_hidden_panel_name(name: str) -> bool:
    text = _norm_text(name)
    if not text:
        return False
    if ADJUNCT_SOURCE_PATTERN.search(text) and not PANEL_NUTRIENT_PATTERN.search(text):
        return False
    return bool(PANEL_NUTRIENT_PATTERN.search(text))


def _row_display_text(row: Dict[str, Any]) -> str:
    return " ".join(
        _norm_text(row.get(key))
        for key in (
            "name",
            "standard_name",
            "standardName",
            "display_name",
            "displayName",
            "raw_source_text",
            "source_text",
            "ingredient_name",
            "original_name",
        )
    )


def _canon_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _norm_text(value)).strip("_")


def _neg_or_zero(value: float) -> float:
    if value <= 0:
        return 0.0
    return round(-float(value), 4)


def _clamp(low: float, high: float, value: float) -> float:
    return max(low, min(high, value))
