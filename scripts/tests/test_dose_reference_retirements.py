"""Reviewed regimens remain evidence without becoming general Dose curves."""
import json
from pathlib import Path

import pytest

from scoring_v4.scored_artifact import build_scored_artifact
from test_v4_botanical_profile import _botanical_ingredient, _botanical_product
from test_v4_sports_dose_p171 import _product, _row
from test_v4_omega_dose_p162 import _omega_product
from test_probiotic_label_dose_independence import owned_label

DATA = Path(__file__).resolve().parents[1] / 'data'


@pytest.mark.parametrize('name,key', [
    ('rda_optimal_uls', 'nutrient_recommendations'),
    ('rda_therapeutic_dosing', 'therapeutic_dosing'),
])
def test_each_existing_dose_reference_records_its_reviewed_meaning(name, key):
    records = json.loads((DATA / (name + '.json')).read_text())[key]
    for record in records:
        semantics = record.get('reference_semantics') or {}
        assert semantics.get('reference_type'), record['id']
        assert semantics.get('approval_status'), record['id']
        assert semantics.get('owner'), record['id']


@pytest.mark.parametrize('amount', [1, 250, 600, 5000])
def test_exact_ksm66_regimens_do_not_define_a_numerical_dose_window(amount):
    product = _botanical_product(_botanical_ingredient(quantity=amount))
    dose = build_scored_artifact(product)['quality_pillars_v4']['dose']
    assert dose['score'] == 11.4


@pytest.mark.parametrize('identity,amount', [
    ('melatonin', .1), ('melatonin', 1), ('melatonin', 20),
    ('5_htp', 50), ('5_htp', 400),
    ('glucosamine', 1500), ('msm', 3000), ('chondroitin', 1200),
])
def test_discrete_sleep_and_joint_regimens_receive_completed_neutral(identity, amount):
    category = 'sleep_support' if identity in {'melatonin', '5_htp'} else 'joint_support'
    product = _product(_row(identity, amount, 'mg'), name=identity, primary_type=category)
    assert build_scored_artifact(product)['quality_pillars_v4']['dose']['score'] == 11.4


@pytest.mark.parametrize('amount', [100, 1000, 10000, 20000])
def test_collagen_discrete_regimens_do_not_define_a_continuous_window(amount):
    row = _row('collagen', amount, 'mg')
    row.update(name='Hydrolyzed Collagen Peptides', collagen_subtype='hydrolyzed_peptides')
    product = _product(row, name='Hydrolyzed Collagen Peptides', primary_type='collagen')
    assert build_scored_artifact(product)['quality_pillars_v4']['dose']['score'] == 11.4


@pytest.mark.parametrize('guarantee', ['at_expiration', 'at_manufacture', 'unknown'])
@pytest.mark.parametrize('count', [1e8, 1e9, 1e10, 5e10])
def test_strain_counts_and_guarantee_never_recreate_clinical_dose_tiers(count, guarantee):
    from scoring_v4.modules.probiotic_dose import score_dose
    product = owned_label()
    product['probiotic_data']['guarantee_type'] = guarantee
    product['probiotic_data']['probiotic_blends'][0]['cfu_data']['cfu_count'] = count
    assert score_dose(product)['score'] == 8.55  # existing /15 normalization ->11.4/20
    assert score_dose(product)['metadata']['cfu_guarantee']['applied'] is False


@pytest.mark.parametrize('amount', [50, 250, 2000])
def test_child_omega_does_not_borrow_adult_numerical_bands(amount):
    product = _omega_product(epa=amount / 2, dha=amount / 2)
    product.update(product_name="Children's Omega", target_population=['children'])
    from scoring_v4.modules.omega_dose import score_dose
    assert score_dose(product)['score'] == 11.4


def test_retired_positive_clinical_records_cannot_supply_minima():
    from dose_assessment import _positive_clinical_benchmark_records
    assert not _positive_clinical_benchmark_records()


@pytest.mark.parametrize('identity,category', [
    ('melatonin', 'sleep_support'), ('glucosamine', 'joint_support'),
    ('collagen', 'collagen'),
])
def test_missing_captured_amount_never_becomes_completed_neutral(identity, category):
    row = _row(identity, 100, 'mg')
    row['quantity'] = None
    product = _product(row, name=identity, primary_type=category)
    artifact = build_scored_artifact(product)
    assert artifact['quality_pillars_v4']['dose']['score'] != 11.4
    assert artifact['quality_score_status'] == 'not_scored' or artifact['quality_assessment_status'] == 'partial'


def test_botanical_preparation_review_pending_stays_incomplete(monkeypatch):
    from scoring_v4.modules import botanical_profile
    row = _botanical_ingredient(quantity=300)
    monkeypatch.setattr(botanical_profile, '_dosing_entry_for', lambda row, **kwargs: {
        'id': 'ashwagandha_root_extract', 'reference_semantics': {'reference_type': 'unfinished_review'}})
    result = botanical_profile.score_botanical_purpose_dose(_botanical_product(row), row)
    assert result['metadata']['benchmark'] == 'unresolved'
    assert result['score'] == 0
