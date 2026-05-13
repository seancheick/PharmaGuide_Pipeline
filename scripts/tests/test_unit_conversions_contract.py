"""Metadata contract for `unit_conversions.json`.

This file's shape is multi-section dict, so the universal
``test_data_file_metadata_contract`` cannot apply.

Convention:
    ``_metadata.total_entries`` tracks the number of **vitamin conversion
    entries** (``vitamin_conversions`` dict keys — e.g. ``vitamin_d3``,
    ``vitamin_e_d_alpha_tocopherol``, ``vitamin_a_retinol``). The other
    top-level sub-dicts (``mass_conversions``, ``probiotic_conversions``,
    ``form_detection_patterns``) are static rule/alias config, not vitamin
    conversion entries — they carry their own ``_description`` / ``rules``
    sub-keys and would inflate the count meaninglessly if summed.

If you add a vitamin conversion, bump ``_metadata.total_entries`` by 1.
If you change ``mass_conversions`` / ``probiotic_conversions`` /
``form_detection_patterns``, do not bump total_entries — bump
``_metadata.schema_version`` if the shape changes.
"""

import json
from pathlib import Path

import pytest

PATH = Path(__file__).parent.parent / "data" / "unit_conversions.json"


@pytest.fixture(scope="module")
def blob():
    return json.loads(PATH.read_text(encoding="utf-8"))


def test_total_entries_tracks_vitamin_conversions_count(blob):
    expected = len(blob["vitamin_conversions"])
    actual = blob["_metadata"]["total_entries"]
    assert actual == expected, (
        f"_metadata.total_entries={actual} but vitamin_conversions has "
        f"{expected} entries. Bump total_entries to {expected}."
    )


def test_static_config_sections_are_present(blob):
    """Defensive: the runtime UnitConverter depends on these sub-dicts existing."""
    for required in ("vitamin_conversions", "mass_conversions",
                     "probiotic_conversions", "form_detection_patterns"):
        assert required in blob, f"missing required section {required!r}"
        assert isinstance(blob[required], dict)
        assert blob[required], f"{required!r} cannot be empty"
