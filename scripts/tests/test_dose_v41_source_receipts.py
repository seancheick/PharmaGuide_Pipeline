"""Independent source-failure and receipt regressions for the Dose V4.1 audit."""
from copy import deepcopy

import pytest

from scoring_v4.scored_artifact import build_scored_artifact
from scoring_v4.modules.probiotic_dose import score_dose as probiotic_dose
from test_probiotic_label_dose_independence import owned_label, aggregate_label
from test_dose_final_safety_ceiling import product as ceiling_product
from test_v4_sports_dose_p171 import _product, _row
from test_v4_omega_dose_p162 import _omega_product


def strict_probiotic():
    p = owned_label()
    p['primary_type'] = 'probiotic'
    p['supplement_taxonomy'] = {'primary_type': 'probiotic'}
    row = p['activeIngredients'][0]
    p['ingredient_quality_data'] = {'ingredients_scorable': [{**row,
        'canonical_id': 'lactobacillus_rhamnosus', 'mapped': True, 'bio_score': 12,
        'standard_name': row['name']}]}
    p['probiotic_data']['is_probiotic_product'] = True
    return p


@pytest.mark.parametrize('kind', ['conflicting_rows', 'conflicting_units', 'missing', 'invalid', 'identity_mismatch'])
def test_lost_or_conflicting_disclosed_cfu_keeps_source_hold(kind):
    p = strict_probiotic()
    blend = p['probiotic_data']['probiotic_blends'][0]
    if kind == 'conflicting_rows':
        other = deepcopy(blend)
        other['cfu_data']['cfu_count'] = 50e9
        p['probiotic_data']['probiotic_blends'].append(other)
    elif kind == 'conflicting_units':
        blend['cfu_data']['billion_count'] = 50
    elif kind == 'missing':
        blend['cfu_data']['cfu_count'] = None
    elif kind == 'invalid':
        blend['cfu_data']['cfu_count'] = float('nan')
    else:
        blend['strains'] = ['Bifidobacterium lactis BB-12']
    a = build_scored_artifact(p)
    assert a['quality_score_status'] == 'not_scored'
    assert a['score_unavailable_reason'] == 'blocked_by_completeness_gate'
    assert probiotic_dose(p)['score'] is None


def test_valid_cfu_and_truly_hidden_strain_amounts_remain_assessable():
    assert build_scored_artifact(strict_probiotic())['quality_score_status'] == 'scored'
    assert probiotic_dose(aggregate_label())['score'] == 8.55


def test_magnesium_receipt_does_not_expand_supplemental_ul_to_food():
    p = ceiling_product(137.14, pct_rda=30, low=1, high=4)
    p['product_name'] = 'Magnesium Glycinate'
    facts = build_scored_artifact(p)['quality_pillars_v4']['dose']['explanation']['facts']
    scope = next(f['value_display'] for f in facts if f['id'] == 'dose_safety_ceiling')
    assert 'Limits cover total intake from all sources' not in scope


def test_sports_receipt_records_its_serving_and_daily_exposure():
    p = _product(_row('creatine_monohydrate', 5, 'Gram(s)'), _row('beta_alanine', 1, 'Gram(s)'),
                 name='Creatine + Beta-Alanine', primary_type='pre_workout')
    receipt = build_scored_artifact(p)['quality_pillars_v4']['dose']['explanation']['dose_receipt']
    assert receipt['contributions']
    for row in receipt['contributions']:
        assert {'amount_per_serving', 'amount_at_minimum', 'amount_at_maximum'} <= row.keys()
    assert receipt['reconciles'] is True


def test_triglyceride_reference_is_not_mislabeled_nutritional_reference():
    p = _omega_product(epa=600, dha=400)
    p['statements'] = [{'notes': 'Helps lower triglycerides as part of a healthy diet.'}]
    receipt = build_scored_artifact(p)['quality_pillars_v4']['dose']['explanation']['dose_receipt']
    assert receipt['contributions'][0]['reference_kind'] == 'pharmaguide_policy'


@pytest.mark.parametrize('alias', ['L. rhamnosus GG', 'Lacticaseibacillus rhamnosus GG'])
@pytest.mark.parametrize('count', [10e9, 50e9])
def test_same_source_cfu_aliases_share_one_identity(alias, count):
    p = strict_probiotic()
    original = probiotic_dose(p)['score']
    other = deepcopy(p['probiotic_data']['probiotic_blends'][0])
    other['strains'] = [alias]
    other['cfu_data']['cfu_count'] = count
    p['probiotic_data']['probiotic_blends'].append(other)
    if count == 10e9:
        assert probiotic_dose(p)['score'] == original
    else:
        assert build_scored_artifact(p)['quality_score_status'] == 'not_scored'


def test_qualified_caffeine_receipt_preserves_label_uncertainty():
    p = _product({**_row('caffeine', 600, 'mg'), 'quantity_operator': '<'},
                 name='Caffeine', primary_type='pre_workout')
    explanation = build_scored_artifact(p)['quality_pillars_v4']['dose']['explanation']
    assert explanation['dose_receipt']['contributions'][0]['quantity_operator'] == '<'
    fact = next(f['value_display'] for f in explanation['facts'] if f['id'] == 'dose_contributions')
    assert '<600' in fact and 'caffeine above400' not in fact.replace(' ', '')


def test_prenatal_receipt_uses_the_reference_actually_assessed():
    from scoring_v4.modules.multi_prenatal_dose import score_dose
    p = {'product_name': 'Prenatal multivitamin', 'rda_ul_data': {'adequacy_results': [
        {'nutrient': 'Iron', 'amount': 27, 'unit': 'mg', 'per_day_min': 27, 'per_day_max': 27,
         'rda_ai': 18, 'pct_rda': 150, 'data_by_group': [
             {'group': 'Pregnancy', 'age_range': '19-30', 'rda_ai': 27}]}]}}
    [row] = score_dose(p)['metadata']['reference_assessments']
    assert row['rda_ai'] == 27 and row['pct_rda'] == 100
    assert row['reference_population'] == 'Pregnancy'


def test_receipt_reconciliation_checks_recorded_contributions():
    from scoring_v4.pillar_explanations import _dose_receipt
    pillar = {'score': 20, 'max': 20, 'components': {'reference': 20, 'adequacy_before_safety': 20}}
    receipt = _dose_receipt(pillar, {'score':20, 'metadata': {'dose_contributions': [
        {'ingredient': 'x', 'assessment': 'panel_component', 'credit_raw': 5}]}}, 'generic')
    assert receipt['reconciles'] is False


def test_receipt_records_existing_unassessed_primary_constraint():
    from scoring_v4.pillar_explanations import _dose_receipt, _dose_receipt_facts
    pillar = {'score': 11.4, 'max': 20, 'components': {'reference': 22, 'adequacy_before_safety': 11.4}}
    metadata = {'dose_participation_basis': 'assessed_nutrient_average',
                'primary_active_unassessed': 'l_leucine', 'partial_credit_value': 12.54,
                'window_proxy_status': 'partial_credit_primary_active_unassessed',
                'dose_contributions': [{'ingredient': 'Vitamin D', 'assessment': 'dri_reference', 'credit_raw': 22}]}
    receipt = _dose_receipt(pillar, {'score':12.54, 'metadata': metadata}, 'generic')
    assert receipt['reconciles'] is True
    # Audit text names the active in words, never by canonical ID.
    assert any('l leucine' in row['value_display'] and '11.4' in row['value_display']
               for row in _dose_receipt_facts(receipt))
    assert not any('l_leucine' in row['value_display'] for row in _dose_receipt_facts(receipt))


def test_undosed_blend_with_unfinished_benchmark_is_not_presented_as_a_clinical_dose():
    """A disclosed total proves neither member dose nor completed benchmark review."""
    import copy
    from scoring_v4.modules.generic_evidence import score_evidence
    from scoring_v4.scored_artifact import build_scored_artifact

    import json
    from pathlib import Path
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    raw = json.loads((Path(__file__).parent / "fixtures" / "evidence_subject_212273_raw.json").read_text())
    product, _ = SupplementEnricherV3().enrich_product(
        EnhancedDSLDNormalizer().normalize_product(raw))
    artifact = build_scored_artifact(copy.deepcopy(product))
    dose = artifact["quality_pillars_v4"]["dose"]
    [item] = dose["explanation"]["dose_receipt"]["contributions"]
    assert item["assessment"] == "botanical_profile"
    assert item["reference_kind"] == "pharmaguide_policy"
    assert "individual amounts unknown" in item["reference"]
    # Identity recognition no longer completes the scientific benchmark review.
    # This real blend has an unresolved review, so zero cannot imply neutral credit.
    metadata = artifact["_v4_module_breakdown"]["dimensions"]["dose"]["metadata"]
    assert metadata["botanical_dose"]["benchmark"] == "unresolved"
    assert dose["score"] == 0
    assert dose["receipt"]["entries"] == []
    assert "amount_at_minimum" not in item
    assert "reference_value" not in item
    assert dose["explanation"]["dose_receipt"]["reference_assessments"] == []
    assert score_evidence(copy.deepcopy(product), apply_primary_floor=True,
                          owner_scoped=True)["metadata"]["primary_evidence_floor"] == 0


@pytest.mark.parametrize('assessment,credit,expected', [
    ('botanical_profile', 0.0, 'applicable dose benchmark review is incomplete'),
    ('no_benchmark_neutral', 12.54, 'no applicable general benchmark: neutral value'),
])
def test_botanical_receipt_preserves_unfinished_vs_completed_benchmark_review(assessment, credit, expected):
    from scoring_v4.pillar_explanations import _dose_receipt, _dose_receipt_facts

    # Both owner outcomes share the amount band. Only the completed review is
    # recorded as no_benchmark_neutral by generic_dose.
    pillar = {'score': credit, 'max': 22,
              'components': {'reference': 22, 'adequacy_before_safety': credit}}
    dose = {'score': credit, 'metadata': {
        'dose_participation_basis': 'single_profile_assessment',
        'dose_contributions': [{'ingredient': 'botanical', 'assessment': assessment,
                               'band': 'disclosed_no_reference', 'credit_raw': credit}]}}
    original = deepcopy(dose)
    receipt = _dose_receipt(pillar, dose, 'generic')
    assert receipt['contributions'][0]['reference'] == expected
    fact = next(row for row in _dose_receipt_facts(receipt) if row['id'] == 'dose_contributions')
    assert expected in fact['value_display']
    assert receipt['final'] == credit
    assert receipt['contributions'][0]['points'] == credit
    assert receipt['reconciles'] is True
    assert dose == original
