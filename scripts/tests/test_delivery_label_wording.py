"""Delivery forms written the way labels write them reach delivery_data.

2026-09-16 silent-empty audit: 337 of 544 labels with delivery wording shipped
delivery_data.matched=false. The enhanced_delivery keys are hyphenated
("enteric-coated", "time-release") and matched literally, and netContents
("30 Vegan Enteric-Coated Tablet(s)") was never read. The Formulation pillar's
A3 delivery credit and probiotic survivability both went unawarded.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _names(delivery_data):
    return {system["name"] for system in delivery_data["systems"]}


@pytest.mark.parametrize("product, expected", [
    # 242514 Mini Fish Oil: trusted statement, space instead of hyphen.
    ({"statements": [{"type": "Formulation re: Other",
                      "notes": "Enteric coated to minimize fish burps"}]}, "enteric-coated"),
    # 227906 Vitamin B-12 1000 mcg Timed-Release: "timed" not "time".
    ({"fullName": "Vitamin B-12 1000 mcg Timed-Release"}, "time-release"),
    # 333918 Garlinase 5000: the dosage form lives in netContents.
    ({"netContents": [{"order": 1, "quantity": 30, "unit": "Vegan Enteric-Coated Tablet(s)",
                       "display": "30 Vegan Enteric-Coated Tablet(s)"}]}, "enteric-coated"),
    # 205138 Fortify Women's 50 Billion.
    ({"netContents": [{"order": 1, "quantity": 30, "unit": "Delayed-Release Veg. Capsule(s)",
                       "display": "30 Delayed-Release Veg. Capsule(s)"}]}, "delayed-release"),
    # Approved submission PG_SUB_A89A9212EDDD4A89A54842EF791F2AE2: a manual label
    # carries physicalState.name only, no DSLD LanguaL description.
    ({"physicalState": {"name": "Delayed-release capsule"}}, "delayed-release"),
])
def test_label_wording_matches_the_delivery_form(enricher, product, expected):
    delivery = enricher._collect_delivery_data({"fullName": "Supplement", **product})
    assert expected in _names(delivery)


@pytest.mark.parametrize("product", [
    {"netContents": [{"order": 1, "quantity": 90, "unit": "Mini Coated Softgel(s)",
                      "display": "90 Mini Coated Softgel(s)"}]},
    {"statements": [{"type": "General Statements: All Other Content",
                     "notes": "Enteric coated to minimize fish burps"}]},
])
def test_plain_coating_and_untrusted_statements_do_not_match(enricher, product):
    delivery = enricher._collect_delivery_data({"fullName": "Supplement", **product})
    assert "enteric-coated" not in _names(delivery)


def test_probiotic_survivability_reads_the_net_contents_form(enricher):
    product = {
        "fullName": "Fortify Women's Probiotic 50 Billion",
        "product_name": "Fortify Women's Probiotic 50 Billion",
        "netContents": [{"order": 1, "quantity": 30, "unit": "Delayed-Release Veg. Capsule(s)",
                         "display": "30 Delayed-Release Veg. Capsule(s)"}],
        "statements": [],
        "activeIngredients": [{
            "name": "Lactobacillus rhamnosus GG", "standardName": "Lactobacillus rhamnosus GG",
            "category": "probiotic", "quantity": 10, "unit": "billion CFU",
            "raw_source_path": "ingredientRows[0]", "harvestMethod": "", "notes": "",
        }],
        "inactiveIngredients": [],
    }
    assert enricher._collect_probiotic_data(product)["has_survivability_coating"] is True


@pytest.mark.parametrize('product', [
    {'statements': [{'type': 'Formula re: Contains', 'notes': 'Enteric Coated Peppermint Oil Capsules'}]},
    {'statements': [{'type': 'Formulation re: Other', 'notes': 'Enteric coating withstands stomach acid'}]},
    {'activeIngredients': [{'name': 'IBgard Peppermint Oil', 'raw_source_text': 'IBgard Peppermint Oil'}]},
])
def test_source_enteric_variants_reach_existing_delivery_owner(enricher, product):
    assert 'enteric-coated' in _names(enricher._collect_delivery_data(product))

@pytest.mark.parametrize('text,expected', [
    ('No high fructose corn syrup, gelatin, added flavors', set()),
    ('No gelatin or syrup', set()),
    ('Not enteric-coated', set()),
    ('Syrup-free capsules', set()),
    ('Without enteric coating', set()),
    ('No syrup; enteric-coated capsules', {'enteric-coated'}),
    ('No syrup but enteric-coated capsules', {'enteric-coated'}),
    ('Enteric-coated capsules without syrup', {'enteric-coated'}),
    ('Enteric-coated syrup-free capsules', {'enteric-coated'}),
    ('Enteric-coated capsules', {'enteric-coated'}),
])
def test_delivery_statement_requires_affirmative_preparation(enricher,text,expected):
    product={'statements':[{'type':'Formula re: Contains','notes':text}]}
    assert _names(enricher._collect_delivery_data(product))==expected


@pytest.mark.parametrize('nested,label,forms,technology', [
    (True,'L-Arginine, Micronized',[],'micronized'),
    (False,'Lycopene',[{'name':'micronized Lycopene'}],'micronized'),
    (False,'Collagen Peptide Complex, Hydrolyzed',[],'hydrolyzed'),
])
def test_delivery_source_preparation_does_not_require_mass_eligibility(enricher,nested,label,forms,technology):
    row={'name':label,'raw_source_text':label,'raw_source_path':'ingredientRows[0].nestedRows[0]' if nested else 'ingredientRows[0]',
         'quantity':0,'unit':'NP','raw_taxonomy':{'forms':forms}}
    active=[{'name':'Blend','raw_source_text':'Blend','raw_source_path':'ingredientRows[0]','nestedIngredients':[row]}] if nested else [row]
    product={'activeIngredients':active,'ingredient_quality_data':{'ingredients_scorable':[],'ingredients':[]}}
    result=enricher._collect_delivery_data(product)
    assert technology in _names(result)
    assert next(x for x in result['systems'] if x['name']==technology)['match_source']==row['raw_source_path']

def test_delivery_detection_preserves_the_label_claim_subject(enricher):
    claim = 'My probiotic blend contains acid resistant strains.'
    delivery = enricher._collect_delivery_data({'statements': [
        {'type': 'Formulation re: Other', 'notes': claim},
    ]})
    system = next(s for s in delivery['systems'] if s['name'] == 'acid-resistant')
    assert system['raw_source_text'] == claim
