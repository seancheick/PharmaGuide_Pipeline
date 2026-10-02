"""Inulin-family source scope and identity; numerical calibration stays separate."""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / 'data' / 'backed_clinical_studies.json'


def entry():
    return next(e for e in json.loads(DATA.read_text())['backed_clinical_studies'] if e['id'] == 'INGR_INULIN')


def test_generic_prebiotic_fiber_does_not_identify_inulin():
    from enrich_supplements_v3 import SupplementEnricherV3
    enricher = SupplementEnricherV3.__new__(SupplementEnricherV3)
    e = entry()
    assert enricher._clinical_study_match(['prebiotic fiber'], e) is None
    for name in ['inulin', 'chicory root fiber', 'FOS']:
        assert enricher._clinical_study_match([name], e) is not None


def test_inulin_digestive_claims_do_not_borrow_discovery_endpoint_tags():
    e = entry()
    assert e['endpoint_relevance_tags'] == ['digestive_health']
    assert 'muscle_recovery' not in e['effect_direction_rationale']
    assert 'stress_mood' not in e['effect_direction_rationale']
    assert 'not re-ratified' in e['effect_direction_rationale']


def test_inulin_sample_size_is_not_unverified_registry_discovery():
    e = entry()
    assert 'total_enrollment' not in e
    assert 'registry_completed_trials_count' not in e
    assert 'overlap' in e['notes'].lower()


def test_inulin_references_bound_preparation_population_and_null_outcomes():
    e = entry()
    refs = {r['pmid']: set(r['supports_claims']) for r in e['references_structured']}
    assert {'chicory_itf_bifidobacterium_surrogate', 'healthy_subject_bowel_function', 'not_gi_disorder_bifidogenic_benefit'} <= refs['35833477']
    assert {'healthy_adult_itf_review', 'mixed_laxation_and_calcium_results', 'preparation_and_chain_length_limitations'} <= refs['34555168']
    assert {'low_or_very_low_certainty_cardiometabolic_risk_factors', 'not_cardiovascular_event_reduction'} <= refs['38309832']
    assert 'General Mills' in e['notes']
    assert 'calcium absorption ↑' not in e['key_endpoints']
