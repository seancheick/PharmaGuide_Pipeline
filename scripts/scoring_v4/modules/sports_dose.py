"""v4 sports-module Dose dimension.

Sports actives are evaluated against exercise-nutrition dose bands rather
than the generic RDA/UL proxy used for vitamins and minerals.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from scoring_v4.modules.generic_helpers import _norm_text, _safe_list
from scoring_v4.modules.sports_helpers import (
    BETA_ALANINE_CANONICALS,
    CITRULLINE_CANONICALS,
    CREATINE_CANONICALS,
    SPORTS_PROTEIN_CANONICALS,
    canonical,
    dose_g,
    group_bcaa,
    group_eaa,
    sports_rows,
)


PHASE_MARKER = "P1.7_sports_dose_v1"
METHOD_MARKER = "sports_active_dose_bands_v1"
DIMENSION_CAP = 25.0


def score_dose(product: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(product, dict):
        product = {}

    identity, primary, basis = _best_primary_score(product)
    support = _score_stack_support(product, identity)
    completeness = _score_ratio_or_completeness(product, identity)
    opaque_penalty, not_evaluable = _opaque_penalty(product, primary)

    components = {
        "sports_primary_active_dose": round(primary, 4),
        "sports_stack_support": round(support, 4),
        "sports_ratio_or_completeness": round(completeness, 4),
    }
    penalties = {
        "opaque_primary_sports_blend": round(-opaque_penalty, 4),
        "stimulant_high_caffeine": 0.0,
    }
    score = _clamp(
        0.0,
        DIMENSION_CAP,
        sum(components.values()) - sum(abs(float(v)) for v in penalties.values()),
    )
    metadata: Dict[str, Any] = {
        "phase": PHASE_MARKER,
        "method": METHOD_MARKER,
        "primary_identity": identity,
        "dose_basis": basis,
    }
    if not_evaluable:
        metadata["not_evaluable_reason"] = not_evaluable

    return {
        "score": round(score, 4),
        "max": DIMENSION_CAP,
        "components": components,
        "penalties": penalties,
        "phase": PHASE_MARKER,
        "metadata": metadata,
    }


def _score_primary(product: Dict[str, Any], identity: Optional[str]) -> Tuple[float, Optional[str]]:
    rows = sports_rows(product)
    if identity == "protein":
        grams = _max_g(rows, SPORTS_PROTEIN_CANONICALS)
        if grams is None:
            return 0.0, "protein_no_dose"
        if grams < 15:
            return 8.0, "protein_under_15_g"
        if grams < 20:
            return 16.0, "protein_15_to_20_g"
        if grams <= 40:
            return 20.0, "protein_20_to_40_g"
        return 16.0, "protein_above_40_g"

    if identity == "creatine":
        grams = _max_g(rows, CREATINE_CANONICALS)
        if grams is None:
            return 0.0, "creatine_no_dose"
        if grams < 3:
            return 8.0, "creatine_under_3_g"
        if grams < 5:
            return 16.0, "creatine_3_to_5_g"
        return 20.0, "creatine_at_least_5_g"

    if identity == "beta_alanine":
        grams = _max_g(rows, BETA_ALANINE_CANONICALS)
        if grams is None:
            return 0.0, "beta_alanine_no_dose"
        if grams < 2:
            return 8.0, "beta_alanine_under_2_g"
        if grams < 4:
            return 16.0, "beta_alanine_2_to_4_g"
        if grams <= 6:
            return 20.0, "beta_alanine_4_to_6_g"
        return 16.0, "beta_alanine_above_6_g"

    if identity == "citrulline":
        row = _first_row(rows, CITRULLINE_CANONICALS)
        grams = dose_g(row or {})
        if grams is None:
            return 0.0, "citrulline_no_dose"
        label = _norm_text((row or {}).get("name") or (row or {}).get("matched_form"))
        malate = "malate" in label
        if malate:
            if grams < 6:
                return _partial(grams, 6.0, 14.0), "citrulline_malate_under_6_g"
            if grams < 8:
                return 14.0, "citrulline_malate_6_to_8_g"
            return 18.0, "citrulline_malate_8_to_12_g"
        if grams < 3:
            return _partial(grams, 3.0, 16.0), "l_citrulline_under_3_g"
        if grams < 6:
            return 16.0, "l_citrulline_3_to_6_g"
        return 18.0, "l_citrulline_6_to_8_g"

    if identity == "bcaa":
        grouped = group_bcaa(rows)
        if not grouped["complete"]:
            return 0.0, "bcaa_incomplete"
        total = float(grouped["total_g"])
        if total < 3:
            return _partial(total, 3.0, 12.0), "bcaa_under_3_g"
        if total < 5:
            return 12.0, "bcaa_3_to_5_g"
        if _bcaa_ratio_is_close(grouped.get("ratio")):
            return 18.0, "bcaa_at_least_5_g_ratio_complete"
        return 14.0, "bcaa_at_least_5_g_ratio_incomplete"

    if identity == "eaa":
        grouped = group_eaa(rows)
        total = float(grouped["total_g"])
        if total < 5:
            return _partial(total, 5.0, 12.0), "eaa_under_5_g"
        if total < 8:
            return 12.0, "eaa_5_to_8_g"
        return 18.0, "eaa_at_least_8_g"

    return 0.0, "no_sports_primary_dose"


def _best_primary_score(product: Dict[str, Any]) -> Tuple[Optional[str], float, Optional[str]]:
    """Pick the dose-supported primary anchor with the highest credit.

    A fixed canonical priority is unsafe for pre-workouts: tiny accessory
    rows can coexist with therapeutic-dose beta-alanine/citrulline/BCAA.
    """
    best_identity: Optional[str] = None
    best_score = 0.0
    best_basis: Optional[str] = "no_sports_primary_dose"
    for identity in ("protein", "creatine", "bcaa", "eaa", "beta_alanine", "citrulline"):
        score, basis = _score_primary(product, identity)
        if score > best_score:
            best_identity = identity
            best_score = score
            best_basis = basis
    return best_identity, best_score, best_basis


def _score_stack_support(product: Dict[str, Any], identity: Optional[str]) -> float:
    if not identity:
        return 0.0
    rows = sports_rows(product)
    support_groups = 0
    canons = {canonical(row) for row in rows}
    if identity != "creatine" and canons & CREATINE_CANONICALS:
        support_groups += 1
    if identity != "beta_alanine" and canons & BETA_ALANINE_CANONICALS:
        support_groups += 1
    if identity != "citrulline" and canons & CITRULLINE_CANONICALS:
        support_groups += 1
    return min(3.0, float(support_groups))


def _score_ratio_or_completeness(product: Dict[str, Any], identity: Optional[str]) -> float:
    rows = sports_rows(product)
    if identity == "bcaa" and _bcaa_ratio_is_close(group_bcaa(rows).get("ratio")):
        return 2.0
    if identity == "eaa" and group_eaa(rows)["complete"]:
        return 2.0
    return 0.0


def _opaque_penalty(product: Dict[str, Any], primary_score: float) -> Tuple[float, Optional[str]]:
    if primary_score > 0:
        return 0.0, None
    blends = [b for b in _safe_list((product or {}).get("proprietary_blends")) if isinstance(b, dict)]
    if not blends:
        return 0.0, "no_sports_primary_dose"
    for blend in blends:
        if _norm_text(blend.get("disclosure_level")) in {"none", "partial", ""}:
            return 10.0, "opaque_primary_sports_blend"
    return 0.0, "no_sports_primary_dose"


def _max_g(rows: list[Dict[str, Any]], canonicals: frozenset[str]) -> Optional[float]:
    values = [dose_g(row) for row in rows if canonical(row) in canonicals]
    values = [value for value in values if value is not None]
    return max(values) if values else None


def _first_row(rows: list[Dict[str, Any]], canonicals: frozenset[str]) -> Optional[Dict[str, Any]]:
    for row in rows:
        if canonical(row) in canonicals:
            return row
    return None


def _partial(value: float, target: float, max_points: float) -> float:
    if target <= 0:
        return 0.0
    return _clamp(0.0, max_points, (value / target) * max_points)


def _bcaa_ratio_is_close(ratio: Any) -> bool:
    if not ratio or len(ratio) != 3:
        return False
    leucine, iso, val = ratio
    return 1.7 <= float(leucine) <= 2.3 and 0.8 <= float(iso) <= 1.2 and 0.8 <= float(val) <= 1.2


def _clamp(lo: float, hi: float, value: float) -> float:
    return max(lo, min(hi, value))
