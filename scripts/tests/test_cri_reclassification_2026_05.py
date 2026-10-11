#!/usr/bin/env python3
"""Keep the anabolic classification while checking dated deductions at their owner.

Warrior Labz sold unapproved SARMs and prescription drugs. Modern Therapy's
criminal proceeding involved prescription anabolic steroids, not products
marketed as supplements. Source scope and user copy must retain that distinction.
"""
import json
from copy import deepcopy
from datetime import date

from api_audit import fda_manufacturer_violations_sync as sync
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


def test_v055_modern_therapy_is_cri_anabolic(entries):
    e = _find(entries, "V055")
    assert e["manufacturer"] == "Modern Therapy", (
        "V055 manufacturer name shifted unexpectedly — "
        "verify reclassification still applies"
    )
    assert e["violation_code"] == "CRI_ANABOLIC", (
        "V055 must remain CRI_ANABOLIC (was reclassified from CRI_UNDRUG "
        "on 2026-05-14 — criminal prosecution for distributing anabolic "
        "prescription steroids)"
    )
    assert e["base_deduction"] == -18


@pytest.mark.parametrize("as_of,expected", [
    (date(2025, 5, 14), -24.0),
    (date(2026, 10, 11), -12.0),
])
def test_warrior_labz_deduction_ages_at_canonical_owner(entries, as_of, expected):
    data = {"manufacturer_violations": deepcopy(entries)}
    sync.recalculate_all_entries(data, sync.load_deduction_expl(), as_of=as_of)
    row = _find(data["manufacturer_violations"], "V054")
    assert row["violation_code"] == "CRI_ANABOLIC"
    assert row["base_deduction"] == -18
    assert row["total_deduction_applied"] == expected
    if as_of == date(2026, 10, 11):
        assert _find(data["manufacturer_violations"], "V055")["total_deduction_applied"] == -4.5


def test_stored_anabolic_deductions_match_recorded_calculation_date(entries):
    source = json.loads(DATA.read_text())
    as_of = date.fromisoformat(source["_metadata"]["calculation_date"])
    recalculated = deepcopy(source)
    sync.recalculate_all_entries(recalculated, sync.load_deduction_expl(), as_of=as_of)
    for vid in ("V054", "V055"):
        actual = _find(entries, vid)
        expected = _find(recalculated["manufacturer_violations"], vid)
        for field in ("base_deduction", "recency_multiplier", "total_deduction_applied"):
            assert actual[field] == expected[field], (vid, field)


def test_user_facing_notes_describe_event_scope_without_score_arithmetic(entries):
    for vid in ("V054", "V055"):
        row = _find(entries, vid)
        note = row["user_facing_note"]
        assert row["manufacturer"] in note
        assert row["date"] in note
        assert row["product"] in note
        assert row["reason"] in note
        assert "Affected scope:" in note
        assert "Penalty:" not in note
        assert "FDA Recall" not in note
    modern = _find(entries, "V055")
    assert "prescription" in modern["product"].lower()
    assert "this source does not describe supplements" in modern["reason"].lower()


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
