"""Returned preparation-specific findings cannot become broad efficacy clearance."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clinical_applicability import assess_clinical_source_review, reviewed_entries
from clinical_evidence_schema import validate_ingredient_context


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
