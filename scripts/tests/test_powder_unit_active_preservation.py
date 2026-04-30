#!/usr/bin/env python3
"""
Powder-unit single-active preservation (Batch 5 cleaner bug fix).

Background: 429 single-active products (Creatine, L-Glutamine, MSM, D-Mannose,
Inositol, Beta-Sitosterol, Ribose, etc.) were silently dropped by the cleaner
because their dose is in Gram(s) — a unit shared with the Nutrition Facts
panel ("Total Carbohydrates: 5g"). The cleaner's _is_nutrition_fact() filter
returned True for any ingredient with `unit ∈ {Gram, Grams, Gram(s)}` BEFORE
checking whether DSLD's `category` field identifies the row as a real
supplement (non-nutrient/non-botanical, amino acid, etc.).

Fix: the unit-based panel-exclusion must respect the supplement-category
bypass that already exists for name-based exclusions.
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
# Single-active powders dosed in grams must be preserved
# ---------------------------------------------------------------------------


def test_creatine_powder_gram_unit_preserved(normalizer):
    """Pure Encapsulations Creatine Powder shape (DSLD 219648).

    DSLD raw: name='Creatine Monohydrate', category='non-nutrient/non-botanical',
    quantity=4 Gram(s), no forms, no nestedRows. Dosed at 4g per heaping scoop.
    Must NOT be filtered as nutrition-panel data.
    """
    out = _normalize_one_active(normalizer, {
        "name": "Creatine Monohydrate",
        "category": "non-nutrient/non-botanical",
        "quantity": [{"quantity": 4, "unit": "Gram(s)"}],
        "forms": [],
    })
    assert out["raw_actives_count"] == 1
    assert len(out["activeIngredients"]) == 1, (
        f"Creatine in Gram(s) was silently dropped — got {len(out['activeIngredients'])} actives"
    )
    assert out["activeIngredients"][0]["name"].lower().startswith("creatine")


def test_l_glutamine_powder_gram_unit_preserved(normalizer):
    out = _normalize_one_active(normalizer, {
        "name": "L-Glutamine",
        "category": "amino acid",
        "quantity": [{"quantity": 5, "unit": "Gram(s)"}],
        "forms": [],
    })
    assert len(out["activeIngredients"]) == 1, (
        "L-Glutamine in Gram(s) must not be dropped"
    )


def test_msm_powder_gram_unit_preserved(normalizer):
    out = _normalize_one_active(normalizer, {
        "name": "MSM",
        "category": "non-nutrient/non-botanical",
        "quantity": [{"quantity": 3, "unit": "Gram(s)"}],
        "forms": [],
    })
    assert len(out["activeIngredients"]) == 1, "MSM in Gram(s) must not be dropped"


def test_inositol_gram_unit_preserved(normalizer):
    out = _normalize_one_active(normalizer, {
        "name": "Inositol",
        "category": "non-nutrient/non-botanical",
        "quantity": [{"quantity": 2, "unit": "Gram(s)"}],
        "forms": [],
    })
    assert len(out["activeIngredients"]) == 1


def test_beta_sitosterol_gram_unit_preserved(normalizer):
    out = _normalize_one_active(normalizer, {
        "name": "Beta-Sitosterol",
        "category": "non-nutrient/non-botanical",
        "quantity": [{"quantity": 1, "unit": "Gram(s)"}],
        "forms": [],
    })
    assert len(out["activeIngredients"]) == 1


# ---------------------------------------------------------------------------
# Genuine Nutrition-Facts panel rows must STILL be filtered
# ---------------------------------------------------------------------------


def test_total_carbohydrates_still_filtered(normalizer):
    """Real nutrition-panel rows (no supplement category) MUST still be excluded."""
    out = _normalize_one_active(normalizer, {
        "name": "Total Carbohydrates",
        "category": "carbohydrate",
        "quantity": [{"quantity": 5, "unit": "Gram(s)"}],
        "forms": [],
    })
    assert len(out["activeIngredients"]) == 0, (
        "Total Carbohydrates is a Nutrition Facts panel row — must be filtered"
    )


def test_total_fat_still_filtered(normalizer):
    out = _normalize_one_active(normalizer, {
        "name": "Total Fat",
        "category": "fat",
        "quantity": [{"quantity": 2, "unit": "Gram(s)"}],
        "forms": [],
    })
    assert len(out["activeIngredients"]) == 0


def test_calories_still_filtered(normalizer):
    out = _normalize_one_active(normalizer, {
        "name": "Calories",
        "category": "calories",
        "quantity": [{"quantity": 30, "unit": "Calories"}],
        "forms": [],
    })
    assert len(out["activeIngredients"]) == 0


def test_total_sugars_still_filtered(normalizer):
    out = _normalize_one_active(normalizer, {
        "name": "Total Sugars",
        "category": "sugars",
        "quantity": [{"quantity": 4, "unit": "Gram(s)"}],
        "forms": [],
    })
    assert len(out["activeIngredients"]) == 0


# ---------------------------------------------------------------------------
# Mixed-category edge cases
# ---------------------------------------------------------------------------


def test_protein_with_supplement_category_preserved(normalizer):
    """Whey protein isolate dosed in grams — real supplement, not panel data."""
    out = _normalize_one_active(normalizer, {
        "name": "Whey Protein Isolate",
        "category": "non-nutrient/non-botanical",
        "quantity": [{"quantity": 25, "unit": "Gram(s)"}],
        "forms": [],
    })
    assert len(out["activeIngredients"]) == 1, (
        "Whey Protein Isolate as a category=non-nutrient/non-botanical "
        "supplement must not be filtered as nutrition-panel data"
    )


def test_protein_panel_disclosure_still_filtered(normalizer):
    """Bare 'Protein' row with category=protein and small dose is a panel
    disclosure — still filter.
    Updated 2026-04-29 (Batch 14a): supplement-magnitude threshold raised
    to 10g; panel disclosures use sub-10g quantities (typical 1-7g).
    """
    out = _normalize_one_active(normalizer, {
        "name": "Protein",
        "category": "protein",
        "quantity": [{"quantity": 5, "unit": "Gram(s)"}],
        "forms": [],
    })
    assert len(out["activeIngredients"]) == 0
