"""v4 Omega Dose dimension — P1.6.2.

Scores omega-3 dose adequacy against the 25-point rubric in
scripts/data/omega_rubric.json:

    epa_dha_band         /20  Purpose-qualified proportional contribution
                              then plateau; no general pediatric target.

The former +5 EPA:DHA ratio bonus was removed in quality_score 1.2.0: no
clinical optimum ratio exists for a generic omega product. Per-serving EPA
and DHA stay in metadata for indication-specific logic.

Per Sean's 'do not invent fields' rule:
- EPA/DHA quantities are summed ONLY when canonical_id ∈ {epa, dha, epa_dha}
  AND quantity > 0 AND unit is a recognized mg/g/mcg variant. Bare
  fish_oil parent mass is NOT included (per §9: '3000 mg fish oil is
  not the same as 3000 mg EPA+DHA').
- Servings-per-day comes from `generic_helpers.daily_serving_range()`, the
  single v4 resolver shared with the sleep/immune/joint/evidence modules. It
  reads the label's canonical serving row (highest quantity, matching the
  enricher's `_select_canonical_serving`) and falls back to `serving_basis`
  only when the label declares no daily servings. When nothing is declared it
  defaults to 1 serving/day (the recorded default — products labeled without
  daily-serving guidance can't be over-credited as multi-serving regimens).

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

import re
from typing import Any, Dict, List, Optional, Tuple

from evidence_resolver import resolve_omega_evidence_standard
from scoring_input_contract import (
    PRENATAL_DHA_TARGET_MG, epa_dha_amounts_per_serving,
    get_source_score_eligible_active_rows, has_source_printed_amount,
    has_unresolved_identity_reason,
)
from scoring_v4.exposure import row_exposure
from scoring_v4.modules.generic_helpers import (
    archetype_dose_reference,
    daily_serving_range,
    dose_reference_scope,
    unbenchmarked_dose_credit,
)


PHASE_MARKER = "P1.6.2_omega_dose"
from scoring_v4.quality_score_config import block as _cfg_block

_DM = _cfg_block("dose_magnitudes", "omega")["omega"]


CAP_DOSE = _DM["cap_dose"]

# Dose V4.1 §3.1: the purpose owner selects the reference; see the rubric's
# dose.adequacy_references. Child/baby products receive the existing neutral.
_CHILD_OR_BABY = "held_child_or_baby_population"
_PRENATAL = "prenatal_dha_intake_authority"
_TRIGLYCERIDE = "explicit_adult_triglyceride_lowering_purpose"


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


def _dose_context(per_day_mg: float, bands: List[Dict[str, Any]]) -> Tuple[str, Optional[str]]:
    """Return a descriptive exposure label and context flag, never points."""
    for band in bands:
        if per_day_mg >= float(band.get("min_mg_day", 0) or 0):
            return str(band.get("label") or ""), band.get("flag")
    return "below_efsa_ai", None


def _prenatal_dha_is_source_printed_zero(product: Dict[str, Any]) -> bool:
    """Every retained DHA owner must prove an exact label zero, not a default."""
    rows = [row for row in get_source_score_eligible_active_rows(product)
            if str(row.get("canonical_id") or "").strip().lower() == "dha"]
    if not rows:
        return False
    for row in rows:
        if (has_unresolved_identity_reason(row)
                or not has_source_printed_amount(row, allow_zero=True)):
            return False
        exposure = row_exposure(product, row, basis="per_use", unit="mg")
        if not exposure.exact or exposure.per_serving_amount != 0:
            return False
    return True


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

    # Band labels and the prescription context flag stay descriptive; the
    # upper endpoint never increases adequacy credit.
    minimum_label, minimum_flag = _dose_context(per_day_min, bands)
    maximum_label, maximum_flag = _dose_context(per_day_max, bands)
    band_label = minimum_label if minimum_label == maximum_label else f"{minimum_label}_to_{maximum_label}"
    band_flag = minimum_flag or maximum_flag
    interval_crosses_band = minimum_label != maximum_label

    # Adequacy at the minimum directed daily use against the purpose's reference.
    standard = resolve_omega_evidence_standard(product)
    purpose = standard.get("applicability_reason")
    references = dose_cfg["adequacy_references"]
    reference: Dict[str, Any]
    prenatal = bool(standard.get("prenatal"))
    if purpose == _CHILD_OR_BABY and not prenatal:
        # A prenatal title can mention a baby ("Baby & Me Prenatal"); it is a
        # maternal product and keeps the prenatal DHA reference below.
        with dose_reference_scope(archetype_dose_reference("omega")):
            band_score = unbenchmarked_dose_credit()
        reference = {"purpose": "child_or_baby", "curve": "completed_no_benchmark_neutral"}
    elif prenatal and dha_ps <= 0 and not _prenatal_dha_is_source_printed_zero(product):
        # Combined EPA+DHA cannot stand in for the undisclosed prenatal DHA.
        with dose_reference_scope(archetype_dose_reference("omega")):
            band_score = unbenchmarked_dose_credit()
        reference = {"purpose": "prenatal_dha", "curve": "unbenchmarked_neutral",
                     "reason": "prenatal_dha_amount_not_disclosed"}
    else:
        if purpose == _PRENATAL or prenatal:
            amount, target, name = dha_ps * min_daily, PRENATAL_DHA_TARGET_MG, "prenatal_dha"
        elif purpose == _TRIGLYCERIDE:
            amount, target, name = per_day_min, references["triglyceride_purpose"]["target_mg_day"], "triglyceride"
        else:
            amount, target, name = per_day_min, references["ordinary_adult"]["target_mg_day"], "ordinary_adult"
        band_score = round(min(band_cap, band_cap * min(amount / float(target), 1.0)), 2)
        reference = {"purpose": name, "curve": "proportional_then_plateau",
                     "target_mg_day": float(target), "amount_mg_day": round(amount, 2)}
    indication_label = reference["purpose"] if reference["purpose"] == "prenatal_dha" else None

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
        "adequacy_reference": reference,
        "omega_purpose": purpose,
        "epa_dha_band_flag": band_flag,
        "interval_crosses_band": interval_crosses_band,
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
