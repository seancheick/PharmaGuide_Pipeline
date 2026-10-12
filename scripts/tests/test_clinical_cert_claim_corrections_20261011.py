import json
from pathlib import Path
import pytest
from enrich_supplements_v3 import SupplementEnricherV3

DATA=Path(__file__).resolve().parents[1]/'data/cert_claim_rules.json'

@pytest.fixture(scope='module')
def rules(): return json.loads(DATA.read_text())

@pytest.fixture(scope='module')
def enricher(): return SupplementEnricherV3()

@pytest.mark.parametrize('group,key,text',[
 ('third_party_programs','nsf_contents_certified','Our lab uses NSF/ANSI 173 methods'),
 ('third_party_programs','bscg','BSCG Certified Quality'),
 ('third_party_programs','goed','GOED Member'),
 ('third_party_programs','itested','Tested by Eurofins'),
 ('third_party_programs','tga_listed','TGA Registered'),
 ('third_party_programs','nsf_ansi_455','NSF Dietary Supplement Certified'),
 ('gmp_certifications','cgmp_certified','cGMP Compliant'),
 ('organic_certifications','usda_organic','Certified Organic'),
 ('allergen_free_claims','gluten_free_certified','Certified Gluten-Free'),
 ('allergen_free_claims','non_gmo_project','Not Non-GMO Project Verified'),
 ('quality_markers','iso_certified','ISO 14001 guidelines'),
 ('quality_markers','iso_certified','ISO 50001 Certified'),
])
def test_other_program_or_negated_wording_is_not_specific_eligible_claim(rules,enricher,group,key,text):
 result=enricher._check_claim_with_validation(text,'statements[0]',rules['rules'][group][key],rules['config']['source_field_groups'])
 assert result is None or not result['score_eligible']

@pytest.mark.parametrize('group,key,text',[
 ('third_party_programs','nsf_contents_certified','NSF Contents Certified'),
 ('third_party_programs','bscg','BSCG Certified Drug Free'),
 ('third_party_programs','itested','iHerb iTested'),
 ('third_party_programs','tga_listed','AUST L 123456'),
 ('third_party_programs','nsf_ansi_455','NSF/ANSI 455-2 certified'),
 ('gmp_certifications','cgmp_certified','cGMP Certified'),
 ('organic_certifications','usda_organic','USDA Organic'),
 ('allergen_free_claims','gluten_free_certified','GFCO Certified'),
 ('allergen_free_claims','non_gmo_project','Non-GMO Project Verified'),
 ('quality_markers','iso_certified','ISO 9001 Certified'),
])
def test_explicit_program_claim_controls_remain_detectable(rules,enricher,group,key,text):
 result=enricher._check_claim_with_validation(text,'statements[0]',rules['rules'][group][key],rules['config']['source_field_groups'])
 assert result and result['score_eligible']


def test_informed_quality_review_does_not_establish_independent_gmp_audit(rules):
 for key in ['informed_sport','informed_choice']:
  assert not rules['rules']['third_party_programs'][key].get('implies_gmp')
