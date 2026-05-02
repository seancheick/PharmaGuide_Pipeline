#!/usr/bin/env python3
"""Contract tests for `data/iqm_category_vocab.json` (locked v1.0.0, 2026-05-01)."""

import json
import os
import re

import pytest

VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "iqm_category_vocab.json"
)


@pytest.fixture(scope="module")
def vocab():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def cats(vocab):
    return vocab["iqm_categories"]


def test_metadata(vocab):
    md = vocab["_metadata"]
    assert md["schema_version"] == "1.0.0"
    assert md["total_entries"] == 12
    assert "LOCKED" in md["status"]


def test_exactly_12(cats):
    assert len(cats) == 12


REQUIRED = {"id", "name", "notes", "examples"}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def test_required_fields(cats):
    for c in cats:
        assert set(c.keys()) == REQUIRED


def test_canonical_12_ids(cats):
    expected = {
        "amino_acids", "antioxidants", "enzymes", "fatty_acids",
        "fibers", "functional_foods", "herbs", "minerals",
        "other", "probiotics", "proteins", "vitamins",
    }
    assert {c["id"] for c in cats} == expected


def test_ids_unique_and_snake(cats):
    ids = [c["id"] for c in cats]
    assert len(set(ids)) == len(ids)
    for cid in ids:
        assert ID_PATTERN.match(cid)


def test_notes_within_char_limit(cats):
    over = [(c["id"], len(c["notes"])) for c in cats if len(c["notes"]) > 200]
    assert not over, f"notes >200 chars: {over}"


def test_examples_nonempty(cats):
    for c in cats:
        assert isinstance(c["examples"], list) and c["examples"]


def _walk(obj, key, found):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key and isinstance(v, str):
                found.add(v)
            _walk(v, key, found)
    elif isinstance(obj, list):
        for x in obj:
            _walk(x, key, found)


def test_every_iqm_parent_category_in_vocab(cats):
    """Every distinct `category` value in ingredient_quality_map.json
    must be one of the 12 vocab IDs."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "data", "ingredient_quality_map.json"
    )
    found = set()
    _walk(json.load(open(path, encoding="utf-8")), "category", found)
    vocab_ids = {c["id"] for c in cats}
    unknown = found - vocab_ids
    assert not unknown, f"IQM categories NOT in vocab: {unknown}"
