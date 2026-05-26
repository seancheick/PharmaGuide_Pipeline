"""Wave 6.Z probiotic CFU provenance regression locks."""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture
def enricher():
    return SupplementEnricherV3()


def _product_level_probiotic_data(total_cfu=20_000_000_000):
    return {
        "is_probiotic_product": True,
        "has_cfu": True,
        "total_cfu": total_cfu,
        "total_strain_count": 3,
        "probiotic_blends": [
            {"name": "Probiotic Blend", "raw_source_path": "activeIngredients[1]"}
        ],
        "cfu_source": "product_identity",
        "cfu_raw_source_path": "fullName",
        "cfu_evidence_scope": "product_level",
        "cfu_linked_rows": ["fullName"],
    }


def _fiber_row():
    return {
        "name": "Dietary Fiber",
        "standardName": "Dietary Fiber",
        "canonical_id": "fiber",
        "quantity": 5,
        "unit": "g",
        "score_eligible_by_cleaner": True,
        "cleaner_row_role": "active_scorable",
    }


def test_product_name_cfu_guarantee_populates_product_level_provenance(enricher):
    product = {
        "id": "garden_of_life_name_cfu",
        "product_name": "Dr. Formulated Probiotics Daily Care 25 Billion CFU Guaranteed",
        "fullName": "Garden of Life Dr. Formulated Probiotics Daily Care 25 Billion CFU Guaranteed",
        "bundleName": "",
        "statements": [],
        "activeIngredients": [
            {
                "name": "Daily Probiotic Blend",
                "standardName": "Probiotic Blend",
                "category": "probiotic",
                "quantity": 0,
                "unit": "NP",
                "raw_source_path": "activeIngredients[0]",
                "nestedIngredients": [
                    {"name": "Lactobacillus acidophilus"},
                    {"name": "Bifidobacterium lactis"},
                    {"name": "Lactobacillus plantarum"},
                ],
                "harvestMethod": "",
                "notes": "",
            }
        ],
        "inactiveIngredients": [],
    }

    probiotic_data = enricher._collect_probiotic_data(product)

    assert probiotic_data["is_probiotic_product"] is True
    assert probiotic_data["has_cfu"] is True
    assert probiotic_data["total_cfu"] == pytest.approx(25_000_000_000)
    assert probiotic_data["total_billion_count"] == pytest.approx(25.0)
    assert probiotic_data["cfu_source"] == "product_identity"
    assert probiotic_data["cfu_raw_source_path"] in {"product_name", "fullName"}
    assert probiotic_data["cfu_evidence_scope"] == "product_level"
    assert probiotic_data["cfu_raw_source_path"] in probiotic_data["cfu_linked_rows"]


def test_fiber_support_row_does_not_block_probiotic_cfu_product_evidence(enricher):
    enriched = {
        "activeIngredients": [
            _fiber_row(),
            {
                "name": "Probiotic Blend",
                "standardName": "Probiotic Blend",
                "canonical_id": "probiotics",
                "quantity": 100,
                "unit": "mg",
                "score_eligible_by_cleaner": False,
                "cleaner_row_role": "blend_header_total",
            },
        ],
        "probiotic_data": _product_level_probiotic_data(),
        "supplement_taxonomy": {"primary_type": "general_supplement"},
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {
                    "name": "Dietary Fiber",
                    "canonical_id": "fiber",
                    "dose_class": "nutrition_fact",
                }
            ]
        },
    }

    evidence = enricher._collect_product_scoring_evidence(enriched)

    assert evidence[0]["scoreable"] is True
    assert evidence[0]["canonical_id"] == "probiotic_cfu_total"
    assert evidence[0]["reason"] == "product_level_cfu_with_probiotic_row_identity"
    assert evidence[0]["confidence"] == "high"


def test_unrelated_strict_active_still_rejects_accessory_probiotic_cfu(enricher):
    enriched = {
        "activeIngredients": [
            {
                "name": "Vitamin C",
                "standardName": "Vitamin C",
                "canonical_id": "vitamin_c",
                "quantity": 500,
                "unit": "mg",
                "score_eligible_by_cleaner": True,
                "cleaner_row_role": "active_scorable",
            }
        ],
        "probiotic_data": _product_level_probiotic_data(total_cfu=5_000_000_000),
        "supplement_taxonomy": {"primary_type": "general_supplement"},
        "ingredient_quality_data": {"ingredients_scorable": []},
    }

    evidence = enricher._collect_product_scoring_evidence(enriched)

    assert evidence[0]["scoreable"] is False
    assert evidence[0]["rejection_reason"] == "non_probiotic_strict_active_present"
