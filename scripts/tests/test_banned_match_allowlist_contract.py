"""Metadata contract for `banned_match_allowlist.json`.

This file has two top-level arrays: ``allowlist`` (the primary catalog of
banned-substance match overrides allowed despite name collisions, e.g.
``ALA`` legitimately appearing as alpha-lipoic-acid vs. accidentally
matching banned amphetamines aliases) and ``denylist`` (negative-match
guards that block matches when they shouldn't fire).

Convention:
    ``_metadata.total_entries`` tracks ``len(allowlist)`` only. The
    ``denylist`` count is auxiliary — it's part of the same negative-match
    machinery but tracked separately because it has different semantic
    (block vs. permit).

If you add an allowlist entry, bump ``total_entries`` by 1. If you add a
denylist entry, do not bump ``total_entries``.
"""

import json
from pathlib import Path

import pytest

PATH = Path(__file__).parent.parent / "data" / "banned_match_allowlist.json"


@pytest.fixture(scope="module")
def blob():
    return json.loads(PATH.read_text(encoding="utf-8"))


def test_total_entries_tracks_allowlist_only(blob):
    expected = len(blob["allowlist"])
    actual = blob["_metadata"]["total_entries"]
    assert actual == expected, (
        f"_metadata.total_entries={actual} but allowlist has {expected} "
        f"entries. Bump total_entries to {expected} (denylist has "
        f"{len(blob['denylist'])} entries and is tracked separately)."
    )


def test_both_arrays_present(blob):
    """Defensive: the matcher reads both arrays. If one disappears, matching
    behavior changes silently."""
    for required in ("allowlist", "denylist"):
        assert required in blob, f"missing required array {required!r}"
        assert isinstance(blob[required], list)
