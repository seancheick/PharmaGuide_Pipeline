import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / 'data' / 'harmful_additives.json'

def records():
    return {row['id']: row for row in json.loads(DATA.read_text())['harmful_additives']}

def test_chlorophyllin_does_not_claim_efsa_confirmed_safety():
    row = records()['ADD_SODIUM_COPPER_CHLOROPHYLLIN']
    text = json.dumps({k:v for k,v in row.items() if k != 'review'}).lower()
    assert 'confirmed safety' not in text
    assert 'cannot be assessed' in text
    assert '4081' not in text
    assert row['severity_level'] == 'low'

def test_xylitol_source_matches_actual_paper():
    text = json.dumps(records()['ADD_XYLITOL'])
    assert '38814334' not in text
    assert '38842092' in text
    assert 'at any dose' not in text

def test_folate_common_variant_does_not_imply_methylfolate_preference():
    row=records()['ADD_SYNTHETIC_B_VITAMINS']
    assert 'methylfolate is preferred' not in json.dumps(row).lower()
    assert '400' in row['mechanism_of_harm']

def test_source_outcomes_and_regulatory_scope_are_not_inflated():
    rows=records()
    assert 'nonrandomized' in rows['ADD_ERYTHRITOL']['notes'].lower()
    assert rows['ADD_SACCHARIN']['dose_thresholds']['value']==9
    assert '2011' in rows['ADD_CARMINE_RED']['regulatory_status']['US']
    assert 'cannot' in rows['ADD_IRON_OXIDE']['regulatory_status']['EU']
    assert 'no overall' in rows['ADD_CARRAGEENAN']['mechanism_of_harm'].lower()
    assert 'no intestinal' in rows['ADD_CARBOXYMETHYLCELLULOSE']['notes'].lower()
    assert '2.5' in rows['ADD_MSG']['notes']

def test_regulatory_references_identify_the_actual_chemical():
    rows=records()
    wrong={'ADD_DISODIUM_EDTA':'172.120','ADD_CROSCARMELLOSE_SODIUM':'172.330','ADD_CROSPOVIDONE':'172.375','ADD_MICROCRYSTALLINE_CELLULOSE':'182.1745','ADD_POTASSIUM_HYDROXIDE':'184.1293','ADD_SODIUM_ALUMINUM_PHOSPHATE':'172.620','ADD_SODIUM_TRIPOLYPHOSPHATE':'172.620','ADD_TETRASODIUM_DIPHOSPHATE':'172.620','ADD_SORBITAN_MONOSTEARATE':'172.840','ADD_STEARIC_ACID':'172.864'}
    for key,citation in wrong.items():
        assert citation not in json.dumps(rows[key]['references_structured']), key
    assert rows['ADD_SORBITAN_MONOSTEARATE']['dose_thresholds'][0]['amount']==10
    assert 'sorbitan' in rows['ADD_SORBITAN_MONOSTEARATE']['dose_thresholds'][0]['unit']

def test_source_species_and_identity_do_not_transfer_to_other_additives():
    rows=records()
    assert '388' not in rows['ADD_POLYSORBATE_20']['mechanism_of_harm']
    assert '25731862' not in json.dumps(rows['ADD_POLYSORBATE_20'])
    assert 'specific' in rows['ADD_SOY_MONOGLYCERIDES']['population_warnings'][0].lower()
    assert '38587819' in json.dumps(rows['ADD_D_MANNOSE'])
    assert 'Southampton' not in json.dumps(rows['ADD_ARTIFICIAL_FLAVORS']['population_warnings'])

def test_total_intake_and_route_context_are_explicit():
    rows=records()
    for key in ['ADD_SODIUM_BENZOATE','ADD_POTASSIUM_BENZOATE']:
        assert '20' in rows[key]['regulatory_status']['WHO']
        assert 'JECFA' not in rows[key]['dose_thresholds']['source']
    for key in ['ADD_FRUCTOSE','ADD_HFCS']:
        assert 'total' in rows[key]['dose_thresholds']['source'].lower()
        assert 'conditional' not in rows[key]['dose_thresholds']['source'].lower()
    assert 'EFSA 2018 re-evaluation' not in rows['ADD_SODIUM_LAURYL_SULFATE']['regulatory_status']['EU']
    assert 'spikes blood sugar quickly' not in rows['ADD_TAPIOCA_FILLER']['safety_summary']


def test_purefruit_select_uses_verified_monk_fruit_owner_without_harm_penalty():
    """Manufacturer identity is monk fruit; no sourced harm supports ADD classification."""
    assert 'ADD_PUREFRUIT_SELECT' not in records()
    other = json.loads((DATA.parent / 'other_ingredients.json').read_text())
    rows = {r['id']: r for r in other['other_ingredients']}
    assert 'purefruit select' in rows['NHA_MONK_FRUIT']['aliases']
