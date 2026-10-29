"""Sean's October29 whole-Cordiart Dose ruling never supplies benefit or safety credit."""
from copy import deepcopy

import pytest

from scripts.tests.test_v4_botanical_profile import citrus_binding_products


@pytest.mark.parametrize('pid', ['60794', '74011'])
def test_exact_whole_cordiart_has_its_own_completed_dose_reference(citrus_binding_products, pid):
    from scoring_v4.scored_artifact import build_scored_artifact
    from build_final_db import build_detail_blob
    from scoring_v4.modules.botanical_profile import score_botanical_purpose_dose
    product = citrus_binding_products[pid]
    row = next(r for r in product['ingredient_quality_data']['ingredients_scorable']
               if r.get('canonical_id') == 'citrus_bioflavonoids')
    result = score_botanical_purpose_dose(product, row)
    assert result['metadata']['benchmark'] == 'absent'
    artifact = build_scored_artifact(product)
    assert artifact['quality_pillars_v4']['dose']['score'] == 11.4
    assert artifact['quality_pillars_v4']['evidence']['score'] == 0
    assert 'dose_benchmark_identity_unresolved' not in artifact['assessment_readiness']['release_assessment']['blockers']
    blob = build_detail_blob(product, artifact)
    assert blob['quality_pillars_v4']['dose']['score'] == 11.4
    if pid == '74011':
        assert blob['allergens'] == [{'allergen_id': 'ALLERGEN_WHEAT',
            'display_name': 'Wheat', 'evidence': 'Contains: Wheat',
            'presence_type': 'contains', 'severity_level': 'moderate'}]


def test_cordiart_reference_is_separately_dated_and_not_clinical_approval():
    from evidence_resolver import _load_literature_evidence
    from dose_assessment import verified_reference_citations
    from clinical_applicability import assess_clinical_source_review
    record = _load_literature_evidence()['cordiart']
    assert record['reference_semantics']['review_date'] == '2026-10-29'
    assert record['reference_semantics']['scope'] == 'exact_preparation'
    assert record['reference_semantics']['source_ids'] == ['PMID:27797708']
    assert 'Sean' in record['reference_semantics']['rationale']
    assert verified_reference_citations(record)
    assert not assess_clinical_source_review(record)['is_complete']


@pytest.mark.parametrize('change', ['generic', 'isolated', 'unverified', 'foreign_ref', 'derived', 'title_only',
 '80_percent', 'fruit', 'missing_spec', 'borrowed_spec'])
def test_cordiart_reference_cannot_be_borrowed(citrus_binding_products, change):
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    product = deepcopy(citrus_binding_products['60794'])
    row = next(r for r in product['ingredient_quality_data']['ingredients_scorable']
               if r.get('canonical_id') == 'citrus_bioflavonoids')
    source = product['activeIngredients'][0]
    if change in {'generic', 'isolated', 'unverified', 'title_only'}:
        literal = {'generic': 'Citrus Bioflavonoids', 'isolated': 'Hesperidin',
                   'unverified': 'Unverified Cordiart preparation', 'title_only': 'Unknown extract'}[change]
        for target in (row, source):
            target['raw_source_text'] = literal
            target['name'] = literal
        product['product_name'] = 'Cordiart Flavonoid Glycoside'
    elif change in {'80_percent', 'fruit', 'missing_spec', 'borrowed_spec'}:
        original = source.get('notes', '')
        source['notes'] = original.replace('90%', '80%') if change == '80_percent' else (
            original.replace('peel', 'fruit') if change == 'fruit' else '')
        source['raw_taxonomy'] = {}
        source['forms'] = []
        if change == 'borrowed_spec':
            row['notes'] = original
    elif change == 'foreign_ref':
        row['raw_source_path'] = 'ingredientRows[99]'
    elif change == 'derived':
        source['is_synthetic'] = True
        source['scoring_input_kind'] = 'synthetic_product_missing_source'
    # Broad citrus may retain its separate approval; it must never resolve by
    # borrowing the named Cordiart reference. Force the broad owner held here.
    from evidence_resolver import _load_literature_evidence
    from unittest.mock import patch
    records = deepcopy(_load_literature_evidence())
    records['citrus_bioflavonoids']['reference_semantics']['approval_status'] = 'pending'
    with patch('evidence_resolver._load_literature_evidence', return_value=records):
        assert _botanical_benchmark(row, product=product) == 'unresolved'


@pytest.mark.parametrize('mutation', ['80_percent', 'fruit', 'missing_spec', 'borrowed_spec', 'percent_missing', 'mg', 'contradictory_part'])
def test_cordiart_physical_constraint_requires_the_original_material_facts(citrus_binding_products, mutation):
    from dose_assessment import _dose_source_preparation_matches
    from evidence_resolver import _load_literature_evidence
    product = deepcopy(citrus_binding_products['60794'])
    row = next(r for r in product['ingredient_quality_data']['ingredients_scorable']
               if r.get('canonical_id') == 'citrus_bioflavonoids')
    record = _load_literature_evidence()['cordiart']
    assert _dose_source_preparation_matches(product, row, record)
    source = product['activeIngredients'][0]
    original = source['notes']
    source['notes'] = (original.replace('90%', '80%') if mutation == '80_percent' else
        original.replace('peel', 'fruit') if mutation == 'fruit' else
        original.replace('90%', '90') if mutation == 'percent_missing' else
        original.replace('90%', '90 mg') if mutation == 'mg' else '')
    source['raw_taxonomy'] = {}
    source['forms'] = []
    if mutation == 'contradictory_part':
        source['notes'] = original
        source['plantPart'] = 'fruit'
    if mutation == 'borrowed_spec':
        row['notes'] = original
    assert not _dose_source_preparation_matches(product, row, record)


@pytest.mark.parametrize('mutation', ['proof', 'semantics', 'approval', 'ambiguous'])
def test_cordiart_reference_requires_current_unique_approved_source_proof(citrus_binding_products, mutation):
    from evidence_resolver import _load_literature_evidence
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    from unittest.mock import patch
    product = citrus_binding_products['60794']
    row = next(r for r in product['ingredient_quality_data']['ingredients_scorable']
               if r.get('canonical_id') == 'citrus_bioflavonoids')
    records = deepcopy(_load_literature_evidence())
    owner = records['cordiart']
    if mutation == 'proof':
        owner['verification_provenance']['reference_citations']['is_complete'] = False
    elif mutation == 'semantics':
        owner['reference_semantics']['scope'] = 'mutated scope'
    elif mutation == 'approval':
        owner['reference_semantics']['approval_status'] = 'pending'
    else:
        records['ambiguous_cordiart'] = deepcopy(owner)
    with patch('evidence_resolver._load_literature_evidence', return_value=records):
        assert _botanical_benchmark(row, product=product) == 'unresolved'


@pytest.mark.parametrize('canonical', ['peppermint', 'chicory_root', 'matcha_tea_powder'])
def test_existing_general_dose_does_not_inherit_clinical_form_requirements(citrus_binding_products, canonical):
    from dose_assessment import _dose_source_preparation_matches
    from evidence_resolver import _load_literature_evidence
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    product = deepcopy(citrus_binding_products['60794'])
    row = next(r for r in product['ingredient_quality_data']['ingredients_scorable']
               if r.get('canonical_id') == 'citrus_bioflavonoids')
    source = product['activeIngredients'][0]
    for target in (source, row):
        target['canonical_id'] = canonical
        target['raw_source_text'] = 'General identified botanical material'
        target['notes'] = ''
        target['raw_taxonomy'] = {}
        target['forms'] = []
        target['plantPart'] = None
    record = _load_literature_evidence()[canonical]
    assert _dose_source_preparation_matches(product, row, record)
    assert _botanical_benchmark(row, product=product) == 'absent'


@pytest.mark.parametrize('canonical', ['cordiart', 'unregistered_cordiart'])
def test_named_reference_requirements_hold_on_every_selection_path(citrus_binding_products, canonical):
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    product = deepcopy(citrus_binding_products['60794'])
    row = next(r for r in product['ingredient_quality_data']['ingredients_scorable']
               if r.get('canonical_id') == 'citrus_bioflavonoids')
    source = product['activeIngredients'][0]
    for target in (source, row):
        target['canonical_id'] = canonical
        target['notes'] = ''
        target['raw_taxonomy'] = {}
        target['forms'] = []
        target['plantPart'] = None
    assert _botanical_benchmark(row, product=product) == 'unresolved'


@pytest.mark.parametrize('mutation', ['missing_product', 'missing_policy', 'missing_required', 'missing_source_flag'])
def test_exact_dose_scope_cannot_complete_without_physical_policy(citrus_binding_products, mutation):
    from evidence_resolver import _load_literature_evidence
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    from unittest.mock import patch
    product = deepcopy(citrus_binding_products['60794'])
    row = next(r for r in product['ingredient_quality_data']['ingredients_scorable']
               if r.get('canonical_id') == 'citrus_bioflavonoids')
    row['canonical_id'] = 'cordiart'
    product['activeIngredients'][0]['canonical_id'] = 'cordiart'
    records = deepcopy(_load_literature_evidence())
    owner = records['cordiart']
    if mutation == 'missing_product':
        product = None
    elif mutation == 'missing_policy':
        owner.pop('applicability')
    elif mutation == 'missing_required':
        owner['applicability'].pop('required_form_terms')
    else:
        owner['applicability'].pop('require_source_label_form')
    with patch('evidence_resolver._load_literature_evidence', return_value=records):
        assert _botanical_benchmark(row, product=product) == 'unresolved'


@pytest.mark.parametrize('mutation', ['missing_proof', 'wrong_reference_type', 'missing_source', 'missing_product'])
def test_exact_dose_scope_keeps_source_proof_on_therapeutic_entry_path(citrus_binding_products, mutation):
    from evidence_resolver import _load_literature_evidence
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    from unittest.mock import patch
    product = deepcopy(citrus_binding_products['60794'])
    row = next(r for r in product['ingredient_quality_data']['ingredients_scorable']
               if r.get('canonical_id') == 'citrus_bioflavonoids')
    entry = deepcopy(_load_literature_evidence()['cordiart'])
    if mutation == 'missing_proof':
        entry['verification_provenance'].pop('reference_citations')
    elif mutation == 'wrong_reference_type':
        entry['reference_semantics']['reference_type'] = 'supported_minimum'
    elif mutation == 'missing_source':
        product['activeIngredients'][0]['notes'] = ''
        product['activeIngredients'][0]['forms'] = []
        product['activeIngredients'][0]['raw_taxonomy'] = {}
        product['activeIngredients'][0]['plantPart'] = None
    else:
        product = None
    # An entry returned before literature lookup cannot evade exact Dose scope
    # merely because its owner is not a backed-clinical-studies path.
    with patch('scoring_v4.modules.botanical_profile._dosing_entry_for', return_value=entry):
        assert _botanical_benchmark(row, product=product) == 'unresolved'
