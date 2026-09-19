"""Canonical v4 generic Formulation dimension.

Formulation measures form quality and formulation design. Ingredient count,
dose adequacy, evidence strength, consumer badges, and product focus do not
manufacture points here; those concerns have their own canonical pillars or
display surfaces. The raw positive components are form quality (15), delivery
(3), absorption design (3), and standardized-botanical detail (1), followed by
the shared formulation penalties.
"""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Dict

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
    is_scorable,
    is_nutrient_form_quality_signal,
    scorable_ingredients,
    _as_float,
    _norm_text,
    _safe_dict,
    _safe_list,
)
from scoring_v4.modules.immune_support import immune_support_formulation_adjustment


# --- v4 generic Formulation weights ---------------------------------------
# Mirror v3 with the §6 rescaling: bio_score cap 18→15, single-ingredient
# 3→1, A5 rollup cap 4 preserved.

# ── Config-driven calibration magnitudes ─────────────────────────
# All formulation-dimension point values, caps, and tier thresholds are hoisted
# to scripts/scoring_v4/config/quality_score.json (formulation_magnitudes +
# formulation_penalties). Read once at import; the A-/B- scoring logic stays in
# code (§13 lock). Fail fast if a block is missing. Drift-guarded by
# test_v4_formulation_magnitudes_config / test_v4_additive_points_config.
_V4_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "quality_score.json"


@lru_cache(maxsize=1)
def _v4_config() -> Dict[str, Any]:
    return json.loads(_V4_CONFIG_PATH.read_text())


def _v4_block(name: str, sentinel: str) -> Dict[str, Any]:
    cfg = _v4_config()
    blk = cfg.get(name) if isinstance(cfg, dict) else None
    if not isinstance(blk, dict) or sentinel not in blk:
        raise RuntimeError(f"quality_score.json missing {name}.{sentinel} — v4 config not found")
    return blk


_FM = _v4_block("formulation_magnitudes", "dimension_cap")


CAP_BIO_SCORE = _FM["a1_bio_score_cap"]
CAP_DELIVERY = _FM["a3_delivery_cap"]
CAP_ABSORPTION = _FM["a4_absorption_cap"]
DIMENSION_CAP = _FM["dimension_cap"]
FORMULATION_PRESENCE_FLOOR = _FM["presence_floor"]

DELIVERY_TIER_POINTS = {int(k): v for k, v in _FM["a3_delivery_tier_points"].items()}


A5B_STANDARDIZED_FULL = _FM["a5b_standardized_full"]
A5B_STANDARDIZED_MARKER_ONLY = _FM["a5b_standardized_marker_only"]

B0_HIGH_RISK_PENALTY = _FM["b0_high_risk_penalty"]
B0_WATCHLIST_PENALTY = _FM["b0_watchlist_penalty"]
B0_MODERATE_PENALTY = _FM["b0_moderate_penalty"]
# B0 safety-signal penalties ACCUMULATE per substance (2 high_risk = -20, a
# high_risk + watchlist mix = -15) so a product carrying more risk is tanked more.
# Bounded by the formulation dimension itself (a B0 of 30 can fully consume the
# 30-pt dimension, not exceed it). Was 10.0 (which collapsed 2 high_risk into 1).
B0_CAP = DIMENSION_CAP  # 30.0

# B1 harmful-additive points/cap are HOISTED to scripts/scoring_v4/config/
# quality_score.json (formulation_penalties). Single source: the safety_hygiene
# pillar reads the same file. Only the VALUES are config-driven; the B1 logic
# stays here (§13 architecture lock). Fail fast if the block is missing — a
# silent wrong score is worse than a loud error. test_v4_additive_points_config
# guards config<->runtime drift.
_FP = _v4_block("formulation_penalties", "b1_harmful_additive_points")
B1_HARMFUL_ADDITIVE_POINTS = {str(k): float(v) for k, v in _FP["b1_harmful_additive_points"].items()}
B1_HARMFUL_ADDITIVE_CAP = float(_FP.get("b1_harmful_additive_cap", 15.0))

# B1 dietary-sugar penalty bands. Uses the strongest applicable band rather
# than summing, so one gummy with syrup and 4g sugar is a high-sugar penalty,
# not three separate sugar penalties.
DIETARY_SUGAR_LOW_ADDED_PENALTY = _FM["dietary_sugar_low_added_penalty"]
DIETARY_SUGAR_HIGH_GLYCEMIC_OR_SYRUP_PENALTY = _FM["dietary_sugar_high_glycemic_or_syrup_penalty"]
DIETARY_SUGAR_SUGAR_ALCOHOL_PENALTY = _FM["dietary_sugar_sugar_alcohol_penalty"]
DIETARY_SUGAR_MODERATE_PENALTY = _FM["dietary_sugar_moderate_penalty"]
DIETARY_SUGAR_HIGH_PENALTY = _FM["dietary_sugar_high_penalty"]
DIETARY_SUGAR_CAP = _FM["dietary_sugar_cap"]

PHASE_MARKER_COMPLETE = "P1.3.1b_formulation_complete"


# --- A1 bio_score ---------------------------------------------------------


def _bio_score_assessment(product: Dict[str, Any]) -> tuple[float, int]:
    """Return the unchanged A1 average and the count of available form ratings.

    No rating and an explicit zero both contribute zero numerically, but they
    must not produce the same consumer explanation. Use the same eligible
    rows and bio_score reader for both the arithmetic and that distinction.
    """
    scorable = scorable_ingredients(
        product,
        allow_sole_mapped_blend=True,
        require_dose=False,
    )
    scores = [s for s in (bio_score_of(i) for i in scorable) if s is not None]
    if not scores:
        return 0.0, 0
    avg = sum(scores) / len(scores)
    return _clamp(0.0, CAP_BIO_SCORE, avg), len(scores)


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


# --- B1 dietary sugar (penalty) -------------------------------------------


def _dietary_sugar_penalty_detail(product: Dict[str, Any]) -> Dict[str, Any]:
    """Classify added sugar/syrup/sugar-alcohol formulation drag."""
    dietary = _safe_dict((product or {}).get("dietary_sensitivity_data"))
    sugar = _safe_dict(dietary.get("sugar"))
    sweeteners = _safe_dict(dietary.get("sweeteners"))
    level = _norm_text(sugar.get("level"))
    sugar_sources = _safe_list(sugar.get("sugar_sources"))
    high_glycemic = _safe_list(
        sweeteners.get("high_glycemic") or sweeteners.get("high_glycemic_sweeteners")
    )
    sugar_alcohols = _safe_list(sweeteners.get("sugar_alcohols"))
    syrup_sources = [
        source for source in sugar_sources
        if "syrup" in _norm_text(source)
    ]

    # The canonical sugar determination, from the enricher that owns it. When it
    # establishes the product carries no dietary sugar at all, this scorer may
    # not manufacture one from a sweetener CLASSIFICATION alone.
    #
    # 2026-09-19: maltodextrin is listed under sweeteners.high_glycemic because
    # its glycemic index really is ~85-105. That is true and useful, but as a
    # sub-2% capsule carrier it is not dietary sugar, and the sugar owner had
    # already said so: level "sugar_free", contains_sugar false, sugar_sources
    # empty. The branch below fired anyway, so 1,146 products classified
    # SUGAR-FREE took a dietary-sugar penalty - and because B1_dietary_sugar
    # mirrors into Safety (penalty_registry FORMULA_QUALITY_MIRROR) while the
    # low-severity additive clamp does not apply to it, 1,101 of them were also
    # told "Safety concern: additive or sweetener concerns" on no other basis.
    #
    # Maltodextrin keeps its own treatment: the additive owner already scores it
    # as ADD_MALTODEXTRIN, category filler, severity_level low, 0.5 - and that
    # penalty IS low-severity, so it correctly clamps out of Safety. One label
    # occurrence, one owner. This guard is deliberately written against the sugar
    # determination rather than the ingredient name, so any future carrier
    # classified the same way is covered without another patch.
    canonical_finds_no_sugar = (
        level in {"sugar_free", "none"}
        and not sugar.get("contains_sugar")
        and not sugar.get("has_added_sugar")
        and not sugar_sources
    )

    penalty = 0.0
    reason = None
    if level == "high":
        penalty = DIETARY_SUGAR_HIGH_PENALTY
        reason = "high_sugar_grams"
    elif level == "moderate":
        penalty = DIETARY_SUGAR_MODERATE_PENALTY
        reason = "moderate_sugar_grams"
    elif (high_glycemic or syrup_sources) and not canonical_finds_no_sugar:
        # Real added sugar / high-glycemic — check FIRST so alcohol+syrup stays here.
        penalty = DIETARY_SUGAR_HIGH_GLYCEMIC_OR_SYRUP_PENALTY
        reason = "high_glycemic_or_syrup"
    elif sugar_alcohols:
        # Sugar alcohols de-conflated (2026-07-04): a light penalty, NOT corn-syrup
        # equivalence. They can still carry their own harmful_additives severity.
        penalty = DIETARY_SUGAR_SUGAR_ALCOHOL_PENALTY
        reason = "sugar_alcohol_source"
    elif bool(sugar.get("has_added_sugar")) or (
        bool(sugar.get("contains_sugar")) and sugar_sources
    ):
        penalty = DIETARY_SUGAR_LOW_ADDED_PENALTY
        reason = "low_added_sugar_source"

    penalty = min(DIETARY_SUGAR_CAP, penalty)
    return {
        "penalty": penalty,
        "reason": reason,
        "canonical_finds_no_sugar": canonical_finds_no_sugar,
        "level": level,
        "contains_sugar": bool(sugar.get("contains_sugar")),
        "has_added_sugar": bool(sugar.get("has_added_sugar")),
        "sugar_sources": sugar_sources,
        "high_glycemic_sweeteners": high_glycemic,
        "sugar_alcohols": sugar_alcohols,
        "syrup_sources": syrup_sources,
    }


def _penalty_dietary_sugar(product: Dict[str, Any]) -> float:
    """Returns a NON-NEGATIVE magnitude — caller subtracts."""
    return float(_dietary_sugar_penalty_detail(product).get("penalty") or 0.0)


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


def _b1_harmful_additive_penalty_detail(product: Dict[str, Any]) -> Dict[str, Any]:
    """Return the B1 total and the exact inactive rows that contributed.

    The per-row ledger follows the same filtering, de-duplication, and point
    configuration as the numeric B1 deduction. Exporters consume this ledger;
    they must not reconstruct an applied penalty from resolver severity.
    """
    contaminant = _safe_dict((product or {}).get("contaminant_data"))
    harmful = _safe_dict(contaminant.get("harmful_additives"))
    additives = _safe_list(harmful.get("additives"))
    if not additives:
        additives = _safe_list((product or {}).get("harmful_additives"))

    best_by_key: dict[str, Dict[str, Any]] = {}
    # Label text of every non-active row that contributed to a key. The rule id
    # alone is not a sufficient join key for exporters: the enricher's harmful
    # matcher and the display resolver can land the same label on DIFFERENT ids
    # (measured 2026-08-07: 95 charged rows across 89 products, e.g. the label
    # "FD&C Yellow 6 Lake" is charged ADD_YELLOW6 but resolves to the benign
    # NHA_ARTIFICIAL_COLORS). Carrying the label lets the exporter mirror the
    # charge on the exact row instead of re-deriving it.
    labels_by_key: dict[str, list[str]] = {}
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
        # A nutrient-form quality signal is not an additive concern. B1 charges
        # "harmful additives"; the nutrient_synthetic class describes the quality
        # of a nutrient being SUPPLIED, and harmful_additives.json says so itself
        # -- ADD_SYNTHETIC_VITAMINS.mechanism_of_harm: "quality signal for
        # non-premium forms, not a safety hazard at recommended doses."
        # Applied to an "Other ingredients" row it is a category error: 47
        # products were charged 2.0 because dl-alpha-tocopherol appeared as a
        # trace antioxidant/preservative, where the bioavailability-vs-natural
        # concern does not apply. The curators already set this precedent on the
        # sibling entry (ADD_SYNTHETIC_B_VITAMINS: "Do not penalize nutrient
        # identities ... only matches explicit synthetic-blend labeling"); this
        # gate generalizes it to the whole class instead of per-alias edits.
        if source_section != "active" and is_nutrient_form_quality_signal(additive):
            continue
        rule_id = str(additive.get("additive_id") or additive.get("id") or "").strip()
        key = (rule_id or f"_anon_{idx}").lower()
        if source_section != "active":
            label = _norm_text(
                additive.get("raw_source_text") or additive.get("ingredient")
            )
            if label:
                bucket = labels_by_key.setdefault(key, [])
                if label not in bucket:
                    bucket.append(label)
        previous = best_by_key.get(key)
        if previous is None or points > float(previous["penalty_applied"]):
            best_by_key[key] = {
                "matched_rule_id": rule_id or None,
                "source_section": source_section,
                "penalty_tier": severity,
                "penalty_applied": float(points),
            }

    total = _clamp(
        0.0,
        B1_HARMFUL_ADDITIVE_CAP,
        sum(float(item["penalty_applied"]) for item in best_by_key.values()),
    )
    inactive_details = [
        {
            "matched_rule_id": item["matched_rule_id"],
            "penalty_tier": item["penalty_tier"],
            "penalty_applied": item["penalty_applied"],
            "matched_labels": labels_by_key.get(key, []),
        }
        for key, item in best_by_key.items()
        if item["matched_rule_id"] and item["source_section"] != "active"
    ]
    return {
        "penalty": total,
        "inactive_penalty_details": inactive_details,
    }


def _penalty_b1_harmful_additives(product: Dict[str, Any]) -> float:
    """Named harmful-additive penalty magnitude used by every v4 module."""
    return float(_b1_harmful_additive_penalty_detail(product)["penalty"])


def shared_formulation_penalty_detail(product: Dict[str, Any]) -> Dict[str, Any]:
    """Shared B0/B1 formulation penalties for every v4 module.

    Generic, sports, omega, probiotic, and multi/prenatal products all read the
    same enriched safety/sugar contracts. Keep the penalty math here so
    module-specific formulation scorers cannot drift on watchlist additives,
    harmful additives, or dietary sugar.
    """
    dietary_sugar_detail = _dietary_sugar_penalty_detail(product)
    harmful_additive_detail = _b1_harmful_additive_penalty_detail(product)
    return {
        "penalties": {
            "B1_dietary_sugar": round(-float(dietary_sugar_detail["penalty"]), 4),
            "B0_moderate_watchlist": round(-_penalty_b0_moderate_watchlist(product), 4),
            "B1_harmful_additives": round(
                -float(harmful_additive_detail["penalty"]), 4
            ),
        },
        "metadata": {
            "dietary_sugar": dietary_sugar_detail,
            "inactive_penalty_details": harmful_additive_detail[
                "inactive_penalty_details"
            ],
        },
    }


def apply_formulation_presence_floor(
    product: Dict[str, Any],
    positive: float,
    penalty_total: float,
    *,
    floor: float,
    cap: float,
) -> tuple[float, bool, float]:
    """Apply the shared mapped-active floor without a penalty discontinuity.

    The previous condition activated only once penalties reduced the raw score
    to zero.  A product at 0.1 therefore scored below an otherwise-identical
    product with one extra 0.1 penalty, which jumped up to the 2-point floor.
    Apply the floor throughout the entire sub-floor interval instead.
    """
    pre_floor_score = positive - penalty_total
    applied = (
        _has_mapped_formulation_active(product)
        and positive > 0
        and pre_floor_score < floor
    )
    score = _clamp(0.0, cap, pre_floor_score)
    if applied:
        score = max(score, floor)
    return score, applied, pre_floor_score


# --- Public entry point ---------------------------------------------------


def score_formulation(product: Dict[str, Any]) -> Dict[str, Any]:
    """Compute the generic Formulation dimension from formulation signals.

    A1 is the equal-weight mean of cleaner-owned form-quality ratings. It is
    intentionally independent of ingredient count and dose disclosure. Dose,
    evidence, badges, and formula breadth are owned by their respective
    pillars or display surfaces.
    """
    if not isinstance(product, dict):
        product = {}

    bio_score, form_assessed_count = _bio_score_assessment(product)
    components: Dict[str, float] = {
        "A1_bio_score": round(bio_score, 4),
        "A3_delivery_system": round(_score_delivery_system(product), 4),
        "A4_absorption_enhancer": round(_score_absorption_enhancer(product), 4),
        "A5b_standardized_botanical": round(_score_a5b_standardized_botanical(product), 4),
    }

    botanical_formulation: Dict[str, Any] = {}
    collagen_formulation: Dict[str, Any] = {}
    formulation_profile = "generic_iqm"
    if is_collagen_product(product):
        col = score_collagen_formulation(product)
        components["A1_bio_score"] = round(col["score"], 4)
        components["A5b_standardized_botanical"] = 0.0
        collagen_formulation = col
        formulation_profile = "collagen"
    elif is_botanical_product(product):
        bot = score_botanical_formulation(product)
        components["A1_bio_score"] = round(bot["score"], 4)
        components["A5b_standardized_botanical"] = 0.0
        botanical_formulation = bot
        formulation_profile = "botanical"

    shared_penalty_detail = shared_formulation_penalty_detail(product)
    # Stored as negatives for ergonomic JSON inspection — the score math
    # subtracts |abs| values explicitly via _sum_penalty_magnitudes so any sign
    # convention error here can't silently inflate scores.
    penalties: Dict[str, float] = dict(shared_penalty_detail["penalties"])
    immune_support_metadata: Dict[str, Any] = {}
    immune_adjustment = immune_support_formulation_adjustment(product)
    if immune_adjustment is not None:
        penalties.update(immune_adjustment.get("penalties", {}))
        immune_support_metadata = immune_adjustment.get("metadata", {})

    positive = (
        components["A1_bio_score"]
        + components["A3_delivery_system"]
        + components["A4_absorption_enhancer"]
        + components["A5b_standardized_botanical"]
    )
    penalty_total = _sum_penalty_magnitudes(penalties)

    score, presence_floor_applied, pre_floor_score = apply_formulation_presence_floor(
        product,
        positive,
        penalty_total,
        floor=FORMULATION_PRESENCE_FLOOR,
        cap=DIMENSION_CAP,
    )

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
            "formulation_profile": formulation_profile,
            "iqm_form_quality_assessed_count": form_assessed_count,
            "botanical_profile_applied": bool(botanical_formulation),
            "botanical_formulation": botanical_formulation.get("components", {}),
            "collagen_profile_applied": bool(collagen_formulation),
            "collagen_formulation": collagen_formulation.get("components", {}),
            "presence_floor": {
                "target": FORMULATION_PRESENCE_FLOOR,
                "pre_floor_score": round(pre_floor_score, 4),
                "applied": presence_floor_applied,
            },
            "immune_support": immune_support_metadata,
            # Spread the WHOLE shared metadata rather than cherry-picking
            # one key. Picking only "dietary_sugar" silently dropped
            # "inactive_penalty_details" -- the ledger build_final_db needs
            # to colour "Other ingredients" dots. 5,116 products carried a
            # real B1 harmful-additive charge while shipping an empty
            # ledger, so every one of their additive dots rendered green.
            **shared_penalty_detail["metadata"],
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
