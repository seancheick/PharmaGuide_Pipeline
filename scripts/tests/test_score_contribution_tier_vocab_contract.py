#!/usr/bin/env python3
"""Contract tests for `data/score_contribution_tier_vocab.json`."""

import json
import os

import pytest

VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "score_contribution_tier_vocab.json"
)


@pytest.fixture(scope="module")
def vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def items(vocab):
    return vocab["score_contribution_tiers"]


def test_metadata(vocab):
    md = vocab["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["total_entries"] == 3


def test_exactly_3(items):
    assert len(items) == 3


REQUIRED = {
    "id", "name", "short_label", "tone",
    "ui_color", "ui_icon", "action", "notes", "tier_rank",
}


def test_required(items):
    for i in items:
        assert set(i.keys()) == REQUIRED


def test_canonical_3(items):
    assert {i["id"] for i in items} == {"tier_1", "tier_2", "tier_3"}


def test_tier_ranks(items):
    by_id = {i["id"]: i for i in items}
    assert by_id["tier_1"]["tier_rank"] == 1
    assert by_id["tier_2"]["tier_rank"] == 2
    assert by_id["tier_3"]["tier_rank"] == 3


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


def test_every_score_contribution_in_vocab(items):
    path = os.path.join(
        os.path.dirname(__file__), "..", "data", "backed_clinical_studies.json"
    )
    found = set()
    _walk(json.load(open(path, encoding="utf-8")), "score_contribution", found)
    canonical = {"tier_1", "tier_2", "tier_3"}
    in_use = found & canonical
    vocab_ids = {i["id"] for i in items}
    assert in_use <= vocab_ids
