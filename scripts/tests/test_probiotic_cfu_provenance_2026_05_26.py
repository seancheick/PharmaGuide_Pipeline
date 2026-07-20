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


def _cfu_evidence(evidence):
    rows = [row for row in evidence if row.get("evidence_type") == "probiotic_cfu"]
    assert rows, "Expected probiotic_cfu evidence row"
    return rows[0]


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


def test_blend_header_total_does_not_double_count_nested_strain_cfus(enricher):
    """A flattened blend header can carry the aggregate CFU guarantee while
    nested strain rows carry individual CFUs. The header is provenance, not a
    fifth strain, and its total must not stack on top of child CFUs."""
    product = {
        "id": "florasport_like",
        "product_name": "FloraSport 20B",
        "fullName": "Thorne FloraSport 20B",
        "bundleName": "",
        "statements": [],
        "activeIngredients": [
            {
                "name": "Probiotic Blend",
                "standardName": "Probiotic & Microbiome Blends",
                "category": "blend",
                "quantity": 250,
                "unit": "mg",
                "raw_source_path": "ingredientRows[0]",
                "cleaner_row_role": "blend_header_total",
                "hierarchyType": "blend_header",
                "score_exclusion_reason": "blend_header_total",
                "nestedIngredients": [],
                "notes": "20 Billion CFUs, At time of expiration when stored as recommended",
            },
            {
                "name": "Lactobacillus paracasei UALpc-04",
                "standardName": "Lactobacillus Paracasei",
                "category": "bacteria",
                "quantity": 0,
                "unit": "NP",
                "raw_source_path": "ingredientRows[0].nestedRows[0]",
                "parentBlend": "Probiotic Blend",
                "nestedIngredients": [],
                "notes": "5 Billion CFUs",
            },
            {
                "name": "Lactobacillus acidophilus UALa-01",
                "standardName": "Lactobacillus Acidophilus",
                "category": "bacteria",
                "quantity": 0,
                "unit": "NP",
                "raw_source_path": "ingredientRows[0].nestedRows[1]",
                "parentBlend": "Probiotic Blend",
                "nestedIngredients": [],
                "notes": "5 Billion CFUs",
            },
            {
                "name": "Bacillus subtilis DE111",
                "standardName": "Bacillus subtilis DE111",
                "category": "bacteria",
                "quantity": 0,
                "unit": "NP",
                "raw_source_path": "ingredientRows[0].nestedRows[2]",
                "parentBlend": "Probiotic Blend",
                "nestedIngredients": [],
                "notes": "5 Billion CFUs",
            },
            {
                "name": "Bifidobacterium animalis lactis HN019",
                "standardName": "Bifidobacterium Lactis",
                "category": "bacteria",
                "quantity": 0,
                "unit": "NP",
                "raw_source_path": "ingredientRows[0].nestedRows[3]",
                "parentBlend": "Probiotic Blend",
                "nestedIngredients": [],
                "notes": "5 Billion CFUs",
            },
        ],
        "inactiveIngredients": [],
    }

    probiotic_data = enricher._collect_probiotic_data(product)

    assert probiotic_data["is_probiotic_product"] is True
    assert probiotic_data["total_strain_count"] == 4
    assert probiotic_data["total_billion_count"] == pytest.approx(20.0)
    assert probiotic_data["total_cfu"] == pytest.approx(20_000_000_000)
    assert probiotic_data["guarantee_type"] == "at_expiration"
    assert probiotic_data["cfu_raw_source_path"] == "ingredientRows[0]"
    assert probiotic_data["cfu_linked_rows"] == [
        "ingredientRows[0]",
        "ingredientRows[0].nestedRows[0]",
        "ingredientRows[0].nestedRows[1]",
        "ingredientRows[0].nestedRows[2]",
        "ingredientRows[0].nestedRows[3]",
    ]
    assert all(
        "Probiotic Blend" not in (blend.get("strains") or [])
        for blend in probiotic_data["probiotic_blends"]
    )
    assert {
        strain["strain"]: strain["cfu_per_day"]
        for strain in probiotic_data["clinical_strains"]
    }["Bifidobacterium animalis lactis HN019"] == pytest.approx(5_000_000_000)


def test_generic_flattened_header_carries_aggregate_live_cell_guarantee(enricher):
    product = {
        "id": "floramend_like",
        "product_name": "FloraMend Prime Probiotic",
        "statements": [],
        "activeIngredients": [
            {
                "name": "Proprietary Blend",
                "standardName": "General Proprietary Blends",
                "category": "blend",
                "quantity": 0,
                "unit": "NP",
                "raw_source_path": "ingredientRows[0]",
                "cleaner_row_role": "blend_header_total",
                "hierarchyType": "blend_header",
                "score_exclusion_reason": "blend_header_total",
                "nestedIngredients": [],
                "notes": "5 billion live cells at time of expiration",
            },
            {
                "name": "Lactobacillus gasseri KS-13",
                "standardName": "Lactobacillus Gasseri",
                "category": "bacteria",
                "quantity": 0,
                "unit": "NP",
                "raw_source_path": "ingredientRows[0].nestedRows[0]",
                "parentBlend": "Proprietary Blend",
                "nestedIngredients": [],
            },
        ],
        "inactiveIngredients": [],
    }

    probiotic_data = enricher._collect_probiotic_data(product)

    assert probiotic_data["total_strain_count"] == 1
    assert probiotic_data["total_billion_count"] == pytest.approx(5.0)
    assert probiotic_data["guarantee_type"] == "at_expiration"
    assert probiotic_data["cfu_raw_source_path"] == "ingredientRows[0]"


def test_multi_serving_probiotic_uses_canonical_header_without_counting_it_as_strain(enricher):
    """Ages-based label columns are alternatives, never additive strains/CFU."""
    product = {
        "id": "184730_like",
        "product_name": "Probiotic 123",
        "serving_basis": {"canonical_serving_size_quantity": 0.5},
        "statements": [],
        "activeIngredients": [
            {
                "name": "Probiotic Blend",
                "standardName": "Probiotic & Microbiome Blends",
                "category": "blend",
                "raw_source_path": "ingredientRows[0]",
                "cleaner_row_role": "blend_header_total",
                "hierarchyType": "blend_header",
                "score_exclusion_reason": "blend_header_total",
                "raw_taxonomy": {"quantityVariants": [{"serving_size_quantity": 0.25}]},
                "nestedIngredients": [],
                "notes": "Probiotic Blend Note: (providing:) (1.12 billion CFU)",
            },
            {
                "name": "Probiotic Blend",
                "standardName": "Probiotic & Microbiome Blends",
                "category": "blend",
                "raw_source_path": "ingredientRows[1]",
                "cleaner_row_role": "blend_header_total",
                "hierarchyType": "blend_header",
                "score_exclusion_reason": "blend_header_total",
                "raw_taxonomy": {"quantityVariants": [{"serving_size_quantity": 0.5}]},
                "nestedIngredients": [],
                "notes": "Probiotic Blend Note: (providing:) (2.25 billion CFU)",
            },
            {
                "name": "Bifidobacterium bifidum (Bb-06)",
                "standardName": "Bifidobacterium Bifidum",
                "category": "bacteria",
                "raw_source_path": "ingredientRows[1].nestedRows[0]",
                "parentBlend": "Probiotic Blend",
                "nestedIngredients": [],
            },
            {
                "name": "Bifidobacterium lactis (Bl-04)",
                "standardName": "Bifidobacterium Lactis",
                "category": "bacteria",
                "raw_source_path": "ingredientRows[1].nestedRows[1]",
                "parentBlend": "Probiotic Blend",
                "nestedIngredients": [],
            },
            {
                "name": "Lactobacillus acidophilus (La-14)",
                "standardName": "Lactobacillus Acidophilus",
                "category": "bacteria",
                "raw_source_path": "ingredientRows[1].nestedRows[2]",
                "parentBlend": "Probiotic Blend",
                "nestedIngredients": [],
            },
        ],
        "inactiveIngredients": [],
    }

    probiotic_data = enricher._collect_probiotic_data(product)

    assert probiotic_data["total_strain_count"] == 3
    assert probiotic_data["total_billion_count"] == pytest.approx(2.25)
    assert probiotic_data["cfu_linked_rows"] == ["ingredientRows[1]"]
    assert all(
        "Probiotic Blend" not in (blend.get("strains") or [])
        for blend in probiotic_data["probiotic_blends"]
    )


def test_distinct_same_name_blends_without_serving_evidence_remain_additive(enricher):
    product = {
        "id": "two_distinct_blends",
        "product_name": "Two Blend Probiotic",
        "statements": [],
        "activeIngredients": [
            {
                "name": "Probiotic Blend",
                "category": "blend",
                "raw_source_path": "ingredientRows[0]",
                "cleaner_row_role": "blend_header_total",
                "nestedIngredients": [],
                "notes": "1 billion CFU",
            },
            {
                "name": "Lactobacillus acidophilus La-14",
                "category": "bacteria",
                "raw_source_path": "ingredientRows[0].nestedRows[0]",
                "nestedIngredients": [],
            },
            {
                "name": "Probiotic Blend",
                "category": "blend",
                "raw_source_path": "ingredientRows[1]",
                "cleaner_row_role": "blend_header_total",
                "nestedIngredients": [],
                "notes": "2 billion CFU",
            },
            {
                "name": "Bifidobacterium lactis Bl-04",
                "category": "bacteria",
                "raw_source_path": "ingredientRows[1].nestedRows[0]",
                "nestedIngredients": [],
            },
        ],
        "inactiveIngredients": [],
    }

    probiotic_data = enricher._collect_probiotic_data(product)

    assert probiotic_data["total_strain_count"] == 2
    assert probiotic_data["total_billion_count"] == pytest.approx(3.0)
    assert len([
        blend
        for blend in probiotic_data["probiotic_blends"]
        if blend.get("is_blend_header_total")
    ]) == 2


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
        "supplement_taxonomy": {"primary_type": "probiotic"},
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
    cfu = _cfu_evidence(evidence)

    assert cfu["scoreable"] is True
    assert cfu["canonical_id"] == "probiotic_cfu_total"
    assert cfu["clean_identity_id"] is None
    assert cfu["scoring_parent_id"] == "probiotic_cfu_total"
    assert cfu["evidence_canonical_id"] == "probiotic_cfu_total"
    assert cfu["canonical_source_db"] == "probiotic_data"
    assert cfu["evidence_origin"] == "native_enrichment"
    assert cfu["reason"] == "product_level_cfu_with_probiotic_identity"
    assert cfu["confidence"] == "high"


def test_product_cfu_evidence_is_rejected_when_taxonomy_is_not_probiotic(enricher):
    """Source-of-truth gate requires scoreable CFU evidence to agree with
    supplement_taxonomy.primary_type. Probiotic row identity is diagnostic
    only until taxonomy routes the product to the probiotic peer class."""
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
        "supplement_taxonomy": {"primary_type": "fiber_digestive"},
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
    cfu = _cfu_evidence(evidence)

    assert cfu["scoreable"] is False
    assert cfu["scoreable_identity"] is False
    assert cfu["rejection_reason"] == "product_taxonomy_not_probiotic"


def test_fiber_primary_product_with_accessory_probiotics_rejects_cfu_evidence(enricher):
    enriched = {
        "product_name": "Clear Mixing Super Fiber With Probiotics",
        "fullName": "Clear Mixing Super Fiber With Probiotics",
        "activeIngredients": [
            _fiber_row(),
            {
                "name": "LAB4",
                "standardName": "LAB4",
                "quantity": 1_000_000_000,
                "unit": "Viable Cells",
                "score_eligible_by_cleaner": False,
                "cleaner_row_role": "blend_header_total",
            },
        ],
        "probiotic_data": _product_level_probiotic_data(total_cfu=1_000_000_000),
        "supplement_taxonomy": {"primary_type": "fiber_digestive"},
        "ingredient_quality_data": {
            "ingredients_scorable": [],
            "ingredients_skipped": [
                {
                    "name": "Dietary Fiber",
                    "canonical_id": "fiber",
                    "dose_class": "nutrition_fact",
                }
            ],
        },
    }

    evidence = enricher._collect_product_scoring_evidence(enriched)
    cfu = _cfu_evidence(evidence)

    assert cfu["scoreable"] is False
    assert cfu["rejection_reason"] == "non_probiotic_strict_active_present"


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
    cfu = _cfu_evidence(evidence)

    assert cfu["scoreable"] is False
    assert cfu["rejection_reason"] == "non_probiotic_strict_active_present"
