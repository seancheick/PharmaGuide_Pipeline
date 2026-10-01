from scoring_v4.modules.generic_evidence import _dose_map, _converted_product_dose, score_evidence


def test_exact_source_dose_precedes_larger_same_identity_sibling():
    product = {"ingredient_quality_data": {"ingredients_scorable": [
        {"name": "Ashwagandha", "canonical_id": "ashwagandha", "quantity": 100,
         "unit": "mg", "raw_source_path": "ingredientRows[0]", "mapped": True},
        {"name": "Ashwagandha", "canonical_id": "ashwagandha", "quantity": 600,
         "unit": "mg", "raw_source_path": "ingredientRows[1]", "mapped": True},
    ]}}
    entry = {"id": "test", "ingredient": "Ashwagandha", "matched_term": "Ashwagandha",
             "matched_source_row_refs": ["ingredientRows[0]"], "dose_unit": "mg"}
    assert _converted_product_dose(entry, _dose_map(product))[0] == 100
    entry["matched_source_row_refs"] = ["ingredientRows[missing]"]
    assert _converted_product_dose(entry, _dose_map(product))[0] is None


def test_same_identity_mass_comparison_uses_compatible_units_in_either_order():
    """10 g must beat 300 mg; exact source refs must still select their own row."""
    for quantities in [(300, "mg", 10, "g"), (1000, "mcg", 2, "mg")]:
        small, small_unit, large, large_unit = quantities
        rows = [
            {"name": "Collagen", "canonical_id": "collagen", "quantity": small,
             "unit": small_unit, "raw_source_path": "ingredientRows[0]", "mapped": True},
            {"name": "Collagen", "canonical_id": "collagen", "quantity": large,
             "unit": large_unit, "raw_source_path": "ingredientRows[1]", "mapped": True},
        ]
        for ordered in [rows, rows[::-1]]:
            product = {"ingredient_quality_data": {"ingredients_scorable": ordered}}
            entry = {"id": "test", "ingredient": "Collagen", "dose_unit": "mg"}
            doses = _dose_map(product)
            expected_large_mg = 10000 if large_unit == "g" else large
            assert _converted_product_dose(entry, doses)[0] == expected_large_mg
            entry["matched_source_row_refs"] = ["ingredientRows[0]"]
            expected_small_mg = small / 1000 if small_unit == "mcg" else small
            assert _converted_product_dose(entry, doses)[0] == expected_small_mg
