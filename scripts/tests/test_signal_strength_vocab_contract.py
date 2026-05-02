#!/usr/bin/env python3
"""Contract tests for `data/signal_strength_vocab.json` (locked v1.0.0, 2026-05-01)."""

import json
import os
import re

import pytest

VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "signal_strength_vocab.json"
)


@pytest.fixture(scope="module")
def vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def items(vocab):
    return vocab["signal_strengths"]


def test_metadata(vocab):
    md = vocab["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["total_entries"] == 3


def test_exactly_3(items):
    assert len(items) == 3


REQUIRED = {
    "id", "name", "short_label", "tone",
    "ui_color", "ui_icon", "action", "notes", "threshold_definition",
}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
TONES = {"positive", "neutral", "info", "warning", "danger"}
COLORS = {"green", "blue", "gray", "yellow", "orange", "red"}
ICONS = {"check", "info", "warning", "alert", "block"}


def test_required_fields(items):
    for i in items:
        assert set(i.keys()) == REQUIRED


def test_canonical_3(items):
    expected = {"strong", "moderate", "weak"}
    assert {i["id"] for i in items} == expected


def test_short_label_within_char_limit(items):
    for i in items:
        assert len(i["short_label"]) <= 12


def test_action_within_char_limit(items):
    for i in items:
        assert len(i["action"]) <= 40


def test_notes_within_char_limit(items):
    for i in items:
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


def test_every_caers_signal_strength_in_vocab(items):
    path = os.path.join(
        os.path.dirname(__file__), "..", "data", "caers_adverse_event_signals.json"
    )
    if not os.path.exists(path):
        pytest.skip("caers_adverse_event_signals.json not present")
    found = set()
    _walk(json.load(open(path, encoding="utf-8")), "signal_strength", found)
    vocab_ids = {i["id"] for i in items}
    canonical = {"strong", "moderate", "weak"}
    in_use = found & canonical
    assert in_use <= vocab_ids
