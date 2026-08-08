"""Regression lock for med–nutrient content audit BATCH 01 (2026-07-23).

Pins the per-entry citation_review_status assigned after live-literature content
verification (research in scripts/audits/batch_01/research.md), and asserts the
two PubMed-confirmed GHOST references were removed from their entries. 4 verified,
7 needs_revision, 0 rejected. Every relationship is clinically real; the 7 defects
are scope/mechanism/citation, not false claims — so they are needs_revision
(SUPPRESSED by the B1.2 publication rule until fixed), never rejected.
"""

import json
import os

EXPECTED_STATUS = {
    "DEP_METFORMIN_VITAMINB12": "verified",
    # statins→CoQ10 + corticosteroids→calcium: relationship holds but the
    # user-visible copy overstates (supplementation framing / universal above-ACR
    # dosing) → needs_revision until the copy is rewritten (2nd-opinion review).
    # Advanced by fix_sprint_02 (see test_med_nutrient_fix_sprint_02.py):
    # statins→CoQ10 copy rewritten, corticosteroids→Ca scoped to prolonged
    # systemic use, corticosteroids→vitD retyped to monitoring_stability.
    "DEP_STATINS_COQ10": "verified",
    "DEP_CORTICOSTEROIDS_CALCIUM": "verified",
    "DEP_CORTICOSTEROIDS_VITAMIND": "verified",
    # Still suppressed — these need the app-side drug-class resolver (Sprint 3).
    "DEP_ANTACIDS_VITAMINB12": "needs_revision",
    "DEP_ANTACIDS_MAGNESIUM": "needs_revision",
    "DEP_DIURETICS_POTASSIUM": "needs_revision",
    "DEP_DIURETICS_MAGNESIUM": "needs_revision",
    # Advanced by Section 3 after live content verification, but only at the
    # direct carbamazepine scope supported by the meta-analysis.
    "DEP_ANTICONVULSANTS_VITAMIND": "verified",
    # Both levothyroxine interactions were advanced to verified by fix_sprint_01
    # (see test_med_nutrient_fix_sprint_01.py): overstated magnitudes corrected,
    # tangents trimmed, iron placeholder → Campbell 1992 controlled trial.
    "DEP_LEVOTHYROXINE_CALCIUM": "verified",
    "DEP_LEVOTHYROXINE_IRON": "verified",
}

# PubMed-confirmed ghost references (title ≠ the label they were cited under):
#   19174283 = "Treatment of calf diarrhea: oral fluid therapy" (cited as Haugen)
#   3003511  = "Aspartate kinases I,II,III from E. coli" (cited as Altura, Magnesium)
GHOST_PMIDS = {"19174283", "3003511"}


def _entries():
    p = os.path.join(
        os.path.dirname(__file__), os.pardir, "data", "medication_depletions.json"
    )
    with open(p, encoding="utf-8") as f:
        return {e["id"]: e for e in json.load(f)["depletions"]}


def test_batch_01_statuses_assigned():
    by = _entries()
    for eid, status in EXPECTED_STATUS.items():
        assert by[eid].get("citation_review_status") == status, (
            f"{eid}: {by[eid].get('citation_review_status')!r} != {status!r}"
        )


def test_batch_01_entries_carry_review_metadata():
    by = _entries()
    for eid in EXPECTED_STATUS:
        e = by[eid]
        assert e.get("reviewed_at"), f"{eid} missing reviewed_at"
        assert e.get("reviewer"), f"{eid} missing reviewer"


def test_batch_01_metformin_copy_softened():
    # Superseded by the final B1 clinical sign-off: current ADA/MHRA guidance
    # is risk- and duration-based and does not support a universal prevalence
    # estimate or a prescribed methylcobalamin regimen in consumer copy.
    entry = _entries()["DEP_METFORMIN_VITAMINB12"]
    assert "multifactorial" in entry["mechanism"].lower()
    # Batch-01's softened recommendation is parked pending a B1 delta
    # re-review; until the sign-off ledger is re-pinned, the approved
    # "4–5 years" copy stays exact. The watch-block removal stands.
    assert "4–5 years" in entry["recommendation"]
    assert "watch_threshold_days" not in entry
    assert "sublingual methylcobalamin" not in entry["recommendation"].lower()
    assert "6-30%" not in entry["clinical_impact"]


def test_batch_01_no_confirmed_ghost_pmids_remain():
    by = _entries()
    for eid, e in by.items():
        urls = " ".join(s.get("url", "") for s in e.get("sources", []))
        for ghost in GHOST_PMIDS:
            assert f"/{ghost}/" not in urls, (
                f"{eid} still cites confirmed ghost PMID {ghost}"
            )
