from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer


def _row(name: str, amount: float, unit: str) -> dict:
    return {"name": name, "quantity": amount, "unit": unit}


def test_panel_fats_and_cholesterol_are_retained_in_nutritional_info() -> None:
    normalizer = EnhancedDSLDNormalizer()

    info = normalizer._extract_nutritional_info([
        _row("Total Fat", 5, "g"),
        _row("Saturated Fat", 2, "g"),
        _row("Trans Fat", 0, "g"),
        _row("Cholesterol", 15, "mg"),
    ])

    assert info["totalFat"] == {"amount": 5.0, "unit": "g"}
    assert info["saturatedFat"] == {"amount": 2.0, "unit": "g"}
    assert info["transFat"] == {"amount": 0.0, "unit": "g"}
    assert info["cholesterol"] == {"amount": 15.0, "unit": "mg"}


def test_sugar_capture_preserves_source_qualifier_and_serving_columns() -> None:
    normalizer = EnhancedDSLDNormalizer()
    rows = [{"name": "Total Carbohydrates", "quantity": 4, "unit": "g", "nestedRows": [{
        "name": "Total Sugars", "quantity": [
            {"quantity": 1, "unit": "g", "operator": "<", "servingSizeOrder": 1},
            {"quantity": 3, "unit": "g", "operator": "=", "servingSizeOrder": 2},
        ],
    }]}]
    sugar = normalizer._extract_nutritional_info(rows)["sugars"]
    assert sugar["raw_source_path"] == "ingredientRows[0].nestedRows[0]"
    assert [(v["quantity"], v["operator"], v["serving_size_order"]) for v in sugar["quantityVariants"]] == [
        (1.0, "<", 1), (3.0, "=", 2),
    ]


def test_nutrition_summary_distinguishes_declared_zero_from_missing() -> None:
    from enrich_supplements_v3 import SupplementEnricherV3

    enricher = SupplementEnricherV3()
    assert enricher._collect_nutrition_summary({"nutritionalInfo": {"sugars": {"amount": 0, "unit": "g"}}})["total_sugars_g"] == 0.0
    for entry in [None, {"amount": 0, "unit": "unspecified"}, {"amount": 0, "unit": "NP"}, {"amount": None, "unit": "g"}]:
        assert enricher._collect_nutrition_summary({"nutritionalInfo": {"sugars": entry}})["total_sugars_g"] is None


def test_unparsed_sugar_quantity_does_not_become_a_declared_zero() -> None:
    from enrich_supplements_v3 import SupplementEnricherV3

    normalizer = EnhancedDSLDNormalizer()
    info = normalizer._extract_nutritional_info([
        {"name": "Total Sugars", "quantity": [{"quantity": "not reported", "unit": "g"}]},
    ])
    assert info["sugars"]["quantityVariants"][0]["quantity_parsed"] is False
    assert SupplementEnricherV3()._collect_nutrition_summary({"nutritionalInfo": info})["total_sugars_g"] is None


def test_nested_sugar_alcohol_is_not_a_total_sugar_declaration() -> None:
    info = EnhancedDSLDNormalizer()._extract_nutritional_info([
        {"name": "Total Carbohydrates", "quantity": 4, "unit": "g", "nestedRows": [
            {"name": "Sugar Alcohols", "quantity": 3, "unit": "g"},
        ]},
    ])
    assert "sugars" not in info


def test_sugar_bound_keeps_its_stated_amount_beside_its_operator() -> None:
    from enrich_supplements_v3 import SupplementEnricherV3

    normalizer = EnhancedDSLDNormalizer()
    info = normalizer._extract_nutritional_info([
        {"name": "Total Sugars", "quantity": [{"quantity": 1, "unit": "g", "operator": "<"}]},
    ])
    assert info["sugars"]["amount"] == 1.0
    assert info["sugars"]["quantityVariants"][0]["operator"] == "<"
    # The stated bound stays beside its operator; the export shows "<1 g".
    summary = SupplementEnricherV3()._collect_nutrition_summary({"nutritionalInfo": info})
    assert summary["total_sugars_g"] == 1.0
    assert summary["quantity_operators"] == {"total_sugars_g": "<"}


def test_nested_sugar_mixture_is_not_a_total_sugar_declaration() -> None:
    info = EnhancedDSLDNormalizer()._extract_nutritional_info([
        {"name": "Total Carbohydrates", "quantity": 4, "unit": "g", "nestedRows": [
            {"name": "Sugar Alcohols and Sugars", "quantity": 3, "unit": "g"},
        ]},
    ])
    assert "sugars" not in info
