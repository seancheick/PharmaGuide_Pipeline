"""Returned preparation-specific findings cannot become broad efficacy clearance."""
from pathlib import Path
import json
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clinical_applicability import assess_clinical_source_review, reviewed_entries
from clinical_evidence_schema import validate_ingredient_context


def test_primavie_returned_biomarker_scope_has_complete_source_context():
    record = reviewed_entries()['BRAND_PRIMAVIE_SHILAJIT']
    review = assess_clinical_source_review(record)
    assert review['is_complete'], review['errors']
    assert len(record['study_contexts']) == 1
    context = record['study_contexts'][0]
    assert context['source_pmids'] == ['26395129']
    assert context['identity']['branded_material'] == 'PrimaVie purified shilajit'
    assert context['dose']['values'] == [500]
    assert context['dose']['duration_days'] == 90
    assert context['dose']['dosage_forms'] == ['oral capsule']
    assert all(outcome['kind'] == 'surrogate' and outcome['hierarchy'] == 'not_reported'
               for outcome in context['outcomes'])
    assert record['effect_direction'] == 'positive_weak'
    assert record['applicability']['supported_outcomes'] == ['testosterone']
    assert record['health_goals_supported'] == []
    assert 'symptomatic benefit' in ' '.join(context['limitations'])


@pytest.mark.parametrize('claim,status,reason', [
    ('Libido Support', 'unresolved', 'label_claim_unclassified'),
    ('Fertility Support', 'unresolved', 'label_claim_unclassified'),
    ('Quality of Life Support', 'unresolved', 'label_claim_unclassified'),
    ('Muscle Strength', 'not_applicable', 'label_purpose_evidence_mismatch'),
    ('Longevity Support', 'not_applicable', 'label_purpose_evidence_mismatch'),
])
def test_primavie_biomarkers_do_not_transfer_to_symptomatic_claims(claim, status, reason):
    from clinical_applicability import assess_clinical_applicability
    record = reviewed_entries()['BRAND_PRIMAVIE_SHILAJIT']
    row = {'name': 'PrimaVie Shilajit', 'raw_source_text': 'PrimaVie Shilajit',
           'canonical_id': 'shilajit', 'mapped': True, 'quantity': 500,
           'unit': 'mg', 'raw_source_path': 'ingredientRows[0]'}
    product = {'product_name': claim, 'activeIngredients': [row],
               'ingredient_quality_data': {'ingredients_scorable': [row]}}
    match = {**record, 'matched_canonical_ids': ['shilajit'],
             'matched_source_row_refs': ['ingredientRows[0]']}
    result = assess_clinical_applicability(product, match)
    assert result['status'] == status
    assert result['reason_code'] == reason


@pytest.mark.parametrize('title,claim', [('PrimaVie Capsules', ''),
    ('PrimaVie Formula', ''), ('Ginger Root Formula', ''), ('Nutritional Formula', ''),
    ('Daily Support', ''),
    ('Testosterone Support', ''), ('Libido Support', 'PrimaVie supports testosterone.')])
def test_primavie_keeps_independently_qualified_testosterone_relationship(title, claim):
    from clinical_applicability import assess_clinical_applicability
    record = reviewed_entries()['BRAND_PRIMAVIE_SHILAJIT']
    row = {'name': 'PrimaVie Shilajit', 'raw_source_text': 'PrimaVie Shilajit',
           'canonical_id': 'shilajit', 'mapped': True, 'quantity': 500,
           'unit': 'mg', 'raw_source_path': 'ingredientRows[0]'}
    product = {'product_name': title, 'activeIngredients': [row],
               'ingredient_quality_data': {'ingredients_scorable': [row]},
               'statements': [{'type': 'Formulation re: Other', 'notes': claim}] if claim else []}
    match = {**record, 'matched_canonical_ids': ['shilajit'],
             'matched_source_row_refs': ['ingredientRows[0]']}
    result = assess_clinical_applicability(product, match)
    assert result['status'] == 'applicable', result
    assert result['supported_outcomes'] == ['testosterone']
    assert result['population_applicability']['context_ids'] == [
        'brand_primavie_26395129_androgen_biomarkers']


@pytest.mark.parametrize('record_id,name,canonical,title', [
    ('BRAND_PRIMAVIE_SHILAJIT', 'PrimaVie Shilajit', 'shilajit',
     'Testosterone Support for Diagnosed Hypogonadism'),
    ('BRAND_KSM66', 'KSM-66 Ashwagandha Root Extract', 'ashwagandha',
     'Perceived Stress and Testosterone Support'),
])
def test_exact_outcome_cannot_override_a_signed_record_exclusion(record_id, name, canonical, title):
    from clinical_applicability import assess_clinical_applicability
    record = reviewed_entries()[record_id]
    row = {'name': name, 'raw_source_text': name, 'canonical_id': canonical,
           'mapped': True, 'quantity': 500, 'unit': 'mg', 'raw_source_path': 'ingredientRows[0]'}
    product = {'product_name': title, 'activeIngredients': [row],
               'ingredient_quality_data': {'ingredients_scorable': [row]}}
    match = {**record, 'matched_canonical_ids': [canonical],
             'matched_source_row_refs': ['ingredientRows[0]']}
    result = assess_clinical_applicability(product, match)
    assert result == {'status': 'not_applicable', 'reason_code': 'label_purpose_evidence_mismatch'}


def test_poolzyme_extraction_preserves_explicit_source_acceptance_hold():
    # Dr. Pham, 2026-10-28 (fifth ruling set): the trial names a fungal
    # multi-enzyme blend, not unequivocally Poolzyme Multi; exact-brand credit
    # needs the study material and its activities identified. The unverified
    # draft extraction lives in the audit receipt (Sean, 2026-10-28: drafts are
    # not production data), so no production context may assert that brand.
    record = reviewed_entries()['INGR_DIGESTIVE_ENZYMES']
    contexts = record.get('study_contexts', [])
    assert contexts == []
    assert 'Poolzyme Multi' not in json.dumps(contexts)
    review = assess_clinical_source_review(record)
    assert review['is_complete'] is False
    assert 'clinical_source_contexts_missing' in review['errors']
    assert record['scoring_eligible'] is False
    assert record['total_enrollment'] == 120
    assert record['registry_completed_trials_count'] is None



def test_explicit_poolzyme_source_hold_cannot_supply_affirmative_credit():
    from evidence_resolver import clinical_record_sources_eligible
    from scoring_v4.modules.generic_evidence import _is_verified_ingredient_human_entry
    record = reviewed_entries()['INGR_DIGESTIVE_ENZYMES']
    assert record.get('scoring_eligible') is False
    assert not clinical_record_sources_eligible(record)
    assert not _is_verified_ingredient_human_entry(record)
    assert record['score_contribution'] == 'tier_2'
    assert record['effect_direction'] == 'positive_strong'  # retained provisionally, not activated
    assert not record.get('study_contexts')
    assert record['references_structured'][0]['pmid'] == '37976892'
