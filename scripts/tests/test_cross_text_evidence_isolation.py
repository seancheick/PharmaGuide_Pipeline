"""Ingredient delivery evidence cannot be borrowed from unrelated product text (H7)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


def test_marketing_statement_cannot_synthesize_liposomal_delivery(enricher) -> None:
    result = enricher._collect_delivery_data({
        "activeIngredients": [{"name": "Vitamin C", "standardName": "Vitamin C"}],
        "statements": [{"notes": "Learn about liposomal delivery in our research library."}],
        "physicalState": {"langualCodeDescription": "Tablet"},
    })

    assert "liposomal" not in {system["name"] for system in result["systems"]}


def test_row_local_liposomal_label_evidence_is_retained(enricher) -> None:
    result = enricher._collect_delivery_data({
        "activeIngredients": [
            {"name": "Liposomal Vitamin C", "standardName": "Vitamin C"}
        ],
        "physicalState": {"langualCodeDescription": "Liquid"},
    })

    liposomal = next(system for system in result["systems"] if system["name"] == "liposomal")
    assert liposomal["match_source"] == "activeIngredients[0]"


@pytest.mark.parametrize(
    ("statement_type", "notes", "system_name"),
    [
        ("Formulation re: Other", "Delayed-release capsule design", "delayed-release"),
        ("Formulation re: Other", "This product is in an acid-resistant capsule", "acid-resistant"),
        (
            "Suggested/Recommended/Usage/Directions",
            "Suggested use: Take 2 drops daily. Invert bottle to dispense individual drops.",
            "drops",
        ),
        ("FDA Statement of Identity", "Whole Food Supplements", "whole food"),
    ],
)
def test_structured_label_statement_delivery_evidence_is_retained(
    enricher,
    statement_type: str,
    notes: str,
    system_name: str,
) -> None:
    result = enricher._collect_delivery_data({
        "activeIngredients": [{"name": "Vitamin C", "standardName": "Vitamin C"}],
        "statements": [{"type": statement_type, "notes": notes}],
        "physicalState": {"langualCodeDescription": "Tablet"},
    })

    system = next(row for row in result["systems"] if row["name"] == system_name)
    assert system["match_source"] == "statements[0]"


def test_generic_astaxanthin_alias_cannot_unlock_astareal_study(enricher) -> None:
    study = next(
        row
        for row in enricher.databases["backed_clinical_studies"]["backed_clinical_studies"]
        if row["id"] == "BRAND_ASTAREAL"
    )
    product = {
        "fullName": "Natural Astaxanthin 12 mg",
        "activeIngredients": [{"name": "Astaxanthin", "standardName": "Astaxanthin"}],
    }

    assert enricher._brand_mentioned(
        study["standard_name"],
        study["aliases"],
        product,
        brand_tokens=study.get("brand_tokens"),
    ) is False


def test_explicit_astareal_marker_unlocks_astareal_study(enricher) -> None:
    study = next(
        row
        for row in enricher.databases["backed_clinical_studies"]["backed_clinical_studies"]
        if row["id"] == "BRAND_ASTAREAL"
    )
    product = {
        "fullName": "AstaReal Astaxanthin 12 mg",
        "activeIngredients": [{"name": "AstaReal", "standardName": "Astaxanthin"}],
    }

    assert enricher._brand_mentioned(
        study["standard_name"],
        study["aliases"],
        product,
        brand_tokens=study.get("brand_tokens"),
    ) is True


def test_standardization_percentage_stays_with_its_ingredient(enricher) -> None:
    result = enricher._collect_standardized_botanicals({
        "activeIngredients": [
            {
                "name": "Green Tea Extract standardized to 98% polyphenols",
                "standardName": "Green Tea",
                "raw_source_text": "Green Tea Extract standardized to 98% polyphenols",
            },
            {
                "name": "Ginkgo Biloba Leaf",
                "standardName": "Ginkgo Biloba",
                "raw_source_text": "Ginkgo Biloba Leaf",
            },
        ],
    })

    ginkgo = next(row for row in result if "ginkgo" in row["standard_name"].lower())
    assert ginkgo["percentage_found"] == 0
    assert ginkgo["percentage_source"] is None
