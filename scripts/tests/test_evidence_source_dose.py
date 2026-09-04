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
