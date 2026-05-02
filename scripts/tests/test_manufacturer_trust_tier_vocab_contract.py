#!/usr/bin/env python3
"""Contract tests for `data/manufacturer_trust_tier_vocab.json`."""

import json
import os
import re

import pytest

VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "manufacturer_trust_tier_vocab.json"
)


@pytest.fixture(scope="module")
def vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def items(vocab):
    return vocab["manufacturer_trust_tiers"]


def test_metadata(vocab):
    md = vocab["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["total_entries"] == 4


def test_exactly_4(items):
    assert len(items) == 4


REQUIRED = {
    "id", "name", "short_label", "tone",
    "ui_color", "ui_icon", "action", "notes", "derivation_rule",
}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
TONES = {"positive", "neutral", "info", "warning", "danger"}
COLORS = {"green", "blue", "gray", "yellow", "orange", "red"}
ICONS = {"check", "info", "warning", "alert", "block"}


def test_required(items):
    for i in items:
        assert set(i.keys()) == REQUIRED


def test_canonical_4(items):
    expected = {"trusted", "neutral", "violations_minor", "violations_critical"}
    assert {i["id"] for i in items} == expected


def test_ids_snake(items):
    for i in items:
        assert ID_PATTERN.match(i["id"])


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
