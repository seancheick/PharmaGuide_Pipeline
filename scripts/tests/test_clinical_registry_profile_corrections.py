"""Source-grounded medication classification and profile-copy corrections."""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / 'data'

def load(name):
    return json.loads((DATA / name).read_text())

def test_non_nsaids_do_not_inherit_prostaglandin_hazards():
    nsaids = load('drug_classes.json')['classes']['class:nsaids']
    assert not {'4845', '2473'} & set(nsaids['member_rxcuis'])
    assert not {'glucosamine', 'chondroitin sulfates'} & set(nsaids['member_names'])
    assert {'5640', '7258', '3355'} <= set(nsaids['member_rxcuis'])

def test_mechanism_classification_preserves_independent_medication_hazards():
    classes = load('drug_classes.json')['classes']
    assert '6448' not in classes['class:antipsychotics']['member_rxcuis']
    assert '6448' in classes['class:antipsychotics'].get('excluded_member_rxcuis', [])
    assert '9639' in classes['class:maois']['member_rxcuis']
    assert '6703' not in classes['class:oral_contraceptives']['member_rxcuis']
    assert '6703' in classes['class:oral_contraceptives'].get('excluded_member_rxcuis', [])
    assert '14584' in classes['class:oral_contraceptives']['member_rxcuis']
    assert 'temazepam' in classes['class:sedatives']['member_names']
    assert 'Non-benzodiazepine' not in classes['class:sedatives']['description']

def test_lithium_identity_preserves_its_existing_specific_profile_warnings():
    classes = load('drug_classes.json')['classes']
    lithium = classes.get('class:lithium')
    assert lithium is not None, 'added lithium must reach the existing lithium profile vocabulary'
    assert list(zip(lithium['member_rxcuis'], lithium['member_names'])) == [('6448', 'lithium')]
    assert lithium['rxclass_id'] == 'N05AN'
    assert '6448' not in classes['class:antipsychotics']['member_rxcuis']
    assert '5640' not in lithium['member_rxcuis']

def test_pregnancy_copy_preserves_prescribed_low_dose_aspirin_exception():
    rules = {r['id']: r for r in load('medication_profile_gate_rules.json')['medication_profile_gate_rules']}
    pregnancy = rules['MCR_PREGNANCY_NSAIDS']
    assert '81 mg' in pregnancy['body']
    assert 'eye' in pregnancy['body'].lower()
    assert 'prescribed' in pregnancy['management'].lower()
    kidney = rules['MCR_KIDNEY_DISEASE_NSAIDS']
    assert 'systemic' in kidney['headline'].lower()
    assert 'topical diclofenac' in kidney['body'].lower()
