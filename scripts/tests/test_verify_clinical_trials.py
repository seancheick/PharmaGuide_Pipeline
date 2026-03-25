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

