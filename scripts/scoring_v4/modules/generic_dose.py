"""v4 generic-module Dose dimension (P1.3.2a).

Per `docs/plans/SCORING_V4_PROPOSAL.md` §6 generic rubric — Dose 25:

    | Item                                  | Cap | Notes                  |
    |---------------------------------------|----:|------------------------|
    | Dose inside the supplemental window   |  22 | NEW per §6 line 369    |
    | Multi-form complex bonus              |   3 | ≥2 premium forms / nutrient |
    | B7 dose safety penalty (>150% UL)     |  -3 | up to -3               |

The "supplemental window" per §6 line 369 is:

    max(0, RDA - typical_dietary_intake)  ≤  supplemental_dose  ≤  supplemental_UL

True window math requires a per-nutrient `typical_dietary_intake`
reference table (NIH ODS / NHANES) that does NOT exist yet. The spec
itself lists this as an open task (line 1471-1474).

P1.3.2a — THIS slice — implements a SAFE PROXY using only existing
enriched data (`rda_ul_data.adequacy_results[].pct_rda` /
`.pct_ul`). The proxy is honest about what it is: every payload
carries explicit metadata so audit / score-delta / Flutter tooling
never mistakes the proxy band for final NIH/NHANES window math.

Proxy rule (per scorable nutrient with `pct_rda` AND `pct_ul`):

    pct_ul >= 150%             →  0    (B7 handles separately; danger zone)
    100% < pct_ul < 150%       →  11   (overdose territory, half credit)
    pct_rda >= 25%             →  22   (in proxy window)
    0% < pct_rda < 25%         →  (pct_rda / 25) * 22  (sub-clinical, proportional)
    pct_rda == 0%              →  0

The dimension contribution averages the per-nutrient band credit
across nutrients that have RDA reference data. Nutrients without
RDA data (most botanicals) are skipped without zeroing the average.
If NO nutrient has RDA data, the line contributes a 0 component for
audit readability but the Dose dimension score is `None` unless a dose
safety flag is present. That distinction is intentional: "no RDA/UL
benchmark exists" (common for botanicals like KSM-66) is not the same
as "bad dose."

Multi-form bonus: group scorable actives by `standard_name`
(case-insensitive nutrient-family key), count distinct premium forms
(bio_score ≥ 12) per group, +3 when any group has ≥ 2.

B7 penalty: read `rda_ul_data.safety_flags[]`, sum 2.0 per flag with
`pct_ul >= 150%`, cap at 3.0. v3-equivalent.

Per §13 architecture lock, this module does not import from
`score_supplements.py` (v3).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from scoring_v4.modules.botanical_profile import (
    is_botanical_product,
    score_botanical_dose,
)
from scoring_v4.modules.collagen_profile import (
    is_collagen_product,
    score_collagen_dose,
)
from scoring_v4.modules.generic_helpers import (
    bio_score_of,
    get_active_ingredients,
    has_usable_individual_dose,
    is_scorable,
    _as_float,
    _norm_text,
    _safe_dict,
    _safe_list,
)
from scoring_v4.modules.immune_support import score_immune_support_dose
from scoring_v4.modules.joint_support import score_joint_support_dose
from scoring_v4.modules.sleep_support import score_sleep_support_dose


# --- Dose 25 weights ------------------------------------------------------

from scoring_v4.quality_score_config import block as _cfg_block

_DM = _cfg_block("dose_magnitudes", "generic")["generic"]


CAP_SUPPLEMENTAL_WINDOW = _DM["cap_supplemental_window"]
CAP_MULTI_FORM_BONUS = _DM["cap_multi_form_bonus"]
DIMENSION_CAP = _DM["dimension_cap"]

# Proxy band cutoffs.
WINDOW_RDA_THRESHOLD = _DM["window_rda_threshold"]      # pct_rda below this is sub-clinical
WINDOW_UL_PARTIAL_BAND = _DM["window_ul_partial_band"]   # above this and below 150 → half credit
B7_UL_PCT_THRESHOLD = _DM["b7_ul_pct_threshold"]      # at/above this triggers B7 + zeroes window
WINDOW_OVERDOSE_CREDIT = _DM["window_overdose_credit"]    # 100% < pct_ul < 150% credit (half of 22)
NO_REFERENCE_INDIVIDUAL_DOSE_CREDIT = _DM["no_reference_individual_dose_credit"]
NO_REFERENCE_PRODUCT_EVIDENCE_CREDIT = _DM["no_reference_product_evidence_credit"]

# Multi-form bonus thresholds.
MULTI_FORM_PREMIUM_BIO_THRESHOLD = _DM["multi_form_premium_bio_threshold"]
MULTI_FORM_MIN_GROUP_COUNT = _DM["multi_form_min_group_count"]

# B7 penalty.
B7_PER_FLAG_PENALTY = _DM["b7_per_flag_penalty"]
B7_CAP = _DM["b7_cap"]

PHASE_MARKER = "P1.3.2a_dose_proxy"
METHOD_MARKER = "rda_ul_proxy_until_dietary_intake_table"
DEFERRED_DATA = "typical_dietary_intake"


# --- Supplemental-window proxy -------------------------------------------


def _band_credit(pct_rda: Optional[float], pct_ul: Optional[float]) -> Optional[float]:
    """Per-nutrient proxy band credit on the 0-22 scale.

    Returns None when the row lacks BOTH pct_rda and pct_ul (no signal).
    Caller treats None as "skip this row from the average."
    """
    if pct_rda is None and pct_ul is None:
        return None

    # pct_ul takes precedence in the upper bands — pct_ul tells us about
    # toxicity proximity, which is the load-bearing safety signal.
    if pct_ul is not None:
        if pct_ul >= B7_UL_PCT_THRESHOLD:
            return 0.0
        if pct_ul > WINDOW_UL_PARTIAL_BAND:
            return WINDOW_OVERDOSE_CREDIT

    if pct_rda is None:
        # We know we're under UL (or it was None) but have no RDA signal.
        # No safe band assignment; skip from the average.
        return None

    if pct_rda <= 0:
        return 0.0
    if pct_rda >= WINDOW_RDA_THRESHOLD:
        return CAP_SUPPLEMENTAL_WINDOW
    return (pct_rda / WINDOW_RDA_THRESHOLD) * CAP_SUPPLEMENTAL_WINDOW


def _score_supplemental_window_proxy(product: Dict[str, Any]) -> tuple[float, Optional[str]]:
    """Average band credit across nutrients with RDA reference data.

    Returns (credit, reason). When no rows have RDA data, returns
    (0.0, "no_rda_reference_data") so the metadata can carry the
    explanation. The public `score_dose` entry point uses this reason
    to avoid converting non-RDA botanicals into a zero Dose score.
    """
    rda_ul = _safe_dict((product or {}).get("rda_ul_data"))
    adequacy_results = _safe_list(rda_ul.get("adequacy_results"))

    contributions: List[float] = []
    for row in adequacy_results:
        if not isinstance(row, dict):
            continue
        pct_rda = _as_float(row.get("pct_rda"), None)
        pct_ul = _as_float(row.get("pct_ul"), None)
        credit = _band_credit(pct_rda, pct_ul)
        if credit is None:
            continue
        contributions.append(credit)

    if not contributions:
        return 0.0, "no_rda_reference_data"

    avg = sum(contributions) / len(contributions)
    return round(_clamp(0.0, CAP_SUPPLEMENTAL_WINDOW, avg), 4), None


def _score_no_reference_quantified_dose(product: Dict[str, Any]) -> tuple[float, Optional[str]]:
    """Conservative partial dose credit when no RDA/UL table exists.

    Botanicals, amino acids, enzymes, and specialty actives often have real
    label doses but no RDA/UL benchmark. That evidence is clinically usable:
    it should not receive full "inside supplemental window" credit, but it
    also should not make the dose dimension disappear. Cleaner/enricher-owned
    product_scoring_evidence is used for aggregate/blend/activity evidence.
    """
    for ingredient in get_active_ingredients(product):
        if not isinstance(ingredient, dict):
            continue
        if ingredient.get("is_parent_total"):
            continue
        dose_class = _norm_text(ingredient.get("dose_class"))
        quantity = _as_float(ingredient.get("quantity"), None)
        if dose_class == "enzyme_activity" and quantity is not None and quantity > 0:
            return NO_REFERENCE_INDIVIDUAL_DOSE_CREDIT, "enzyme_activity_quantified_dose_no_rda_reference"
        if dose_class == "probiotic_cfu" and quantity is not None and quantity > 0:
            return NO_REFERENCE_INDIVIDUAL_DOSE_CREDIT, "probiotic_cfu_quantified_dose_no_rda_reference"
        if has_usable_individual_dose(ingredient):
            return NO_REFERENCE_INDIVIDUAL_DOSE_CREDIT, "individual_quantified_dose_no_rda_reference"

    for evidence in _safe_list(product.get("product_scoring_evidence")):
        if not isinstance(evidence, dict):
            continue
        if not evidence.get("scoreable"):
            continue
        dose_value = _as_float(evidence.get("dose_value"), None)
        if dose_value is None or dose_value <= 0:
            continue
        dose_class = _norm_text(evidence.get("dose_class"))
        evidence_type = _norm_text(evidence.get("evidence_type"))
        if dose_class in {"therapeutic_mass", "enzyme_activity", "probiotic_cfu"}:
            if evidence_type == "blend_anchor_mass":
                return NO_REFERENCE_PRODUCT_EVIDENCE_CREDIT, "blend_anchor_quantified_dose_no_rda_reference"
            return NO_REFERENCE_INDIVIDUAL_DOSE_CREDIT, "product_evidence_quantified_dose_no_rda_reference"

    return 0.0, None


# --- Multi-form bonus ----------------------------------------------------


def _score_multi_form_bonus(product: Dict[str, Any]) -> float:
    """+3 when any nutrient family has ≥ 2 distinct premium forms.

    Groups scorable actives by `standard_name` (case-insensitive) and
    counts distinct `canonical_id`s with `bio_score >= 12` per group.
    A single 3-pt bonus — no stacking beyond that.
    """
    groups: Dict[str, set[str]] = {}
    for ing in get_active_ingredients(product):
        if not is_scorable(ing):
            continue
        score = bio_score_of(ing)
        if score is None or score < MULTI_FORM_PREMIUM_BIO_THRESHOLD:
            continue
        family = _norm_text(ing.get("standard_name"))
        if not family:
            continue
        canonical = _norm_text(ing.get("canonical_id") or ing.get("name"))
        if not canonical:
            continue
        groups.setdefault(family, set()).add(canonical)

    for forms in groups.values():
        if len(forms) >= MULTI_FORM_MIN_GROUP_COUNT:
            return CAP_MULTI_FORM_BONUS
    return 0.0


# --- B7 dose safety penalty ----------------------------------------------


def _penalty_b7_dose_safety(product: Dict[str, Any]) -> float:
    """Returns a NON-NEGATIVE magnitude — caller subtracts. v3-mirror of
    `_compute_dose_safety_penalty`: 2.0 per safety_flag where pct_ul ≥ 150,
    capped at 3.0."""
    rda_ul = _safe_dict((product or {}).get("rda_ul_data"))
    safety_flags = _safe_list(rda_ul.get("safety_flags"))
    total = 0.0
    for flag in safety_flags:
        if not isinstance(flag, dict):
            continue
        pct_ul = _as_float(flag.get("pct_ul"), 0.0) or 0.0
        if pct_ul >= B7_UL_PCT_THRESHOLD:
            total += B7_PER_FLAG_PENALTY
    return _clamp(0.0, B7_CAP, total)


# --- Public entry point --------------------------------------------------


def score_dose(product: Dict[str, Any]) -> Dict[str, Any]:
    """Compute the generic-module Dose dimension at P1.3.2a (proxy).

    Args:
        product: Enriched product dict. Treated as empty if not a dict.

    Returns:
        Dict with shape:
            {
                "score": <float, clamped to [0, 25]> | None,
                "max": 25.0,
                "components": {
                    "supplemental_window_proxy": <0..22>,
                    "multi_form_bonus": <0 or 3>,
                },
                "penalties": {
                    "B7_dose_safety": <0 or -2 or -3>,
                },
                "phase": "P1.3.2a_dose_proxy",
                "metadata": {
                    "phase": "P1.3.2a_dose_proxy",
                    "method": "rda_ul_proxy_until_dietary_intake_table",
                    "deferred_data_dependency": "typical_dietary_intake",
                    "window_proxy_reason": "no_rda_reference_data" | absent,
                    "window_proxy_status": "not_evaluable_by_rda_proxy" | absent,
                },
            }

    GUARDRAIL: the `metadata` field is the contract — Flutter / audit /
    score-delta tooling MUST check it to know this is a proxy, not final.
    """
    if not isinstance(product, dict):
        product = {}

    # Phase 7 — Collagen Profile: per-subtype clinical dose range (unit-aware) so an
    # underdosed collagen no longer borrows its co-formulated vitamins' RDA dose.
    # Checked before botanical (mass-dominance makes them mutually exclusive).
    if is_collagen_product(product):
        col = score_collagen_dose(product)
        b7 = _penalty_b7_dose_safety(product)
        components = {
            "collagen_clinical_dose": round(float(col["score"]), 4),
            "multi_form_bonus": 0.0,
        }
        penalties = {"B7_dose_safety": round(-b7, 4)}
        score = _clamp(0.0, DIMENSION_CAP, float(col["score"]) - b7)
        return {
            "score": round(score, 4),
            "max": DIMENSION_CAP,
            "components": components,
            "penalties": penalties,
            "phase": PHASE_MARKER,
            "metadata": {
                "phase": PHASE_MARKER,
                "method": "collagen_clinical_dose_v1",
                "collagen_dose_band": col["band"],
                "collagen_dose": col.get("metadata", {}),
            },
        }

    # Phase 6 — Botanical Profile: clinical therapeutic-range dose (via
    # rda_therapeutic_dosing.json) instead of the RDA/UL proxy. Always evaluable
    # (never None), so the dose dimension is no longer excluded for botanicals
    # and the Phase-4 botanical_dose_deferred floor guard is superseded.
    if is_botanical_product(product):
        bot = score_botanical_dose(product)
        b7 = _penalty_b7_dose_safety(product)
        components = {
            "botanical_clinical_dose": round(float(bot["score"]), 4),
            "multi_form_bonus": 0.0,
        }
        penalties = {"B7_dose_safety": round(-b7, 4)}
        score = _clamp(0.0, DIMENSION_CAP, float(bot["score"]) - b7)
        return {
            "score": round(score, 4),
            "max": DIMENSION_CAP,
            "components": components,
            "penalties": penalties,
            "phase": PHASE_MARKER,
            "metadata": {
                "phase": PHASE_MARKER,
                "method": "botanical_clinical_dose_v1",
                "botanical_dose_band": bot["band"],
                "botanical_dose": bot.get("metadata", {}),
            },
        }

    sleep = score_sleep_support_dose(product)
    if sleep is not None:
        b7 = _penalty_b7_dose_safety(product)
        components = {
            "sleep_support_dose": round(float(sleep["score"]), 4),
            "multi_form_bonus": 0.0,
        }
        penalties = {"B7_dose_safety": round(-b7, 4)}
        score = _clamp(0.0, DIMENSION_CAP, float(sleep["score"]) - b7)
        return {
            "score": round(score, 4),
            "max": DIMENSION_CAP,
            "components": components,
            "penalties": penalties,
            "phase": PHASE_MARKER,
            "metadata": {
                "phase": PHASE_MARKER,
                "method": "sleep_support_clinical_dose_v1",
                "sleep_support_dose": sleep,
            },
        }

    immune = score_immune_support_dose(product)
    if immune is not None:
        b7 = _penalty_b7_dose_safety(product)
        components = dict(immune["components"])
        components["multi_form_bonus"] = 0.0
        penalties = {"B7_dose_safety": round(-b7, 4)}
        score = _clamp(0.0, DIMENSION_CAP, float(immune["score"]) - b7)
        return {
            "score": round(score, 4),
            "max": DIMENSION_CAP,
            "components": components,
            "penalties": penalties,
            "phase": PHASE_MARKER,
            "metadata": {
                "phase": PHASE_MARKER,
                "method": "immune_support_daily_dose_v1",
                "immune_support_dose": immune.get("metadata", {}),
            },
        }

    joint = score_joint_support_dose(product)
    if joint is not None:
        b7 = _penalty_b7_dose_safety(product)
        components = {
            "joint_support_dose": round(float(joint["score"]), 4),
            "multi_form_bonus": 0.0,
        }
        penalties = {"B7_dose_safety": round(-b7, 4)}
        score = _clamp(0.0, DIMENSION_CAP, float(joint["score"]) - b7)
        return {
            "score": round(score, 4),
            "max": DIMENSION_CAP,
            "components": components,
            "penalties": penalties,
            "phase": PHASE_MARKER,
            "metadata": {
                "phase": PHASE_MARKER,
                "method": "joint_support_clinical_dose_v1",
                "joint_support_dose": joint,
            },
        }

    window_credit, window_reason = _score_supplemental_window_proxy(product)
    no_reference_credit = 0.0
    no_reference_credit_reason: Optional[str] = None
    if window_reason == "no_rda_reference_data":
        no_reference_credit, no_reference_credit_reason = _score_no_reference_quantified_dose(product)
    multi_form = _score_multi_form_bonus(product)
    b7 = _penalty_b7_dose_safety(product)

    components: Dict[str, float] = {
        "supplemental_window_proxy": round(window_credit or no_reference_credit, 4),
        "multi_form_bonus":          round(multi_form, 4),
    }
    penalties: Dict[str, float] = {
        # Stored as negatives for JSON readability; _sum_penalty_magnitudes
        # takes abs() so sign convention is defense-in-depth.
        "B7_dose_safety":            round(-b7, 4),
    }

    positive = components["supplemental_window_proxy"] + components["multi_form_bonus"]
    penalty_total = _sum_penalty_magnitudes(penalties)
    no_rda_reference = window_reason == "no_rda_reference_data"
    if no_rda_reference and b7 <= 0 and no_reference_credit <= 0:
        # Botanicals / herbal actives can have clinically meaningful mg
        # dosing with no RDA/UL reference. Fail open as "not evaluable by
        # this proxy" rather than treating missing dietary-reference data
        # as a poor dose.
        score: Optional[float] = None
    else:
        score = _clamp(0.0, DIMENSION_CAP, positive - penalty_total)

    metadata: Dict[str, Any] = {
        "phase": PHASE_MARKER,
        "method": METHOD_MARKER,
        "deferred_data_dependency": DEFERRED_DATA,
    }
    if window_reason is not None:
        metadata["window_proxy_reason"] = window_reason
    if no_rda_reference:
        if no_reference_credit > 0:
            metadata["window_proxy_status"] = "partial_credit_without_rda_proxy"
            metadata["partial_credit_reason"] = no_reference_credit_reason
            metadata["partial_credit_value"] = round(no_reference_credit, 4)
        else:
            metadata["window_proxy_status"] = "not_evaluable_by_rda_proxy"

    return {
        "score": round(score, 4) if score is not None else None,
        "max": DIMENSION_CAP,
        "components": components,
        "penalties": penalties,
        "phase": PHASE_MARKER,
        "metadata": metadata,
    }


# --- internals -----------------------------------------------------------


def _clamp(lo: float, hi: float, value: float) -> float:
    return max(lo, min(hi, value))


def _sum_penalty_magnitudes(penalties: Dict[str, float]) -> float:
    return sum(abs(_as_float(v, 0.0) or 0.0) for v in penalties.values())
