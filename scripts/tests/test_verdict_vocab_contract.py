#!/usr/bin/env python3
"""
Contract tests for `data/verdict_vocab.json` (clinician-locked v1.0.0,
2026-04-30).

This vocab is the single source of truth for the 5 product-quality verdicts
shipped to Flutter. It carries the full DISPLAY CONTRACT (name + short_label
+ tone + ui_color + ui_icon + action + notes) per the cross-cutting rule in
REFERENCE_DATA_LOOKUP_OPPORTUNITIES.md — Flutter is a renderer, not a
decision-maker for tone/color/icon/action.

Locked decisions captured by these tests:
  - Exactly 5 verdicts: SAFE, CAUTION, POOR, BLOCKED, UNSAFE
  - NOT_SCORED is intentionally excluded (review-queue-only per doc spec)
  - Display contract: 8 required fields per entry
  - tone enum: positive | neutral | info | warning | danger
  - ui_color enum: green | blue | gray | yellow | orange | red
  - ui_icon enum: check | info | warning | alert | block
  - short_label ≤12 chars, action ≤40 chars, notes ≤200 chars
  - All IDs UPPERCASE_SNAKE (verdicts are emitted as uppercase by pipeline)

Adding a 6th verdict requires fresh clinician sign-off and a coordinated
pipeline + Flutter release — should fail this test, not slip through silently.
"""

import json
import os
import re

import pytest

VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "verdict_vocab.json"
)


@pytest.fixture(scope="module")
def vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def verdicts(vocab):
    return vocab["verdicts"]


# ---------------------------------------------------------------------------
# Top-level contract
# ---------------------------------------------------------------------------


def test_metadata_block_present(vocab):
    assert "_metadata" in vocab
    md = vocab["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["total_entries"] == 5
    assert "LOCKED" in md["status"]
    assert md["char_limit_short_label"] == 12
    assert md["char_limit_action"] == 40
    assert md["char_limit_notes"] == 200


def test_exactly_5_verdicts_locked(verdicts):
    """Adding/removing verdicts requires pipeline + Flutter coordination.
    NOT_SCORED is deliberately excluded per doc spec (review-queue-only)."""
    assert len(verdicts) == 5, (
        f"Vocab is locked at 5 verdicts; got {len(verdicts)}. "
        "Adding or removing requires a fresh clinician review cycle "
        "AND a coordinated pipeline + Flutter release."
    )


# ---------------------------------------------------------------------------
# Display contract — every UI-bound vocab carries these 8 fields
# ---------------------------------------------------------------------------


REQUIRED_FIELDS = {
    "id", "name", "short_label", "tone",
    "ui_color", "ui_icon", "action", "notes",
}
ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
ALLOWED_TONES = {"positive", "neutral", "info", "warning", "danger"}
ALLOWED_UI_COLORS = {"green", "blue", "gray", "yellow", "orange", "red"}
ALLOWED_UI_ICONS = {"check", "info", "warning", "alert", "block"}


def test_every_verdict_has_display_contract_fields(verdicts):
    """Display contract fields are mandatory for UI-bound vocabs.
    Flutter relies on these to theme severity_pill, banner, alert_summary_card,
    and score_breakdown_card consistently."""
    for v in verdicts:
        keys = set(v.keys())
        missing = REQUIRED_FIELDS - keys
        extra = keys - REQUIRED_FIELDS
        assert not missing, f"verdict {v.get('id')!r} missing: {missing}"
        assert not extra, (
            f"verdict {v['id']!r} has unexpected fields: {extra}. "
            "Display contract is locked at 8 fields."
        )


def test_every_id_unique_and_uppercase_snake(verdicts):
    ids = [v["id"] for v in verdicts]
    assert len(set(ids)) == len(ids), "duplicate verdict IDs"
    for vid in ids:
        assert ID_PATTERN.match(vid), (
            f"verdict id {vid!r} is not UPPER_SNAKE (must match ^[A-Z][A-Z0-9_]*$)"
        )


def test_canonical_5_ids_present(verdicts):
    """The locked canonical set per REFERENCE_DATA_LOOKUP_OPPORTUNITIES.md §1."""
    expected = {"SAFE", "CAUTION", "POOR", "BLOCKED", "UNSAFE"}
    actual = {v["id"] for v in verdicts}
    missing = expected - actual
    extra = actual - expected
    assert not missing, f"canonical verdicts missing: {missing}"
    assert not extra, (
        f"vocab contains verdicts NOT in canonical set: {extra}. "
        "If pipeline now emits a new verdict, requires fresh review."
    )


def test_not_scored_explicitly_excluded(verdicts):
    """Per doc: NOT_SCORED ships to review queue, never to Flutter.
    Including it in vocab would create a dead ID."""
    ids = {v["id"] for v in verdicts}
    assert "NOT_SCORED" not in ids, (
        "NOT_SCORED MUST NOT be in vocab — products that fail to score "
        "go to the review queue per pipeline contract. Including it here "
        "would be a dead ID."
    )


# ---------------------------------------------------------------------------
# Field-level contract
# ---------------------------------------------------------------------------


def test_every_name_is_nonempty_display_string(verdicts):
    for v in verdicts:
        assert isinstance(v["name"], str) and v["name"].strip()
        assert any(c.isupper() for c in v["name"]), (
            f"verdict {v['id']!r} name {v['name']!r} has no uppercase letters"
        )


def test_short_label_within_char_limit(verdicts):
    over = [(v["id"], len(v["short_label"])) for v in verdicts if len(v["short_label"]) > 12]
    assert not over, f"short_label exceeds 12-char limit: {over}"
    empty = [v["id"] for v in verdicts if not v["short_label"].strip()]
    assert not empty, f"empty short_label: {empty}"


def test_action_within_char_limit(verdicts):
    over = [(v["id"], len(v["action"])) for v in verdicts if len(v["action"]) > 40]
    assert not over, f"action exceeds 40-char limit: {over}"
    empty = [v["id"] for v in verdicts if not v["action"].strip()]
    assert not empty, f"empty action: {empty}"


def test_notes_within_char_limit(verdicts):
    over = [(v["id"], len(v["notes"])) for v in verdicts if len(v["notes"]) > 200]
    assert not over, f"notes exceed 200-char limit: {over}"
    empty = [v["id"] for v in verdicts if not v["notes"].strip()]
    assert not empty, f"empty notes: {empty}"


def test_tone_in_allowed_enum(verdicts):
    for v in verdicts:
        assert v["tone"] in ALLOWED_TONES, (
            f"verdict {v['id']!r} tone {v['tone']!r} not in {ALLOWED_TONES}"
        )


def test_ui_color_in_allowed_enum(verdicts):
    for v in verdicts:
        assert v["ui_color"] in ALLOWED_UI_COLORS, (
            f"verdict {v['id']!r} ui_color {v['ui_color']!r} not in {ALLOWED_UI_COLORS}"
        )


def test_ui_icon_in_allowed_enum(verdicts):
    for v in verdicts:
        assert v["ui_icon"] in ALLOWED_UI_ICONS, (
            f"verdict {v['id']!r} ui_icon {v['ui_icon']!r} not in {ALLOWED_UI_ICONS}"
        )


# ---------------------------------------------------------------------------
# Semantic correctness — locked seed display contract from doc §1
# ---------------------------------------------------------------------------


SEED_DISPLAY_CONTRACT = {
    "SAFE":    {"tone": "positive", "ui_color": "green",  "ui_icon": "check",   "short_label": "Safe"},
    "CAUTION": {"tone": "warning",  "ui_color": "yellow", "ui_icon": "warning", "short_label": "Caution"},
    "POOR":    {"tone": "warning",  "ui_color": "orange", "ui_icon": "warning", "short_label": "Poor"},
    "BLOCKED": {"tone": "danger",   "ui_color": "red",    "ui_icon": "block",   "short_label": "Blocked"},
    "UNSAFE":  {"tone": "danger",   "ui_color": "red",    "ui_icon": "alert",   "short_label": "Unsafe"},
}


def test_seed_display_contract_locked(verdicts):
    """Per doc §1 seed table — locks tone+color+icon+short_label per verdict.
    Changing any of these requires a clinician + design review cycle."""
    by_id = {v["id"]: v for v in verdicts}
    for vid, expected in SEED_DISPLAY_CONTRACT.items():
        v = by_id[vid]
        for field, want in expected.items():
            assert v[field] == want, (
                f"verdict {vid} field {field}: expected {want!r}, got {v[field]!r}. "
                "Seed display contract is locked per REFERENCE_DATA_LOOKUP_OPPORTUNITIES.md §1."
            )
