"""v4 Omega Dose dimension — P1.6.2.

Scores omega-3 dose adequacy against the 25-point rubric in
scripts/data/omega_rubric.json:

    epa_dha_band         /20  EPA+DHA mg per day, six bands lifted from
                              scoring_config.section_A_ingredient_quality.
                              omega3_dose_bonus.bands (EFSA/FDA/AHA-grounded
                              thresholds: 250/500/1000/2000/4000 mg/day)
    ratio_sanity         /5   EPA:DHA ratio in healthy 1:3..3:1 range.
                              Exempt for pure-EPA or pure-DHA products
                              (e.g. icosapent ethyl, algal DHA) — ratio
                              doesn't apply.

Per Sean's 'do not invent fields' rule:
- EPA/DHA quantities are summed ONLY when canonical_id ∈ {epa, dha, epa_dha}
  AND quantity > 0 AND unit is a recognized mg/g/mcg variant. Bare
  fish_oil parent mass is NOT included (per §9: '3000 mg fish oil is
  not the same as 3000 mg EPA+DHA').
- Servings-per-day comes from `servingSizes[0].minDailyServings/
  maxDailyServings` (label-asserted). When missing, defaults to 1
  serving/day (the safe baseline — products labeled without daily-
  serving guidance can't be over-credited as multi-serving regimens).

Per §13 architecture lock, this module does not import score_supplements (v3).
The v3 omega3_dose_bonus math is independently reimplemented in policy
terms.

Conservative EPA+DHA handling:
- epa rows sum to epa_per_serving
- dha rows sum to dha_per_serving
- epa_dha combined rows are summed separately. If epa+dha separates are
  present, the combined row is treated as an alternative reporting form
  and NOT additively double-counted (sum max, not both).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[3]
RUBRIC_PATH = REPO_ROOT / "scripts" / "data" / "omega_rubric.json"


PHASE_MARKER = "P1.6.2_omega_dose"
CAP_DOSE = 25.0


# Unit-conversion table — normalized to mg.
_UNIT_TO_MG: Dict[str, float] = {
    "mg": 1.0,
    "milligram": 1.0,
    "milligrams": 1.0,
    "g": 1000.0,
    "gram": 1000.0,
    "grams": 1000.0,
    "gram(s)": 1000.0,
    "mcg": 0.001,
    "ug": 0.001,
    "µg": 0.001,
    "microgram": 0.001,
    "micrograms": 0.001,
    # Unrecognized units (NP, empty, "unspecified", "softgel", etc.) → not convertible.
    # The completeness gate already requires a valid unit; this is a
    # defensive check in case a malformed product reaches dose scoring.
}


_OMEGA_CANONICALS = {"epa", "dha", "epa_dha"}


def _load_rubric() -> Dict[str, Any]:
    """Load omega_rubric.json. Same pattern as omega_formulation — loaded
    fresh per call for testability; cost is negligible."""
    return json.loads(RUBRIC_PATH.read_text())


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _normalize_unit(unit: Any) -> str:
    return str(unit or "").strip().lower()


def _to_mg(quantity: Any, unit: Any) -> Optional[float]:
    """Convert (quantity, unit) → mg. Returns None when the unit is
    unrecognized or quantity is not a positive number."""
    try:
        q = float(quantity)
    except (TypeError, ValueError):
        return None
    if q <= 0:
        return None
    factor = _UNIT_TO_MG.get(_normalize_unit(unit))
    if factor is None:
        return None
    return q * factor


def _ingredient_rows(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    iqd = _safe_dict(product.get("ingredient_quality_data"))
    candidates = (
        _safe_list(iqd.get("ingredients_scorable"))
        or _safe_list(iqd.get("ingredients"))
        or _safe_list(product.get("activeIngredients"))
        or _safe_list(product.get("active_ingredients"))
    )
    return [i for i in candidates if isinstance(i, dict)]


def _sum_epa_dha_per_serving(product: Dict[str, Any]) -> Tuple[float, float, float]:
    """Return (epa_mg_per_serving, dha_mg_per_serving, combined_mg_per_serving).

    Rows with `canonical_id` ∈ {epa, dha, epa_dha} and a recognizable mg
    quantity are included. Rows with unspecified units (the duplicate
    Nordic-style "qty=0 unit=unspecified" rows the enricher sometimes
    emits) are filtered out by _to_mg returning None.
    """
    epa_total = 0.0
    dha_total = 0.0
    combined_total = 0.0
    for ing in _ingredient_rows(product):
        canon = str(ing.get("canonical_id") or "").strip().lower()
        if canon not in _OMEGA_CANONICALS:
            continue
        # Try all the dose field names the enricher emits.
        mg: Optional[float] = None
        for qty_key in ("quantity", "amount", "dose", "dosage"):
            mg = _to_mg(ing.get(qty_key), ing.get("unit") or ing.get("dose_unit"))
            if mg is not None:
                break
        if mg is None:
            continue
        if canon == "epa":
            epa_total += mg
        elif canon == "dha":
            dha_total += mg
        elif canon == "epa_dha":
            combined_total += mg
    return epa_total, dha_total, combined_total


def _extract_daily_servings(product: Dict[str, Any]) -> Tuple[float, float, bool]:
    """Return (min_daily_servings, max_daily_servings, was_defaulted).

    Pulls from servingSizes[0].minDailyServings/maxDailyServings (the
    cleaner's standardized fields). When missing or invalid, defaults
    to (1, 1) — the safe baseline that avoids inflating dose by
    assuming multi-serving regimens.
    """
    sizes = _safe_list(product.get("servingSizes"))
    for entry in sizes:
        if not isinstance(entry, dict):
            continue
        mn = entry.get("minDailyServings") or entry.get("min_daily_servings")
        mx = entry.get("maxDailyServings") or entry.get("max_daily_servings")
        try:
            mn_f = float(mn) if mn is not None else None
            mx_f = float(mx) if mx is not None else None
        except (TypeError, ValueError):
            continue
        if mn_f is None or mn_f <= 0:
            continue
        if mx_f is None or mx_f <= 0:
            mx_f = mn_f
        return mn_f, mx_f, False
    # Fallback paths
    for key in ("servings_per_day_min", "servings_per_day_max"):
        value = product.get(key)
        if value is not None:
            try:
                f = float(value)
                if f > 0:
                    return f, f, False
            except (TypeError, ValueError):
                continue
    return 1.0, 1.0, True


def _band_score(per_day_mg: float, bands: List[Dict[str, Any]]) -> Tuple[float, str, Optional[str]]:
    """Look up the highest band the per-day dose qualifies for.

    Bands in omega_rubric are descending-threshold order
    (4000, 2000, 1000, 500, 250, 0). Return (score, label, flag).
    """
    for band in bands:
        threshold = float(band.get("min_mg_day", 0) or 0)
        if per_day_mg >= threshold:
            return (
                float(band.get("score", 0) or 0),
                str(band.get("label") or ""),
                band.get("flag"),
            )
    return 0.0, "below_efsa_ai", None


def _ratio_sanity_score(
    epa_per_serving: float,
    dha_per_serving: float,
    cfg: Dict[str, Any],
) -> Tuple[float, Dict[str, Any]]:
    """Award +5 when EPA:DHA ratio is in the configured healthy range.

    Pure-EPA or pure-DHA products (one component at 0) are EXEMPT from
    ratio sanity per the rubric — score 0 (not penalized). The user gets
    full credit for the disclosed component via the band; the ratio
    bonus is reserved for products that disclose both.
    """
    exempt = bool(cfg.get("exempt_when_one_zero", True))
    score = float(cfg.get("score", 5) or 5)
    min_ratio = float(cfg.get("min_ratio", 0.333) or 0.333)
    max_ratio = float(cfg.get("max_ratio", 3.0) or 3.0)
    metadata = {
        "min_ratio": min_ratio,
        "max_ratio": max_ratio,
        "exempt_when_one_zero": exempt,
    }

    if epa_per_serving <= 0 or dha_per_serving <= 0:
        metadata["status"] = "exempt_one_component_zero" if exempt else "skipped"
        return 0.0, metadata

    ratio = epa_per_serving / dha_per_serving
    metadata["epa_dha_ratio"] = round(ratio, 4)
    if min_ratio <= ratio <= max_ratio:
        metadata["status"] = "in_range"
        return score, metadata
    metadata["status"] = "out_of_range"
    return 0.0, metadata


def score_dose(product: Any) -> Dict[str, Any]:
    """Score omega-class Dose dimension.

    P1.6.2 implementation. Returns the standard dimension payload shape.
    """
    if not isinstance(product, dict):
        product = {}

    rubric = _load_rubric()
    dose_cfg = rubric["dose"]
    bands = list(dose_cfg["epa_dha_bands"])
    band_cap = float(dose_cfg.get("epa_dha_band_cap", 20) or 20)
    ratio_cfg = _safe_dict(dose_cfg.get("ratio_sanity"))

    epa_ps, dha_ps, combined_ps = _sum_epa_dha_per_serving(product)
    # Avoid additive double-count when both separates AND combined are
    # disclosed — treat combined as an alternative reporting and take the
    # max (the row that disclosed more wins).
    separates_total = epa_ps + dha_ps
    total_per_serving = max(separates_total, combined_ps)

    if total_per_serving <= 0:
        # Completeness gate would normally have blocked this, but be
        # defensive — Dose dimension scores 0 with explanatory metadata.
        return {
            "score": 0.0,
            "max": CAP_DOSE,
            "components": {},
            "penalties": {},
            "metadata": {
                "phase": PHASE_MARKER,
                "epa_mg_per_serving": 0.0,
                "dha_mg_per_serving": 0.0,
                "epa_dha_combined_mg_per_serving": 0.0,
                "per_day_mg": 0.0,
                "reason": "no_disclosed_epa_dha",
            },
        }

    min_daily, max_daily, defaulted = _extract_daily_servings(product)
    per_day_min = total_per_serving * min_daily
    per_day_max = total_per_serving * max_daily
    per_day_mid = (per_day_min + per_day_max) / 2.0

    band_score, band_label, band_flag = _band_score(per_day_mid, bands)
    band_score = min(band_score, band_cap)

    ratio_score, ratio_meta = _ratio_sanity_score(epa_ps, dha_ps, ratio_cfg)

    components: Dict[str, float] = {}
    if band_score > 0:
        components["epa_dha_band"] = band_score
    if ratio_score > 0:
        components["ratio_sanity"] = ratio_score

    raw_score = band_score + ratio_score
    score = max(0.0, min(CAP_DOSE, raw_score))

    metadata: Dict[str, Any] = {
        "phase": PHASE_MARKER,
        "epa_mg_per_serving": round(epa_ps, 2),
        "dha_mg_per_serving": round(dha_ps, 2),
        "epa_dha_combined_mg_per_serving": round(combined_ps, 2),
        "total_epa_dha_per_serving": round(total_per_serving, 2),
        "servings_per_day_min": min_daily,
        "servings_per_day_max": max_daily,
        "servings_defaulted": defaulted,
        "per_day_min_mg": round(per_day_min, 2),
        "per_day_mid_mg": round(per_day_mid, 2),
        "per_day_max_mg": round(per_day_max, 2),
        "epa_dha_band_label": band_label,
        "epa_dha_band_flag": band_flag,
        "ratio_sanity": ratio_meta,
        "raw_score": round(raw_score, 4),
        "cap_applied": raw_score > CAP_DOSE,
    }

    return {
        "score": round(score, 2),
        "max": CAP_DOSE,
        "components": components,
        "penalties": {},
        "metadata": metadata,
    }
