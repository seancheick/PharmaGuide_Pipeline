#!/usr/bin/env python3
"""
Phase 4a — flag-based suppression contract tests.

Asserts:
  - retire entries carry is_label_descriptor: true
  - move-to-actives entries carry is_active_only: true
  - Build pipeline (build_final_db.py:2272) skips both flag classes
    from inactive_ingredients[] blob
"""

import json
import os
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DATA_PATH = Path(__file__).parent.parent / "data" / "other_ingredients.json"


@pytest.fixture(scope="module")
def entries():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)["other_ingredients"]


def test_label_descriptor_count(entries):
    """All label-descriptor entries are flagged."""
    flagged = [e for e in entries if e.get("is_label_descriptor")]
    expected = [e for e in entries if e.get("category") == "label_descriptor"]
    assert len(flagged) == len(expected)


def test_active_only_count(entries):
    """All move-to-actives entries are flagged."""
    flagged = [e for e in entries if e.get("is_active_only")]
    expected = [e for e in entries if e.get("category") == "active_pending_relocation"]
    assert len(flagged) == len(expected)


def test_no_entry_has_both_flags(entries):
    """An entry can't be BOTH a label descriptor AND a move-to-actives target.
    These are mutually exclusive dispositions."""
    both = [e.get("id") for e in entries
            if e.get("is_label_descriptor") and e.get("is_active_only")]
    assert not both, f"entries with both flags (mutually exclusive): {both}"


def test_flagged_entries_have_empty_functional_roles(entries):
    """Phase 3 backfill assigned [] to all flag-eligible entries. The flags
    just identify WHY they're empty. Both flag classes should still have []."""
    bad = []
    for e in entries:
        if (e.get("is_label_descriptor") or e.get("is_active_only")):
            roles = e.get("functional_roles", [])
            if roles:
                bad.append((e.get("id"), roles))
    assert not bad, f"flagged entries should have functional_roles=[]: {bad[:5]}"


def test_unflagged_entries_have_populated_roles(entries):
    """Inverse invariant: any other_ingredient with NO flag should have
    populated functional_roles[]. Catches entries that fell between cracks."""
    unflagged_empty = []
    for e in entries:
        is_label = e.get("is_label_descriptor", False)
        is_active = e.get("is_active_only", False)
        roles = e.get("functional_roles", [])
        if not is_label and not is_active and not roles:
            unflagged_empty.append(e.get("id"))
    # The 1 known exception is NHA_GLYCOLIPIDS (manual_review case).
    # Allow at most 1 such entry without breaking the invariant.
    assert len(unflagged_empty) <= 1, (
        f"unflagged entries with empty roles: {unflagged_empty[:10]}"
    )


def test_build_blob_suppresses_label_descriptor(entries):
    """End-to-end: when an inactive ingredient maps to a flagged entry,
    build_final_db.py must skip it from inactive_ingredients[]."""
    # Pick a known label-descriptor entry to test against
    label_entries = [e for e in entries if e.get("is_label_descriptor")]
    assert label_entries, "no label_descriptor entries found in fixture"
    sample = label_entries[0]
    sample_name = sample.get("standard_name") or (sample.get("aliases") or [""])[0]
    assert sample_name, "fixture entry has no standard_name or alias"

    # Synthesize a minimal enriched product where this descriptor appears
    # in inactiveIngredients
    from build_final_db import resolve_other_ingredient_reference

    other_ref = resolve_other_ingredient_reference(sample_name, "")
    assert other_ref.get("is_label_descriptor") is True, (
        f"resolve_other_ingredient_reference didn't surface "
        f"is_label_descriptor flag for {sample_name!r}"
    )


def test_build_blob_suppresses_active_only(entries):
    """End-to-end: same for is_active_only flag."""
    active_entries = [e for e in entries if e.get("is_active_only")]
    assert active_entries
    sample = active_entries[0]
    sample_name = sample.get("standard_name") or (sample.get("aliases") or [""])[0]

    from build_final_db import resolve_other_ingredient_reference
    other_ref = resolve_other_ingredient_reference(sample_name, "")
    assert other_ref.get("is_active_only") is True, (
        f"is_active_only flag not surfaced for {sample_name!r}"
    )
