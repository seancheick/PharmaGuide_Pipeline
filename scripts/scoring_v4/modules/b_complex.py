"""v4 B-complex module.

B-complex products are focused micronutrient panels. They should not be scored
as broad multivitamins/prenatals, but they also should not get single-ingredient
rubric treatment. This module rewards:
  - a complete core B-vitamin panel,
  - moderate disclosed RDA/AI coverage,
  - preferred active forms where relevant,
  - clean formulation / transparency / verification via the shared v4 contracts.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from scoring_v4.modules.generic import GenericModuleResult, _assemble_score, _empty_dimensions
from scoring_v4.modules.generic_evidence import score_evidence as score_generic_evidence
from scoring_v4.modules.generic_formulation import shared_formulation_penalty_detail
from scoring_v4.modules.generic_helpers import (
    _as_float,
    _norm_text,
    _safe_dict,
    _safe_list,
    bio_score_of,
    get_active_ingredients,
    has_usable_individual_dose,
)
from scoring_v4.modules.generic_manufacturer import (
    score_manufacturer_trust,
    score_manufacturer_violations,
)
from scoring_v4.modules.generic_transparency import score_transparency
from scoring_v4.modules.safety_hygiene import score_safety_hygiene_base
from scoring_v4.modules.verification_bonus import score_verification_bonus


PHASE_MARKER = "P1.9_b_complex_module"

B_CORE = (
    "vitamin_b1_thiamine",
    "vitamin_b2_riboflavin",
    "vitamin_b3_niacin",
    "vitamin_b5_pantothenic_acid",
    "vitamin_b6_pyridoxine",
    "vitamin_b9_folate",
    "vitamin_b12_cobalamin",
    "vitamin_b7_biotin",
)
B_OPTIONAL_SUPPORT = {"choline", "inositol"}

from scoring_v4.quality_score_config import block as _cfg_block

_CM = _cfg_block("category_magnitudes", "b_complex")["b_complex"]


FORMULATION_CAP = _CM["formulation_cap"]
DOSE_CAP = _CM["dose_cap"]
EVIDENCE_CAP = _CM["evidence_cap"]
B7_UL_PCT_THRESHOLD = _CM["b7_ul_pct_threshold"]
B7_PER_FLAG_PENALTY = _CM["b7_per_flag_penalty"]
B7_CAP = _CM["b7_cap"]

PREFERRED_FORM_PATTERNS = {
    "vitamin_b2_riboflavin": re.compile(r"\b(riboflavin[-\s]?5[-\s]?phosphate|r5p)\b", re.IGNORECASE),
    "vitamin_b3_niacin": re.compile(r"\b(niacinamide|nicotinamide)\b", re.IGNORECASE),
    "vitamin_b6_pyridoxine": re.compile(r"\b(pyridoxal[-\s]?5[-\s]?phosphate|p5p|plp)\b", re.IGNORECASE),
    "vitamin_b9_folate": re.compile(r"\b(5[-\s]?mthf|l[-\s]?5[-\s]?mthf|methylfolate|folinic|quatrefolic)\b", re.IGNORECASE),
    "vitamin_b12_cobalamin": re.compile(r"\b(methylcobalamin|adenosylcobalamin|hydroxocobalamin|hydroxycobalamin)\b", re.IGNORECASE),
}


def _clamp(low: float, high: float, value: float) -> float:
    return max(low, min(high, value))


def _round(value: float) -> float:
    return round(float(value), 4)


def _b_key(value: Any) -> str:
    text = _norm_text(value).replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    if not text:
        return ""
    if text in {"vitamin b1 thiamine", "vitamin b1", "b1", "thiamin", "thiamine"}:
        return "vitamin_b1_thiamine"
    if text in {"vitamin b2 riboflavin", "vitamin b2", "b2", "riboflavin"} or "riboflavin" in text:
        return "vitamin_b2_riboflavin"
    if text in {"vitamin b3 niacin", "vitamin b3", "b3", "niacin", "niacinamide", "nicotinamide"} or "niacin" in text:
        return "vitamin_b3_niacin"
    if "pantothenic" in text or text in {"vitamin b5", "b5"}:
        return "vitamin_b5_pantothenic_acid"
    if "pyridox" in text or text in {"vitamin b6", "b6", "p5p", "plp"}:
        return "vitamin_b6_pyridoxine"
    if "folate" in text or "folic acid" in text or "mthf" in text or text in {"vitamin b9", "b9"}:
        return "vitamin_b9_folate"
    if "cobalamin" in text or text in {"vitamin b12", "b12"}:
        return "vitamin_b12_cobalamin"
    if "biotin" in text or text in {"vitamin b7", "b7"}:
        return "vitamin_b7_biotin"
    if "choline" in text:
        return "choline"
    if "inositol" in text:
        return "inositol"
    return text.replace(" ", "_")


def _row_b_key(row: Dict[str, Any]) -> str:
    for value in (
        row.get("canonical_id"),
        row.get("standard_name"),
        row.get("name"),
        row.get("matched_form"),
    ):
        key = _b_key(value)
        if key in set(B_CORE) | B_OPTIONAL_SUPPORT:
            return key
    return ""


def _active_rows(product: Dict[str, Any]) -> list[Dict[str, Any]]:
    return [row for row in get_active_ingredients(product) if isinstance(row, dict)]


def _b_rows(product: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    rows: Dict[str, Dict[str, Any]] = {}
    for row in _active_rows(product):
        key = _row_b_key(row)
        if key:
            rows.setdefault(key, row)
    return rows


def _ingredient_text(row: Dict[str, Any]) -> str:
    parts = []
    for key in ("name", "standard_name", "matched_form", "form", "raw_source_text"):
        value = row.get(key)
        if value:
            parts.append(str(value))
    for form in row.get("matched_forms") or []:
        if isinstance(form, dict):
            parts.extend(str(form.get(k)) for k in ("form_key", "raw_form_text", "matched_candidate") if form.get(k))
    return " ".join(parts)


def _score_preferred_forms(rows: Dict[str, Dict[str, Any]]) -> tuple[float, list[str]]:
    hits: list[str] = []
    for key, pattern in PREFERRED_FORM_PATTERNS.items():
        row = rows.get(key)
        if row and pattern.search(_ingredient_text(row)):
            hits.append(key)
    score = _clamp(0.0, 7.0, len(hits) * (7.0 / len(PREFERRED_FORM_PATTERNS)))
    return _round(score), hits


def _score_form_quality(rows: Dict[str, Dict[str, Any]]) -> tuple[float, Optional[float]]:
    scores = []
    for key in B_CORE:
        row = rows.get(key)
        if not row:
            continue
        score = bio_score_of(row)
        if score is None:
            score = 10.0 if row.get("mapped") else 0.0
        scores.append(_clamp(0.0, 15.0, float(score)))
    if not scores:
        return 0.0, None
    avg = sum(scores) / len(scores)
    return _round((avg / 15.0) * 8.0), _round(avg)


def _score_focus_purity(product: Dict[str, Any], rows: Dict[str, Dict[str, Any]]) -> tuple[float, int]:
    b_keys = set(rows)
    non_b = 0
    for row in _active_rows(product):
        if _row_b_key(row) in b_keys:
            continue
        canonical = _norm_text(row.get("canonical_id") or row.get("standard_name") or row.get("name"))
        if not canonical:
            continue
        non_b += 1
    if non_b == 0:
        return 3.0, 0
    if non_b == 1:
        return 2.0, non_b
    return 0.0, non_b


def _score_dose_disclosure(rows: Dict[str, Dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    disclosed = sum(1 for row in rows.values() if has_usable_individual_dose(row))
    return _round(_clamp(0.0, 2.0, (disclosed / len(rows)) * 2.0))


def _score_formulation(product: Dict[str, Any]) -> Dict[str, Any]:
    rows = _b_rows(product)
    core_count = len(set(rows) & set(B_CORE))
    core_panel = _round((core_count / len(B_CORE)) * 10.0)
    form_quality, avg_bio = _score_form_quality(rows)
    preferred_forms, preferred_hits = _score_preferred_forms(rows)
    focus_purity, non_b_count = _score_focus_purity(product, rows)
    dose_disclosure = _score_dose_disclosure(rows)

    shared = shared_formulation_penalty_detail(product)
    penalties = dict(shared["penalties"])
    positive = core_panel + form_quality + preferred_forms + focus_purity + dose_disclosure
    penalty_total = sum(abs(float(value)) for value in penalties.values())
    score = _round(_clamp(0.0, FORMULATION_CAP, positive - penalty_total))
    return {
        "score": score,
        "max": FORMULATION_CAP,
        "components": {
            "core_b_panel_coverage": core_panel,
            "b_form_quality": form_quality,
            "preferred_active_forms": preferred_forms,
            "b_complex_focus_purity": focus_purity,
            "dose_disclosure": dose_disclosure,
        },
        "penalties": penalties,
        "metadata": {
            "phase": PHASE_MARKER,
            "method": "focused_b_complex_panel_form_quality",
            "core_b_count": core_count,
            "optional_support_count": len(set(rows) & B_OPTIONAL_SUPPORT),
            "average_bio_score": avg_bio,
            "preferred_form_hits": preferred_hits,
            "non_b_active_count": non_b_count,
            **shared.get("metadata", {}),
        },
    }


def _pct_values(row: Dict[str, Any]) -> tuple[Optional[float], Optional[float]]:
    return _as_float(row.get("pct_rda"), None), _as_float(row.get("pct_ul"), None)


def _coverage_credit(key: str, pct_rda: Optional[float], pct_ul: Optional[float]) -> Optional[float]:
    if pct_rda is None and pct_ul is None:
        return None
    if pct_ul is not None:
        if pct_ul >= B7_UL_PCT_THRESHOLD:
            return 0.0
        if pct_ul > 100.0:
            return 0.4
    if pct_rda is None:
        return None
    if pct_rda <= 0:
        return 0.0
    if pct_rda < 25.0:
        return pct_rda / 50.0
    if pct_rda < 50.0:
        return 0.5 + ((pct_rda - 25.0) / 25.0) * 0.35
    if pct_rda <= 300.0:
        return 1.0
    if key in {"vitamin_b12_cobalamin", "vitamin_b7_biotin"} and pct_ul is None:
        return 0.95
    if pct_rda <= 1000.0:
        return 0.9
    return 0.75


def _coverage_scores(product: Dict[str, Any]) -> Dict[str, float]:
    rows = _safe_list(_safe_dict(product.get("rda_ul_data")).get("adequacy_results"))
    scores: Dict[str, float] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("scoring_eligible") is False:
            continue
        key = _b_key(row.get("nutrient") or row.get("standard_name"))
        if key not in set(B_CORE) | B_OPTIONAL_SUPPORT:
            continue
        credit = _coverage_credit(key, *_pct_values(row))
        if credit is None:
            continue
        scores[key] = max(scores.get(key, 0.0), _round(_clamp(0.0, 1.0, credit)))
    return scores


def _b7_dose_safety(product: Dict[str, Any]) -> float:
    total = 0.0
    for flag in _safe_list(_safe_dict(product.get("rda_ul_data")).get("safety_flags")):
        if not isinstance(flag, dict):
            continue
        pct_ul = _as_float(flag.get("pct_ul"), 0.0) or 0.0
        if pct_ul >= B7_UL_PCT_THRESHOLD:
            total += B7_PER_FLAG_PENALTY
    return _round(_clamp(0.0, B7_CAP, total))


def _score_dose(product: Dict[str, Any]) -> Dict[str, Any]:
    coverage = _coverage_scores(product)
    core_scores = {key: value for key, value in coverage.items() if key in B_CORE}
    if core_scores:
        avg = sum(core_scores.values()) / len(B_CORE)
    else:
        avg = 0.0
    rda_ai_coverage = _round(avg * 18.0)
    panel_breadth = _round((len(core_scores) / len(B_CORE)) * 4.0)
    moderate_dose_fit = 3.0 if _b7_dose_safety(product) == 0.0 and core_scores else 0.0
    b7 = _b7_dose_safety(product)
    score = _round(_clamp(0.0, DOSE_CAP, rda_ai_coverage + panel_breadth + moderate_dose_fit - b7))
    return {
        "score": score,
        "max": DOSE_CAP,
        "components": {
            "b_rda_ai_coverage": rda_ai_coverage,
            "core_b_panel_breadth": panel_breadth,
            "moderate_dose_fit": moderate_dose_fit,
        },
        "penalties": {"B7_dose_safety": -b7},
        "metadata": {
            "phase": PHASE_MARKER,
            "method": "b_complex_rda_ai_moderate_dose_window",
            "coverage_nutrient_count": len(coverage),
            "coverage_nutrient_scores": dict(sorted(coverage.items())),
        },
    }


def _score_evidence(product: Dict[str, Any]) -> Dict[str, Any]:
    generic = score_generic_evidence(product)
    generic_score = _as_float(generic.get("score"), 0.0) or 0.0
    core_count = len(set(_b_rows(product)) & set(B_CORE))
    nutrition_authority = 6.0 + (core_count / len(B_CORE)) * 6.0 if core_count else 0.0
    adjusted = _round(_clamp(0.0, EVIDENCE_CAP, max(min(generic_score, 15.0), nutrition_authority)))
    return {
        "score": adjusted,
        "max": EVIDENCE_CAP,
        "components": {
            "b_nutrient_authority_floor": _round(nutrition_authority),
            "generic_evidence_signal": _round(generic_score),
        },
        "penalties": {},
        "metadata": {
            "phase": PHASE_MARKER,
            "method": "essential_b_nutrient_authority_floor_with_generic_evidence_cap",
            "core_b_count": core_count,
            "generic_evidence_metadata": dict(_safe_dict(generic.get("metadata"))),
        },
    }


def _fill_dimension(result: GenericModuleResult, name: str, payload: Dict[str, Any]) -> None:
    dim = result.dimensions[name]
    dim.score = payload["score"]
    dim.components = payload["components"]
    dim.penalties = payload["penalties"]
    dim.metadata = payload.get("metadata", {})


def score_b_complex(product: Any) -> GenericModuleResult:
    if not isinstance(product, dict):
        product = {}

    result = GenericModuleResult(module="b_complex", dimensions=_empty_dimensions())

    _fill_dimension(result, "formulation", _score_formulation(product))
    _fill_dimension(result, "dose", _score_dose(product))
    _fill_dimension(result, "evidence", _score_evidence(product))
    _fill_dimension(result, "transparency", score_transparency(product))

    vb_payload = score_verification_bonus(product, "generic")
    result.verification_bonus.score = vb_payload["score"]
    result.verification_bonus.max = vb_payload["max"]
    result.verification_bonus.components = vb_payload["components"]
    result.verification_bonus.penalties = vb_payload.get("penalties", {})
    result.verification_bonus.metadata = vb_payload.get("metadata", {})

    manufacturer_trust_payload = score_manufacturer_trust(product)
    result.manufacturer_trust.score = manufacturer_trust_payload["score"]
    result.manufacturer_trust.max = manufacturer_trust_payload["max"]
    result.manufacturer_trust.components = manufacturer_trust_payload["components"]
    result.manufacturer_trust.metadata = manufacturer_trust_payload.get("metadata", {})

    manufacturer_violations_payload = score_manufacturer_violations(product)
    result.manufacturer_violations.score = manufacturer_violations_payload["score"]
    result.manufacturer_violations.floor = manufacturer_violations_payload["floor"]
    result.manufacturer_violations.components = manufacturer_violations_payload["components"]
    result.manufacturer_violations.metadata = manufacturer_violations_payload.get("metadata", {})

    result.safety_hygiene_base = score_safety_hygiene_base(product)
    _assemble_score(result)
    result.phase = PHASE_MARKER
    result.metadata["phase"] = PHASE_MARKER
    return result
