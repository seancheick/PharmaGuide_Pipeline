"""The source-qualified American root capsule keeps its existing biological owner."""
import json
from copy import deepcopy
from pathlib import Path
import pytest

@pytest.fixture(scope='module')
def pipeline():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    n,e=EnhancedDSLDNormalizer(),SupplementEnricherV3()
    return lambda raw: (lambda c:(c,e.enrich_product(c)[0]))(n.normalize_product(raw))

def raw_label():
    return json.loads((Path(__file__).parent/'fixtures/raw_american_capsule_251494.json').read_text())

def test_original_american_root_capsule_uses_existing_owner(pipeline):
    from scoring_input_contract import _route_scoring_rows
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    clean,product=pipeline(raw_label())
    row=next(r for r in _route_scoring_rows(product) if r.get('raw_source_path')=='ingredientRows[0]')
    assert clean['activeIngredients'][0]['canonical_id']=='american_ginseng'
    assert row['canonical_id']=='american_ginseng'
    assert row['quantity']==1.1 and row['unit']=='Gram(s)'
    assert _botanical_benchmark(row,product=product)=='absent'

@pytest.mark.parametrize('change',['missing_root','extract','gummy'])
def test_capsule_scope_cannot_supply_missing_or_different_material(pipeline,change):
    from scoring_input_contract import _route_scoring_rows
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    raw=raw_label();raw['id']=991180
    source=raw['ingredientRows'][0]
    source['notes']='American Ginseng PlantPart: root'
    if change=='missing_root': source['notes']='American Ginseng'
    elif change=='extract':
        source['name']='American Ginseng Extract'
    else:
        raw['physicalState']={'langualCode':'A0126','langualCodeDescription':'Gummy'}
    _,product=pipeline(raw)
    row=next(r for r in _route_scoring_rows(product) if r.get('raw_source_path')=='ingredientRows[0]')
    assert _botanical_benchmark(row,product=product)=='unresolved'


def powder_label():
    return json.loads((Path(__file__).parent/'fixtures/raw_american_capsule_216622.json').read_text())


def test_original_whole_root_powder_capsule_remains_separate_from_extract(pipeline):
    from scoring_input_contract import _route_scoring_rows
    from scoring_v4.modules.botanical_profile import score_botanical_purpose_dose
    clean,product=pipeline(powder_label())
    rows={r.get('raw_source_path'):r for r in _route_scoring_rows(product)}
    powder,extract=rows['ingredientRows[2]'],rows['ingredientRows[1]']
    assert powder['canonical_id']=='american_ginseng'
    original=next(r for r in clean['activeIngredients'] if r['raw_source_path']=='ingredientRows[2]')
    assert original['plantPart']=='whole root'
    assert original['quantity']==200 and original['unit']=='mg'
    assert original['forms']==[]
    assert extract['quantity']==100 and extract['unit']=='mg'
    assert score_botanical_purpose_dose(product,powder)['metadata']['benchmark']=='absent'
    assert score_botanical_purpose_dose(product,extract)['metadata']['benchmark']=='absent'


@pytest.mark.parametrize('change',['missing_part','extract','gummy'])
def test_whole_root_capsule_reference_requires_same_original_material(pipeline,change):
    from scoring_input_contract import _route_scoring_rows
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    _,product=pipeline(powder_label())
    rows=_route_scoring_rows(product)
    row=next(r for r in rows if r.get('raw_source_path')=='ingredientRows[2]')
    from dose_assessment import _source_dose_row
    source=_source_dose_row(product,row)
    if change=='missing_part':
        source['notes']='';source['plantPart']=None
    elif change=='extract': source['raw_source_text']=source['name']='American Ginseng Extract'
    else: product['physicalState']={'langualCodeDescription':'Gummy'}
    assert _botanical_benchmark(row,product=product)=='unresolved'
