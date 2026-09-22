"""Tests for get_assessable_evidence_ingredients canonical contract.

Pins the single canonical contract for Evidence-bearing rows across all modules:
1. Includes active_scorable rows.
2. Excludes inactive section rows, excipients, and inactive_non_scorable roles.
3. Excludes structural rows (blend_header_total, parent_total, compound_duplicate, is_proprietary_blend).
4. Excludes Nutrition Facts nutrient declarations (via skip_reason, panel_type, cleaner_row_role, etc.).
5. Includes disclosed nested_display_only child actives with resolved canonical identity.
6. Excludes nested_display_only rows with missing/empty or sentinel canonical IDs.
7. Excludes unresolved active rows without canonical identity.
8. Falls back cleanly when ingredient_quality_data.ingredients is absent.
9. Preserves raw source provenance and never fabricates dose on nested rows.
"""

from __future__ import annotations

import pytest
from scoring_input_contract import (
    get_assessable_evidence_ingredients,
    is_nutrition_fact_declaration,
)


def _wrap(rows: list[dict]) -> dict:
    return {
        "ingredient_quality_data": {
            "ingredients": rows,
        }
    }


def test_active_scorable_rows_included():
    row = {
        "cleaner_row_role": "active_scorable",
        "name": "Vitamin C",
        "canonical_id": "vitamin_c",
        "source_section": "active",
        "quantity": 500,
        "unit": "mg",
    }
    result = get_assessable_evidence_ingredients(_wrap([row]))
    assert len(result) == 1
    assert result[0]["canonical_id"] == "vitamin_c"
    assert result[0]["quantity"] == 500


def test_inactive_section_rows_excluded():
    rows = [
        {"cleaner_row_role": "active_scorable", "name": "Silicon Dioxide", "source_section": "inactive"},
        {"cleaner_row_role": "active_scorable", "name": "Magnesium Stearate", "is_excipient": True, "source_section": "active"},
        {"cleaner_row_role": "inactive", "name": "Gelatin", "source_section": "active"},
    ]
    result = get_assessable_evidence_ingredients(_wrap(rows))
    assert result == []


def test_blend_header_total_excluded():
    rows = [
        {"cleaner_row_role": "blend_header_total", "name": "Proprietary Blend", "is_blend_header": True},
        {"is_proprietary_blend": True, "name": "Digestive Enzyme Blend"},
    ]
    result = get_assessable_evidence_ingredients(_wrap(rows))
    assert result == []


def test_parent_total_and_compound_duplicate_excluded():
    rows = [
        {"cleaner_row_role": "parent_total", "is_parent_total": True, "name": "Total Fish Oil"},
        {"cleaner_row_role": "compound_duplicate", "is_compound_duplicate": True, "name": "EPA Duplicate"},
    ]
    result = get_assessable_evidence_ingredients(_wrap(rows))
    assert result == []


def test_nutrition_facts_declaration_excluded():
    rows = [
        {"name": "Calories", "skip_reason": "excluded_nutrition_fact"},
        {"name": "Total Fat", "cleaner_row_role": "nutrition_fact"},
        {"name": "Total Carbohydrate", "cleaner_row_role": "nutrition_rollup"},
        {"name": "Sodium", "source_section": "nutrition_fact"},
        {"name": "Protein", "canonical_source_db": "cleaner_nutrition_fact"},
    ]
    for row in rows:
        assert is_nutrition_fact_declaration(row) is True
    result = get_assessable_evidence_ingredients(_wrap(rows))
    assert result == []


def test_nested_display_only_with_canonical_id_included():
    row = {
        "cleaner_row_role": "nested_display_only",
        "name": "Amylase",
        "canonical_id": "digestive_enzymes",
        "source_section": "active",
        "mapped": False,
        "quantity": 0.0,
        "unit": "NP",
    }
    result = get_assessable_evidence_ingredients(_wrap([row]))
    assert len(result) == 1
    assert result[0]["canonical_id"] == "digestive_enzymes"


def test_nested_display_only_without_canonical_id_excluded():
    rows = [
        {"cleaner_row_role": "nested_display_only", "name": "Unresolved Botanical", "canonical_id": "", "source_section": "active"},
        {"cleaner_row_role": "nested_display_only", "name": "Unknown", "canonical_id": "unknown", "source_section": "active"},
        {"cleaner_row_role": "nested_display_only", "name": "Blend Placeholder", "canonical_id": "blend_general", "source_section": "active"},
    ]
    result = get_assessable_evidence_ingredients(_wrap(rows))
    assert result == []


def test_unmapped_active_rows_without_canonical_id_excluded():
    rows = [
        {"cleaner_row_role": "active_scorable", "name": "Mystery Powder", "role_classification": "active_unmapped", "canonical_id": ""},
        {"cleaner_row_role": "active_scorable", "name": "Unknown Plant", "identity_decision_reason": "unresolved_identity_no_quality_map_match", "canonical_id": ""},
    ]
    result = get_assessable_evidence_ingredients(_wrap(rows))
    assert result == []


def test_fallback_when_iqd_ingredients_absent():
    product = {
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {
                    "cleaner_row_role": "active_scorable",
                    "name": "Zinc Glycinate",
                    "canonical_id": "zinc",
                    "source_section": "active",
                    "quantity": 30,
                    "unit": "mg",
                }
            ]
        }
    }
    result = get_assessable_evidence_ingredients(product)
    assert len(result) == 1
    assert result[0]["canonical_id"] == "zinc"


def test_provenance_preserved_and_quantity_not_fabricated():
    row = {
        "cleaner_row_role": "nested_display_only",
        "name": "Lactobacillus acidophilus",
        "raw_source_text": "L. acidophilus",
        "raw_source_path": "ingredientRows[0].nestedRows[3]",
        "canonical_id": "lactobacillus_acidophilus",
        "source_section": "active",
        "mapped": False,
        "quantity": 0.0,
        "unit": "NP",
    }
    result = get_assessable_evidence_ingredients(_wrap([row]))
    assert len(result) == 1
    out = result[0]
    assert out["raw_source_path"] == "ingredientRows[0].nestedRows[3]"
    assert out["raw_source_text"] == "L. acidophilus"
    assert out["canonical_id"] == "lactobacillus_acidophilus"
    assert out["quantity"] == 0.0
    assert out["unit"] == "NP"


def test_named_blend_child_is_retained_despite_its_inactive_non_scorable_classification():
    """The enricher classifies undosed named blend children inactive_non_scorable.

    That label is about scoring, not efficacy: the Phase-5 contract keeps a named
    child (Bacillus subtilis in an enzyme blend) in the Evidence universe.
    """
    rows = [{"cleaner_row_role": "nested_display_only", "role_classification": "inactive_non_scorable",
             "canonical_id": "bacillus_subtilis", "name": "Bacillus subtilis", "source_section": "active"}]
    assert [r["canonical_id"] for r in get_assessable_evidence_ingredients(_wrap(rows))] == ["bacillus_subtilis"]
