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
    assert gap.ul == 40 and gap.ul_population["reference_gap"] == "pediatric_ul_rows_not_in_reference_data"


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
