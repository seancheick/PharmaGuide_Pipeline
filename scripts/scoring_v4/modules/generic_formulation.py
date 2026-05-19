"""v4 generic-module Formulation dimension (P1.3.1).

Per `docs/plans/SCORING_V4_PROPOSAL.md` §6 generic rubric — Formulation 30:

    | Item                                  | Cap | v3 source                |
    |---------------------------------------|----:|--------------------------|
    | Form-specific bioavailability         |  15 | A1 bio_score             |
    | Premium forms (beyond primary)        |   4 | A2 premium_forms         |
    | Delivery system                       |   3 | A3 delivery_system       |
    | Absorption enhancer pairing           |   3 | A4 absorption_enhancer   |
    | Formulation excellence rollup         |   4 | A5 organic + std + synergy + non-GMO + natural |
    | Single-ingredient efficiency          |   1 | A6 single_ingredient     |
    | Enzyme recognition (single-ing only)  |   2 | enzyme_recognition       |
    |                                       |     |                          |
    | B0 immediate_fail (moderate/watchlist)| -10 | safety_signals           |
    | B1 harmful_additives                  | -15 | contaminant_data         |
    | B1 dietary_sugar                      |-1.5 | dietary_sensitivity_data |

Final: clamp(0, 30, sum(components) − sum(|penalties|)).

P1.3.1a — THIS slice — implements the 8 "simple" sub-rubrics that are
mostly direct field reads:

    A1 bio_score, A2 premium forms, A3 delivery, A4 absorption,
    A5a organic, A5e natural source, A6 single-ingredient,
    B1 dietary sugar.

P1.3.1b — NEXT slice — implements the 6 "complex" sub-rubrics that
need additional reverse-engineering:

    A5b standardized botanical, A5c synergy 4-tier, A5d non-GMO,
    enzyme recognition, B0 moderate/watchlist, B1 harmful additives.

Until P1.3.1b lands, the 6 stubs return 0.0 and explicit metadata lists
which component/penalty lines are deferred. The dimension score is the
sum of the 8 partial components minus the dietary-sugar penalty, clamped
to [0, 30]. Audit / score-delta tooling sees the phase marker and knows
the score is not final.

Per §13 architecture lock, this module does not import from
`score_supplements.py` (v3). The numeric rules below mirror v3's
A1-A6/B1 logic by re-implementation, not by import.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from scoring_v4.modules.generic_helpers import (
    bio_score_of,
    canonical_key,
    get_active_ingredients,
    is_scorable,
    scorable_ingredients,
    supp_type_of,
    _as_float,
    _norm_text,
    _safe_dict,
    _safe_list,
)


# --- v4 generic Formulation weights ---------------------------------------
# Mirror v3 with the §6 rescaling: bio_score cap 18→15, single-ingredient
# 3→1, A5 rollup cap 4 preserved.

CAP_BIO_SCORE = 15.0
CAP_PREMIUM_FORMS = 4.0
CAP_DELIVERY = 3.0
CAP_ABSORPTION = 3.0
CAP_EXCELLENCE = 4.0       # A5 rollup
CAP_SINGLE_INGREDIENT = 1.0
CAP_ENZYME = 2.0
DIMENSION_CAP = 30.0

PREMIUM_FORM_THRESHOLD = 12.0           # v3.6.0 A2 threshold on bio_score scale
PREMIUM_FORM_POINTS_PER_ADDITIONAL = 0.5
PREMIUM_FORM_SKIP_FIRST = True

DELIVERY_TIER_POINTS = {1: 3.0, 2: 2.0, 3: 1.0}

SINGLE_INGREDIENT_SUPP_TYPES = frozenset({"single", "single_nutrient"})
SINGLE_INGREDIENT_BIO_THRESHOLD = 14.0   # v4 single-ingredient bonus needs bio_score ≥14

# A5 rollup sub-credits (sum can exceed CAP_EXCELLENCE; we clamp at the end).
A5A_ORGANIC = 1.0
A5E_NATURAL = 1.0

# B1 dietary-sugar penalty bands (mirrors scoring_config.B1_dietary_sugar_penalty).
DIETARY_SUGAR_MODERATE_PENALTY = 0.5
DIETARY_SUGAR_HIGH_PENALTY = 1.5
DIETARY_SUGAR_CAP = 1.5

PHASE_MARKER_PARTIAL = "P1.3.1a_partial"

# Stub components — populated by P1.3.1b. Listed here so audit tooling can
# distinguish "deliberately deferred to P1.3.1b" from "field absent in blob".
DEFERRED_TO_P131B_COMPONENTS = (
    "A5b_standardized_botanical",
    "A5c_synergy_cluster",
    "A5d_non_gmo",
    "enzyme_recognition",
)
DEFERRED_TO_P131B_PENALTIES = (
    "B0_moderate_watchlist",
    "B1_harmful_additives",
)


# --- A1 bio_score ---------------------------------------------------------


def _score_bio_score(product: Dict[str, Any]) -> float:
    """Average bio_score across scorable active ingredients. Already on
    the 0-15 scale, so the dimension contribution = avg directly (no
    rescale, vs v3 where avg/15 * 18). Returns 0 when no scorable ings."""
    scorable = scorable_ingredients(product, allow_sole_mapped_blend=True)
    if not scorable:
        return 0.0
    scores = [s for s in (bio_score_of(i) for i in scorable) if s is not None]
    if not scores:
        return 0.0
    avg = sum(scores) / len(scores)
    return _clamp(0.0, CAP_BIO_SCORE, avg)


# --- A2 premium forms -----------------------------------------------------


def _score_premium_forms(product: Dict[str, Any]) -> float:
    """Count distinct scorable ingredients with bio_score ≥ 12. Skip-first
    rule means N premium forms earn (N-1) * 0.5, capped at CAP_PREMIUM_FORMS.
    Same threshold (12 on bio_score 0-15) as v3.6.0 A2."""
    keys: set = set()
    for ing in get_active_ingredients(product):
        if not is_scorable(ing):
            continue
        score = bio_score_of(ing)
        if score is None or score < PREMIUM_FORM_THRESHOLD:
            continue
        key = canonical_key(ing)
        if key:
            keys.add(key)
    count = len(keys)
    effective = max(0, count - 1) if PREMIUM_FORM_SKIP_FIRST else count
    return _clamp(0.0, CAP_PREMIUM_FORMS, effective * PREMIUM_FORM_POINTS_PER_ADDITIONAL)


# --- A3 delivery system ---------------------------------------------------


def _score_delivery_system(product: Dict[str, Any]) -> float:
    """Lookup delivery_tier (1/2/3) → 3/2/1 points. Reads `delivery_tier`
    at the top level first, then falls back to `delivery_data.highest_tier`
    (matches v3's lookup order)."""
    tier = (product or {}).get("delivery_tier")
    if tier is None:
        tier = _safe_dict((product or {}).get("delivery_data")).get("highest_tier")
    tier_int = int(_as_float(tier, 0) or 0)
    return _clamp(0.0, CAP_DELIVERY, DELIVERY_TIER_POINTS.get(tier_int, 0.0))


# --- A4 absorption enhancer pairing ---------------------------------------


def _score_absorption_enhancer(product: Dict[str, Any]) -> float:
    """+CAP_ABSORPTION (3) when the enricher detected a known
    absorption-enhancer pairing (Bioperine + curcumin, vit C + iron, etc.).
    Reads top-level `absorption_enhancer_paired` boolean first, then falls
    back to `absorption_data.qualifies_for_bonus`."""
    if (product or {}).get("absorption_enhancer_paired") is not None:
        return float(CAP_ABSORPTION) if bool(product.get("absorption_enhancer_paired")) else 0.0
    qualifies = bool(
        _safe_dict((product or {}).get("absorption_data")).get("qualifies_for_bonus", False)
    )
    return float(CAP_ABSORPTION) if qualifies else 0.0


# --- A5a organic (part of excellence rollup) ------------------------------


def _score_a5a_organic(product: Dict[str, Any]) -> float:
    """USDA-verified organic or claimed-without-exclusion → +1. Mirrors v3
    `_compute_formulation_bonus`'s organic-detection branch."""
    organic = _safe_dict((product or {}).get("formulation_data")).get("organic")
    if isinstance(organic, dict):
        verified = bool(organic.get("usda_verified"))
        claimed_clean = bool(organic.get("claimed")) and not organic.get("exclusion_matched")
        return A5A_ORGANIC if (verified or claimed_clean) else 0.0
    return A5A_ORGANIC if bool(organic) else 0.0


# --- A5e natural source (part of excellence rollup) -----------------------


def _score_a5e_natural_source(product: Dict[str, Any]) -> float:
    """+1 when a majority of scorable active ingredients have `natural=True`.
    Tiebreaker, not tier — single trace ingredient doesn't earn the badge."""
    scorable = [i for i in get_active_ingredients(product) if is_scorable(i)]
    if not scorable:
        return 0.0
    natural_count = sum(1 for i in scorable if bool(i.get("natural", False)))
    return A5E_NATURAL if natural_count * 2 >= len(scorable) else 0.0


# --- A6 single-ingredient efficiency --------------------------------------


def _score_single_ingredient_efficiency(product: Dict[str, Any]) -> float:
    """+1 when the product is single-ingredient (supp_type in
    {single, single_nutrient}) AND the first scorable active has
    bio_score ≥ 14. v4 caps this at 1 (vs v3's 3) because the bio_score
    contribution at the dimension level (cap 15) already covers premium
    chelated singles."""
    if supp_type_of(product) not in SINGLE_INGREDIENT_SUPP_TYPES:
        return 0.0
    scorable = [i for i in get_active_ingredients(product) if is_scorable(i)]
    if not scorable:
        return 0.0
    score = bio_score_of(scorable[0])
    if score is None or score < SINGLE_INGREDIENT_BIO_THRESHOLD:
        return 0.0
    return CAP_SINGLE_INGREDIENT


# --- B1 dietary sugar (penalty) -------------------------------------------


def _penalty_dietary_sugar(product: Dict[str, Any]) -> float:
    """Returns a NON-NEGATIVE magnitude — caller subtracts. Reads
    `dietary_sensitivity_data.sugar.level` (moderate / high)."""
    sugar = _safe_dict(
        _safe_dict((product or {}).get("dietary_sensitivity_data")).get("sugar")
    )
    level = _norm_text(sugar.get("level"))
    if level == "high":
        return min(DIETARY_SUGAR_CAP, DIETARY_SUGAR_HIGH_PENALTY)
    if level == "moderate":
        return min(DIETARY_SUGAR_CAP, DIETARY_SUGAR_MODERATE_PENALTY)
    return 0.0


# --- Public entry point ---------------------------------------------------


def score_formulation(product: Dict[str, Any]) -> Dict[str, Any]:
    """Compute the generic-module Formulation dimension.

    Returns a dict compatible with the `DimensionResult` shape used by
    `score_generic()`. The caller (generic module orchestrator) merges
    this into `result.dimensions["formulation"]`.

    P1.3.1a state: 8 simple components populated, 6 complex components
    stubbed at 0 with explicit `metadata.deferred_components` /
    `metadata.deferred_penalties` in the breakdown payload so audit /
    score-delta tooling can distinguish "scored as zero" from "deferred
    until next slice."

    Args:
        product: Enriched product dict. Treated as empty if not a dict.

    Returns:
        Dict with shape:
            {
                "score": <float, clamped to [0, 30]>,
                "max": 30.0,
                "components": { ... },
                "penalties": { ... },
                "phase": "P1.3.1a_partial",
                "metadata": { ... },
            }
    """
    if not isinstance(product, dict):
        product = {}

    components: Dict[str, float] = {
        "A1_bio_score":               round(_score_bio_score(product), 4),
        "A2_premium_forms":           round(_score_premium_forms(product), 4),
        "A3_delivery_system":         round(_score_delivery_system(product), 4),
        "A4_absorption_enhancer":     round(_score_absorption_enhancer(product), 4),
        "A5a_organic":                round(_score_a5a_organic(product), 4),
        "A5e_natural_source":         round(_score_a5e_natural_source(product), 4),
        "A6_single_ingredient":       round(_score_single_ingredient_efficiency(product), 4),
    }
    # Stubs — P1.3.1b. Recorded as 0.0 with a sibling deferred-marker so
    # audit tooling does not confuse "scored zero" with "not yet implemented".
    for stub in DEFERRED_TO_P131B_COMPONENTS:
        components[stub] = 0.0

    penalties: Dict[str, float] = {
        # Stored as negatives for ergonomic JSON inspection — the score
        # math subtracts |abs| values explicitly via _sum_penalty_magnitudes
        # so any sign convention error here can't silently inflate scores.
        "B1_dietary_sugar":           round(-_penalty_dietary_sugar(product), 4),
    }
    for stub in DEFERRED_TO_P131B_PENALTIES:
        penalties[stub] = 0.0

    # A5 rollup hard-clamp at CAP_EXCELLENCE (4). Sub-credits A5a/A5e
    # currently sum to ≤ 2; future P1.3.1b additions (std/synergy/non-GMO)
    # bring the rollup max to ~4.5 and the clamp matters then. Applying
    # the clamp now means P1.3.1b can't accidentally exceed it.
    a5_sum = components["A5a_organic"] + components["A5e_natural_source"]
    a5_clamped = _clamp(0.0, CAP_EXCELLENCE, a5_sum)
    a5_excess = a5_sum - a5_clamped  # always ≥ 0; subtract to enforce the clamp

    # Dimension score: positives minus penalty magnitudes, clamped to [0, 30].
    positive = (
        components["A1_bio_score"]
        + components["A2_premium_forms"]
        + components["A3_delivery_system"]
        + components["A4_absorption_enhancer"]
        + a5_clamped
        + components["A6_single_ingredient"]
        # P1.3.1b stubs are 0 — already excluded from sum
    )
    penalty_total = _sum_penalty_magnitudes(penalties)

    score = _clamp(0.0, DIMENSION_CAP, positive - penalty_total)

    # Record the excellence rollup clamp in the breakdown for explainability.
    if a5_excess > 0:
        components["_A5_rollup_clamped_from"] = round(a5_sum, 4)

    return {
        "score": round(score, 4),
        "max": DIMENSION_CAP,
        "components": components,
        "penalties": penalties,
        "phase": PHASE_MARKER_PARTIAL,
        "metadata": {
            "phase": PHASE_MARKER_PARTIAL,
            "deferred_components": list(DEFERRED_TO_P131B_COMPONENTS),
            "deferred_penalties": list(DEFERRED_TO_P131B_PENALTIES),
        },
    }


# --- internals ------------------------------------------------------------


def _clamp(lo: float, hi: float, value: float) -> float:
    return max(lo, min(hi, value))


def _sum_penalty_magnitudes(penalties: Dict[str, float]) -> float:
    """Sum the ABSOLUTE values of penalty entries. Defensive: regardless
    of whether callers stored penalties as positive or negative numbers,
    this returns the magnitude to subtract from positives."""
    return sum(abs(_as_float(v, 0.0) or 0.0) for v in penalties.values())
