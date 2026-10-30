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
