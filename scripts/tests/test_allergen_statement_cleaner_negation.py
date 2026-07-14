"""Cleaner allergen-statement regressions (review finding C3)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


def _clean(normalizer: EnhancedDSLDNormalizer, statement: str) -> dict:
    return normalizer.normalize_product({
        "id": "allergen-statement-regression",
        "fullName": "Allergen Statement Regression",
        "brandName": "Test",
        "ingredientRows": [{
            "name": "Vitamin C",
            "quantity": [{"quantity": 100, "unit": "mg"}],
        }],
        "statements": [{"text": statement}],
    })


def test_contains_no_list_does_not_create_positive_allergens(normalizer) -> None:
    cleaned = _clean(normalizer, "Contains no milk, soy, wheat, or eggs.")

    assert cleaned["labelText"]["parsed"]["allergens"] == []


def test_milk_thistle_ingredient_phrase_is_not_a_milk_warning(normalizer) -> None:
    cleaned = _clean(normalizer, "Contains milk thistle extract.")

    assert "milk" not in cleaned["labelText"]["parsed"]["allergens"]
