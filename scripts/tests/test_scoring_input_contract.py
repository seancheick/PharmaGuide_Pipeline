from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_input_contract import (  # noqa: E402
    LEGACY_IQD_SOURCE,
    SCORING_SOURCE,
    get_scoring_ingredients,
    is_nutrition_only_product,
)


def _row(**overrides):
    row = {
        "name": "Magnesium Glycinate",
        "canonical_id": "magnesium",
        "mapped": True,
        "quantity": 200,
        "unit": "mg",
        "source_section": "active",
        "raw_source_path": "ingredientRows[0]",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "score_exclusion_reason": None,
        "dose_class": "therapeutic_mass",
        "raw_taxonomy": {"category": "vitamin/mineral"},
        "role_classification": "active_scorable",
        "scoreable_identity": True,
    }
    row.update(overrides)
    return row


def _product(rows, **extra):
    product = {
        "ingredient_quality_data": {
            "ingredients_scorable": rows,
            "ingredients": [{"name": "Legacy Active", "canonical_id": "legacy", "mapped": True}],
        }
    }
    product.update(extra)
    return product


def test_strict_rows_come_only_from_ingredients_scorable():
    result = get_scoring_ingredients(_product([_row()]), strict=True)

    assert result.source == SCORING_SOURCE
    assert [r["canonical_id"] for r in result.rows] == ["magnesium"]
    assert result.mapped_coverage == 1.0
    assert result.strict_contract_passed is True


def test_strict_mode_does_not_fallback_to_legacy_iqd_ingredients():
    result = get_scoring_ingredients(_product([]), strict=True)

    assert result.rows == []
    assert result.source == SCORING_SOURCE
    assert result.zero_scorable_reason == "no_strict_scoring_candidates"
    assert result.fallbacks_used == []
    assert result.strict_contract_passed is True


def test_legacy_fallback_is_explicit_old_batch_compatibility():
    result = get_scoring_ingredients(_product([]), strict=False, allow_legacy_fallback=True)

    assert result.source == LEGACY_IQD_SOURCE
    assert result.fallbacks_used[0].fallback_class == "old_batch_compatibility"


def test_forbidden_roles_are_rejected():
    result = get_scoring_ingredients(
        _product([_row(cleaner_row_role="blend_header_total")]),
        strict=True,
    )

    assert result.rows == []
    assert result.rejected_rows[0].reason == "excluded_cleaner_role:blend_header_total"


def test_recognized_non_scorable_does_not_enter_scoring_rows():
    result = get_scoring_ingredients(
        _product([_row(role_classification="recognized_non_scorable")]),
        strict=True,
    )

    assert result.rows == []
    assert result.rejected_rows[0].reason == "excluded_role_classification:recognized_non_scorable"


def test_enzyme_activity_and_probiotic_cfu_count_as_dose_evidence():
    rows = [
        _row(name="Protease", canonical_id="protease", quantity=None, unit="SPU", dose_class="enzyme_activity"),
        _row(name="Lactobacillus", canonical_id="lactobacillus", quantity=None, unit=None, dose_class="probiotic_cfu"),
    ]

    result = get_scoring_ingredients(_product(rows), strict=True)

    assert [row["canonical_id"] for row in result.rows] == ["protease", "lactobacillus"]


def test_no_dose_known_identity_is_rejected():
    result = get_scoring_ingredients(
        _product([_row(quantity=None, unit=None, has_dose=False)]),
        strict=True,
    )

    assert result.rows == []
    assert result.rejected_rows[0].reason == "missing_dose_evidence"


def test_product_level_probiotic_evidence_is_accepted_from_contract_only():
    product = _product(
        [],
        product_name="Digestive Probiotic 20 Billion",
        product_scoring_evidence=[
            {
                "name": "Total CFU",
                "canonical_id": "probiotic_cfu_total",
                "clean_identity_id": None,
                "scoring_parent_id": "probiotic_cfu_total",
                "evidence_canonical_id": "probiotic_cfu_total",
                "canonical_source_db": "product_scoring_evidence",
                "evidence_origin": "native_enrichment",
                "evidence_type": "probiotic_cfu",
                "scoreable": True,
                "scoreable_identity": True,
                "score_eligible_by_cleaner": True,
                "dose_class": "probiotic_cfu",
                "dose_value": 20_000_000_000,
                "dose_unit": "CFU",
                "source": "statements",
                "raw_source_path": "statements[0]",
                "evidence_scope": "product_level",
                "linked_rows": ["statements[0]"],
                "confidence": "high",
                "reason": "product_level_cfu_with_probiotic_identity",
            }
        ],
    )

    result = get_scoring_ingredients(product, strict=True)

    assert result.rows[0]["canonical_id"] == "probiotic_cfu_total"
    assert result.rows[0]["scoring_input_kind"] == "product_level_evidence"
    assert result.rows[0]["section_support"] == ["probiotic_dose_adequacy"]
    assert result.rows[0]["generic_form_quality_credit"] is False
    assert "product_scoring_evidence" in result.source


def test_product_level_evidence_missing_identity_chain_is_rejected():
    product = _product(
        [],
        product_name="Digestive Probiotic 20 Billion",
        product_scoring_evidence=[
            {
                "name": "Total CFU",
                "canonical_id": "probiotic_cfu_total",
                "evidence_type": "probiotic_cfu",
                "scoreable": True,
                "scoreable_identity": True,
                "score_eligible_by_cleaner": True,
                "dose_class": "probiotic_cfu",
                "dose_value": 20_000_000_000,
                "dose_unit": "CFU",
                "source": "statements",
                "raw_source_path": "statements[0]",
                "evidence_scope": "product_level",
                "linked_rows": ["statements[0]"],
                "confidence": "high",
                "reason": "product_level_cfu_with_probiotic_identity",
            }
        ],
    )

    result = get_scoring_ingredients(product, strict=True)

    assert result.rows == []
    assert result.rejected_rows[0].reason == "malformed_product_scoring_evidence"
    assert set(result.rejected_rows[0].missing_fields) >= {
        "clean_identity_id",
        "scoring_parent_id",
        "evidence_canonical_id",
        "canonical_source_db",
        "evidence_origin",
    }
    assert result.strict_contract_passed is False


def test_legacy_probiotic_data_can_repair_stale_native_cfu_evidence():
    product = _product(
        [],
        supplement_taxonomy={"primary_type": "probiotic"},
        probiotic_data={
            "is_probiotic_product": True,
            "total_cfu": 3_370_000_000,
            "total_strain_count": 2,
            "probiotic_blends": [{"name": "Probiotic Blend", "raw_source_path": "ingredientRows[0]"}],
            "cfu_source": "activeIngredients.notes",
            "cfu_raw_source_path": "ingredientRows[0]",
            "cfu_evidence_scope": "row_level",
            "cfu_linked_rows": ["ingredientRows[0]"],
        },
        product_scoring_evidence=[
            {
                "name": "Total CFU",
                "canonical_id": "probiotic_cfu_total",
                "evidence_type": "probiotic_cfu",
                "scoreable": True,
                "scoreable_identity": True,
                "score_eligible_by_cleaner": True,
                "dose_class": "probiotic_cfu",
                "dose_value": 3_370_000_000,
                "dose_unit": "CFU",
                "source": "activeIngredients.notes",
                "raw_source_path": "ingredientRows[0]",
                "evidence_scope": "row_level",
                "linked_rows": ["ingredientRows[0]"],
                "confidence": "high",
                "reason": "legacy_native_missing_identity_chain",
            }
        ],
    )

    result = get_scoring_ingredients(product, strict=True)

    assert result.rows
    assert result.rows[0]["evidence_type"] == "probiotic_cfu"
    assert result.rows[0]["evidence_origin"] == "compatibility_derived"
    assert result.rows[0]["canonical_source_db"] == "probiotic_data"
    assert result.rejected_rows[0].reason == "malformed_product_scoring_evidence"
    assert "evidence_origin" in result.rejected_rows[0].missing_fields


def test_sports_primary_identity_without_dose_is_contract_diagnostic():
    product = _product(
        [],
        primary_type="protein_powder",
        activeIngredients=[
            {
                "name": "Whey Protein Hydrolysate",
                "canonical_id": "whey_protein",
                "quantity": 0,
                "unit": "unspecified",
                "raw_source_path": "activeIngredients",
                "score_eligible_by_cleaner": True,
                "cleaner_row_role": "active_scorable",
            }
        ],
    )

    result = get_scoring_ingredients(product, strict=True)

    assert result.rows == []
    assert result.rejected_rows[0].reason == "product_evidence_not_scoreable:missing_primary_sports_dose"
    assert result.rejected_rows[0].row["evidence_type"] == "sports_primary_dose"
    assert result.rejected_rows[0].row["clean_identity_id"] == "whey_protein"


def test_product_level_evidence_missing_provenance_is_rejected():
    product = _product(
        [],
        product_scoring_evidence=[
            {
                "evidence_type": "probiotic_cfu",
                "clean_identity_id": None,
                "scoring_parent_id": "probiotic_cfu_total",
                "evidence_canonical_id": "probiotic_cfu_total",
                "canonical_source_db": "product_scoring_evidence",
                "evidence_origin": "native_enrichment",
                "scoreable": True,
                "scoreable_identity": True,
                "score_eligible_by_cleaner": True,
                "dose_class": "probiotic_cfu",
                "dose_value": 20_000_000_000,
                "dose_unit": "CFU",
                "source": "probiotic_data.total_cfu",
                "evidence_scope": "product_level",
                "linked_rows": [],
                "confidence": "low",
                "reason": "missing_source",
            }
        ],
    )

    result = get_scoring_ingredients(product, strict=True)

    assert result.rows == []
    assert result.rejected_rows[0].reason == "malformed_product_scoring_evidence"
    assert "raw_source_path" in result.rejected_rows[0].missing_fields
    assert result.strict_contract_passed is False


def test_rejected_product_evidence_is_visible_but_not_scorable():
    product = _product(
        [],
        product_scoring_evidence=[
            {
                "evidence_type": "probiotic_cfu",
                "scoreable": False,
                "scoreable_identity": False,
                "score_eligible_by_cleaner": False,
                "dose_class": "probiotic_cfu",
                "dose_value": 20_000_000_000,
                "dose_unit": "CFU",
                "source": "probiotic_data.total_cfu",
                "raw_source_path": "statements[0]",
                "evidence_scope": "product_level",
                "linked_rows": ["statements[0]"],
                "confidence": "low",
                "reason": "probiotic_cfu_rejected_by_identity_or_provenance_gate",
                "rejection_reason": "product_identity_not_probiotic",
            }
        ],
    )

    result = get_scoring_ingredients(product, strict=True)

    assert result.rows == []
    assert result.rejected_rows[0].reason == "product_evidence_not_scoreable:product_identity_not_probiotic"
    assert result.strict_contract_passed is True


def test_product_name_alone_does_not_create_product_level_evidence():
    result = get_scoring_ingredients(
        _product([], product_name="Digestive Probiotic 20 Billion"),
        strict=True,
    )

    assert result.rows == []
    assert result.zero_scorable_reason == "no_strict_scoring_candidates"


def test_blend_header_mass_with_mapped_nested_child_emits_conservative_anchor():
    product = _product(
        [],
        product_name="Kudzu Root 1,226 mg",
        ingredient_quality_data={
            "ingredients_scorable": [],
            "ingredients": [],
            "ingredients_skipped": [
                {
                    "name": "Proprietary Blend",
                    "canonical_id": "BLEND_GENERAL",
                    "raw_source_path": "ingredientRows[0]",
                    "cleaner_row_role": "blend_header_total",
                    "skip_reason": "blend_header_total_weight_only",
                    "quantity": 1.226,
                    "unit": "Gram(s)",
                    "unit_normalized": "gram(s)",
                    "is_blend_header": True,
                    "blend_total_weight_only": True,
                    "raw_taxonomy": {"category": "blend", "ingredientGroup": "Proprietary Blend"},
                },
                {
                    "name": "Kudzu extract",
                    "standard_name": "Puerarin (Kudzu Extract)",
                    "canonical_id": "puerarin_kudzu_extract",
                    "canonical_source_db": "ingredient_quality_map",
                    "raw_source_path": "ingredientRows[0].nestedRows[0]",
                    "cleaner_row_role": "nested_display_only",
                    "skip_reason": "nested_under_non_therapeutic_parent",
                    "quantity": 0,
                    "unit": "NP",
                    "raw_taxonomy": {"category": "botanical", "ingredientGroup": "Kudzu extract"},
                },
            ],
        },
    )

    result = get_scoring_ingredients(product, strict=True)

    assert len(result.rows) == 1
    row = result.rows[0]
    assert row["scoring_input_kind"] == "product_level_evidence"
    assert row["evidence_type"] == "blend_anchor_mass"
    assert row["canonical_id"] == "puerarin_kudzu_extract"
    assert row["quantity"] == 1.226
    assert row["unit"] == "Gram(s)"
    assert row["reason"] == "identity_bearing_blend_header_mass_from_nested_child"
    assert row["evidence_scope"] == "blend_level"


def test_blend_header_mass_does_not_create_mass_anchor_for_probiotic_strain():
    product = _product(
        [],
        product_name="Skin Squad Pre + Probiotic",
        ingredient_quality_data={
            "ingredients_scorable": [],
            "ingredients": [],
            "ingredients_skipped": [
                {
                    "name": "Proprietary Blend",
                    "canonical_id": "BLEND_GENERAL",
                    "raw_source_path": "ingredientRows[0]",
                    "cleaner_row_role": "blend_header_total",
                    "skip_reason": "blend_header_total_weight_only",
                    "quantity": 200,
                    "unit": "mg",
                    "is_blend_header": True,
                    "blend_total_weight_only": True,
                    "raw_taxonomy": {"category": "blend", "ingredientGroup": "Proprietary Blend"},
                },
                {
                    "name": "Bacillus subtilis DE111",
                    "standard_name": "Bacillus Subtilis",
                    "canonical_id": "bacillus_subtilis",
                    "raw_source_path": "ingredientRows[0].nestedRows[0]",
                    "cleaner_row_role": "nested_display_only",
                    "skip_reason": "nested_under_non_therapeutic_parent",
                    "quantity": 0,
                    "unit": "NP",
                    "raw_taxonomy": {"category": "bacteria", "ingredientGroup": "Bacillus subtilis"},
                },
            ],
        },
    )

    result = get_scoring_ingredients(product, strict=True)

    assert result.rows == []
    assert result.zero_scorable_reason == "no_strict_scoring_candidates"


def test_nutrition_only_uses_explicit_contract_not_keywords_by_default():
    assert is_nutrition_only_product({"product_name": "Whey Protein Powder"}) is False
    assert is_nutrition_only_product({"product_scoring_class": "nutrition_only"}) is True
    assert is_nutrition_only_product(
        {"product_name": "Whey Protein Powder"},
        allow_legacy_keyword_fallback=True,
    ) is True
