import logging

import pytest

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _ambiguity_warnings(caplog):
    return [
        record.getMessage()
        for record in caplog.records
        if "Ambiguous quality-map match:" in record.getMessage()
    ]


def _duplicate_path_debugs(caplog):
    return [
        record.getMessage()
        for record in caplog.records
        if "duplicate match paths resolved" in record.getMessage()
    ]


@pytest.mark.parametrize(
    ("raw_label", "standard_name", "expected_parent", "expected_form"),
    [
        ("Sodium", "Sodium", "sodium", "sodium (unspecified)"),
        (
            "EpiCor dried Yeast Fermentate",
            "Yeast Fermentate Dried",
            "yeast_fermentate",
            "yeast fermentate (unspecified)",
        ),
        (
            "Chondroitin Sulfate, Sodium",
            "Chondroitin Sulfate, Sodium",
            "chondroitin",
            "chondroitin sulfate",
        ),
    ],
)
def test_same_resolution_quality_map_duplicates_do_not_warn(
    enricher,
    caplog,
    raw_label,
    standard_name,
    expected_parent,
    expected_form,
):
    quality_map = enricher.databases.get("ingredient_quality_map", {})
    caplog.clear()

    with caplog.at_level(logging.DEBUG, logger="enrich_supplements_v3"):
        result = enricher._match_quality_map(raw_label, standard_name, quality_map)

    assert result is not None
    assert result["canonical_id"] == expected_parent
    assert result["form_id"] == expected_form
    assert result["match_ambiguity_candidates"] == []
    assert _ambiguity_warnings(caplog) == []
    assert _duplicate_path_debugs(caplog) == []
