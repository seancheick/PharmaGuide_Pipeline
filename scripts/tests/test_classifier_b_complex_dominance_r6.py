"""R6: explicit B-complex identity survives bounded mineral companions."""

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
        "dsld_id": f"r6-{name}",
        "product_name": name,
        "fullName": name,
        "ingredient_quality_data": {
            "ingredients_scorable": rows,
            "ingredients": rows,
        },
        "probiotic_data": {"is_probiotic_product": False, "total_cfu": 0},
    }


def _b_vitamins(count: int) -> list[dict]:
    ids = [
        "vitamin_b1_thiamine",
        "vitamin_b2_riboflavin",
        "vitamin_b3_niacin",
        "vitamin_b6_pyridoxine",
        "vitamin_b12_cobalamin",
    ]
    return [_row(cid, "vitamin") for cid in ids[:count]]


def _minerals(count: int) -> list[dict]:
    ids = ["calcium", "magnesium", "zinc", "copper", "selenium"]
    return [_row(cid, "mineral") for cid in ids[:count]]


def test_named_b_complex_with_three_minerals_stays_b_complex_when_b_dominant():
    taxonomy = classify_supplement(_product(
        "Active B-Complex with Minerals",
        _b_vitamins(5) + _minerals(3),
    ))

    assert taxonomy["primary_type"] == "b_complex"
    assert "b_complex_dominant_named_panel" in taxonomy["classification_reason_codes"]


def test_named_b_complex_does_not_override_a_mineral_dominant_broad_panel():
    taxonomy = classify_supplement(_product(
        "B-Complex with Mineral Matrix",
        _b_vitamins(3) + _minerals(5),
    ))

    assert taxonomy["primary_type"] == "multivitamin"
    assert "b_complex_dominant_named_panel" not in taxonomy["classification_reason_codes"]


def test_b_vitamins_plus_three_minerals_without_b_complex_identity_stays_multi():
    taxonomy = classify_supplement(_product(
        "Daily Calcium Magnesium Support",
        _b_vitamins(5) + _minerals(3),
    ))

    assert taxonomy["primary_type"] == "multivitamin"
    assert "b_complex_dominant_named_panel" not in taxonomy["classification_reason_codes"]


def test_existing_focused_b_complex_with_two_minerals_is_unchanged():
    taxonomy = classify_supplement(_product(
        "B-Complex Complete",
        _b_vitamins(5) + _minerals(2),
    ))

    assert taxonomy["primary_type"] == "b_complex"
    assert "b_complex_panel" in taxonomy["classification_reason_codes"]
