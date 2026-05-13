"""Metadata contract for `manufacture_deduction_expl.json`.

This file is structural scoring config — not an entry catalog. Its top
level is a mix of:

* one scalar (``total_deduction_cap``: int) — the overall deduction floor
* four nested dicts (``violation_categories``, ``modifiers``,
  ``calculation_rules``, ``score_thresholds``) — each carrying their own
  sub-rules

The universal ``test_data_file_metadata_contract`` skips this file because
the shape isn't entry-shaped. The convention encoded by the author is:

    ``_metadata.total_entries`` == count of top-level non-``_metadata``
    sub-sections (5 today: 1 scalar + 4 dicts).

Adding a new top-level scoring config section bumps total_entries by 1.
Adding rules INSIDE an existing sub-dict does NOT change total_entries —
that's intra-section growth and would be tracked by a per-section schema
bump if at all.
"""

import json
from pathlib import Path

import pytest

PATH = Path(__file__).parent.parent / "data" / "manufacture_deduction_expl.json"


@pytest.fixture(scope="module")
def blob():
    return json.loads(PATH.read_text(encoding="utf-8"))


def test_total_entries_tracks_top_level_section_count(blob):
    non_meta = [k for k in blob.keys() if k != "_metadata"]
    expected = len(non_meta)
    actual = blob["_metadata"]["total_entries"]
    assert actual == expected, (
        f"_metadata.total_entries={actual} but there are {expected} "
        f"top-level non-_metadata sub-sections: {non_meta}. "
        f"Bump total_entries to {expected}."
    )


def test_required_top_level_sections_are_present(blob):
    """Defensive: the scoring engine reads each of these by name. If one
    disappears, manufacturer deduction breaks at runtime."""
    required = {
        "total_deduction_cap",
        "violation_categories",
        "modifiers",
        "calculation_rules",
        "score_thresholds",
    }
    missing = required - set(blob.keys())
    assert not missing, f"required top-level sections missing: {missing}"
