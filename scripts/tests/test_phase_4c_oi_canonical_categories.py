#!/usr/bin/env python3
"""
Phase 4c — `other_ingredients.json` category canonicalization contract.

After the Phase 4c backfill, every `category` value must be either:
  - a functional_roles vocab ID (32 canonical roles), OR
  - one of 3 transitional buckets:
      label_descriptor, active_pending_relocation, manual_review

This brings the distinct count from 241 → ≤35 (target ≤30 + 3 transitional).
"""

import json
from pathlib import Path
import pytest

DATA_PATH = Path(__file__).parent.parent / "data" / "other_ingredients.json"
VOCAB_PATH = Path(__file__).parent.parent / "data" / "functional_roles_vocab.json"

TRANSITIONAL = {"label_descriptor", "active_pending_relocation", "manual_review"}


@pytest.fixture(scope="module")
def entries():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)["other_ingredients"]


@pytest.fixture(scope="module")
def vocab_ids():
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return {r["id"] for r in json.load(f)["functional_roles"]}


def test_distinct_category_count(entries):
    """241 → ≤35. Catches regressions where a free-text category leaks in."""
    distinct = {e.get("category") for e in entries if e.get("category")}
    assert len(distinct) <= 35, (
        f"too many distinct categories ({len(distinct)}): {sorted(distinct)}"
    )


def test_every_category_is_canonical(entries, vocab_ids):
    """Every category value must be a vocab role ID or transitional bucket."""
    allowed = vocab_ids | TRANSITIONAL
    bad = [(e.get("id"), e.get("category"))
           for e in entries
           if e.get("category") and e["category"] not in allowed]
    assert not bad, (
        f"{len(bad)} entries with non-canonical category: {bad[:10]}"
    )


def test_label_descriptor_category_matches_flag(entries):
    """category=label_descriptor ↔ is_label_descriptor=true (Phase 4a flag)."""
    bad = []
    for e in entries:
        cat_says_descriptor = e.get("category") == "label_descriptor"
        flag_says_descriptor = bool(e.get("is_label_descriptor"))
        if cat_says_descriptor != flag_says_descriptor:
            bad.append((e.get("id"), cat_says_descriptor, flag_says_descriptor))
    assert not bad, f"category↔flag mismatch: {bad[:5]}"


def test_active_pending_relocation_category_matches_flag(entries):
    """category=active_pending_relocation ↔ is_active_only=true."""
    bad = []
    for e in entries:
        cat_says = e.get("category") == "active_pending_relocation"
        flag_says = bool(e.get("is_active_only"))
        if cat_says != flag_says:
            bad.append((e.get("id"), cat_says, flag_says))
    assert not bad, f"category↔flag mismatch: {bad[:5]}"
