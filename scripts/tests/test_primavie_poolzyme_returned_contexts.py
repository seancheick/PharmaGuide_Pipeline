"""Returned preparation-specific findings cannot become broad efficacy clearance."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clinical_applicability import assess_clinical_source_review, reviewed_entries
from clinical_evidence_schema import validate_ingredient_context


def test_poolzyme_extraction_preserves_explicit_source_acceptance_hold():
    record = reviewed_entries()['INGR_DIGESTIVE_ENZYMES']
    contexts = record.get('study_contexts', [])
    assert len(contexts) == 1
    [context] = contexts
    assert context['source_pmids'] == ['37976892']
    assert context['identity']['branded_material'] == 'Poolzyme Multi'
    assert context['dose']['values'] == [400]
    assert context['dose']['administration_frequency'] == 'One200mg capsule at lunch and one200mg capsule at dinner.'
    assert context['dose']['duration_days'] == 60
    assert context['population']['description'].startswith('120 adults')
    assert context['review_status'] == 'source_verified_pending_clinical_review'
    assert all(o['direction'] == 'unresolved' and 'outcome_role' not in o for o in context['outcomes'])
    assert 'clinical_review' not in context
    assert validate_ingredient_context(context, authoring=True) == []
    assert assess_clinical_source_review(record)['is_complete'] is False
    assert any('review.approval_required' in e for e in assess_clinical_source_review(record)['errors'])
    limits = ' '.join(context['limitations'])
    assert 'RAW' in limits and 'ethics' in limits and 'registration' in limits
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
    assert record['study_contexts'][0]['dose']['values'] == [400]
    assert record['references_structured'][0]['pmid'] == '37976892'
