#!/usr/bin/env python3
"""Contract tests for `data/legal_status_vocab.json` (locked v1.0.0, 2026-05-01)."""

import json
import os
import re

import pytest

VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "legal_status_vocab.json"
)


@pytest.fixture(scope="module")
def vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def items(vocab):
    return vocab["legal_statuses"]


def test_metadata(vocab):
    md = vocab["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["total_entries"] == 10


def test_exactly_10(items):
    assert len(items) == 10


REQUIRED = {"id", "name", "notes", "authority", "implication"}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
AUTHORITIES = {"FDA", "DEA", "WADA", "state", "EU"}


def test_required_fields(items):
    for i in items:
        assert set(i.keys()) == REQUIRED


def test_canonical_10(items):
    expected = {
        "not_lawful_as_supplement", "adulterant", "banned_federal",
        "banned_state", "controlled_substance", "wada_prohibited",
        "restricted", "high_risk", "contaminant_risk", "lawful",
    }
    assert {i["id"] for i in items} == expected


def test_ids_unique_and_snake(items):
    ids = [i["id"] for i in items]
    assert len(set(ids)) == len(ids)
    for iid in ids:
        assert ID_PATTERN.match(iid)


def test_authority_in_enum(items):
    for i in items:
        assert i["authority"] in AUTHORITIES


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


def test_every_legal_status_in_vocab(items):
    path = os.path.join(
        os.path.dirname(__file__), "..", "data", "banned_recalled_ingredients.json"
    )
    found = set()
    _walk(json.load(open(path, encoding="utf-8")), "legal_status_enum", found)
    canonical = {
        "not_lawful_as_supplement", "adulterant", "banned_federal",
        "banned_state", "controlled_substance", "wada_prohibited",
        "restricted", "high_risk", "contaminant_risk", "lawful",
    }
    in_use = found & canonical
    vocab_ids = {i["id"] for i in items}
    assert in_use <= vocab_ids
