"""Offline tests for the medication-depletion direct-drug identity gate.

Locks the 2026-07-24 hardening (Codex point 2): the 20 `type:drug` depletion
entries carry a direct rxcui the app matches by numeric id, and nothing was
live-verifying them. This gate must (a) pass a correct numeric rxcui, (b) fail a
wrong/retired one, (c) fail a non-numeric synthetic id, (d) still TRACK the
known dead `antibiotics_broadspectrum` without silently passing it, and (e) fail
a class ref that doesn't exist. `name_fn` is injected — no network.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api_audit"))

import verify_medication_depletion_identifiers as vd  # noqa: E402

CLASS_IDS = {"class:proton_pump_inhibitors"}


def _dep(eid, dtype, did, name="Furosemide (Lasix)"):
    return {"id": eid, "drug_ref": {"type": dtype, "id": did, "display_name": name}}


def test_good_numeric_drug_passes():
    deps = [_dep("E", "drug", "4603", "Furosemide (Lasix)")]
    problems, tracked, checked = vd.audit(deps, CLASS_IDS, name_fn=lambda rx: "furosemide")
    assert not problems and checked == 1


def test_wrong_drug_flagged():
    deps = [_dep("E", "drug", "4603", "Furosemide (Lasix)")]
    problems, _, _ = vd.audit(deps, CLASS_IDS, name_fn=lambda rx: "metronidazole")
    assert problems and "WRONG DRUG" in problems[0]


def test_retired_rxcui_flagged():
    deps = [_dep("E", "drug", "4603")]
    problems, _, _ = vd.audit(deps, CLASS_IDS, name_fn=lambda rx: "")
    assert problems and "no current RxNorm name" in problems[0]


def test_transient_error_fails_closed():
    deps = [_dep("E", "drug", "4603")]
    problems, _, _ = vd.audit(deps, CLASS_IDS, name_fn=lambda rx: "ERR:timeout")
    assert problems  # ERR must be a problem, never a pass


def test_non_numeric_synthetic_id_flagged():
    deps = [_dep("E", "drug", "some_made_up_id", "Whatever")]
    problems, tracked, _ = vd.audit(deps, CLASS_IDS, name_fn=lambda rx: "x")
    assert any("synthetic/dead id" in p for p in problems)
    assert not tracked


def test_dead_id_on_displayed_entry_fails():
    # A synthetic id on a DISPLAYED (unverified/verified) entry blocks the gate.
    deps = [_dep("E", "drug", "antibiotics_broadspectrum", "Broad-spectrum antibiotics")]
    problems, _, _ = vd.audit(deps, CLASS_IDS, name_fn=lambda rx: "x")
    assert any("synthetic/dead id" in p for p in problems)


def test_suppressed_entry_identity_not_enforced():
    # The SAME dead id on a needs_revision (app-hidden) entry is tracked, not failed.
    deps = [{
        "id": "E",
        "citation_review_status": "needs_revision",
        "drug_ref": {"type": "drug", "id": "antibiotics_broadspectrum", "display_name": "x"},
    }]
    problems, tracked, _ = vd.audit(deps, CLASS_IDS, name_fn=lambda rx: "x")
    assert not problems and len(tracked) == 1


def test_missing_class_ref_flagged():
    deps = [{"id": "E", "drug_ref": {"type": "class", "id": "class:does_not_exist"}}]
    problems, _, _ = vd.audit(deps, CLASS_IDS, name_fn=lambda rx: "x")
    assert problems and "not in drug_classes.json" in problems[0]


def test_valid_class_ref_passes():
    deps = [{"id": "E", "drug_ref": {"type": "class", "id": "class:proton_pump_inhibitors"}}]
    problems, _, _ = vd.audit(deps, CLASS_IDS, name_fn=lambda rx: "x")
    assert not problems


def test_name_matches_tolerates_descriptive_suffix():
    assert vd._name_matches("furosemide", "Furosemide (Lasix)")
    assert vd._name_matches("metformin", "Metformin (type 2 diabetes medication)")
    assert not vd._name_matches("metronidazole", "Furosemide (Lasix)")
