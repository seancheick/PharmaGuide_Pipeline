"""Regression lock for med–nutrient content audit BATCH 02 (2026-07-23).

10 entries, live-literature verified (every PMID PubMed-content-checked). Locked
rule from batch 01: `verified` requires EVERY user-visible field to be defensible
AND a real cited source to support the specific claim. Result: 8 verified (after
small source firm-ups), 2 needs_revision (the OCP entries — placeholder sources,
overstated depletion the modern literature contradicts, and an over-UL B6 dose).
No ghost references this batch.
"""

import json
import os

EXPECTED_STATUS = {
    "DEP_ANTICOAGULANTS_VITAMINK": "verified",
    "DEP_ORLISTAT_VITAMIND": "verified",
    "DEP_CHOLESTYRAMINE_VITAMINK": "verified",
    "DEP_SULFASALAZINE_FOLATE": "verified",
    "DEP_COLCHICINE_VITAMINB12": "verified",
    "DEP_METHOTREXATE_FOLATE": "verified",
    "DEP_ISONIAZID_VITAMINB6": "verified",
    "DEP_SSRIS_SODIUM": "verified",
    "DEP_OCP_VITAMINB6": "needs_revision",
    "DEP_OCP_FOLATE": "needs_revision",
}


def _entries():
    p = os.path.join(
        os.path.dirname(__file__), os.pardir, "data", "medication_depletions.json"
    )
    with open(p, encoding="utf-8") as f:
        return {e["id"]: e for e in json.load(f)["depletions"]}


def _urls(entry):
    return " ".join(s.get("url", "") for s in entry.get("sources", []))


def test_batch_02_statuses_assigned():
    by = _entries()
    for eid, status in EXPECTED_STATUS.items():
        assert by[eid].get("citation_review_status") == status, (
            f"{eid}: {by[eid].get('citation_review_status')!r} != {status!r}"
        )


def test_batch_02_entries_carry_review_metadata():
    by = _entries()
    for eid in EXPECTED_STATUS:
        e = by[eid]
        assert e.get("reviewed_at"), f"{eid} missing reviewed_at"
        assert e.get("reviewer"), f"{eid} missing reviewer"


def test_batch_02_ssri_placeholder_source_replaced():
    # The generic NIH ODS Sodium sheet (which says nothing about SSRI-SIADH) is
    # replaced by the real, on-topic De Picker 2014 review.
    urls = _urls(_entries()["DEP_SSRIS_SODIUM"])
    assert "/25262043/" in urls, "De Picker 2014 not cited"
    assert "Sodium-HealthProfessional" not in urls, "placeholder still present"


def test_batch_02_mtx_and_colchicine_primary_pmids_added():
    by = _entries()
    assert "/23728635/" in _urls(by["DEP_METHOTREXATE_FOLATE"]), "Cochrane not added"
    assert "/5677718/" in _urls(by["DEP_COLCHICINE_VITAMINB12"]), "Webb 1968 not added"
