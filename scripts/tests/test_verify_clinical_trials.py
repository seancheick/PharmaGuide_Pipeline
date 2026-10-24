#!/usr/bin/env python3
"""Tests for ClinicalTrials.gov verification behavior."""

import os
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_get_study_preserves_not_found_sentinel():
    from api_audit.verify_clinical_trials import ClinicalTrialsClient

    class FakeClient(ClinicalTrialsClient):
        def __init__(self):
            super().__init__(cache_path=None)

        def _get(self, url):
            assert url.endswith("/NCT00000000")
            return {"_not_found": True}

    client = FakeClient()

    assert client.get_study("NCT00000000") == {"_not_found": True}


def test_verify_clinical_file_classifies_not_found_nct_as_broken():
    from api_audit.verify_clinical_trials import verify_clinical_file

    class FakeClient:
        _request_count = 1

        def get_study(self, nct_id):
            assert nct_id == "NCT00000000"
            return {"_not_found": True}

    data = {
        "backed_clinical_studies": [
            {
                "id": "TEST_ENTRY",
                "standard_name": "Example",
                "study_type": "rct_single",
                "notable_studies": "Pilot study registered as NCT00000000",
            }
        ]
    }

    results = verify_clinical_file(data, FakeClient())

    assert results["broken_nct"] == [
        {"id": "TEST_ENTRY", "name": "Example", "nct_id": "NCT00000000"}
    ]
    assert results["errors"] == []



def test_native_context_registration_is_discovered():
    from api_audit.verify_clinical_trials import extract_nct_ids
    assert extract_nct_ids({'study_contexts': [
        {'trial_registration': 'NCT02974894'},
        {'trial_registration': 'https://clinicaltrials.gov/study/NCT01773967'},
        {'trial_registration': None}]}) == {'NCT02974894', 'NCT01773967'}


def test_trial_report_retains_protocol_and_results_without_approval():
    from api_audit.verify_clinical_trials import verify_clinical_file
    class Client:
        _request_count = 1
        def get_study(self, nct):
            return {'protocolSection': {
                'identificationModule': {'nctId': nct, 'briefTitle': 'Example'},
                'armsInterventionsModule': {'interventions': [{'name': 'exact preparation'}]},
                'outcomesModule': {'primaryOutcomes': [{'measure': 'symptom change'}]},
                'eligibilityModule': {'eligibilityCriteria': 'Adults'}},
                'resultsSection': {'outcomeMeasuresModule': {'outcomeMeasures': []}}}
    result = verify_clinical_file({'backed_clinical_studies': [
        {'id': 'EXAMPLE', 'notes': 'NCT00000001'}]}, Client())
    record = result['verified'][0]
    assert record['protocol']['armsInterventionsModule']['interventions'][0]['name'] == 'exact preparation'
    assert record['protocol']['outcomesModule']['primaryOutcomes'][0]['measure'] == 'symptom change'
    assert record['posted_results'] is not None
    assert record['clinical_applicability_verified'] is False
