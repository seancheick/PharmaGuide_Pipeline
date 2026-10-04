"""A UL verdict's amount, unit, UL and warning text must share one unit.

rda_optimal_uls.json states each UL in the nutrient's reference unit (copper:
10,000 mcg). The calculator reconciles a label amount in mg before comparing,
so pct_ul was right, but the shipped safety flag kept the label unit beside
the reference-unit UL: a 15 mg copper label read "15 mg ... upper limit of
10000 mg", nutrient_unit said "mg" next to a mcg UL, and two copper rows in mg
and mcg were never summed (incompatible_units). Only plain mass units are
rescaled; qualified units (mcg DFE, mcg RAE, mg NE) keep their own lineage.
"""

import pytest

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _row(name, quantity, unit, order, canonical_id):
    return {
        "name": name, "standardName": name, "order": order,
        "canonical_id": canonical_id, "canonical_source_db": "ingredient_quality_map",
        "quantity": quantity, "unit": unit, "forms": [],
    }


def _rda(enricher, rows):
    product = {
        "id": "ul-unit-alignment", "product_name": "test", "fullName": "test",
        "activeIngredients": rows, "inactiveIngredients": [],
        "servingSizes": [{"order": 1, "minQuantity": 1, "maxQuantity": 1, "unit": "Tablet(s)",
                          "minDailyServings": 1, "maxDailyServings": 1}],
    }
    enriched, errors = enricher.enrich_product(product)
    assert errors == []
    return enriched["rda_ul_data"]


def test_copper_flag_is_stated_in_the_reference_unit(enricher):
    rda = _rda(enricher, [_row("Copper", 15, "mg", 1, "copper")])
    [flag] = [f for f in rda["safety_flags"] if f["nutrient"] == "Copper"]
    assert (flag["amount"], flag["unit"], flag["ul"]) == (15000, "mcg", 10000)
    assert flag["over_amount"] == 5000
    assert "15000 mcg" in flag["warning"] and "10000 mcg" in flag["warning"]
    assert " mg" not in flag["warning"]
    [row] = [r for r in rda["ingredients_with_rda"] if r["canonical_id"] == "copper"]
    assert row["nutrient_unit"] == "mcg"


def test_copper_rows_in_mg_and_mcg_are_summed(enricher):
    rda = _rda(enricher, [
        _row("Copper", 6, "mg", 1, "copper"),
        _row("Copper", 5000, "mcg", 2, "copper"),
    ])
    summed = [f for f in rda["safety_flags"] if f.get("aggregation") == "canonical_sum"]
    assert [(f["amount"], f["unit"]) for f in summed] == [(11000, "mcg")]
    assert not any(e.get("reason") == "incompatible_aggregate_units"
                   for e in rda.get("dose_assessment_errors") or [])


def test_qualified_reference_units_are_not_rescaled(enricher):
    rda = _rda(enricher, [_row("Folic Acid", 1200, "mcg", 1, "vitamin_b9_folate")])
    [row] = [r for r in rda["ingredients_with_rda"] if r["canonical_id"] == "vitamin_b9_folate"]
    assert row["nutrient_unit"] == "mcg DFE"
    for flag in rda["safety_flags"]:
        assert flag["unit"] == "mcg DFE"
