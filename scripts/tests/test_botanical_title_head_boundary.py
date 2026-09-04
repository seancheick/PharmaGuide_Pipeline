"""An ingredient named after a title separator is not the product's head."""

from __future__ import annotations

from copy import deepcopy

import pytest

from scoring_input_contract import build_scoring_classification
from scoring_v4.modules.generic_dose import score_dose


def _row(canonical: str, name: str, amount: float, source_ref: str, **extra) -> dict:
    return {
        "canonical_id": canonical, "name": name, "quantity": amount, "unit": "mg",
        "mapped": True, "source_section": "activeIngredients",
        "raw_source_path": source_ref, "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True, "dose_class": "therapeutic_mass",
        "role_classification": "active_scorable", "scoreable_identity": True,
        **extra,
    }


def _macuguard_product() -> dict:
    # Source-owned 182388 shape: the title names both separate actives AFTER
    # "with". The opaque 173 mg blend is not a disclosed saffron dose.
    return {
        "fullName": "MacuGuard Ocular Support with Saffron & Astaxanthin",
        "ingredient_quality_data": {"ingredients_scorable": [
            _row("saffron", "Saffron extract", 20, "ingredientRows[1]",
                 raw_taxonomy={"category": "botanical", "forms": [{"name": "extract"}]}),
            _row("astaxanthin", "natural Astaxanthin", 6, "ingredientRows[2]",
                 raw_taxonomy={"category": "non-nutrient/non-botanical", "forms": [
                     {"name": "Haematococcus pluvialis algae", "category": "other"},
                 ]}),
            _row("macuguard_proprietary_blend", "MacuGuard Proprietary Blend", 173,
                 "ingredientRows[0]", scoring_input_kind="product_level_evidence",
                 evidence_type="blend_anchor_mass", raw_taxonomy={"category": "blend"}),
        ]},
    }


def test_macuguard_post_separator_saffron_does_not_own_the_profile() -> None:
    product = _macuguard_product()
    original = deepcopy(product)

    classification = build_scoring_classification(product)
    botanical = classification["profile_eligibility"]["botanical"]

    assert botanical["eligible"] is False
    assert botanical["owner_reason_code"] == "nonbotanical_title_head_blocks_botanical"
    assert score_dose(product)["metadata"]["method"] != "botanical_clinical_dose_v1"
    assert product == original


@pytest.mark.parametrize("separator", ["with", "plus", "and", "featuring", "&", "+"])
@pytest.mark.parametrize("additions", ["Saffron & Astaxanthin", "Astaxanthin & Saffron"])
def test_post_separator_word_order_cannot_create_a_botanical_head(
    separator: str, additions: str,
) -> None:
    product = _macuguard_product()
    product["fullName"] = f"MacuGuard Ocular Support {separator} {additions}"

    botanical = build_scoring_classification(product)["profile_eligibility"]["botanical"]

    assert botanical["eligible"] is False
    assert botanical["owner_reason_code"] == "nonbotanical_title_head_blocks_botanical"


@pytest.mark.parametrize("title,eligible", [
    ("Saffron with Astaxanthin", True),
    ("Saffron plus Astaxanthin", True),
    ("Saffron & Astaxanthin", True),
    ("Saffron Astaxanthin", True),
    ("Astaxanthin Saffron", False),
    ("Astaxanthin with Saffron", False),
    ("Astaxanthin & Saffron", False),
    ("Saffron Astaxanthin with Other Ingredients", True),
    ("Astaxanthin Saffron with Other Ingredients", False),
])
def test_genuine_title_head_and_head_ties_preserve_precedence(
    title: str, eligible: bool,
) -> None:
    product = _macuguard_product()
    product["fullName"] = title
    product["ingredient_quality_data"]["ingredients_scorable"].pop()

    assert build_scoring_classification(product)["profile_eligibility"]["botanical"]["eligible"] is eligible


def test_material_standardized_botanical_still_owns_without_being_title_head() -> None:
    # "After with" is not a claim that the ingredient is immaterial. The
    # existing standardized/material-owner branch must retain its authority.
    product = {
        "fullName": "Formula with Elderberry & Zinc",
        "ingredient_quality_data": {"ingredients_scorable": [
            _row("elderberry", "Elderberry Extract", 1000, "ingredientRows[0]",
                 raw_taxonomy={"category": "botanical"}),
            _row("zinc", "Zinc", 15, "ingredientRows[1]",
                 raw_taxonomy={"category": "mineral"}),
        ]},
        "formulation_data": {"standardized_botanicals": [
            {"name": "Elderberry Extract", "botanical_id": "elderberry"},
        ]},
    }

    botanical = build_scoring_classification(product)["profile_eligibility"]["botanical"]

    assert botanical["eligible"] is True
    assert botanical["owner_reason_code"] == "standardized_botanical_owner"
