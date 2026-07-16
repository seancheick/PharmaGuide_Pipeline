"""Phase 0d R4 — a multivitamin must contain vitamins.

THE DEFECT
    `multi_panel_signal` fires on `len(vitamin_ids) + len(mineral_ids) >= 6`
    with ZERO vitamins required, so a pure 6+-mineral panel becomes a
    "multivitamin". "Trace Minerals" and "Only Trace Minerals" are classified
    multivitamin today. A multivitamin with no vitamins is a contradiction, and
    it mis-seeds the multivitamin peer cohort.

THE RULE
    Require `len(vitamin_ids) >= 1` for the panel signal. A pure-mineral panel is
    not a multivitamin. Absent a `mineral_complex` vocabulary term (deferred with
    R6/R7b as a user decision), it falls to the reason-coded residual — an honest
    "not a multivitamin" rather than a wrong-specific label.

    Measured: 8 products. Small, but the gate is wrong in principle and the fix
    is a one-line bound.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from supplement_taxonomy import classify_supplement  # noqa: E402


def _row(name, canonical_id, category, qty=100.0, unit="mg"):
    return {
        "name": name, "canonical_id": canonical_id, "standard_name": name,
        "category": category, "quantity": qty, "unit": unit, "mapped": True,
        "role_classification": "active_scorable",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
    }


def _product(name, rows):
    return {
        "dsld_id": 910001, "product_name": name, "fullName": name,
        "ingredient_quality_data": {"ingredients_scorable": rows},
        "probiotic_data": {"is_probiotic_product": False, "total_cfu": 0},
    }


_SIX_MINERALS = [
    _row("Calcium", "calcium", "mineral", 200.0),
    _row("Magnesium", "magnesium", "mineral", 100.0),
    _row("Zinc", "zinc", "mineral", 15.0),
    _row("Selenium", "selenium", "mineral", 55.0),
    _row("Copper", "copper", "mineral", 0.9),
    _row("Manganese", "manganese", "mineral", 2.0),
]


def test_pure_mineral_panel_is_not_a_multivitamin():
    taxonomy = classify_supplement(_product("Trace Minerals", list(_SIX_MINERALS)))
    assert taxonomy["primary_type"] != "multivitamin", (
        "a panel with zero vitamins was classified multivitamin"
    )
    assert taxonomy["classification_reasons"], "§10: must still state a reason"


def test_one_vitamin_is_enough_to_be_a_multivitamin():
    """The near-miss: add a single vitamin and the panel is a real multivitamin
    again. Guards against over-correcting the bound."""
    rows = list(_SIX_MINERALS) + [_row("Vitamin D", "vitamin_d", "vitamin", 20.0)]
    taxonomy = classify_supplement(_product("Daily Multi", rows))
    assert taxonomy["primary_type"] == "multivitamin"


def test_real_multivitamin_is_unaffected():
    rows = [
        _row("Vitamin A", "vitamin_a", "vitamin", 900.0),
        _row("Vitamin C", "vitamin_c", "vitamin", 90.0),
        _row("Vitamin D", "vitamin_d", "vitamin", 20.0),
        _row("Vitamin E", "vitamin_e", "vitamin", 15.0),
        _row("Zinc", "zinc", "mineral", 11.0),
        _row("Selenium", "selenium", "mineral", 55.0),
    ]
    taxonomy = classify_supplement(_product("Complete Multivitamin", rows))
    assert taxonomy["primary_type"] == "multivitamin"
