"""Metadata contract for `functional_ingredient_groupings.json`.

Three top-level arrays drive different parts of the active-ingredient
classification and transparency-scoring pipeline:

* ``functional_groupings`` — PRIMARY catalog of named functional clusters
  (e.g. "antioxidant blend", "energy complex") that the cleaner treats as
  proprietary blend headers (8 entries).
* ``vague_terms_to_flag`` — generic marketing phrases that trigger the
  transparency penalty (7 entries).
* ``transparency_bonuses`` — opposite of vague_terms — disclosure
  language that earns the transparency bonus (3 entries).

Convention:
    ``_metadata.total_entries`` tracks ``len(functional_groupings)`` only.
    The other 2 arrays are smaller, auxiliary signals.

If you add a functional grouping, bump ``total_entries``. Additions to
``vague_terms_to_flag`` or ``transparency_bonuses`` do NOT bump
``total_entries``.
"""

import json
from pathlib import Path

import pytest

PATH = Path(__file__).parent.parent / "data" / "functional_ingredient_groupings.json"

REQUIRED_ARRAYS = (
    "functional_groupings",
    "vague_terms_to_flag",
    "transparency_bonuses",
)


@pytest.fixture(scope="module")
def blob():
    return json.loads(PATH.read_text(encoding="utf-8"))


def test_total_entries_tracks_functional_groupings_only(blob):
    expected = len(blob["functional_groupings"])
    actual = blob["_metadata"]["total_entries"]
    assert actual == expected, (
        f"_metadata.total_entries={actual} but functional_groupings has "
        f"{expected} entries. Bump total_entries to {expected}. "
        f"(vague_terms_to_flag / transparency_bonuses are auxiliary.)"
    )


def test_all_three_arrays_present(blob):
    for a in REQUIRED_ARRAYS:
        assert a in blob, f"missing required array {a!r}"
        assert isinstance(blob[a], list)
