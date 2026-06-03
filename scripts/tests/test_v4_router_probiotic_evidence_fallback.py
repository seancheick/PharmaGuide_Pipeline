"""Regression tests for probiotic routing when taxonomy under-classifies.

The router should not resurrect legacy ``supplement_type`` routing, but it must
not ignore strong probiotic_data evidence either. These cases mirror fresh
catalog artifacts where taxonomy emitted a generic/functional class while the
probiotic enricher correctly extracted strains and CFU data.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scoring_v4.router import class_for_product  # noqa: E402


def _product(**overrides):
    product = {
        "product_name": "FloraSport 20B",
        "primary_type": "general_supplement",
        "probiotic_data": {
            "is_probiotic_product": True,
            "total_strain_count": 5,
            "has_cfu": True,
            "total_cfu": 20_000_000_000,
            "total_billion_count": 20.0,
        },
    }
    product.update(overrides)
    return product


def test_probiotic_data_with_cfu_overrides_underclassified_taxonomy():
    product = _product()

    assert class_for_product(product) == "probiotic"


def test_probiotic_name_plus_named_strains_routes_to_probiotic_for_gate_block():
    product = _product(
        product_name="Skin Squad Pre + Probiotic",
        primary_type="beauty_hair_skin_nails",
        probiotic_data={
            "is_probiotic_product": True,
            "total_strain_count": 10,
            "has_cfu": False,
            "total_cfu": 0,
            "total_billion_count": 0,
        },
    )

    assert class_for_product(product) == "probiotic"


def test_incidental_non_quantified_probiotic_rows_do_not_promote_without_name_or_cfu():
    product = _product(
        product_name="Whole Food Zinc Quercetin Complex",
        primary_type="general_supplement",
        probiotic_data={
            "is_probiotic_product": True,
            "total_strain_count": 5,
            "has_cfu": False,
            "total_cfu": 0,
            "total_billion_count": 0,
        },
    )

    assert class_for_product(product) == "generic"


def test_prebiotic_only_name_does_not_route_to_probiotic_without_probiotic_word():
    product = _product(
        product_name="Daily Prebiotic Fiber",
        primary_type="fiber_digestive",
        probiotic_data={
            "is_probiotic_product": True,
            "total_strain_count": 5,
            "has_cfu": False,
            "total_cfu": 0,
            "total_billion_count": 0,
        },
    )

    assert class_for_product(product) == "generic"


def test_specific_vitamin_mineral_taxonomy_with_low_cfu_adjunct_stays_generic():
    """A tiny probiotic adjunct must not hijack a specific vitamin/mineral SKU."""
    product = _product(
        product_name="Cal-Mag Zinc + D3",
        primary_type="multivitamin",
        probiotic_data={
            "is_probiotic_product": True,
            "total_strain_count": 6,
            "has_cfu": True,
            "total_cfu": 90_000_000,
            "total_billion_count": 0.09,
        },
        ingredient_quality_data={
            "ingredients_scorable": [
                {"canonical_id": "calcium", "quantity": 500, "unit": "mg", "category": "minerals"},
                {"canonical_id": "magnesium", "quantity": 250, "unit": "mg", "category": "minerals"},
                {"canonical_id": "zinc", "quantity": 15, "unit": "mg", "category": "minerals"},
                {"canonical_id": "vitamin_d", "quantity": 400, "unit": "IU", "category": "vitamins"},
                {"canonical_id": "vitamin_k", "quantity": 50, "unit": "mcg", "category": "vitamins"},
                {"canonical_id": "boron", "quantity": 1, "unit": "mg", "category": "minerals"},
            ]
        },
    )

    assert class_for_product(product) == "multi_or_prenatal"


def test_high_cfu_low_adjunct_product_can_still_route_probiotic_without_name():
    """High-CFU products with only a tiny adjunct panel are still probiotic
    even when the taxonomy is functional rather than probiotic."""
    product = _product(
        product_name="Fortify Dual Action Immune Defense 20 Billion",
        primary_type="immune_support",
        probiotic_data={
            "is_probiotic_product": True,
            "total_strain_count": 5,
            "has_cfu": True,
            "total_cfu": 20_000_000_000,
            "total_billion_count": 20.0,
        },
        ingredient_quality_data={
            "ingredients_scorable": [
                {"canonical_id": "vitamin_c", "quantity": 90, "unit": "mg", "category": "vitamins"},
                {"canonical_id": "zinc", "quantity": 10, "unit": "mg", "category": "minerals"},
            ]
        },
    )

    assert class_for_product(product) == "probiotic"


def test_epa_dha_name_without_panel_routes_omega_for_completeness_gate():
    product = {
        "product_name": "Omega-3 EPA/DHA",
        "primary_type": "single_vitamin",
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"canonical_id": "vitamin_a", "quantity": 500, "unit": "IU"},
                {"canonical_id": "vitamin_c", "quantity": 6, "unit": "mg"},
            ],
            "ingredients": [
                {"canonical_id": "vitamin_a", "quantity": 500, "unit": "IU"},
                {"canonical_id": "vitamin_c", "quantity": 6, "unit": "mg"},
            ]
        },
    }

    assert class_for_product(product) == "omega"


def test_efa_blend_with_disclosed_epa_dha_routes_omega_despite_mixed_fatty_acids():
    """EFA products can include borage/evening-primrose/Vit E adjuncts; disclosed
    EPA/DHA plus EFA label intent should still use the omega module."""
    product = {
        "product_name": "EFA Blend for Kids",
        "primary_type": "omega_3",
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"canonical_id": "fish_oil", "quantity": 300, "unit": "mg"},
                {"canonical_id": "epa", "quantity": 50, "unit": "mg"},
                {"canonical_id": "dha", "quantity": 30, "unit": "mg"},
                {"canonical_id": "evening_primrose_oil", "quantity": 50, "unit": "mg"},
                {"canonical_id": "vitamin_e", "quantity": 3, "unit": "mg"},
            ]
        },
    }

    assert class_for_product(product) == "omega"


def test_omega_369_with_disclosed_epa_dha_routes_omega():
    product = {
        "product_name": "Mega Omega 3/6/9",
        "primary_type": "omega_3",
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"canonical_id": "fish_oil", "quantity": 800, "unit": "mg"},
                {"canonical_id": "epa", "quantity": 80, "unit": "mg"},
                {"canonical_id": "dha", "quantity": 60, "unit": "mg"},
                {"canonical_id": "alpha_linolenic_acid", "quantity": 100, "unit": "mg"},
                {"canonical_id": "gamma_linolenic_acid", "quantity": 40, "unit": "mg"},
            ]
        },
    }

    assert class_for_product(product) == "omega"


def test_krill_joint_blend_anchor_routes_generic_not_omega_not_scored():
    product = {
        "product_name": "Krill Healthy Joint Formula",
        "primary_type": "joint_support",
        "form_factor": "softgel",
        "product_scoring_evidence": [
            {
                "evidence_type": "blend_anchor_mass",
                "scoreable": True,
                "scoreable_identity": True,
                "score_eligible_by_cleaner": True,
                "dose_class": "therapeutic_mass",
                "dose_value": 353.0,
                "dose_unit": "mg",
                "source": "active",
                "raw_source_path": "ingredientRows[0]",
                "evidence_scope": "blend_level",
                "linked_rows": ["ingredientRows[0]"],
                "confidence": "medium",
                "reason": "identity_bearing_blend_header_mass",
                "name": "Healthy Joint Proprietary Blend",
                "canonical_id": "healthy_joint_proprietary_blend",
                "clean_identity_id": None,
                "scoring_parent_id": "healthy_joint_proprietary_blend",
                "evidence_canonical_id": "healthy_joint_proprietary_blend",
                "canonical_source_db": "unmapped",
                "evidence_origin": "native_enrichment",
                "source_section": "product",
            }
        ],
    }

    assert class_for_product(product) == "generic"


def test_targeted_three_b_vitamin_product_does_not_route_multi_as_b_complex():
    product = {
        "product_name": "Hair Sweet Hair Berry",
        "primary_type": "b_complex",
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"canonical_id": "vitamin_b12_cobalamin", "quantity": 850, "unit": "mcg"},
                {"canonical_id": "vitamin_b9_folate", "quantity": 500, "unit": "mcg"},
                {"canonical_id": "vitamin_b7_biotin", "quantity": 5000, "unit": "mcg"},
                {"canonical_id": "zinc", "quantity": 20, "unit": "mg"},
                {"canonical_id": "paba", "quantity": 25, "unit": "mg"},
                {"canonical_id": "fo_ti", "quantity": 10, "unit": "mg"},
            ]
        },
    }

    assert class_for_product(product) == "generic"


def test_explicit_b_complex_label_still_routes_multi():
    product = {
        "product_name": "High Potency B-Complex",
        "primary_type": "b_complex",
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"canonical_id": "vitamin_b1_thiamine", "quantity": 10, "unit": "mg"},
                {"canonical_id": "vitamin_b2_riboflavin", "quantity": 10, "unit": "mg"},
                {"canonical_id": "vitamin_b3_niacin", "quantity": 10, "unit": "mg"},
            ]
        },
    }

    assert class_for_product(product) == "multi_or_prenatal"


def test_broad_b_complex_panel_routes_multi_without_explicit_name():
    product = {
        "product_name": "Daily Energy Support",
        "primary_type": "b_complex",
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"canonical_id": "vitamin_b1_thiamine", "quantity": 10, "unit": "mg"},
                {"canonical_id": "vitamin_b2_riboflavin", "quantity": 10, "unit": "mg"},
                {"canonical_id": "vitamin_b3_niacin", "quantity": 10, "unit": "mg"},
                {"canonical_id": "vitamin_b5_pantothenic_acid", "quantity": 10, "unit": "mg"},
                {"canonical_id": "vitamin_b6_pyridoxine", "quantity": 10, "unit": "mg"},
                {"canonical_id": "vitamin_b12_cobalamin", "quantity": 100, "unit": "mcg"},
            ]
        },
    }

    assert class_for_product(product) == "multi_or_prenatal"
