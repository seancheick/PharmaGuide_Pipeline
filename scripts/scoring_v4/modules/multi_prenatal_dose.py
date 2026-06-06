"""v4 multi/prenatal Dose dimension (P3.2).

Dose for multis/prenatals is RDA/AI-centered, but not punitive toward
common above-RDA B-vitamin dosing when no UL exists. It uses the
enricher's `rda_ul_data.adequacy_results` and `safety_flags`; no v3 scorer
imports.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

from scoring_v4.modules.generic_helpers import (
    get_active_ingredients,
    has_usable_individual_dose,
    bio_score_of,
    _as_float,
    _norm_text,
    _safe_dict,
    _safe_list,
)

# Bioavailability weighting of dose coverage. "Adequate on paper" (100% RDA) does
# not mean adequate in vivo — magnesium oxide is poorly absorbed vs glycinate. So
# each nutrient's coverage credit is scaled by its FORM bio_score, so a cheap-form
# multi cannot out-dose a premium-form one purely on panel breadth. Floor 0.75 so
# a cheap-but-real form still mostly counts as dose; formulation remains the main
# lane for form-quality differences. Unknown bio_score is neutral (1.0).
_BIO_SCORE_MAX = 15.0
_BIO_WEIGHT_FLOOR = 0.75


DIMENSION_CAP = 25.0
CAP_RDA_AI_COVERAGE = 15.0
CAP_PANEL_BREADTH = 3.0
CAP_CRITICAL_NUTRIENT_COVERAGE = 5.0
CAP_PRENATAL_COMPLEMENT_SUPPORT = 2.0

B7_UL_PCT_THRESHOLD = 150.0
B7_PER_FLAG_PENALTY = 2.0
B7_CAP = 3.0

PANEL_BREADTH_FULL_COUNT = 18
PRENATAL_DHA_FULL_MG = 200.0
PRENATAL_DHA_PARTIAL_MG = 100.0

PHASE_MARKER = "P3.2_multi_prenatal_dose"
METHOD_MARKER = "rda_ai_panel_coverage_from_enriched_rda_ul_data"

PRENATAL_RE = re.compile(r"\b(prenatal|pregnancy|pre-natal|expecting|maternal|gestation)\b")
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
TARGETED_MULTI_SELECTED_ANCHORS = 5

PRENATAL_CORE_ANCHORS = (
    "folate",
    "iron",
    "iodine",
    "vitamin_d",
    "vitamin_b12",
)
PRENATAL_COMPLEMENT_ANCHORS = ("choline", "dha")

CRITICAL_MIN_PCT_RDA = {
    "folate": 50.0,
    "iron": 50.0,
    "iodine": 50.0,
    "vitamin_d": 50.0,
    "vitamin_b12": 50.0,
    "choline": 25.0,
}


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
    return bool(PRENATAL_RE.search(_norm_text(haystack)))


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
    """Return 0..1 per distinct nutrient, or None when not evaluable."""
    if pct_rda is None and pct_ul is None:
        return None

    if pct_ul is not None:
        if pct_ul >= B7_UL_PCT_THRESHOLD:
            return 0.0
        if pct_ul > 100.0:
            return 0.5

    if pct_rda is None:
        return None
    if pct_rda <= 0:
        return 0.0
    if pct_rda < 25.0:
        return pct_rda / 50.0
    if pct_rda < 50.0:
        return 0.5 + ((pct_rda - 25.0) / 25.0) * 0.35
    if pct_rda <= 200.0:
        return 1.0
    if pct_rda <= 500.0:
        return 0.85
    return 0.65


def _nutrient_bio_index(product: Dict[str, Any]) -> Dict[str, float]:
    """nutrient_key -> form bio_score, from the scorable ingredient rows. Used to
    bioavailability-weight each nutrient's dose-coverage credit."""
    index: Dict[str, float] = {}
    for row in get_active_ingredients(product):
        if not isinstance(row, dict):
            continue
        bio = bio_score_of(row)
        if bio is None:
            continue
        for tok in (row.get("canonical_id"), row.get("standard_name"), row.get("name")):
            key = _nutrient_key(tok)
            if key:
                index[key] = max(index.get(key, 0.0), float(bio))
    return index


def _bio_weight(bio_score: Optional[float]) -> float:
    """Coverage weight from a form's bio_score: premium ~1.0, cheap ~floor.
    Unknown bio is neutral (1.0) so we never penalize missing data."""
    if bio_score is None:
        return 1.0
    return max(_BIO_WEIGHT_FLOOR, min(1.0, _BIO_WEIGHT_FLOOR + (1.0 - _BIO_WEIGHT_FLOOR) * (bio_score / _BIO_SCORE_MAX)))


def _coverage_scores(product: Dict[str, Any]) -> Dict[str, float]:
    rda_ul = _safe_dict(product.get("rda_ul_data"))
    rows = _safe_list(rda_ul.get("adequacy_results"))
    bio_index = _nutrient_bio_index(product)
    scores: Dict[str, float] = {}

    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("scoring_eligible") is False:
            continue
        key = _nutrient_key(row.get("nutrient") or row.get("standard_name"))
        if not key:
            continue
        credit = _coverage_unit_credit(
            _as_float(row.get("pct_rda"), None),
            _as_float(row.get("pct_ul"), None),
        )
        if credit is None:
            continue
        # Bioavailability-weight the coverage credit by the nutrient's form quality
        # (cheap oxide/synthetic forms count less toward "adequate dose").
        credit = credit * _bio_weight(bio_index.get(key))
        # Multiple rows for the same nutrient (e.g. vitamin A forms) should
        # not overweight the average. Keep the best row-level coverage signal.
        scores[key] = max(scores.get(key, 0.0), _round(_clamp(0.0, 1.0, credit)))
    return scores


def _critical_threshold_scores(product: Dict[str, Any]) -> Dict[str, float]:
    """Raw RDA/AI threshold credit for prenatal-critical nutrients.

    Broad dose coverage is bioavailability-weighted so a low-quality form does
    not outscore a premium one. Critical prenatal adequacy is a different
    question: did the label disclose enough folate/iron/iodine/choline to clear
    the clinically meaningful minimum? Use raw pct_rda for that threshold, then
    let formulation carry form quality and B7 carry excess-dose safety.
    """
    rda_ul = _safe_dict(product.get("rda_ul_data"))
    rows = _safe_list(rda_ul.get("adequacy_results"))
    scores: Dict[str, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("scoring_eligible") is False:
            continue
        key = _nutrient_key(row.get("nutrient") or row.get("standard_name"))
        min_pct = CRITICAL_MIN_PCT_RDA.get(key)
        if min_pct is None:
            continue
        pct_rda = _as_float(row.get("pct_rda"), None)
        if pct_rda is None or pct_rda <= 0:
            credit = 0.0
        elif pct_rda >= min_pct:
            credit = 1.0
        else:
            credit = 0.5
        scores[key] = max(scores.get(key, 0.0), credit)
    return scores


def _score_rda_ai_coverage(scores: Dict[str, float]) -> float:
    if not scores:
        return 0.0
    avg = sum(scores.values()) / len(scores)
    return _round(_clamp(0.0, CAP_RDA_AI_COVERAGE, avg * CAP_RDA_AI_COVERAGE))


def _score_panel_breadth(scores: Dict[str, float]) -> float:
    count = len(scores)
    if count <= 0:
        return 0.0
    return _round(_clamp(0.0, CAP_PANEL_BREADTH, (count / PANEL_BREADTH_FULL_COUNT) * CAP_PANEL_BREADTH))


def _is_dha_ingredient(ingredient: Dict[str, Any]) -> bool:
    canonical = _norm_text(ingredient.get("canonical_id") or ingredient.get("standard_name") or "")
    if canonical in {"dha", "epa_dha", "docosahexaenoic_acid"}:
        return True
    if DHA_RE.search(str(ingredient.get("name") or "")):
        return True
    return bool(DHA_RE.search(canonical.replace("_", "-")))


def _quantity_mg(ingredient: Dict[str, Any]) -> Optional[float]:
    qty = _as_float(ingredient.get("quantity"), None)
    if qty is None or qty <= 0:
        return None
    unit = _norm_text(
        ingredient.get("unit_normalized")
        or ingredient.get("normalized_unit")
        or ingredient.get("unit")
    )
    compact = unit.replace(" ", "")
    if compact in {"mg", "milligram", "milligrams", "milligram(s)"}:
        return qty
    if compact in {"g", "gram", "grams", "gram(s)"}:
        return qty * 1000.0
    if compact in {"mcg", "ug", "microgram", "micrograms", "microgram(s)"}:
        return qty / 1000.0
    return None


def _dha_score(product: Dict[str, Any]) -> float:
    best = 0.0
    for ing in _active_ingredients(product):
        if not _is_dha_ingredient(ing):
            continue
        if not has_usable_individual_dose(ing):
            continue
        qty = _quantity_mg(ing)
        if qty is None:
            continue
        canonical = _norm_text(ing.get("canonical_id") or ing.get("standard_name") or "")
        is_combined_epa_dha = canonical == "epa_dha"
        if is_combined_epa_dha:
            # EPA+DHA aggregate is useful omega evidence, but it does not prove
            # the DHA component alone reaches the prenatal DHA target. Give
            # partial critical-nutrient credit without pretending itemization.
            if qty >= PRENATAL_DHA_FULL_MG:
                best = max(best, 0.5)
            elif qty > 0:
                best = max(best, 0.25)
            continue
        if qty >= PRENATAL_DHA_FULL_MG:
            best = max(best, 1.0)
        elif qty >= PRENATAL_DHA_PARTIAL_MG:
            best = max(best, 0.5)
        elif qty > 0:
            best = max(best, 0.25)
    return best


def _anchor_critical_value(anchor: str, coverage_scores: Dict[str, float], threshold_scores: Dict[str, float]) -> float:
    if anchor in threshold_scores:
        return threshold_scores[anchor]
    coverage = coverage_scores.get(anchor, 0.0)
    # Critical coverage uses stricter minimums than the broad RDA average. If a
    # nutrient is present but below the minimum, it can still earn half credit.
    min_pct = CRITICAL_MIN_PCT_RDA.get(anchor)
    if min_pct is None:
        return coverage
    return coverage if coverage >= 1.0 else (0.5 if coverage > 0 else 0.0)


def _targeted_multi_critical_scores(
    coverage_scores: Dict[str, float],
    threshold_scores: Dict[str, float],
) -> tuple[Dict[str, float], Dict[str, float]]:
    scored = {
        anchor: _round(_clamp(0.0, 1.0, _anchor_critical_value(anchor, coverage_scores, threshold_scores)))
        for anchor in TARGETED_MULTI_ANCHORS
    }
    selected = sorted(scored.items(), key=lambda item: (-item[1], item[0]))[:TARGETED_MULTI_SELECTED_ANCHORS]
    return dict(sorted(selected)), scored


def _critical_scores(product: Dict[str, Any], coverage_scores: Dict[str, float]) -> tuple[str, Dict[str, float], List[str]]:
    prenatal = _is_prenatal(product)
    targeted_multi = (not prenatal) and _is_targeted_multi(product)
    anchors = PRENATAL_CORE_ANCHORS if prenatal else CORE_MULTI_ANCHORS
    mode = "prenatal" if prenatal else ("targeted_core_multi" if targeted_multi else "core_multi")
    threshold_scores = _critical_threshold_scores(product)

    if targeted_multi:
        scores, all_scores = _targeted_multi_critical_scores(coverage_scores, threshold_scores)
        missing = [anchor for anchor in TARGETED_MULTI_ANCHORS if all_scores.get(anchor, 0.0) <= 0]
        return mode, scores, missing

    scores: Dict[str, float] = {}
    missing: List[str] = []
    for anchor in anchors:
        if anchor == "dha":
            value = _dha_score(product)
        else:
            value = _anchor_critical_value(anchor, coverage_scores, threshold_scores)
        value = _round(_clamp(0.0, 1.0, value))
        scores[anchor] = value
        if value <= 0:
            missing.append(anchor)

    return mode, scores, missing


def _prenatal_complement_scores(product: Dict[str, Any]) -> Dict[str, float]:
    if not _is_prenatal(product):
        return {}
    threshold_scores = _critical_threshold_scores(product)
    scores = {
        "choline": _round(_clamp(0.0, 1.0, threshold_scores.get("choline", 0.0))),
        "dha": _round(_clamp(0.0, 1.0, _dha_score(product))),
    }
    return scores


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


def _is_folate_parent_total_duplicate_flag(flag: Dict[str, Any]) -> bool:
    canonical = _norm_text(flag.get("canonical_id"))
    nutrient = _norm_text(flag.get("nutrient"))
    if canonical not in {"vitamin_b9_folate", "folate"} and "folate" not in nutrient:
        return False
    if _norm_text(flag.get("aggregation")) != "canonical_sum":
        return False

    rows = [row for row in _safe_list(flag.get("contributing_rows")) if isinstance(row, dict)]
    if len(rows) < 2:
        return False

    parent_amount = None
    form_amounts: List[float] = []
    for row in rows:
        name = _norm_text(row.get("ingredient"))
        amount = _as_float(row.get("amount"), None)
        if amount is None or amount <= 0:
            continue
        is_parent_total = name in {"folate", "vitamin b9 folate", "vitamin b9"} or name == nutrient
        is_form = any(
            token in name
            for token in (
                "folic acid",
                "mthf",
                "methyltetrahydrofolate",
                "methylfolate",
                "folinic",
                "folinate",
            )
        )
        if is_parent_total:
            parent_amount = max(parent_amount or 0.0, amount)
        elif is_form:
            form_amounts.append(amount)

    if parent_amount is None or not form_amounts:
        return False
    form_sum = sum(form_amounts)
    if form_sum <= 0:
        return False
    tolerance = max(50.0, parent_amount * 0.10)
    return abs(parent_amount - form_sum) <= tolerance


def _b7_dose_safety(product: Dict[str, Any]) -> tuple[float, List[Dict[str, Any]]]:
    rda_ul = _safe_dict(product.get("rda_ul_data"))
    total = 0.0
    ignored: List[Dict[str, Any]] = []
    for flag in _safe_list(rda_ul.get("safety_flags")):
        if not isinstance(flag, dict):
            continue
        pct_ul = _as_float(flag.get("pct_ul"), 0.0) or 0.0
        if pct_ul < B7_UL_PCT_THRESHOLD:
            continue
        if _is_folate_parent_total_duplicate_flag(flag):
            ignored.append({
                "nutrient": flag.get("nutrient"),
                "canonical_id": flag.get("canonical_id"),
                "pct_ul": flag.get("pct_ul"),
                "reason": "folate_parent_total_plus_form_breakdown_duplicate",
            })
            continue
        total += B7_PER_FLAG_PENALTY
    return _round(_clamp(0.0, B7_CAP, total)), ignored


def _penalty_b7_dose_safety(product: Dict[str, Any]) -> float:
    penalty, _ = _b7_dose_safety(product)
    return penalty


def score_dose(product: Any) -> Dict[str, Any]:
    """Compute the P3.2 multi/prenatal Dose 25 dimension."""
    product = _safe_product(product)

    coverage_scores = _coverage_scores(product)
    rda_ai_coverage = _score_rda_ai_coverage(coverage_scores)
    panel_breadth = _score_panel_breadth(coverage_scores)
    critical_mode, critical_scores, critical_missing = _critical_scores(product, coverage_scores)
    critical_coverage = _score_critical_coverage(critical_scores)
    prenatal_complement_scores = _prenatal_complement_scores(product)
    prenatal_complement_support = _score_prenatal_complement_support(prenatal_complement_scores)
    b7, b7_ignored_flags = _b7_dose_safety(product)

    components = {
        "rda_ai_coverage": rda_ai_coverage,
        "panel_breadth": panel_breadth,
        "critical_nutrient_coverage": critical_coverage,
    }
    if prenatal_complement_support > 0:
        components["prenatal_complement_support"] = prenatal_complement_support
    penalties = {"B7_dose_safety": -b7}

    positive = sum(components.values())
    score = _round(_clamp(0.0, DIMENSION_CAP, positive - b7))

    metadata: Dict[str, Any] = {
        "phase": PHASE_MARKER,
        "method": METHOD_MARKER,
        "coverage_nutrient_count": len(coverage_scores),
        "coverage_nutrient_scores": dict(sorted(coverage_scores.items())),
        "panel_breadth_count": len(coverage_scores),
        "critical_nutrient_mode": critical_mode,
        "critical_nutrient_scores": dict(sorted(critical_scores.items())),
        "critical_nutrients_missing": critical_missing,
        "prenatal_complement_scores": dict(sorted(prenatal_complement_scores.items())),
        "B7_ignored_safety_flags": b7_ignored_flags,
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
