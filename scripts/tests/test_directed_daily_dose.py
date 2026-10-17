"""Dose V4.1 exposure: adequacy at minimum directed daily use, safety at maximum."""
from copy import deepcopy

from test_v4_generic_dose_p132a import _ingredient, _product
from scoring_v4.scored_artifact import build_scored_artifact


def product(quantity=120, low=1, high=4, directions=True):
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
    if directions:
        p['serving_basis'] = {'min_servings_per_day': low, 'max_servings_per_day': high,
                              'servings_per_day_source': 'directions'}
    return p


def dose(artifact):
    return artifact['quality_pillars_v4']['dose']['score']


def test_maximum_directed_use_reaches_dose_safety_and_does_not_mutate_input():
    p = product(low=1, high=4)
    before = deepcopy(p)
    ranged = build_scored_artifact(p)
    once = build_scored_artifact(product(low=1, high=1))
    assert p == before
    assert dose(ranged) < dose(once)
    assert ranged['product_safety_status'] == 'caution'


def test_dose_metadata_names_the_directed_daily_interval():
    meta = build_scored_artifact(product(low=1, high=4))['_v4_module_breakdown']['dimensions']['dose']['metadata']
    assert meta['assessment_basis'] == 'directed_daily_use'
    assert meta['daily_use'] == {'minimum_servings': 1.0, 'maximum_servings': 4.0, 'defaulted': False}


def test_missing_directions_default_to_one_identified_serving():
    meta = build_scored_artifact(product(low=1, high=1, directions=False))['_v4_module_breakdown']['dimensions']['dose']['metadata']
    assert meta['daily_use'] == {'minimum_servings': 1.0, 'maximum_servings': 1.0, 'defaulted': True}


def test_intermittent_directions_are_assessed_at_their_daily_exposure():
    # 600 mg every other day is 300 mg/day: below the 350 mg UL, so no excess.
    a = build_scored_artifact(product(quantity=600, low=.5, high=.5))
    assert a['product_safety_status'] == 'no_known_catalog_concern'
    assert a['_v4_module_breakdown']['dimensions']['dose']['penalties'].get('B7_dose_safety', 0) == 0


def test_module_reassembly_keeps_the_sports_subtype():
    # A cross-cutting reassembly once rebuilt module metadata without the sports
    # subtype, so a protein product fell back to the sports_single archetype.
    from scoring_v4.modules.generic import _assemble_score
    from scoring_v4.modules.sports import score_sports
    result = score_sports({'product_name': 'Whey Protein', 'primary_type': 'protein_powder'})
    subtype = result.metadata['sports_subtype']
    _assemble_score(result)
    assert result.metadata['sports_subtype'] == subtype
