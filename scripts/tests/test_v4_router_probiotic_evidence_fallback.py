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
