"""Source-bound botanical correction regressions; identity is not efficacy."""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / 'data'

def records(name):
    return {r['id']: r for r in json.loads((DATA / (name + '.json')).read_text())[name]}

WRONG_ALIASES = {
    'aloe_vera_concentrated_gel': ['cape aloe extract', 'Cape Aloe leaf latex extract'],
    'apricot': ['apricot seed extract'], 'barberry_root': ['berberis aristata root'],
    'blue_vervain': ['European Vervain'], 'cassia_nomame': ['cassia nomame seed extract'],
    'catuaba': ['erythroxylum catuaba'],
    'cinnamon': ['cinnamomum verum', 'ceylon cinnamon', 'cinnamomum cassia'],
    'cinnamon_bark': ['cinnamomum verum bark', 'true cinnamon'],
    'cistanche': ['cistanche deserticola'],
    'cordyceps_mushroom_powder': ['cordyceps sinensis powder'],
    'fruits': ['apple', 'Pineapple', 'papaya', 'Papaya juice powder'],
    'inulin': ['fructooligosaccharides', 'FOS'], 'kelp_powder': ['laminaria'],
    'linden_flower': ['tilia platyphyllos'], 'lemongrass': ['cymbopogon flexuosus'],
    'prickly_ash': ['zanthoxylum clava-herculis'],
    'sarsaparilla': ['smilax officinalis'],
    'wild_blueberry': ['vaccinium myrtillus', 'wild bilberry'],
    'sphaeranthus_indicus': ['Holimel', 'Meratrim'],
}

def test_species_part_and_polymer_aliases_do_not_collapse():
    rows = records('botanical_ingredients')
    for key, aliases in WRONG_ALIASES.items():
        found = {a.casefold() for a in rows[key]['aliases']}
        assert not found.intersection(a.casefold() for a in aliases), key

def test_wrong_topic_botanical_sources_do_not_assert_clinical_evidence():
    rows = records('botanical_ingredients')
    for key in ['african_geranium', 'beet_root', 'boswellia_serrata_resin',
                'citrus_bergamot', 'coleus_forskohlii_root', 'cranberry',
                'devils_claw_tuber', 'fenugreek_seed', 'feverfew', 'guava',
                'gymnema_sylvestre', 'lemon_balm_leaf', 'maitake',
                'milk_thistle_seed', 'nigella', 'pomegranate', 'rhodiola_rosea_root']:
        assert 'RCT evidence' not in rows[key]['notes'], key

def test_manufacturer_percent_is_not_a_dose_or_pure_compound():
    rows = records('standardized_botanicals')
    assert rows['cranrx']['standardization_unit'] == 'mg_per_dose'
    assert rows['morosil']['min_threshold'] == 0.8
    assert '0.8–0.9%' in rows['morosil']['notes']
    assert 'total proanthocyanidins' in rows['enovita']['notes']
    assert 'OPCs' not in rows['enovita']['notes']
    assert 'Delphinol standard' not in rows['maqui_berry']['threshold_source']
    assert 'artemisinin' not in rows['wormwood']['markers']
    assert 'calendula officinalis' not in rows['marigold']['aliases']

def test_unverified_branded_rows_keep_identity_without_bonus_certainty():
    rows = records('standardized_botanicals')
    for key in ['astazine', 'bil_max', 'blue_max', 'cran_max', 'thermosil',
                'uniflex', 'turmipure_gold', 'sharp_ps_green']:
        assert rows[key]['bonus_eligible'] is False, key
        assert rows[key]['data_quality'] == 'requires_verification', key
        assert rows[key]['aliases'], key

import pytest
from enrich_supplements_v3 import SupplementEnricherV3
from scoring_v4.modules import botanical_profile as bp
from scoring_v4.modules import generic_formulation as gf

@pytest.fixture(scope='module')
def collector():
    return SupplementEnricherV3()

@pytest.mark.parametrize('hold', [
    {'bonus_eligible': False}, {'data_quality': 'requires_verification'},
])
def test_existing_standardization_holds_block_both_tier_consumers(collector, monkeypatch, hold):
    entry={'id':'source_hold','standard_name':'Source Hold', 'aliases':['Source Hold'],
           'branded_form':True, 'markers':['anthocyanins'], 'min_threshold':20, **hold}
    monkeypatch.setitem(collector.databases, 'standardized_botanicals', {'standardized_botanicals':[entry]})
    row={'name':'Source Hold', 'notes':'standardized to 95% anthocyanins', 'quantity':100, 'unit':'mg'}
    found=collector._collect_standardized_botanicals({'activeIngredients':[row]})
    product={'formulation_data':{'standardized_botanicals':found},
             'has_standardized_botanical':any(r['meets_threshold'] for r in found)}
    assert gf._score_a5b_standardized_botanical(product)==0
    assert bp._standardization_tier_credit(product,row)==0


def test_duplicate_standardized_entry_does_not_erase_explicit_hold(collector, monkeypatch):
    valid={'id':'source_hold','standard_name':'Source Hold','aliases':['Source Hold'],
           'branded_form':True,'markers':['anthocyanins'],'min_threshold':20,'bonus_eligible':True}
    held={**valid,'bonus_eligible':False}
    monkeypatch.setitem(collector.databases,'standardized_botanicals',{'standardized_botanicals':[valid,held]})
    assert collector._collect_standardized_botanicals({'activeIngredients':[{'name':'Source Hold'}]})==[]


def test_valid_standardization_control_retains_credit(collector,monkeypatch):
    valid={'id':'valid_control','standard_name':'Valid Control','aliases':['Valid Control'],
           'markers':['anthocyanins'],'min_threshold':20,'bonus_eligible':True}
    monkeypatch.setitem(collector.databases,'standardized_botanicals',{'standardized_botanicals':[valid]})
    row={'name':'Valid Control','notes':'standardized to 25% anthocyanins'}
    found=collector._collect_standardized_botanicals({'activeIngredients':[row]})
    assert found[0]['meets_threshold'] is True
    assert bp._standardization_tier_credit({'formulation_data':{'standardized_botanicals':found}},row)>0

@pytest.mark.parametrize('source_hold', [
    {'scoring_eligible':False}, {'study_type':'reference','evidence_level':'reference'},
    {'references_structured':[{'pmid':'41573009','retracted':True}]},
])
def test_held_clinical_match_cannot_provide_branded_standardization(source_hold):
    match={'id':'BRAND_SOURCE_HOLD','evidence_level':'branded_rct',
           'matched_source_row_refs':['ingredientRows[0]'],**source_hold}
    product={'evidence_data':{'clinical_matches':[match]}}
    row={'name':'Source Hold','raw_source_path':'ingredientRows[0]'}
    assert bp._branded_studied_row(product,row) is False
    assert bp._standardization_tier_credit(product,row)==0


def test_valid_clinical_match_retains_independent_branded_credit():
    match={'id':'BRAND_VALID','evidence_level':'branded_rct',
           'matched_source_row_refs':['ingredientRows[0]'],'references_structured':[{'pmid':'28661438'}]}
    row={'name':'Valid','raw_source_path':'ingredientRows[0]'}
    assert bp._branded_studied_row({'evidence_data':{'clinical_matches':[match]}},row)


def test_projection_brand_index_obeys_existing_source_integrity(tmp_path,monkeypatch):
    original=bp._DATA_DIR
    data={'backed_clinical_studies':[
        {'id':'BRAND_HELD','standard_name':'Held Brand','aliases':['Held Brand'],
         'evidence_level':'branded_rct','scoring_eligible':False},
        {'id':'BRAND_VALID','standard_name':'Valid Brand','aliases':['Valid Brand'],
         'evidence_level':'branded_rct','references_structured':[{'pmid':'28661438'}]},
    ]}
    (tmp_path/'backed_clinical_studies.json').write_text(json.dumps(data))
    monkeypatch.setattr(bp,'_DATA_DIR',tmp_path)
    bp._branded_studied_entries.cache_clear()
    try:
        keys={name for names,_tokens in bp._branded_studied_entries() for name in names}
        assert 'held brand' not in keys
        assert 'valid brand' in keys
    finally:
        monkeypatch.setattr(bp,'_DATA_DIR',original)
        bp._branded_studied_entries.cache_clear()


def test_wrong_analyte_or_preparation_cannot_reuse_a_numeric_threshold():
    rows=records('standardized_botanicals')
    for key in ['ginkgolides','eucalyptus']:
        assert rows[key]['min_threshold'] is None,key
        assert rows[key]['bonus_eligible'] is False,key
    assert rows['green_tea']['markers']==['polyphenols']
    assert 'BDNF' not in rows['neurofactor']['markers']
    assert 'blackcurrant seed oil' not in rows['black_currant']['aliases']
    assert rows['cognigrape']['external_ids'].get('unii') is None
    assert records('botanical_ingredients')['graviola']['external_ids'].get('unii') is None


def test_native_enrichment_preserves_parent_hold_before_branded_credit(collector):
    native = next(
        row for row in collector.databases['backed_clinical_studies']['backed_clinical_studies']
        if row['id'] == 'BRAND_LIFE_EXTENSION_SUPER_BIOCURCUMIN'
    )
    assert native['scoring_eligible'] is False
    row = {
        'name': native['standard_name'], 'standardName': native['standard_name'],
        'quantity': 400, 'unit': 'mg', 'raw_source_path': 'ingredientRows[0]',
    }
    product = {'activeIngredients': [row], 'productName': 'Life Extension Super Bio-Curcumin (BCM-95)'}
    evidence = collector._collect_evidence_data(product)
    held = next(match for match in evidence['clinical_matches'] if match['id'] == native['id'])
    assert held.get('scoring_eligible') is False
    # Other independently valid matches retain their own eligibility. This
    # assertion isolates the collected held source rather than borrowing them.
    product['evidence_data'] = {'clinical_matches': [held]}
    assert bp._branded_studied_row(product, row) is False
    assert bp._standardization_tier_credit(product, row) == 0
