"""A form-scoped interaction rule sees every declared form on the row.

331488 and 12012 declare "Vitamin A (as Beta-Carotene, Retinyl Acetate)": the
row's primary form_id is beta-carotene, and reading form_id alone hid the
retinyl acetate from the preformed vitamin A pregnancy rule.
"""
import json
import os
from pathlib import Path

import pytest

RULE = {'id': 'RULE_TEST', 'form_scope': ['retinyl acetate', 'retinyl palmitate']}


@pytest.fixture(scope='module')
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3
    return SupplementEnricherV3()


def test_a_declared_secondary_form_in_scope_applies_the_rule(enricher):
    row = {'form_id': 'beta-carotene from mixed carotenoids',
           'matched_forms': [{'form_key': 'beta-carotene from mixed carotenoids'}, {'form_key': 'retinyl acetate'}]}
    assert enricher._interaction_rule_applies(RULE, row)


def test_no_declared_form_in_scope_leaves_the_rule_off(enricher):
    row = {'form_id': 'beta-carotene from mixed carotenoids',
           'matched_forms': [{'form_key': 'beta-carotene from mixed carotenoids'}]}
    assert not enricher._interaction_rule_applies(RULE, row)


@pytest.mark.parametrize('pid', ['331488', '12012'])
def test_real_mixed_vitamin_a_labels_get_the_pregnancy_rule(enricher, pid):
    staging = Path(os.environ.get('PG_DSLD_STAGING', '/Users/seancheick/Downloads/PharmaGuide_Datasets/staging/brands'))
    raw = next(iter(sorted(staging.glob(f'*/{pid}.json'))), None) if staging.is_dir() else None
    if raw is None:
        pytest.skip('raw reference label unavailable')
    from enhanced_normalizer import EnhancedDSLDNormalizer
    product, _ = enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(json.loads(raw.read_text())))
    rules = {h.get('rule_id') for r in product['ingredient_quality_data']['ingredients'] if r.get('canonical_id') == 'vitamin_a'
             for h in r.get('safety_hits') or []}
    assert 'RULE_IQM_VITAMIN_A_PREGNANCY_DOSE' in rules


@pytest.mark.parametrize('row, expected', [
    ({'identity_disposition': 'identity_conflict', 'canonical_id': None,
      'recognition_source': 'banned_recalled_ingredients', 'recognized_entry_id': 'ADD_CASCARA_SAGRADA'}, True),
    ({'identity_disposition': 'identity_conflict', 'canonical_id': 'cascara_sagrada',
      'recognition_source': 'banned_recalled_ingredients', 'recognized_entry_id': 'ADD_CASCARA_SAGRADA'}, False),
    ({'identity_disposition': 'resolved', 'canonical_id': 'cascara_sagrada'}, False),
    ({'identity_disposition': 'identity_conflict', 'canonical_id': None,
      'recognition_source': 'banned_recalled_ingredients', 'recognized_entry_id': 'OTHER'}, False),
    ({'identity_disposition': 'identity_conflict', 'canonical_id': None}, False),
])
def test_uncertainty_rule_requires_its_unresolved_safety_subject(enricher, row, expected):
    rule = {'_identity_conflict_only': True, 'subject_ref': {
        'db': 'banned_recalled_ingredients', 'canonical_id': 'ADD_CASCARA_SAGRADA'}}
    assert enricher._interaction_rule_applies(rule, row) is expected


@pytest.mark.parametrize('notes, expected', [
    ('Cascara Sagrada Extract (Rhamnus davurica) PlantPart: bark', True),
    ('Rhamnus purshiana bark', False), ('', False),
])
def test_uncertainty_rule_requires_its_printed_conflicting_species(enricher, notes, expected):
    rule = next(r for r in json.loads((Path(__file__).parents[1] / 'data/ingredient_interaction_rules.json').read_text())['interaction_rules']
                if r['id'] == 'RULE_CASCARA_UNRESOLVED_IDENTITY')
    row = {'identity_disposition': 'identity_conflict', 'canonical_id': None,
           'recognition_source': 'banned_recalled_ingredients',
           'recognized_entry_id': 'ADD_CASCARA_SAGRADA', 'notes': notes}
    assert enricher._interaction_rule_applies(rule, row) is expected
