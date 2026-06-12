"""Shared v4 formulation safety penalties must not drift by module."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _flagged_product() -> dict:
    return {
        "status": "active",
        "form_factor": "capsule",
        "product_name": "Flagged Product",
        "contaminant_data": {
            "banned_substances": {
                "substances": [
                    {
                        "name": "Moderate Watchlist Ingredient",
                        "status": "watchlist",
                        "match_type": "exact",
                    }
                ]
            },
            "harmful_additives": {
                "additives": [
                    {
                        "additive_id": "ADD_TEST_HIGH",
                        "name": "High Risk Additive",
                        "severity_level": "high",
                        "source_section": "inactive",
                    }
                ]
            },
        },
        "dietary_sensitivity_data": {
            "sugar": {
                "level": "low",
                "contains_sugar": True,
                "has_added_sugar": True,
                "sugar_sources": ["corn syrup"],
            },
            "sweeteners": {
                "high_glycemic": ["corn syrup"],
                "sugar_alcohols": [],
            },
        },
        "ingredient_quality_data": {
            "total_active": 1,
            "ingredients_scorable": [
                {
                    "name": "Test Active",
                    "canonical_id": "test_active",
                    "mapped": True,
                    "quantity": 10,
                    "unit": "mg",
                    "bio_score": 12,
                }
            ],
        },
    }


def test_shared_formulation_penalties_are_identical_across_module_formulators() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation as score_generic_formulation
    from scoring_v4.modules.multi_prenatal_formulation import score_formulation as score_multi_formulation
    from scoring_v4.modules.omega_formulation import score_formulation as score_omega_formulation
    from scoring_v4.modules.probiotic_formulation import score_formulation as score_probiotic_formulation

    product = _flagged_product()
    expected = {
        "B1_dietary_sugar": -2.0,
        "B0_moderate_watchlist": -5.0,
        "B1_harmful_additives": -2.0,
    }

    for scorer in (
        score_generic_formulation,
        score_multi_formulation,
        score_omega_formulation,
        score_probiotic_formulation,
    ):
        penalties = scorer(product)["penalties"]
        for key, value in expected.items():
            assert penalties[key] == value, f"{scorer.__module__} drifted on {key}"


def test_shared_formulation_penalties_keep_dietary_sugar_metadata() -> None:
    from scoring_v4.modules.omega_formulation import score_formulation

    payload = score_formulation(_flagged_product())

    sugar = payload["metadata"]["dietary_sugar"]
    assert sugar["penalty"] == 2.0
    assert sugar["reason"] == "high_glycemic_syrup_or_sugar_alcohol"
    assert sugar["syrup_sources"] == ["corn syrup"]
