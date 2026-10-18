"""Omega Dose: reference contribution per declared serving in production.

The shared serving adapter owns the assessment basis. This owner selects the
existing purpose resolver's ordinary-adult or prenatal reference; held and
explicit triglyceride-purpose contexts retain their separate rubric bands.
Only disclosed EPA/DHA counts; carrier oil never becomes active omega amount.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from scoring_input_contract import epa_dha_amounts_per_serving
from evidence_resolver import resolve_omega_evidence_standard
from scoring_v4.modules.generic_helpers import daily_serving_range


PHASE_MARKER = "P1.6.2_omega_dose"
from scoring_v4.quality_score_config import block as _cfg_block

_DM = _cfg_block("dose_magnitudes", "omega")["omega"]


CAP_DOSE = _DM["cap_dose"]


def _load_rubric() -> Dict[str, Any]:
    """Load omega_rubric.json. Same pattern as omega_formulation — loaded
    fresh per call for testability; cost is negligible."""
    from scoring_v4.config_registry import load_rubric
    return load_rubric("omega")  # Phase 0: shared registry (validated + fingerprinted)


def _extract_daily_servings(product: Dict[str, Any]) -> Tuple[float, float, bool]:
    """Return (min_daily_servings, max_daily_servings, was_defaulted).

    Delegates to the shared v4 resolver so omega, sleep, immune and joint all
    read one daily-serving policy. This used to take `servingSizes[0]`, which
    is the *child* row on a product that declares both a child and an adult
    serving, and it had no sanity bound on the values it accepted.
    """
    return daily_serving_range(product)


def _band_score(per_day_mg: float, bands: List[Dict[str, Any]]) -> Tuple[float, str, Optional[str]]:
    """Score EPA+DHA per day against the rubric bands. Return (score, label, flag).

    The reviewed band values are anchors, not steps: between two anchors the
    score follows a straight line, so 999 mg and 1000 mg differ by a hair
    instead of 6 points. No band value moves — 250 still scores 5, 1000 still
    scores 16, 2000 and above still score 20. The label and context flag come
    from the band the amount actually falls in, exactly as before.

    Bands in omega_rubric are in descending-threshold order
    (4000, 2000, 1000, 500, 250, 200, 100, 0).
    """
    label, flag = "below_efsa_ai", None
    for band in bands:
        if per_day_mg >= float(band.get("min_mg_day", 0) or 0):
            label = str(band.get("label") or "")
            flag = band.get("flag")
            break
    if per_day_mg <= 0:
        return 0.0, "below_efsa_ai", None

    anchors = sorted(
        (float(band.get("min_mg_day", 0) or 0), float(band.get("score", 0) or 0))
        for band in bands
    )
    if not anchors:
        return 0.0, label, flag
    # Below the lowest scoring anchor the rubric is a floor, not a ramp: a trace
    # omega gummy earns nothing, which is the reviewed policy for <100 mg/day.
    lowest_scoring = next((mg for mg, score in anchors if score > 0), None)
    if lowest_scoring is not None and per_day_mg < lowest_scoring:
        return 0.0, label, flag
    if per_day_mg >= anchors[-1][0]:
        return anchors[-1][1], label, flag
    for (low_mg, low_score), (high_mg, high_score) in zip(anchors, anchors[1:]):
        if per_day_mg <= high_mg:
            span = high_mg - low_mg
            if span <= 0:
                return high_score, label, flag
            value = low_score + (high_score - low_score) * (per_day_mg - low_mg) / span
            return round(value, 2), label, flag
    return anchors[-1][1], label, flag


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

    epa_ps, dha_ps, combined_ps = epa_dha_amounts_per_serving(product)
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

    # Adequacy uses the minimum directed daily exposure (shared with
    # Evidence and RDA adequacy). Keep the upper endpoint for interval
    # explanation and safety; it cannot increase adequacy credit.
    minimum_score, minimum_label, minimum_flag = _band_score(per_day_min, bands)
    maximum_score, maximum_label, maximum_flag = _band_score(per_day_max, bands)
    band_score = min(minimum_score, band_cap)
    band_label = minimum_label if minimum_label == maximum_label else f"{minimum_label}_to_{maximum_label}"
    band_flag = minimum_flag or maximum_flag
    interval_crosses_band = minimum_label != maximum_label

    # Purpose/population selection is shared with Evidence, never inferred here
    # from an independent title regex or from Evidence points.
    purpose = resolve_omega_evidence_standard(product)
    context = purpose["applicability_reason"]
    indication_label: Optional[str] = None
    # Prenatal amount comparison and clinical Evidence applicability are
    # separate policies. An Evidence hold cannot make EPA substitute for DHA.
    prenatal_context = purpose["prenatal"]
    reference = None
    if prenatal_context:
        reference = float(_DM["prenatal_dha_reference_mg"])
        amount_min, amount_max = dha_ps * min_daily, dha_ps * max_daily
        indication_label = "prenatal_dha_within_target" if amount_min >= reference else "prenatal_dha_below_target"
        band_label = indication_label
    elif context == "ordinary_adult_explicit_epa_dha":
        reference = float(_DM["adult_nutritional_reference_mg"])
        amount_min, amount_max = per_day_min, per_day_max
        band_label = "adult_nutritional_reference_met" if amount_min >= reference else "adult_nutritional_reference_partial"
    if reference is not None:
        cap = float(_DM["reference_contribution_cap"])
        minimum_score = round(cap * min(max(amount_min, 0.0) / reference, 1.0), 2)
        maximum_score = round(cap * min(max(amount_max, 0.0) / reference, 1.0), 2)
        band_score = minimum_score
        interval_crosses_band = amount_min < reference <= amount_max

    components: Dict[str, float] = {}
    if band_score > 0:
        components["epa_dha_band"] = band_score

    raw_score = band_score
    score = max(0.0, min(CAP_DOSE, raw_score))

    metadata: Dict[str, Any] = {
        "phase": PHASE_MARKER,
        "prenatal_dha_indication": indication_label,
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
        "interval_crosses_band": interval_crosses_band,
        "minimum_band_score": round(minimum_score, 2),
        "maximum_band_score": round(maximum_score, 2),
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
