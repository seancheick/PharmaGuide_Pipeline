#!/usr/bin/env python3
"""Contract tests for `data/ban_context_vocab.json` (locked v1.0.0, 2026-05-01)."""

import json
import os
import re

import pytest

VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "ban_context_vocab.json"
)


@pytest.fixture(scope="module")
def vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def items(vocab):
    return vocab["ban_contexts"]


def test_metadata(vocab):
    md = vocab["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["total_entries"] == 5


def test_exactly_5(items):
    assert len(items) == 5


REQUIRED = {"id", "name", "notes", "when_it_applies", "action_recommendation"}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def test_required_fields(items):
    for i in items:
        assert set(i.keys()) == REQUIRED


def test_canonical_5(items):
    expected = {
        "substance", "adulterant_in_supplements", "contamination_recall",
        "watchlist", "export_restricted",
    }
    assert {i["id"] for i in items} == expected


def test_ids_unique_and_snake(items):
    ids = [i["id"] for i in items]
    assert len(set(ids)) == len(ids)
    for iid in ids:
        assert ID_PATTERN.match(iid)


def test_notes_within_char_limit(items):
    for i in items:
        assert len(i["notes"]) <= 200, f"{i['id']} notes >200"


def _walk(obj, key, found):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key and isinstance(v, str):
                found.add(v)
            _walk(v, key, found)
    elif isinstance(obj, list):
        for x in obj:
            _walk(x, key, found)


def test_every_ban_context_in_vocab(items):
    path = os.path.join(
        os.path.dirname(__file__), "..", "data", "banned_recalled_ingredients.json"
    )
    found = set()
    _walk(json.load(open(path, encoding="utf-8")), "ban_context", found)
    canonical = {
        "substance", "adulterant_in_supplements", "contamination_recall",
        "watchlist", "export_restricted",
    }
    in_use = found & canonical
    vocab_ids = {i["id"] for i in items}
    assert in_use <= vocab_ids
