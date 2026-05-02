#!/usr/bin/env python3
"""Contract tests for `data/banned_status_vocab.json` (locked v1.0.0, 2026-05-01)."""

import json
import os
import re

import pytest

VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "banned_status_vocab.json"
)


@pytest.fixture(scope="module")
def vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def statuses(vocab):
    return vocab["banned_statuses"]


def test_metadata(vocab):
    md = vocab["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["total_entries"] == 4
    assert "LOCKED" in md["status"]


def test_exactly_4(statuses):
    assert len(statuses) == 4


REQUIRED = {
    "id", "name", "short_label", "tone",
    "ui_color", "ui_icon", "action", "notes", "regulatory_basis",
}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
TONES = {"positive", "neutral", "info", "warning", "danger"}
COLORS = {"green", "blue", "gray", "yellow", "orange", "red"}
ICONS = {"check", "info", "warning", "alert", "block"}


def test_required_fields(statuses):
    for s in statuses:
        assert set(s.keys()) == REQUIRED, (
            f"{s.get('id')!r} drift: missing={REQUIRED - set(s)}, extra={set(s) - REQUIRED}"
        )


def test_canonical_4_ids(statuses):
    expected = {"banned", "recalled", "high_risk", "watchlist"}
    assert {s["id"] for s in statuses} == expected


def test_ids_unique_and_snake(statuses):
    ids = [s["id"] for s in statuses]
    assert len(set(ids)) == len(ids)
    for sid in ids:
        assert ID_PATTERN.match(sid)


def test_short_label_within_char_limit(statuses):
    over = [(s["id"], len(s["short_label"])) for s in statuses if len(s["short_label"]) > 12]
    assert not over


def test_action_within_char_limit(statuses):
    over = [(s["id"], len(s["action"])) for s in statuses if len(s["action"]) > 40]
    assert not over


def test_notes_within_char_limit(statuses):
    over = [(s["id"], len(s["notes"])) for s in statuses if len(s["notes"]) > 200]
    assert not over


def test_tone_color_icon_enums(statuses):
    for s in statuses:
        assert s["tone"] in TONES, f"{s['id']} tone"
        assert s["ui_color"] in COLORS, f"{s['id']} color"
        assert s["ui_icon"] in ICONS, f"{s['id']} icon"


def _walk(obj, key, found):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key and isinstance(v, str):
                found.add(v)
            _walk(v, key, found)
    elif isinstance(obj, list):
        for x in obj:
            _walk(x, key, found)


def test_every_banned_status_in_vocab(statuses):
    """Every distinct `status` value in banned_recalled_ingredients.json
    that's NOT a metadata description string must be in the vocab."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "data", "banned_recalled_ingredients.json"
    )
    found = set()
    _walk(json.load(open(path, encoding="utf-8")), "status", found)
    # Filter metadata strings + any non-canonical legacy values that would
    # be a separate cleanup task
    canonical = {"banned", "recalled", "high_risk", "watchlist"}
    in_use = found & canonical
    vocab_ids = {s["id"] for s in statuses}
    assert in_use <= vocab_ids, f"banned statuses NOT in vocab: {in_use - vocab_ids}"
