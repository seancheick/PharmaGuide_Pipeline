#!/usr/bin/env python3
"""Tests for EFSA validation logic."""

import os
import sys
from datetime import datetime, timezone
from unittest.mock import patch


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_validate_harmful_additives_uses_runtime_year_for_stale_opinion_check():
    from api_audit.verify_efsa import validate_harmful_additives

    data = {
        "harmful_additives": [
            {
                "id": "ADD_TEST",
                "standard_name": "Test Additive",
                "aliases": ["E999"],
                "regulatory_status": {"EU": "E999 approved with ADI of 1 mg/kg body weight/day (EFSA 2018)"},
                "notes": "Test note",
                "mechanism_of_harm": "Test mechanism",
            }
        ]
    }
    lookup = {
        "test additive": {
            "_ref_name": "Test Additive",
            "efsa_opinion_year": 2018,
            "efsa_adi_mg_kg_bw": 1.0,
            "efsa_adi_source": "EFSA Journal 2018",
        }
    }

    class FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2030, 1, 1, tzinfo=UTC)

    with patch("api_audit.verify_efsa.datetime", FakeDateTime):
        results = validate_harmful_additives(data, lookup)

    assert len(results["stale_opinion"]) == 1
    assert results["stale_opinion"][0]["years_old"] == 12

