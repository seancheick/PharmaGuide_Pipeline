#!/usr/bin/env python3
"""
Protein-supplement preservation in cleaner (Batch 14a).

37 protein-supplement products (whey, casein, collagen, plant protein)
were misrouted to NUTRITION_ONLY because the cleaner treats `category=protein`
+ `unit=Gram(s)` as a Nutrition Facts panel disclosure (the 5g protein on
a multivitamin) regardless of dose magnitude. Result: products with 24g
of whey protein per serving lost their active and got NUTRITION_ONLY verdict.

Disambiguator: dose magnitude. A panel disclosure shows 1-7g protein per
serving (incidental). A protein supplement shows 10-30g per serving.
Threshold ≥10g per serving routes the row as a real supplement-active.

Calorie units stay strictly excluded (panel-only signal).
"""

import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
logging.disable(logging.CRITICAL)

from enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: E402


@pytest.fixture(scope="module")
def normalizer():
    return EnhancedDSLDNormalizer()


def _normalize_one_active(normalizer, ingredient_row):
    raw = {
        "id": "TEST",
        "fullName": "Test Product",
        "offMarket": 0,
        "events": [],
        "ingredientRows": [ingredient_row],
        "otherIngredients": {"ingredients": []},
    }
    return normalizer.normalize_product(raw)


# ---------------------------------------------------------------------------
# Real protein supplements at supplement-magnitude doses preserved
# ---------------------------------------------------------------------------


def test_whey_protein_24g_preserved(normalizer):
    """GNC 100% Whey Vanilla Cream — 24g protein per serving — must NOT
    be filtered as a nutrition-panel disclosure."""
    out = _normalize_one_active(normalizer, {
        "name": "Protein",
        "category": "protein",
        "quantity": [{"quantity": 24, "unit": "Gram(s)"}],
        "forms": [],
    })
    assert len(out["activeIngredients"]) == 1, (
        "Protein at 24g per serving must be preserved as supplement active"
    )


def test_whey_protein_isolate_named_form_preserved(normalizer):
    """Even with a named ingredient like 'Whey Protein Isolate', the
    category-based check must let it through at supplement doses."""
    out = _normalize_one_active(normalizer, {
        "name": "Whey Protein Isolate",
        "category": "protein",
        "quantity": [{"quantity": 25, "unit": "Gram(s)"}],
        "forms": [],
    })
    assert len(out["activeIngredients"]) == 1


def test_collagen_peptides_11g_preserved(normalizer):
    """Nutricost Collagen Hydrolysate 11g — supplement dose, must preserve."""
    out = _normalize_one_active(normalizer, {
        "name": "Collagen Hydrolysate",
        "category": "protein",
        "quantity": [{"quantity": 11, "unit": "Gram(s)"}],
        "forms": [],
    })
    assert len(out["activeIngredients"]) == 1


def test_protein_at_threshold_10g_preserved(normalizer):
    """10g is the threshold — exactly 10g must be preserved (boundary)."""
    out = _normalize_one_active(normalizer, {
        "name": "Plant Protein Blend",
        "category": "protein",
        "quantity": [{"quantity": 10, "unit": "Gram(s)"}],
        "forms": [],
    })
    assert len(out["activeIngredients"]) == 1


# ---------------------------------------------------------------------------
# Genuine Nutrition-Facts protein disclosures still filtered
# ---------------------------------------------------------------------------


def test_protein_5g_panel_disclosure_filtered(normalizer):
    """Multivitamin gummy with 5g protein content disclosure — panel only,
    must STILL be filtered as nutrition-panel data."""
    out = _normalize_one_active(normalizer, {
        "name": "Protein",
        "category": "protein",
        "quantity": [{"quantity": 5, "unit": "Gram(s)"}],
        "forms": [],
    })
    assert len(out["activeIngredients"]) == 0


def test_protein_2g_panel_disclosure_filtered(normalizer):
    """Energy bar with 2g protein content — clear panel disclosure."""
    out = _normalize_one_active(normalizer, {
        "name": "Protein",
        "category": "protein",
        "quantity": [{"quantity": 2, "unit": "Gram(s)"}],
        "forms": [],
    })
    assert len(out["activeIngredients"]) == 0


def test_protein_no_quantity_filtered_as_panel(normalizer):
    """Without a parsable quantity, default to panel-disclosure (safer)."""
    out = _normalize_one_active(normalizer, {
        "name": "Protein",
        "category": "protein",
        "quantity": [],
        "forms": [],
    })
    assert len(out["activeIngredients"]) == 0


# ---------------------------------------------------------------------------
# Other category panel rows unaffected
# ---------------------------------------------------------------------------


def test_total_carbs_5g_still_filtered(normalizer):
    """Carbs are NEVER a supplement active — must always filter."""
    out = _normalize_one_active(normalizer, {
        "name": "Total Carbohydrates",
        "category": "carbohydrate",
        "quantity": [{"quantity": 5, "unit": "Gram(s)"}],
        "forms": [],
    })
    assert len(out["activeIngredients"]) == 0


def test_total_carbs_30g_still_filtered(normalizer):
    """Even 30g carbs (energy bar) — STILL filter — only protein has the
    threshold-based bypass."""
    out = _normalize_one_active(normalizer, {
        "name": "Total Carbohydrates",
        "category": "carbohydrate",
        "quantity": [{"quantity": 30, "unit": "Gram(s)"}],
        "forms": [],
    })
    assert len(out["activeIngredients"]) == 0
