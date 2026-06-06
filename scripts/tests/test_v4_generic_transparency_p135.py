"""v4 Generic Transparency dimension — P1.3.5 tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _opaque_blend(
    *,
    name: str = "Proprietary Blend",
    total_mg: float = 500.0,
    hidden_count: int = 4,
    disclosure_level: str = "none",
) -> dict:
    return {
        "name": name,
        "disclosure_level": disclosure_level,
        "blend_total_mg": total_mg,
        "hidden_count": hidden_count,
        "nested_count": hidden_count,
        "sources": ["detector", "cleaning"],
        "source_field": "activeIngredients",
        "source_path": "activeIngredients[0]",
    }


def _partial_blend(
    *,
    name: str = "Energy Blend",
    total_mg: float = 1000.0,
    disclosed_children_mg: float = 200.0,
    hidden_count: int = 3,
) -> dict:
    return {
        "name": name,
        "disclosure_level": "partial",
        "blend_total_mg": total_mg,
        "hidden_count": hidden_count,
        "nested_count": hidden_count,
        "child_ingredients": [
            {"name": "Disclosed Child", "amount": disclosed_children_mg, "unit": "mg"}
        ],
        "evidence": {
            "ingredients_without_amounts": [
                {"name": f"Hidden Child {idx}"} for idx in range(hidden_count)
            ]
        },
        "sources": ["detector", "cleaning"],
        "source_field": "activeIngredients",
        "source_path": "activeIngredients[0]",
    }


def _full_blend() -> dict:
    return {
        "name": "Transparent Blend",
        "disclosure_level": "full",
        "blend_total_mg": 500.0,
        "hidden_count": 0,
        "nested_count": 0,
        "child_ingredients": [
            {"name": "C1", "amount": 200, "unit": "mg"},
            {"name": "C2", "amount": 300, "unit": "mg"},
        ],
        "sources": ["cleaning"],
        "source_field": "activeIngredients",
        "source_path": "activeIngredients[0]",
    }


def _ingredient(name: str = "Magnesium", standard_name: str | None = None) -> dict:
    return {
        "name": name,
        "standard_name": standard_name or name,
        "mapped": True,
        "canonical_id": (standard_name or name).lower().replace(" ", "_"),
        "quantity": 200,
        "unit": "mg",
    }


def _probiotic_ingredient() -> dict:
    return {
        "name": "Lactobacillus rhamnosus GG",
        "standard_name": "Lactobacillus rhamnosus GG",
        "mapped": True,
        "canonical_id": "lactobacillus_rhamnosus_gg",
        "category": "probiotic",
        "quantity": 10,
        "unit": "billion CFU",
    }


def _product(
    *,
    blends: list | None = None,
    supp_type: str | None = "single_nutrient",
    product_name: str = "Example Product",
    primary_category: str | None = None,
    total_active_mg: float = 2000.0,
    total_active_ingredients: int = 5,
    compliance_data: dict | None = None,
    allergens: list | None = None,
    top_level: dict | None = None,
) -> dict:
    if supp_type == "probiotic":
        rows = [_probiotic_ingredient()]
        if product_name == "Example Product":
            product_name = "Example Probiotic"
    else:
        rows = [_ingredient()]
        if supp_type == "multivitamin" and product_name == "Example Product":
            product_name = "Example Multivitamin"
    primary_type_by_supp_type = {
        "probiotic": "probiotic",
        "multivitamin": "multivitamin",
        "single_nutrient": "single_mineral",
        "specialty": "general_supplement",
    }
    product = {
        "status": "active",
        "form_factor": "capsule",
        "product_name": product_name,
        "fullName": product_name,
        "brand_name": "Example Brand",
        "supplement_taxonomy": {
            "primary_type": primary_type_by_supp_type.get(supp_type or "", "general_supplement")
        },
        "supplement_type": {"type": supp_type} if supp_type is not None else {},
        "primary_category": primary_category or "",
        "ingredient_quality_data": {
            "total_active": total_active_ingredients,
            "ingredients_scorable": rows,
            "ingredients": rows,
        },
        "proprietary_blends": blends or [],
        "proprietary_data": {
            "blends": blends or [],
            "total_active_mg": total_active_mg,
            "total_active_ingredients": total_active_ingredients,
        },
        "probiotic_data": {
            "is_probiotic_product": True,
            "total_strain_count": 1,
            "has_cfu": True,
            "total_billion_count": 10,
        } if supp_type == "probiotic" else {},
        "contaminant_data": {
            "allergens": {"found": bool(allergens), "allergens": allergens or []}
        },
        "compliance_data": compliance_data
        or {
            "allergen_free_claims": [],
            "gluten_free": False,
            "vegan": False,
            "vegetarian": False,
            "conflicts": [],
            "has_may_contain_warning": False,
        },
    }
    if top_level:
        product.update(top_level)
    return product


def test_transparency_payload_shape_and_phase() -> None:
    from scoring_v4.modules.generic_transparency import score_transparency

    payload = score_transparency(_product())

    assert payload["score"] == 6.0
    assert payload["max"] == 10.0
    assert payload["components"]["clear_disclosure_base"] == 6.0
    assert payload["components"]["complete_active_identity_dose_disclosure"] == 0.0
    assert payload["components"]["B3_claim_compliance"] == 0.0
    assert payload["penalties"]["B2_false_allergen_free_claim"] == 0.0
    assert payload["penalties"]["B5_proprietary_blend_opacity"] == 0.0
    assert payload["penalties"]["B6_marketing_claims"] == 0.0
    assert payload["phase"] == "P1.3.5_transparency"
    assert payload["metadata"]["phase"] == "P1.3.5_transparency"
    assert payload["metadata"]["complete_active_disclosure"]["qualifies"] is False
    assert payload["metadata"]["complete_active_disclosure"]["blockers"] == [
        "declared_count_exceeds_rows",
        "incomplete_active_rows",
    ]


def test_complete_single_active_identity_and_dose_earns_disclosure_credit() -> None:
    from scoring_v4.modules.generic_transparency import score_transparency

    payload = score_transparency(
        _product(total_active_ingredients=1, total_active_mg=200.0)
    )

    assert payload["components"]["clear_disclosure_base"] == 6.0
    assert payload["components"]["complete_active_identity_dose_disclosure"] == 3.0
    assert payload["components"]["B3_claim_compliance"] == 0.0
    assert payload["score"] == 9.0
    assert payload["metadata"]["complete_active_disclosure"] == {
        "qualifies": True,
        "bonus": 3.0,
        "declared_active_count": 1,
        "active_row_count": 1,
        "complete_row_count": 1,
        "blockers": [],
        "incomplete_rows": [],
    }


def test_complete_active_disclosure_credit_requires_usable_dose() -> None:
    from scoring_v4.modules.generic_transparency import score_transparency

    product = _product(total_active_ingredients=1, total_active_mg=0.0)
    row = product["ingredient_quality_data"]["ingredients_scorable"][0]
    row["quantity"] = None
    row["unit"] = ""

    payload = score_transparency(product)

    assert payload["components"]["complete_active_identity_dose_disclosure"] == 0.0
    assert payload["score"] == 6.0
    assert payload["metadata"]["complete_active_disclosure"]["qualifies"] is False
    assert payload["metadata"]["complete_active_disclosure"]["blockers"] == [
        "incomplete_active_rows"
    ]
    assert payload["metadata"]["complete_active_disclosure"]["incomplete_rows"][0]["blockers"] == [
        "missing_usable_dose"
    ]


def test_complete_active_disclosure_credit_blocked_by_proprietary_opacity() -> None:
    from scoring_v4.modules.generic_transparency import score_transparency

    payload = score_transparency(
        _product(
            blends=[_opaque_blend()],
            total_active_ingredients=1,
            total_active_mg=500.0,
        )
    )

    assert payload["components"]["complete_active_identity_dose_disclosure"] == 0.0
    assert "proprietary_blend_opacity" in payload["metadata"]["complete_active_disclosure"]["blockers"]


def test_complete_active_disclosure_and_claims_still_cap_at_ten() -> None:
    from scoring_v4.modules.generic_transparency import score_transparency

    compliance = {
        "allergen_free_claims": [{"validated": True, "allergen": "dairy"}],
        "gluten_free": True,
        "vegan": True,
        "vegetarian": False,
        "conflicts": [],
        "has_may_contain_warning": False,
    }

    payload = score_transparency(
        _product(total_active_ingredients=1, total_active_mg=200.0, compliance_data=compliance)
    )

    assert payload["components"]["complete_active_identity_dose_disclosure"] == 3.0
    assert payload["components"]["B3_claim_compliance"] == 4.0
    assert payload["metadata"]["raw_transparency"] == 13.0
    assert payload["metadata"]["cap_applied"] is True
    assert payload["score"] == 10.0


def test_valid_claims_can_reach_full_transparency_score() -> None:
    from scoring_v4.modules.generic_transparency import score_transparency

    compliance = {
        "allergen_free_claims": [{"validated": True, "allergen": "dairy"}],
        "gluten_free": True,
        "vegan": True,
        "vegetarian": False,
        "conflicts": [],
        "has_may_contain_warning": False,
    }

    payload = score_transparency(_product(compliance_data=compliance))

    assert payload["components"]["B3_claim_compliance"] == 4.0
    assert payload["score"] == 10.0
    assert payload["metadata"]["claim_validations"] == {
        "allergen_free": True,
        "gluten_free": True,
        "vegan_or_vegetarian": True,
    }


def test_disclosed_allergen_without_free_claim_has_no_transparency_penalty() -> None:
    from scoring_v4.modules.generic_transparency import score_transparency

    payload = score_transparency(
        _product(
            allergens=[
                {"allergen_name": "Milk", "severity_level": "high"},
                {"allergen_name": "Soy", "severity_level": "moderate"},
            ],
        )
    )

    assert payload["penalties"]["B2_false_allergen_free_claim"] == 0.0
    assert payload["metadata"]["B2_seen_allergens"] == {"milk": 2.0, "soy": 1.5}
    assert payload["metadata"]["matched_false_claim_groups"] == []


def test_false_allergen_free_claim_penalty_deduplicates_and_blocks_bonus() -> None:
    from scoring_v4.modules.generic_transparency import score_transparency

    compliance = {
        "allergen_free_claims": [{"validated": True, "allergen": "dairy"}],
        "gluten_free": False,
        "vegan": False,
        "vegetarian": False,
        "conflicts": [],
        "has_may_contain_warning": False,
    }
    payload = score_transparency(
        _product(
            compliance_data=compliance,
            allergens=[
                {"allergen_name": "Milk", "severity_level": "high"},
                {"allergen_name": "Milk", "severity_level": "high"},
                {"allergen_name": "Soy", "severity_level": "moderate"},
            ],
        )
    )

    assert payload["penalties"]["B2_false_allergen_free_claim"] == -2.0
    assert payload["components"]["B3_claim_compliance"] == 0.0
    assert payload["metadata"]["B2_raw_before_cap"] == pytest.approx(2.0)
    assert payload["metadata"]["claim_validations"]["allergen_free"] is False
    assert payload["metadata"]["matched_false_claim_groups"] == ["dairy"]


def test_gluten_free_claim_penalizes_wheat_or_barley_conflict_only() -> None:
    from scoring_v4.modules.generic_transparency import score_transparency

    gluten_conflict = score_transparency(
        _product(
            compliance_data={
                "allergen_free_claims": [],
                "gluten_free": True,
                "vegan": False,
                "vegetarian": False,
                "conflicts": ["gluten-free claim conflicts with detected gluten/wheat"],
                "has_may_contain_warning": False,
            },
            allergens=[{"allergen_name": "Kamut", "severity_level": "high"}],
        )
    )
    dairy_present = score_transparency(
        _product(
            compliance_data={
                "allergen_free_claims": [],
                "gluten_free": True,
                "vegan": False,
                "vegetarian": False,
                "conflicts": [],
                "has_may_contain_warning": False,
            },
            allergens=[{"allergen_name": "Milk", "severity_level": "high"}],
        )
    )

    assert gluten_conflict["penalties"]["B2_false_allergen_free_claim"] == -2.0
    assert dairy_present["penalties"]["B2_false_allergen_free_claim"] == 0.0
    assert dairy_present["metadata"]["claim_validations"]["gluten_free"] is True


def test_label_contradiction_blocks_gluten_and_vegan_claims() -> None:
    from scoring_v4.modules.generic_transparency import score_transparency

    payload = score_transparency(
        _product(
            compliance_data={
                "allergen_free_claims": [],
                "gluten_free": True,
                "vegan": True,
                "vegetarian": False,
                "conflicts": ["contains wheat", "contains gelatin"],
                "has_may_contain_warning": False,
            }
        )
    )

    assert payload["components"]["B3_claim_compliance"] == 0.0
    assert "LABEL_CONTRADICTION_DETECTED" in payload["metadata"]["flags"]


def test_disease_claim_penalty_uses_b6_and_floors_score_not_below_zero() -> None:
    from scoring_v4.modules.generic_transparency import score_transparency

    payload = score_transparency(
        _product(
            top_level={"has_disease_claims": True},
            blends=[_opaque_blend(name=f"Energy Matrix {idx}") for idx in range(4)],
            product_name="MegaPre Pre-Workout",
            supp_type="specialty",
        )
    )

    assert payload["penalties"]["B6_marketing_claims"] == -5.0
    assert payload["penalties"]["B5_proprietary_blend_opacity"] == -10.0
    assert payload["score"] == 0.0
    assert "DISEASE_CLAIM_DETECTED" in payload["metadata"]["flags"]


def test_b5_generic_opaque_blend_matches_v3_penalty_inside_transparency() -> None:
    from scoring_v4.modules.generic_transparency import score_transparency

    payload = score_transparency(_product(blends=[_opaque_blend()]))

    assert payload["penalties"]["B5_proprietary_blend_opacity"] == pytest.approx(-3.25)
    assert payload["score"] == pytest.approx(2.75)


def test_b5_probiotic_multiplier_is_soft_not_zero() -> None:
    from scoring_v4.modules.generic_transparency import score_transparency

    payload = score_transparency(
        _product(blends=[_opaque_blend()], supp_type="probiotic")
    )

    assert payload["penalties"]["B5_proprietary_blend_opacity"] == pytest.approx(-1.3)
    assert payload["metadata"]["B5_blend_evidence"][0]["blend_class"] == "probiotic"
    assert payload["metadata"]["B5_blend_evidence"][0]["class_multiplier_applied"] == 0.4


def test_b5_multivitamin_and_sports_multipliers_apply() -> None:
    from scoring_v4.modules.generic_transparency import score_transparency

    multi = score_transparency(
        _product(blends=[_opaque_blend()], supp_type="multivitamin")
    )
    sports = score_transparency(
        _product(
            blends=[_opaque_blend()],
            supp_type="specialty",
            product_name="Hyper Pre-Workout Energy Matrix",
        )
    )

    assert multi["penalties"]["B5_proprietary_blend_opacity"] == pytest.approx(-4.225)
    assert sports["penalties"]["B5_proprietary_blend_opacity"] == pytest.approx(-4.875)


def test_b5_full_disclosure_blend_has_no_opacity_penalty() -> None:
    from scoring_v4.modules.generic_transparency import score_transparency

    payload = score_transparency(_product(blends=[_full_blend()]))

    assert payload["penalties"]["B5_proprietary_blend_opacity"] == 0.0
    assert payload["score"] == 6.0


def test_b5_partial_blend_uses_hidden_mass_share() -> None:
    from scoring_v4.modules.generic_transparency import score_transparency

    payload = score_transparency(_product(blends=[_partial_blend()]))

    assert payload["penalties"]["B5_proprietary_blend_opacity"] == pytest.approx(-2.2)
    evidence = payload["metadata"]["B5_blend_evidence"][0]
    assert evidence["impact_source"] == "mg_share"
    assert evidence["hidden_mass_mg"] == 800.0


def test_b5_dedupes_detector_placeholder_when_cleaned_blend_exists() -> None:
    from scoring_v4.modules.generic_transparency import score_transparency

    detector_placeholder = {
        "name": "Superfood, Greens & Herbal Blends",
        "disclosure_level": "none",
        "source_field": "activeIngredients[19]",
        "source_path": "activeIngredients[19]",
        "sources": ["detector"],
        "evidence": {
            "blend_id": "BLEND_SUPERFOOD",
            "matched_text": "Organic Fruit & Vegetable Blend",
            "source_field": "activeIngredients[19]",
        },
    }
    cleaned_blend = {
        "name": "Raw Organic Fruit & Vegetable Blend",
        "disclosure_level": "partial",
        "blend_total_mg": 20.0,
        "total_weight": 20.0,
        "unit": "mg",
        "source_field": "activeIngredients[19]",
        "source_path": "activeIngredients[19]",
        "sources": ["cleaning"],
    }

    payload = score_transparency(_product(
        blends=[detector_placeholder, cleaned_blend],
        supp_type="multivitamin",
        total_active_mg=200.0,
        total_active_ingredients=46,
    ))

    evidence = payload["metadata"]["B5_blend_evidence"]
    assert len(evidence) == 1
    assert evidence[0]["blend_name"] == "Raw Organic Fruit & Vegetable Blend"
    assert payload["penalties"]["B5_proprietary_blend_opacity"] == pytest.approx(-1.69)


def test_b5_dedupes_parent_and_child_rows_for_same_blend_total() -> None:
    from scoring_v4.modules.generic_transparency import score_transparency

    parent = {
        "name": "Raw Organic Fruit & Vegetable Blend",
        "disclosure_level": "partial",
        "blend_total_mg": 20.0,
        "total_weight": 20.0,
        "unit": "mg",
        "source_field": "activeIngredients[19]",
        "source_path": "activeIngredients[19]",
        "sources": ["cleaning"],
    }
    child_list = {
        "name": "Raw Organic Fruit & Vegetable Blend",
        "disclosure_level": "none",
        "blend_total_mg": 20.0,
        "total_weight": 20.0,
        "unit": "mg",
        "hidden_count": 3,
        "nested_count": 3,
        "source_field": "activeIngredients[20]",
        "source_path": "activeIngredients[20]",
        "sources": ["cleaning"],
        "child_ingredients": [
            {"name": "Broccoli", "amount": None, "unit": ""},
            {"name": "Apple", "amount": None, "unit": ""},
            {"name": "Carrot", "amount": None, "unit": ""},
        ],
    }

    payload = score_transparency(_product(
        blends=[parent, child_list],
        supp_type="multivitamin",
        total_active_mg=200.0,
        total_active_ingredients=46,
    ))

    evidence = payload["metadata"]["B5_blend_evidence"]
    assert len(evidence) == 1
    assert evidence[0]["disclosure_tier"] == "partial"
    assert evidence[0]["children_without_amount_count"] == 3
    assert payload["penalties"]["B5_proprietary_blend_opacity"] == pytest.approx(-1.69)


def test_b5_trivial_non_safety_micro_blend_is_discounted() -> None:
    """A sub-milligram carotenoid carrier blend in a multi/prenatal is a label
    clarity limitation, not the same opacity risk as a real hidden formula."""
    from scoring_v4.modules.generic_transparency import score_transparency

    blend = {
        "name": "Mixed Carotenoid Blend",
        "disclosure_level": "partial",
        "blend_total_mg": 0.45,
        "total_weight": 0.45,
        "unit": "mg",
        "hidden_count": 2,
        "nested_count": 2,
        "source_field": "activeIngredients[22]",
        "source_path": "activeIngredients[22]",
        "sources": ["cleaning"],
        "child_ingredients": [
            {"name": "Lutein", "amount": None, "unit": ""},
            {"name": "Zeaxanthin", "amount": None, "unit": ""},
        ],
    }

    payload = score_transparency(_product(
        blends=[blend],
        supp_type="multivitamin",
        total_active_mg=800.0,
        total_active_ingredients=24,
    ))

    evidence = payload["metadata"]["B5_blend_evidence"][0]
    assert evidence["hidden_mass_mg"] == 0.45
    assert evidence["trivial_micro_blend_discount_applied"] is True
    assert evidence["computed_blend_penalty_magnitude"] == 0.0
    assert payload["penalties"]["B5_proprietary_blend_opacity"] == 0.0


def test_b5_trivial_micro_blend_discount_does_not_apply_to_stimulants() -> None:
    from scoring_v4.modules.generic_transparency import score_transparency

    blend = {
        "name": "Caffeine Energy Matrix",
        "disclosure_level": "partial",
        "blend_total_mg": 0.45,
        "total_weight": 0.45,
        "unit": "mg",
        "hidden_count": 1,
        "nested_count": 1,
        "source_field": "activeIngredients[2]",
        "source_path": "activeIngredients[2]",
        "sources": ["cleaning"],
        "child_ingredients": [{"name": "Caffeine", "amount": None, "unit": ""}],
    }

    payload = score_transparency(_product(
        blends=[blend],
        supp_type="multivitamin",
        total_active_mg=800.0,
        total_active_ingredients=24,
    ))

    evidence = payload["metadata"]["B5_blend_evidence"][0]
    assert evidence["trivial_micro_blend_discount_applied"] is False
    assert payload["penalties"]["B5_proprietary_blend_opacity"] == pytest.approx(-1.69)


def test_shadow_wires_transparency_dimension_when_generic_module_runs() -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    out = score_product_v4_shadow(_product())
    dim = out["shadow_score_v4_breakdown"]["module"]["dimensions"]["transparency"]

    assert dim["score"] == 6.0
    assert dim["components"]["clear_disclosure_base"] == 6.0
    assert dim["metadata"]["phase"] == "P1.3.5_transparency"


def test_transparency_module_does_not_import_v3_scorer() -> None:
    import scoring_v4.modules.generic_transparency as module

    source = Path(module.__file__).read_text()
    assert "from score_supplements" not in source
    assert "import score_supplements" not in source
