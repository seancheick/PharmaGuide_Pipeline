"""Fiber/digestive v4 module calibration tests.

The fiber category should not be scored as a generic capsule. A well-labeled
psyllium/acacia fiber should be able to score strongly, while underdosed gummies
or stimulant-laxative blends should remain low.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from score_supplements_v4 import score_product_v4  # noqa: E402
from scoring_v4.modules.fiber_digestive import score_fiber_digestive  # noqa: E402
from scoring_v4.modules.fiber_digestive_dose import score_dose  # noqa: E402


def _row(
    canonical_id: str,
    quantity: float,
    unit: str = "Gram(s)",
    *,
    name: str | None = None,
    category: str = "fiber",
    bio_score: float = 12.0,
    proprietary: bool = False,
) -> dict:
    label = name or canonical_id.replace("_", " ").title()
    return {
        "name": label,
        "standard_name": label,
        "canonical_id": canonical_id,
        "quantity": quantity,
        "unit": unit,
        "unit_normalized": unit.lower(),
        "category": category,
        "bio_score": bio_score,
        "matched_form": label.lower(),
        "raw_source_text": label,
        "mapped": True,
        "mapped_identity": True,
        "scoreable_identity": True,
        "score_eligible_by_cleaner": True,
        "role_classification": "active_scorable",
        "cleaner_row_role": "active_scorable",
        "source_section": "active",
        "is_proprietary_blend": proprietary,
        "is_parent_total": False,
    }


def _match(
    *,
    ingredient: str = "Psyllium",
    canonical_id: str = "psyllium",
    study_type: str = "rct_multiple",
    evidence_level: str = "ingredient-human",
) -> dict:
    return {
        "id": f"INGR_{canonical_id.upper()}",
        "ingredient": ingredient,
        "standard_name": ingredient,
        "canonical_id": canonical_id,
        "study_type": study_type,
        "evidence_level": evidence_level,
        "effect_direction": "positive_strong",
        "total_enrollment": 500,
    }


def _fiber_product(
    rows: list[dict],
    *,
    name: str = "PharmaGuide Benchmark Psyllium Fiber",
    dietary_fiber_g: float | None = 8.0,
    sugar: dict | None = None,
    sweeteners: dict | None = None,
    additives: list[dict] | None = None,
    matches: list[dict] | None = None,
) -> dict:
    return {
        "id": 910001,
        "dsld_id": "910001",
        "fullName": name,
        "product_name": name,
        "brandName": "PharmaGuide Benchmark",
        "primary_type": "fiber_digestive",
        "supplement_taxonomy": {
            "primary_type": "fiber_digestive",
            "percentile_category": "fiber_digestive",
        },
        "form_factor": "powder",
        "form_factor_canonical": "powder",
        "status": "active",
        "ingredient_quality_data": {
            "ingredients_scorable": rows,
            "ingredients": rows,
        },
        "nutrition_summary": {
            "dietary_fiber_g": dietary_fiber_g,
            "total_sugars_g": 0.0 if sugar is None else sugar.get("amount_g"),
        },
        "nutrition_detail": {
            "dietary_fiber_g": dietary_fiber_g,
            "total_sugars_g": 0.0 if sugar is None else sugar.get("amount_g"),
        },
        "dietary_sensitivity_data": {
            "sugar": sugar
            or {
                "amount_g": 0.0,
                "level": "sugar_free",
                "contains_sugar": False,
                "has_added_sugar": False,
                "sugar_sources": [],
            },
            "sweeteners": sweeteners
            or {
                "artificial": [],
                "high_glycemic": [],
                "sugar_alcohols": [],
                "safer_alternatives": [],
            },
        },
        "contaminant_data": {
            "harmful_additives": {
                "found": bool(additives),
                "additives": additives or [],
            },
            "banned_substances": {"found": False, "substances": []},
        },
        "proprietary_blends": [],
        "proprietary_data": {"blends": [], "total_active_ingredients": len(rows)},
        "evidence_data": {"clinical_matches": matches or [_match()]},
    }


def test_clean_psyllium_fiber_routes_to_dedicated_module_and_scores_strong() -> None:
    product = _fiber_product([_row("psyllium", 8.0, name="Psyllium Husk")])

    out = score_product_v4(product)

    assert out["v4_module"] == "fiber_digestive"
    assert out["v4_breakdown"]["module"]["module"] == "fiber_digestive"
    assert out["quality_score_v4_100"] >= 88.0
    dose = out["v4_breakdown"]["module"]["dimensions"]["dose"]
    assert dose["metadata"]["method"] == "fiber_effective_dose_v1"
    assert dose["components"]["fiber_effective_dose"] >= 22.0


def test_under_dosed_fiber_gummy_stays_low_despite_category_membership() -> None:
    product = _fiber_product(
        [_row("fiber", 0.8, name="Soluble Corn Fiber")],
        name="Fiber Candy Gummies",
        dietary_fiber_g=0.8,
        sugar={
            "amount_g": 6.0,
            "level": "high",
            "contains_sugar": True,
            "has_added_sugar": True,
            "sugar_sources": ["glucose syrup"],
        },
        sweeteners={
            "artificial": ["sucralose"],
            "high_glycemic": ["glucose syrup"],
            "sugar_alcohols": ["maltitol"],
            "safer_alternatives": [],
        },
        additives=[
            {
                "additive_id": "ADD_RED_40",
                "severity_level": "moderate",
                "source_section": "inactive",
            }
        ],
        matches=[],
    )

    result = score_fiber_digestive(product)
    breakdown = result.to_breakdown()

    assert result.score_100 < 55.0
    assert breakdown["dimensions"]["dose"]["score"] < 8.0
    assert breakdown["dimensions"]["formulation"]["penalties"]["fiber_gummy_delivery_penalty"] < 0


def test_stimulant_laxative_cleanse_is_not_rewarded_as_fiber() -> None:
    product = _fiber_product(
        [
            _row("psyllium", 2.0, name="Psyllium Husk"),
            _row("senna", 20.0, "mg", name="Senna Leaf", category="herb", bio_score=6),
            _row("cascara_sagrada", 20.0, "mg", name="Cascara Sagrada", category="herb", bio_score=6),
        ],
        name="Fiber Cleanse Detox",
        dietary_fiber_g=2.0,
        matches=[],
    )

    result = score_fiber_digestive(product)
    formulation = result.to_breakdown()["dimensions"]["formulation"]

    assert result.score_100 < 65.0
    assert formulation["penalties"]["fiber_stimulant_laxative_penalty"] < 0
    assert formulation["metadata"]["fiber_profile_applied"] is True


def test_fiber_dose_prefers_label_fiber_grams_over_active_mass_noise() -> None:
    product = _fiber_product(
        [
            _row("psyllium", 500.0, "mg", name="Psyllium Husk"),
            _row("natural_flavor", 2.0, "mg", name="Natural Flavor", category="other", bio_score=0),
        ],
        dietary_fiber_g=7.0,
    )

    dose = score_dose(product)

    assert dose["score"] >= 22.0
    assert dose["metadata"]["fiber_dose_source"] == "nutrition_facts"
    assert dose["metadata"]["fiber_grams_per_serving"] == 7.0
