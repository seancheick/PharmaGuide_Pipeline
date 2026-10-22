"""Dose V4.1 §2.4 (D1): one product-level safety ceiling, applied once after
normalization. ≤100% none; >100% and <150% → at most 10; ≥150% → 0."""
import pytest

from test_v4_generic_dose_p132a import _ingredient, _product
from scoring_v4.scored_artifact import build_scored_artifact


def _row(nutrient, canonical, pct_rda, pct_ul, *, low=1, high=1):
    return {'nutrient': nutrient, 'canonical_id': canonical, 'unit': 'mg', 'rda_ai': 400, 'ul': 350,
            'ul_status': 'established', 'pct_rda': pct_rda, 'pct_ul': pct_ul,
            'servings_per_day_min': low, 'servings_per_day_max': high,
            'scoring_eligible': True, 'ul_gate_eligible': True}


def _flag(nutrient, canonical, pct_ul, eligible=True):
    return {'nutrient': nutrient, 'canonical_id': canonical, 'pct_ul': pct_ul, 'amount': 3.5 * pct_ul,
            'ul': 350, 'ul_gate_eligible': eligible}


def product(pct_ul, *, pct_rda=60.0, low=1, high=1, eligible=True, rows=None, flags=None):
    p = _product(ingredients=[_ingredient(quantity=120)],
                 adequacy_results=rows or [_row('Magnesium', 'magnesium', pct_rda, pct_ul, low=low, high=high)],
                 safety_flags=flags if flags is not None else (
                     [_flag('Magnesium', 'magnesium', pct_ul, eligible)] if pct_ul > 100 else []))
    p['serving_basis'] = {'min_servings_per_day': low, 'max_servings_per_day': high,
                          'servings_per_day_source': 'directions'}
    return p


def dose(p):
    return build_scored_artifact(p)['quality_pillars_v4']['dose']


@pytest.mark.parametrize('pct,expected', [(100.0, 20.0), (100.01, 10.0), (149.99, 10.0), (150.0, 0.0), (240.0, 0.0)])
def test_exact_ceiling_boundaries(pct, expected):
    assert dose(product(pct))['score'] == expected


def test_ceiling_never_raises_a_lower_adequacy_score():
    low = dose(product(50.0, pct_rda=5.0))['score']
    assert 0 < low < 10
    assert dose(product(120.0, pct_rda=5.0))['score'] == low


def test_one_excessive_nutrient_is_not_diluted_by_a_panel():
    rows = [_row('Magnesium', 'magnesium', 60.0, 30.0), _row('Zinc', 'zinc', 300.0, 160.0)]
    assert dose(product(0, rows=rows, flags=[_flag('Zinc', 'zinc', 160.0)]))['score'] == 0.0


def test_an_incidental_nutrient_without_an_adequacy_vote_still_counts():
    flags = [_flag('Vitamin B6', 'vitamin_b6_pyridoxine', 120.0)]
    assert dose(product(30.0, flags=flags))['score'] == 10.0


def test_unresolved_comparison_keeps_review_state_without_a_ceiling():
    assert dose(product(130.0, eligible=False))['score'] == 20.0


def test_no_dose_safety_subtraction_remains_and_the_evaluation_is_kept():
    a = build_scored_artifact(product(160.0))
    dim = a['_v4_module_breakdown']['dimensions']['dose']
    assert 'B7_dose_safety' not in dim['penalties']
    assert dim['metadata']['B7_safety_evaluation']['state_counts'] == {'confirmed_over_threshold': 1}
    assert a['quality_pillars_v4']['safety_hygiene']['score'] == 10.0


def test_explanation_distinguishes_minimum_from_maximum_exceedance():
    always_pillar = dose(product(120.0))
    ranged_pillar = dose(product(137.0, pct_rda=30.0, low=1, high=4))
    always, ranged = always_pillar['reason'], ranged_pillar['reason']
    assert 'even the lowest directed daily use' in always.lower()
    assert 'higher directed daily amounts' in ranged.lower()
    for pillar in (always_pillar, ranged_pillar):
        # One-sentence reason; the policy statement is kept as audit detail.
        assert 'scoring policy' not in pillar['reason'].lower()
        facts = {f['id']: f for f in pillar['explanation']['facts']}
        assert 'pharmaguide scoring policy' in facts['dose_safety_ceiling']['value_display'].lower()
        assert facts['dose_safety_ceiling']['audience'] == 'audit'
        assert facts['dose_upper_limit_result']['audience'] == 'consumer'


def test_receipt_itemizes_the_ceiling_and_reconciles():
    pillar = dose(product(137.0, pct_rda=30.0, low=1, high=4))
    assert pillar['score'] == 18.0
    entries = pillar['receipt']['entries']
    cap = [e for e in entries if e['id'] == 'dose_safety_ceiling']
    assert cap and cap[0]['kind'] == 'deduction' and cap[0]['points'] == -2.0
    assert round(sum(e['points'] for e in entries), 4) == 18.0


def test_the_ceiling_names_the_reference_nutrient_not_the_label_brand():
    # A row flag carries the label text (e.g. "VEGADELIGHT"); the explanation
    # names the nutrient whose limit applies.
    flags = [{**_flag('VEGADELIGHT', None, 125.0), 'reference_nutrient': 'Vitamin D'}]
    reason = dose(product(30.0, flags=flags))['reason']
    assert 'Vitamin D' in reason and 'VEGADELIGHT' not in reason


def test_enriched_row_flags_carry_the_reference_nutrient():
    from enrich_supplements_v3 import SupplementEnricherV3
    product_in = {"activeIngredients": [{"name": "Zinc Gluconate Complex", "standardName": "Zinc",
                                         "canonical_id": "zinc", "canonical_source_db": "ingredient_quality_map",
                                         "quantity": 200, "unit": "mg", "dailyValue": 1818.0}],
                  "inactiveIngredients": []}
    result = SupplementEnricherV3()._collect_rda_ul_data(product_in, min_servings_per_day=1, max_servings_per_day=1)
    assert result["safety_flags"][0]["reference_nutrient"] == "Zinc"


def test_a_neutral_adequacy_under_a_ceiling_takes_the_lower_value():
    # No benchmark (neutral 11.4) and a 120% exceedance: the cap of 10 applies;
    # at 160% Dose is 0. The ceiling never lifts a neutral.
    from test_v4_generic_dose_p132a import _ingredient, _product
    for pct, expected in ((120.0, 10.0), (160.0, 0.0), (90.0, 11.4)):
        p = _product(ingredients=[_ingredient(name="Ashwagandha", canonical_id="unbenchmarked_botanical", quantity=300)],
                     adequacy_results=[], safety_flags=[_flag('Zinc', 'zinc', pct)] if pct > 100 else [])
        assert dose(p)['score'] == expected, pct


def test_the_ceiling_starts_where_a_confirmed_exceedance_starts():
    from scoring_v4 import dose_safety
    assert float(dose_safety._CEILING["exceeds_above_pct"]) == dose_safety._CONFIRMED_UL_EXCEEDANCE_PCT == 100.0


def test_optional_higher_use_keeps_earned_minimum_dose_credit():
    # Sean2026-10-22: optional high use is a small deduction, not loss of
    # otherwise earned adequacy. Exact magnitude is owned by approved config.
    fixed = dose(product(50.0))
    optional = dose(product(150.0, low=1, high=3))
    assert fixed['score'] == 20.0
    assert optional['score'] == fixed['score'] - 2.0
    assert optional['components']['adequacy_before_safety'] == fixed['score']


def test_optional_excess_does_not_remove_safety_finding():
    artifact = build_scored_artifact(product(150.0, low=1, high=3))
    evaluation = artifact['_v4_module_breakdown']['dimensions']['dose']['metadata']['B7_safety_evaluation']
    assert evaluation['state_counts']['confirmed_over_threshold'] == 1
    assert evaluation['flags'][0]['pct_ul'] == 150.0
    assert evaluation['flags'][0]['pct_ul_at_minimum'] == 50.0


@pytest.mark.parametrize('pct', [100.01, 137.0, 150.0, 299.99, 300.0])
def test_optional_deduction_is_two_points_regardless_of_high_end(pct):
    assert dose(product(pct, low=1, high=3))['score'] == 18.0


def test_optional_deduction_is_once_and_never_negative():
    flags = [_flag('Magnesium', 'magnesium', 150), _flag('Zinc', 'zinc', 160)]
    assert dose(product(150, low=1, high=3, flags=flags))['score'] == 18.0
    baseline = dose(product(50, pct_rda=0.1, low=1, high=3))['score']
    assert baseline < 2
    assert dose(product(150, pct_rda=0.1, low=1, high=3))['score'] == 0


def test_minimum_exceedance_retains_stronger_rule():
    assert dose(product(300.01, low=1, high=3))['score'] == 0.0


def test_optional_receipt_reconciles_and_retains_reference():
    p = dose(product(150, low=1, high=3))
    assessment = p['explanation']['dose_receipt']
    assert assessment['upper_reference']['deduction_public'] == 2
    assert assessment['upper_reference']['pct_ul'] == 150
    assert assessment['reconciles'] is True
    assert p['receipt']['realized_deductions'] == -2.0
