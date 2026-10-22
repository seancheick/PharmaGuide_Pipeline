"""A reviewer-typed Nutrition Facts value survives Clean.

The submission console writes DSLD's raw ``nutritionalInfo`` shape when a
reviewer types a printed Calories/Fat/Carbohydrate/Fiber/Sugars/Protein/Sodium
value. Clean used to rebuild ``nutritionalInfo`` from ingredient rows only, so
an approved submission label with ``calories: 20 kcal`` (submission S03,
2026-10-22) lost the value at Clean. A printed panel row still wins when both
exist; a malformed typed entry is never invented into a value.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer

_BASE = {
    "id": "submission-probe",
    "fullName": "Creatine Monohydrate",
    "brandName": "Probe",
    "productType": {"langualCodeDescription": "Non-Nutrient/Non-Botanical"},
    "physicalState": {"langualCodeDescription": "Powder"},
    "servingSizes": [{"minQuantity": 1, "maxQuantity": 1, "unit": "Scoop", "order": 1}],
    "servingsPerContainer": 60,
    "statements": [],
    "claims": [],
    "otheringredients": {"ingredients": []},
    "ingredientRows": [{
        "order": 1, "name": "Micronized Creatine Monohydrate", "ingredientGroup": "Creatine",
        "category": "amino acid", "forms": [], "nestedRows": [],
        "quantity": [{"servingSizeOrder": 1, "servingSizeQuantity": 1, "operator": "=",
                      "quantity": 5, "unit": "g", "dailyValueTargetGroup": []}],
    }],
}


def _calories_row(amount: float) -> dict:
    return {
        "order": 0, "name": "Calories", "ingredientGroup": "Calories", "category": "other",
        "forms": [], "nestedRows": [],
        "quantity": [{"servingSizeOrder": 1, "servingSizeQuantity": 1, "operator": "=",
                      "quantity": amount, "unit": "Calories", "dailyValueTargetGroup": []}],
    }


def _clean(product: dict) -> dict:
    return EnhancedDSLDNormalizer().normalize_product(product)["nutritionalInfo"]


def test_reviewer_typed_calories_survive_clean() -> None:
    product = copy.deepcopy(_BASE)
    product["nutritionalInfo"] = {
        "calories": {"amount": 20, "unit": "kcal"},
        "protein": {"amount": 0, "unit": "g"},
    }
    info = _clean(product)
    assert info["calories"] == {"amount": 20.0, "unit": "kcal"}
    assert info["protein"] == {"amount": 0.0, "unit": "g"}


def test_printed_panel_row_wins_over_a_typed_value() -> None:
    product = copy.deepcopy(_BASE)
    product["ingredientRows"].insert(0, _calories_row(20))
    product["nutritionalInfo"] = {"calories": {"amount": 25, "unit": "kcal"}}
    assert _clean(product)["calories"]["amount"] == 20.0


def test_malformed_typed_entries_are_not_invented() -> None:
    product = copy.deepcopy(_BASE)
    product["nutritionalInfo"] = {
        "calories": {"amount": "twenty", "unit": "kcal"},
        "totalFat": {"amount": 1},
        "sodium": None,
        "sugars": {"amount": float("nan"), "unit": "g"},
    }
    info = _clean(product)
    for key in ("calories", "totalFat", "sodium", "sugars"):
        assert key not in info
