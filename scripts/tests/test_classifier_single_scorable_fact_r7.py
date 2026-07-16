"""Phase 0d R7a — `is_single_scorable_active`, the canonical single fact.

WHY THIS EXISTS
    §3 of SUPP_TYPE_CONSOLIDATION_PLAN.md names the proven scoring split:
    `generic_formulation.py` gates the A6 focus bonus and the premium/standard
    single floors on the LEGACY `supp_type_of()` + `SINGLE_INGREDIENT_SUPP_TYPES`.
    Phase 1 replaces that with a fact the taxonomy emits. This is that fact.

    It must NOT be derived from the type name. Measured: 346 products are
    `single_mineral`/`single_vitamin` while carrying 2+ DISTINCT identities
    (223 + 123) — a 3-mineral blend is called `single_mineral` while its own
    reason string says "mineral combo". Anything reading the type name would
    hand all 346 a single-ingredient bonus.

THE CONTRACT (plan §9)
    "is_single_scorable_active = true only when there is exactly one
     score-eligible active AND no second unresolved quantified active."
    Otherwise a product with one mapped + one unmapped active would incorrectly
    receive single-ingredient bonuses.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from supplement_taxonomy import classify_supplement  # noqa: E402


def _row(name, canonical_id, category, qty=100.0, unit="mg", **extra):
    row = {
        "name": name, "canonical_id": canonical_id, "standard_name": name,
        "category": category, "quantity": qty, "unit": unit, "mapped": True,
        "role_classification": "active_scorable",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "source_section": "active",
        "raw_source_path": f"ingredientRows[{name}]",
        "dose_class": "therapeutic_mass",
        "scoreable_identity": bool(canonical_id),
        "mapped_identity": bool(canonical_id),
        "identity_disposition": "clean" if canonical_id else "unresolved",
    }
    row.update(extra)
    return row


def _product(name, rows):
    scorable = [row for row in rows if row.get("mapped") is not False]
    unresolved = []
    for row in rows:
        if row.get("mapped") is not False:
            continue
        unresolved_row = dict(row)
        unresolved_row.update({
            "role_classification": "active_unmapped",
            "skip_reason": "no_quality_map_match",
            "has_dose": True,
        })
        unresolved.append(unresolved_row)
    return {
        "dsld_id": 930001, "product_name": name, "fullName": name,
        "ingredient_quality_data": {
            "ingredients_scorable": scorable,
            "ingredients": scorable + unresolved,
            "ingredients_skipped": unresolved,
        },
        "probiotic_data": {"is_probiotic_product": False, "total_cfu": 0},
    }


def test_one_scorable_active_is_single():
    taxonomy = classify_supplement(_product("Magnesium Glycinate", [
        _row("Magnesium Glycinate", "magnesium", "mineral", 200.0),
    ]))
    assert taxonomy["is_single_scorable_active"] is True
    assert taxonomy["scorable_active_count"] == 1


def test_two_forms_of_one_nutrient_are_still_single():
    """R1's dedup must carry into the fact: niacin + niacinamide is ONE
    ingredient in two forms, so the single-ingredient floors still apply."""
    taxonomy = classify_supplement(_product("Vitamin B3", [
        _row("Niacin", "vitamin_b3", "vitamin", 20.0),
        _row("Niacinamide", "vitamin_b3", "vitamin", 630.0),
    ]))
    assert taxonomy["is_single_scorable_active"] is True
    assert taxonomy["scorable_active_count"] == 1


def test_three_distinct_minerals_are_not_single():
    """§7 #5 / the 346. The type name may still say single_mineral (R7b is a
    vocabulary decision), but the FACT must not."""
    taxonomy = classify_supplement(_product("Cal Mag Zinc", [
        _row("Calcium", "calcium", "mineral", 500.0),
        _row("Magnesium", "magnesium", "mineral", 250.0),
        _row("Zinc", "zinc", "mineral", 15.0),
    ]))
    assert taxonomy["scorable_active_count"] == 3
    assert taxonomy["is_single_scorable_active"] is False, (
        "a 3-mineral blend would receive a single-ingredient scoring bonus"
    )


def test_the_fact_is_not_derived_from_the_type_name():
    """The whole point: 346 products claim a single_* type with 2+ identities."""
    taxonomy = classify_supplement(_product("Cal Mag Zinc", [
        _row("Calcium", "calcium", "mineral", 500.0),
        _row("Magnesium", "magnesium", "mineral", 250.0),
        _row("Zinc", "zinc", "mineral", 15.0),
    ]))
    if taxonomy["primary_type"] == "single_mineral":
        assert taxonomy["is_single_scorable_active"] is False, (
            "the fact tracked the type NAME instead of the evidence — this is "
            "exactly the bug Phase 1 depends on not having"
        )


def test_one_mapped_plus_one_unresolved_active_is_not_single():
    """The plan's explicit carve-out: 'a product with one mapped + one unmapped
    active would incorrectly receive single-ingredient bonuses'."""
    taxonomy = classify_supplement(_product("Magnesium + Mystery Herb", [
        _row("Magnesium Glycinate", "magnesium", "mineral", 200.0),
        _row("Proprietary Herb", "", "botanical", 300.0, mapped=False),
    ]))

    assert taxonomy["scorable_active_count"] == 1
    assert taxonomy["unresolved_quantified_active_count"] == 1
    assert taxonomy["is_single_scorable_active"] is False, (
        "one score-eligible active plus an unresolved second active is NOT a "
        "single-ingredient product"
    )


def test_zero_actives_is_not_single():
    taxonomy = classify_supplement(_product("Empty", []))
    assert taxonomy["is_single_scorable_active"] is False
    assert taxonomy["scorable_active_count"] == 0


def test_quantified_label_active_count_includes_unresolved():
    """The two populations stay distinct: classification sees the unmapped
    active, scoring does not."""
    taxonomy = classify_supplement(_product("Magnesium + Mystery Herb", [
        _row("Magnesium Glycinate", "magnesium", "mineral", 200.0),
        _row("Proprietary Herb", "", "botanical", 300.0, mapped=False),
    ]))
    assert taxonomy["quantified_label_active_count"] == 2
    assert taxonomy["scorable_active_count"] == 1


def test_decorative_np_row_does_not_defeat_single():
    taxonomy = classify_supplement(_product("Magnesium Glycinate", [
        _row("Magnesium Glycinate", "magnesium", "mineral", 200.0),
        _row("Rice Flour", "rice_flour", "excipient", 0.0, unit="NP"),
    ]))
    assert taxonomy["is_single_scorable_active"] is True
