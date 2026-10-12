"""Exact source/identity corrections; null chemistry does not imply safe use."""
import json
from pathlib import Path
import pytest
from inactive_ingredient_resolver import InactiveIngredientResolver
from enrich_supplements_v3 import SupplementEnricherV3
from build_final_db import build_structured_allergens
from enhanced_normalizer import EnhancedDSLDNormalizer

DATA=Path(__file__).resolve().parents[1]/'data'

def test_hpmcp_exact_derivative_beats_plain_hypromellose_group():
    normalizer = EnhancedDSLDNormalizer()
    name = 'Hydroxypropyl Methylcellulose Phthalate'
    standard, mapped, _ = normalizer._map_inactive_name_prefer_other(
        name, ingredient_group='Hypromellose')
    assert mapped is True
    assert standard == 'Hypromellose Phthalate'
    owner = InactiveIngredientResolver()
    result = owner.resolve(name)
    assert result.matched_rule_id == 'NHA_HYPROMELLOSE_PHTHALATE'
    assert result.identifiers.get('external_ids', {}).get('pubchem_cid') is None
    assert not result.is_banned
    assert owner.resolve('Hydroxypropyl Methylcellulose').matched_rule_id == 'PII_HPMC'
    assert owner.resolve('Diethyl Phthalate').matched_rule_id == 'BANNED_ADD_PHTHALATES'

def rows(name):
    return {r['id']:r for r in json.loads((DATA/(name+'.json')).read_text())[name]}

BAD_IDS={
 'NHA_CALCIUM_CASEINATE':('pubchem_cid',161712915),
 'PII_DIASTASE':('pubchem_cid',71475145),
 'NHA_HYPROMELLOSE_PHTHALATE':('pubchem_cid',57469),
 'PII_PALM_SOURCE_DESCRIPTOR':('pubchem_cid',2723),
 'OI_POLACRILLIN_POTASSIUM':('unii','RWP5GA015D'),
 'PII_XYLANASE':('pubchem_cid',171706620),
 'NHA_RESOLVIN_D5':('pubchem_cid',24932575),
 'NHA_PROTECTIN_DX':('pubchem_cid',11968800),
 'PII_SPECTRA_BRANDED_BLEND':('pubchem_cid',38078),
 'PII_TESTOSTERONE_SUPPORT_MARKETING_DESCRIPTOR':('unii','3XMK78S47O'),
 'NHA_FOS':('pubchem_cid',439709),
 'PII_MUCIN':('pubchem_cid',3037582),
 'NHA_XYLO_OLIGOSACCHARIDE':('pubchem_cid',6912),
}

@pytest.mark.parametrize('key,field,bad',[(k,*v) for k,v in BAD_IDS.items()])
def test_actual_inactive_owner_does_not_export_wrong_chemical(key,field,bad):
    source=rows('other_ingredients')[key]
    assert source['external_ids'].get(field)!=bad,key
    owner=InactiveIngredientResolver()
    result=owner.resolve(source['standard_name'])
    assert result.identifiers.get('external_ids',{}).get(field)!=bad,key
    assert not result.is_banned


def test_known_form_scope_keeps_valid_counterparts():
    r=rows('other_ingredients')
    assert r['PII_BETAINE_MONOHYDRATE']['external_ids'].get('unii') is None
    assert r['PII_BETAINE_MONOHYDRATE']['external_ids']['pubchem_cid']==24884197
    assert r['NHA_CALCIUM_CHLORIDE']['external_ids'].get('unii') is None
    assert r['NHA_CALCIUM_CHLORIDE']['external_ids']['pubchem_cid']==5284359
    assert 'piperine' not in r['NHA_BLACK_PEPPER_EXTRACT']['aliases']
    assert 'cranberry seed oil' not in r['NHA_CRANBERRY_FIBER']['aliases']
    assert 'hydroxypropyl methylcellulose phthalate' not in r['PII_HPMC']['aliases']


def test_source_copy_qualifies_actual_population_design_and_outcomes():
    r=rows('other_ingredients')
    assert 'supports gut microbiome diversity' not in r['NHA_AGAVE_FIBER']['notes']
    assert 'no significant' in r['NHA_AGAVE_FIBER']['notes']
    assert 'Does not affect blood sugar' not in r['NHA_ALLULOSE']['notes']
    assert 'type 2 diabetes' in r['NHA_ALLULOSE']['notes']
    assert 'monotherapy' in r['NHA_SARCOSINE']['notes']
    assert 'no significant' in r['NHA_SARCOSINE']['notes']
    assert 'cognitive enhancement' not in r['NHA_SARCOSINE']['notes']

@pytest.fixture(scope='module')
def enrichment_owner():
    return SupplementEnricherV3()

@pytest.mark.parametrize('name,expected',[
 ('goat milk','ALLERGEN_MILK'),('sheep milk','ALLERGEN_MILK'),
 ('duck egg','ALLERGEN_EGGS'),('goose egg','ALLERGEN_EGGS'),('quail egg','ALLERGEN_EGGS'),
 ('milk','ALLERGEN_MILK'),('egg','ALLERGEN_EGGS'),
])
def test_species_expanded_allergen_reaches_existing_export(enrichment_owner,name,expected):
    result=enrichment_owner._check_allergens([{'name':name,'standardName':name}],{})
    export=build_structured_allergens({'allergen_hits':result['allergens']})
    assert any(r['allergen_id']==expected for r in export),name


def test_labeling_exceptions_do_not_erase_unknown_allergy_risk():
    r=rows('allergens')
    assert 'exempt' in r['ALLERGEN_SOY']['notes']
    assert 'must still be labeled' not in r['ALLERGEN_SOY']['notes']
    assert 'Shea nut (Vitellaria paradoxa) is FDA-classified as tree nut' not in r['ALLERGEN_TREE_NUTS']['notes']
    assert 'not FDA major' in r['ALLERGEN_TREE_NUTS']['notes']
    # FDA labeling exemption alone is not evidence that an allergic patient is safe.
    assert 'chestnut' in r['ALLERGEN_TREE_NUTS']['aliases']
    assert 'shea nut' in r['ALLERGEN_TREE_NUTS']['aliases']


def test_known_hydrate_and_metal_aliases_do_not_assign_other_forms():
    r=rows('other_ingredients')
    assert "glauber's salt" not in r['NHA_SODIUM_SULFATE']['aliases']
    assert 'sodium copper chlorophyllin' not in r['NHA_CHLOROPHYLLIN']['aliases']
    assert 'E141' not in r['NHA_CHLOROPHYLLIN']['aliases']
    assert 'Also known as Glauber' not in r['NHA_SODIUM_SULFATE']['notes']
