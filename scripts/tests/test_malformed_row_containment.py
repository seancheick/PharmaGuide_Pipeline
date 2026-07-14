"""Malformed label rows remain local failures (review finding H6)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


def test_non_mapping_nutrition_row_does_not_erase_valid_nutrients(normalizer) -> None:
    result = normalizer._extract_nutritional_info([
        {"name": "Calories", "quantity": 120, "unit": "Calories"},
        "malformed row",
        {"name": "Sodium", "quantity": 140, "unit": "mg"},
    ])

    assert result["calories"]["amount"] == 120
    assert result["sodium"]["amount"] == 140


def test_non_mapping_nested_row_does_not_erase_valid_nested_nutrient(normalizer) -> None:
    result = normalizer._extract_nutritional_info([
        {
            "name": "Total Carbohydrate",
            "quantity": 5,
            "unit": "g",
            "nestedRows": [
                "malformed nested row",
                {"name": "Dietary Fiber", "quantity": 3, "unit": "g"},
            ],
        }
    ])

    assert result["dietaryFiber"]["amount"] == 3
