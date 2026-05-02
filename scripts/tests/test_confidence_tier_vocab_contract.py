#!/usr/bin/env python3
"""Contract tests for `data/confidence_tier_vocab.json`."""

import json
import os

import pytest

VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "confidence_tier_vocab.json"
)


@pytest.fixture(scope="module")
def vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def items(vocab):
    return vocab["confidence_tiers"]


def test_metadata(vocab):
    md = vocab["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["total_entries"] == 3


def test_exactly_3(items):
    assert len(items) == 3


REQUIRED = {
    "id", "name", "short_label", "tone",
    "ui_color", "ui_icon", "action", "notes",
}
TONES = {"positive", "neutral", "info", "warning", "danger"}
COLORS = {"green", "blue", "gray", "yellow", "orange", "red"}
ICONS = {"check", "info", "warning", "alert", "block"}


def test_required(items):
    for i in items:
        assert set(i.keys()) == REQUIRED


def test_canonical_3(items):
    assert {i["id"] for i in items} == {"high", "medium", "low"}


def test_char_limits(items):
    for i in items:
        assert len(i["short_label"]) <= 12
        assert len(i["action"]) <= 40
        assert len(i["notes"]) <= 200


def test_display_enums(items):
    for i in items:
        assert i["tone"] in TONES
        assert i["ui_color"] in COLORS
        assert i["ui_icon"] in ICONS


def _walk(obj, key, found):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key and isinstance(v, str):
                found.add(v)
            _walk(v, key, found)
    elif isinstance(obj, list):
        for x in obj:
            _walk(x, key, found)


def test_every_confidence_value_in_vocab(items):
    """Cross-source: harmful_additives.confidence + clinical_studies.effect_direction_confidence."""
    vocab_ids = {i["id"] for i in items}
    for relpath, fieldname in (
        ("harmful_additives.json", "confidence"),
        ("backed_clinical_studies.json", "effect_direction_confidence"),
    ):
        path = os.path.join(os.path.dirname(__file__), "..", "data", relpath)
        if not os.path.exists(path):
            continue
        found = set()
        _walk(json.load(open(path, encoding="utf-8")), fieldname, found)
        canonical = {"high", "medium", "low"}
        in_use = found & canonical
        assert in_use <= vocab_ids, f"{relpath}.{fieldname} NOT in vocab: {in_use - vocab_ids}"
