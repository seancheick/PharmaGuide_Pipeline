"""A row named for the nutrient declares the nutrient amount; its source salt is context.

Under 21 CFR 101.36 a Supplement Facts row such as "Magnesium 50 mg (as magnesium
hydroxide)" states 50 mg of magnesium. The active-moiety rules (choline bitartrate,
magnesium hydroxide, inositol hexanicotinate) are for rows that measure the
compound itself ("Magnesium Hydroxide 2.6 g"). They also fired on the disclosed
form, under-counting the declared nutrient (DSLD 1178: Magnesium 50 mg -> 20.8 mg;
200725: Choline 40 mg -> 16.5 mg; 12930: Niacin 20 mg -> 18.2 mg).
"""

import pytest

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _converted(enricher, name, canonical_id, quantity, unit, forms, daily_value):
    product = {
        "id": "declared-nutrient", "product_name": "test", "fullName": "test",
        "activeIngredients": [{
            "name": name, "standardName": name, "raw_source_text": name, "order": 1,
            "canonical_id": canonical_id, "canonical_source_db": "ingredient_quality_map",
            "quantity": quantity, "unit": unit, "dailyValue": daily_value,
            "forms": [{"name": f, "prefix": "as"} for f in forms],
        }],
        "inactiveIngredients": [],
        "servingSizes": [{"order": 1, "minQuantity": 1, "maxQuantity": 1, "unit": "Tablet(s)",
                          "minDailyServings": 1, "maxDailyServings": 1}],
    }
    enriched, errors = enricher.enrich_product(product)
    assert errors == []
    [row] = [r for r in enriched["rda_ul_data"]["ingredients_with_rda"] if r["canonical_id"] == canonical_id]
    return row["converted_quantity"]


@pytest.mark.parametrize("name,canonical_id,quantity,forms,daily_value", [
    ("Magnesium", "magnesium", 50, ["Magnesium Carbonate", "Magnesium Hydroxide"], 12),
    ("Magnesium", "magnesium", 300, ["Magnesium Hydroxide"], None),
    ("Choline", "choline", 40, ["Choline Bitartrate"], 7),
    ("Niacin", "vitamin_b3_niacin", 20, ["Inositol Niacinate"], 125),
    ("Choline (as Choline Bitartrate)", "choline", 40, [], 7),
])
def test_nutrient_named_row_keeps_its_declared_amount(enricher, name, canonical_id, quantity, forms, daily_value):
    assert _converted(enricher, name, canonical_id, quantity, "mg", forms, daily_value) == pytest.approx(quantity)


@pytest.mark.parametrize("name,canonical_id,quantity,factor", [
    ("Magnesium Hydroxide", "magnesium", 1000, 24.305 / 58.320),
    ("Choline Bitartrate", "choline", 1000, 104.17 / 253.25),
    ("Choline L-Bitartrate", "choline", 1000, 104.17 / 253.25),
    ("Choline DL-Bitartrate", "choline", 1000, 104.17 / 253.25),
    ("Inositol Hexanicotinate", "vitamin_b3_niacin", 500, 0.9111385222647094),
    ("Inositol Hexaniacinate", "vitamin_b3_niacin", 500, 0.9111385222647094),
])
def test_compound_named_row_still_converts_to_the_moiety(enricher, name, canonical_id, quantity, factor):
    assert _converted(enricher, name, canonical_id, quantity, "mg", [], None) == pytest.approx(quantity * factor, rel=1e-3)


def test_callers_without_a_row_name_keep_the_text_based_rule():
    from unit_converter import UnitConverter

    result = UnitConverter().convert_nutrient(
        "Magnesium", 1000, "mg", ingredient_name="Magnesium Hydroxide"
    )
    assert result.conversion_rule_id == "magnesium_hydroxide_to_magnesium"
