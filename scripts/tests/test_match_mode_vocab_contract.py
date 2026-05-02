#!/usr/bin/env python3
"""Contract tests for `data/match_mode_vocab.json`."""

import json
import os

import pytest

VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "match_mode_vocab.json"
)


@pytest.fixture(scope="module")
def vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def items(vocab):
    return vocab["match_modes"]


def test_metadata(vocab):
    md = vocab["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["total_entries"] == 3


def test_exactly_3(items):
    assert len(items) == 3


REQUIRED = {"id", "name", "notes", "fires_in_scoring"}


def test_required(items):
    for i in items:
        assert set(i.keys()) == REQUIRED


def test_canonical_3(items):
    assert {i["id"] for i in items} == {"active", "disabled", "historical"}


def test_fires_in_scoring_bool(items):
    for i in items:
        assert isinstance(i["fires_in_scoring"], bool)


def test_active_fires_others_dont(items):
    by_id = {i["id"]: i for i in items}
    assert by_id["active"]["fires_in_scoring"] is True
    assert by_id["disabled"]["fires_in_scoring"] is False
    assert by_id["historical"]["fires_in_scoring"] is False


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


def test_every_match_mode_in_vocab(items):
    path = os.path.join(
        os.path.dirname(__file__), "..", "data", "banned_recalled_ingredients.json"
    )
    found = set()
    _walk(json.load(open(path, encoding="utf-8")), "match_mode", found)
    canonical = {"active", "disabled", "historical"}
    in_use = found & canonical
    vocab_ids = {i["id"] for i in items}
    assert in_use <= vocab_ids
