#!/usr/bin/env python3
"""Contract tests for `data/efsa_genotoxicity_vocab.json`."""

import json
import os

import pytest

VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "efsa_genotoxicity_vocab.json"
)


@pytest.fixture(scope="module")
def vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def items(vocab):
    return vocab["genotoxicity_classifications"]


def test_metadata(vocab):
    md = vocab["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["total_entries"] == 7


def test_exactly_7(items):
    assert len(items) == 7


REQUIRED = {"id", "name", "notes"}


def test_required(items):
    for i in items:
        assert set(i.keys()) == REQUIRED


def test_canonical_7(items):
    expected = {
        "negative", "positive", "equivocal", "insufficient_data",
        "indirect", "cannot_be_excluded", "under_review",
    }
    assert {i["id"] for i in items} == expected


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


def test_every_genotoxicity_in_vocab(items):
    path = os.path.join(
        os.path.dirname(__file__), "..", "data", "efsa_openfoodtox_reference.json"
    )
    if not os.path.exists(path):
        pytest.skip("efsa_openfoodtox_reference.json not present")
    found = set()
    _walk(json.load(open(path, encoding="utf-8")), "genotoxicity", found)
    vocab_ids = {i["id"] for i in items}
    unknown = found - vocab_ids
    assert not unknown, f"genotoxicity values NOT in vocab: {unknown}"
