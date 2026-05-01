#!/usr/bin/env python3
"""
Contract tests for `data/severity_vocab.json` (locked v1.0.0, 2026-04-30).

Single source of truth for severity labels across interaction rules,
harmful-additive flags, and the clinical-risk taxonomy. Carries the full
DISPLAY CONTRACT per REFERENCE_DATA_LOOKUP_OPPORTUNITIES.md cross-cutting
rule.

Locked decisions:
  - Exactly 6 severities: contraindicated, avoid, caution, monitor,
    informational, safe
  - `info` was renamed to `informational` 2026-04-30 (39 source-data
    occurrences + Python emitters); the legacy `info` string MUST NOT
    appear in the vocab
  - Display contract: 8 required fields per entry
  - All IDs lowercase snake_case (severity is emitted lowercase by pipeline)

Cross-data validation lives separately in
`test_severity_vocab_cross_data_membership.py` — every `severity` value
in interaction rules + clinical_risk_taxonomy must be a vocab ID.
"""

import json
import os
import re

import pytest

VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "severity_vocab.json"
)


@pytest.fixture(scope="module")
def vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def severities(vocab):
    return vocab["severities"]


def test_metadata_block_present(vocab):
    md = vocab["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["total_entries"] == 6
    assert "LOCKED" in md["status"]
    assert md["char_limit_short_label"] == 12
    assert md["char_limit_action"] == 40
    assert md["char_limit_notes"] == 200


def test_exactly_6_severities_locked(severities):
    assert len(severities) == 6, (
        f"Vocab is locked at 6 severities; got {len(severities)}."
    )


REQUIRED_FIELDS = {
    "id", "name", "short_label", "tone",
    "ui_color", "ui_icon", "action", "notes",
}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
ALLOWED_TONES = {"positive", "neutral", "info", "warning", "danger"}
ALLOWED_UI_COLORS = {"green", "blue", "gray", "yellow", "orange", "red"}
ALLOWED_UI_ICONS = {"check", "info", "warning", "alert", "block"}


def test_every_severity_has_display_contract_fields(severities):
    for s in severities:
        keys = set(s.keys())
        missing = REQUIRED_FIELDS - keys
        extra = keys - REQUIRED_FIELDS
        assert not missing, f"severity {s.get('id')!r} missing: {missing}"
        assert not extra, f"severity {s['id']!r} extra fields: {extra}"


def test_every_id_unique_and_lowercase_snake(severities):
    ids = [s["id"] for s in severities]
    assert len(set(ids)) == len(ids), "duplicate severity IDs"
    for sid in ids:
        assert ID_PATTERN.match(sid), f"severity id {sid!r} not snake_case"


def test_canonical_6_ids_present(severities):
    expected = {
        "contraindicated", "avoid", "caution",
        "monitor", "informational", "safe",
    }
    actual = {s["id"] for s in severities}
    missing = expected - actual
    extra = actual - expected
    assert not missing, f"canonical severities missing: {missing}"
    assert not extra, f"vocab has severities NOT in canonical set: {extra}"


def test_legacy_info_id_absent(severities):
    """Per 2026-04-30 rename: `info` → `informational`. The legacy `info`
    string is dead and must not reappear in the vocab."""
    ids = {s["id"] for s in severities}
    assert "info" not in ids, (
        "Legacy `info` ID found in vocab — it was renamed to `informational` "
        "in 2026-04-30 across data files (20 sites) + Python emitters. "
        "Adding it back would re-create the inconsistency."
    )


def test_short_label_within_char_limit(severities):
    over = [(s["id"], len(s["short_label"])) for s in severities if len(s["short_label"]) > 12]
    assert not over, f"short_label exceeds 12-char limit: {over}"
    empty = [s["id"] for s in severities if not s["short_label"].strip()]
    assert not empty, f"empty short_label: {empty}"


def test_action_within_char_limit(severities):
    over = [(s["id"], len(s["action"])) for s in severities if len(s["action"]) > 40]
    assert not over, f"action exceeds 40-char limit: {over}"


def test_notes_within_char_limit(severities):
    over = [(s["id"], len(s["notes"])) for s in severities if len(s["notes"]) > 200]
    assert not over, f"notes exceed 200-char limit: {over}"
    empty = [s["id"] for s in severities if not s["notes"].strip()]
    assert not empty, f"empty notes: {empty}"


def test_tone_in_allowed_enum(severities):
    for s in severities:
        assert s["tone"] in ALLOWED_TONES, f"{s['id']} tone={s['tone']!r}"


def test_ui_color_in_allowed_enum(severities):
    for s in severities:
        assert s["ui_color"] in ALLOWED_UI_COLORS, f"{s['id']} ui_color={s['ui_color']!r}"


def test_ui_icon_in_allowed_enum(severities):
    for s in severities:
        assert s["ui_icon"] in ALLOWED_UI_ICONS, f"{s['id']} ui_icon={s['ui_icon']!r}"


SEED_DISPLAY_CONTRACT = {
    "contraindicated": {"tone": "danger", "ui_color": "red", "ui_icon": "block", "short_label": "Do not use"},
    "avoid":           {"tone": "danger", "ui_color": "red", "ui_icon": "alert", "short_label": "Avoid"},
    "caution":         {"tone": "warning", "ui_color": "orange", "ui_icon": "warning", "short_label": "Caution"},
    "monitor":         {"tone": "warning", "ui_color": "yellow", "ui_icon": "warning", "short_label": "Monitor"},
    "informational":   {"tone": "info", "ui_color": "blue", "ui_icon": "info", "short_label": "Info"},
    "safe":            {"tone": "positive", "ui_color": "green", "ui_icon": "check", "short_label": "Safe"},
}


def test_seed_display_contract_locked(severities):
    """Per doc §2 seed table — locks tone+color+icon+short_label per severity."""
    by_id = {s["id"]: s for s in severities}
    for sid, expected in SEED_DISPLAY_CONTRACT.items():
        s = by_id[sid]
        for field, want in expected.items():
            assert s[field] == want, (
                f"severity {sid} field {field}: expected {want!r}, got {s[field]!r}. "
                "Seed display contract is locked per REFERENCE_DATA_LOOKUP_OPPORTUNITIES.md §2."
            )


# ---------------------------------------------------------------------------
# Cross-data membership — every severity value in source data files MUST be
# in vocab. This is the integrity-gate equivalent for severity (separate from
# db_integrity_sanity_check.py because the gate is fast and self-contained).
# ---------------------------------------------------------------------------


def _walk_severities(obj, found):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "severity" and isinstance(v, str):
                found.add(v)
            _walk_severities(v, found)
    elif isinstance(obj, list):
        for x in obj:
            _walk_severities(x, found)


@pytest.fixture(scope="module")
def severity_values_in_source_data():
    found = set()
    for relpath in (
        "ingredient_interaction_rules.json",
        "ingredient_interaction_rules_Reviewed.json",
    ):
        path = os.path.join(os.path.dirname(__file__), "..", "data", relpath)
        with open(path, encoding="utf-8") as f:
            _walk_severities(json.load(f), found)
    return found


def test_every_source_data_severity_is_in_vocab(severities, severity_values_in_source_data):
    vocab_ids = {s["id"] for s in severities}
    unknown = severity_values_in_source_data - vocab_ids
    assert not unknown, (
        f"severity values found in source data NOT in vocab: {unknown}. "
        "Either add to vocab (with clinician sign-off) or fix the source data."
    )


def test_clinical_risk_taxonomy_severity_levels_in_vocab(severities):
    """clinical_risk_taxonomy.json carries a parallel severity_levels list.
    Its IDs must align with severity_vocab.json."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "data", "clinical_risk_taxonomy.json"
    )
    with open(path, encoding="utf-8") as f:
        tax = json.load(f)

    if "severity_levels" not in tax:
        pytest.skip("clinical_risk_taxonomy.json has no severity_levels list")

    vocab_ids = {s["id"] for s in severities}
    tax_ids = {entry["id"] for entry in tax["severity_levels"] if isinstance(entry, dict) and "id" in entry}
    # tax may include extras like "no_data" that aren't shipped severities;
    # we only assert that its overlap with the canonical set is consistent.
    overlap = tax_ids & vocab_ids
    canonical_in_tax = {"contraindicated", "avoid", "caution", "monitor", "informational", "safe"} & tax_ids
    assert canonical_in_tax <= overlap, (
        f"clinical_risk_taxonomy severity_levels has canonical IDs not in vocab: "
        f"{canonical_in_tax - overlap}"
    )
