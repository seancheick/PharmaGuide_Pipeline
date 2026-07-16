from __future__ import annotations

import json
import os
from typing import Any


def _load_probiotic_terms() -> frozenset[str]:
    """Derive PROBIOTIC_TERMS from clinically_relevant_strains.json.

    Collects genera (first word, lowercased) from all standard_names and
    all aliases in the strains data file, then merges with a minimal
    hardcoded baseline so the module works even if the data file is absent.
    """
    baseline = frozenset({
        "probiotic",
        "lactobacillus",
        "bifidobacterium",
        "streptococcus",
        "bacillus",
        "saccharomyces",
        "limosilactobacillus",
        "lacticaseibacillus",
    })
    strains_path = os.path.join(
        os.path.dirname(__file__), "data", "clinically_relevant_strains.json"
    )
    try:
        with open(strains_path, encoding="utf-8") as fh:
            data = json.load(fh)
        strains = data.get("clinically_relevant_strains", [])
        derived: set[str] = set()
        for strain in strains:
            standard = strain.get("standard_name", "")
            if standard:
                derived.add(standard.split()[0].lower())
            for alias in strain.get("aliases", []):
                if alias:
                    first = alias.split()[0].lower()
                    # Only include multi-character words that look like genus names
                    # (start with uppercase in the source, len > 3 after lower)
                    if len(first) > 3:
                        derived.add(first)
        return baseline | frozenset(derived)
    except (OSError, json.JSONDecodeError, KeyError):
        return baseline


PROBIOTIC_TERMS: frozenset[str] = _load_probiotic_terms()

NON_SCORABLE_CATEGORIES = {
    "excipient",
    "additive",
    "inactive",
    "blend_header",
    "non_therapeutic",
}

# Legacy hardcoded alias map. SP-4 (2026-05-21): kept for backward compat /
# audit visibility, but `canonical_category()` no longer reads it. The
# canonical source of truth is `scripts/data/ingredient_category_vocab.json`,
# accessed via `ingredient_category_normalizer.canonicalize_ingredient_category`.
# Parity between this map and the vocab is locked by
# `test_ingredient_category_vocab.py::TestParityWithLegacy`.
CATEGORY_ALIASES = {
    "vitamin": "vitamin",
    "vitamins": "vitamin",
    "mineral": "mineral",
    "minerals": "mineral",
    "herb": "herb",
    "herbs": "herb",
    "botanical": "botanical",
    "botanicals": "botanical",
    "probiotic": "probiotic",
    "probiotics": "probiotic",
    "bacteria": "bacteria",
    "protein": "protein",
    "proteins": "protein",
    "fiber": "fiber",
    "fibers": "fiber",
    "fatty acid": "fatty_acid",
    "fatty acids": "fatty_acid",
    "fatty_acid": "fatty_acid",
    "fatty_acids": "fatty_acid",
    "amino acid": "amino_acid",
    "amino acids": "amino_acid",
    "amino_acid": "amino_acid",
    "amino_acids": "amino_acid",
    "enzyme": "enzyme",
    "enzymes": "enzyme",
    "antioxidant": "antioxidant",
    "antioxidants": "antioxidant",
    "functional food": "functional_food",
    "functional foods": "functional_food",
    "functional_food": "functional_food",
    "functional_foods": "functional_food",
}


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def canonical_category(value: Any) -> str:
    """Return the canonical ingredient-category id for a raw value.

    SP-4 (2026-05-21): now a thin wrapper around the SP-4 normalizer
    which reads `scripts/data/ingredient_category_vocab.json`. The legacy
    CATEGORY_ALIASES map above is retained for audit / migration parity
    but no longer drives canonicalization. Callers do not need to change
    — output is identical for every alias the legacy map handled (locked
    by test_ingredient_category_vocab.TestParityWithLegacy).
    """
    from ingredient_category_normalizer import canonicalize_ingredient_category
    return canonicalize_ingredient_category(value)


def _ingredient_name(row: dict[str, Any]) -> str:
    return _normalize_text(
        row.get("standard_name")
        or row.get("standardName")
        or row.get("name")
        or row.get("raw_source_text")
    )


# Canonicals where the dual-declaration pattern applies: DRI vitamins and
# minerals, whose Supplement Facts row is the FDA-mandated ELEMENTAL amount
# while a sibling row may restate the source compound's weight ("Magnesium
# Glycinate 400 mg"). Outside this set — probiotic strains ("Lactobacillus
# Acidophilus LA-14" beside a bare species row), botanicals ("Turmeric
# Extract" beside "Turmeric") — name-extension siblings can be genuinely
# additive and must NOT be marked.
_DRI_DUAL_DECLARATION_CANONICALS = frozenset({
    "copper", "zinc", "selenium", "iodine", "chromium", "molybdenum",
    "manganese", "iron", "calcium", "magnesium", "potassium", "phosphorus",
    "chloride", "sodium", "boron",
    "vitamin_a", "vitamin_c", "vitamin_d", "vitamin_d3", "vitamin_e",
    "vitamin_k", "vitamin_k1", "vitamin_k2",
    "vitamin_b1", "vitamin_b2", "vitamin_b3", "vitamin_b5", "vitamin_b6",
    "vitamin_b12", "folate", "biotin", "choline",
})


def mark_compound_duplicate_rows(rows: list[Any]) -> list[dict[str, Any]]:
    """Mark dual-declaration compound rows with ``is_compound_duplicate=True``.

    Mineral labels frequently declare the same nutrient twice: once as the
    bare elemental nutrient ("Magnesium" 60 mg — the Supplement Facts
    elemental value) and once as compound weight ("Magnesium Glycinate"
    400 mg — the source material restated). These are ONE ingredient stated
    two ways, not two additive sources. Without this marker downstream
    consumers double-count: UL aggregation sums 60+400=460 mg (false
    over-UL flag), supplement-type counting sees 2 actives (demoting a
    single to 'targeted'), and formulation scoring loses its
    single-ingredient floors/A6.

    A compound row is marked only when the canonical is a DRI vitamin or
    mineral (``_DRI_DUAL_DECLARATION_CANONICALS``) and, within the same
    ``canonical_id`` group of top-level non-blend rows:
      - a bare row exists whose normalized label name equals the canonical
        nutrient name AND carries a positive quantity (the elemental row
        must be able to "win"), and
      - the sibling row has a different literal label name. The declared bare
        nutrient total owns same-canonical source compounds even when the
        compound name leads with a counterion (for example, Calcium Ascorbate
        as the source of a declared Vitamin C total).
    Genuinely additive multi-form labels with no bare elemental row
    (e.g. beta-carotene + retinyl palmitate) are untouched.

    Idempotent. Returns the rows that are marked.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        if bool(row.get("is_nested_ingredient")) or bool(row.get("is_parent_total")):
            continue
        if bool(row.get("is_proprietary_blend")) or bool(row.get("is_blend_header")):
            continue
        canonical_id = str(row.get("canonical_id") or "").strip().lower()
        if not canonical_id:
            continue
        groups.setdefault(canonical_id, []).append(row)

    marked: list[dict[str, Any]] = []
    for canonical_id, group in groups.items():
        if canonical_id not in _DRI_DUAL_DECLARATION_CANONICALS:
            continue
        if len(group) < 2:
            continue
        canonical_name = _normalize_text(canonical_id.replace("_", " "))
        if not canonical_name:
            continue

        def _row_qty(row: dict[str, Any]) -> float:
            try:
                return float(row.get("quantity") or 0)
            except (TypeError, ValueError):
                return 0.0

        bare_rows = [
            row for row in group
            if _normalize_text(row.get("name")) == canonical_name
            and _row_qty(row) > 0
        ]
        if not bare_rows:
            continue
        for row in group:
            name = _normalize_text(row.get("name"))
            if name != canonical_name:
                row["is_compound_duplicate"] = True
                marked.append(row)
    return marked
