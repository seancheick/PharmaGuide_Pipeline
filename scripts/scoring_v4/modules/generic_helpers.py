"""v4 generic-module shared field extraction helpers.

Centralizes the field-path reads that multiple dimension scorers
(formulation, dose, evidence, trust, transparency) all need so each
dimension module doesn't redefine them.

This is a v4-owned, deliberate re-implementation of v3 patterns. Per
§13 architecture lock, this module MUST NOT import from
`score_supplements.py`. It reads the same enriched-product fields v3
reads so the two scorers see the same world, but the read logic is
duplicated to keep v4 evolvable without v3 entanglement.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from scoring_input_contract import get_scoring_ingredients


_DOSE_UNIT_WHITELIST = frozenset(
    {
        "mg", "milligram", "milligrams", "milligram(s)",
        "mcg", "ug", "µg", "μg", "microgram", "micrograms", "microgram(s)",
        "mcg rae", "mcgrae", "mg rae", "mgrae",
        "g", "gram", "grams", "gram(s)",
        "iu",
        "cfu", "cfu(s)", "cfus",
        "billion cfu", "million cfu",
        "colony forming unit", "colony forming units", "colony forming unit(s)",
        "colonyformingunit", "colonyformingunits", "colonyformingunit(s)",
        "live cell", "live cells", "live cell(s)",
        "livecell", "livecells", "livecell(s)",
        "viable cell", "viable cells", "viable cell(s)",
        "viablecell", "viablecells", "viablecell(s)",
        "active cell", "active cells", "active cell(s)",
        "activecell", "activecells", "activecell(s)",
        "mcgdfe", "mgdfe",
    }
)


def _norm_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _positive_float(value: Any) -> Optional[float]:
    """Coerce to a positive float, rejecting bools (which are ints in Python)."""
    if isinstance(value, bool):
        return None
    number = _as_float(value, None)
    if number is None or number <= 0:
        return None
    return number


def _ordered_pair(low: Any, high: Any) -> Optional[Tuple[float, float]]:
    """Coerce a (min, max) pair to positive floats, tolerating either being absent."""
    lo = _positive_float(low)
    hi = _positive_float(high)
    if lo is None and hi is None:
        return None
    if lo is None:
        lo = hi
    if hi is None:
        hi = lo
    return (hi, lo) if lo > hi else (lo, hi)


def _label_declared_daily_range(product: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """The canonical serving row's declared daily-serving range.

    Products can declare several serving rows (e.g. a 5 mL child serving and a
    10 mL adult serving). This mirrors the enricher's `_select_canonical_serving`
    by taking the row with the highest serving quantity — the adult default —
    rather than `servingSizes[0]`, which is the child row on such products.
    """
    best: Optional[Tuple[float, float]] = None
    best_quantity = -1.0
    for entry in _safe_list(product.get("servingSizes")):
        if not isinstance(entry, dict):
            continue
        pair = _ordered_pair(
            entry.get("minDailyServings") or entry.get("min_daily_servings"),
            entry.get("maxDailyServings") or entry.get("max_daily_servings"),
        )
        if pair is None:
            continue
        quantity = 0.0
        for key in ("quantity", "servingSizeQuantity", "maxQuantity", "minQuantity"):
            number = _positive_float(entry.get(key))
            if number is not None:
                quantity = number
                break
        if best is None or quantity > best_quantity:
            best, best_quantity = pair, quantity
    return best


def daily_serving_range(product: Dict[str, Any]) -> Tuple[float, float, bool]:
    """Return (min_servings_per_day, max_servings_per_day, was_defaulted).

    The single source of daily-serving policy for v4. `daily_serving_multiplier`
    is the top of this range; omega scores its midpoint.

    The label's own declaration wins. `serving_basis` is only consulted when the
    label declares no daily servings, because a 2026-08-06 enricher bug divided
    the label's count by the serving size before storing it there — deflating
    records (0.044 = 1/22.7 g) and inflating others whose serving is under one
    unit (33.3 = 1/0.03 mL, on infant vitamin D). Those values are wrong even
    when they land somewhere believable: DSLD 183945 declares 2 servings a day
    and stored 1.0.

    When the label is silent, `serving_basis` is guarded. A below-one value is
    only believed when `servings_per_day_source` is "directions" — the one place
    a genuine every-other-day regimen originates. `parsed_from_directions` is
    NOT that signal: the enricher sets it whenever it parsed the directions text
    at all, so 346 of the corrupted records carry it.
    """
    label = _label_declared_daily_range(product)
    if label is not None:
        return label[0], label[1], False

    pair = _ordered_pair(
        product.get("servings_per_day_min"), product.get("servings_per_day_max")
    )
    if pair is not None:
        return pair[0], pair[1], False

    for container_key in ("serving_basis", "serving_info"):
        container = _safe_dict(product.get(container_key))
        if not container:
            continue
        pair = _ordered_pair(
            container.get("min_servings_per_day"),
            container.get("max_servings_per_day"),
        )
        if pair is None:
            continue
        if pair[1] < 1.0 and _norm_text(
            container.get("servings_per_day_source")
        ) != "directions":
            continue
        return pair[0], pair[1], False

    return 1.0, 1.0, True


def daily_serving_multiplier(product: Dict[str, Any]) -> float:
    """Servings per day to scale a per-serving amount by.

    The top of `daily_serving_range` — the maximum directed daily use, matching
    `generic_evidence`.
    """
    return daily_serving_range(product)[1]


def get_active_ingredients(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return the active (scorable) ingredient list from an enriched product.

    Version-neutral scoring contract: consume only validated
    ingredient_quality_data.ingredients_scorable rows. Legacy fallback is
    handled by the adapter only when explicitly requested elsewhere.
    """
    return list(get_scoring_ingredients(product or {}, strict=True).rows)


def has_usable_individual_dose(ingredient: Dict[str, Any]) -> bool:
    """True when the ingredient has a positive quantity in a recognized
    dose unit (mg/mcg/g/IU/CFU) — or the enricher explicitly set
    `has_dose=True` to bypass unit checks (legacy probiotic CFU shapes).
    """
    if not isinstance(ingredient, dict):
        return False
    qty = _as_float(ingredient.get("quantity"), None)
    if qty is None or qty <= 0:
        # Probiotic ingredients sometimes lack a numeric quantity but
        # carry has_dose=True when CFU is disclosed via strain-side
        # fields. Honor that signal.
        return bool(ingredient.get("has_dose", False))
    unit = _norm_text(ingredient.get("unit_normalized") or ingredient.get("unit"))
    if not unit:
        return bool(ingredient.get("has_dose", False))
    if unit in _DOSE_UNIT_WHITELIST:
        return True
    # Match v3's compact-form check ("livecell(s)" without spaces).
    if unit.replace(" ", "") in _DOSE_UNIT_WHITELIST:
        return True
    return bool(ingredient.get("has_dose", False))


def is_scorable(ingredient: Dict[str, Any]) -> bool:
    """An ingredient counts toward Formulation sub-rubrics only when it is
    not a proprietary-blend container, not a parent-total roll-up row,
    and has an individually usable dose. v3 applies the same gate before
    A2/A5e/A6 reads.

    A1 has one extra context-dependent exemption for sole mapped blend
    parents. Use `scorable_ingredients(..., allow_sole_mapped_blend=True)`
    for that path rather than widening this single-row predicate.
    """
    if not isinstance(ingredient, dict):
        return False
    if ingredient.get("is_proprietary_blend"):
        return False
    if ingredient.get("is_parent_total"):
        return False
    if ingredient.get("is_compound_duplicate"):
        # Dual-declaration compound-weight row (e.g. "Magnesium Glycinate"
        # 400 mg restating the bare "Magnesium" 60 mg elemental row). The
        # bare row carries the score-bearing dose; counting both would
        # break single-ingredient detection and the premium-single floors.
        return False
    return has_usable_individual_dose(ingredient)


def scorable_ingredients(
    product: Dict[str, Any],
    *,
    allow_sole_mapped_blend: bool = False,
) -> List[Dict[str, Any]]:
    """Return ingredients eligible for a formulation sub-rubric.

    Default behavior matches v3's A2/A5e/A6 gate: skip proprietary blend
    containers, parent-total rows, and rows without an individual dose.

    A1 bio_score has a narrower v3 exemption: when a mapped blend parent
    is the ONLY dose-bearing candidate, score it as the dose-bearing
    active. This protects legitimate single-row branded actives that are
    flagged `is_proprietary_blend` by name pattern but map to a real IQM
    identity (for example I3C/DIM Complex or BioCell Collagen Complex).
    Opaque/unmapped blend parents still earn no A1 credit.
    """
    rows = get_active_ingredients(product)
    non_blend_candidates = sum(
        1
        for ing in rows
        if isinstance(ing, dict)
        and not ing.get("is_proprietary_blend")
        and not ing.get("is_parent_total")
        and has_usable_individual_dose(ing)
    )

    eligible: List[Dict[str, Any]] = []
    for ing in rows:
        if not isinstance(ing, dict):
            continue
        if ing.get("is_parent_total"):
            continue
        if not has_usable_individual_dose(ing):
            continue
        if ing.get("is_proprietary_blend"):
            if (
                allow_sole_mapped_blend
                and non_blend_candidates == 0
                and bool(ing.get("mapped", False))
            ):
                eligible.append(ing)
            continue
        eligible.append(ing)
    return eligible


def bio_score_of(ingredient: Dict[str, Any]) -> Optional[float]:
    """Return the ingredient's form-quality bio_score (0-15 scale), or
    None when unavailable. Falls back to the legacy `score` field for
    blobs from pre-v3.6.0 enrichers — v3.6.0+ emits score == bio_score
    so the fallback yields identical numbers.
    """
    if not isinstance(ingredient, dict):
        return None
    score = _as_float(ingredient.get("bio_score"), None)
    if score is None:
        score = _as_float(ingredient.get("score"), None)
    return score


def canonical_key(ingredient: Dict[str, Any]) -> str:
    """Stable identity key for de-duplication in A2 premium-form counting.
    Prefers canonical_id, falls back to standard_name then raw name."""
    for field in ("canonical_id", "standard_name", "name"):
        value = ingredient.get(field) if isinstance(ingredient, dict) else None
        if value:
            return _norm_text(value)
    return ""


def is_single_scorable_active_of(product: Any) -> bool:
    """Return the taxonomy's canonical single-active fact.

    CONSUME this; never rebuild it. The classifier owns single-ness and emits it
    from distinct score-eligible identities (exactly one, with no second
    unresolved quantified active). Re-deriving it from a type name is the bug
    this replaces: 542 products carry a single-ish `primary_type` while holding
    2+ distinct actives — "BCAA 2:1:1" is `amino_acid` with three amino acids.

    Absent field => False. Pre-0d enriched blobs predate the fact, and we cannot
    prove a product is single without it; refusing the single-ingredient floors
    under-credits rather than over-credits, which is the safe direction. Those
    blobs are already blocked from release by the SoT contract-version gate and
    are regenerated by the Phase 5 rebuild.
    """
    if not isinstance(product, dict):
        return False
    taxonomy = product.get("supplement_taxonomy")
    if not isinstance(taxonomy, dict):
        return False
    return taxonomy.get("is_single_scorable_active") is True


def primary_type_of(product: Any) -> str:
    """Return the normalized taxonomy `primary_type`, or "" when absent.

    Current enriched blobs write the value both at top level and under
    `supplement_taxonomy.primary_type`; prefer the top-level field and use
    the nested path as a defensive fallback. Callers that need old-batch
    pre-taxonomy artifacts are rejected by the strict enrichment contract.
    """
    if not isinstance(product, dict):
        return ""

    direct = product.get("primary_type")
    if isinstance(direct, str):
        normalized = _norm_text(direct)
        if normalized:
            return normalized

    taxonomy = product.get("supplement_taxonomy")
    if isinstance(taxonomy, dict):
        nested = taxonomy.get("primary_type")
        if isinstance(nested, str):
            return _norm_text(nested)
    return ""
