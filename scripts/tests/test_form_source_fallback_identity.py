"""Printed source text must not become a different chemical form."""

import copy

import pytest

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


@pytest.mark.parametrize("form,expected", [
    ("d-alpha-tocopherol from sunflower oil", "d-alpha-tocopherol"),
    ("d-alpha-tocopheryl acetate from sunflower oil", "d-alpha-tocopheryl acetate"),
    ("dl-alpha-tocopherol from a synthetic source", "dl-alpha-tocopherol"),
])
@pytest.mark.parametrize("structured", [True, False])
def test_source_qualified_tocopherol_keeps_printed_chemical_form(
    enricher, form, expected, structured
):
    product = {
        "id": "form-source-regression",
        "product_name": "Vitamin E",
        "activeIngredients": [{
            "name": "Vitamin E" if structured else f"Vitamin E (as {form})",
            "standardName": "Vitamin E",
            "canonical_id": "vitamin_e",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 12, "unit": "mg",
            "forms": [{"name": form}] if structured else [],
        }],
        "inactiveIngredients": [],
    }
    original = copy.deepcopy(product)
    enriched, errors = enricher.enrich_product(product)
    assert errors == []
    row = enriched["ingredient_quality_data"]["ingredients"][0]
    assert row["form_id"] == expected
    assert "wheat" not in str(row).lower()
    for key in ("name", "quantity", "unit", "forms"):
        assert enriched["activeIngredients"][0][key] == original["activeIngredients"][0][key]
