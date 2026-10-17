"""Declared-serving quality is independent of maximum labeled daily risk."""
from copy import deepcopy

import pytest

from test_v4_generic_dose_p132a import _ingredient, _product
from scoring_v4.scored_artifact import build_scored_artifact


def product(quantity=120, low=1, high=4):
    pct = quantity * high / 350 * 100
    p = _product(ingredients=[_ingredient(quantity=quantity)], adequacy_results=[{
        'nutrient': 'Magnesium', 'canonical_id': 'magnesium', 'amount': quantity,
        'unit': 'mg', 'rda_ai': 400, 'ul': 350, 'ul_status': 'established',
        'pct_rda': quantity * low / 400 * 100, 'pct_ul': pct,
        'servings_per_day_min': low, 'servings_per_day_max': high,
        'per_day_min': quantity * low, 'per_day_max': quantity * high,
        'scoring_eligible': True, 'ul_gate_eligible': True,
    }], safety_flags=[{'nutrient': 'Magnesium', 'pct_ul': pct, 'amount': quantity * high,
                       'ul': 350, 'ul_gate_eligible': True}] if pct > 100 else [])
    p['serving_basis'] = {'min_servings_per_day': low, 'max_servings_per_day': high,
                          'servings_per_day_source': 'directions'}
    return p


@pytest.mark.parametrize('low,high', [(1, 4), (2, 4), (.5, 1), (1, 8)])
def test_score_uses_one_declared_serving_but_preserves_daily_safety(low, high):
    p = product(low=low, high=high)
    before = deepcopy(p)
    result = build_scored_artifact(p)
    control = build_scored_artifact(product(low=1, high=1))
    assert result['quality_pillars_v4']['dose']['score'] == control['quality_pillars_v4']['dose']['score']
    assert p == before
    if high > 350 / 120:
        assert result['product_safety_status'] == 'caution'


def test_a_high_declared_serving_keeps_its_dose_deduction():
    low = build_scored_artifact(product(quantity=120, low=1, high=1))
    high = build_scored_artifact(product(quantity=600, low=1, high=1))
    assert high['quality_pillars_v4']['dose']['score'] < low['quality_pillars_v4']['dose']['score']


def test_serving_projection_preserves_units_and_does_not_turn_unknown_into_zero():
    from scoring_input_contract import declared_serving_dose_input
    p = product(low=2, high=4)
    p['rda_ul_data']['adequacy_results'][0]['pct_ul'] = None
    projected = declared_serving_dose_input(p)
    row = projected['rda_ul_data']['adequacy_results'][0]
    assert row['pct_rda'] == 30
    assert row['pct_ul'] is None
    assert row['unit'] == 'mg'


def test_serving_context_is_scoped_and_does_not_change_label_frequency():
    from scoring_v4.modules.generic_helpers import score_declared_serving_dose
    from serving_frequency import resolve_daily_serving_range
    p = product(low=2, high=4)
    observed = []
    def consumer(projected):
        observed.append(resolve_daily_serving_range(projected)[:2])
        return {'metadata': {}}
    result = score_declared_serving_dose(p, consumer)
    assert observed == [(1, 1)]
    assert resolve_daily_serving_range(p)[:2] == (2, 4)
    assert result['metadata']['assessment_basis'] == 'declared_serving'
