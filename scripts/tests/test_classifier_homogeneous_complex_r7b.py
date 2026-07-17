"""R7b: homogeneous multi-identity panels get honest complex labels."""

from __future__ import annotations

import json
import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from scoring_input_contract import build_scoring_classification  # noqa: E402
from supplement_taxonomy import classify_supplement  # noqa: E402


def _row(canonical_id: str, category: str, *, path: str | None = None) -> dict:
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
        "raw_source_path": path or f"ingredientRows[{canonical_id}]",
    }


def _product(name: str, rows: list[dict]) -> dict:
    return {
        "dsld_id": f"r7b-{name}",
        "product_name": name,
        "fullName": name,
        "ingredient_quality_data": {
            "ingredients_scorable": rows,
            "ingredients": rows,
        },
        "probiotic_data": {"is_probiotic_product": False, "total_cfu": 0},
    }


def test_three_distinct_minerals_are_a_mineral_complex():
    taxonomy = classify_supplement(_product("Cal Mag Zinc", [
        _row("calcium", "mineral"),
        _row("magnesium", "mineral"),
        _row("zinc", "mineral"),
    ]))

    assert taxonomy["primary_type"] == "mineral_complex"
    assert "mineral_complex_panel" in taxonomy["classification_reason_codes"]
    assert taxonomy["is_single_scorable_active"] is False


def test_two_distinct_vitamins_are_a_vitamin_complex():
    taxonomy = classify_supplement(_product("Vitamin D3 + K2", [
        _row("vitamin_d3", "vitamin"),
        _row("vitamin_k2", "vitamin"),
    ]))

    assert taxonomy["primary_type"] == "vitamin_complex"
    assert "vitamin_complex_panel" in taxonomy["classification_reason_codes"]


def test_six_mineral_panel_no_longer_falls_to_general_or_multivitamin():
    taxonomy = classify_supplement(_product("Trace Mineral Complex", [
        _row("calcium", "mineral"),
        _row("magnesium", "mineral"),
        _row("zinc", "mineral"),
        _row("copper", "mineral"),
        _row("selenium", "mineral"),
        _row("manganese", "mineral"),
    ]))

    assert taxonomy["primary_type"] == "mineral_complex"
    assert "mineral_complex_panel" in taxonomy["classification_reason_codes"]


def test_two_forms_of_one_mineral_remain_single_by_identity():
    taxonomy = classify_supplement(_product("Magnesium Complex", [
        _row("magnesium", "mineral", path="ingredientRows[0]"),
        _row("magnesium", "mineral", path="ingredientRows[1]"),
    ]))

    assert taxonomy["distinct_active_identity_count"] == 1
    assert taxonomy["primary_type"] == "single_mineral"


def test_named_dominant_identity_with_unrelated_companion_remains_single_family():
    taxonomy = classify_supplement(_product("Calcium BHB", [
        _row("calcium", "mineral"),
        _row("d_beta_hydroxybutyrate_bhb", "fatty_acid"),
    ]))

    assert taxonomy["primary_type"] == "single_mineral"
    assert "name_dominant_identity" in taxonomy["classification_reason_codes"]


def test_short_magnesium_alias_is_bounded_and_does_not_match_magical():
    taxonomy = classify_supplement(_product("Magical Zinc", [
        _row("magnesium", "mineral"),
        _row("zinc", "mineral"),
    ]))

    assert taxonomy["primary_type"] == "single_mineral"
    assert taxonomy["secondary_type"] == "zinc"


def test_new_complex_types_use_the_existing_generic_scoring_route():
    for primary_type in ("vitamin_complex", "mineral_complex"):
        product = {
            "product_name": primary_type,
            "primary_type": primary_type,
            "supplement_taxonomy": {"primary_type": primary_type},
            "ingredient_quality_data": {"ingredients_scorable": []},
        }
        classification = build_scoring_classification(
            product,
            classification_origin="native_enrichment",
        )
        assert classification["route_module"] == "generic"
        assert classification["route_reason"] == f"taxonomy:{primary_type}"


def test_controlled_vocab_declares_both_complex_types():
    payload = json.loads((SCRIPTS_DIR / "data" / "product_type_vocab.json").read_text())
    entries = payload["product_types"]
    ids = {entry["id"] for entry in entries}

    assert {"vitamin_complex", "mineral_complex"} <= ids
    assert payload["_metadata"]["total_entries"] == len(entries) == 22
