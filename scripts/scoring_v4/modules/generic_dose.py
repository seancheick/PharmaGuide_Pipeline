"""v4 generic-module Dose dimension (P1.3.2a).

Per `docs/plans/SCORING_V4_PROPOSAL.md` §6 generic rubric — Dose 25:

    | Item                                  | Cap | Notes                  |
    |---------------------------------------|----:|------------------------|
    | Dose inside the supplemental window   |  22 | NEW per §6 line 369    |
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

Below the UL, credit depends on what the reference is (quality_score 1.4.0):

    official DRI vitamin / trace mineral (RDA or AI):
        pct_rda >= 100%        →  22   (meets the requirement)
        20% <= pct_rda < 100%  →  11 → 22 linear (20% = FDA "high/excellent
                                   source", 21 CFR 101.54(b))
        pct_rda < 20%          →  (pct_rda / 20) * 11
    verified clinical anchor (no DRI; the reference is the lowest clinically
    effective daily dose, content-verified against PubMed 2026-09-15 in
    scripts/audits/clinical_anchor_verification_2026_09_15):
        pct_rda >= 100%        →  22
        pct_rda < 100%         →  (pct_rda / 100) * 22
    macrominerals and every other reference, including anchors the review
    could not establish (unchanged until a dietary intake table exists):
        pct_rda >= 25%         →  22
        0% < pct_rda < 25%     →  (pct_rda / 25) * 22

The dimension contribution averages the per-nutrient band credit
across nutrients that have RDA reference data. Nutrients without
RDA data (most botanicals) are skipped without zeroing the average.
If NO nutrient has RDA data, the line contributes a 0 component for
audit readability but the Dose dimension score is `None` unless a dose
safety flag is present. That distinction is intentional: "no RDA/UL
benchmark exists" (common for botanicals like KSM-66) is not the same
as "bad dose."

Form quality is not a Dose input. IQM forms[].bio_score is its one owner
(matrix concept `ingredient_form_quality`), read by Formulation; the former
+3 for >= 2 premium forms of one nutrient was retired in quality_score
1.14.0: a count of forms is neither an amount nor a reference.

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
    get_active_ingredients,
    has_usable_individual_dose,
    _as_float,
    _norm_text,
    _safe_dict,
    _safe_list,
)
from scoring_input_contract import mass_primary_label_actives, source_linked_rows
from scoring_v4.dose_safety import resolve_dose_safety
from scoring_v4.modules.immune_support import score_immune_support_dose
from scoring_v4.modules.joint_support import score_joint_support_dose
from scoring_v4.modules.sleep_support import score_sleep_support_dose


# --- Dose 25 weights ------------------------------------------------------

from scoring_v4.quality_score_config import block as _cfg_block

_DM = _cfg_block("dose_magnitudes", "generic")["generic"]
_B7 = _cfg_block("dose_safety_policy", "ul_pct_threshold")


CAP_SUPPLEMENTAL_WINDOW = _DM["cap_supplemental_window"]
DIMENSION_CAP = _DM["dimension_cap"]

# Proxy band cutoffs.
WINDOW_RDA_THRESHOLD = _DM["window_rda_threshold"]      # pct_rda below this is sub-clinical
WINDOW_UL_PARTIAL_BAND = _DM["window_ul_partial_band"]   # above this and below 150 → half credit
B7_UL_PCT_THRESHOLD = _B7["ul_pct_threshold"]      # at/above this triggers B7 + zeroes window
WINDOW_OVERDOSE_CREDIT = _DM["window_overdose_credit"]    # 100% < pct_ul < 150% credit (half of 22)
WINDOW_HIGH_SOURCE_PCT = _DM["window_high_source_pct"]    # 21 CFR 101.54(b) "high source"
WINDOW_FULL_ADEQUACY_PCT = _DM["window_full_adequacy_pct"]
NO_REFERENCE_INDIVIDUAL_DOSE_CREDIT = _DM["no_reference_individual_dose_credit"]
NO_REFERENCE_PRODUCT_EVIDENCE_CREDIT = _DM["no_reference_product_evidence_credit"]

# B7 penalty.
B7_PER_FLAG_PENALTY = _B7["per_flag_penalty"]
B7_CAP = _B7["cap"]

PHASE_MARKER = "P1.3.2a_dose_proxy"
METHOD_MARKER = "rda_ul_proxy_until_dietary_intake_table"
DEFERRED_DATA = "typical_dietary_intake"

# These nutrients are supplied mainly by food, while ordinary standalone
# supplements intentionally provide only a small fraction of the dietary AI.
# Comparing a normal label dose directly with the full dietary target makes a
# market-standard product look defective. Keep the RDA/AI in nutrient tracking;
# only the generic product-quality proxy excludes it.
_DIETARY_INTAKE_DOMINANT_CANONICALS = frozenset({"potassium"})

# Which kind of reference an adequacy row's percentage is measured against,
# keyed by the row canonical_id -> rda_optimal_uls.json reference id. Official
# DRI vitamins and trace minerals are judged against the requirement itself.
_DRI_REFERENCE_BY_CANONICAL = {
    "vitamin_a": "vitamin_a", "beta_carotene": "vitamin_a", "alpha_carotene": "vitamin_a",
    "cryptoxanthin": "vitamin_a", "vitamin_c": "vitamin_c", "vitamin_d": "vitamin_d",
    "vitamin_e": "vitamin_e", "vitamin_k": "vitamin_k", "vitamin_k1": "vitamin_k",
    "vitamin_k2": "vitamin_k", "vitamin_b1_thiamine": "thiamin", "vitamin_b2_riboflavin": "riboflavin",
    "vitamin_b3_niacin": "niacin", "vitamin_b5_pantothenic": "pantothenic_acid",
    "vitamin_b6_pyridoxine": "vitamin_b6", "vitamin_b7_biotin": "biotin",
    "vitamin_b9_folate": "folate", "vitamin_b12_cobalamin": "vitamin_b12", "choline": "choline",
    "chromium": "chromium", "copper": "copper", "fluoride": "fluoride", "iodine": "iodine",
    "iron": "iron", "manganese": "manganese", "molybdenum": "molybdenum",
    "selenium": "selenium", "zinc": "zinc",
}

# No official DRI: the reference is the lowest clinically effective daily dose.
# Alias-to-reference routing is owned by the production config, while the
# clinical-anchor audit ledger supplies the evidence and eligibility review.
# Keeping the map in config prevents a silent second scoring vocabulary here.
_CLINICAL_ANCHOR_REFERENCE_BY_CANONICAL = _DM["_clinical_anchor_reference_by_canonical"]


def _adequacy_reference_kind(canonical: object) -> str:
    key = _norm_text(canonical)
    if key in _DRI_REFERENCE_BY_CANONICAL:
        return "dri"
    if key in _CLINICAL_ANCHOR_REFERENCE_BY_CANONICAL:
        return "clinical_anchor"
    return "legacy"


# --- Supplemental-window proxy -------------------------------------------


def _band_credit(
    pct_rda: Optional[float],
    pct_ul: Optional[float],
    canonical: object = None,
) -> Optional[float]:
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
    kind = _adequacy_reference_kind(canonical)
    if pct_rda >= (WINDOW_RDA_THRESHOLD if kind == "legacy" else WINDOW_FULL_ADEQUACY_PCT):
        return CAP_SUPPLEMENTAL_WINDOW
    if kind == "dri":
        half = CAP_SUPPLEMENTAL_WINDOW / 2.0
        if pct_rda >= WINDOW_HIGH_SOURCE_PCT:
            span = WINDOW_FULL_ADEQUACY_PCT - WINDOW_HIGH_SOURCE_PCT
            return half + half * (pct_rda - WINDOW_HIGH_SOURCE_PCT) / span
        return half * pct_rda / WINDOW_HIGH_SOURCE_PCT
    if kind == "clinical_anchor":
        return CAP_SUPPLEMENTAL_WINDOW * pct_rda / WINDOW_FULL_ADEQUACY_PCT
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
    dietary_reference_exclusions = 0
    for row in adequacy_results:
        if not isinstance(row, dict):
            continue
        canonical = _norm_text(row.get("canonical_id"))
        nutrient = _norm_text(row.get("nutrient"))
        if canonical in _DIETARY_INTAKE_DOMINANT_CANONICALS or nutrient in _DIETARY_INTAKE_DOMINANT_CANONICALS:
            dietary_reference_exclusions += 1
            continue
        pct_rda = _as_float(row.get("pct_rda"), None)
        pct_ul = _as_float(row.get("pct_ul"), None)
        credit = _band_credit(pct_rda, pct_ul, row.get("canonical_id"))
        if credit is None:
            continue
        contributions.append(credit)

    if not contributions:
        if dietary_reference_exclusions:
            return 0.0, "dietary_intake_dominant_reference_excluded"
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


def _mass_primary_without_reference(product: Dict[str, Any]) -> Optional[str]:
    """Identity of a mass-primary label active that has no usable assessment.

    The scoring contract decides which rows are the primaries (shared source
    ownership, no opaque totals, no unmapped identities, every row tied at the
    top mass). An adequacy row counts as an assessment only when the window
    proxy could band it (`_band_credit` is not None): a row with no reference
    percentage assesses nothing. When several primaries lack an assessment the
    first by identity is named, so the decision is the same for any label
    order.
    """
    assessed: set[str] = set()
    for row in _safe_list(_safe_dict((product or {}).get("rda_ul_data")).get("adequacy_results")):
        if not isinstance(row, dict):
            continue
        if _band_credit(_as_float(row.get("pct_rda"), None), _as_float(row.get("pct_ul"), None), row.get("canonical_id")) is None:
            continue
        assessed.update(
            _norm_text(row.get(key)) for key in ("canonical_id", "nutrient") if row.get(key)
        )
    active_rows = get_active_ingredients(product)
    for primary in mass_primary_label_actives(product, active_rows):
        # An assessment is source-linked: it may sit on the primary itself, on
        # a projection of the same label row, or on a constituent the row
        # declares (ALA under flaxseed oil). The contract owns that lineage.
        identities = {
            _norm_text(linked_row.get(key))
            for linked_row in (primary, *source_linked_rows(product, primary, active_rows))
            for key in ("canonical_id", "standard_name", "name", "nutrient")
            if linked_row.get(key)
        }
        if identities and not (identities & assessed):
            return _norm_text(primary.get("canonical_id") or primary.get("standard_name") or primary.get("name"))
    return None


# --- B7 dose safety penalty ----------------------------------------------


def _select_window_component(
    *,
    window_credit: float,
    no_reference_credit: float,
    no_rda_reference: bool,
) -> float:
    """Choose the dose-window signal that actually applies.

    The fallback credit answers "a dose is disclosed but no reference range
    exists". It applies when there is no reference — never merely because the
    evaluated window came out at zero. An evaluated 0.0 means every nutrient hit
    at least 150% of its upper limit, or contributed no adequacy at all; that is
    a finding, not a missing value.
    """
    return no_reference_credit if no_rda_reference else window_credit


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
    b7_evaluation = resolve_dose_safety(
        product,
        threshold=B7_UL_PCT_THRESHOLD,
        per_flag_penalty=B7_PER_FLAG_PENALTY,
        cap=B7_CAP,
    )
    b7 = b7_evaluation.penalty
    b7_metadata = b7_evaluation.audit_metadata()

    # Phase 7 — Collagen Profile: per-subtype clinical dose range (unit-aware) so an
    # underdosed collagen no longer borrows its co-formulated vitamins' RDA dose.
    # Checked before botanical (mass-dominance makes them mutually exclusive).
    if is_collagen_product(product):
        col = score_collagen_dose(product)
        components = {
            "collagen_clinical_dose": round(float(col["score"]), 4),
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
                "B7_safety_evaluation": b7_metadata,
            },
        }

    # Phase 6 — Botanical Profile: clinical therapeutic-range dose (via
    # rda_therapeutic_dosing.json) instead of the RDA/UL proxy. Always evaluable
    # (never None), so the dose dimension is no longer excluded for botanicals
    # and the Phase-4 botanical_dose_deferred floor guard is superseded.
    if is_botanical_product(product):
        bot = score_botanical_dose(product)
        components = {
            "botanical_clinical_dose": round(float(bot["score"]), 4),
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
                "B7_safety_evaluation": b7_metadata,
            },
        }

    sleep = score_sleep_support_dose(product)
    if sleep is not None:
        components = {
            "sleep_support_dose": round(float(sleep["score"]), 4),
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
                "B7_safety_evaluation": b7_metadata,
            },
        }

    immune = score_immune_support_dose(product)
    if immune is not None:
        components = dict(immune["components"])
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
                "B7_safety_evaluation": b7_metadata,
            },
        }

    joint = score_joint_support_dose(product)
    if joint is not None:
        components = {
            "joint_support_dose": round(float(joint["score"]), 4),
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
                "B7_safety_evaluation": b7_metadata,
            },
        }

    window_credit, window_reason = _score_supplemental_window_proxy(product)
    no_rda_reference = window_reason in {
        "no_rda_reference_data",
        "dietary_intake_dominant_reference_excluded",
    }
    no_reference_credit = 0.0
    no_reference_credit_reason: Optional[str] = None
    if no_rda_reference:
        no_reference_credit, no_reference_credit_reason = _score_no_reference_quantified_dose(product)
    unassessed_primary: Optional[str] = None
    if not no_rda_reference:
        unassessed_primary = _mass_primary_without_reference(product)
        if unassessed_primary and window_credit > NO_REFERENCE_INDIVIDUAL_DOSE_CREDIT:
            # The assessed nutrients' window average must not present a
            # complete product-dose assessment while the mass-primary active
            # has no reference at all; it can earn no more than the existing
            # partial credit for a disclosed dose without a reference.
            window_credit = NO_REFERENCE_INDIVIDUAL_DOSE_CREDIT

    components: Dict[str, float] = {
        "supplemental_window_proxy": round(
            _select_window_component(
                window_credit=window_credit,
                no_reference_credit=no_reference_credit,
                no_rda_reference=no_rda_reference,
            ),
            4,
        ),
    }
    penalties: Dict[str, float] = {
        # Stored as negatives for JSON readability; _sum_penalty_magnitudes
        # takes abs() so sign convention is defense-in-depth.
        "B7_dose_safety":            round(-b7, 4),
    }

    positive = components["supplemental_window_proxy"]
    penalty_total = _sum_penalty_magnitudes(penalties)
    no_rda_reference = window_reason in {
        "no_rda_reference_data",
        "dietary_intake_dominant_reference_excluded",
    }
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
        "B7_safety_evaluation": b7_metadata,
    }
    if window_reason is not None:
        metadata["window_proxy_reason"] = window_reason
    if unassessed_primary:
        metadata["primary_active_unassessed"] = unassessed_primary
        if components["supplemental_window_proxy"] <= NO_REFERENCE_INDIVIDUAL_DOSE_CREDIT:
            metadata["window_proxy_status"] = "partial_credit_primary_active_unassessed"
            metadata["partial_credit_value"] = round(components["supplemental_window_proxy"], 4)
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
