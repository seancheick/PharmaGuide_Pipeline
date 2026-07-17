"""R5: specialized sports/hydration identity outranks a broad nutrient panel.

Product intent is corroborating evidence, never sufficient by itself.  These
fixtures therefore require both a bounded name signal and category-owned
canonical anchors, and pin both one-sided near misses.
"""

from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from supplement_taxonomy import classify_supplement  # noqa: E402


def _row(canonical_id: str, category: str) -> dict:
    return {
        "name": canonical_id.replace("_", " "),
        "canonical_id": canonical_id,
        "category": category,
        "quantity": 100.0,
        "unit": "mg",
        "mapped": True,
        "mapped_identity": True,
        "scoreable_identity": True,
        "identity_disposition": "clean",
        "role_classification": "active_scorable",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "raw_source_path": f"ingredientRows[{canonical_id}]",
    }


def _product(name: str, rows: list[dict]) -> dict:
    return {
        "dsld_id": f"r5-{name}",
        "product_name": name,
        "fullName": name,
        "ingredient_quality_data": {
            "ingredients_scorable": rows,
            "ingredients": rows,
        },
        "probiotic_data": {"is_probiotic_product": False, "total_cfu": 0},
    }


def _broad_panel() -> list[dict]:
    return [
        _row("vitamin_b1_thiamine", "vitamin"),
        _row("vitamin_b2_riboflavin", "vitamin"),
        _row("vitamin_b3_niacin", "vitamin"),
        _row("vitamin_b6_pyridoxine", "vitamin"),
        _row("vitamin_b12_cobalamin", "vitamin"),
        _row("vitamin_c", "vitamin"),
        _row("calcium", "mineral"),
        _row("magnesium", "mineral"),
        _row("potassium", "mineral"),
    ]


def test_pre_workout_intent_plus_two_performance_anchors_outranks_panel():
    rows = _broad_panel() + [
        _row("caffeine", "stimulant"),
        _row("l_citrulline", "amino_acid"),
    ]

    taxonomy = classify_supplement(_product("Pre-Workout Complex", rows))

    assert taxonomy["primary_type"] == "pre_workout"
    assert "specialized_panel_pre_workout" in taxonomy["classification_reason_codes"]


def test_endurance_intent_plus_two_performance_anchors_outranks_panel():
    rows = _broad_panel() + [
        _row("caffeine", "stimulant"),
        _row("l_citrulline", "amino_acid"),
    ]

    taxonomy = classify_supplement(_product("Amplified Endurance Booster", rows))

    assert taxonomy["primary_type"] == "pre_workout"
    assert "specialized_panel_pre_workout" in taxonomy["classification_reason_codes"]


def test_hydration_intent_plus_three_electrolytes_outranks_panel():
    taxonomy = classify_supplement(_product(
        "Advanced Hydration Complex",
        _broad_panel(),
    ))

    assert taxonomy["primary_type"] == "electrolyte"
    assert "specialized_panel_electrolyte" in taxonomy["classification_reason_codes"]


def test_pre_workout_title_without_performance_anchors_cannot_mint_type():
    taxonomy = classify_supplement(_product("Pre-Workout Vitamins", _broad_panel()))

    assert taxonomy["primary_type"] == "multivitamin"
    assert "specialized_panel_pre_workout" not in taxonomy["classification_reason_codes"]


def test_hydration_title_without_three_electrolytes_cannot_mint_type():
    rows = [
        _row("vitamin_b1_thiamine", "vitamin"),
        _row("vitamin_b2_riboflavin", "vitamin"),
        _row("vitamin_b3_niacin", "vitamin"),
        _row("vitamin_b6_pyridoxine", "vitamin"),
        _row("vitamin_b12_cobalamin", "vitamin"),
        _row("vitamin_c", "vitamin"),
        _row("magnesium", "mineral"),
        _row("zinc", "mineral"),
    ]

    taxonomy = classify_supplement(_product("Daily Hydration Vitamins", rows))

    assert taxonomy["primary_type"] != "electrolyte"
    assert "specialized_panel_electrolyte" not in taxonomy["classification_reason_codes"]


def test_anchor_rich_multivitamin_without_specialized_intent_stays_multivitamin():
    rows = _broad_panel() + [
        _row("caffeine", "stimulant"),
        _row("l_citrulline", "amino_acid"),
    ]

    taxonomy = classify_supplement(_product("Complete Daily Multivitamin", rows))

    assert taxonomy["primary_type"] == "multivitamin"


def test_with_hydration_is_accessory_evidence_and_cannot_steal_amino_identity():
    rows = [
        _row("l_leucine", "amino_acid"),
        _row("l_isoleucine", "amino_acid"),
        _row("l_valine", "amino_acid"),
        _row("calcium", "mineral"),
        _row("magnesium", "mineral"),
        _row("potassium", "mineral"),
    ]

    taxonomy = classify_supplement(_product("BCAA+ With Hydration Complex", rows))

    assert taxonomy["primary_type"] == "amino_acid"
    assert "specialized_panel_electrolyte" not in taxonomy["classification_reason_codes"]
