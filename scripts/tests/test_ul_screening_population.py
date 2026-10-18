"""Dose V4.1 §2.5 (Sean D2): catalog UL screening uses the lowest established UL
across the product's population. With no stated population that is every
ordinary adult group (calcium 2,000 mg; phosphorus 3,000 mg); a stated
population narrows it; adequacy references are unchanged."""
from __future__ import annotations

import pytest

from enrich_supplements_v3 import SupplementEnricherV3
from rda_ul_calculator import RDAULCalculator


@pytest.fixture(scope="module")
def calculator() -> RDAULCalculator:
    return RDAULCalculator()


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


@pytest.mark.parametrize("nutrient,population,expected", [
    ("Calcium", "general_adult", 2000),
    ("Calcium", "adults_19_50", 2500),
    ("Calcium", "adults_51_plus", 2000),
    ("Calcium", "pregnancy_lactation", 2500),
    ("Phosphorus", "general_adult", 3000),
    ("Phosphorus", "adults_19_50", 4000),
    ("Magnesium", "general_adult", 350),
    ("Vitamin A", "pregnancy_lactation", 3000),
    ("Phosphorus", "pregnancy_lactation", 3500),
    ("Folate", "pregnancy_lactation", 1667),  # mcg DFE table unit
])
def test_screening_ul_is_the_lowest_across_the_population(calculator, nutrient, population, expected):
    result = calculator.compute_nutrient_adequacy(nutrient, 1.0, "mg" if nutrient != "Vitamin A" else "mcg",
                                                  sex="adult_neutral", ul_population=population)
    assert result.ul == expected


def test_adequacy_reference_is_unchanged(calculator):
    adequacy = calculator.compute_nutrient_adequacy("Calcium", 260.0, "mg", age_group="19-30", sex="adult_neutral")
    assert adequacy.rda_ai == 1000 and adequacy.ul == 2500
    screening = calculator.compute_nutrient_adequacy("Calcium", 2400.0, "mg", sex="adult_neutral",
                                                     ul_population="general_adult")
    assert screening.rda_ai == 1000
    assert screening.ul == 2000 and screening.pct_ul == pytest.approx(120.0) and screening.over_ul


def test_warning_names_the_population_whose_limit_applies(calculator):
    calcium = calculator.compute_nutrient_adequacy("Calcium", 2400.0, "mg", sex="adult_neutral",
                                                   ul_population="general_adult")
    assert "upper limit for adults 51+ of 2000 mg" in calcium.warnings[0]
    magnesium = calculator.compute_nutrient_adequacy("Magnesium", 480.0, "mg", sex="adult_neutral",
                                                     ul_population="general_adult")
    assert "general adult upper limit of 350 mg" in magnesium.warnings[0]
    assert calcium.ul_population["label"] == "adults 51+"


# The screen covers every population the label states (plan section 2.5:
# the lowest UL across the whole stated population), so a label naming two
# populations screens against the rows of both.
@pytest.mark.parametrize("groups,expected", [
    ([], ("general_adult",)),
    (["Adult (18 - 50 Years)"], ("general_adult",)),
    (["Adult (18 - 50 Years)", "Gluten Free"], ("general_adult",)),
    (["Seniors/Mature (>50 Years) - Women ONLY"], ("adults_51_plus",)),
    (["Pregnant Women", "Lactating"], ("pregnancy_lactation",)),
    (["Adult Female (18 - 50 Years)", "Lactating", "Pregnant Women"], ("general_adult", "pregnancy_lactation")),
    (["Children 4 or More Years of Age"], ("pediatric",)),
    (["Adult (18 - 50 Years)", "Children 4 or More Years of Age"], ("general_adult", "pediatric")),
    # A negated life stage is not that life stage (959 stored labels).
    (["Women (not pregnant or lactating)"], ("general_adult",)),
    (["Seniors/Mature (>50 Years) - Women ONLY", "Women (not pregnant or lactating)"],
     ("adults_51_plus", "general_adult")),
    (["Menopause"], ("general_adult",)),
])
def test_label_population_from_dsld_target_groups(enricher, groups, expected):
    assert enricher._ul_screening_population({"targetGroups": groups}) == tuple(sorted(expected))


def test_not_pregnant_women_calcium_above_the_general_adult_limit_is_flagged(enricher):
    product = {**_calcium(1100), "targetGroups": ["Women (not pregnant or lactating)",
                                                  "Seniors/Mature (>50 Years) - Women ONLY"]}
    result = enricher._collect_rda_ul_data(product, min_servings_per_day=1, max_servings_per_day=2)
    flags = [f for f in result["safety_flags"] if f.get("nutrient") == "Calcium"]
    assert flags and flags[0]["ul"] == 2000 and flags[0]["ul_gate_eligible"] is True
    assert "pregnan" not in flags[0]["ul_population"]["label"]


def test_a_union_takes_the_lowest_limit_across_every_stated_population(calculator):
    union = calculator.compute_nutrient_adequacy("Calcium", 2200.0, "mg", sex="adult_neutral",
                                                 ul_population=("general_adult", "pregnancy_lactation"))
    assert union.ul == 2000 and union.over_ul
    assert union.ul_population["members"] == ["general_adult", "pregnancy_lactation"]
    assert union.ul_population["label"] == "adults 51+"
    gap = calculator.compute_nutrient_adequacy("Zinc", 50.0, "mg", sex="adult_neutral",
                                               ul_population=("general_adult", "pediatric"))
    assert gap.ul == 34 and gap.ul_population["reference_gap"] == "pediatric_ul_rows_below_14_not_in_reference_data"


def _calcium(quantity):
    return {"activeIngredients": [{"name": "Calcium", "standardName": "Calcium", "canonical_id": "calcium",
                                   "canonical_source_db": "ingredient_quality_map", "quantity": quantity,
                                   "unit": "mg", "dailyValue": quantity / 13.0}],
            "inactiveIngredients": []}


def test_general_adult_calcium_between_2000_and_2500_is_now_a_confirmed_exceedance(enricher):
    result = enricher._collect_rda_ul_data(_calcium(1200), min_servings_per_day=1, max_servings_per_day=2)
    flags = [f for f in result["safety_flags"] if f.get("nutrient") == "Calcium"]
    assert flags and flags[0]["ul"] == 2000 and flags[0]["pct_ul"] == pytest.approx(120.0)
    assert flags[0]["ul_gate_eligible"] is True
    assert flags[0]["ul_population"]["id"] == "general_adult"
    row = next(r for r in result["adequacy_results"] if r.get("canonical_id") == "calcium")
    assert row["rda_ai"] == 1000 and row["ul"] == 2000


def test_labeled_pregnancy_population_uses_its_own_limit(enricher):
    product = {**_calcium(1200), "targetGroups": ["Pregnant Women", "Lactating"]}
    result = enricher._collect_rda_ul_data(product, min_servings_per_day=1, max_servings_per_day=2)
    assert not [f for f in result["safety_flags"] if f.get("nutrient") == "Calcium"]
    row = next(r for r in result["adequacy_results"] if r.get("canonical_id") == "calcium")
    assert row["ul"] == 2500 and row["ul_population"]["id"] == "pregnancy_lactation"


@pytest.mark.parametrize("groups,expected", [
    (["Adults 19-50"], ("adults_19_50",)),
    ([{"text": "Adults (19 – 50 Years)"}], ("adults_19_50",)),
    (["Adults 19-50", "Lactating"], ("adults_19_50", "pregnancy_lactation")),
    (["Adult (18 - 50 Years)", "Adults 19-50"], ("adults_19_50", "general_adult")),
    (["Women 19-50 (not pregnant or lactating)"], ("adults_19_50",)),
])
def test_explicit_19_50_population_text_reaches_existing_owner(enricher, groups, expected):
    assert enricher._ul_screening_population({"targetGroups": groups}) == tuple(sorted(expected))


def test_explicit_19_50_calcium_uses_the_restricted_limit(enricher):
    result = enricher._collect_rda_ul_data({**_calcium(2200), "targetGroups": ["Adults 19-50"]},
                                         min_servings_per_day=1, max_servings_per_day=1)
    row = next(r for r in result["adequacy_results"] if r.get("canonical_id") == "calcium")
    assert row["ul"] == 2500 and row["ul_population"]["id"] == "adults_19_50"
    assert not result["safety_flags"]


def test_pediatric_screen_uses_available_adolescent_ul_and_reports_younger_gap(enricher):
    product = {"targetGroups": ["Children 4 or More Years of Age"], "activeIngredients": [{
        "name": "Zinc", "standardName": "Zinc", "canonical_id": "zinc",
        "canonical_source_db": "ingredient_quality_map", "quantity": 36,
        "unit": "mg", "dailyValue": 327.27}], "inactiveIngredients": []}
    result = enricher._collect_rda_ul_data(product, min_servings_per_day=1, max_servings_per_day=1)
    row = next(r for r in result["adequacy_results"] if r.get("canonical_id") == "zinc")
    assert row["ul"] == 34 and row["pct_ul"] == pytest.approx(100 * 36 / 34)
    assert row["ul_population"]["label"] == "adolescents 14-18"
    assert row["ul_population"]["reference_gap"] == "pediatric_ul_rows_below_14_not_in_reference_data"
    assert any(flag.get("ul") == 34 and flag["ul_gate_eligible"] is True for flag in result["safety_flags"])


def test_missing_pediatric_ul_does_not_borrow_adult_rows(calculator):
    ul, scope = calculator._screening_ul({"data": [
        {"group": "Male", "age_range": "19-30", "ul": 40},
        {"group": "Female", "age_range": "19-30", "ul": 40}]}, "pediatric")
    assert ul is None
    assert scope["reference_gap"] == "pediatric_ul_rows_below_14_not_in_reference_data"


@pytest.mark.parametrize("target", ["Infants", "Children 4-8 Years", "Children under 14 years"])
def test_explicit_younger_children_do_not_claim_adolescent_reference(enricher, target):
    product = {**_calcium(2200), "targetGroups": [target]}
    result = enricher._collect_rda_ul_data(product, min_servings_per_day=1, max_servings_per_day=1)
    row = next(r for r in result["adequacy_results"] if r.get("canonical_id") == "calcium")
    assert row["ul"] is None
    assert row["ul_population"]["label"] == "pediatric"
    assert row["ul_population"]["reference_gap"] == "pediatric_ul_rows_below_14_not_in_reference_data"


def test_broad_pediatric_label_in_union_retains_applicable_adolescent_reference(enricher):
    product = {**_calcium(2200), "targetGroups": ["Infants", "Children 4 or More Years of Age"]}
    result = enricher._collect_rda_ul_data(product, min_servings_per_day=1, max_servings_per_day=1)
    row = next(r for r in result["adequacy_results"] if r.get("canonical_id") == "calcium")
    assert row["ul"] == 3000 and row["ul_population"]["label"] == "adolescents 14-18"


@pytest.mark.parametrize("target", ["Infants", "Children 4 or More Years of Age"])
def test_pediatric_reference_gap_is_incomplete_through_enrich_and_score(enricher, target):
    from scoring_v4.scored_artifact import build_scored_artifact
    product = {**_calcium(2200), "id": "pediatric-reference-gap", "product_name": "Calcium",
               "targetGroups": [target], "servingSizes": [{"minDailyServings": 1, "maxDailyServings": 1}]}
    product["activeIngredients"][0]["raw_source_path"] = "ingredientRows[0]"
    enriched, errors = enricher.enrich_product(product)
    assert not errors
    [assessment] = enriched["rda_ul_data"]["dose_assessments"]
    assert assessment["readiness"] == "incomplete"
    assert assessment["reason_code"] == "pediatric_reference_gap"
    artifact = build_scored_artifact(enriched)
    assert artifact["assessment_readiness"]["dose"]["readiness"] == "incomplete"
    assert artifact["quality_score_status"] == "not_scored"
    assert artifact["dose_safety_evaluation"]["state_counts"]["material_but_unresolved"] >= 1


def test_broad_pediatric_exceedance_retains_known_concern_and_unknown_coverage(enricher):
    from scoring_v4.dose_safety import evaluate_dose_safety
    product = {"targetGroups": ["Children 4 or More Years of Age"], "activeIngredients": [{
        "name": "Zinc", "standardName": "Zinc", "canonical_id": "zinc",
        "canonical_source_db": "ingredient_quality_map", "quantity": 36,
        "unit": "mg", "dailyValue": 327.27}], "inactiveIngredients": []}
    rda = enricher._collect_rda_ul_data(product, min_servings_per_day=1, max_servings_per_day=1)
    result = evaluate_dose_safety({"rda_ul_data": rda})
    states = result.audit_metadata()["state_counts"]
    assert states["confirmed_over_threshold"] == 1
    assert states["material_but_unresolved"] == 1
    assert result.dose_ceiling()["cap_public"] == 10


def test_explicit_adolescent_population_has_no_younger_child_gap(enricher):
    result = enricher._collect_rda_ul_data({**_calcium(2200), "targetGroups": ["Children 14-18 Years"]},
                                         min_servings_per_day=1, max_servings_per_day=1)
    row = next(r for r in result["adequacy_results"] if r.get("canonical_id") == "calcium")
    assert row["ul"] == 3000
    assert not row["ul_population"].get("reference_gap")
    assert not result["safety_flags"]


def test_pediatric_aggregate_excess_does_not_discard_unresolved_younger_coverage(enricher):
    from scoring_v4.dose_safety import evaluate_dose_safety
    rows = [{"name": "Zinc", "standardName": "Zinc", "canonical_id": "zinc",
             "canonical_source_db": "ingredient_quality_map", "quantity": 20, "unit": "mg",
             "dailyValue": 181.8, "raw_source_path": f"ingredientRows[{index}]"} for index in range(2)]
    rda = enricher._collect_rda_ul_data({"targetGroups": ["Children 4 or More Years of Age"],
                                      "activeIngredients": rows, "inactiveIngredients": []},
                                      min_servings_per_day=1, max_servings_per_day=1)
    states = evaluate_dose_safety({"rda_ul_data": rda}).audit_metadata()["state_counts"]
    assert states["confirmed_over_threshold"] == 1
    assert states["material_but_unresolved"] >= 1


def test_no_established_ul_is_not_a_missing_pediatric_reference(enricher):
    product = {"id": "pediatric-no-established-ul", "product_name": "Vitamin B12",
               "targetGroups": ["Children 4 or More Years of Age"], "activeIngredients": [{
                   "name": "Vitamin B12", "standardName": "Vitamin B12", "canonical_id": "vitamin_b12",
                   "canonical_source_db": "ingredient_quality_map", "quantity": 10, "unit": "mcg",
                   "dailyValue": 416.7, "raw_source_path": "ingredientRows[0]"}], "inactiveIngredients": []}
    enriched, errors = enricher.enrich_product(product)
    assert not errors
    [assessment] = enriched["rda_ul_data"]["dose_assessments"]
    assert assessment["readiness"] == "not_applicable"
    assert assessment["ul_assessment_status"] == "no_ul_applicable"
    assert not enriched["rda_ul_data"]["safety_flags"]
