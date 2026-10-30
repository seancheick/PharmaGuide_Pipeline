"""Horsetail whole extract is not the isolated silica standardization marker."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

IDS=['294422','294424','312021','312023','331010']

@pytest.fixture(scope='module')
def pipeline():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    n,e=EnhancedDSLDNormalizer(),SupplementEnricherV3()
    def run(raw):
        clean=n.normalize_product(raw)
        return clean,e.enrich_product(clean)[0]
    run.normalizer=n
    return run


def raw_label(pid):
    return json.loads((Path(__file__).parent/'fixtures'/f'raw_horsetail_{pid}.json').read_text())


@pytest.mark.parametrize('pid',IDS)
def test_whole_horsetail_amount_keeps_its_biological_identity(pipeline,pid):
    from scoring_input_contract import _route_scoring_rows
    from scoring_v4.modules.botanical_profile import score_botanical_purpose_dose
    raw=raw_label(pid)
    clean,product=pipeline(raw)
    assert len(clean['activeIngredients'])==1
    active=clean['activeIngredients'][0]
    assert active['canonical_id']=='horsetail'
    assert active['quantity']==raw['ingredientRows'][0]['quantity'][0]['quantity']
    assert active['raw_source_text']=='Horsetail Whole Herb Extract'
    assert '>=7%' in active['notes']
    assert active['forms'][0]['percent'] is None  # preserve API unknown, not exact7 arithmetic
    row=next(r for r in _route_scoring_rows(product) if r.get('raw_source_path')=='ingredientRows[0]')
    assert row['canonical_id']=='horsetail'
    assert score_botanical_purpose_dose(product,row)['metadata']['benchmark']=='absent'


@pytest.mark.parametrize('species',['Equisetum palustre','Equisetum hyemale',''])
def test_other_or_missing_species_cannot_borrow_arvense_reference(pipeline,species):
    from scoring_input_contract import _route_scoring_rows
    from scoring_v4.modules.botanical_profile import score_botanical_purpose_dose
    raw=raw_label('294422');raw['id']=991107
    raw['ingredientRows'][0]['notes']=f'Horsetail Extract ({species}) PlantPart: whole herb Note: standardized to contain >=7% Silica'
    _,product=pipeline(raw)
    row=next(r for r in _route_scoring_rows(product) if r.get('raw_source_path')=='ingredientRows[0]')
    assert row['canonical_id']=='horsetail'
    assert score_botanical_purpose_dose(product,row)['metadata']['benchmark']=='unresolved'


def test_top_level_silica_identifier_retains_priority(pipeline):
    raw=raw_label('294422')['ingredientRows'][0]
    raw['uniiCode']='ETJ7Z6XBU4'
    payload,method=pipeline.normalizer._try_unii_match(raw)
    assert method=='unii_exact_match'
    assert payload['canonical_id']=='silica'


def test_isolated_and_mixed_silica_are_not_horsetail(pipeline):
    from scoring_input_contract import _route_scoring_rows
    for name in ['Silica','Mixed Silica Complex']:
        raw=raw_label('294422');raw['id']=991108
        row=raw['ingredientRows'][0];row.update(name=name,category='mineral',ingredientGroup='Silicon',notes='')
        _,product=pipeline(raw)
        assert all(r.get('canonical_id')!='horsetail' for r in _route_scoring_rows(product))
