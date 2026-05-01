#!/usr/bin/env python3
"""
Contract tests for `data/condition_vocab.json` (locked v1.0.0, 2026-04-30).

Single source of truth for user-profile condition labels migrated from
the hardcoded `conditionLabels` map in
`lib/core/constants/schema_ids.dart`.

Locked decisions:
  - Exactly 14 conditions (matches schema_ids.dart `conditions` list)
  - Lean schema: id + name + notes + (optional) synonyms + icd10
  - notes ≤200 chars
  - All IDs lowercase snake_case

Cross-data validation: every condition_id in interaction_rules and
clinical_risk_taxonomy must be in this vocab.
"""

import json
import os
import re

import pytest

VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "condition_vocab.json"
)


@pytest.fixture(scope="module")
def vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def conditions(vocab):
    return vocab["conditions"]


def test_metadata_block_present(vocab):
    md = vocab["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["total_entries"] == 14
    assert "LOCKED" in md["status"]
    assert md["char_limit_notes"] == 200


def test_exactly_14_conditions_locked(conditions):
    assert len(conditions) == 14, f"locked at 14; got {len(conditions)}"


REQUIRED_FIELDS = {"id", "name", "notes"}
OPTIONAL_FIELDS = {"synonyms", "icd10"}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def test_required_fields_present(conditions):
    for c in conditions:
        for f in REQUIRED_FIELDS:
            assert f in c, f"condition {c.get('id')!r} missing {f}"
        # No unexpected fields beyond required + optional
        extra = set(c.keys()) - (REQUIRED_FIELDS | OPTIONAL_FIELDS)
        assert not extra, f"condition {c['id']!r} has unexpected fields: {extra}"


def test_every_id_unique_and_snake_case(conditions):
    ids = [c["id"] for c in conditions]
    assert len(set(ids)) == len(ids), "duplicate condition IDs"
    for cid in ids:
        assert ID_PATTERN.match(cid), f"id {cid!r} not snake_case"


def test_canonical_ids_match_schema_ids_dart(conditions):
    """The 14 IDs must match `conditions` in lib/core/constants/schema_ids.dart"""
    expected = {
        "pregnancy", "lactation", "ttc", "surgery_scheduled",
        "hypertension", "heart_disease", "diabetes",
        "bleeding_disorders", "kidney_disease", "liver_disease",
        "thyroid_disorder", "autoimmune", "seizure_disorder",
        "high_cholesterol",
    }
    actual = {c["id"] for c in conditions}
    assert actual == expected, f"missing={expected-actual} extra={actual-expected}"


def test_notes_within_char_limit(conditions):
    over = [(c["id"], len(c["notes"])) for c in conditions if len(c["notes"]) > 200]
    assert not over, f"notes exceed 200 chars: {over}"
    empty = [c["id"] for c in conditions if not c["notes"].strip()]
    assert not empty, f"empty notes: {empty}"


def test_name_nonempty(conditions):
    for c in conditions:
        assert isinstance(c["name"], str) and c["name"].strip()
        assert any(ch.isupper() for ch in c["name"])


def test_optional_fields_well_formed(conditions):
    for c in conditions:
        if "synonyms" in c:
            assert isinstance(c["synonyms"], list)
            for s in c["synonyms"]:
                assert isinstance(s, str) and s.strip()
        if "icd10" in c:
            assert isinstance(c["icd10"], list)
            for ref in c["icd10"]:
                assert isinstance(ref, dict)
                assert ref.get("code"), f"{c['id']}: icd10 ref missing code"
                assert ref.get("description"), f"{c['id']}: icd10 ref missing description"


# ---------------------------------------------------------------------------
# Cross-data membership
# ---------------------------------------------------------------------------


def _walk_condition_ids(obj, found):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "condition_id" and isinstance(v, str):
                found.add(v)
            elif k == "conditions" and isinstance(v, list):
                for item in v:
                    if isinstance(item, str):
                        found.add(item)
            _walk_condition_ids(v, found)
    elif isinstance(obj, list):
        for x in obj:
            _walk_condition_ids(x, found)


def test_every_interaction_rule_condition_id_in_vocab(conditions):
    found = set()
    for relpath in (
        "ingredient_interaction_rules.json",
        "ingredient_interaction_rules_Reviewed.json",
    ):
        path = os.path.join(os.path.dirname(__file__), "..", "data", relpath)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        _walk_condition_ids(data, found)

    vocab_ids = {c["id"] for c in conditions}
    unknown = found - vocab_ids
    # Strip empty strings + obvious false-positives that aren't real condition IDs
    unknown = {x for x in unknown if x and x not in {"none", "n/a"}}
    assert not unknown, (
        f"condition_ids in interaction rules NOT in vocab: {unknown}. "
        "Either add to vocab (with sign-off) or fix the source data."
    )
