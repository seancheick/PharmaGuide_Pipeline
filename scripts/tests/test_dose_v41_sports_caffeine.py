"""Dose V4.1 §3.2-3.3 (Sean D3): sports adequacy plateaus above studied ranges;
total daily caffeine feeds the one product-level ceiling (400 mg/day FDA
reference; >400 and <600 -> at most 10, >=600 -> 0); co-primaries average."""
import pytest

from test_v4_sports_dose_p171 import _product, _row
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
    assert _primary(_product(_row(canonical, amount, unit), name=name, primary_type=primary_type)) == 20.0


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
    product = _product(_row("whey_protein", 10, "Gram(s)"), _row("taurine", 1, "Gram(s)"),
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
