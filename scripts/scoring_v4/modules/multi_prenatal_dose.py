"""v4 multi/prenatal Dose dimension (P3.2).

Dose for multis/prenatals uses the shared nutritional RDA/AI curve and the
enricher's `rda_ul_data.adequacy_results`. Safety stays in the single
product-level ceiling; no v3 scorer imports.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from scoring_v4.dose_safety import resolve_dose_safety
from scoring_v4.exposure import row_exposure
from scoring_v4.modules.generic_helpers import (
    get_active_ingredients,
    has_usable_individual_dose,
    _as_float,
    _norm_text,
    _safe_dict,
    _safe_list,
)
from scoring_input_contract import PRENATAL_TITLE_RE

# Coverage is not weighted by form bio_score (quality_score 1.7.0). bio_score is
# an ordinal IQM form rating, not a measured absorption fraction, and it already
# drives Formulation panel form quality. Dose scores the disclosed amount only.


from scoring_v4.quality_score_config import block as _cfg_block

_DM = _cfg_block("dose_magnitudes", "multi_prenatal")["multi_prenatal"]


DIMENSION_CAP = _DM["dimension_cap"]
CAP_RDA_AI_COVERAGE = _DM["cap_rda_ai_coverage"]
CAP_CRITICAL_NUTRIENT_COVERAGE = _DM["cap_critical_nutrient_coverage"]
CAP_PRENATAL_COMPLEMENT_SUPPORT = _DM["cap_prenatal_complement_support"]

PRENATAL_DHA_FULL_MG = _DM["prenatal_dha_full_mg"]

PHASE_MARKER = "P3.2_multi_prenatal_dose"
METHOD_MARKER = "rda_ai_panel_coverage_from_enriched_rda_ul_data"

DHA_RE = re.compile(r"\bdha\b|docosahexaenoic", re.IGNORECASE)
TARGETED_MULTI_RE = re.compile(r"\b(essential|targeted|selective|minimalist|core)\b", re.IGNORECASE)
BROAD_MULTI_RE = re.compile(
    r"\b(complete|comprehensive|full[\s-]*spectrum|one\s+a\s+day|whole\s+food|total|centrum|mega\s+men)\b",
    re.IGNORECASE,
)

CORE_MULTI_ANCHORS = (
    "vitamin_a",
    "vitamin_c",
    "vitamin_d",
    "folate",
    "vitamin_b12",
    "zinc",
)
TARGETED_MULTI_ANCHORS = (
    "vitamin_d",
    "folate",
    "vitamin_b12",
    "iron",
    "magnesium",
    "zinc",
)
TARGETED_MULTI_SELECTED_ANCHORS = _DM["targeted_multi_selected_anchors"]

PRENATAL_CORE_ANCHORS = (
    "folate",
    "iron",
    "iodine",
    "vitamin_d",
    "vitamin_b12",
    "choline",
)
# Choline belongs to the fixed prenatal critical core; DHA retains its separate
# one-point complement budget.
PRENATAL_COMPLEMENT_ANCHORS = ("dha",)


def _clamp(low: float, high: float, value: float) -> float:
    return max(low, min(high, value))


def _round(value: float) -> float:
    return round(float(value), 4)


def _safe_product(product: Any) -> Dict[str, Any]:
    return product if isinstance(product, dict) else {}


def _nutrient_key(value: Any) -> str:
    text = _norm_text(value)
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    if not text:
        return ""

    if "folate" in text or "folic acid" in text or "vitamin b9" in text:
        return "folate"
    if "b12" in text or "cobalamin" in text:
        return "vitamin_b12"
    if "b1" in text or "thiamine" in text:
        return "vitamin_b1_thiamine"
    if "b2" in text or "riboflavin" in text:
        return "vitamin_b2_riboflavin"
    if "b3" in text or "niacin" in text:
        return "vitamin_b3_niacin"
    if "b6" in text or "pyridoxine" in text:
        return "vitamin_b6_pyridoxine"
    if "vitamin a" in text:
        return "vitamin_a"
    if "vitamin c" in text:
        return "vitamin_c"
    if "vitamin d" in text:
        return "vitamin_d"
    if "vitamin e" in text:
        return "vitamin_e"
    if "vitamin k" in text:
        return "vitamin_k"
    if "iron" in text:
        return "iron"
    if "iodine" in text:
        return "iodine"
    if "choline" in text:
        return "choline"
    if "zinc" in text:
        return "zinc"
    if "magnesium" in text:
        return "magnesium"
    if "calcium" in text:
        return "calcium"
    if "selenium" in text:
        return "selenium"
    if "dha" in text or "docosahexaenoic" in text:
        return "dha"

    return text.replace(" ", "_")


def _is_prenatal(product: Dict[str, Any]) -> bool:
    # Use product-label text only. Brand/bundle context such as "Prenatal
    # Program" can contain standalone calcium/DHA/herbal SKUs that should not
    # inherit full prenatal-multi critical-nutrient floors.
    haystack = " ".join(
        str(product.get(key) or "")
        for key in ("product_name", "fullName")
    )
    return bool(PRENATAL_TITLE_RE.search(haystack))


def _label_text(product: Dict[str, Any]) -> str:
    return " ".join(
        str(product.get(key) or "")
        for key in ("product_name", "fullName")
    )


def _is_targeted_multi(product: Dict[str, Any]) -> bool:
    """Return True for selective gap-filler multivitamins.

    A targeted multi should be judged on whether it covers its adult
    gap-filler job, not whether it includes every classical complete-multi
    anchor. Broad/complete multis keep the fixed complete-multi anchor set.
    """
    text = _label_text(product)
    if not TARGETED_MULTI_RE.search(text):
        return False
    return not BROAD_MULTI_RE.search(text)


def _active_ingredients(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    return get_active_ingredients(product)


def _coverage_unit_credit(pct_rda: Optional[float], pct_ul: Optional[float]) -> Optional[float]:
    """Return 0..1 adequacy per distinct nutrient, or None when not evaluable.

    ``pct_ul`` is unused: an upper-limit exceedance is the product-level Dose
    ceiling's (Dose V4.1 §2.4), never a per-nutrient reduction here.
    """
    from scoring_v4.modules.generic_dose import nutritional_unit_credit

    return nutritional_unit_credit(pct_rda)


def _coverage_scores(
    product: Dict[str, Any],
    *,
    rda_group: Optional[str] = None,
    reference_assessments: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, float]:
    rda_ul = _safe_dict(product.get("rda_ul_data"))
    rows = _safe_list(rda_ul.get("adequacy_results"))
    scores: Dict[str, float] = {}

    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("scoring_eligible") is False:
            continue
        key = _nutrient_key(row.get("nutrient") or row.get("standard_name"))
        if not key:
            continue
        pct_rda, pct_ul = _normalized_pct_values(row, key, rda_group=rda_group)
        credit = _coverage_unit_credit(
            pct_rda,
            pct_ul,
        )
        if credit is None:
            continue
        if reference_assessments is not None:
            reference = {name: row.get(name) for name in (
                "nutrient", "canonical_id", "amount", "unit", "per_day_min", "per_day_max",
                "rda_ai", "ul", "ul_basis", "ul_population") if row.get(name) is not None}
            reference["pct_rda"] = pct_rda
            group_reference = _group_rda_ai(row, rda_group) if rda_group else None
            if group_reference is not None:
                reference.update(rda_ai=group_reference, reference_population=rda_group)
            reference_assessments.append(reference)
        # Multiple rows for the same nutrient (e.g. vitamin A forms) should
        # not overweight the average. Keep the best row-level coverage signal.
        scores[key] = max(scores.get(key, 0.0), _round(_clamp(0.0, 1.0, credit)))
    return scores


def _unit_text(row: Dict[str, Any]) -> str:
    return _norm_text(row.get("unit") or row.get("original_unit"))


def _group_rda_ai(row: Dict[str, Any], group: str) -> Optional[float]:
    """Read the adult reference for a life-stage group from the RDA/UL owner."""
    candidates = [
        item
        for item in _safe_list(row.get("data_by_group"))
        if isinstance(item, dict) and _norm_text(item.get("group")) == _norm_text(group)
    ]
    for age_range in ("19-30", "31-50"):
        for item in candidates:
            if str(item.get("age_range") or "").strip() != age_range:
                continue
            value = _as_float(item.get("rda_ai"), None)
            if value is not None and value > 0:
                return value
    return None


def _normalized_pct_values(
    row: Dict[str, Any],
    nutrient_key: str,
    *,
    rda_group: Optional[str] = None,
) -> tuple[Optional[float], Optional[float]]:
    """Return normalized adequacy and safety percentages.

    Older enriched artifacts treated `1.7 mg DFE` as `1.7 mcg DFE` when
    computing pct_rda/pct_ul because `unit_conversions.json` lacked
    mg_DFE -> mcg_DFE conversion rules. The converter fix prevents this on the
    next pipeline run; this guard keeps v4 scoring correct on already-enriched
    blobs. For prenatal products, adequacy is then rebased from the neutral RDA
    to the adult Pregnancy RDA already carried in `data_by_group`. The UL
    percentage remains owned by the universal safety policy.
    """
    pct_rda = _as_float(row.get("pct_rda"), None)
    pct_ul = _as_float(row.get("pct_ul"), None)
    if nutrient_key == "folate":
        amount = _as_float(row.get("amount") or row.get("original_quantity"), None)
        unit = _unit_text(row)
        stale_mg_dfe = (
            amount is not None
            and amount > 0
            and unit.startswith("mg")
            and (pct_rda is None or pct_rda < 10.0)
            and (pct_ul is None or pct_ul < 10.0)
        )
        if stale_mg_dfe:
            amount_mcg_dfe = amount * (1000.0 if "dfe" in unit else 1700.0)
            rda_ai = _as_float(row.get("rda_ai"), None)
            ul = _as_float(row.get("ul"), None)
            if rda_ai and rda_ai > 0:
                pct_rda = (amount_mcg_dfe / rda_ai) * 100.0
            if ul and ul > 0:
                pct_ul = (amount_mcg_dfe / ul) * 100.0

    if rda_group and pct_rda is not None:
        neutral_rda = _as_float(row.get("rda_ai"), None)
        group_rda = _group_rda_ai(row, rda_group)
        if neutral_rda is not None and neutral_rda > 0 and group_rda is not None:
            pct_rda = pct_rda * neutral_rda / group_rda

    return pct_rda, pct_ul


def _score_rda_ai_coverage(scores: Dict[str, float]) -> float:
    if not scores:
        return 0.0
    avg = sum(scores.values()) / len(scores)
    return _round(_clamp(0.0, CAP_RDA_AI_COVERAGE, avg * CAP_RDA_AI_COVERAGE))


def _is_dha_ingredient(ingredient: Dict[str, Any]) -> bool:
    canonical = _norm_text(ingredient.get("canonical_id") or ingredient.get("standard_name") or "")
    if canonical in {"dha", "epa_dha", "docosahexaenoic_acid"}:
        return True
    if DHA_RE.search(str(ingredient.get("name") or "")):
        return True
    return bool(DHA_RE.search(canonical.replace("_", "-")))


def _dha_score(product: Dict[str, Any]) -> float:
    best = 0.0
    for ing in _active_ingredients(product):
        if not _is_dha_ingredient(ing):
            continue
        if not has_usable_individual_dose(ing):
            continue
        qty = row_exposure(product, ing, basis="daily", unit="mg").benchmark_amount
        if qty is None:
            continue
        canonical = _norm_text(ing.get("canonical_id") or ing.get("standard_name") or "")
        name = _norm_text(ing.get("name"))
        if canonical == "epa_dha" or re.search(r"\bepa\b", name):
            # An aggregate does not establish the explicit DHA amount.
            continue
        best = max(best, min(qty / PRENATAL_DHA_FULL_MG, 1.0))
    return best


def _targeted_multi_critical_scores(
    coverage_scores: Dict[str, float],
) -> tuple[Dict[str, float], Dict[str, float]]:
    scored = {
        anchor: _round(_clamp(0.0, 1.0, coverage_scores.get(anchor, 0.0)))
        for anchor in TARGETED_MULTI_ANCHORS
    }
    selected = sorted(scored.items(), key=lambda item: (-item[1], item[0]))[:TARGETED_MULTI_SELECTED_ANCHORS]
    return dict(sorted(selected)), scored


def _critical_scores(product: Dict[str, Any], coverage_scores: Dict[str, float]) -> tuple[str, Dict[str, float], List[str]]:
    prenatal = _is_prenatal(product)
    targeted_multi = (not prenatal) and _is_targeted_multi(product)
    anchors = PRENATAL_CORE_ANCHORS if prenatal else CORE_MULTI_ANCHORS
    mode = "prenatal" if prenatal else ("targeted_core_multi" if targeted_multi else "core_multi")

    if targeted_multi:
        scores, all_scores = _targeted_multi_critical_scores(coverage_scores)
        missing = [anchor for anchor in TARGETED_MULTI_ANCHORS if all_scores.get(anchor, 0.0) <= 0]
        return mode, scores, missing

    scores: Dict[str, float] = {}
    missing: List[str] = []
    for anchor in anchors:
        value = coverage_scores.get(anchor, 0.0)
        value = _round(_clamp(0.0, 1.0, value))
        scores[anchor] = value
        if value <= 0:
            missing.append(anchor)

    return mode, scores, missing


def _prenatal_complement_scores(product: Dict[str, Any]) -> Dict[str, float]:
    if not _is_prenatal(product):
        return {}
    return {"dha": _round(_clamp(0.0, 1.0, _dha_score(product)))}


def _score_critical_coverage(scores: Dict[str, float]) -> float:
    if not scores:
        return 0.0
    avg = sum(scores.values()) / len(scores)
    return _round(_clamp(0.0, CAP_CRITICAL_NUTRIENT_COVERAGE, avg * CAP_CRITICAL_NUTRIENT_COVERAGE))


def _score_prenatal_complement_support(scores: Dict[str, float]) -> float:
    if not scores:
        return 0.0
    avg = sum(scores.values()) / len(PRENATAL_COMPLEMENT_ANCHORS)
    return _round(_clamp(0.0, CAP_PRENATAL_COMPLEMENT_SUPPORT, avg * CAP_PRENATAL_COMPLEMENT_SUPPORT))


def score_dose(product: Any) -> Dict[str, Any]:
    """Compute the P3.2 multi/prenatal Dose 25 dimension."""
    product = _safe_product(product)

    prenatal = _is_prenatal(product)
    reference_assessments: List[Dict[str, Any]] = []
    coverage_scores = _coverage_scores(product, rda_group="Pregnancy" if prenatal else None,
                                       reference_assessments=reference_assessments)
    rda_ai_coverage = _score_rda_ai_coverage(coverage_scores)
    critical_mode, critical_scores, critical_missing = _critical_scores(product, coverage_scores)
    critical_coverage = _score_critical_coverage(critical_scores)
    prenatal_complement_scores = _prenatal_complement_scores(product)
    prenatal_complement_support = _score_prenatal_complement_support(prenatal_complement_scores)
    b7_evaluation = resolve_dose_safety(product)
    b7_ignored_flags = b7_evaluation.ignored_flags

    components = {
        "rda_ai_coverage": rda_ai_coverage,
        "critical_nutrient_coverage": critical_coverage,
    }
    if prenatal_complement_support > 0:
        components["prenatal_complement_support"] = prenatal_complement_support
    penalties: Dict[str, float] = {}

    positive = sum(components.values())
    score = _round(_clamp(0.0, DIMENSION_CAP, positive))

    metadata: Dict[str, Any] = {
        "phase": PHASE_MARKER,
        "method": METHOD_MARKER,
        "coverage_nutrient_count": len(coverage_scores),
        "reference_assessments": reference_assessments,
        "coverage_nutrient_scores": dict(sorted(coverage_scores.items())),
        "critical_nutrient_mode": critical_mode,
        "critical_nutrient_scores": dict(sorted(critical_scores.items())),
        "critical_nutrients_missing": critical_missing,
        "prenatal_complement_scores": dict(sorted(prenatal_complement_scores.items())),
        "B7_ignored_safety_flags": b7_ignored_flags,
        "B7_safety_evaluation": b7_evaluation.audit_metadata(),
    }
    if not coverage_scores:
        metadata["coverage_status"] = "no_rda_reference_data"

    return {
        "score": score,
        "max": DIMENSION_CAP,
        "components": components,
        "penalties": penalties,
        "metadata": metadata,
    }
