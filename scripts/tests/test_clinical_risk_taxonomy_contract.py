"""Metadata contract for `clinical_risk_taxonomy.json`.

This file is the canonical taxonomy for interaction-rule processing in
``enrich_supplements_v3._collect_interaction_profile``. It carries 7
top-level arrays — each enumerates a distinct dimension of the
interaction model:

* ``conditions`` — recognized medical conditions (hypertension, kidney_disease, …)
* ``drug_classes`` — recognized drug class buckets (anticoagulants, statins, …)
* ``severity_levels`` — severity scale (contraindicated → info)
* ``evidence_levels`` — evidence quality (established → no_data)
* ``profile_flags`` — user-profile flags (pregnant, lactating, …)
* ``product_forms`` — supplement forms (capsule, softgel, …)
* ``sources`` — citation source IDs (DailyMed, NCCIH, …)

Convention (UNIQUE among the multi-array files):
    ``_metadata.total_entries`` = SUM of all 7 arrays. This file uses a
    sum convention because each array contributes equally to the taxonomy
    — no single array is "primary".

If you add an entry to ANY array, bump ``total_entries`` by 1.
"""

import json
from pathlib import Path
import re

import pytest

PATH = Path(__file__).parent.parent / "data" / "clinical_risk_taxonomy.json"
DATA_DIR = PATH.parent

REQUIRED_ARRAYS = (
    "conditions",
    "drug_classes",
    "severity_levels",
    "evidence_levels",
    "profile_flags",
    "product_forms",
    "sources",
)


@pytest.fixture(scope="module")
def blob():
    return json.loads(PATH.read_text(encoding="utf-8"))


def test_total_entries_is_sum_of_all_taxonomy_arrays(blob):
    expected = sum(
        len(v) for k, v in blob.items() if k != "_metadata" and isinstance(v, list)
    )
    actual = blob["_metadata"]["total_entries"]
    assert actual == expected, (
        f"_metadata.total_entries={actual} but sum of all 7 taxonomy "
        f"arrays = {expected}. Bump total_entries to {expected}."
    )


def test_all_seven_taxonomy_arrays_present(blob):
    """Defensive: ``_collect_interaction_profile`` reads each of these by
    name. If any disappears, the interaction engine loses a dimension."""
    missing = [a for a in REQUIRED_ARRAYS if a not in blob]
    assert not missing, f"required taxonomy arrays missing: {missing}"
    for a in REQUIRED_ARRAYS:
        assert isinstance(blob[a], list), f"{a!r} must be a list"
        assert blob[a], f"{a!r} cannot be empty"


def test_serotonergic_medications_drug_class_is_taxonomy_backed(blob):
    """5-HTP cannot safely broaden beyond SSRI/SNRI + MAOI unless the
    profile-gate vocabulary has a real class for other serotonergic drugs."""
    drug_classes = {entry["id"]: entry for entry in blob["drug_classes"]}
    entry = drug_classes.get("serotonergic_medications")
    assert entry is not None
    assert entry["category"] == "psychiatry"
    assert "Serotonergic" in entry["label"]


def test_conditions_are_the_complete_user_profile_contract(blob):
    conditions = blob["conditions"]
    assert len(conditions) == 15
    assert all(condition.get("user_selectable") is True for condition in conditions)

    ids = [condition["id"] for condition in conditions]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"[a-z][a-z0-9_]*", condition_id) for condition_id in ids)

    priorities = [condition["display_priority"] for condition in conditions]
    assert priorities == sorted(priorities)
    assert len(priorities) == len(set(priorities))

    for condition in conditions:
        assert condition["label"].strip()
        assert condition["description"].strip()
        assert len(condition["description"]) <= 200
        assert all(item.strip() for item in condition.get("synonyms", []))
        for reference in condition.get("icd10", []):
            assert reference["code"].strip()
            assert reference["description"].strip()


def _collect_profile_flag_references(value, found):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"profile_flags_any", "profile_flags_all"} and isinstance(
                item, list
            ):
                found.update(flag for flag in item if isinstance(flag, str))
            _collect_profile_flag_references(item, found)
    elif isinstance(value, list):
        for item in value:
            _collect_profile_flag_references(item, found)


def _collect_condition_references(value, found):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "condition_id" and isinstance(item, str):
                found.add(item)
            elif key in {"conditions_any", "conditions_all"} and isinstance(
                item, list
            ):
                found.update(
                    condition for condition in item if isinstance(condition, str)
                )
            _collect_condition_references(item, found)
    elif isinstance(value, list):
        for item in value:
            _collect_condition_references(item, found)


def _active_rule_payloads():
    for filename in (
        "ingredient_interaction_rules.json",
        "medication_profile_gate_rules.json",
    ):
        yield json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))


def test_every_selectable_condition_has_an_active_rule_consumer(blob):
    conditions = {entry["id"] for entry in blob["conditions"]}
    active_references = set()
    for payload in _active_rule_payloads():
        _collect_condition_references(payload, active_references)

    assert active_references == conditions, (
        "selectable condition/rule reachability drift: "
        f"unused={sorted(conditions - active_references)}, "
        f"unknown={sorted(active_references - conditions)}"
    )


def test_profile_capture_modes_keep_every_active_rule_reachable(blob):
    conditions = {entry["id"] for entry in blob["conditions"]}
    flags = {entry["id"]: entry for entry in blob["profile_flags"]}
    allowed_modes = {"derived_from_condition", "user_selectable", "reserved"}

    active_references = set()
    for payload in _active_rule_payloads():
        _collect_profile_flag_references(payload, active_references)

    for flag_id, entry in flags.items():
        mode = entry.get("capture_mode")
        assert mode in allowed_modes, f"{flag_id}: invalid capture_mode={mode!r}"
        source_condition_id = entry.get("source_condition_id")
        if mode == "derived_from_condition":
            assert source_condition_id in conditions, (
                f"{flag_id}: derived flag needs a real source_condition_id"
            )
        else:
            assert source_condition_id is None, (
                f"{flag_id}: only derived flags may declare source_condition_id"
            )

    missing = active_references - flags.keys()
    assert not missing, f"active rules reference unknown profile flags: {sorted(missing)}"

    unreachable = {
        flag_id
        for flag_id in active_references
        if flags[flag_id]["capture_mode"] == "reserved"
    }
    assert not unreachable, (
        "active rules reference reserved, non-capturable profile flags: "
        f"{sorted(unreachable)}"
    )

    stale_selectable = {
        flag_id
        for flag_id, entry in flags.items()
        if entry["capture_mode"] == "user_selectable"
        and flag_id not in active_references
    }
    assert not stale_selectable, (
        "user-selectable profile flags have no active rule consumer: "
        f"{sorted(stale_selectable)}"
    )
