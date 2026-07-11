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
    build_scoring_classification,
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


def test_no_dose_known_identity_is_kept_for_scoring():
    result = get_scoring_ingredients(
        _product([_row(quantity=None, unit=None, has_dose=False)]),
        strict=True,
    )

    assert [row["canonical_id"] for row in result.rows] == ["magnesium"]
    assert result.rejected_rows == []


def test_skipped_mapped_active_without_dose_is_recovered_for_scoring():
    product = _product(
        [],
        ingredient_quality_data={
            "ingredients_scorable": [],
            "ingredients_skipped": [
                _row(
                    name="Vitamin C",
                    canonical_id="vitamin_c",
                    quantity=0,
                    unit="NP",
                    role_classification="recognized_non_scorable",
                    mapped=False,
                    score_exclusion_reason=None,
                )
            ],
        },
    )

    result = get_scoring_ingredients(product, strict=True)

    assert [row["canonical_id"] for row in result.rows] == ["vitamin_c"]
    assert result.rows[0]["scoring_input_kind"] == "recovered_active_identity"
    assert result.rows[0]["scoring_input_recovery_reason"] == "mapped_active_identity_without_disclosed_dose"


def test_active_scorable_canonical_row_excluded_for_missing_dose_is_recovered():
    product = _product(
        [],
        ingredient_quality_data={
            "ingredients_scorable": [],
            "ingredients_skipped": [
                _row(
                    name="Tocotrienol-Tocopherol Complex",
                    canonical_id="vitamin_e",
                    quantity=0,
                    unit="NP",
                    role_classification="inactive_non_scorable",
                    mapped=False,
                    mapped_identity=False,
                    score_eligible_by_cleaner=True,
                    score_exclusion_reason="blend_header_without_dosage",
                    dose_class="therapeutic_mass",
                )
            ],
        },
    )

    result = get_scoring_ingredients(product, strict=True)

    assert [row["canonical_id"] for row in result.rows] == ["vitamin_e"]
    assert result.rows[0]["scoring_input_kind"] == "recovered_active_identity"
    assert result.rows[0]["mapped_identity"] is True


def test_skipped_probiotic_strain_identity_is_recovered_without_inventing_cfu():
    product = _product(
        [],
        ingredient_quality_data={
            "ingredients_scorable": [],
            "ingredients_skipped": [
                _row(
                    name="Lactobacillus gasseri KS-13",
                    canonical_id="lactobacillus_gasseri",
                    quantity=0,
                    unit="NP",
                    cleaner_row_role="nested_display_only",
                    role_classification="inactive_non_scorable",
                    score_eligible_by_cleaner=False,
                    mapped=False,
                    dose_class="zero_or_np",
                )
            ],
        },
    )

    result = get_scoring_ingredients(product, strict=True)

    assert [row["canonical_id"] for row in result.rows] == ["lactobacillus_gasseri"]
    assert result.rows[0]["scoring_input_kind"] == "recovered_active_identity"
    assert result.rows[0]["quantity"] == 0
    assert result.rows[0]["unit"] == "NP"
    assert result.rows[0]["mapped_identity"] is True
    assert result.rows[0]["is_proprietary_blend"] is False


def test_skipped_omega_nested_identity_is_recovered_without_inventing_epa_dha_dose():
    product = _product(
        [],
        ingredient_quality_data={
            "ingredients_scorable": [],
            "ingredients_skipped": [
                _row(
                    name="Eicosapentaenoic Acid",
                    canonical_id="epa",
                    quantity=0,
                    unit="NP",
                    cleaner_row_role="nested_display_only",
                    role_classification="inactive_non_scorable",
                    score_eligible_by_cleaner=False,
                    mapped=False,
                    dose_class="zero_or_np",
                    raw_source_path="ingredientRows[0].nestedRows[0]",
                ),
                _row(
                    name="Docosahexaenoic Acid",
                    canonical_id="dha",
                    quantity=0,
                    unit="NP",
                    cleaner_row_role="nested_display_only",
                    role_classification="inactive_non_scorable",
                    score_eligible_by_cleaner=False,
                    mapped=False,
                    dose_class="zero_or_np",
                    raw_source_path="ingredientRows[0].nestedRows[1]",
                ),
            ],
        },
    )

    result = get_scoring_ingredients(product, strict=True)

    assert [row["canonical_id"] for row in result.rows] == ["epa", "dha"]
    assert all(row["scoring_input_kind"] == "recovered_active_identity" for row in result.rows)
    assert all(row["quantity"] == 0 for row in result.rows)
    assert all(row["unit"] == "NP" for row in result.rows)
    assert all(row["mapped_identity"] is True for row in result.rows)
    assert all(row["is_proprietary_blend"] is False for row in result.rows)


def test_skipped_botanical_nested_identity_is_recovered_when_blend_has_no_mass_anchor():
    product = _product(
        [],
        ingredient_quality_data={
            "ingredients_scorable": [],
            "ingredients_skipped": [
                {
                    "name": "Organic Proprietary Blend",
                    "canonical_id": "BLEND_GENERAL",
                    "raw_source_path": "ingredientRows[0]",
                    "cleaner_row_role": "blend_header_total",
                    "quantity": 1,
                    "unit": "mL",
                    "is_blend_header": True,
                    "blend_total_weight_only": True,
                    "raw_taxonomy": {"category": "blend", "ingredientGroup": "Proprietary Blend"},
                },
                {
                    "name": "Astragalus",
                    "canonical_id": "astragalus",
                    "raw_source_path": "ingredientRows[0].nestedRows[0]",
                    "cleaner_row_role": "nested_display_only",
                    "role_classification": "inactive_non_scorable",
                    "score_eligible_by_cleaner": False,
                    "mapped": False,
                    "quantity": 0,
                    "unit": "NP",
                    "raw_taxonomy": {"category": "botanical", "ingredientGroup": "Astragalus"},
                },
            ],
        },
    )

    result = get_scoring_ingredients(product, strict=True)

    assert [row["canonical_id"] for row in result.rows] == ["astragalus"]
    assert result.rows[0]["scoring_input_kind"] == "recovered_active_identity"
    assert result.rows[0].get("evidence_type") != "blend_anchor_mass"
    assert result.rows[0]["is_proprietary_blend"] is False


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


def test_derived_active_anchor_preserves_botanical_context_for_profile():
    product = _product(
        [],
        product_name="Blessed Thistle 780 mg",
        activeIngredients=[
            {
                "name": "Blessed Thistle",
                "standardName": "Blessed Thistle",
                "canonical_id": "blessed_thistle",
                "canonical_source_db": "botanical_ingredients",
                "quantity": 780,
                "unit": "mg",
                "source_section": "active",
                "raw_source_path": "ingredientRows[0]",
                "cleaner_row_role": "active_scorable",
                "score_eligible_by_cleaner": True,
                "dose_class": "therapeutic_mass",
                "raw_taxonomy": {"category": "botanical", "ingredientGroup": "Blessed Thistle"},
            }
        ],
    )

    result = get_scoring_ingredients(product, strict=True)
    contract = build_scoring_classification(product)

    assert result.rows[0]["canonical_id"] == "blessed_thistle"
    assert result.rows[0]["scoring_input_kind"] == "product_level_evidence"
    assert result.rows[0]["raw_taxonomy"]["category"] == "botanical"
    assert contract["ingredients"][0]["botanical_source"]["value"] is True
    assert "raw_taxonomy_botanical" in contract["ingredients"][0]["botanical_source"]["evidence"]
    assert contract["profile_eligibility"]["botanical"]["eligible"] is True


def test_stale_native_anchor_evidence_is_repaired_with_active_context():
    product = _product(
        [],
        product_name="Blessed Thistle 780 mg",
        activeIngredients=[
            {
                "name": "Blessed Thistle",
                "standardName": "Blessed Thistle",
                "canonical_id": "blessed_thistle",
                "canonical_source_db": "botanical_ingredients",
                "quantity": 780,
                "unit": "mg",
                "source_section": "active",
                "raw_source_path": "ingredientRows[0]",
                "cleaner_row_role": "active_scorable",
                "score_eligible_by_cleaner": True,
                "dose_class": "therapeutic_mass",
                "raw_taxonomy": {"category": "botanical", "ingredientGroup": "Blessed Thistle"},
            }
        ],
        product_scoring_evidence=[
            {
                "evidence_type": "blend_anchor_mass",
                "scoreable": True,
                "scoreable_identity": True,
                "score_eligible_by_cleaner": True,
                "dose_class": "therapeutic_mass",
                "dose_value": 780,
                "dose_unit": "mg",
                "source": "active",
                "raw_source_path": "ingredientRows[0]",
                "evidence_scope": "row_level",
                "linked_rows": ["ingredientRows[0]"],
                "confidence": "medium",
                "reason": "identity_bearing_active_anchor_mass",
                "name": "Blessed Thistle",
                "canonical_id": "blessed_thistle",
                "clean_identity_id": "blessed_thistle",
                "scoring_parent_id": "blessed_thistle",
                "evidence_canonical_id": "blessed_thistle",
                "canonical_source_db": "botanical_ingredients",
                "evidence_origin": "compatibility_derived",
                "source_section": "product",
            }
        ],
    )

    result = get_scoring_ingredients(product, strict=True)
    contract = build_scoring_classification(product)

    assert result.rows[0]["raw_taxonomy"]["category"] == "botanical"
    assert contract["ingredients"][0]["botanical_source"]["value"] is True
    assert contract["profile_eligibility"]["botanical"]["eligible"] is True


def test_stale_embedded_classification_is_rederived_after_contract_bump():
    product = _product(
        [],
        product_name="Blessed Thistle 780 mg",
        activeIngredients=[
            {
                "name": "Blessed Thistle",
                "standardName": "Blessed Thistle",
                "canonical_id": "blessed_thistle",
                "canonical_source_db": "botanical_ingredients",
                "quantity": 780,
                "unit": "mg",
                "source_section": "active",
                "raw_source_path": "ingredientRows[0]",
                "cleaner_row_role": "active_scorable",
                "score_eligible_by_cleaner": True,
                "dose_class": "therapeutic_mass",
                "raw_taxonomy": {"category": "botanical", "ingredientGroup": "Blessed Thistle"},
            }
        ],
        product_scoring_classification={
            "classification_schema_version": "1.1.1",
            "classification_origin": "native_enrichment",
            "classification_failed": False,
            "route_module": "generic",
            "route_reason": "stale_fixture",
            "route_confidence": "medium",
            "route_evidence": ["stale_fixture"],
            "ingredients": [
                {
                    "canonical_id": "blessed_thistle",
                    "name": "Blessed Thistle",
                    "ingredient_domain": "generic_active",
                    "botanical_source": {"value": False, "evidence": []},
                    "profile_eligibility": {"botanical": {"eligible": False, "evidence": []}},
                }
            ],
            "profile_eligibility": {
                "botanical": {"eligible": False, "eligible_row_count": 0, "evidence": []}
            },
        },
    )

    contract = build_scoring_classification(product)

    assert contract["classification_schema_version"] != "1.1.1"
    assert contract["ingredients"][0]["botanical_source"]["value"] is True
    assert contract["profile_eligibility"]["botanical"]["eligible"] is True


def test_botanical_reference_membership_alone_still_does_not_grant_profile():
    product = _product(
        [],
        product_name="Petroselinic Acid 100 mg",
        activeIngredients=[
            {
                "name": "Petroselinic Acid",
                "canonical_id": "petroselinic_acid",
                "canonical_source_db": "botanical_ingredients",
                "quantity": 100,
                "unit": "mg",
                "source_section": "active",
                "raw_source_path": "ingredientRows[0]",
                "cleaner_row_role": "active_scorable",
                "score_eligible_by_cleaner": True,
                "dose_class": "therapeutic_mass",
            }
        ],
    )

    contract = build_scoring_classification(product)

    assert contract["ingredients"][0]["botanical_source"]["value"] is False
    assert contract["profile_eligibility"]["botanical"]["eligible"] is False


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

    assert [row["canonical_id"] for row in result.rows] == ["bacillus_subtilis"]
    assert result.rows[0]["scoring_input_kind"] == "recovered_active_identity"
    assert result.rows[0].get("evidence_type") != "blend_anchor_mass"
    assert result.rows[0]["is_proprietary_blend"] is False


def test_iqm_blend_anchor_mass_carries_conservative_form_quality():
    product = _product(
        [],
        activeIngredients=[
            {
                "name": "Pancreatin",
                "standardName": "Digestive Enzymes",
                "canonical_id": "digestive_enzymes",
                "canonical_source_db": "ingredient_quality_map",
                "quantity": 1.0,
                "unit": "Gram(s)",
                "source_section": "active",
                "raw_source_path": "ingredientRows[0]",
                "cleaner_row_role": "blend_header_total",
                "score_eligible_by_cleaner": False,
                "dose_class": "blend_total_weight",
                "raw_taxonomy": {
                    "category": "blend",
                    "ingredientGroup": "Blend (non-nutrient/non-botanical)",
                    "forms": [{"name": "Porcine"}],
                },
            }
        ],
    )

    result = get_scoring_ingredients(product, strict=True)

    assert len(result.rows) == 1
    row = result.rows[0]
    assert row["evidence_type"] == "blend_anchor_mass"
    assert row["canonical_id"] == "digestive_enzymes"
    assert row["bio_score"] == 11
    assert row["score"] == 14
    assert row["matched_form"] == "pancreatic enzymes (animal-derived)"
    assert row["generic_form_quality_credit"] is True


def test_unmapped_blend_anchor_mass_does_not_get_iqm_form_quality_credit():
    product = _product(
        [],
        activeIngredients=[
            {
                "name": "Relora Patented Proprietary Blend",
                "standardName": "Relora Patented Proprietary Blend",
                "canonical_id": None,
                "canonical_source_db": "unmapped",
                "quantity": 250.0,
                "unit": "mg",
                "source_section": "active",
                "raw_source_path": "ingredientRows[0]",
                "cleaner_row_role": "blend_header_total",
                "score_eligible_by_cleaner": False,
                "dose_class": "blend_total_weight",
                "raw_taxonomy": {
                    "category": "blend",
                    "ingredientGroup": "Proprietary Blend (Herb/Botanical)",
                },
            }
        ],
    )

    result = get_scoring_ingredients(product, strict=True)

    assert len(result.rows) == 1
    row = result.rows[0]
    assert row["evidence_type"] == "blend_anchor_mass"
    assert row["canonical_id"] == "relora_patented_proprietary_blend"
    assert row.get("bio_score") is None
    assert row["generic_form_quality_credit"] is False


def test_nutrition_only_uses_explicit_contract_not_keywords_by_default():
    assert is_nutrition_only_product({"product_name": "Whey Protein Powder"}) is False
    assert is_nutrition_only_product({"product_scoring_class": "nutrition_only"}) is True
    assert is_nutrition_only_product(
        {"product_name": "Whey Protein Powder"},
        allow_legacy_keyword_fallback=True,
    ) is True


# --- Task 3: strict scoring-input identity disposition guard ---
# _row() defaults scoreable_identity=True, so passing a non-scoreable disposition
# reproduces the malformed upstream invariant: a row that claims to be scoreable
# while its identity disposition says otherwise. Strict mode must reject it and
# fail the contract; non-strict mode keeps the old-batch behavior.


def test_identity_integrity_strict_rejects_conflict_disposition_even_when_flag_true():
    result = get_scoring_ingredients(
        _product([_row(identity_disposition="identity_conflict")]),
        strict=True,
    )

    assert result.rows == []
    assert any(
        r.reason.startswith("identity_disposition_not_scoreable")
        for r in result.rejected_rows
    )
    assert result.strict_contract_passed is False


def test_identity_integrity_strict_rejects_missing_display_label_disposition():
    result = get_scoring_ingredients(
        _product([_row(identity_disposition="missing_display_label")]),
        strict=True,
    )

    assert result.rows == []
    assert result.strict_contract_passed is False


def test_identity_integrity_strict_rejects_unrecognized_disposition():
    result = get_scoring_ingredients(
        _product([_row(identity_disposition="totally_bogus")]),
        strict=True,
    )

    assert result.rows == []
    assert any(
        r.reason.startswith("invalid_identity_disposition")
        for r in result.rejected_rows
    )
    assert result.strict_contract_passed is False


def test_identity_integrity_strict_accepts_scoreable_dispositions():
    for disposition in ("clean", "repaired", "taxonomy_only"):
        result = get_scoring_ingredients(
            _product([_row(identity_disposition=disposition)]),
            strict=True,
        )
        assert [r["canonical_id"] for r in result.rows] == ["magnesium"], disposition
        assert result.strict_contract_passed is True, disposition


def test_identity_integrity_non_strict_tolerates_conflict_for_old_batch():
    result = get_scoring_ingredients(
        _product([_row(identity_disposition="identity_conflict")]),
        strict=False,
    )

    assert [r["canonical_id"] for r in result.rows] == ["magnesium"]


def test_identity_integrity_conflict_row_is_not_recovered_into_scoring():
    # A skipped row with a usable anchor but an unresolved identity must not be
    # recovered into scoring inputs at all — an unresolved conflict cannot drive
    # scoring, evidence, or interactions (design contract). Recovering it only to
    # reject it downstream would still let it briefly claim scoreable_identity.
    conflict = _row(
        name="UC-II standardized Cartilage",
        canonical_id="collagen",
        identity_disposition="identity_conflict",
        scoreable_identity=False,
        raw_source_path="activeIngredients[0]",
    )
    product = _product(
        [],
        ingredient_quality_data={
            "ingredients_scorable": [],
            "ingredients_skipped": [conflict],
        },
    )
    result = get_scoring_ingredients(product, strict=True)

    assert result.rows == []
    assert not any(
        r.row.get("scoring_input_kind") == "recovered_active_identity"
        for r in result.rejected_rows
    )


def test_identity_integrity_scoreable_skipped_row_is_still_recovered():
    # Control: a skipped row with a resolved identity is still recovered so the
    # guard does not over-suppress legitimate mapped-active-without-dose rows.
    clean = _row(
        name="Vitamin C",
        canonical_id="vitamin_c",
        identity_disposition="clean",
        scoreable_identity=True,
        quantity=0,
        unit="NP",
        raw_source_path="activeIngredients[0]",
    )
    product = _product(
        [],
        ingredient_quality_data={
            "ingredients_scorable": [],
            "ingredients_skipped": [clean],
        },
    )
    result = get_scoring_ingredients(product, strict=True)

    assert [r["canonical_id"] for r in result.rows] == ["vitamin_c"]
    assert result.rows[0]["scoring_input_kind"] == "recovered_active_identity"
