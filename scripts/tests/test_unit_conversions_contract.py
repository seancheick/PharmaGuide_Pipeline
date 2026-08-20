"""Metadata contract for `unit_conversions.json`.

This file's shape is multi-section dict, so the universal
``test_data_file_metadata_contract`` cannot apply.

Convention:
    ``_metadata.total_entries`` tracks the number of **vitamin conversion
    entries** (``vitamin_conversions`` dict keys — e.g. ``vitamin_d3``,
    ``vitamin_e_d_alpha_tocopherol``, ``vitamin_a_retinol``). The other
    top-level sub-dicts (``mass_conversions`` and
    ``form_detection_patterns``) are static rule/alias config, not vitamin
    conversion entries — they carry their own ``_description`` / ``rules``
    sub-keys and would inflate the count meaninglessly if summed.

If you add a vitamin conversion, bump ``_metadata.total_entries`` by 1.
If you change ``mass_conversions`` / ``form_detection_patterns``, do not bump
total_entries — bump
``_metadata.schema_version`` if the shape changes.
"""

import json
from pathlib import Path

import pytest

from enrich_supplements_v3 import SupplementEnricherV3
from unit_converter import UnitConverter

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


def test_conversion_statistics_are_derived_from_live_rules(blob):
    statistics = blob["_metadata"]["statistics"]
    vitamin_rules = blob["vitamin_conversions"]
    conversion_keys = sum(
        len(rule.get("conversions") or {})
        for rule in vitamin_rules.values()
        if isinstance(rule, dict)
    )
    mass_rules = len(blob["mass_conversions"]["rules"])

    assert statistics["vitamin_conversions"] == len(vitamin_rules)
    assert statistics["total_conversion_rules"] == conversion_keys + mass_rules


def test_static_config_sections_are_present(blob):
    """Defensive: the runtime UnitConverter depends on these sub-dicts existing."""
    for required in (
        "vitamin_conversions",
        "mass_conversions",
        "form_detection_patterns",
    ):
        assert required in blob, f"missing required section {required!r}"
        assert isinstance(blob[required], dict)
        assert blob[required], f"{required!r} cannot be empty"


def test_beta_carotene_conversion_contract_is_supplement_only(blob):
    """DSLD labels dietary supplements, so food-matrix factors are invalid here."""
    conversions = blob["vitamin_conversions"]

    assert "vitamin_a_beta_carotene_food" not in conversions
    supplement = conversions["vitamin_a_beta_carotene_supplement"]
    assert supplement["conversions"]["iu_to_mcg_rae"] == pytest.approx(0.3)
    assert (
        supplement["conversions"]["mcg_beta_carotene_to_mcg_rae"]
        == pytest.approx(0.5)
    )


def test_cfu_normalization_has_one_live_owner(blob):
    """CFU parsing belongs to enrichment, not the nutrient unit converter."""
    assert "probiotic_conversions" not in blob
    assert not hasattr(UnitConverter, "normalize_cfu")
    assert not hasattr(UnitConverter, "convert_ingredient_list")
    assert hasattr(SupplementEnricherV3, "_extract_cfu")
