"""Metadata contract for `ingredient_weights.json`.

This file's shape is dict-keyed-multi-payload, so the universal
``test_data_file_metadata_contract`` cannot apply. The author's convention
is documented here and pinned by the test below.

Convention:
    ``_metadata.total_entries`` tracks the number of **dosage tiers**
    (``dosage_weights`` keys: ``therapeutic``, ``optimal``, ``maintenance``,
    ``trace``). The other top-level dicts (``category_weights`` with 10
    ingredient categories, ``ingredient_priorities`` with 3 priority bands)
    are static structural config — adding a category or a priority band is a
    schema migration, not an entry addition.

If you add a new dosage tier (very rare), bump ``_metadata.total_entries``
to match. If you add an ingredient category or priority band, do not bump
``total_entries`` — but DO bump ``_metadata.schema_version`` and update this
docstring to record the shape change.
"""

import json
from pathlib import Path

import pytest

PATH = Path(__file__).parent.parent / "data" / "ingredient_weights.json"


@pytest.fixture(scope="module")
def blob():
    return json.loads(PATH.read_text(encoding="utf-8"))


def test_total_entries_tracks_dosage_weights_tier_count(blob):
    """Pins the file-specific semantic so drift fails fast at commit time."""
    expected = len(blob["dosage_weights"])
    actual = blob["_metadata"]["total_entries"]
    assert actual == expected, (
        f"_metadata.total_entries={actual} but dosage_weights has {expected} "
        f"tiers. Either bump total_entries to {expected}, or update this "
        f"test if the semantic intentionally changed."
    )


def test_category_weights_and_priorities_are_present(blob):
    """Defensive: these two sub-dicts are required structural config. If they
    disappear, the scoring engine's lookup will fail at runtime — catch it here."""
    assert "category_weights" in blob and isinstance(blob["category_weights"], dict)
    assert blob["category_weights"], "category_weights cannot be empty"
    assert "ingredient_priorities" in blob and isinstance(blob["ingredient_priorities"], dict)
    assert blob["ingredient_priorities"], "ingredient_priorities cannot be empty"
