#!/usr/bin/env python3
"""Contract tests for `data/primary_outcome_vocab.json`."""

import json
import os
import re

import pytest

VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "primary_outcome_vocab.json"
)


@pytest.fixture(scope="module")
def vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def items(vocab):
    return vocab["primary_outcomes"]


def test_metadata(vocab):
    md = vocab["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["total_entries"] == 15


def test_exactly_15(items):
    assert len(items) == 15


REQUIRED = {"id", "name", "legacy_display", "notes", "related_user_goal_id"}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def test_required(items):
    for i in items:
        assert set(i.keys()) == REQUIRED


def test_ids_snake(items):
    for i in items:
        assert ID_PATTERN.match(i["id"]), f"id {i['id']!r} not snake_case"


def test_notes_within_char_limit(items):
    for i in items:
        assert len(i["notes"]) <= 200


def _walk(obj, key, found):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key and isinstance(v, str):
                found.add(v)
            _walk(v, key, found)
    elif isinstance(obj, list):
        for x in obj:
            _walk(x, key, found)


def test_legacy_display_covers_source_data(items):
    """Every distinct primary_outcome value in source data must match a vocab
    entry's legacy_display field (round-trip lookup)."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "data", "backed_clinical_studies.json"
    )
    found = set()
    _walk(json.load(open(path, encoding="utf-8")), "primary_outcome", found)
    legacy_set = {i["legacy_display"] for i in items}
    unknown = found - legacy_set
    assert not unknown, f"primary_outcome values NOT in vocab.legacy_display: {unknown}"


def test_related_user_goal_ids_are_real(items):
    """Cross-reference: every related_user_goal_id must exist in user_goals_vocab."""
    goals_path = os.path.join(
        os.path.dirname(__file__), "..", "data", "user_goals_vocab.json"
    )
    if not os.path.exists(goals_path):
        pytest.skip("user_goals_vocab.json not present")
    goal_ids = {g["id"] for g in json.load(open(goals_path))["user_goals"]}
    for i in items:
        gid = i.get("related_user_goal_id")
        if gid:
            assert gid in goal_ids, f"{i['id']} references {gid} not in user_goals_vocab"
