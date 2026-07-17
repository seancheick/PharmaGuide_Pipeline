"""Phase 0d R1 — classification counts distinct IDENTITIES, not label rows.

THE DEFECT
    `classify_supplement` set `active_count = len(quantified_rows)`, so a label
    that declares ONE nutrient twice counted as TWO actives. That drops the
    product into the `active_count == 2` band, which has no vocabulary and emits
    `general_supplement` with NOTHING:

        242284 "Vitamin B3"                  rows=2 identities=1 -> gs @0.0 reasons=[]
        252532 "Choline L-Bitartrate 600 mg" rows=2 identities=1 -> gs @0.0 reasons=[]
        269490 "Pure Collagen Types 1 and 3" rows=2 identities=1 -> gs @0.0 reasons=[]

    503 products reached `general_supplement` with EMPTY reasons this way,
    violating the plan's §10 gate ("`general_supplement` reasons are never
    empty"). A product named "Vitamin B3" was unclassified with no stated reason.

WHY NOT `mark_compound_duplicate_rows` (which RC2 prescribed)
    Measured: the helper collapses only 19 of those 503; counting distinct
    identities collapses 216. The helper answers a DOSE question — "is this row
    a restatement of the same amount, so don't sum it?" — and it deliberately
    leaves genuinely additive multi-form labels alone. Niacin + niacinamide are
    two additive DOSES of one IDENTITY: the dose path must sum them, and the
    classifier must see one ingredient. Using the dose helper to count identities
    is a category error, which is exactly why it under-reaches.

    The helper stays where it belongs (enrich's UL path); this does not touch it.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from supplement_taxonomy import classify_supplement  # noqa: E402


def _row(name, canonical_id, category, qty=100.0, unit="mg", **extra):
    row = {
        "name": name,
        "canonical_id": canonical_id,
        "standard_name": name,
        "category": category,
        "quantity": qty,
        "unit": unit,
        "mapped": True,
        "role_classification": "active_scorable",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "raw_source_path": f"activeIngredients[{name}]",
    }
    row.update(extra)
    return row


def _product(name, rows):
    return {
        "dsld_id": 960001,
        "product_name": name,
        "fullName": name,
        "ingredient_quality_data": {"ingredients_scorable": rows},
        "probiotic_data": {"is_probiotic_product": False, "total_cfu": 0},
    }


# ---------------------------------------------------------------------------
# One nutrient declared twice is ONE active
# ---------------------------------------------------------------------------


def test_two_forms_of_one_vitamin_are_one_identity():
    """The 242284 "Vitamin B3" shape: niacin + niacinamide, both vitamin_b3.
    Two additive doses, one ingredient."""
    taxonomy = classify_supplement(_product("Vitamin B3", [
        _row("Niacin", "vitamin_b3", "vitamin", 20.0),
        _row("Niacinamide", "vitamin_b3", "vitamin", 630.0),
    ]))

    assert taxonomy["distinct_active_identity_count"] == 1
    assert taxonomy["quantified_active_count"] == 1, (
        "the classifier still counts label rows instead of identities"
    )
    assert taxonomy["quantified_active_row_count"] == 2, (
        "the raw row count must remain available as a diagnostic"
    )
    assert taxonomy["primary_type"] == "single_vitamin"
    assert taxonomy["classification_reasons"], "§10: reasons must never be empty"


def test_elemental_plus_compound_salt_is_one_identity():
    """The 252532 "Choline L-Bitartrate" shape — the plan's cited RC2 case."""
    taxonomy = classify_supplement(_product("Choline L-Bitartrate 600 mg", [
        _row("Choline", "choline", "vitamin", 250.0),
        _row("Choline L-Bitartrate", "choline", "vitamin", 600.0),
    ]))

    assert taxonomy["distinct_active_identity_count"] == 1
    assert taxonomy["primary_type"] == "single_vitamin"


def test_collagen_types_i_and_iii_are_one_identity():
    """The 269490 "Pure Collagen Types 1 and 3" shape. mark_compound_duplicate_rows
    does NOT cover collagen (not a DRI canonical) — identity counting does."""
    taxonomy = classify_supplement(_product("Pure Collagen Types 1 and 3 Powder", [
        _row("Collagen Type I", "collagen", "protein", 5000.0),
        _row("Collagen Type III", "collagen", "protein", 5000.0),
    ]))

    assert taxonomy["distinct_active_identity_count"] == 1
    assert taxonomy["classification_reasons"], "§10: reasons must never be empty"
    assert taxonomy["classification_confidence"] > 0.0


# ---------------------------------------------------------------------------
# Near-miss negatives — distinct identities must stay distinct
# ---------------------------------------------------------------------------


def test_two_distinct_minerals_are_not_collapsed():
    """The R1 near-miss: magnesium + zinc are two ingredients, not one.

    R1's contract is the COUNT. What the branch then names the product is R7's
    contract — see the xfail below.
    """
    taxonomy = classify_supplement(_product("Mag + Zinc", [
        _row("Magnesium Glycinate", "magnesium", "mineral", 200.0),
        _row("Zinc Picolinate", "zinc", "mineral", 15.0),
    ]))

    assert taxonomy["distinct_active_identity_count"] == 2
    assert taxonomy["quantified_active_count"] == 2


def test_r7_distinct_identities_must_not_yield_a_single_type():
    taxonomy = classify_supplement(_product("Mag + Zinc", [
        _row("Magnesium Glycinate", "magnesium", "mineral", 200.0),
        _row("Zinc Picolinate", "zinc", "mineral", 15.0),
    ]))
    assert taxonomy["primary_type"] == "mineral_complex"


def test_unresolved_rows_each_count_as_their_own_identity():
    """Rows with no canonical id cannot be proven to be the same ingredient, so
    they must not be merged. Conservative: never under-count actives."""
    taxonomy = classify_supplement(_product("Mystery Blend", [
        _row("Mystery Herb A", "", "botanical", 300.0),
        _row("Mystery Herb B", "", "botanical", 300.0),
    ]))

    assert taxonomy["distinct_active_identity_count"] == 2


# ---------------------------------------------------------------------------
# Invariance
# ---------------------------------------------------------------------------


def test_row_order_does_not_change_the_collapse():
    rows = [
        _row("Niacin", "vitamin_b3", "vitamin", 20.0),
        _row("Niacinamide", "vitamin_b3", "vitamin", 630.0),
    ]
    forward = classify_supplement(_product("Vitamin B3", list(rows)))
    reverse = classify_supplement(_product("Vitamin B3", list(reversed(rows))))

    assert forward["distinct_active_identity_count"] == reverse["distinct_active_identity_count"]
    assert forward["primary_type"] == reverse["primary_type"]


def test_decorative_zero_dose_sibling_does_not_resurrect_the_count():
    """A decorative NP sibling is excluded as non-quantified and must not make a
    single-ingredient product look like two."""
    taxonomy = classify_supplement(_product("Magnesium Glycinate", [
        _row("Magnesium Glycinate", "magnesium", "mineral", 200.0),
        _row("Magnesium Oxide", "magnesium", "mineral", 0.0, unit="NP"),
    ]))

    assert taxonomy["distinct_active_identity_count"] == 1
    assert taxonomy["primary_type"] == "single_mineral"


def test_identity_count_never_exceeds_the_row_count():
    taxonomy = classify_supplement(_product("Mag + Zinc", [
        _row("Magnesium Glycinate", "magnesium", "mineral", 200.0),
        _row("Zinc Picolinate", "zinc", "mineral", 15.0),
    ]))
    assert (
        taxonomy["distinct_active_identity_count"]
        <= taxonomy["quantified_active_row_count"]
    )
