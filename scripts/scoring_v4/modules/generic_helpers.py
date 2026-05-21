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

from typing import Any, Dict, List, Optional


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


def get_active_ingredients(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return the active (scorable) ingredient list from an enriched product.

    Mirrors v3's `_get_active_ingredients` behavior: prefer
    `ingredient_quality_data.ingredients_scorable`, fall back to the full
    `ingredients` list when scorable is empty but the full list has at
    least one mapped non-filler entry. Returns [] on malformed input.
    """
    iqd = _safe_dict((product or {}).get("ingredient_quality_data"))
    rows = _safe_list(iqd.get("ingredients_scorable"))
    if not rows:
        fallback = _safe_list(iqd.get("ingredients"))
        if any(
            isinstance(i, dict)
            and (i.get("mapped") or i.get("canonical_id"))
            and not i.get("is_filler")
            for i in fallback
        ):
            rows = fallback
    return [i for i in rows if isinstance(i, dict)]


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


def supp_type_of(product: Dict[str, Any]) -> str:
    """Return the normalized supplement_type string ('single_nutrient',
    'probiotic', etc.) from the enriched payload. Handles both the dict
    shape (`supplement_type.type`) and the legacy string shape.

    Legacy helper. Prefer `primary_type_of()` for taxonomy-aware new code.
    """
    payload = (product or {}).get("supplement_type")
    if isinstance(payload, dict):
        return _norm_text(payload.get("type"))
    if isinstance(payload, str):
        return _norm_text(payload)
    return ""


def primary_type_of(product: Any) -> str:
    """Return the normalized taxonomy `primary_type`, or "" when absent.

    Current enriched blobs write the value both at top level and under
    `supplement_taxonomy.primary_type`; prefer the top-level field and use
    the nested path as a defensive fallback. Callers that need old-batch
    compatibility can explicitly fall back to `supp_type_of()`.
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
