"""Child Tolerable Upper Intake Levels (NASEM DRI summary tables): accurate child notes, adult score.

Sean, 2026-10-19: the catalog score is for adults (the app's customers); children are not scored,
but when a label names children the child limits are shown accurately, for an adult scanning a
child's product. The 1-3, 4-8 and 9-13 UL rows feed that child screen only. Source:
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


# Values read from the NASEM tables; folate is stored in mcg DFE (folic acid x 1.7, matching the canonical FDA label converter;
# 14-18 = 800 x 1.7 = 1360), choline/phosphorus/chloride in mg (table g/d).
@pytest.mark.parametrize("nutrient,expected", [
    ("vitamin_a", (600, 900, 1700)),
    ("vitamin_c", (400, 650, 1200)),
    ("vitamin_d", (63, 75, 100)),
    ("folate", (510, 680, 1020)),
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
    # An upper bound stated in months stays an upper bound (outside review, 2026-10-19).
    (["Children under 12 months"], ("0-1",)),
    (["Children less than 24 months"], ("0-1", "1-3")),
    (["Children 12-36 months"], ("1-3",)),
])
def test_label_pediatric_age_ranges_cover_every_dsld_child_tag(groups, expected):
    assert rda_ul_calculator.label_pediatric_age_ranges({"targetGroups": groups}) == expected


# Which labels carry child notes: the one children's-product rule shared with omega Evidence.
@pytest.mark.parametrize("product,expected", [
    ({"targetGroups": ["Children 4 or More Years of Age"]}, ("4-8", "9-13", "14-18")),
    ({"targetGroups": ["Infants/Baby (0 - 1 Year)"]}, ("0-1",)),
    # A DSLD child tag beside an adult tag does not make an adult product a children's product.
    ({"targetGroups": ["Adult (18 - 50 Years)", "Children 4 or More Years of Age"]}, None),
    ({"fullName": "Women's Advanced Multivitamin",
      "targetGroups": ["Girls: (All)", "Adult Female (18 - 50 Years)"]}, None),
    ({"targetGroups": ["Adult (18 - 50 Years)"]}, None),
    # A title-only children's product is read from its title.
    ({"fullName": "Kids Multivitamin Gummies", "targetGroups": []}, ("1-3", "4-8", "9-13", "14-18")),
    ({"fullName": "Baby Vitamin D Drops", "targetGroups": []}, ("0-1",)),
    ({"fullName": "Kids Chewable Ages 4+", "targetGroups": []}, ("4-8", "9-13", "14-18")),
])
def test_child_notes_cover_childrens_products_only(enricher, product, expected):
    assert rda_ul_calculator.label_child_ul_ages(product) == expected
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


def _collect(enricher, groups, *rows):
    return enricher._collect_rda_ul_data(
        {"targetGroups": groups, "activeIngredients": list(rows), "inactiveIngredients": []},
        min_servings_per_day=1, max_servings_per_day=1)


def _adequacy(rda, canonical_id):
    return next(r for r in rda["adequacy_results"] if r.get("canonical_id") == canonical_id)


@pytest.mark.parametrize("groups,expected", [
    (["Children 4 or More Years of Age"], ("general_adult",)),
    (["Adult (18 - 50 Years)", "Girls: (All)"], ("general_adult",)),
    (["Infants/Baby (0 - 1 Year)"], ("general_adult",)),
    (["Pregnant Women", "Children (All)"], ("pregnancy_lactation",)),
    (["Seniors/Mature (>50 Years)", "Boys: (All)"], ("adults_51_plus",)),
])
def test_the_score_screens_adult_populations_only(enricher, groups, expected):
    assert enricher._ul_screening_population({"targetGroups": groups}) == expected


def test_adult_product_with_a_broad_girls_tag_is_an_adult_product(enricher):
    # Shape of MegaFood Women's Advanced Multivitamin (327574): adult directions, DSLD files it
    # under "Girls: (All)" beside adult groups, 15 mg zinc at the directed two tablets.
    from scoring_v4.dose_safety import evaluate_dose_safety
    rda = _collect(enricher, ["Adult (18 - 50 Years)", "Girls: (All)"], _row("Zinc", "zinc", 15))
    row = _adequacy(rda, "zinc")
    assert row["ul"] == 40 and row["ul_population"]["id"] == "general_adult"
    assert not [flag for flag in rda["safety_flags"] if flag.get("ul_gate_eligible") is True]
    assert evaluate_dose_safety({"rda_ul_data": rda}).dose_ceiling() is None
    assert rda["child_ul_screen"] == []


def test_childrens_product_note_names_the_applicable_child_limit(enricher):
    from scoring_v4.dose_safety import evaluate_dose_safety
    rda = _collect(enricher, ["Children (All)"], _row("Zinc", "zinc", 15))
    assert _adequacy(rda, "zinc")["ul"] == 40
    assert evaluate_dose_safety({"rda_ul_data": rda}).dose_ceiling() is None
    [note] = rda["child_ul_screen"]
    assert note["status"] == "over_limit" and note["ul"] == 7 and note["canonical_id"] == "zinc"
    assert note["ul_population"]["label"] == "children 1-3"
    assert "upper limit for children 1-3 of 7 mg" in note["warning"]


def test_children_4_plus_vitamin_c_note_names_the_4_8_limit(enricher):
    rda = _collect(enricher, ["Children 4 or More Years of Age"], _row("Vitamin C", "vitamin_c", 1000))
    assert _adequacy(rda, "vitamin_c")["ul"] == 2000
    assert not rda["safety_flags"]
    [note] = rda["child_ul_screen"]
    assert note["status"] == "over_limit" and note["ul"] == 650
    assert note["pct_ul"] == pytest.approx(100 * 1000 / 650)
    assert "upper limit for children 4-8 of 650 mg" in note["warning"]


def test_within_child_limits_emits_no_note(enricher):
    rda = _collect(enricher, ["Children 4 or More Years of Age"], _row("Calcium", "calcium", 500))
    assert rda["child_ul_screen"] == []


def test_no_established_ul_emits_no_child_note(enricher):
    rda = _collect(enricher, ["Children 4 or More Years of Age"],
                   _row("Vitamin B12", "vitamin_b12", 10, "mcg"))
    assert rda["child_ul_screen"] == []


def test_a_label_without_children_has_no_child_screen(enricher):
    rda = _collect(enricher, ["Adult (18 - 50 Years)"], _row("Zinc", "zinc", 15))
    assert rda["child_ul_screen"] == []


@pytest.mark.parametrize("groups", [["Infants"], ["Infants/Baby (0 - 1 Year)"]])
def test_infant_label_is_scored_for_adults_and_infant_coverage_stays_unknown(enricher, groups):
    from scoring_v4.scored_artifact import build_scored_artifact
    product = {"id": "infant-label", "product_name": "Calcium", "targetGroups": groups,
               "servingSizes": [{"minDailyServings": 1, "maxDailyServings": 1}],
               "activeIngredients": [_row("Calcium", "calcium", 500)], "inactiveIngredients": []}
    enriched, errors = enricher.enrich_product(product)
    assert not errors
    [assessment] = enriched["rda_ul_data"]["dose_assessments"]
    assert assessment["readiness"] == "complete" and assessment["ul_value"] == 2000
    artifact = build_scored_artifact(enriched)
    assert artifact["assessment_readiness"]["dose"]["readiness"] == "complete"
    [note] = enriched["rda_ul_data"]["child_ul_screen"]
    assert note["status"] == "not_assessable" and note.get("pct_ul") is None
    assert note["reason"] == GAP and note["ul_population"]["missing_age_ranges"] == ["0-1"]


def test_known_child_exceedance_keeps_the_infant_gap_on_the_note(enricher):
    rda = _collect(enricher, ["Infants", "Children 4 or More Years of Age"], _row("Zinc", "zinc", 15))
    [note] = rda["child_ul_screen"]
    assert note["status"] == "over_limit" and note["ul"] == 12
    assert note["ul_population"]["missing_age_ranges"] == ["0-1"]


# Outside review, 2026-10-19: the bounded unknown-form shortcuts compare a worst case with adult
# constants. That is the adult score's assessment; for a child it proves nothing either way.
@pytest.mark.parametrize("name,canonical,quantity,unit", [
    ("Folate", "vitamin_b9_folate", 667, "mcg DFE"),
    ("Vitamin A", "vitamin_a", 1000, "mcg RAE"),
    ("Vitamin E", "vitamin_e", 400, "mg"),
])
def test_unknown_form_never_clears_or_flags_a_child_limit(enricher, name, canonical, quantity, unit):
    ingredient = {"name": name, "standardName": name, "canonical_id": canonical,
                  "matched_form": "standard", "quantity": quantity, "unit": unit}
    rda = _collect(enricher, ["Children 1-3 Years"], ingredient)
    [note] = rda["child_ul_screen"]
    assert note["status"] == "not_assessable"
    assert note.get("pct_ul") is None and note.get("ul") is None
    assert note["reason"]


def test_child_exposure_is_summed_across_forms_of_one_nutrient(enricher):
    rows = [{**_row("Zinc", "zinc", 8), "raw_source_path": f"ingredientRows[{index}]"} for index in range(2)]
    rda = _collect(enricher, ["Children 4 or More Years of Age"], *rows)
    assert not rda["safety_flags"]
    [note] = rda["child_ul_screen"]
    assert note["status"] == "over_limit" and note["amount"] == 16 and note["ul"] == 12
    assert note["aggregation"] == "canonical_sum" and len(note["contributing_rows"]) == 2

@pytest.mark.parametrize('amount,over', [(300, False), (301, True)])
def test_child_folic_acid_native_ul_uses_the_same_label_conversion(enricher, amount, over):
    # NASEM1-3 UL is300mcg folic acid. The production converter uses FDA label DFE x1.7;
    # mixing its510DFE exposure with a500DFE limit invents an exceedance at exactly the UL.
    rda = _collect(enricher, ['Children 1-3 Years'], _row('Folic Acid', 'vitamin_b9_folate', amount, 'mcg'))
    notes = [n for n in rda['child_ul_screen'] if n['status'] == 'over_limit']
    assert bool(notes) is over
    if over:
        assert notes[0]['ul'] == 510
        assert notes[0]['pct_ul'] == pytest.approx(amount / 300 * 100)

@pytest.mark.parametrize('amount,over', [(1000, False), (1001, True)])
def test_adult_folic_acid_native_ul_uses_the_same_label_conversion(enricher, amount, over):
    rda = _collect(enricher, ['Adult (18 - 50 Years)'], _row('Folic Acid', 'vitamin_b9_folate', amount, 'mcg'))
    row = _adequacy(rda, 'vitamin_b9_folate')
    assert row['ul'] == 1700
    assert row['over_ul'] is over
    assert row['pct_ul'] == pytest.approx(amount / 1000 * 100)


def test_child_nickel_sum_preserves_qualified_soluble_form(enricher):
    # Each known soluble-salt row exceeds the1-3 UL. Adding another real exposure
    # must not erase the concern when the aggregated comparison loses its form.
    rows = [{**_row('Nickel', 'nickel', 0.3), 'matched_form': 'nickel sulfate',
             'raw_source_path': f'ingredientRows[{i}]'} for i in range(2)]
    product = {'id':'child-nickel-sum','fullName':'Kids Nickel',
               'targetGroups':['Children 1-3 Years'], 'activeIngredients':rows,
               'inactiveIngredients':[], 'servingSizes':[{'minDailyServings':1,'maxDailyServings':1}]}
    enriched, errors = enricher.enrich_product(product)
    assert not errors
    [note] = enriched['rda_ul_data']['child_ul_screen']
    assert note['status'] == 'over_limit'
    assert note['amount'] == pytest.approx(0.6)
    assert note['ul'] == pytest.approx(0.2)
    assert note['pct_ul'] == pytest.approx(300)


def test_child_note_unresolved_comparison_remains_explicit(enricher):
    note = enricher._child_ul_note('Nickel', 'Nickel', 'nickel', ('1-3',), amount=0.3, unit='mg')
    assert note is not None
    assert note['status'] == 'not_assessable'

@pytest.mark.parametrize('tag', ['Kids 4-8 Years', 'Children 4-8 Years'])
def test_child_note_ages_honor_every_recognized_child_tag(enricher, tag):
    rda = enricher._collect_rda_ul_data({'fullName':'Kids Multivitamin','targetGroups':[tag],
        'activeIngredients':[_row('Zinc','zinc',8)],'inactiveIngredients':[]}, min_servings_per_day=1,max_servings_per_day=1)
    assert rda['child_ul_screen'] == []


def test_baby_tag_without_infant_word_keeps_infant_gap(enricher):
    rda = enricher._collect_rda_ul_data({'fullName':'Kids Minerals','targetGroups':['Baby (0-1 Year)'],
        'activeIngredients':[_row('Zinc','zinc',8)],'inactiveIngredients':[]}, min_servings_per_day=1,max_servings_per_day=1)
    [note] = rda['child_ul_screen']
    assert note['status'] == 'not_assessable'
    assert note['ul_population']['missing_age_ranges'] == ['0-1']


def test_linked_folic_acid_component_is_not_added_to_child_label_total(enricher):
    parent={**_row('Folate','vitamin_b9_folate',500,'mcg DFE'),
            'raw_source_text':'Folate 500 mcg DFE (300 mcg folic acid)'}
    child={**_row('Folic Acid','vitamin_b9_folate',300,'mcg'),
           'raw_source_path':'ingredientRows[0].nestedRows[0]', 'isNestedIngredient':True, 'parentBlend':'Folate'}
    rda=_collect(enricher,['Children 1-3 Years'],parent,child)
    assert rda['child_ul_screen'] == []
    assert not rda['safety_flags']


@pytest.mark.parametrize('name',['Folate','Folic Acid'])
@pytest.mark.parametrize('native,dfe,cap',[(1000,1667,None),(1001,1668,10),(1500,2500,0)])
def test_printed_native_folic_acid_controls_ul_without_changing_adequacy(enricher,native,dfe,cap,name):
    from scoring_v4.dose_safety import evaluate_dose_safety
    parent={**_row(name,'vitamin_b9_folate',dfe,'mcg DFE'),
            'raw_source_text':f'Folate {dfe} mcg DFE ({native} mcg folic acid)'}
    rda=_collect(enricher,['Adult (18 - 50 Years)'],parent)
    row=_adequacy(rda,'vitamin_b9_folate')
    assert row['adequacy_exposure']['per_day'] == dfe
    assert row['safety_exposure']['per_day'] == pytest.approx(native * 1.7)
    ceiling=evaluate_dose_safety({'rda_ul_data':rda}).dose_ceiling()
    assert (ceiling['cap_public'] if ceiling else None) == cap


def test_folate_native_child_retains_real_adult_ceiling(enricher):
    from scoring_v4.dose_safety import evaluate_dose_safety
    parent={**_row('Folate','vitamin_b9_folate',2500,'mcg DFE'),
            'raw_source_text':'Folate 2500 mcg DFE (1500 mcg folic acid)'}
    child={**_row('Folic Acid','vitamin_b9_folate',1500,'mcg'),
           'raw_source_path':'ingredientRows[0].nestedRows[0]', 'isNestedIngredient':True,'parentBlend':'Folate'}
    rda=_collect(enricher,['Adult (18 - 50 Years)'],parent,child)
    assert len(rda['safety_flags']) == 1
    assert evaluate_dose_safety({'rda_ul_data':rda}).dose_ceiling()['cap_public'] == 0


def test_explicit_native_folic_acid_is_assessed_in_a_mixed_folate_declaration(enricher):
    parent={**_row('Folate','vitamin_b9_folate',2000,'mcg DFE'),
            'raw_source_text':'Folate 2000 mcg DFE (1001 mcg folic acid and L-5-MTHF)'}
    rda=_collect(enricher,['Adult (18 - 50 Years)'],parent)
    assert rda['has_over_ul'] is True


def test_independent_equal_folic_acid_rows_are_not_a_total_and_component(enricher):
    from scoring_v4.dose_safety import evaluate_dose_safety
    rows=[{**_row('Folic Acid','vitamin_b9_folate',600,'mcg'),
           'raw_source_path':f'ingredientRows[{i}]'} for i in range(2)]
    rda=_collect(enricher,['Adult (18 - 50 Years)'],*rows)
    assert len(rda['safety_flags']) == 1
    ceiling=evaluate_dose_safety({'rda_ul_data':rda}).dose_ceiling()
    assert ceiling is not None
    assert ceiling['cap_public'] == 10
    assert ceiling['pct_ul'] == pytest.approx(120)
