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
        "raw_source_path": f"ingredientRows[{order - 1}]",
        "quantity": quantity, "unit": unit, "forms": [],
    }


def _rda(enricher, rows, min_daily=1, max_daily=1):
    product = {
        "id": "ul-unit-alignment", "product_name": "test", "fullName": "test",
        "activeIngredients": rows, "inactiveIngredients": [],
        "servingSizes": [{"order": 1, "minQuantity": 1, "maxQuantity": 1, "unit": "Tablet(s)",
                          "minDailyServings": min_daily, "maxDailyServings": max_daily}],
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

@pytest.mark.parametrize("quantity,unit,form,activity,ul_mass", [
    (2000, "IU", "dl-alpha-tocopheryl acetate", 900, 1800),
    (1000, "IU", "dl-alpha-tocopheryl acetate", 450, 900),
    (600, "mg", "dl-alpha-tocopheryl acetate", 600, 1200),
    (1000, "IU", "d-alpha-tocopheryl acetate", 670, 670),
])
def test_vitamin_e_ul_uses_mass_not_nutritional_activity(
    enricher, quantity, unit, form, activity, ul_mass,
):
    row = _row("Vitamin E", quantity, unit, 1, "vitamin_e")
    row["forms"] = [{"name": form, "prefix": "as"}]
    rda = _rda(enricher, [row])
    [adequacy] = rda["adequacy_results"]
    [consumer] = rda["ingredients_with_rda"]
    assert adequacy["adequacy_exposure"]["per_day"] == pytest.approx(activity)
    assert adequacy["safety_exposure"] == {"per_day": pytest.approx(ul_mass), "unit": "mg"}
    assert consumer["safety_exposure"] == adequacy["safety_exposure"]
    assert adequacy["pct_ul"] == pytest.approx(ul_mass / 10)
    assert adequacy["over_ul"] is (ul_mass > 1000)
    assert bool(rda["safety_flags"]) is (ul_mass > 1000)


@pytest.mark.parametrize("quantity,unit,ul_mass,within", [
    (800, "IU", 720, True),
    (1200, "IU", 1080, False),
    (400, "mg", 800, True),
    (600, "mg", 1200, False),
])
def test_unknown_vitamin_e_uses_all_stereoisomer_safety_bound(
    enricher, quantity, unit, ul_mass, within,
):
    rda = _rda(enricher, [_row("Vitamin E", quantity, unit, 1, "vitamin_e")])
    [adequacy] = rda["adequacy_results"]
    assert adequacy["safety_exposure"] == {"per_day": pytest.approx(ul_mass), "unit": "mg"}
    assert (adequacy["ul_assessment_status"] == "assessed_within_limit") is within
    assert adequacy["over_ul"] is False  # an upper bound is not a confirmed exceedance
    if not within:
        assert adequacy["skip_ul_reason"] == "unknown_vitamin_form"
    assert not rda["safety_flags"]


def test_synthetic_vitamin_e_rows_sum_ul_mass_once(enricher):
    rows = [_row("Vitamin E", 750, "IU", i, "vitamin_e") for i in (1, 2)]
    for row in rows:
        row["forms"] = [{"name": "dl-alpha-tocopheryl acetate", "prefix": "as"}]
    rda = _rda(enricher, rows)
    [flag] = rda["safety_flags"]
    assert flag["aggregation"] == "canonical_sum"
    assert flag["amount"] == pytest.approx(1350)
    assert flag["pct_ul"] == pytest.approx(135)


def test_unknown_vitamin_e_family_cannot_clear_a_high_aggregate_bound(enricher):
    known = _row("Vitamin E", 750, "IU", 1, "vitamin_e")
    known["forms"] = [{"name": "dl-alpha-tocopheryl acetate", "prefix": "as"}]
    unknown = _row("Vitamin E", 600, "IU", 2, "vitamin_e")
    rda = _rda(enricher, [known, unknown])
    [assessment] = [a for a in rda["dose_assessments"] if a.get("reason_code") == "unknown_vitamin_form"]
    assert assessment["readiness"] == "incomplete"
    assert assessment["ul_assessment_status"] == "unresolved_form"
    assert not rda["safety_flags"]  # the unknown bound is not confirmed exposure


def test_standalone_synthetic_compound_mass_is_not_doubled(enricher):
    row = _row("dl-alpha-tocopheryl acetate", 500, "mg", 1, "vitamin_e")
    rda = _rda(enricher, [row])
    assert rda["adequacy_results"][0]["safety_exposure"]["per_day"] == pytest.approx(500)


def test_mixed_natural_synthetic_vitamin_e_does_not_claim_natural_exposure(enricher):
    row = _row("Vitamin E", 1200, "IU", 1, "vitamin_e")
    row["forms"] = [{"name": "d-alpha-tocopherol"}, {"name": "dl-alpha-tocopheryl acetate"}]
    rda = _rda(enricher, [row])
    [assessment] = rda["dose_assessments"]
    assert assessment["readiness"] == "incomplete"
    assert rda["adequacy_results"][0]["skip_ul_reason"] == "unknown_vitamin_form"
    assert rda["adequacy_results"][0]["safety_exposure"]["per_day"] == pytest.approx(1080)


def test_unknown_fda_mg_family_preserves_consumer_activity(enricher):
    rda = _rda(enricher, [_row("Vitamin E", q, "mg", i, "vitamin_e") for i, q in ((1, 30), (2, 31))])
    for consumer, adequacy in zip(rda["ingredients_with_rda"], rda["adequacy_results"]):
        assert consumer["pct_rda"] == adequacy["pct_rda"]
        assert consumer["adequacy_band"] == adequacy["adequacy_band"]
        assert adequacy["scoring_eligible"] is True


def test_unknown_alpha_moiety_in_standalone_ester_cannot_earn_adequacy(enricher):
    row = _row("dl-alpha-tocopheryl acetate", 1200, "mg", 1, "vitamin_e")
    row["standardName"] = "Vitamin E"
    rda = _rda(enricher, [row])
    [adequacy] = rda["adequacy_results"]
    assert adequacy["ul_gate_ineligible_reason"] == "compound_mass_not_elemental"
    assert adequacy["pct_rda"] is None
    assert adequacy["scoring_eligible"] is False


@pytest.mark.parametrize("unit", ["IU", "U", "UI"])
def test_synthetic_vitamin_e_iu_aliases_have_one_ul_exposure(enricher, unit):
    row = _row("dl-alpha-tocopheryl acetate", 2000, unit, 1, "vitamin_e")
    row["standardName"] = "Vitamin E"
    rda = _rda(enricher, [row])
    assert rda["adequacy_results"][0]["safety_exposure"]["per_day"] == pytest.approx(1800)


@pytest.mark.parametrize("unit", ["IU", "U", "UI"])
def test_unknown_vitamin_e_iu_aliases_have_one_bound(enricher, unit):
    rda = _rda(enricher, [_row("Vitamin E", 600, unit, 1, "vitamin_e")])
    [adequacy] = rda["adequacy_results"]
    assert adequacy["safety_exposure"] == {"per_day": pytest.approx(540), "unit": "mg"}
    assert adequacy["ul_assessment_status"] == "assessed_within_limit"


def test_synthetic_vitamin_e_minimum_benefit_maximum_safety(enricher):
    row = _row("Vitamin E", 500, "IU", 1, "vitamin_e")
    row["forms"] = [{"name": "dl-alpha-tocopheryl acetate"}]
    [adequacy] = _rda(enricher, [row], 1, 3)["adequacy_results"]
    assert adequacy["adequacy_exposure"]["per_day"] == pytest.approx(225)
    assert adequacy["safety_exposure"]["per_day"] == pytest.approx(1350)
    assert adequacy["over_ul"] is True


def test_unknown_vitamin_e_compound_grams_cannot_be_treated_as_mg(enricher):
    row = _row("Mixed Tocopherols", 2, "g", 1, "vitamin_e")
    row["standardName"] = "Vitamin E"
    [adequacy] = _rda(enricher, [row])["adequacy_results"]
    assert adequacy["safety_exposure"] == {"per_day": pytest.approx(2000), "unit": "mg"}
    assert adequacy["ul_assessment_status"] != "assessed_within_limit"


@pytest.mark.parametrize("quantity,unit", [(600, "mg"), (600, "mg AT"), (0.6, "g"), (600000, "mcg")])
@pytest.mark.parametrize("form,multiplier,known", [
    ("d-alpha-tocopheryl acetate", 1, True),
    ("dl-alpha-tocopheryl acetate", 2, True),
    ("d-alpha-tocopheryl acetate and dl-alpha-tocopheryl acetate", 2, False),
    (None, 2, False),
])
def test_vitamin_e_parent_mass_units_preserve_activity_and_ul_lineage(
    enricher, quantity, unit, form, multiplier, known,
):
    row = _row("Vitamin E", quantity, unit, 1, "vitamin_e")
    if form:
        row["forms"] = [{"name": form}]
    [assessment] = _rda(enricher, [row])["adequacy_results"]
    assert assessment["adequacy_exposure"]["per_day"] == pytest.approx(600)
    assert assessment["safety_exposure"] == {"per_day": pytest.approx(600 * multiplier), "unit": "mg"}
    assert assessment["over_ul"] is (known and multiplier == 2)
    if not known:
        assert assessment["ul_assessment_status"] != "assessed_within_limit"
        assert assessment["skip_ul_reason"] == "unknown_vitamin_form"


@pytest.mark.parametrize("quantity,unit", [(600, "mg"), (0.6, "g"), (600000, "mcg")])
@pytest.mark.parametrize("name", ["dl-alpha-tocopheryl acetate", "Mixed Tocopherols"])
def test_vitamin_e_compound_mass_units_do_not_become_parent_activity(enricher, quantity, unit, name):
    row = _row(name, quantity, unit, 1, "vitamin_e")
    row["standardName"] = "Vitamin E"
    [assessment] = _rda(enricher, [row])["adequacy_results"]
    assert assessment["safety_exposure"] == {"per_day": pytest.approx(600), "unit": "mg"}
    assert assessment["scoring_eligible"] is False
