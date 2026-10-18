"""Dose V4.1 §4: every Dose receipt shows daily use, what was assessed and how
it combines, adequacy before safety, the upper reference with its population,
exposure and cap, and a final Dose that reconciles exactly."""
import sys

import pytest

from test_dose_final_safety_ceiling import product as ceiling_product
from scoring_v4.scored_artifact import build_scored_artifact


def _suite():
    import audit_v4_archetype_fixtures as fixtures
    return fixtures.load_fixture_suite().cases


@pytest.mark.parametrize("case", _suite(), ids=lambda case: case.case_id)
def test_every_archetype_dose_receipt_reconciles(case):
    pillars = build_scored_artifact(case.product).get("quality_pillars_v4")
    if not pillars:
        pytest.skip("not scored")
    dose = pillars["dose"]
    receipt = dose["explanation"]["dose_receipt"]
    if receipt.get("assessment_status") == "incomplete":
        assert case.product.get("nutrition_summary", {}).get("protein_g") is None
        assert case.case_id.startswith("sports_protein__")
        assert build_scored_artifact(case.product)["quality_assessment_status"] == "partial"
        assert receipt["final"] is None and receipt["reconciles"] is None
        return
    assert receipt["reconciles"] is True
    assert receipt["final"] == dose["score"]
    assert receipt["aggregation"] is not None, case.case_id
    assert any(fact["id"] == "dose_arithmetic" for fact in dose["explanation"]["facts"])
    if receipt["upper_reference"]:
        assert dose["score"] <= receipt["upper_reference"]["cap_public"]


def test_the_worked_example_reads_like_the_plan():
    # 120 mg magnesium, 1-4 servings (Pure 205309 shape): adequacy 20, cap 10.
    product = ceiling_product(137.14, pct_rda=30.0, low=1, high=4)
    row = product["rda_ul_data"]["adequacy_results"][0]
    row.update(per_day_min=120.0, per_day_max=480.0)
    product["product_name"] = "Magnesium Glycinate"
    dose = build_scored_artifact(product)["quality_pillars_v4"]["dose"]
    receipt = dose["explanation"]["dose_receipt"]
    assert receipt["daily_use"] == {"minimum_servings": 1.0, "maximum_servings": 4.0, "defaulted": False}
    [item] = receipt["contributions"]
    assert item["reference_kind"] == "pharmaguide_policy" and item["reference_value"] == 84.0
    assert item["pct_of_reference"] == pytest.approx(142.86, abs=0.01)
    assert (item["amount_at_minimum"], item["amount_at_maximum"]) == (120.0, 480.0)
    upper = receipt["upper_reference"]
    assert upper["ul"] == 350.0 and upper["ul_population"] == "general adult" and upper["cap_public"] == 10.0
    assert receipt["adequacy_before_safety"] == 20.0 and receipt["final"] == 10.0
    facts = {fact["id"]: fact["value_display"] for fact in dose["explanation"]["facts"]}
    assert facts["dose_arithmetic"] == "Adequacy 20/20, capped at 10: Dose 10/20."
    assert "(general adult limit)" in facts["dose_upper_reference"]
    assert "PharmaGuide scoring policy" in facts["dose_upper_reference"]


def test_incomplete_coprimary_receipt_never_awards_known_peer_points_as_final():
    from test_v4_sports_dose_p171 import _product, _row
    from scoring_v4.scored_artifact import build_scored_artifact
    missing = {**_row('beta_alanine', 1, 'Gram(s)'), 'quantity':None, 'unit':''}
    product = _product(_row('creatine_monohydrate',5,'Gram(s)'), missing,
                       name='Creatine + Beta-Alanine', primary_type='pre_workout')
    artifact = build_scored_artifact(product)
    pillar = artifact['quality_pillars_v4']['dose']
    assert artifact['quality_assessment_status'] == 'partial'
    receipt = pillar['explanation']['dose_receipt']
    assert receipt['assessment_status'] == 'incomplete'
    assert receipt['final'] is None and receipt['adequacy_before_safety'] is None
    assert receipt['reconciles'] is None
    facts = pillar['explanation']['facts']
    assert any(f['id']=='dose_assessment_incomplete' for f in facts)
    assert not any(f['id']=='dose_arithmetic' for f in facts)


@pytest.mark.parametrize('amount', [None,225.0])
def test_prenatal_choline_explains_dietary_reference_and_separate_weighting(amount):
    from scoring_v4.modules.multi_prenatal_dose import score_dose
    from scoring_v4.pillar_explanations import _dose_receipt_facts
    rows = [] if amount is None else [{'nutrient':'Choline','canonical_id':'choline',
        'amount':amount,'per_day_min':amount,'per_day_max':amount,'unit':'mg',
        'pct_rda':100*amount/550,'rda_ai':550,
        'data_by_group':[{'group':'Pregnancy','age_range':'19-30','rda_ai':450}]}]
    dose=score_dose({'product_name':'Prenatal multivitamin','rda_ul_data':{'adequacy_results':rows}})
    facts=_dose_receipt_facts({'aggregation':'panel','contributions':[],
                              'reference_assessments':dose['metadata']['reference_assessments']},dose['metadata'])
    choline=next(f for f in facts if f['id']=='dose_prenatal_choline')
    text=choline['value_display']
    assert 'food' in text and 'required supplement amount' in text
    if amount is None:
        assert 'No choline contribution identified' in text and 'total intake is zero' in text
    else:
        assert '225 mg' in text and '50%' in text
        assert 'broad panel' in text and 'critical' in text


@pytest.mark.parametrize('identity,amount,label', [('creatine_monohydrate',3,'contribution'),('alpha_gpc',300,'neutral')])
def test_sports_receipt_distinguishes_policy_from_clinical_minimum(identity,amount,label):
    from test_v4_sports_dose_p171 import _product,_row
    a=build_scored_artifact(_product(_row(identity,amount,'g' if identity=='creatine_monohydrate' else 'mg'),name=identity,primary_type='pre_workout'))
    item=a['quality_pillars_v4']['dose']['explanation']['dose_receipt']['contributions'][0]
    assert item['reference_kind']=='pharmaguide_policy'
    assert label in item['reference'].lower()
