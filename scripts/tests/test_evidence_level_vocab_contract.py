#!/usr/bin/env python3
"""
Contract tests for `data/evidence_level_vocab.json` (locked v1.0.0, 2026-04-30).

Lean-shape vocab (id+name+notes+multiplier+tier). Cross-data membership
is scoped to `backed_clinical_studies.json` only — `ingredient_interaction_rules.json`
uses a DIFFERENT field also called `evidence_level` containing strength values
(established/probable/theoretical) that warrants its own evidence_strength_vocab
in a future sprint.
"""

import json
import os

import pytest

VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "evidence_level_vocab.json"
)


@pytest.fixture(scope="module")
def vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def levels(vocab):
    return vocab["evidence_levels"]


def test_metadata(vocab):
    md = vocab["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["total_entries"] == 5
    assert "LOCKED" in md["status"]


def test_exactly_5_levels(levels):
    assert len(levels) == 5


REQUIRED_FIELDS = {"id", "name", "notes", "multiplier", "tier"}


def test_required_fields_present(levels):
    for l in levels:
        keys = set(l.keys())
        assert REQUIRED_FIELDS == keys, (
            f"level {l.get('id')!r} fields drift: missing={REQUIRED_FIELDS - keys}, "
            f"extra={keys - REQUIRED_FIELDS}"
        )


def test_canonical_5_ids(levels):
    expected = {
        "product-human", "branded-rct", "ingredient-human",
        "strain-clinical", "preclinical",
    }
    actual = {l["id"] for l in levels}
    assert actual == expected, f"missing={expected-actual} extra={actual-expected}"


def test_multiplier_in_range(levels):
    for l in levels:
        m = l["multiplier"]
        assert isinstance(m, (int, float)) and 0.0 <= m <= 1.0, (
            f"{l['id']}: multiplier={m} not in [0,1]"
        )


def test_multipliers_match_scoring_config(levels):
    cfg_path = os.path.join(
        os.path.dirname(__file__), "..", "config", "scoring_config.json"
    )
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    expected = cfg["section_C_evidence_research"]["evidence_level_multipliers"]
    actual = {entry["id"]: entry["multiplier"] for entry in levels}
    assert actual == expected


def test_tier_in_range(levels):
    for l in levels:
        t = l["tier"]
        assert isinstance(t, int) and 1 <= t <= 5, f"{l['id']}: tier={t} not in [1,5]"


def test_notes_within_char_limit(levels):
    over = [(l["id"], len(l["notes"])) for l in levels if len(l["notes"]) > 200]
    assert not over, f"notes >200 chars: {over}"


def _walk_field(obj, key, found):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key and isinstance(v, str):
                found.add(v)
            _walk_field(v, key, found)
    elif isinstance(obj, list):
        for x in obj:
            _walk_field(x, key, found)


def test_every_clinical_study_evidence_level_in_vocab(levels):
    """Scoped to backed_clinical_studies only — interaction_rules use a
    different concept under same field name."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "data", "backed_clinical_studies.json"
    )
    found = set()
    _walk_field(json.load(open(path, encoding="utf-8")), "evidence_level", found)
    # Filter out the metadata description string
    found = {x for x in found if not x.startswith("Determines")}
    vocab_ids = {l["id"] for l in levels}
    unknown = found - vocab_ids
    assert not unknown, f"clinical study evidence_levels NOT in vocab: {unknown}"
