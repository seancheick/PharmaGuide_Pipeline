#!/usr/bin/env python3
"""Contract tests for `data/allergen_regulatory_status_vocab.json`."""

import json
import os

import pytest

VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "allergen_regulatory_status_vocab.json"
)


@pytest.fixture(scope="module")
def vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def items(vocab):
    return vocab["allergen_regulatory_statuses"]


def test_metadata(vocab):
    md = vocab["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["total_entries"] == 3


def test_exactly_3(items):
    assert len(items) == 3


def test_canonical_3(items):
    assert {i["id"] for i in items} == {"fda_major", "eu_major", "eu_allergen"}


REQUIRED = {"id", "name", "notes", "authority"}


def test_required(items):
    for i in items:
        assert set(i.keys()) == REQUIRED


def test_authority_enum(items):
    for i in items:
        assert i["authority"] in {"FDA", "EU"}


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


def test_every_regulatory_status_in_vocab(items):
    path = os.path.join(
        os.path.dirname(__file__), "..", "data", "allergens.json"
    )
    found = set()
    _walk(json.load(open(path, encoding="utf-8")), "regulatory_status", found)
    canonical = {"fda_major", "eu_major", "eu_allergen"}
    in_use = found & canonical
    vocab_ids = {i["id"] for i in items}
    assert in_use <= vocab_ids
