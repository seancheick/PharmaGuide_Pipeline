#!/usr/bin/env python3
"""Pins the V054/V055 CRI_UNDRUG → CRI_ANABOLIC reclassification.

Audit performed 2026-05-14: scanned all 37 CRI_UNDRUG entries in
manufacturer_violations.json against GLP-1, anabolic, and botanical-
substitution markers. Found exactly 2 entries that warranted moving
from the generic CRI_UNDRUG (-15) to the more specific CRI_ANABOLIC
(-18):

  V054 — Warrior Labz SARMS (explicit SARMs + ED-drug spike; the
         manufacturer name itself contains "SARMS"). The CRI_ANABOLIC
         code's examples list mentions "stanozolol", "designer
         prohormone", and pre-workout SARM spikes.

  V055 — Modern Therapy (criminal prosecution for conspiracy to
         distribute controlled anabolic steroids as supplements).
         undeclared_drugs field literally reads
         "anabolic steroids (multiple)".

Score impact (per the 2026-05-14 audit, reports/cri_reclassification_2026_05_14):
  - V054 manufacturer score: 79 Acceptable → 76 Acceptable (no band change)
  - V055 manufacturer score: 96.25 Trusted → 95.5 Trusted (no band change)
  - 0 manufacturers crossed any band boundary

The remaining 35 CRI_UNDRUG entries are correctly classified — they
cover pharmaceutical adulterations that aren't anabolic or GLP-1
(ED drugs alone, NSAIDs like diclofenac, corticosteroids like
dexamethasone, weight-loss agents like sibutramine from the pre-GLP1
era, kratom-derived opioids, etc.).

This test prevents drift if a future sync run or manual edit
accidentally reverts the reclassification.
"""
import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "data" / "manufacturer_violations.json"


@pytest.fixture(scope="module")
def entries() -> list[dict]:
    with open(DATA) as f:
        return json.load(f)["manufacturer_violations"]


def _find(entries, id_):
    for e in entries:
        if e.get("id") == id_:
            return e
    raise AssertionError(f"{id_} not found in manufacturer_violations.json")


def test_v054_warrior_labz_is_cri_anabolic(entries):
    e = _find(entries, "V054")
    assert e["manufacturer"] == "Warrior Labz SARMS", (
        "V054 manufacturer name shifted unexpectedly — "
        "verify reclassification still applies"
    )
    assert e["violation_code"] == "CRI_ANABOLIC", (
        "V054 must remain CRI_ANABOLIC (was reclassified from CRI_UNDRUG "
        "on 2026-05-14 — manufacturer literally sells RAD-140, MK-677, "
        "MK-2866, LGD-4033 SARMs)"
    )
    assert e["base_deduction"] == -18, (
        "V054 base_deduction must match CRI_ANABOLIC's -18"
    )
    # (-18 + -3 unresolved + -3 multi_line) * 1.0 recency = -24
    assert e["total_deduction_applied"] == -24.0, (
        f"V054 total_deduction_applied expected -24.0, got {e['total_deduction_applied']}"
    )


def test_v055_modern_therapy_is_cri_anabolic(entries):
    e = _find(entries, "V055")
    assert e["manufacturer"] == "Modern Therapy", (
        "V055 manufacturer name shifted unexpectedly — "
        "verify reclassification still applies"
    )
    assert e["violation_code"] == "CRI_ANABOLIC", (
        "V055 must remain CRI_ANABOLIC (was reclassified from CRI_UNDRUG "
        "on 2026-05-14 — criminal prosecution for distributing anabolic "
        "steroids as supplements)"
    )
    assert e["base_deduction"] == -18
    # (-18 + 0 modifiers) * 0.25 recency = -4.5
    assert e["total_deduction_applied"] == -4.5, (
        f"V055 total_deduction_applied expected -4.5, got {e['total_deduction_applied']}"
    )


def test_user_facing_note_penalty_reflects_new_total(entries):
    """The user_facing_note ends with 'Penalty: <value> pts.' — must
    track total_deduction_applied so the Flutter card displays the
    correct number."""
    for vid, expected in (("V054", "-24.0"), ("V055", "-4.5")):
        e = _find(entries, vid)
        note = e["user_facing_note"]
        assert f"Penalty: {expected} pts." in note, (
            f"{vid} user_facing_note must end with 'Penalty: {expected} pts.', "
            f"got: ...{note[-60:]}"
        )


def test_no_other_cri_undrug_is_obviously_anabolic_or_glp1(entries):
    """Drift guard — if a future entry looks anabolic / GLP-1 but is
    coded CRI_UNDRUG, this catches it so it gets a deliberate code
    rather than silently sitting in the generic bucket.

    NOTE: this list is a small allowlist of the few terms we know
    indicate the more-specific buckets. New patterns require
    reclassification + re-running the audit, not silent allowlisting.
    """
    anabolic_markers = (
        "sarm", "anabolic steroid", "stanozolol", "trenbolone",
        "oxandrolone", "winstrol", "dianabol", "nandrolone",
        "prohormone", "ostarine", "ligandrol",
    )
    glp1_markers = (
        "semaglutide", "ozempic", "tirzepatide", "mounjaro",
        "liraglutide", "wegovy", "zepbound", "retatrutide",
    )

    for e in entries:
        if e.get("violation_code") != "CRI_UNDRUG":
            continue
        haystack = " ".join([
            e.get("reason", "") or "",
            e.get("contamination_type", "") or "",
            " ".join(e.get("undeclared_drugs") or []),
            e.get("internal_note", "") or "",
        ]).lower()
        anabolic_hits = [m for m in anabolic_markers if m in haystack]
        glp1_hits = [m for m in glp1_markers if m in haystack]
        assert not anabolic_hits, (
            f"{e.get('id')} ({e.get('manufacturer')}) is coded CRI_UNDRUG but "
            f"its text contains anabolic markers {anabolic_hits} — reclassify "
            "to CRI_ANABOLIC and re-run the audit at "
            "reports/cri_reclassification_2026_05_14/audit.json"
        )
        assert not glp1_hits, (
            f"{e.get('id')} ({e.get('manufacturer')}) is coded CRI_UNDRUG but "
            f"its text contains GLP-1 markers {glp1_hits} — reclassify "
            "to CRI_GLP1 and re-run the audit"
        )
