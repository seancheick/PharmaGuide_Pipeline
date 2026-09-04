"""Whole seaweed labels must not borrow a co-declared mineral's dose score."""

from __future__ import annotations

import pytest

from scoring_input_contract import build_scoring_classification
from scoring_v4.modules.generic_dose import score_dose


def _row(canonical: str, name: str, amount: float, unit: str, **extra) -> dict:
    return {
        "canonical_id": canonical, "name": name, "quantity": amount, "unit": unit,
        "mapped": True, "source_section": "activeIngredients",
        "raw_source_path": f"ingredientRows[{canonical}]",
        "cleaner_row_role": "active_scorable", "score_eligible_by_cleaner": True,
        "dose_class": "therapeutic_mass", "role_classification": "active_scorable",
        "scoreable_identity": True, **extra,
    }


@pytest.mark.parametrize("canonical,label", [
    ("kelp_powder", "Kelp"), ("nha_bladderwrack", "Bladderwrack"),
    ("seaweed", "Seaweed"),
])
@pytest.mark.parametrize("standard_name", [None, "Corrected registry name"])
def test_whole_seaweed_profile_does_not_depend_on_generated_extract_name(
    canonical: str, label: str, standard_name: str | None,
) -> None:
    # Nature's Way 251618/337206: DSLD calls the whole seaweed row "other";
    # its declared 600/580 mg does not disappear when Seaweed Extract is repaired.
    rows = [
        _row("iodine", "Iodine", 270, "mcg", raw_taxonomy={"category": "mineral"}),
        _row(canonical, label, 600, "mg", standardName=standard_name,
             raw_taxonomy={"category": "other", "ingredientGroup": label}),
    ]
    product = {
        "fullName": label, "supplement_taxonomy": {"primary_type": "single_mineral"},
        "ingredient_quality_data": {"ingredients_scorable": rows},
    }
    classification = build_scoring_classification(product)
    assert classification["ingredients"][1]["profile_eligibility"]["botanical"]["eligible"]
    assert classification["profile_eligibility"]["botanical"]["eligible"]
    # Assert the adapter, not an arbitrary target score or an inferred clinical range.
    assert score_dose(product)["metadata"]["method"] == "botanical_clinical_dose_v1"


def test_previous_native_stamp_cannot_hide_the_corrected_seaweed_profile() -> None:
    product = {"fullName": "Kelp", "ingredient_quality_data": {"ingredients_scorable": [
        _row("kelp_powder", "Kelp", 600, "mg", raw_taxonomy={"category": "other"}),
    ]}}
    stale = build_scoring_classification(product, classification_origin="native_enrichment")
    stale["route_decision"]["classifier_version"] = "1.3.0"
    stale["profile_eligibility"]["botanical"]["eligible"] = False
    product["product_scoring_classification"] = stale
    assert build_scoring_classification(product)["profile_eligibility"]["botanical"]["eligible"]


@pytest.mark.parametrize("canonical,label,forms", [
    ("iodine", "Iodine", [{"name": "Kelp", "category": "botanical"}]),
    ("algal_oil", "Algal Oil", [{"name": "Seaweed", "category": "botanical"}]),
    ("astaxanthin", "Astaxanthin", [{"name": "Seaweed", "category": "botanical"}]),
    ("fucoidan", "Fucoidan", [{"name": "Kelp"}]),
    ("fucoxanthin", "Brown Seaweed Fucoxanthin Concentrate",
     [{"name": "Undaria pinnatifida", "category": "other"}]),
    ("generic_active", "Kelproprietary", []),
])
def test_seaweed_source_does_not_turn_a_different_primary_into_whole_seaweed(
    canonical: str, label: str, forms: list[dict],
) -> None:
    row = _row(canonical, label, 100, "mg",
               raw_taxonomy={"category": "other", "forms": forms})
    product = {"fullName": "Seaweed support", "ingredient_quality_data": {"ingredients_scorable": [row]}}
    classification = build_scoring_classification(product)
    assert not classification["ingredients"][0]["profile_eligibility"]["botanical"]["eligible"]
    assert not classification["profile_eligibility"]["botanical"]["eligible"]
