"""The returned 299v review preserves matching-dose positive and null trials."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clinical_evidence_schema import validate_frozen_context
from probiotic_measurements import context_accepted_for_scoring, derived_context_evidence
from studied_formulas import _clinical_strain_registry
from scoring_v4.modules.probiotic_evidence import score_evidence
from test_probiotic_applicability_rubric import strain_product


def _record():
    payload = json.loads((Path(__file__).resolve().parents[1] / 'data/clinically_relevant_strains.json').read_text())
    return next(e for e in payload['clinically_relevant_strains'] if e['id'] == 'STRAIN_PLANTARUM_299V')


def test_returned_299v_positive_and_negative_matching_doses_are_separate_trials():
    record = _record()
    by_source = {c['source_pmids'][0]: c for c in record['study_contexts']}
    positive, negative = by_source['22912552'], by_source['25194614']
    assert positive['trial_family'] != negative['trial_family']
    assert positive['dose']['values'] == negative['dose']['values'] == [10_000_000_000]
    assert positive['dose']['duration_days'] == 28
    assert negative['dose']['duration_days'] == 56
    assert positive['dose']['administration_frequency'] == 'once_daily'
    assert negative['dose']['administration_frequency'] == 'Two capsules daily; within-day timing not reported in the abstract.'
    assert 'Co-therapies were not established by the inspected abstract' in ' '.join(negative['limitations'])
    assert negative['dose']['co_therapies'] == []  # none extracted, not proven absent
    assert negative['outcomes'][0]['direction'] == 'null'
    assert negative['outcomes'][0]['outcome_role'] == 'direct_between_group_effect'
    for context in (positive, negative):
        assert context['clinical_review']['reviewer'] == 'Dr. Pham'
        assert context['clinical_review']['reviewed_at'] == '2026-10-26'
        assert context_accepted_for_scoring(context)
        assert validate_frozen_context(context) == []
    assert derived_context_evidence(record)['effect_direction'] == 'mixed'


def test_299v_sen_null_symptom_result_cannot_invent_dose_or_supply_positive_credit():
    record = _record()
    context = next(c for c in record['study_contexts'] if c['source_pmids'] == ['12452404'])
    assert context['review_status'] == 'rejected_source'
    assert context['scoring_eligible'] is False
    assert context['dose']['values'] == []
    assert context['dose']['dosage_forms'] == []
    assert context['dose']['dose_status'] == 'extraction_pending'
    assert not context_accepted_for_scoring(context)
    assert any(o['direction'] == 'null' for o in context['outcomes'])


def test_broad_digestive_health_cannot_borrow_the_scoped_299v_ibs_contexts():
    _clinical_strain_registry.cache_clear()
    product = strain_product(dose=1e10, clinical_id='STRAIN_PLANTARUM_299V', name='Lactobacillus plantarum 299v')
    product['product_name'] = 'Digestive Health Probiotic'
    result = score_evidence(product)
    assert result['score'] == 0
    assert result['metadata']['evidence_result_state'] == 'research_present_applicability_unestablished'
