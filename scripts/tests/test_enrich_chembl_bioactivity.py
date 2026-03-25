#!/usr/bin/env python3
"""Tests for ChEMBL enrichment review behavior."""

import os
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_enrich_banned_recalled_flags_unknown_mechanism_claim_when_chembl_has_one():
    from api_audit.enrich_chembl_bioactivity import enrich_banned_recalled

    class FakeClient:
        _request_count = 2

        def search_molecule(self, name):
            assert name == "Sildenafil"
            return {
                "molecule_chembl_id": "CHEMBL192",
                "pref_name": "SILDENAFIL",
                "molecule_type": "Small molecule",
                "max_phase": 4,
                "first_approval": 1998,
                "indication_class": None,
                "molecule_properties": {},
            }

        def get_mechanism(self, chembl_id):
            assert chembl_id == "CHEMBL192"
            return [{
                "mechanism_of_action": "Phosphodiesterase 5 inhibitor",
                "action_type": "INHIBITOR",
                "target_chembl_id": "CHEMBL1827",
                "direct_interaction": True,
            }]

        def get_target(self, target_chembl_id):
            assert target_chembl_id == "CHEMBL1827"
            return {"pref_name": "Phosphodiesterase 5A", "target_type": "SINGLE PROTEIN"}

        def get_top_bioactivity(self, chembl_id, limit=10):
            return []

    data = {
        "ingredients": [
            {
                "id": "ADULTERANT_SILDENAFIL",
                "standard_name": "Sildenafil",
                "source_category": "pharmaceutical_contaminant",
                "notes": "Exact mechanism unknown in supplements, but risk is high.",
                "aliases": [],
            }
        ]
    }

    results = enrich_banned_recalled(data, FakeClient(), apply=False)

    assert len(results["claim_review_needed"]) == 1
    assert "mechanism is unknown" in results["claim_review_needed"][0]["issues"][0]["detail"].lower()

