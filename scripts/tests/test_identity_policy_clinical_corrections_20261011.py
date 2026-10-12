import json
from pathlib import Path
import pytest
from enrich_supplements_v3 import SupplementEnricherV3

DATA=Path(__file__).resolve().parents[1]/'data'

@pytest.mark.parametrize('name',['igf-1 lr3','lr3-igf-1','lr3 igf 1','long r3 igf-1'])
def test_lr3_veto_and_specific_owner_agree(name):
    e=SupplementEnricherV3.__new__(SupplementEnricherV3)
    for key in ['_regex_pattern_cache','_hyphen_space_pattern_cache','_token_bounded_pattern_cache']:
        setattr(e,key,{})
    db=json.loads((DATA/'banned_match_allowlist.json').read_text())
    positive=[r for r in db['allowlist'] if r['id']=='ALLOW_IGF1_LR3']
    veto=[r for r in db['denylist'] if r['id']=='DENY_IGF1_LR3']
    assert e._allowlist_match(name,positive)
    assert e._denylist_match(name,veto)
    assert not e._denylist_match('IGF-1',veto)

def test_nitrite_nitrate_umbrella_does_not_take_one_compound_identifier():
    row=json.loads((DATA/'curated_overrides'/'cui_overrides.json').read_text())['sodium nitrite/nitrate']
    assert row['cui'] is None
    assert row['name'] is None
    assert 'nitrate' in row['note'].lower()
