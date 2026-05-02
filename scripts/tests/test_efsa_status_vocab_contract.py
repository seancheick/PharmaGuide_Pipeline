#!/usr/bin/env python3
"""Contract tests for `data/efsa_status_vocab.json`."""

import json
import os
import re

import pytest

VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "efsa_status_vocab.json"
)


@pytest.fixture(scope="module")
def vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def items(vocab):
    return vocab["efsa_statuses"]


def test_metadata(vocab):
    md = vocab["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["total_entries"] == 10


def test_exactly_10(items):
    assert len(items) == 10


REQUIRED = {"id", "name", "notes"}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def test_required(items):
    for i in items:
        assert set(i.keys()) == REQUIRED


def test_canonical_10(items):
    expected = {
        "approved", "approved_with_restrictions", "approved_restricted",
        "restricted_eu", "banned_eu", "not_authorised_eu",
        "contaminant_monitored", "under_review",
        "food_ingredient", "extraction_solvent",
    }
    assert {i["id"] for i in items} == expected


def test_ids_snake(items):
    for i in items:
        assert ID_PATTERN.match(i["id"])


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


def test_every_efsa_status_in_vocab(items):
    path = os.path.join(
        os.path.dirname(__file__), "..", "data", "efsa_openfoodtox_reference.json"
    )
    if not os.path.exists(path):
        pytest.skip("efsa_openfoodtox_reference.json not present")
    found = set()
    _walk(json.load(open(path, encoding="utf-8")), "efsa_status", found)
    vocab_ids = {i["id"] for i in items}
    unknown = found - vocab_ids
    assert not unknown, f"efsa_status values NOT in vocab: {unknown}"
