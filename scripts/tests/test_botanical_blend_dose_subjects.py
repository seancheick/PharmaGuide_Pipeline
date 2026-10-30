"""Structural blend totals remain zero without inventing an ingredient benchmark duty."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

IDS = ['1640','19435','19436','219891','243132','69625','28548','46707','176190','232084']


@pytest.fixture(scope='module')
def structural_blend_products():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    n, e = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    base = Path(__file__).parent / 'fixtures'
    return {pid: e.enrich_product(n.normalize_product(json.loads((base / (
        f'raw_blend_grapefruit_{pid}.json' if pid in {'176190','232084'} else
        f'raw_named_blend_{pid}.json')).read_text())))[0] for pid in IDS}


def _parent(product):
    from scoring_v4.modules.botanical_profile import _scoring_actives
    return next(row for row in _scoring_actives(product)
                if row.get('reason') == 'identity_bearing_blend_header_mass'
                and row.get('scoring_input_kind') == 'product_level_evidence')


@pytest.mark.parametrize('pid', IDS)
def test_unidentified_source_blend_header_is_not_an_ingredient_dose_subject(structural_blend_products, pid):
    from scoring_v4.modules.botanical_profile import score_botanical_purpose_dose, _is_named_botanical_preparation
    from scoring_v4.scored_artifact import unfinished_source_assessment
    product = structural_blend_products[pid]
    row = _parent(product)
    before = deepcopy(product)
    assert not _is_named_botanical_preparation(product,row)
    result = score_botanical_purpose_dose(product,row)
    assert result['score'] == 0
    assert result['band'] == 'blend_total_only'
    assert result['metadata']['assessment_status'] == 'not_applicable'
    assert 'benchmark' not in result['metadata']
    assert unfinished_source_assessment(product, {'dimensions': {'dose': {'metadata': {
        'specialized_purpose_assessments': [result]}}}}) is None
    assert product == before


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'foreign', 'role', 'canonical', 'missing_canonical',
                                     'missing_ledger', 'duplicate_ledger', 'malformed_mass', 'unknown_unit'])
def test_unidentified_blend_disposition_needs_positive_original_header_proof(structural_blend_products, change):
    from scoring_input_contract import _source_tree_rows
    from scoring_v4.modules.botanical_profile import score_botanical_purpose_dose
    product = deepcopy(structural_blend_products['1640'])
    row = _parent(product)
    source = next(r for r in _source_tree_rows(product) if r.get('raw_source_path') == row['raw_source_path'])
    assert source is not None
    if change == 'missing':
        product['activeIngredients'] = []
    elif change == 'duplicate':
        product['activeIngredients'].append(deepcopy(source))
    elif change == 'foreign':
        row['raw_source_path'] = 'ingredientRows[999]'
    elif change == 'role':
        source['cleaner_row_role'] = 'active_scorable'
    elif change == 'canonical':
        source['canonical_id'] = 'unknown_prepared_material'
    elif change == 'missing_canonical':
        source.pop('canonical_id')
    elif change == 'missing_ledger':
        product['label_source_rows'] = []
    elif change == 'duplicate_ledger':
        product['label_source_rows'].append(deepcopy(next(r for r in product['label_source_rows']
                                                          if r.get('raw_source_path')==row['raw_source_path'])))
    elif change == 'malformed_mass':
        source['quantity'] = 'unread'
    else:
        source['unit'] = 'unknown_unit'
    result = score_botanical_purpose_dose(product,row)
    assert result['score'] == 0
    assert result['metadata'].get('assessment_status') != 'not_applicable'
    assert result['metadata']['benchmark'] == 'unresolved'


@pytest.mark.parametrize('pid', ['28548','46707'])
def test_known_hidden_member_keeps_its_separate_amount_limitation(structural_blend_products,pid):
    from scoring_input_contract import is_lent_blend_mass
    from scoring_v4.modules.botanical_profile import _scoring_actives, score_botanical_purpose_dose
    product=structural_blend_products[pid]
    rows=[r for r in _scoring_actives(product) if is_lent_blend_mass(r)]
    assert rows
    result=score_botanical_purpose_dose(product,rows[0])
    assert result['score'] > 0
    assert result['metadata']['assessment_status']=='complete'
    assert result['metadata']['reason_code']=='amount_not_declared'


from scripts.tests.test_v4_botanical_profile import citrus_binding_products


@pytest.mark.parametrize('pid',['60794','74011'])
def test_source_verified_cordiart_keeps_its_own_dose_reference(citrus_binding_products,pid):
    from dose_assessment import _source_dose_row
    from scoring_v4.modules.botanical_profile import score_botanical_purpose_dose
    product=citrus_binding_products[pid]
    row=next(r for r in product['ingredient_quality_data']['ingredients_scorable']
             if r.get('canonical_id')=='citrus_bioflavonoids')
    # Cordiart's direct ingredient has its own verified reference; it is not
    # a synthetic structural header, irrespective of the complex-form helper.
    source = _source_dose_row(product,row)
    assert source is not None and source['canonical_id']=='citrus_bioflavonoids'
    result=score_botanical_purpose_dose(product,row)
    assert result['score'] > 0
    assert result['metadata']['benchmark']=='absent'
    assert result['metadata'].get('assessment_status')!='not_applicable'
