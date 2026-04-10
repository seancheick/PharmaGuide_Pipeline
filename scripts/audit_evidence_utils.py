from __future__ import annotations

import re
from typing import Any


_OMEGA3_CANONICAL_IDS = {
    "epa",
    "dha",
    "epa_dha",
    "fish_oil",
    "krill_oil",
    "algal_oil",
    "cod_liver_oil",
    "omega_3",
    "omega3",
}
_OMEGA3_KEYWORDS = (
    "omega-3",
    "omega 3",
    "fish oil",
    "krill oil",
    "algal oil",
    "cod liver oil",
    "eicosapentaenoic acid",
    "docosahexaenoic acid",
)
_NON_GMO_PROJECT_PATTERNS = (
    "non-gmo-project",
    "non gmo project",
    "non-gmo project",
    "non gmo project verified",
    "non-gmo project verified",
)
_NON_GMO_GENERIC_PATTERNS = (
    "non-gmo-general",
    "non gmo",
    "non-gmo",
)


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result


def _norm_text(value: Any) -> str:
    text = _safe_str(value).lower()
    return re.sub(r"\s+", " ", text)


def _non_gmo_signal_type(text: str) -> str | None:
    lowered = _norm_text(text)
    if any(pattern in lowered for pattern in _NON_GMO_PROJECT_PATTERNS):
        return "project_verified"
    if any(pattern in lowered for pattern in _NON_GMO_GENERIC_PATTERNS):
        return "generic_claim"
    return None


def derive_non_gmo_audit(product: dict[str, Any]) -> dict[str, Any]:
    label_parsed = _safe_dict(_safe_dict(product.get("labelText")).get("parsed"))
    certification_data = _safe_dict(product.get("certification_data"))
    third_party_programs = _safe_dict(certification_data.get("third_party_programs"))

    candidate_signals: list[dict[str, str]] = []

    for value in _safe_list(label_parsed.get("certifications")):
        if _safe_str(value):
            candidate_signals.append({"source": "label_certifications", "text": _safe_str(value)})

    for value in _safe_list(label_parsed.get("cleanLabelClaims")):
        if _safe_str(value):
            candidate_signals.append({"source": "clean_label_claims", "text": _safe_str(value)})

    for value in _safe_list(product.get("named_cert_programs")):
        if _safe_str(value):
            candidate_signals.append({"source": "named_cert_programs", "text": _safe_str(value)})

    for program in _safe_list(third_party_programs.get("programs")):
        if isinstance(program, dict):
            text = _safe_str(program.get("name") or program.get("program"))
        else:
            text = _safe_str(program)
        if text:
            candidate_signals.append({"source": "third_party_programs", "text": text})

    verified_signals: list[dict[str, str]] = []
    generic_signals: list[dict[str, str]] = []
    for signal in candidate_signals:
        signal_type = _non_gmo_signal_type(signal["text"])
        if signal_type == "project_verified":
            verified_signals.append(signal)
        elif signal_type == "generic_claim":
            generic_signals.append(signal)

    project_verified = bool(
        product.get("claim_non_gmo_project_verified")
        or verified_signals
    )
    claim_present = project_verified or bool(generic_signals)

    if project_verified:
        reason = "verified_program_detected"
    elif claim_present:
        reason = "generic_claim_only"
    else:
        reason = "no_non_gmo_signal"

    return {
        "claim_present": claim_present,
        "project_verified": project_verified,
        "score_eligible": project_verified,
        "reason": reason,
        "verified_signals": verified_signals,
        "generic_signals": generic_signals,
        "all_signals": candidate_signals,
    }


def _iter_omega3_ingredients(product: dict[str, Any]) -> list[dict[str, Any]]:
    iqd = _safe_dict(product.get("ingredient_quality_data"))
    merged: list[dict[str, Any]] = []
    for key in ("ingredients", "ingredients_scorable"):
        for ingredient in _safe_list(iqd.get(key)):
            if isinstance(ingredient, dict):
                merged.append(ingredient)
    return merged


def _is_omega3_ingredient(ingredient: dict[str, Any]) -> bool:
    for key in ("canonical_id", "parent_key", "standard_name", "name", "raw_source_text"):
        value = _norm_text(ingredient.get(key))
        if not value:
            continue
        if value in _OMEGA3_CANONICAL_IDS:
            return True
        if any(keyword in value for keyword in _OMEGA3_KEYWORDS):
            return True
    return False


def derive_omega3_audit(
    product: dict[str, Any],
    scored: dict[str, Any] | None = None,
) -> dict[str, Any]:
    matched_ingredients: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()

    for ingredient in _iter_omega3_ingredients(product):
        if not _is_omega3_ingredient(ingredient):
            continue
        key = (_safe_str(ingredient.get("canonical_id")), _safe_str(ingredient.get("standard_name") or ingredient.get("name")))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        matched_ingredients.append(
            {
                "name": _safe_str(ingredient.get("standard_name") or ingredient.get("name") or ingredient.get("raw_source_text")),
                "canonical_id": _safe_str(ingredient.get("canonical_id")),
                "category": _safe_str(ingredient.get("category")),
                "raw_source_text": _safe_str(ingredient.get("raw_source_text")),
            }
        )

    breakdown = _safe_dict(_safe_dict(_safe_dict(scored).get("breakdown")).get("A")).get("omega3_breakdown")
    if not isinstance(breakdown, dict):
        breakdown = {}

    contains_omega3 = bool(matched_ingredients or breakdown.get("applicable"))
    bonus_score = _as_float(
        breakdown.get("omega3_dose_bonus", breakdown.get("score")),
        0.0,
    ) or 0.0

    if bonus_score > 0:
        reason = "omega3_bonus_awarded"
    elif breakdown.get("applicable"):
        reason = "omega3_present_below_bonus_threshold"
    elif contains_omega3:
        reason = "omega3_ingredients_detected"
    else:
        reason = "no_omega3_signal"

    return {
        "contains_omega3": contains_omega3,
        "reason": reason,
        "matched_ingredients": matched_ingredients,
        "bonus_score": round(bonus_score, 2),
        "applicable_for_dose_bonus": bool(breakdown.get("applicable")),
        "dose_band": _safe_str(breakdown.get("dose_band")),
        "per_day_mid_mg": _as_float(breakdown.get("per_day_mid_mg")),
        "per_day_min_mg": _as_float(breakdown.get("per_day_min_mg")),
        "per_day_max_mg": _as_float(breakdown.get("per_day_max_mg")),
        "epa_mg_per_unit": _as_float(breakdown.get("epa_mg_per_unit")),
        "dha_mg_per_unit": _as_float(breakdown.get("dha_mg_per_unit")),
        "epa_dha_mg_per_unit": _as_float(breakdown.get("epa_dha_mg_per_unit")),
    }


def derive_proprietary_blend_audit(
    product: dict[str, Any],
    scored: dict[str, Any] | None = None,
) -> dict[str, Any]:
    proprietary_data = _safe_dict(product.get("proprietary_data"))
    section_b = _safe_dict(_safe_dict(_safe_dict(scored).get("breakdown")).get("B"))
    evidence = _safe_list(section_b.get("B5_blend_evidence"))
    penalty = _as_float(section_b.get("B5_penalty"), 0.0) or 0.0
    return {
        "has_proprietary_blends": bool(proprietary_data.get("has_proprietary_blends")),
        "blend_count": len(_safe_list(proprietary_data.get("blends"))),
        "penalty_score": round(penalty, 2),
        "evidence": evidence,
    }

