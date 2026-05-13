"""Metadata contract for `color_indicators.json`.

This file's 4 top-level arrays serve different purposes in the
color-claim scoring pipeline:

* ``natural_indicators`` — the PRIMARY catalog of words/phrases that
  positively signal natural coloring on a label (66 entries).
* ``artificial_indicators`` — negative-signal phrases (39).
* ``explicit_natural_dyes`` — named natural dyes (51).
* ``explicit_artificial_dyes`` — named artificial dyes (81).

Convention:
    ``_metadata.total_entries`` tracks ``len(natural_indicators)`` only.
    The other 3 arrays are auxiliary — they're consumed by the same
    classifier but tracked separately because they have different
    severity weights and override semantics.

If you add a natural_indicator, bump ``total_entries`` by 1. Adding to
any of the other 3 arrays does NOT change total_entries.

NOTE: this asymmetric convention is fragile. A consolidation refactor
(``total_entries`` = sum of all 4) is on the wishlist but would require
an audit pass on every consumer. Until then, this test pins the current
semantic so authors don't accidentally double-bump.
"""

import json
from pathlib import Path

import pytest

PATH = Path(__file__).parent.parent / "data" / "color_indicators.json"

REQUIRED_ARRAYS = (
    "natural_indicators",
    "artificial_indicators",
    "explicit_natural_dyes",
    "explicit_artificial_dyes",
)


@pytest.fixture(scope="module")
def blob():
    return json.loads(PATH.read_text(encoding="utf-8"))


def test_total_entries_tracks_natural_indicators_only(blob):
    expected = len(blob["natural_indicators"])
    actual = blob["_metadata"]["total_entries"]
    assert actual == expected, (
        f"_metadata.total_entries={actual} but natural_indicators has "
        f"{expected} entries. Bump total_entries to {expected}. "
        f"(artificial_indicators / explicit_*_dyes are auxiliary and "
        f"are NOT counted in this metadata field.)"
    )


def test_all_four_arrays_present_and_non_empty(blob):
    """Defensive: the color classifier reads all 4 arrays. If any is missing
    or empty, scoring degrades silently for that signal class."""
    for a in REQUIRED_ARRAYS:
        assert a in blob, f"missing required array {a!r}"
        assert isinstance(blob[a], list) and blob[a], f"{a!r} must be a non-empty list"
