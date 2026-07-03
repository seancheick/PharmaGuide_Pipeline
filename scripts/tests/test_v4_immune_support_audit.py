"""Immune-support audit regressions.

These pin the category behavior surfaced by the July 2026 immune audit:
clean daily immune formulas should be able to score in the high-80s, while
gummy/syrup/high-zinc "emergency" formulas should not look benchmark-clean.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from score_supplements_v4 import score_product_v4  # noqa: E402


DATA_DIR = SCRIPTS_DIR / "data"


def _row(
    name: str,
    canonical_id: str,
    quantity: float,
    unit: str,
    *,
    bio_score: float = 12.0,
    category: str = "vitamin",
) -> Dict[str, Any]:
    return {
        "name": name,
        "standard_name": name,
        "canonical_id": canonical_id,
        "quantity": quantity,
        "unit": unit,
        "bio_score": bio_score,
        "mapped": True,
        "scoreable_identity": True,
        "cleaner_row_role": "active_scorable",
        "category": category,
    }


def _cert(program: str = "NSF Sport", scope: str = "sku") -> Dict[str, Any]:
    return {
        "program": program,
        "scope": scope,
        "recency_status": "fresh",
        "brand_matched": True,
    }


def _immune_product(*, high_zinc: bool = False, gummy: bool = False) -> Dict[str, Any]:
    zinc_mg = 50.0 if high_zinc else 15.0
    sugar = {
        "level": "high" if gummy else "sugar_free",
        "contains_sugar": gummy,
        "has_added_sugar": gummy,
        "amount_g": 8 if gummy else 0,
        "sugar_sources": ["glucose syrup"] if gummy else [],
    }
    return {
        "product_name": (
            "Ultra Immune Emergency Gummies"
            if gummy
            else "ClearShield Immune Daily"
        ),
        "brand_name": "PharmaGuide Benchmark",
        "primary_type": "immune_support",
        "supplement_taxonomy": {"primary_type": "immune_support"},
        "product_status": "active",
        "form_factor": "gummy" if gummy else "capsule",
        "form_factor_canonical": "gummy" if gummy else "capsule",
        "verified_cert_programs": [_cert()],
        "ingredient_quality_data": {
            "ingredients_scorable": [
                _row("Vitamin C as calcium ascorbate", "vitamin_c", 500, "mg", bio_score=13),
                _row("Vitamin D3", "vitamin_d3", 25, "mcg", bio_score=13),
                _row("Zinc bisglycinate", "zinc", zinc_mg, "mg", bio_score=13, category="mineral"),
                _row("Copper bisglycinate", "copper", 1, "mg", bio_score=13, category="mineral"),
                _row("Selenium selenomethionine", "selenium", 55, "mcg", bio_score=13, category="mineral"),
                _row("Yeast beta-glucan 1,3/1,6", "beta_glucan", 250, "mg", bio_score=11, category="other"),
                _row("Quercetin phytosome", "quercetin", 500, "mg", bio_score=12, category="botanical"),
                _row("Elderberry extract", "elderberry", 300, "mg", bio_score=10, category="botanical"),
            ]
        },
        "evidence_data": {
            "clinical_matches": [
                {
                    "ingredient": "Vitamin C",
                    "standard_name": "Vitamin C",
                    "study_type": "systematic_review_meta",
                    "evidence_level": "ingredient-human",
                    "effect_direction": "positive_weak",
                    "total_enrollment": 1000,
                    "min_clinical_dose": 200,
                    "dose_unit": "mg",
                },
                {
                    "ingredient": "Vitamin D3",
                    "standard_name": "Vitamin D3",
                    "study_type": "systematic_review_meta",
                    "evidence_level": "ingredient-human",
                    "effect_direction": "positive_weak",
                    "total_enrollment": 1000,
                    "min_clinical_dose": 15,
                    "dose_unit": "mcg",
                },
                {
                    "ingredient": "Zinc",
                    "standard_name": "Zinc",
                    "study_type": "systematic_review_meta",
                    "evidence_level": "ingredient-human",
                    "effect_direction": "positive_weak",
                    "total_enrollment": 500,
                    "min_clinical_dose": 10,
                    "dose_unit": "mg",
                },
            ]
        },
        "rda_ul_data": {
            "safety_flags": (
                [{"nutrient": "Zinc", "pct_ul": 125.0, "flag": "OVER_UL_Zinc"}]
                if high_zinc
                else []
            ),
            "adequacy_results": [
                {"nutrient": "Vitamin C", "pct_rda": 555, "pct_ul": 25},
                {"nutrient": "Vitamin D3", "pct_rda": 125, "pct_ul": 25},
                {"nutrient": "Zinc", "pct_rda": 455 if high_zinc else 136, "pct_ul": 125 if high_zinc else 37.5},
                {"nutrient": "Copper", "pct_rda": 111, "pct_ul": 10},
                {"nutrient": "Selenium", "pct_rda": 100, "pct_ul": 12.2},
            ],
        },
        "dietary_sensitivity_data": {
            "sugar": sugar,
            "sweeteners": {"high_glycemic": ["glucose syrup"] if gummy else []},
        },
    }


def _emergency_gummy_product() -> Dict[str, Any]:
    product = _immune_product(high_zinc=True, gummy=True)
    product["verified_cert_programs"] = []
    product["ingredient_quality_data"]["ingredients_scorable"] = [
        _row("Vitamin C", "vitamin_c", 1000, "mg", bio_score=8),
        _row("Vitamin D3", "vitamin_d3", 100, "mcg", bio_score=10),
        _row("Zinc oxide", "zinc", 50, "mg", bio_score=4, category="mineral"),
        _row("Elderberry syrup concentrate", "elderberry", 100, "mg", bio_score=6, category="botanical"),
    ]
    return product


def _botanical_stack_with_duplicate_rows() -> Dict[str, Any]:
    rows = [
        _row("Vitamin C", "vitamin_c", 250, "mg", bio_score=10),
    ]
    for name, canonical_id in (
        ("Echinacea", "echinacea"),
        ("Goldenseal", "goldenseal"),
        ("Astragalus", "astragalus"),
        ("Andrographis", "andrographis"),
        ("Oregano oil", "oregano_oil"),
    ):
        rows.append(_row(name, canonical_id, 100, "mg", bio_score=6, category="botanical"))
        rows.append(_row(f"{name} extract duplicate", canonical_id, 100, "mg", bio_score=6, category="botanical"))

    product = _immune_product()
    product["product_name"] = "Immune Botanical Defense Complex"
    product["verified_cert_programs"] = []
    product["ingredient_quality_data"]["ingredients_scorable"] = rows
    product["evidence_data"]["clinical_matches"] = []
    product["rda_ul_data"]["safety_flags"] = []
    product["rda_ul_data"]["adequacy_results"] = [
        {"nutrient": "Vitamin C", "pct_rda": 277, "pct_ul": 12.5},
    ]
    product["dietary_sensitivity_data"] = {
        "sugar": {"level": "sugar_free", "contains_sugar": False, "has_added_sugar": False, "amount_g": 0},
        "sweeteners": {},
    }
    return product


def test_clean_daily_immune_formula_reaches_realistic_high_80s() -> None:
    out = score_product_v4(_immune_product())

    assert out["v4_module"] == "generic"
    assert 86.0 <= out["quality_score_v4_100"] <= 92.0
    assert out["quality_pillars_v4"]["dose"]["score"] >= 17.0
    assert out["quality_pillars_v4"]["formulation"]["score"] >= 16.0
    assert out["v4_breakdown"]["module"]["dimensions"]["formulation"]["metadata"][
        "immune_support"
    ]["profile_applied"] is True


def test_gummy_high_zinc_immune_formula_not_benchmark_clean() -> None:
    out = score_product_v4(_immune_product(high_zinc=True, gummy=True))
    pillars = out["quality_pillars_v4"]

    assert out["quality_score_v4_100"] < 75.0
    assert pillars["safety_hygiene"]["score"] < 10.0
    assert pillars["dose"]["score"] < 17.0


def test_high_zinc_gummy_does_not_receive_clean_daily_immune_evidence_floor() -> None:
    out = score_product_v4(_emergency_gummy_product())
    evidence = out["v4_breakdown"]["module"]["dimensions"]["evidence"]

    assert out["quality_score_v4_100"] < 60.0
    assert evidence["score"] < 14.0
    assert evidence["metadata"]["immune_support_evidence_floor_applied"] is False


def test_high_variability_botanical_count_dedupes_duplicate_rows() -> None:
    out = score_product_v4(_botanical_stack_with_duplicate_rows())
    formulation = out["v4_breakdown"]["module"]["dimensions"]["formulation"]
    immune_meta = formulation["metadata"]["immune_support"]

    assert immune_meta["high_variability_botanical_count"] == 5
    assert "immune_high_variability_botanical_stack" in formulation["penalties"]
    assert out["quality_score_v4_100"] < 50.0


def test_immune_goal_mapping_excludes_broad_lifestyle_clusters() -> None:
    mappings = json.loads((DATA_DIR / "user_goals_to_clusters.json").read_text())[
        "user_goal_mappings"
    ]
    immune = next(item for item in mappings if item["id"] == "GOAL_IMMUNE_SUPPORT")

    assert set(immune["required_clusters"]) == {
        "immune_defense",
        "immune_probiotic_blend",
    }
    assert not {
        "bone_health",
        "antioxidant_defense",
        "detox_pathway",
        "liver_support",
    } & set(immune["cluster_weights"])


def test_immune_defense_copy_does_not_claim_tier_1_synergy() -> None:
    clusters = json.loads((DATA_DIR / "synergy_cluster.json").read_text())[
        "synergy_clusters"
    ]
    immune = next(item for item in clusters if item["id"] == "immune_defense")

    assert immune["evidence_tier"] == 3
    assert "Tier 1" not in immune["note"]
    assert "no clinical trial has tested this exact combination" in immune["evidence_note"]
