"""v4 generic-module Formulation dimension (P1.3.1).

Per `docs/plans/SCORING_V4_PROPOSAL.md` §6 generic rubric — Formulation 30:

    | Item                                  | Cap | v3 source                |
    |---------------------------------------|----:|--------------------------|
    | Form-specific bioavailability         |  15 | A1 bio_score             |
    | Premium forms (beyond primary)        |   4 | A2 premium_forms         |
    | Delivery system                       |   3 | A3 delivery_system       |
    | Absorption enhancer pairing           |   3 | A4 absorption_enhancer   |
    | Formulation excellence rollup         |   4 | A5 organic + std + synergy + non-GMO + natural |
    | Single-ingredient efficiency (tiered) |   4 | A6 single_ingredient     |
    | Enzyme recognition (single-ing only)  |   2 | enzyme_recognition       |
    |                                       |     |                          |
    | B0 immediate_fail (moderate/watchlist)| -10 | safety_signals           |
    | B1 harmful_additives                  | -15 | contaminant_data         |
    | B1 dietary_sugar                      |-1.5 | dietary_sensitivity_data |

Final: clamp(0, 30, sum(components) − sum(|penalties|)).

P1.3.1a implemented the 8 "simple" sub-rubrics that are mostly direct
field reads:

    A1 bio_score, A2 premium forms, A3 delivery, A4 absorption,
    A5a organic, A5e natural source, A6 single-ingredient,
    B1 dietary sugar.

P1.3.1b implements the 6 "complex" sub-rubrics that need additional
reverse-engineering:

    A5b standardized botanical, A5c synergy 4-tier, A5d non-GMO,
    enzyme recognition, B0 moderate/watchlist, B1 harmful additives.

The dimension score is the positive component sum minus penalty
magnitudes, clamped to [0, 30]. Audit / score-delta tooling sees the
phase marker and knows formulation math is complete while downstream
dimensions are still skeleton.

Per §13 architecture lock, this module does not import from
`score_supplements.py` (v3). The numeric rules below mirror v3's
A1-A6/B1 logic by re-implementation, not by import.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict

from audit_evidence_utils import derive_non_gmo_audit
from scoring_v4.modules.botanical_profile import (
    is_botanical_product,
    score_botanical_formulation,
)
from scoring_v4.modules.collagen_profile import (
    is_collagen_product,
    score_collagen_formulation,
)
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
# A6 (v4.1) — tiered focused-single-ingredient quality. Compensates a focused
# product for the A2 "premium forms beyond primary" breadth bonus it structurally
# cannot earn (a single active has no additional forms). Mutually exclusive with A2
# in practice: A2 needs >=2 premium forms; A6 only fires for single-ingredient types.
# Tiered by bio_score so "solid premium" (12) and "elite" (>=14) differ, controlling
# inflation. A1 still pays the form's bioavailability; A6 is the focus bonus on top,
# the single's structural analog to a multi's A2.
CAP_SINGLE_INGREDIENT = 4.0
A6_TIER_FLOOR_BIO = 10.0        # below this: acceptable/weak form, no focus bonus
A6_TIER_SOLID_BIO = 12.0
A6_TIER_ELITE_BIO = 14.0
A6_POINTS_GOOD = 1.0            # bio 10-11.99
A6_POINTS_SOLID = 3.0          # bio 12-13.99
A6_POINTS_ELITE = 4.0          # bio >= 14
CAP_ENZYME = 2.0
DIMENSION_CAP = 30.0
FORMULATION_PRESENCE_FLOOR = 2.0
PREMIUM_SINGLE_FLOOR_SOLID = 22.0
PREMIUM_SINGLE_FLOOR_ELITE = 24.0
STANDARD_SINGLE_FLOOR_VALIDATED_LOW_BIO = 13.0
_VALIDATED_LOW_BIO_STANDARD_SINGLE_CANONICALS = frozenset({
    # Standard oral NAC is the clinically studied supplement form despite
    # intrinsically poor oral bioavailability. Do not inflate it to premium, but
    # do keep a focused, dose-bearing NAC single out of weak-form territory.
    "nac",
})

PREMIUM_FORM_THRESHOLD = 12.0           # v3.6.0 A2 threshold on bio_score scale
PREMIUM_FORM_POINTS_PER_ADDITIONAL = 0.5
PREMIUM_FORM_SKIP_FIRST = True

DELIVERY_TIER_POINTS = {1: 3.0, 2: 2.0, 3: 1.0}

SINGLE_INGREDIENT_SUPP_TYPES = frozenset({"single", "single_nutrient"})

# A5 rollup sub-credits (sum can exceed CAP_EXCELLENCE; we clamp at the end).
A5A_ORGANIC = 1.0
A5B_STANDARDIZED_FULL = 1.0
A5B_STANDARDIZED_MARKER_ONLY = 0.5
A5C_SYNERGY_TIER_POINTS = {1: 1.0, 2: 0.75, 3: 0.5, 4: 0.25}
A5D_NON_GMO_PROJECT = 0.5
A5E_NATURAL = 1.0

ENZYME_POINTS_PER_NAMED = 0.5
_KNOWN_ENZYMES = frozenset(
    {
        "amylase",
        "protease",
        "lipase",
        "cellulase",
        "lactase",
        "bromelain",
        "papain",
        "pepsin",
        "rennin",
        "trypsin",
        "chymotrypsin",
        "serrapeptase",
        "alpha-galactosidase",
        "alpha galactosidase",
        "hemicellulase",
        "invertase",
        "maltase",
        "sucrase",
        "xylanase",
        "beta-glucanase",
        "phytase",
        "pectinase",
        "catalase",
        "superoxide dismutase",
        "sod",
        "nattokinase",
    }
)

B0_HIGH_RISK_PENALTY = 10.0
B0_WATCHLIST_PENALTY = 5.0
B0_MODERATE_PENALTY = 10.0
B0_CAP = 10.0

B1_HARMFUL_ADDITIVE_CAP = 15.0
B1_HARMFUL_ADDITIVE_POINTS = {
    "critical": 3.0,
    "high": 2.0,
    "moderate": 1.0,
    "low": 0.5,
    "none": 0.0,
}

# B1 dietary-sugar penalty bands (mirrors scoring_config.B1_dietary_sugar_penalty).
DIETARY_SUGAR_MODERATE_PENALTY = 0.5
DIETARY_SUGAR_HIGH_PENALTY = 1.5
DIETARY_SUGAR_CAP = 1.5

PHASE_MARKER_COMPLETE = "P1.3.1b_formulation_complete"


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


def _score_a5b_standardized_botanical(product: Dict[str, Any]) -> float:
    """Standardized botanical credit. Full credit for threshold-backed
    standardized extracts; marker-word-only evidence earns conservative
    half credit. Mirrors v3's `A5b_standardized_botanical` branch."""
    formulation = _safe_dict((product or {}).get("formulation_data"))
    best = 0.0
    for item in _safe_list(formulation.get("standardized_botanicals")):
        if not isinstance(item, dict):
            continue
        if not item.get("meets_threshold"):
            continue
        evidence_source = _norm_text(item.get("evidence_source"))
        if evidence_source == "marker_word_only":
            best = max(best, A5B_STANDARDIZED_MARKER_ONLY)
            continue
        return A5B_STANDARDIZED_FULL
    if best:
        return best
    return A5B_STANDARDIZED_FULL if bool((product or {}).get("has_standardized_botanical")) else 0.0


def _score_a5c_synergy_cluster(product: Dict[str, Any]) -> float:
    """4-tier synergy-cluster bonus. Dose-checkable clusters require at
    least half the checkable ingredients to meet minimum effective dose;
    the best qualifying tier wins."""
    explicit = (product or {}).get("synergy_cluster_qualified")
    if explicit is True:
        return A5C_SYNERGY_TIER_POINTS[2]  # v3 legacy default for precomputed True
    if explicit is False:
        return 0.0

    best = 0.0
    formulation = _safe_dict((product or {}).get("formulation_data"))
    for cluster in _safe_list(formulation.get("synergy_clusters")):
        if not isinstance(cluster, dict):
            continue
        matched = [i for i in _safe_list(cluster.get("matched_ingredients")) if isinstance(i, dict)]
        match_count = int(_as_float(cluster.get("match_count"), len(matched)) or 0)
        if match_count < 2:
            continue
        checkable = [
            item
            for item in matched
            if (_as_float(item.get("min_effective_dose"), 0.0) or 0.0) > 0
        ]
        if not checkable:
            continue
        dosed = [item for item in checkable if bool(item.get("meets_minimum"))]
        if len(dosed) < math.ceil(len(checkable) / 2):
            continue
        tier = int(_as_float(cluster.get("evidence_tier"), 4) or 4)
        best = max(best, A5C_SYNERGY_TIER_POINTS.get(tier, A5C_SYNERGY_TIER_POINTS[4]))
    return best


def _score_a5d_non_gmo(product: Dict[str, Any]) -> float:
    """Non-GMO Project Verified earns +0.5. Generic non-GMO marketing
    claims intentionally do not score."""
    try:
        audit = derive_non_gmo_audit(product or {})
    except Exception:
        return 0.0
    return A5D_NON_GMO_PROJECT if bool(audit.get("project_verified")) else 0.0


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


def _score_single_ingredient_efficiency(
    product: Dict[str, Any], effective_quality: float | None
) -> float:
    """Tiered focus bonus for single-ingredient products (supp_type in
    {single, single_nutrient}) on the EFFECTIVE formulation quality that fills
    the A1 slot: bio_score for generic singles, the botanical adapter score for
    botanical singles, the collagen adapter for collagen singles.
    Tiers: >= 14 -> +4, >= 12 -> +3, >= 10 -> +1, else 0.

    Reading the effective A1 quality (not the raw row bio_score) keeps A1 and A6
    one brain: a premium botanical single (Meriva/Curcumin Phytosome, KSM-66)
    whose adapter recognizes its identity/standardization/dose now earns the
    focus bonus instead of being silently zeroed because herbs sit low on the
    vitamin/mineral bio scale. For generic singles the effective A1 IS the bio
    average, so prior bio-tier behavior is unchanged. v4.1 raised this from a
    flat +1 (gate 14). A1 already pays the form's quality; this is the focus
    bonus on top, compensating for the A2 breadth bonus a single can never earn.
    """
    if supp_type_of(product) not in SINGLE_INGREDIENT_SUPP_TYPES:
        return 0.0
    # Proprietary-blend containers are not transparent singles — keep them out
    # of the focus bonus even when their parent fills the A1 slot (v3 parity).
    scorable = [i for i in get_active_ingredients(product) if is_scorable(i)]
    if not scorable:
        return 0.0
    if effective_quality is None or effective_quality < A6_TIER_FLOOR_BIO:
        return 0.0
    if effective_quality >= A6_TIER_ELITE_BIO:
        return A6_POINTS_ELITE
    if effective_quality >= A6_TIER_SOLID_BIO:
        return A6_POINTS_SOLID
    return A6_POINTS_GOOD


def _premium_single_floor_target(
    product: Dict[str, Any],
    effective_quality: float | None,
) -> float:
    """Return the formulation floor for a focused premium single.

    This is the top-band ceiling repair: focused singles cannot earn A2 breadth
    or most formulation-stack bonuses, so premium-quality singles were capped in
    the high teens. The floor is deliberately narrow:
      - only explicit single/single_nutrient products,
      - exactly one non-blend, dose-bearing scorable active,
      - effective A1 quality >= 12.

    It does not lift weak forms, multis, or proprietary blend containers.
    """
    if supp_type_of(product) not in SINGLE_INGREDIENT_SUPP_TYPES:
        return 0.0
    scorable = [i for i in get_active_ingredients(product) if is_scorable(i)]
    if len(scorable) != 1:
        return 0.0
    if effective_quality is None:
        return 0.0
    if effective_quality >= A6_TIER_ELITE_BIO:
        return PREMIUM_SINGLE_FLOOR_ELITE
    if effective_quality >= A6_TIER_SOLID_BIO:
        return PREMIUM_SINGLE_FLOOR_SOLID
    return 0.0


def _standard_single_floor_target(
    product: Dict[str, Any],
    effective_quality: float | None,
) -> float:
    """Modest floor for clinically validated standard-form simple molecules.

    Some oral actives have low systemic bioavailability but are still the
    clinically validated supplement form. This is not a premium-form bonus; it
    prevents the formulation dimension from miscommunicating "weak form" when
    the label is a focused, standard, dose-bearing single.
    """
    if effective_quality is None or effective_quality < 6.0:
        return 0.0
    row = _single_scorable_active(product)
    if row is None:
        return 0.0
    canonical_id = str(row.get("canonical_id") or "").strip().lower()
    if canonical_id not in _VALIDATED_LOW_BIO_STANDARD_SINGLE_CANONICALS:
        return 0.0
    return STANDARD_SINGLE_FLOOR_VALIDATED_LOW_BIO


def _single_scorable_active(product: Dict[str, Any]) -> Dict[str, Any] | None:
    if supp_type_of(product) not in SINGLE_INGREDIENT_SUPP_TYPES:
        return None
    scorable = [i for i in get_active_ingredients(product) if is_scorable(i)]
    if len(scorable) != 1:
        return None
    row = scorable[0]
    if bool(row.get("is_proprietary_blend")):
        return None
    return row


def _score_enzyme_recognition(product: Dict[str, Any]) -> float:
    """Named-enzyme recognition for single-ingredient generic products.
    Dedupes enzyme families and caps at 2 points in v4."""
    if supp_type_of(product) not in SINGLE_INGREDIENT_SUPP_TYPES:
        return 0.0
    seen: set[str] = set()
    for ing in get_active_ingredients(product):
        enzyme = _known_enzyme_name(ing)
        if enzyme:
            seen.add(enzyme)
    return _clamp(0.0, CAP_ENZYME, len(seen) * ENZYME_POINTS_PER_NAMED)


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


def _penalty_b0_moderate_watchlist(product: Dict[str, Any]) -> float:
    """Moderate/high-risk/watchlist safety signals that are not
    short-circuit verdicts. Only exact/alias matches score here; fuzzy
    review items stay non-scoring until reviewed."""
    substances = _safe_list(
        _safe_dict(_safe_dict((product or {}).get("contaminant_data")).get("banned_substances")).get("substances")
    )
    total = 0.0
    for substance in substances:
        if not isinstance(substance, dict):
            continue
        match_type = _normalize_match_type(
            substance.get("match_type") or substance.get("match_method") or substance.get("match_basis")
        )
        if match_type not in {"exact", "alias"}:
            continue
        status = _norm_text(substance.get("status"))
        severity = _norm_text(substance.get("severity_level") or substance.get("severity"))
        if status == "high_risk":
            total += B0_HIGH_RISK_PENALTY
        elif status == "watchlist":
            total += B0_WATCHLIST_PENALTY
        elif severity == "moderate":
            total += B0_MODERATE_PENALTY
    return _clamp(0.0, B0_CAP, total)


def _penalty_b1_harmful_additives(product: Dict[str, Any]) -> float:
    """Named harmful-additive penalty. Low/moderate active-source rows are
    suppressed to avoid penalizing active nutrients that share names with
    excipient entries; high/critical still score."""
    contaminant = _safe_dict((product or {}).get("contaminant_data"))
    harmful = _safe_dict(contaminant.get("harmful_additives"))
    additives = _safe_list(harmful.get("additives"))
    if not additives:
        additives = _safe_list((product or {}).get("harmful_additives"))

    best_by_key: dict[str, float] = {}
    for idx, additive in enumerate(additives):
        if not isinstance(additive, dict):
            continue
        severity = _norm_text(additive.get("severity_level") or additive.get("severity"))
        points = B1_HARMFUL_ADDITIVE_POINTS.get(severity, 0.0)
        if points <= 0:
            continue
        source_section = _norm_text(additive.get("source_section") or additive.get("source"))
        if source_section == "active" and severity in {"low", "moderate"}:
            continue
        key = str(additive.get("additive_id") or additive.get("id") or f"_anon_{idx}").strip().lower()
        best_by_key[key] = max(best_by_key.get(key, 0.0), points)
    return _clamp(0.0, B1_HARMFUL_ADDITIVE_CAP, sum(best_by_key.values()))


# --- Public entry point ---------------------------------------------------


def score_formulation(product: Dict[str, Any]) -> Dict[str, Any]:
    """Compute the generic-module Formulation dimension.

    Returns a dict compatible with the `DimensionResult` shape used by
    `score_generic()`. The caller (generic module orchestrator) merges
    this into `result.dimensions["formulation"]`.

    P1.3.1b state: all Formulation components and penalties are online.
    Downstream dimensions remain skeleton until their P1.3.x slices land.

    Args:
        product: Enriched product dict. Treated as empty if not a dict.

    Returns:
        Dict with shape:
            {
                "score": <float, clamped to [0, 30]>,
                "max": 30.0,
                "components": { ... },
                "penalties": { ... },
                "phase": "P1.3.1b_formulation_complete",
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
        "A5b_standardized_botanical": round(_score_a5b_standardized_botanical(product), 4),
        "A5c_synergy_cluster":        round(_score_a5c_synergy_cluster(product), 4),
        "A5d_non_gmo":                round(_score_a5d_non_gmo(product), 4),
        "A5e_natural_source":         round(_score_a5e_natural_source(product), 4),
        "A6_single_ingredient":       0.0,  # computed below, after the A1 slot is finalized
        "enzyme_recognition":         round(_score_enzyme_recognition(product), 4),
    }

    # Phase 6 — Botanical Profile. For botanical products the bio_score (A1) +
    # premium-forms (A2) vitamin/mineral logic is replaced by the botanical
    # formulation adapter (max 15, occupies the A1 slot). A5b standardization is
    # disabled here because marker standardization is now core formulation
    # inside the adapter (no duplicate +1 bonus).
    botanical_formulation: Dict[str, Any] = {}
    collagen_formulation: Dict[str, Any] = {}
    if is_collagen_product(product):
        # Phase 7 — Collagen Profile occupies the A1 slot (type/hydrolyzed/source/
        # dose/branded). A2 premium-forms + A5b standardization are vitamin/herb
        # concepts and are disabled for collagen. Checked before botanical;
        # mass-dominance makes them mutually exclusive.
        col = score_collagen_formulation(product)
        components["A1_bio_score"] = round(col["score"], 4)
        components["A2_premium_forms"] = 0.0
        components["A5b_standardized_botanical"] = 0.0
        collagen_formulation = col
    elif is_botanical_product(product):
        bot = score_botanical_formulation(product)
        components["A1_bio_score"] = round(bot["score"], 4)
        components["A2_premium_forms"] = 0.0
        components["A5b_standardized_botanical"] = 0.0
        botanical_formulation = bot

    # A6 reads the EFFECTIVE A1-slot quality (bio for generic, botanical/collagen
    # adapter for those profiles), computed after any adapter overwrite so a
    # premium botanical single earns the focus bonus consistently with A1.
    components["A6_single_ingredient"] = round(
        _score_single_ingredient_efficiency(product, components["A1_bio_score"]), 4
    )

    penalties: Dict[str, float] = {
        # Stored as negatives for ergonomic JSON inspection — the score
        # math subtracts |abs| values explicitly via _sum_penalty_magnitudes
        # so any sign convention error here can't silently inflate scores.
        "B1_dietary_sugar":           round(-_penalty_dietary_sugar(product), 4),
        "B0_moderate_watchlist":       round(-_penalty_b0_moderate_watchlist(product), 4),
        "B1_harmful_additives":        round(-_penalty_b1_harmful_additives(product), 4),
    }

    # A5 rollup hard-clamp at CAP_EXCELLENCE (4).
    a5_sum = (
        components["A5a_organic"]
        + components["A5b_standardized_botanical"]
        + components["A5c_synergy_cluster"]
        + components["A5d_non_gmo"]
        + components["A5e_natural_source"]
    )
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
        + components["enzyme_recognition"]
    )
    premium_single_floor = _premium_single_floor_target(product, components["A1_bio_score"])
    standard_single_floor = _standard_single_floor_target(product, components["A1_bio_score"])
    single_floor = max(premium_single_floor, standard_single_floor)
    single_floor_adjustment = max(0.0, single_floor - positive)
    premium_single_floor_adjustment = (
        single_floor_adjustment
        if premium_single_floor >= standard_single_floor
        else 0.0
    )
    standard_single_floor_adjustment = (
        single_floor_adjustment
        if standard_single_floor > premium_single_floor
        else 0.0
    )
    if premium_single_floor_adjustment > 0:
        components["premium_single_ingredient_floor_adjustment"] = round(
            premium_single_floor_adjustment, 4
        )
    if standard_single_floor_adjustment > 0:
        components["standard_single_ingredient_floor_adjustment"] = round(
            standard_single_floor_adjustment, 4
        )
    if single_floor_adjustment > 0:
        positive += single_floor_adjustment
    penalty_total = _sum_penalty_magnitudes(penalties)

    pre_floor_score = positive - penalty_total
    presence_floor_applied = (
        _has_mapped_formulation_active(product)
        and positive > 0
        and penalty_total > 0
        and pre_floor_score <= 0
    )
    score = _clamp(0.0, DIMENSION_CAP, pre_floor_score)
    if presence_floor_applied:
        score = max(score, FORMULATION_PRESENCE_FLOOR)

    # Record the excellence rollup clamp in the breakdown for explainability.
    if a5_excess > 0:
        components["_A5_rollup_clamped_from"] = round(a5_sum, 4)

    return {
        "score": round(score, 4),
        "max": DIMENSION_CAP,
        "components": components,
        "penalties": penalties,
        "phase": PHASE_MARKER_COMPLETE,
        "metadata": {
            "phase": PHASE_MARKER_COMPLETE,
            "deferred_components": [],
            "deferred_penalties": [],
            "botanical_profile_applied": bool(botanical_formulation),
            "botanical_formulation": botanical_formulation.get("components", {}),
            "collagen_profile_applied": bool(collagen_formulation),
            "collagen_formulation": collagen_formulation.get("components", {}),
            "premium_single_ingredient_floor": {
                "target": round(premium_single_floor, 4),
                "adjustment": round(premium_single_floor_adjustment, 4),
                "applied": premium_single_floor_adjustment > 0,
            },
            "standard_single_ingredient_floor": {
                "target": round(standard_single_floor, 4),
                "adjustment": round(standard_single_floor_adjustment, 4),
                "applied": standard_single_floor_adjustment > 0,
            },
            "presence_floor": {
                "target": FORMULATION_PRESENCE_FLOOR,
                "pre_floor_score": round(pre_floor_score, 4),
                "applied": presence_floor_applied,
            },
        },
    }


# --- internals ------------------------------------------------------------


def _clamp(lo: float, hi: float, value: float) -> float:
    return max(lo, min(hi, value))


def _has_mapped_formulation_active(product: Dict[str, Any]) -> bool:
    """True when the product has a mapped, dose-bearing active eligible for
    formulation scoring. The presence floor only protects a real positive form
    signal from being erased by unrelated penalties.

    Use the cleaner-promoted ``ingredients_scorable`` rows directly here. The
    broader scoring contract may synthesize product-level evidence rows for
    blend/dose support; those are legitimate for profile scoring, but they do
    not prove the cleaner identified a concrete active form for this display
    hygiene floor.
    """
    iqd = _safe_dict((product or {}).get("ingredient_quality_data"))
    for ing in _safe_list(iqd.get("ingredients_scorable")):
        if not is_scorable(ing):
            continue
        if bool(ing.get("mapped", False)) or canonical_key(ing):
            return True
    return False


def _known_enzyme_name(ingredient: Dict[str, Any]) -> str | None:
    """Return the canonical enzyme family if the ingredient name contains
    a known enzyme as a word-bounded term."""
    text = " ".join(
        _norm_text(ingredient.get(field))
        for field in ("name", "standard_name")
        if _norm_text(ingredient.get(field))
    )
    if not text:
        return None
    for enzyme in sorted(_KNOWN_ENZYMES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(enzyme)}\b", text):
            return enzyme
    return None


def _normalize_match_type(value: Any) -> str:
    text = _norm_text(value)
    if text in {"exact", "alias", "token_bounded"}:
        return text
    if text.startswith("exact"):
        return "exact"
    if "alias" in text:
        return "alias"
    if "token" in text:
        return "token_bounded"
    return text


def _sum_penalty_magnitudes(penalties: Dict[str, float]) -> float:
    """Sum the ABSOLUTE values of penalty entries. Defensive: regardless
    of whether callers stored penalties as positive or negative numbers,
    this returns the magnitude to subtract from positives."""
    return sum(abs(_as_float(v, 0.0) or 0.0) for v in penalties.values())
