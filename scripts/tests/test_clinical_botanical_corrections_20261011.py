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
    assert bp._resolved_preparation_row(product,row) is False
    assert bp._standardization_tier_credit(product,row)==0


def test_valid_clinical_match_alone_does_not_establish_a_material_spec():
    match={'id':'BRAND_VALID','evidence_level':'branded_rct',
           'matched_source_row_refs':['ingredientRows[0]'],'references_structured':[{'pmid':'28661438'}]}
    row={'name':'Valid','raw_source_path':'ingredientRows[0]'}
    product = {'evidence_data': {'clinical_matches': [match]}}
    assert not bp._resolved_preparation_row(product, row)
    assert bp._standardization_tier_credit(product, row) == 0


@pytest.mark.parametrize('eligible', [False, True])
def test_physical_preparation_identity_is_not_marker_or_clinical_eligibility(eligible):
    row = {'name': 'Sytrinol', 'canonical_id': 'sytrinol',
           'matched_form': 'specific preparation', 'mapped': True, 'form_match_status': 'mapped'}
    product = {'evidence_data': {'clinical_matches': [{'id': 'BRAND_CONTROL', 'scoring_eligible': eligible}]}}
    assert bp._resolved_preparation_row(product, row)
    assert bp._standardization_tier_credit(product, row) == 0
    # Parent preparation identity serves Dose independently of marker credit.
    assert bp._is_named_botanical_preparation(product, {**row, 'is_parent_total': True})


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
    assert not any(match['id'] == native['id'] for match in evidence['clinical_matches'])
    assert any(match['id'] == native['id'] for match in evidence['rejected_clinical_matches'])
    # Clinical rejection itself supplies neither physical identity nor markers.
    product['evidence_data'] = evidence
    assert bp._resolved_preparation_row(product, row) is False
    assert bp._standardization_tier_credit(product, row) == 0


# Sean's material/benefit separation ruling, October 28, 2026.
def test_real_testofen_material_spec_keeps_clinical_hold_and_earns_only_formulation(collector):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from scoring_v4.scored_artifact import build_scored_artifact
    raw = json.loads((Path(__file__).parent / 'fixtures/material_standardization_304641_raw.json').read_text())
    enriched, errors = collector.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    assert not errors
    material = next(x for x in enriched['formulation_data']['standardized_botanicals'] if x['name'] == 'Testofen')
    assert material['evidence_source'] == 'branded_form'
    assert material['percentage_found'] == 0 and material['percentage_source'] is None
    assert material['meets_threshold'] is True
    artifact = build_scored_artifact(enriched)
    formulation = bp.score_botanical_formulation(enriched)
    assert formulation['components']['marker_standardization_declared'] == bp.STANDARDIZATION_TIER_FULL
    entries = artifact['quality_pillars_v4']['formulation']['receipt']['entries']
    assert len([entry for entry in entries if entry['id'] == 'marker_standardization_declared']) == 1
    # Neither the held material study nor unqualified generic fenugreek can earn benefit credit.
    assert not {'BRAND_TESTOFEN', 'INGR_FENUGREEK'} & {
        m['id'] for m in enriched['evidence_data']['clinical_matches']}
    assert artifact['quality_pillars_v4']['evidence']['score'] == 0.0


@pytest.mark.parametrize('clinical_state', ['approved', 'held', 'null', 'retracted'])
def test_verified_material_credit_is_independent_of_clinical_state(collector, clinical_state):
    row = {'name': 'Testofen', 'standard_name': 'Fenugreek', 'canonical_id': 'fenugreek',
           'matched_form': 'testofen', 'form_match_status': 'mapped', 'mapped': True,
           'mapped_identity': True, 'identity_disposition': 'clean',
           'raw_source_path': 'ingredientRows[0]', 'quantity': 600, 'unit': 'mg',
           'raw_taxonomy': {'category': 'botanical', 'forms': [{'name': 'Fenugreek Seed Extract'}]}}
    product = {'activeIngredients': [row], 'ingredient_quality_data': {'ingredients_scorable': [row]},
               'evidence_data': {'clinical_matches': [{'id': 'BRAND_TESTOFEN', 'evidence_level': 'branded-rct',
                   'matched_source_row_refs': ['ingredientRows[0]'], 'scoring_eligible': clinical_state == 'approved',
                   'effect_direction': 'null' if clinical_state == 'null' else 'positive_strong',
                   'references_structured': [{'pmid': '26791805', 'retracted': clinical_state == 'retracted'}]}]}}
    product['formulation_data'] = {'standardized_botanicals': collector._collect_standardized_botanicals(product)}
    assert bp._standardization_tier_credit(product, row) == bp.STANDARDIZATION_TIER_FULL


@pytest.mark.parametrize('name,extra', [
    ('Fenugreek Seed Extract', {}),
    ('Ambiguous Testofen', {'identity_disposition': 'ambiguous', 'match_ambiguity_candidates': ['fenugreek', 'other']}),
    ('Unstandardized Studied Material', {}),
])
def test_clinical_brand_and_generic_or_ambiguous_identity_do_not_prove_standardization(collector, name, extra):
    row = {'name': name, 'canonical_id': 'fenugreek', 'standard_name': 'Fenugreek',
           'raw_source_path': 'ingredientRows[0]', 'quantity': 600, 'unit': 'mg', **extra}
    product = {'activeIngredients': [row], 'evidence_data': {'clinical_matches': [{
        'id': 'BRAND_STUDIED_CONTROL', 'evidence_level': 'branded-rct',
        'matched_source_row_refs': ['ingredientRows[0]']}]}}
    product['formulation_data'] = {'standardized_botanicals': collector._collect_standardized_botanicals(product)}
    assert bp._standardization_tier_credit(product, row) == 0


@pytest.mark.parametrize('eligible', [False, True])
def test_unstandardized_specific_material_keeps_primary_and_named_preparation_identity(eligible):
    prepared = {'name': 'Sytrinol', 'canonical_id': 'sytrinol', 'standard_name': 'Fenugreek',
                'matched_form': 'specific extract', 'mapped': True, 'form_match_status': 'mapped',
                'quantity': 500, 'unit': 'mg', 'raw_source_path': 'ingredientRows[0]',
                'raw_taxonomy': {'category': 'botanical'}}
    generic = {'name': 'Generic botanical', 'canonical_id': 'tribulus', 'standard_name': 'Tribulus',
               'mapped': True, 'quantity': 1000, 'unit': 'mg', 'raw_source_path': 'ingredientRows[1]',
               'raw_taxonomy': {'category': 'botanical'}}
    product = {'ingredient_quality_data': {'ingredients_scorable': [prepared, generic]},
               'evidence_data': {'clinical_matches': [{'id': 'BRAND_CONTROL', 'scoring_eligible': eligible,
                   'matched_source_row_refs': ['ingredientRows[0]']}]}}
    assert bp._primary_botanical_active(product)['raw_source_path'] == 'ingredientRows[0]'
    assert bp._is_named_botanical_preparation(product, {**prepared, 'is_parent_total': True})
    assert bp._standardization_tier_credit(product, prepared) == 0


def test_ambiguous_material_cannot_inherit_a_parent_standardization_projection():
    row = {'name': 'Ambiguous Testofen', 'canonical_id': 'fenugreek', 'mapped': True,
           'matched_form': 'testofen', 'identity_disposition': 'ambiguous'}
    product = {'formulation_data': {'standardized_botanicals': [{'name': 'Fenugreek',
        'botanical_id': 'fenugreek', 'meets_threshold': True}]}}
    assert not bp._resolved_preparation_row(product, row)
    assert not bp._standardized_match(product, row)
    assert bp._standardization_tier_credit(product, row) == 0


def test_exact_brand_name_cannot_override_a_conflicting_canonical_material(collector):
    row = {'name': 'Testofen', 'canonical_id': 'tribulus', 'canonical_source_db': 'ingredient_quality_map',
           'quantity': 600, 'unit': 'mg'}
    found = collector._collect_standardized_botanicals({'activeIngredients': [row]})
    assert not any(item.get('botanical_id') == 'testofen' and item['meets_threshold'] for item in found)


def test_exact_testofen_source_form_carries_material_spec_without_label_percent(collector):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from scoring_v4.scored_artifact import build_scored_artifact
    raw = json.loads((Path(__file__).parent / 'fixtures/material_standardization_304641_raw.json').read_text())
    raw['ingredientRows'][0]['name'] = 'Fenugreek'
    raw['ingredientRows'][0]['forms'].append({'order': 2, 'name': 'Testofen',
                                             'category': 'botanical', 'ingredientGroup': 'Fenugreek'})
    product, errors = collector.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    assert not errors
    owner = next(row for row in product['ingredient_quality_data']['ingredients_scorable']
                 if row['raw_source_path'] == 'ingredientRows[0]')
    assert owner['matched_form'] == 'testofen'
    assert bp._standardization_tier_credit(product, owner) == bp.STANDARDIZATION_TIER_FULL
    item = next(x for x in product['formulation_data']['standardized_botanicals'] if x['botanical_id'] == 'testofen')
    assert item['percentage_found'] == 0 and item['percentage_source'] is None
    assert build_scored_artifact(product)['quality_pillars_v4']['evidence']['score'] == 0.0


def test_generic_slendesta_alias_cannot_claim_the_proprietary_material_spec(collector):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from scoring_v4.scored_artifact import build_scored_artifact
    raw = json.loads((Path(__file__).parent / 'fixtures/material_standardization_304641_raw.json').read_text())
    raw['ingredientRows'] = raw['ingredientRows'][:1]
    raw['ingredientRows'][0].update(name='Potato protein extract', ingredientGroup='Potato', forms=[])
    product, errors = collector.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    assert not errors
    assert not any(x['evidence_source'] == 'branded_form' and x['meets_threshold']
                   for x in product['formulation_data']['standardized_botanicals'])
    assert bp.score_botanical_formulation(product)['components'].get('marker_standardization_declared', 0) == 0
    build_scored_artifact(product)


@pytest.mark.parametrize('name', ['KSM-66', 'KSM-66 Ashwagandha'])
def test_existing_short_brand_identity_keeps_verified_spec_without_clinical_credit(collector, name):
    row = {'name': name, 'canonical_id': 'ashwagandha', 'quantity': 600, 'unit': 'mg'}
    found = collector._collect_standardized_botanicals({'activeIngredients': [row],
                                                      'evidence_data': {'clinical_matches': []}})
    item = next(x for x in found if x['botanical_id'] == 'ksm_66_ashwagandha')
    assert item['tier'] == 'full' and item['evidence_source'] == 'branded_form'
    assert item['percentage_found'] == 0 and item['percentage_source'] is None


def test_unrelated_product_brand_cannot_supply_a_generic_rows_material_proof(collector):
    row = {'name': 'Potato protein extract', 'quantity': 600, 'unit': 'mg'}
    found = collector._collect_standardized_botanicals({'product_name': 'Slendesta Testofen',
                                                       'activeIngredients': [row]})
    assert not any(x['evidence_source'] == 'branded_form' for x in found)



def test_real_clean_ksm_identity_retains_standardization_despite_generic_candidate_history(collector):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from scoring_v4.scored_artifact import build_scored_artifact
    raw = json.loads((Path(__file__).parent / 'fixtures/material_standardization_306237_raw.json').read_text())
    product, errors = collector.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    assert not errors
    row = product['ingredient_quality_data']['ingredients_scorable'][0]
    assert row['identity_disposition'] == 'clean' and row['match_ambiguity_candidates']
    assert bp._standardization_tier_credit(product, row) == bp.STANDARDIZATION_TIER_FULL
    artifact = build_scored_artifact(product)
    assert artifact['quality_pillars_v4']['evidence']['score'] == 15.6
    assert artifact['quality_pillars_v4']['dose']['score'] == 11.4


@pytest.mark.parametrize('form', ['Fenugreek powder', 'Fenugreek oil', 'Fenugreek seed extract'])
def test_generic_mapped_parent_form_is_not_a_named_defined_material(form):
    row = {'name': 'Fenugreek', 'canonical_id': 'fenugreek', 'matched_form': form,
           'mapped': True, 'form_match_status': 'mapped', 'identity_disposition': 'clean',
           'is_parent_total': True, 'quantity': 500, 'unit': 'mg'}
    assert not bp._is_named_botanical_preparation({}, row)
    generic_marker = {'formulation_data': {'standardized_botanicals': [{
        'name': 'Fenugreek', 'meets_threshold': True, 'evidence_source': 'percentage_local'}]}}
    assert not bp._is_named_botanical_preparation(generic_marker, row)



def test_same_standardized_registry_identity_is_not_a_conflicting_iqm_parent(collector):
    row = {'name': 'KSM-66 Ashwagandha root extract', 'canonical_id': 'ksm_66_ashwagandha',
           'canonical_source_db': 'standardized_botanicals', 'quantity': 600, 'unit': 'mg'}
    found = collector._collect_standardized_botanicals({'activeIngredients': [row]})
    assert any(x['botanical_id'] == 'ksm_66_ashwagandha' and x['meets_threshold'] for x in found)


def test_exact_material_projection_cannot_lend_standardization_to_generic_sibling(collector):
    from copy import deepcopy
    from enhanced_normalizer import EnhancedDSLDNormalizer
    raw = json.loads((Path(__file__).parent / 'fixtures/material_standardization_304641_raw.json').read_text())
    first = raw['ingredientRows'][0]
    first['name'] = 'Fenugreek'
    first['forms'].append({'order': 2, 'name': 'Testofen', 'category': 'botanical', 'ingredientGroup': 'Fenugreek'})
    sibling = deepcopy(first)
    sibling['forms'] = []
    sibling['order'] = 2
    raw['ingredientRows'] = [first, sibling]
    product, errors = collector.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    assert not errors
    rows = {x['raw_source_path']: x for x in product['ingredient_quality_data']['ingredients_scorable']}
    exact, generic = rows['ingredientRows[0]'], rows['ingredientRows[1]']
    assert bp._standardization_tier_credit(product, exact) == bp.STANDARDIZATION_TIER_FULL
    assert bp._standardization_tier_credit(product, generic) == 0
    assert bp._is_named_botanical_preparation(product, {**exact, 'is_parent_total': True})
    assert not bp._is_named_botanical_preparation(product, {**generic, 'is_parent_total': True})
    for item in product['formulation_data']['standardized_botanicals']:
        item.pop('raw_source_path', None)
    assert bp._standardization_tier_credit(product, exact) == bp.STANDARDIZATION_TIER_FULL
    assert bp._standardization_tier_credit(product, generic) == 0


@pytest.mark.parametrize('literal', ['Potato protein extract', 'Potato protein', 'Proteinase inhibitor II', 'PI2'])
def test_generic_potato_identity_is_not_repaired_to_slendesta(collector, literal):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    raw = json.loads((Path(__file__).parent / 'fixtures/material_standardization_304641_raw.json').read_text())
    raw['ingredientRows'] = raw['ingredientRows'][:1]
    raw['ingredientRows'][0].update(name=literal, ingredientGroup='Potato', forms=[])
    product, errors = collector.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    assert not errors
    assert not any(x.get('canonical_id') == 'slendesta' for x in product['ingredient_quality_data']['ingredients'])



def test_explicit_slendesta_still_resolves_its_own_material_spec(collector):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    raw = json.loads((Path(__file__).parent / 'fixtures/material_standardization_304641_raw.json').read_text())
    raw['ingredientRows'] = raw['ingredientRows'][:1]
    raw['ingredientRows'][0].update(name='Slendesta', ingredientGroup='Potato', forms=[])
    product, errors = collector.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    assert not errors
    assert any(x.get('canonical_id') == 'slendesta' for x in product['ingredient_quality_data']['ingredients'])
    assert any(x['botanical_id'] == 'slendesta' and x['tier'] == 'full'
               for x in product['formulation_data']['standardized_botanicals'])



def test_legacy_projection_cannot_borrow_a_different_reviewed_brand():
    row = {'name': 'KSM-66', 'canonical_id': 'ashwagandha', 'mapped': True,
           'matched_form': 'KSM-66 ashwagandha', 'identity_disposition': 'clean'}
    product = {'formulation_data': {'standardized_botanicals': [{
        'name': 'KSM-66', 'botanical_id': 'testofen', 'standard_name': 'Testofen',
        'evidence_source': 'branded_form', 'meets_threshold': True}]}}
    assert bp._standardization_tier_credit(product, row) == 0
    assert not bp._is_named_botanical_preparation(product, {**row, 'is_parent_total': True,
                                                          'name': 'Generic Ashwagandha'})



def test_strict_material_identity_accepts_exact_sensoril_id_without_spec_credit():
    from evidence_resolver import is_reviewed_branded_material
    assert is_reviewed_branded_material('ashwagandha', 'Sensoril', strict_material_spelling=True)
    assert not is_reviewed_branded_material('ashwagandha', 'Ashwagandha leaf root extract',
                                           strict_material_spelling=True)
    assert not is_reviewed_branded_material('ashwagandha', 'Sensorilized extract',
                                           strict_material_spelling=True)
    assert not is_reviewed_branded_material('fenugreek', 'Torabolic', preparation_name='Testofen',
                                           strict_material_spelling=True)
    row = {'name': 'Sensoril', 'canonical_id': 'ashwagandha', 'matched_form': 'sensoril ashwagandha',
           'mapped': True, 'form_match_status': 'mapped', 'identity_disposition': 'clean'}
    assert bp._resolved_preparation_row({}, row)
    assert bp._standardization_tier_credit({}, row) == 0


def test_real_sensoril_primary_is_not_displaced_by_an_opaque_mushroom_blend(collector):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    raw = json.loads((Path(__file__).parent / 'fixtures/botanical_blend_321944_raw.json').read_text())
    product, errors = collector.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    assert not errors
    primary = bp._primary_botanical_active(product)
    assert primary['canonical_id'] == 'ashwagandha'
    assert primary['raw_source_path'] == 'ingredientRows[3]'
    assert primary['quantity'] == 250
    assert bp.score_botanical_dose(product)['band'] == 'disclosed_no_reference'
    assert bp._standardization_tier_credit(product, primary) == 0
