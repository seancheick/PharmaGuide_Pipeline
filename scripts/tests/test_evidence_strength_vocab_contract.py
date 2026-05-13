#!/usr/bin/env python3
"""
Contract tests for `data/evidence_strength_vocab.json` (locked v1.0.0, 2026-05-01).

This vocab covers the qualitative interaction-rule evidence tiers currently
stored under the source-data field name `evidence_level`. It is deliberately
separate from `evidence_level_vocab.json`, which covers clinical-study design
tiers in `backed_clinical_studies.json`.
"""

import json
import os

import pytest

VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "evidence_strength_vocab.json"
)
INTERACTION_RULE_PATHS = [
    os.path.join(os.path.dirname(__file__), "..", "data", "ingredient_interaction_rules.json"),
    os.path.join(os.path.dirname(__file__), "..", "data", "ingredient_interaction_rules_Reviewed.json"),
]


@pytest.fixture(scope="module")
def vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def strengths(vocab):
    return vocab["evidence_strengths"]


def test_metadata(vocab):
    md = vocab["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["total_entries"] == 6
    assert "LOCKED" in md["status"]
    assert md["char_limit_notes"] == 200


def test_exactly_6_strengths(strengths):
    assert len(strengths) == 6


REQUIRED_FIELDS = {"id", "name", "notes", "tier"}


def test_required_fields_present(strengths):
    for entry in strengths:
        keys = set(entry.keys())
        assert REQUIRED_FIELDS == keys, (
            f"strength {entry.get('id')!r} fields drift: "
            f"missing={REQUIRED_FIELDS - keys}, extra={keys - REQUIRED_FIELDS}"
        )


def test_canonical_6_ids(strengths):
    expected = {"established", "probable", "moderate", "limited", "theoretical", "no_data"}
    actual = {entry["id"] for entry in strengths}
    assert actual == expected, f"missing={expected - actual} extra={actual - expected}"


def test_tier_values_are_unique_and_ordered(strengths):
    tiers = [entry["tier"] for entry in strengths]
    assert sorted(tiers) == [1, 2, 3, 4, 5, 6]


def test_notes_within_char_limit(strengths):
    over = [(entry["id"], len(entry["notes"])) for entry in strengths if len(entry["notes"]) > 200]
    assert not over, f"notes >200 chars: {over}"


def _walk_field(obj, key, found):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key and isinstance(v, str):
                found.add(v)
            _walk_field(v, key, found)
    elif isinstance(obj, list):
        for item in obj:
            _walk_field(item, key, found)


def test_every_interaction_rule_evidence_level_in_strength_vocab(strengths):
    found = set()
    # ingredient_interaction_rules_Reviewed.json is a stale v5.2.0
    # snapshot retired 2026-05-13. Existence-guarded so this test
    # tolerates either presence (during transition) or absence
    # (post-retirement) without dropping coverage on the live file.
    for path in INTERACTION_RULE_PATHS:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            _walk_field(json.load(f), "evidence_level", found)
    vocab_ids = {entry["id"] for entry in strengths}
    unknown = found - vocab_ids
    assert not unknown, f"interaction-rule evidence_level values NOT in vocab: {unknown}"
