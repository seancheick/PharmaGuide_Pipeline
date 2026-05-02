#!/usr/bin/env python3
"""Contract tests for `data/clinical_risk_vocab.json` (locked v1.0.0, 2026-05-01)."""

import json
import os
import re

import pytest

VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "clinical_risk_vocab.json"
)


@pytest.fixture(scope="module")
def vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def risks(vocab):
    return vocab["clinical_risks"]


def test_metadata(vocab):
    md = vocab["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["total_entries"] == 5


def test_exactly_5(risks):
    assert len(risks) == 5


REQUIRED = {
    "id", "name", "short_label", "tone",
    "ui_color", "ui_icon", "action", "notes", "severity_weight",
}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def test_required_fields(risks):
    for r in risks:
        assert set(r.keys()) == REQUIRED


def test_canonical_5(risks):
    expected = {"critical", "high", "moderate", "dose_dependent", "low"}
    assert {r["id"] for r in risks} == expected


def test_ids_unique_and_snake(risks):
    ids = [r["id"] for r in risks]
    assert len(set(ids)) == len(ids)
    for rid in ids:
        assert ID_PATTERN.match(rid)


def test_short_label_within_char_limit(risks):
    for r in risks:
        assert len(r["short_label"]) <= 12


def test_action_within_char_limit(risks):
    for r in risks:
        assert len(r["action"]) <= 40


def test_notes_within_char_limit(risks):
    for r in risks:
        assert len(r["notes"]) <= 200


def test_severity_weight_in_range(risks):
    for r in risks:
        w = r["severity_weight"]
        assert isinstance(w, int) and 1 <= w <= 5


def _walk(obj, key, found):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key and isinstance(v, str):
                found.add(v)
            _walk(v, key, found)
    elif isinstance(obj, list):
        for x in obj:
            _walk(x, key, found)


def test_every_clinical_risk_in_vocab(risks):
    """Every distinct `clinical_risk_enum` value in source data, excluding
    metadata description strings."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "data", "banned_recalled_ingredients.json"
    )
    found = set()
    _walk(json.load(open(path, encoding="utf-8")), "clinical_risk_enum", found)
    canonical = {"critical", "high", "moderate", "dose_dependent", "low"}
    in_use = found & canonical
    vocab_ids = {r["id"] for r in risks}
    assert in_use <= vocab_ids
