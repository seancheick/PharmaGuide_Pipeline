"""Dose V4.1 §3.1 calibrations (Sean, 2026-10-17): ordinary-adult references.

Magnesium 84 mg and calcium 260 mg elemental per minimum directed day are
PharmaGuide contribution-policy targets (20% of the FDA Daily Value), scored
20 x min(amount / target, 1). Potassium is a completed neutral. Ordinary omega
EPA+DHA is proportional to 250 mg/day; an explicit triglyceride purpose uses
2,000 mg/day; prenatal products use the 200 mg DHA reference."""
import json
from pathlib import Path

import pytest

from test_v4_generic_dose_p132a import _ingredient, _product
from test_v4_omega_dose_p162 import _omega_product
from scoring_v4.scored_artifact import build_scored_artifact
from scoring_v4.modules.omega_dose import score_dose as omega_dose

SCRIPTS = Path(__file__).resolve().parents[1]


def _mineral(canonical, name, amount, rda, ul, *, population=None):
    row = {'nutrient': name, 'canonical_id': canonical, 'unit': 'mg', 'rda_ai': rda, 'ul': ul,
           'ul_status': 'established', 'pct_rda': amount / rda * 100, 'pct_ul': amount / ul * 100,
           'per_day_min': amount, 'per_day_max': amount, 'scoring_eligible': True, 'ul_gate_eligible': True}
    if population:
        row['ul_population'] = {'id': population}
    p = _product(ingredients=[_ingredient(name=name, canonical_id=canonical, quantity=amount)],
                 adequacy_results=[row], safety_flags=[])
    p['serving_basis'] = {'min_servings_per_day': 1, 'max_servings_per_day': 1,
                          'servings_per_day_source': 'directions'}
    return p


def _dose(p):
    return build_scored_artifact(p)['quality_pillars_v4']['dose']['score']


@pytest.mark.parametrize('amount,expected', [(84, 20.0), (42, 10.0), (120, 20.0), (21, 5.0)])
def test_magnesium_is_proportional_to_84_mg_then_plateaus(amount, expected):
    assert _dose(_mineral('magnesium', 'Magnesium', amount, 400, 350)) == expected


@pytest.mark.parametrize('amount,expected', [(260, 20.0), (130, 10.0), (600, 20.0)])
def test_calcium_is_proportional_to_260_mg_then_plateaus(amount, expected):
    assert _dose(_mineral('calcium', 'Calcium', amount, 1000, 2000)) == expected


def test_prenatal_population_keeps_its_own_reference():
    # 84 mg against the legacy 25%-of-RDA band (100 mg), not the adult target.
    assert _dose(_mineral('magnesium', 'Magnesium', 84, 400, 350, population='pregnancy_lactation')) == 16.8


def test_a_label_that_includes_pregnancy_keeps_the_prenatal_reference():
    # A label stating adults and pregnancy screens both populations' limits;
    # the ordinary-adult contribution target does not apply to it.
    p = _mineral('magnesium', 'Magnesium', 84, 400, 350)
    p['rda_ul_data']['adequacy_results'][0]['ul_population'] = {
        'id': 'general_adult+pregnancy_lactation', 'members': ['general_adult', 'pregnancy_lactation']}
    assert _dose(p) == 16.8


def test_potassium_is_a_completed_neutral():
    artifact = build_scored_artifact(_mineral('potassium', 'Potassium', 99, 3400, 99000))
    assert artifact['quality_pillars_v4']['dose']['score'] == 11.4
    assert artifact['quality_assessment_status'] == 'complete'


def test_no_ordinary_target_requires_more_than_its_supplemental_ul():
    targets = json.loads((SCRIPTS / 'scoring_v4/config/quality_score.json').read_text())[
        'dose_magnitudes']['generic']['contribution_policy_targets']
    data = json.loads((SCRIPTS / 'data/rda_optimal_uls.json').read_text())['nutrient_recommendations']
    for canonical, record in targets.items():
        if canonical.startswith('_'):
            continue
        entry = next(e for e in data if e['id'] == canonical)
        adult_uls = [r['ul'] for r in entry['data'] if r['group'] in ('Male', 'Female')
                     and r['age_range'] != '14-18' and isinstance(r['ul'], (int, float))]
        assert record['target_mg'] < min(adult_uls), canonical


def _score(product):
    return omega_dose(product)['components'].get('epa_dha_band', 0.0)


@pytest.mark.parametrize('epa,dha,expected', [(150, 100, 20.0), (75, 50, 10.0), (1500, 900, 20.0), (40, 10, 4.0)])
def test_ordinary_omega_is_proportional_to_250_mg(epa, dha, expected):
    assert _score(_omega_product(epa=epa, dha=dha)) == expected


def test_prescription_amount_keeps_its_context_flag_without_extra_credit():
    payload = omega_dose(_omega_product(epa=2500, dha=2000))
    assert payload['components']['epa_dha_band'] == 20.0
    assert payload['metadata']['epa_dha_band_flag'] == 'PRESCRIPTION_DOSE_OMEGA3'


def test_explicit_triglyceride_purpose_uses_2000_mg():
    product = _omega_product(epa=600, dha=400)
    product['statements'] = [{'notes': 'Helps lower triglycerides as part of a healthy diet.'}]
    payload = omega_dose(product)
    assert payload['components']['epa_dha_band'] == 10.0
    assert payload['metadata']['adequacy_reference']['purpose'] == 'triglyceride'


@pytest.mark.parametrize('epa,dha,expected', [(0, 200, 20.0), (200, 100, 10.0)])
def test_prenatal_omega_uses_the_dha_reference_only(epa, dha, expected):
    product = _omega_product(epa=epa or None, dha=dha)
    product['product_name'] = 'Prenatal DHA'
    assert _score(product) == expected


def test_child_omega_keeps_its_existing_reference():
    product = _omega_product(epa=300, dha=200)
    product['product_name'] = 'Kids Omega'
    assert _score(product) == 10.0


def test_potassium_named_as_the_product_purpose_is_also_a_completed_neutral():
    product = _mineral('potassium', 'Potassium', 99, 3400, 99000)
    product['product_name'] = 'Potassium 99 mg'
    artifact = build_scored_artifact(product)
    assert artifact['quality_pillars_v4']['dose']['score'] == 11.4
    assert artifact['quality_assessment_status'] == 'complete'


def test_a_prenatal_title_that_mentions_baby_still_uses_the_prenatal_dha_reference():
    # "Baby & Me 2 Prenatal DHA" is a maternal product; the Evidence hold for a
    # child/baby title must not send its Dose to the child bands.
    product = _omega_product(epa=None, dha=250)
    product['product_name'] = 'Baby & Me 2 Prenatal DHA & Choline'
    payload = omega_dose(product)
    assert payload['metadata']['adequacy_reference']['purpose'] == 'prenatal_dha'
    assert payload['components']['epa_dha_band'] == 20.0


def _calcium_serving(per_serving, servings):
    p = _mineral('calcium', 'Calcium', per_serving * servings, 1000, 2000)
    row = p['rda_ul_data']['adequacy_results'][0]
    row.update(amount=per_serving, per_day_min=per_serving * servings, per_day_max=per_serving * servings)
    p['serving_basis'] = {'min_servings_per_day': servings, 'max_servings_per_day': servings,
                          'servings_per_day_source': 'directions'}
    return p


def _facts(product):
    dose = build_scored_artifact(product)['quality_pillars_v4']['dose']
    return dose['score'], {f['id']: f['value_display'] for f in dose['explanation']['facts']}


def test_calcium_above_500_mg_per_serving_is_absorption_context_only():
    single, facts = _facts(_calcium_serving(600, 1))
    divided, divided_facts = _facts(_calcium_serving(300, 2))
    assert single == divided == 20.0  # no numerical penalty
    assert 'does not change the score' in facts['dose_absorption_context']
    assert '500 mg or less at a time' in facts['dose_absorption_context']
    assert 'dose_absorption_context' not in divided_facts  # 300 mg per serving


def test_niacinamide_ceiling_copy_does_not_claim_flushing():
    from test_dose_final_safety_ceiling import product as ceiling_product
    p = ceiling_product(130.0, flags=[{'nutrient': 'Niacinamide', 'reference_nutrient': 'Niacin',
                                       'pct_ul': 130.0, 'ul': 35, 'ul_gate_eligible': True}])
    dose = build_scored_artifact(p)['quality_pillars_v4']['dose']
    text = dose['reason'] + ' '.join(f['value_display'] for f in dose['explanation']['facts'])
    assert 'Niacin' in dose['reason'] and 'flush' not in text.lower()
