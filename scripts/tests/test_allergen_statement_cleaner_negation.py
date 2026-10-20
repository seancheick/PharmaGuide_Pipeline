"""Cleaner allergen-statement regressions (review finding C3)."""

from __future__ import annotations

import json
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
        "statements": [{"text": statement, "notes": statement}],
    })


def test_contains_no_list_does_not_create_positive_allergens(normalizer) -> None:
    cleaned = _clean(normalizer, "Contains no milk, soy, wheat, or eggs.")

    assert cleaned["labelText"]["parsed"]["allergens"] == []


def test_milk_thistle_ingredient_phrase_is_not_a_milk_warning(normalizer) -> None:
    cleaned = _clean(normalizer, "Contains milk thistle extract.")

    assert "milk" not in cleaned["labelText"]["parsed"]["allergens"]


@pytest.mark.parametrize("statement,expected", [
    ("Processed in a facility with products that may contain soy, egg, peanuts, tree nuts, milk, shellfish and wheat.", set()),
    ("May contain milk and soy.", set()),
    ("Contains: chocolate made with milk.", {"milk"}),
    ("Manufactured in a facility that contains milk and soy.", set()),
    ("Contains: Milk, Soy", {"milk", "soy"}),
    ("Made in a dedicated facility, contains milk", {"milk"}),
    ("Contains milk and not  manufactured in a facility that processes soy", {"milk"}),
    ("Contains milk, packaged in a facility that processes soy", {"milk"}),
    ("Allergy information\nContains:\nMilk, Soy", {"milk", "soy"}),
    ("Contains milk and may contain soy.", {"milk"}),
    ("Contains: Tree nuts (coconut)", {"tree nuts"}),
])
def test_cross_contact_is_not_a_positive_declaration(normalizer, statement, expected):
    cleaned = _clean(normalizer, statement)
    assert set(cleaned["labelText"]["parsed"]["allergens"]) == expected


def test_contains_declaration_stops_before_facility_clause(normalizer):
    cleaned = _clean(normalizer, "Contains: Fish (tuna)\nProcessed in a facility with products that may contain soy, egg, peanuts, tree nuts, milk, shellfish and wheat.")
    assert set(cleaned["labelText"]["parsed"]["allergens"]) == {"fish"}


@pytest.mark.parametrize("product_id,expected", [
    ("230194", {"fish"}),
    ("1060", {"milk", "soy", "wheat"}),
    ("248755", {"soy"}),
    ("222850", {"tree nuts"}),
])
def test_frozen_raw_declaration_keeps_only_actual_contains(normalizer, product_id, expected):
    raw = json.loads((Path(__file__).parent / "fixtures" /
                      f"allergen_declaration_{product_id}_raw.json").read_text())
    cleaned = normalizer.normalize_product(raw)
    assert set(cleaned["labelText"]["parsed"]["allergens"]) == expected
