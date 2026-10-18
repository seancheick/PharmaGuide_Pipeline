"""Dose V4.1 §3.2-3.3 (Sean D3): sports adequacy plateaus above studied ranges;
total daily caffeine feeds the one product-level ceiling (400 mg/day FDA
reference; >400 and <600 -> at most 10, >=600 -> 0); co-primaries average."""
import pytest

from test_v4_sports_dose_p171 import _declared_protein_row, _product, _row
from scoring_v4.modules.sports_dose import score_dose
from scoring_v4.scored_artifact import build_scored_artifact
from scoring_v4.dose_safety import evaluate_dose_safety


def _primary(product):
    return score_dose(product)["components"]["sports_primary_active_dose"]


@pytest.mark.parametrize("canonical,amount,unit,name", [
    ("whey_protein", 50, "Gram(s)", "Whey Protein"),
    ("creatine_monohydrate", 15, "Gram(s)", "Creatine"),
    ("beta_alanine", 8, "Gram(s)", "Beta-Alanine"),
    ("hmb", 8, "Gram(s)", "HMB"),
])
def test_above_former_studied_ranges_plateau(canonical, amount, unit, name):
    primary_type = "protein_powder" if canonical == "whey_protein" else "amino_acid"
    rows = [_row(canonical, amount, unit)]
    if canonical == "whey_protein":
        rows.append(_declared_protein_row(amount))
    assert _primary(_product(*rows, name=name, primary_type=primary_type)) == 20.0


def test_caffeine_above_400_keeps_its_per_use_adequacy():
    assert _primary(_product(_row("caffeine", 450, "mg"), name="Caffeine", primary_type="pre_workout")) == 18.0


def _caffeine(per_serving, servings=1, extra=()):
    product = _product(_row("caffeine", per_serving, "mg"), *extra, name="Energy", primary_type="pre_workout")
    product["servingSizes"] = [{"quantity": 1, "unit": "scoop", "minDailyServings": 1, "maxDailyServings": servings}]
    return product


@pytest.mark.parametrize("per_serving,servings,cap", [
    (400, 1, None), (401, 1, 10.0), (599, 1, 10.0), (600, 1, 0.0), (200, 3, 0.0), (250, 2, 10.0)])
def test_daily_caffeine_ceiling_boundaries(per_serving, servings, cap):
    ceiling = evaluate_dose_safety(_caffeine(per_serving, servings)).dose_ceiling()
    assert (ceiling or {}).get("cap_public") == cap


def test_caffeine_from_several_quantified_sources_is_summed():
    second = {**_row("caffeine", 250, "mg", name="Caffeine (from green tea)"),
              "raw_source_path": "activeIngredients[caffeine_green_tea]"}
    assert evaluate_dose_safety(_caffeine(250, 1, (second,))).dose_ceiling()["cap_public"] == 10.0


def test_declared_total_and_its_components_are_not_counted_twice():
    total = {**_row("caffeine", 300, "mg", name="Total Caffeine"), "is_parent_total": True,
             "raw_source_path": "activeIngredients[caffeine_total]"}
    assert evaluate_dose_safety(_caffeine(300, 1, (total,))).dose_ceiling() is None


def test_unknown_caffeine_amount_stays_unknown():
    product = _caffeine(300)
    product["ingredient_quality_data"]["ingredients_scorable"][0]["quantity"] = None
    result = evaluate_dose_safety(product)
    assert result.dose_ceiling() is None
    assert result.caffeine["unknown_rows"] == 1


def test_caffeine_ceiling_reaches_the_public_dose_on_any_route_and_names_its_policy():
    artifact = build_scored_artifact(_caffeine(300, 2))
    dose = artifact["quality_pillars_v4"]["dose"]
    assert dose["score"] == 0.0
    assert "400 mg" in dose["reason"] and "PharmaGuide scoring policy" in dose["reason"]


def test_two_co_primaries_average_instead_of_the_strongest():
    product = _product(_row("creatine_monohydrate", 5, "Gram(s)"), _row("beta_alanine", 1, "Gram(s)"),
                       name="Creatine + Beta-Alanine", primary_type="pre_workout")
    payload = score_dose(product)
    assert payload["metadata"]["dose_aggregation"] == "co_primary_average"
    assert payload["components"]["sports_primary_active_dose"] == 14.0  # (20 + 8) / 2


def test_one_co_primary_is_scored_on_its_own_benchmark_not_an_accessory():
    # 10 g protein is the primary (8); a 1 g taurine accessory (20) cannot stand in.
    product = _product(_row("whey_protein", 12, "Gram(s)"), _declared_protein_row(10), _row("taurine", 1, "Gram(s)"),
                       name="Protein Shake", primary_type="protein_powder")
    payload = score_dose(product)
    assert payload["metadata"]["dose_aggregation"] == "single_primary"
    assert payload["metadata"]["primary_identity"] == "protein"
    assert payload["components"]["sports_primary_active_dose"] == 8.0


def test_caffeine_that_is_not_a_primary_still_reaches_the_ceiling_on_the_generic_route():
    from test_v4_generic_dose_p132a import _ingredient, _product as generic_product
    p = generic_product(ingredients=[_ingredient(quantity=120),
                                     {**_ingredient(name="Caffeine", canonical_id="caffeine", quantity=450),
                                      "raw_source_path": "activeIngredients[caffeine]"}],
                        adequacy_results=[], safety_flags=[])
    p["product_name"] = "Magnesium Energy"
    assert evaluate_dose_safety(p).dose_ceiling()["cap_public"] == 10.0
    assert build_scored_artifact(p)["quality_pillars_v4"]["dose"]["score"] <= 10.0


@pytest.mark.parametrize("component", [None, 100, 600])
def test_authoritative_caffeine_total_is_retained(component):
    total = {**_row("caffeine", 600, "mg", name="Total Caffeine"), "is_parent_total": True}
    rows = [total]
    if component is not None:
        rows.append({**_row("caffeine", component, "mg", name="Caffeine from coffee"),
                     "raw_source_path": "activeIngredients[component]"})
    product = _product(*rows, name="Caffeine", primary_type="pre_workout")
    result = evaluate_dose_safety(product)
    assert result.caffeine["total_mg_day_max"] == 600
    assert result.dose_ceiling()["cap_public"] == 0
    assert build_scored_artifact(product)["quality_pillars_v4"]["dose"]["score"] == 0


def test_enricher_marked_caffeine_total_retains_partial_component_exposure():
    from enrich_supplements_v3 import SupplementEnricherV3
    total = {**_row("caffeine", 600, "mg", name="Caffeine"), "source_section": "active"}
    component = {**_row("caffeine", 100, "mg", name="Caffeine from coffee"),
                 "source_section": "active", "is_nested_ingredient": True,
                 "parent_blend": "Caffeine", "raw_source_path": "activeIngredients[component]"}
    rows = [total, component]
    SupplementEnricherV3()._mark_parent_total_rows(rows)
    assert total["is_parent_total"] is True
    assert evaluate_dose_safety(_product(*rows)).caffeine["total_mg_day_max"] == 600


def test_quantified_caffeine_projection_is_retained_when_carrier_is_not_caffeine():
    carrier = _row("guarana", 2000, "mg")
    projection = {**_row("caffeine", 500, "mg"), "scoring_input_kind": "product_level_evidence",
                  "raw_source_path": carrier["raw_source_path"], "linked_rows": [carrier["raw_source_path"]]}
    product = _product(carrier, projection, name="Caffeine", primary_type="pre_workout")
    assert evaluate_dose_safety(product).caffeine["total_mg_day_max"] == 500
    assert build_scored_artifact(product)["quality_pillars_v4"]["dose"]["score"] == 10


def test_caffeine_projection_of_counted_caffeine_is_not_a_second_exposure():
    caffeine = _row("caffeine", 300, "mg")
    projection = {**caffeine, "scoring_input_kind": "product_level_evidence",
                  "linked_rows": [caffeine["raw_source_path"]]}
    result = evaluate_dose_safety(_product(caffeine, projection))
    assert result.caffeine["total_mg_day_max"] == 300
    assert result.dose_ceiling() is None


@pytest.mark.parametrize("operator,amount,cap", [
    ("<", 600, None), ("<=", 600, None), (">", 400, 10), (">=", 400, None),
    (">=", 600, 0), (">", 599, 10), ("~", 600, None),
])
def test_caffeine_qualified_amounts_only_cap_confirmed_exposure(operator, amount, cap):
    row = {**_row("caffeine", amount, "mg"), "quantity_operator": operator}
    result = evaluate_dose_safety(_product(row, name="Caffeine", primary_type="pre_workout"))
    assert result.caffeine["total_mg_day_max"] is None
    ceiling = result.dose_ceiling()
    assert (ceiling or {}).get("cap_public") == cap
    if ceiling:
        assert ceiling["quantity_operator"] in {">", ">="}


def test_upper_bound_caffeine_does_not_claim_exact_six_hundred_or_minimum_excess():
    product = _product({**_row("caffeine", 600, "mg"), "quantity_operator": "<"},
                       name="Caffeine", primary_type="pre_workout")
    artifact = build_scored_artifact(product)
    dose = artifact["quality_pillars_v4"]["dose"]
    assert dose["score"] == 18
    assert "label provides 600 mg" not in dose["reason"]
    assert artifact["dose_safety_evaluation"]["state_counts"]["material_but_unresolved"] == 1


def test_defaulted_frequency_assesses_one_serving_and_records_the_default():
    product = _caffeine(600)
    product.pop("servingSizes")
    ceiling = evaluate_dose_safety(product).dose_ceiling()
    assert ceiling["cap_public"] == 0
    assert ceiling["amount_mg_day"] == 600 and ceiling["frequency_defaulted"] is True


def test_scoped_caffeine_total_does_not_hide_an_independent_source():
    total = {**_row("caffeine", 300, "mg", name="Coffee caffeine"), "is_parent_total": True}
    child = {**_row("caffeine", 100, "mg"), "parent_blend": "Coffee caffeine",
             "is_nested_ingredient": True, "raw_source_path": "activeIngredients[coffee_part]"}
    separate = {**_row("caffeine_anhydrous", 200, "mg"), "raw_source_path": "activeIngredients[anhydrous]"}
    result = evaluate_dose_safety(_product(total, child, separate))
    assert result.caffeine["total_mg_day_max"] == 500
    assert result.dose_ceiling()["cap_public"] == 10


def test_known_caffeine_total_is_not_made_unknown_by_unquantified_components():
    total = {**_row("caffeine", 600, "mg"), "is_parent_total": True}
    child = {**_row("caffeine", None, "mg"), "raw_source_path": "activeIngredients[component]"}
    result = evaluate_dose_safety(_product(total, child))
    assert result.caffeine["total_mg_day_max"] == 600 and result.caffeine["unknown_rows"] == 0
    assert result.dose_ceiling()["cap_public"] == 0


def test_known_caffeine_partial_total_still_confirms_a_ceiling_with_unknown_source():
    known = _row("caffeine", 450, "mg")
    unknown = {**_row("caffeine_anhydrous", None, "mg"), "raw_source_path": "activeIngredients[unknown]"}
    result = evaluate_dose_safety(_product(known, unknown))
    assert result.caffeine["total_mg_day_max"] is None
    ceiling = result.dose_ceiling()
    assert ceiling["cap_public"] == 10 and ceiling["amount_mg_day"] == 450
    assert ceiling["quantity_operator"] == ">="


def test_qualified_caffeine_total_retains_the_confirmed_component_floor():
    total = {**_row("caffeine", 600, "mg", name="Coffee caffeine"),
             "is_parent_total": True, "quantity_operator": "<"}
    child = {**_row("caffeine", 450, "mg"), "parent_blend": "Coffee caffeine",
             "is_nested_ingredient": True, "raw_source_path": "activeIngredients[coffee_part]"}
    result = evaluate_dose_safety(_product(total, child))
    ceiling = result.dose_ceiling()
    assert ceiling["cap_public"] == 10 and ceiling["amount_mg_day"] == 450
    assert ceiling["quantity_operator"] == ">="


def test_unread_caffeine_total_does_not_erase_confirmed_components_or_double_count():
    total = {**_row("caffeine", None, "mg", name="Coffee caffeine"), "is_parent_total": True}
    child = {**_row("caffeine", 450, "mg"), "parent_blend": "Coffee caffeine",
             "is_nested_ingredient": True, "raw_source_path": "activeIngredients[coffee_part]"}
    result = evaluate_dose_safety(_product(total, child))
    assert result.caffeine["total_mg_day_max"] is None
    assert result.dose_ceiling()["amount_mg_day"] == 450


def test_enricher_parent_marker_for_repeated_row_keeps_an_independent_caffeine_source():
    from enrich_supplements_v3 import SupplementEnricherV3
    parent = {**_row("caffeine", 300, "mg", name="Caffeine"), "source_section": "active"}
    child = {**parent, "is_nested_ingredient": True, "parent_blend": "Performance Blend",
             "raw_source_path": "activeIngredients[repeat]"}
    separate = {**_row("caffeine_anhydrous", 200, "mg"), "source_section": "active"}
    rows = [parent, child, separate]
    SupplementEnricherV3()._mark_parent_total_rows(rows)
    assert parent["is_parent_total"] is True
    result = evaluate_dose_safety(_product(*rows))
    assert result.caffeine["total_mg_day_max"] == 500
    assert result.dose_ceiling()["cap_public"] == 10


def test_uncounted_raw_caffeine_source_cannot_erase_its_counted_projection():
    projection = {**_row("caffeine", 600, "mg"), "scoring_input_kind": "product_level_evidence",
                  "raw_source_path": "activeIngredients[0]", "linked_rows": ["activeIngredients[0]"]}
    product = _product(projection)
    product["activeIngredients"] = [{**_row("caffeine", None, "mg"), "raw_source_path": "activeIngredients[0]"}]
    result = evaluate_dose_safety(product)
    assert result.caffeine["total_mg_day_max"] == 600
    assert result.dose_ceiling()["cap_public"] == 0
