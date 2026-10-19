"""Child Tolerable Upper Intake Levels (NASEM DRI summary tables) reach the label-population screen.

Sean, 2026-10-19 (scripts/audits/dose_hold_census_20261019/REPORT.md, option 1): a broad children
label screens the 1-3, 4-8 and 9-13 UL rows instead of being withheld for their absence. Source:
NCBI Bookshelf NBK545442 Appendix J, Tolerable Upper Intake Levels, Vitamins (table appJ_tab8) and
Elements (table appJ_tab9). Infants (0-12 months) have no rows in the reference file and vanadium's
UL "could be used to set a UL for adults but not children and adolescents" (table note d), so those
two keep the explicit reference gap.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from enrich_supplements_v3 import SupplementEnricherV3
import rda_ul_calculator
from rda_ul_calculator import RDAULCalculator

DATA = Path(__file__).resolve().parents[1] / "data" / "rda_optimal_uls.json"
CHILD_AGES = ("1-3", "4-8", "9-13")
GAP = "pediatric_ul_row_missing_for_stated_age"


@pytest.fixture(scope="module")
def records() -> dict:
    return {r["id"]: r for r in json.loads(DATA.read_text())["nutrient_recommendations"]}


@pytest.fixture(scope="module")
def calculator() -> RDAULCalculator:
    return RDAULCalculator()


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


def _child_uls(record: dict) -> dict:
    return {(row["group"], row["age_range"]): row["ul"] for row in record["data"]
            if row["age_range"] in CHILD_AGES}


# Values read from the NASEM tables; folate is stored in mcg DFE (folic acid x 1.667, the file's
# existing convention: 14-18 = 800 x 1.667 = 1334), choline/phosphorus/chloride in mg (table g/d).
@pytest.mark.parametrize("nutrient,expected", [
    ("vitamin_a", (600, 900, 1700)),
    ("vitamin_c", (400, 650, 1200)),
    ("vitamin_d", (63, 75, 100)),
    ("folate", (500, 667, 1000)),
    ("choline", (1000, 1000, 2000)),
    ("zinc", (7, 12, 23)),
    ("calcium", (2500, 2500, 3000)),
    ("magnesium", (65, 110, 350)),
    ("fluoride", (1.3, 2.2, 10)),
    ("chloride", (2300, 2900, 3400)),
    ("vitamin_e", (200, 300, 600)),
    ("niacin", (10, 15, 20)),
    ("vitamin_b6", (30, 40, 60)),
    ("boron", (3, 6, 11)),
    ("copper", (1000, 3000, 5000)),
    ("iodine", (200, 300, 600)),
    ("iron", (40, 40, 40)),
    ("manganese", (2, 3, 6)),
    ("molybdenum", (300, 600, 1100)),
    ("nickel", (0.2, 0.3, 0.6)),
    ("phosphorus", (3000, 3000, 4000)),
    ("selenium", (90, 150, 280)),
])
def test_child_ul_rows_match_the_nasem_tables(records, nutrient, expected):
    uls = _child_uls(records[nutrient])
    for sex in ("Male", "Female"):
        assert tuple(uls[(sex, age)] for age in CHILD_AGES) == expected


def test_every_established_ul_has_child_rows_except_vanadium(records):
    for nutrient_id, record in records.items():
        adult = [row["ul"] for row in record["data"] if row["age_range"] == "19-30" and row.get("ul")]
        if not adult or nutrient_id == "vanadium":
            assert not _child_uls(record), f"{nutrient_id}: no established child UL to record"
            continue
        uls = _child_uls(record)
        assert set(uls) == {(sex, age) for sex in ("Male", "Female") for age in CHILD_AGES}, nutrient_id
        teen = min(row["ul"] for row in record["data"] if row["age_range"] == "14-18"
                   and row["group"] in {"Male", "Female"} and row.get("ul"))
        # A child limit is positive and never above the adolescent limit (transcription guard).
        assert all(0 < uls[(sex, age)] <= teen for sex, age in uls), nutrient_id
        for row in record["data"]:
            if row["age_range"] in CHILD_AGES:
                assert row["rda_ai"] is None, "child rows carry the UL only; adequacy stays adult"
    assert not _child_uls(records["vanadium"])


@pytest.mark.parametrize("groups,expected", [
    (["Children 4 or More Years of Age"], ("4-8", "9-13", "14-18")),
    (["Children more than 1 but less than 4"], ("1-3",)),
    (["Infants/Baby (0 - 1 Year)"], ("0-1",)),
    (["Children (All)"], ("1-3", "4-8", "9-13", "14-18")),
    (["Girls: (All)"], ("1-3", "4-8", "9-13", "14-18")),
    (["Boys: (All)", "Children 4 or More Years of Age"], ("1-3", "4-8", "9-13", "14-18")),
    (["Children 4 or More Years of Age", "Children more than 1 but less than 4"],
     ("1-3", "4-8", "9-13", "14-18")),
    (["Children more than 1 but less than 4", "Infants/Baby (0 - 1 Year)"], ("0-1", "1-3")),
    (["Children 4-8 Years"], ("4-8",)),
    (["Children 14-18 Years"], ("14-18",)),
    (["Children under 14 years"], ("0-1", "1-3", "4-8", "9-13")),
    (["Adult (18 - 50 Years)", "Gluten Free"], None),
    # Ages stated in months keep the infant age (review finding, 2026-10-19).
    (["Children 6 months to 3 years"], ("0-1", "1-3")),
    (["Children 6-36 months"], ("0-1", "1-3")),
    ([{"text": "Children more than 1 but less than 4"}], ("1-3",)),
    # A child tag whose ages match no NASEM band cannot be placed: it is unresolved, never "no ages".
    (["Children 20-30 years"], ("unresolved",)),
])
def test_label_pediatric_age_ranges_cover_every_dsld_child_tag(enricher, groups, expected):
    product = {"targetGroups": groups}
    assert rda_ul_calculator.label_pediatric_age_ranges(product) == expected
    assert enricher._ul_screening_pediatric_age_groups(product) == expected


def test_children_4_plus_vitamin_c_screens_the_4_8_limit(calculator):
    result = calculator.compute_nutrient_adequacy(
        "Vitamin C", 1000.0, "mg", sex="adult_neutral", ul_population=("general_adult", "pediatric"),
        pediatric_age_groups=("4-8", "9-13", "14-18"))
    assert result.ul == 650 and result.over_ul
    assert result.ul_population["label"] == "children 4-8"
    assert "reference_gap" not in result.ul_population
    assert "upper limit for children 4-8 of 650 mg" in result.warnings[0]


def test_infant_coverage_keeps_the_reference_gap(calculator):
    result = calculator.compute_nutrient_adequacy(
        "Calcium", 300.0, "mg", sex="adult_neutral", ul_population="pediatric",
        pediatric_age_groups=("0-1", "1-3"))
    assert result.ul == 2500
    assert result.ul_population["reference_gap"] == GAP
    assert result.ul_population["missing_age_ranges"] == ["0-1"]


@pytest.mark.parametrize("ages", [(), ("unresolved",)])
def test_unplaceable_child_ages_are_a_gap_not_no_limit(calculator, ages):
    # An established-UL nutrient on a child label must never read as "no UL applies".
    result = calculator.compute_nutrient_adequacy(
        "Vitamin A", 5000.0, "mcg RAE", sex="adult_neutral", ul_population=("pediatric",),
        pediatric_age_groups=ages)
    assert result.ul is None
    assert result.ul_population["reference_gap"] == GAP


def test_non_contiguous_child_ages_are_named_exactly(calculator):
    result = calculator.compute_nutrient_adequacy(
        "Iron", 50.0, "mg", sex="adult_neutral", ul_population="pediatric",
        pediatric_age_groups=("1-3", "9-13"))
    assert result.ul == 40
    assert result.ul_population["label"] == "children 1-3 and 9-13"


def test_vanadium_child_label_keeps_the_reference_gap(calculator, records):
    ul, scope = calculator._screening_ul(records["vanadium"], ("general_adult", "pediatric"),
                                         ("4-8", "9-13", "14-18"))
    assert scope["reference_gap"] == GAP
    assert scope["missing_age_ranges"] == ["4-8", "9-13", "14-18"]


def _row(name, canonical_id, quantity, unit="mg"):
    return {"name": name, "standardName": name, "canonical_id": canonical_id,
            "canonical_source_db": "ingredient_quality_map", "quantity": quantity, "unit": unit,
            "raw_source_path": "ingredientRows[0]"}


def test_children_4_plus_calcium_within_limits_completes_and_scores(enricher):
    from scoring_v4.scored_artifact import build_scored_artifact
    product = {"id": "pediatric-complete", "product_name": "Calcium",
               "targetGroups": ["Children 4 or More Years of Age"],
               "servingSizes": [{"minDailyServings": 1, "maxDailyServings": 1}],
               "activeIngredients": [_row("Calcium", "calcium", 500)], "inactiveIngredients": []}
    enriched, errors = enricher.enrich_product(product)
    assert not errors
    [assessment] = enriched["rda_ul_data"]["dose_assessments"]
    assert assessment["readiness"] == "complete" and assessment["ul_value"] == 2500
    artifact = build_scored_artifact(enriched)
    assert artifact["assessment_readiness"]["dose"]["readiness"] == "complete"


def test_children_4_plus_zinc_above_the_4_8_limit_is_a_confirmed_exceedance(enricher):
    from scoring_v4.dose_safety import evaluate_dose_safety
    product = {"targetGroups": ["Children 4 or More Years of Age"],
               "activeIngredients": [_row("Zinc", "zinc", 15)], "inactiveIngredients": []}
    rda = enricher._collect_rda_ul_data(product, min_servings_per_day=1, max_servings_per_day=1)
    row = next(r for r in rda["adequacy_results"] if r.get("canonical_id") == "zinc")
    assert row["ul"] == 12 and row["ul_population"]["label"] == "children 4-8"
    flags = [f for f in rda["safety_flags"] if f.get("nutrient") == "Zinc"]
    assert flags and flags[0]["ul_gate_eligible"] is True and flags[0]["ul"] == 12
    assert "upper limit for children 4-8 of 12 mg" in flags[0]["warning"]
    states = evaluate_dose_safety({"rda_ul_data": rda}).audit_metadata()["state_counts"]
    assert states["confirmed_over_threshold"] == 1
    assert states.get("material_but_unresolved", 0) == 0
