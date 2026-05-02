#!/usr/bin/env python3
"""Contract tests for `data/allergen_prevalence_vocab.json` (locked v1.0.0, 2026-05-01)."""

import json
import os

import pytest

VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "allergen_prevalence_vocab.json"
)


@pytest.fixture(scope="module")
def vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def items(vocab):
    return vocab["allergen_prevalences"]


def test_metadata(vocab):
    md = vocab["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["total_entries"] == 3


def test_exactly_3(items):
    assert len(items) == 3


REQUIRED_CORE = {"id", "name", "short_label", "tone", "ui_color", "ui_icon", "action", "notes"}
TONES = {"positive", "neutral", "info", "warning", "danger"}
COLORS = {"green", "blue", "gray", "yellow", "orange", "red"}
ICONS = {"check", "info", "warning", "alert", "block"}


def test_canonical_3(items):
    assert {i["id"] for i in items} == {"high", "moderate", "low"}


def test_required_display_contract(items):
    for i in items:
        for f in REQUIRED_CORE:
            assert f in i, f"{i.get('id')!r} missing {f}"
            assert isinstance(i[f], str) and i[f].strip()


def test_display_enums(items):
    for i in items:
        assert i["tone"] in TONES
        assert i["ui_color"] in COLORS
        assert i["ui_icon"] in ICONS


def test_char_limits(items):
    for i in items:
        assert len(i["short_label"]) <= 12
        assert len(i["action"]) <= 40
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


def test_every_prevalence_in_vocab(items):
    path = os.path.join(
        os.path.dirname(__file__), "..", "data", "allergens.json"
    )
    found = set()
    _walk(json.load(open(path, encoding="utf-8")), "prevalence", found)
    canonical = {"high", "moderate", "low"}
    in_use = found & canonical
    vocab_ids = {i["id"] for i in items}
    assert in_use <= vocab_ids
