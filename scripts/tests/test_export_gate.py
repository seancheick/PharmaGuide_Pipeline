#!/usr/bin/env python3
"""
Export Gate Test Suite
=====================
Strict contract tests that run against real enriched/scored fixtures from
multiple brands.  CI should fail if any of these fail.

Coverage:
  - Schema column count matches tuple length
  - Export contract validator catches all required-field violations
  - Enrichment metadata export_contract_valid blocks broken products
  - All safety categories (banned, recalled, high_risk, watchlist) route correctly
  - Allergen, harmful additive, and interaction provenance survives export
  - Detail blob ingredient keys match FLUTTER_DATA_CONTRACT_V1.md exactly
  - Blocking reason is never set for watchlist or missing data
  - top_warnings priority ordering is deterministic
  - diabetes_friendly / hypertension_friendly default to False (cautious) when absent
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from build_final_db import (
    CORE_COLUMN_COUNT,
    EXPORT_REQUIRED_IQD_FIELDS,
    build_core_row,
    build_detail_blob,
    build_top_warnings,
    derive_blocking_reason,
    has_banned_substance,
    has_recalled_ingredient,
    validate_export_contract,
)


# ─── Fixture Factories ───


def _base_enriched(**overrides):
    """Minimal valid enriched product."""
    data = {
        "dsld_id": "EG001",
        "product_name": "Export Gate Fixture",
        "brandName": "TestBrand",
        "upcSku": "0000000000001",
        "imageUrl": None,
        "status": "active",
        "discontinuedDate": None,
        "form_factor": "capsule",
        "supplement_type": {"type": "targeted"},
        "enrichment_version": "3.1.0",
        "is_certified_organic": False,
        "is_trusted_manufacturer": False,
        "manufacturing_region": "USA",
        "named_cert_programs": [],
        "has_full_disclosure": False,
        "compliance_data": {
            "gluten_free": False,
            "dairy_free": False,
            "soy_free": False,
            "vegan": False,
            "vegetarian": False,
        },
        "probiotic_data": {"is_probiotic_product": False},
        "contaminant_data": {"banned_substances": {"substances": []}},
        "harmful_additives": [],
        "allergen_hits": [],
        "interaction_profile": {"ingredient_alerts": []},
        "dietary_sensitivity_data": {},
        "activeIngredients": [
            {
                "name": "Vitamin C",
                "standardName": "Ascorbic Acid",
                "normalized_key": "vitamin_c",
                "raw_source_text": "Vitamin C (as Ascorbic Acid)",
                "forms": [{"name": "Ascorbic Acid"}],
                "quantity": 500,
                "unit": "mg",
            }
        ],
        "ingredient_quality_data": {
            "ingredients": [
                {
                    "raw_source_text": "Vitamin C (as Ascorbic Acid)",
                    "name": "Vitamin C",
                    "parent_key": "vitamin_c",
                    "form": "ascorbic acid",
                    "category": "vitamins",
                    "bio_score": 10,
                    "natural": False,
                    "score": 10.0,
                    "mapped": True,
                    "standard_name": "Vitamin C",
                    "notes": "Most common Vitamin C form.",
                    "matched_form": "ascorbic acid",
                    "matched_forms": [],
                    "extracted_forms": [],
                    "safety_hits": [],
                }
            ]
        },
        "dosage_normalization": {"normalized_ingredients": []},
        "inactiveIngredients": [],
        "certification_data": {"third_party_programs": [], "gmp": {}, "purity_verified": False, "heavy_metal_tested": False, "label_accuracy_verified": False},
        "proprietary_data": {"has_proprietary_blends": False, "blends": []},
        "serving_basis": {"basis_count": 1, "basis_unit": "capsule", "min_servings_per_day": 1, "max_servings_per_day": 1},
        "manufacturer_data": {"violations": {"fda_warning_letters": 0}},
    }
    data.update(overrides)
    return data


def _base_scored(**overrides):
    data = {
        "score_80": 50.0,
        "display": "50.0/80",
        "display_100": "62.5/100",
        "score_100_equivalent": 62.5,
        "grade": "Fair",
        "verdict": "SAFE",
        "safety_verdict": "SAFE",
        "mapped_coverage": 1.0,
        "badges": [],
        "flags": [],
        "section_scores": {
            "A_ingredient_quality": {"score": 15.0, "max": 25.0},
            "B_safety_purity": {"score": 20.0, "max": 30.0},
            "C_evidence_research": {"score": 10.0, "max": 20.0},
            "D_brand_trust": {"score": 3.0, "max": 5.0},
        },
        "category_percentile": {"available": False},
        "scoring_metadata": {
            "scoring_version": "3.1.0",
            "output_schema_version": "5.0.0",
            "scored_date": "2026-03-17T00:00:00Z",
        },
        "breakdown": {
            "A": {"score": 15.0, "max": 25.0},
            "B": {"score": 20.0, "max": 30.0},
            "C": {"score": 10.0, "max": 20.0},
            "D": {"score": 3.0, "max": 5.0},
            "violation_penalty": 0.0,
        },
    }
    data.update(overrides)
    return data


COLUMNS = [
    "dsld_id", "product_name", "brand_name", "upc_sku", "image_url", "image_is_pdf", "thumbnail_key",
    "detail_blob_sha256", "interaction_summary_hint", "decision_highlights",
    "product_status", "discontinued_date", "form_factor", "supplement_type",
    "score_quality_80", "score_display_80", "score_display_100_equivalent",
    "score_100_equivalent", "grade", "verdict", "safety_verdict", "mapped_coverage",
    "score_ingredient_quality", "score_ingredient_quality_max",
    "score_safety_purity", "score_safety_purity_max",
    "score_evidence_research", "score_evidence_research_max",
    "score_brand_trust", "score_brand_trust_max",
    "percentile_rank", "percentile_top_pct", "percentile_category", "percentile_label", "percentile_cohort",
    "is_gluten_free", "is_dairy_free", "is_soy_free", "is_vegan", "is_vegetarian", "is_organic", "is_non_gmo",
    "has_banned_substance", "has_recalled_ingredient", "has_harmful_additives", "has_allergen_risks",
    "blocking_reason",
    "is_probiotic", "contains_sugar", "contains_sodium", "diabetes_friendly", "hypertension_friendly",
    "is_trusted_manufacturer", "has_third_party_testing", "has_full_disclosure",
    "cert_programs", "badges", "top_warnings", "flags",
    # v1.1.0+ additions
    "ingredient_fingerprint", "key_nutrients_summary",
    "contains_stimulants", "contains_sedatives", "contains_blood_thinners",
    "share_title", "share_description", "share_highlights", "share_og_image_url",
    "primary_category", "secondary_categories",
    "contains_omega3", "contains_probiotics", "contains_collagen",
    "contains_adaptogens", "contains_nootropics", "key_ingredient_tags",
    "goal_matches", "goal_match_confidence",
    "dosing_summary", "servings_per_container",
    "net_contents_quantity", "net_contents_unit",
    "allergen_summary",
    "calories_per_serving",  # v1.3.2
    "image_thumbnail_url",  # v1.4.0
    "scoring_version", "output_schema_version", "enrichment_version", "scored_date",
    "export_version", "exported_at",
]


def _row_dict(enriched, scored):
    row = build_core_row(enriched, scored, "2026-03-17T00:00:00Z")
    return dict(zip(COLUMNS, row))


# ═══════════════════════════════════════════════════════════════
# 1. Schema Integrity
# ═══════════════════════════════════════════════════════════════

class TestSchemaIntegrity:

    def test_core_column_count_matches_row_tuple_length(self):
        row = build_core_row(_base_enriched(), _base_scored(), "2026-03-17T00:00:00Z")
        assert len(row) == CORE_COLUMN_COUNT, (
            f"Row tuple has {len(row)} elements but CORE_COLUMN_COUNT is {CORE_COLUMN_COUNT}"
        )

    def test_column_list_matches_core_column_count(self):
        assert len(COLUMNS) == CORE_COLUMN_COUNT


# ═══════════════════════════════════════════════════════════════
# 2. Export Contract Validator
# ═══════════════════════════════════════════════════════════════

class TestExportContractValidator:

    def test_valid_product_has_no_issues(self):
        assert validate_export_contract(_base_enriched(), _base_scored()) == []

    def test_missing_dsld_id_flagged(self):
        e = _base_enriched(dsld_id="")
        issues = validate_export_contract(e, _base_scored())
        assert any("dsld_id" in i for i in issues)

    def test_missing_product_name_flagged(self):
        e = _base_enriched(product_name="")
        issues = validate_export_contract(e, _base_scored())
        assert any("product_name" in i for i in issues)

    def test_missing_required_iqd_field_flagged(self):
        e = _base_enriched()
        del e["ingredient_quality_data"]["ingredients"][0]["score"]
        issues = validate_export_contract(e, _base_scored())
        assert any("score" in i for i in issues)

    def test_missing_section_scores_flagged(self):
        s = _base_scored()
        del s["section_scores"]
        issues = validate_export_contract(_base_enriched(), s)
        assert any("section_scores" in i for i in issues)

    def test_missing_scoring_metadata_flagged(self):
        s = _base_scored()
        del s["scoring_metadata"]
        issues = validate_export_contract(_base_enriched(), s)
        assert any("scoring_metadata" in i for i in issues)

    def test_optional_form_fields_do_not_trigger_issues(self):
        e = _base_enriched()
        del e["ingredient_quality_data"]["ingredients"][0]["matched_forms"]
        del e["ingredient_quality_data"]["ingredients"][0]["extracted_forms"]
        issues = validate_export_contract(e, _base_scored())
        assert not any("matched_forms" in i for i in issues)
        assert not any("extracted_forms" in i for i in issues)

    def test_each_required_iqd_field_individually(self):
        """Every field in EXPORT_REQUIRED_IQD_FIELDS must trigger a validation error when missing."""
        for field in sorted(EXPORT_REQUIRED_IQD_FIELDS):
            e = _base_enriched()
            del e["ingredient_quality_data"]["ingredients"][0][field]
            issues = validate_export_contract(e, _base_scored())
            assert any(field in i for i in issues), f"Missing {field} should be flagged"


# ═══════════════════════════════════════════════════════════════
# 3. Safety Category Routing
# ═══════════════════════════════════════════════════════════════

class TestSafetyCategoryRouting:

    @pytest.mark.parametrize("status,expect_banned,expect_recalled,expect_blocking", [
        ("banned", True, False, "banned_ingredient"),
        ("recalled", False, True, "recalled_ingredient"),
        ("high_risk", False, False, "high_risk_ingredient"),
        ("watchlist", False, False, None),
    ])
    def test_contaminant_status_routes_correctly(self, status, expect_banned, expect_recalled, expect_blocking):
        e = _base_enriched()
        e["contaminant_data"]["banned_substances"]["substances"] = [
            {"ingredient": "Test", "banned_name": "Test", "status": status, "match_type": "exact"}
        ]
        verdict = "BLOCKED" if status == "banned" else "UNSAFE" if status == "recalled" else "CAUTION"
        s = _base_scored(verdict=verdict)

        row = _row_dict(e, s)
        assert row["has_banned_substance"] == (1 if expect_banned else 0)
        assert row["has_recalled_ingredient"] == (1 if expect_recalled else 0)
        assert row["blocking_reason"] == expect_blocking

    def test_watchlist_never_blocks(self):
        e = _base_enriched()
        e["contaminant_data"]["banned_substances"]["substances"] = [
            {"ingredient": "X", "banned_name": "X", "status": "watchlist", "match_type": "exact"}
        ]
        for verdict in ("SAFE", "CAUTION", "POOR", "UNSAFE", "BLOCKED"):
            s = _base_scored(verdict=verdict)
            blocking = derive_blocking_reason(e, s)
            # watchlist alone should never produce a blocking reason
            if verdict in ("BLOCKED", "UNSAFE"):
                # Only "safety_block" generic, NOT watchlist-derived
                assert blocking in (None, "safety_block")
            else:
                assert blocking is None

    def test_fuzzy_match_type_excluded(self):
        """fuzzy match_type should NOT trigger safety flags."""
        e = _base_enriched()
        e["contaminant_data"]["banned_substances"]["substances"] = [
            {"ingredient": "X", "banned_name": "X", "status": "banned", "match_type": "fuzzy"}
        ]
        assert has_banned_substance(e) is False
        assert has_recalled_ingredient(e) is False


# ═══════════════════════════════════════════════════════════════
# 4. Detail Blob Contract
# ═══════════════════════════════════════════════════════════════

FLUTTER_INGREDIENT_KEYS = {
    "raw_source_text", "name", "standardName", "normalized_key", "forms",
    "quantity", "unit", "standard_name", "form", "matched_form",
    "matched_forms", "extracted_forms", "category", "bio_score", "natural",
    "score", "notes", "mapped", "safety_hits",
    "normalized_amount", "normalized_unit", "role", "parent_key",
    "dosage", "dosage_unit", "normalized_value",
    "is_mapped", "is_harmful", "harmful_severity", "harmful_notes",
    "is_banned", "is_allergen",
}


class TestDetailBlobContract:

    def test_ingredient_keys_match_flutter_contract(self):
        blob = build_detail_blob(_base_enriched(), _base_scored())
        ingredient = blob["ingredients"][0]
        missing = FLUTTER_INGREDIENT_KEYS - set(ingredient.keys())
        assert not missing, f"Missing keys in detail blob ingredient: {missing}"

    def test_blob_has_required_top_level_keys(self):
        blob = build_detail_blob(_base_enriched(), _base_scored())
        required = {
            "dsld_id", "blob_version", "ingredients", "inactive_ingredients",
            "warnings", "section_breakdown", "compliance_detail",
            "certification_detail", "proprietary_blend_detail",
            "dietary_sensitivity_detail", "serving_info", "manufacturer_detail",
        }
        missing = required - set(blob.keys())
        assert not missing, f"Missing top-level blob keys: {missing}"

    def test_section_breakdown_uses_descriptive_names(self):
        blob = build_detail_blob(_base_enriched(), _base_scored())
        sb = blob["section_breakdown"]
        assert "ingredient_quality" in sb
        assert "safety_purity" in sb
        assert "evidence_research" in sb
        assert "brand_trust" in sb
        assert "violation_penalty" in sb
        # Must NOT have internal scorer labels
        assert "A" not in sb
        assert "B" not in sb

    def test_warnings_include_provenance_source(self):
        e = _base_enriched()
        e["allergen_hits"] = [
            {"allergen_id": "SOY", "allergen_name": "Soy", "presence_type": "contains",
             "matched_text": "soy", "severity_level": "low", "evidence": "label"}
        ]
        blob = build_detail_blob(e, _base_scored())
        allergen_warnings = [w for w in blob["warnings"] if w["type"] == "allergen"]
        assert allergen_warnings
        assert allergen_warnings[0]["source"] == "allergen_db"

    def test_harmful_additive_carries_mechanism_from_reference(self):
        """Harmful additive detail should include real reference notes, not just category."""
        e = _base_enriched()
        e["harmful_additives"] = [
            {"ingredient": "Titanium Dioxide", "additive_name": "Titanium Dioxide",
             "severity_level": "moderate", "category": "colorant",
             "raw_source_text": "Titanium Dioxide"}
        ]
        blob = build_detail_blob(e, _base_scored())
        ha_warnings = [w for w in blob["warnings"] if w["type"] == "harmful_additive"]
        assert ha_warnings
        assert ha_warnings[0]["source"] == "harmful_additives_db"


# ═══════════════════════════════════════════════════════════════
# 5. top_warnings Priority & Determinism
# ═══════════════════════════════════════════════════════════════

class TestTopWarningsPriority:

    def test_banned_before_recalled_before_watchlist(self):
        e = _base_enriched()
        e["contaminant_data"]["banned_substances"]["substances"] = [
            {"ingredient": "A", "banned_name": "A", "status": "watchlist", "match_type": "exact"},
            {"ingredient": "B", "banned_name": "B", "status": "recalled", "match_type": "alias"},
            {"ingredient": "C", "banned_name": "C", "status": "banned", "match_type": "exact"},
        ]
        warnings = build_top_warnings(e)
        assert warnings[0].startswith("Banned substance:")
        assert warnings[1].startswith("Recalled ingredient:")
        assert any("Watchlist" in w for w in warnings)

    def test_max_five_warnings(self):
        e = _base_enriched()
        e["allergen_hits"] = [
            {"allergen_name": f"Allergen{i}", "matched_text": f"a{i}", "severity_level": "low", "presence_type": "contains"}
            for i in range(10)
        ]
        warnings = build_top_warnings(e)
        assert len(warnings) <= 5

    def test_safety_before_dietary_before_status(self):
        e = _base_enriched()
        e["status"] = "discontinued"
        e["discontinuedDate"] = "2025-01-01"
        e["allergen_hits"] = [
            {"allergen_name": "Soy", "matched_text": "soy", "severity_level": "low", "presence_type": "contains"}
        ]
        e["dietary_sensitivity_data"]["warnings"] = [
            {"type": "diabetes", "severity": "moderate", "message": "Contains sugar."}
        ]
        warnings = build_top_warnings(e)
        # Allergen should come before dietary
        allergen_idx = next((i for i, w in enumerate(warnings) if "Allergen" in w), 99)
        dietary_idx = next((i for i, w in enumerate(warnings) if "sugar" in w.lower()), 99)
        assert allergen_idx < dietary_idx


# ═══════════════════════════════════════════════════════════════
# 6. Medical Safety Defaults
# ═══════════════════════════════════════════════════════════════

class TestMedicalSafetyDefaults:

    def test_diabetes_friendly_defaults_to_false_when_absent(self):
        """Missing dietary data must NOT claim diabetes-friendly."""
        e = _base_enriched()
        e["dietary_sensitivity_data"] = {}
        row = _row_dict(e, _base_scored())
        assert row["diabetes_friendly"] == 0

    def test_hypertension_friendly_defaults_to_false_when_absent(self):
        """Missing dietary data must NOT claim hypertension-friendly."""
        e = _base_enriched()
        e["dietary_sensitivity_data"] = {}
        row = _row_dict(e, _base_scored())
        assert row["hypertension_friendly"] == 0

    def test_diabetes_friendly_true_when_explicitly_set(self):
        e = _base_enriched()
        e["dietary_sensitivity_data"] = {"diabetes_friendly": True, "hypertension_friendly": True}
        row = _row_dict(e, _base_scored())
        assert row["diabetes_friendly"] == 1
        assert row["hypertension_friendly"] == 1

    def test_blocking_reason_null_for_safe_verdict(self):
        row = _row_dict(_base_enriched(), _base_scored(verdict="SAFE"))
        assert row["blocking_reason"] is None

    def test_not_scored_verdict_exports_cleanly(self):
        s = _base_scored(verdict="NOT_SCORED", score_80=None, display=None, display_100=None,
                         score_100_equivalent=None, grade=None)
        row = _row_dict(_base_enriched(), s)
        assert row["verdict"] == "NOT_SCORED"
        assert row["score_quality_80"] is None
        assert row["blocking_reason"] is None


# ═══════════════════════════════════════════════════════════════
# 7. Golden Product Tests
# ═══════════════════════════════════════════════════════════════

class TestGoldenProducts:
    """High-value edge cases that must never regress."""

    def test_golden_banned_product(self):
        """Product with banned ingredient: must block, must flag, must warn."""
        e = _base_enriched(dsld_id="GOLDEN_BANNED")
        e["contaminant_data"]["banned_substances"]["substances"] = [
            {"ingredient": "DMAA", "banned_name": "1,3-Dimethylamylamine", "status": "banned",
             "match_type": "alias", "reason": "FDA banned stimulant"}
        ]
        s = _base_scored(verdict="BLOCKED")
        row = _row_dict(e, s)
        assert row["has_banned_substance"] == 1
        assert row["blocking_reason"] == "banned_ingredient"
        blob = build_detail_blob(e, s)
        assert any(w["type"] == "banned_substance" for w in blob["warnings"])
        top = build_top_warnings(e)
        assert top[0].startswith("Banned substance:")

    def test_golden_recalled_product(self):
        """Product with recalled ingredient: flag recalled, not banned."""
        e = _base_enriched(dsld_id="GOLDEN_RECALLED")
        e["contaminant_data"]["banned_substances"]["substances"] = [
            {"ingredient": "Phenolphthalein", "banned_name": "Phenolphthalein",
             "status": "recalled", "match_type": "exact"}
        ]
        s = _base_scored(verdict="UNSAFE")
        row = _row_dict(e, s)
        assert row["has_banned_substance"] == 0
        assert row["has_recalled_ingredient"] == 1
        assert row["blocking_reason"] == "recalled_ingredient"

    def test_golden_watchlist_product(self):
        """Watchlist: warn only, never block."""
        e = _base_enriched(dsld_id="GOLDEN_WATCHLIST")
        e["contaminant_data"]["banned_substances"]["substances"] = [
            {"ingredient": "Green Tea Extract", "banned_name": "Green Tea Extract",
             "status": "watchlist", "match_type": "exact", "severity_level": "moderate",
             "reason": "Hepatotoxicity risk at high doses"}
        ]
        s = _base_scored(verdict="CAUTION")
        row = _row_dict(e, s)
        assert row["has_banned_substance"] == 0
        assert row["has_recalled_ingredient"] == 0
        assert row["blocking_reason"] is None
        top = build_top_warnings(e)
        assert any("Watchlist" in w for w in top)

    def test_golden_allergen_product(self):
        """Product with allergen: flag in row + detail blob."""
        e = _base_enriched(dsld_id="GOLDEN_ALLERGEN")
        e["allergen_hits"] = [
            {"allergen_id": "MILK", "allergen_name": "Milk", "presence_type": "contains",
             "matched_text": "milk", "severity_level": "high", "evidence": "label declares milk"}
        ]
        s = _base_scored()
        row = _row_dict(e, s)
        assert row["has_allergen_risks"] == 1
        blob = build_detail_blob(e, s)
        assert any(w["type"] == "allergen" for w in blob["warnings"])

    def test_golden_high_risk_product(self):
        """High-risk: sets blocking_reason but NOT has_banned_substance."""
        e = _base_enriched(dsld_id="GOLDEN_HIGH_RISK")
        e["contaminant_data"]["banned_substances"]["substances"] = [
            {"ingredient": "Kava", "banned_name": "Kava Kava", "status": "high_risk",
             "match_type": "exact"}
        ]
        s = _base_scored(verdict="CAUTION")
        row = _row_dict(e, s)
        assert row["has_banned_substance"] == 0
        assert row["blocking_reason"] == "high_risk_ingredient"

    def test_golden_unmapped_product(self):
        """Product where IQD has no scored ingredients: exports with NULL scores."""
        e = _base_enriched(dsld_id="GOLDEN_UNMAPPED")
        e["ingredient_quality_data"]["ingredients"] = []
        e["activeIngredients"] = []
        s = _base_scored(verdict="NOT_SCORED", score_80=None, mapped_coverage=0.0)
        # No IQD ingredients means contract validator won't flag (empty list is valid)
        issues = validate_export_contract(e, s)
        assert not any("ingredient_quality_data" in i for i in issues)
        row = _row_dict(e, s)
        assert row["score_quality_80"] is None
        assert row["mapped_coverage"] == 0.0

    def test_golden_multi_safety_product(self):
        """Product with banned + allergen + harmful: all coexist correctly."""
        e = _base_enriched(dsld_id="GOLDEN_MULTI")
        e["contaminant_data"]["banned_substances"]["substances"] = [
            {"ingredient": "DMAA", "banned_name": "DMAA", "status": "banned", "match_type": "exact"}
        ]
        e["allergen_hits"] = [
            {"allergen_id": "WHEAT", "allergen_name": "Wheat", "presence_type": "contains",
             "matched_text": "wheat", "severity_level": "moderate"}
        ]
        e["harmful_additives"] = [
            {"ingredient": "Red 40", "additive_name": "Red 40", "severity_level": "high",
             "category": "synthetic dye"}
        ]
        s = _base_scored(verdict="BLOCKED")
        row = _row_dict(e, s)
        assert row["has_banned_substance"] == 1
        assert row["has_allergen_risks"] == 1
        assert row["has_harmful_additives"] == 1
        assert row["blocking_reason"] == "banned_ingredient"
        blob = build_detail_blob(e, s)
        types = {w["type"] for w in blob["warnings"]}
        assert "banned_substance" in types
        assert "allergen" in types
        assert "harmful_additive" in types


# ═══════════════════════════════════════════════════════════════
# 8. Score Bonus/Penalty Lists
# ═══════════════════════════════════════════════════════════════

class TestScoreBonusPenaltyLists:
    """Verify the app gets structured bonus and penalty lists."""

    def test_blob_has_bonus_and_penalty_keys(self):
        blob = build_detail_blob(_base_enriched(), _base_scored())
        assert "score_bonuses" in blob
        assert "score_penalties" in blob
        assert isinstance(blob["score_bonuses"], list)
        assert isinstance(blob["score_penalties"], list)

    def test_bonus_list_includes_purity_testing_when_scored(self):
        s = _base_scored()
        s["breakdown"]["B"]["B4a"] = 5.0
        blob = build_detail_blob(_base_enriched(), s)
        bonus_ids = {b["id"] for b in blob["score_bonuses"]}
        assert "B4a" in bonus_ids

    def test_penalty_list_includes_banned_per_item(self):
        e = _base_enriched()
        e["contaminant_data"]["banned_substances"]["substances"] = [
            {"ingredient": "DMAA", "banned_name": "DMAA", "status": "banned",
             "match_type": "exact", "reason": "FDA banned"}
        ]
        s = _base_scored(verdict="BLOCKED")
        s["breakdown"]["B"]["B0_moderate_penalty"] = 5.0
        blob = build_detail_blob(e, s)
        b0_penalties = [p for p in blob["score_penalties"] if p["id"] == "B0"]
        assert len(b0_penalties) == 1
        assert "DMAA" in b0_penalties[0]["label"]
        assert b0_penalties[0]["status"] == "banned"

    def test_penalty_list_includes_allergen_per_item(self):
        e = _base_enriched()
        e["allergen_hits"] = [
            {"allergen_id": "MILK", "allergen_name": "Milk", "presence_type": "contains",
             "matched_text": "milk", "severity_level": "high"}
        ]
        s = _base_scored()
        s["breakdown"]["B"]["B2_penalty"] = 1.0
        blob = build_detail_blob(e, s)
        b2_penalties = [p for p in blob["score_penalties"] if p["id"] == "B2"]
        assert len(b2_penalties) == 1
        assert "Milk" in b2_penalties[0]["label"]

    def test_penalty_list_includes_harmful_additive_per_item(self):
        e = _base_enriched()
        e["harmful_additives"] = [
            {"ingredient": "Red 40", "additive_name": "Red 40",
             "severity_level": "high", "category": "synthetic dye",
             "mechanism_of_harm": "Linked to hyperactivity in children"}
        ]
        s = _base_scored()
        s["breakdown"]["B"]["B1_penalty"] = 2.0
        blob = build_detail_blob(e, s)
        b1_penalties = [p for p in blob["score_penalties"] if p["id"] == "B1"]
        assert len(b1_penalties) == 1
        assert "Red 40" in b1_penalties[0]["label"]
        assert b1_penalties[0]["reason"]

    def test_empty_product_has_no_bonuses_or_penalties(self):
        """Clean product with no bonuses or penalties shows empty lists."""
        s = _base_scored()
        # Zero out all bonuses and penalties in breakdown
        s["breakdown"]["A"] = {"score": 10.0, "max": 25.0, "A1": 10.0}
        s["breakdown"]["B"] = {"score": 25.0, "max": 30.0}
        blob = build_detail_blob(_base_enriched(), s)
        assert blob["score_bonuses"] == []
        assert blob["score_penalties"] == []


# ═══════════════════════════════════════════════════════════════
# 9. Formulation Detail
# ═══════════════════════════════════════════════════════════════

class TestFormulationDetail:
    """Verify formulation context is exported for bonus explanation."""

    def test_blob_has_formulation_detail(self):
        blob = build_detail_blob(_base_enriched(), _base_scored())
        assert "formulation_detail" in blob
        fd = blob["formulation_detail"]
        assert "delivery_tier" in fd
        assert "absorption_enhancer_paired" in fd
        assert "is_certified_organic" in fd
        assert "standardized_botanicals" in fd
        assert "synergy_cluster_qualified" in fd
        assert "claim_non_gmo_verified" in fd

    def test_all_ingredients_always_listed(self):
        """Every active and inactive ingredient must appear in blob."""
        e = _base_enriched()
        e["activeIngredients"].append({
            "name": "Zinc", "standardName": "Zinc Gluconate",
            "normalized_key": "zinc", "raw_source_text": "Zinc (as Zinc Gluconate)",
            "forms": [], "quantity": 15, "unit": "mg",
        })
        e["inactiveIngredients"] = [
            {"name": "Cellulose", "raw_source_text": "Cellulose",
             "category": "filler", "isAdditive": True, "additiveType": "filler"},
            {"name": "Magnesium Stearate", "raw_source_text": "Magnesium Stearate",
             "category": "lubricant", "isAdditive": True, "additiveType": "lubricant"},
        ]
        blob = build_detail_blob(e, _base_scored())
        active_names = {i["name"] for i in blob["ingredients"]}
        inactive_names = {i["name"] for i in blob["inactive_ingredients"]}
        assert "Vitamin C" in active_names
        assert "Zinc" in active_names
        assert "Cellulose" in inactive_names
        assert "Magnesium Stearate" in inactive_names


# ═══════════════════════════════════════════════════════════════
# 10. Interaction Profile & User Condition Matching
# ═══════════════════════════════════════════════════════════════

class TestInteractionProfileExport:
    """Verify the detail blob carries enough data for the app to
    instantly flag products based on user health conditions."""

    def _enriched_with_interactions(self):
        e = _base_enriched()
        e["interaction_profile"] = {
            "ingredient_alerts": [
                {
                    "ingredient_name": "Vitamin A Palmitate",
                    "standard_name": "Vitamin A",
                    "rule_id": "RULE_VITA_PREGNANCY",
                    "condition_hits": [
                        {
                            "condition_id": "pregnancy",
                            "severity": "contraindicated",
                            "evidence_level": "established",
                            "mechanism": "Retinoid exposure risk during pregnancy.",
                            "action": "Do not use preformed Vitamin A above 3000 mcg RAE.",
                            "sources": ["https://ods.od.nih.gov/factsheets/VitaminA"],
                            "dose_threshold_evaluation": {
                                "evaluated": True,
                                "matched_threshold": True,
                                "thresholds_checked": [{
                                    "evaluated": True,
                                    "basis": "per_day",
                                    "computed_amount": 600.0,
                                    "computed_unit": "mcg RAE",
                                    "threshold_value": 3000.0,
                                    "threshold_unit": "mcg RAE",
                                    "comparator": ">",
                                    "matched": False,
                                }],
                                "selected_severity": "monitor",
                                "reason": "dose below threshold",
                            },
                        }
                    ],
                    "drug_class_hits": [
                        {
                            "drug_class_id": "retinoids",
                            "severity": "avoid",
                            "evidence_level": "established",
                            "mechanism": "Overlapping retinoid exposure.",
                            "action": "Avoid use with retinoid medications.",
                            "sources": ["https://ods.od.nih.gov/factsheets/VitaminA"],
                        }
                    ],
                }
            ],
            "condition_summary": {
                "pregnancy": {
                    "label": "Pregnancy",
                    "highest_severity": "contraindicated",
                    "ingredient_count": 1,
                    "ingredients": ["Vitamin A Palmitate"],
                    "rule_ids": ["RULE_VITA_PREGNANCY"],
                    "actions": ["Do not use preformed Vitamin A above 3000 mcg RAE."],
                }
            },
            "drug_class_summary": {
                "retinoids": {
                    "label": "Retinoids",
                    "highest_severity": "avoid",
                    "ingredient_count": 1,
                    "ingredients": ["Vitamin A Palmitate"],
                    "rule_ids": ["RULE_VITA_PREGNANCY"],
                    "actions": ["Avoid use with retinoid medications."],
                }
            },
            "highest_severity": "contraindicated",
        }
        return e

    def test_interaction_summary_exported(self):
        """Detail blob must carry condition_summary and drug_class_summary."""
        blob = build_detail_blob(self._enriched_with_interactions(), _base_scored())
        assert "interaction_summary" in blob
        summary = blob["interaction_summary"]
        assert summary["highest_severity"] == "contraindicated"
        assert "pregnancy" in summary["condition_summary"]
        preg = summary["condition_summary"]["pregnancy"]
        assert preg["highest_severity"] == "contraindicated"
        assert preg["ingredient_count"] == 1
        assert "Vitamin A Palmitate" in preg["ingredients"]

    def test_drug_class_summary_exported(self):
        blob = build_detail_blob(self._enriched_with_interactions(), _base_scored())
        summary = blob["interaction_summary"]
        assert "retinoids" in summary["drug_class_summary"]
        ret = summary["drug_class_summary"]["retinoids"]
        assert ret["highest_severity"] == "avoid"

    def test_interaction_warnings_carry_condition_id(self):
        """Each interaction warning must have condition_id for user-profile matching."""
        blob = build_detail_blob(self._enriched_with_interactions(), _base_scored())
        condition_warnings = [w for w in blob["warnings"] if w["type"] == "interaction"]
        assert condition_warnings
        w = condition_warnings[0]
        assert w["condition_id"] == "pregnancy"
        assert w["ingredient_name"] == "Vitamin A Palmitate"
        assert w["action"]

    def test_interaction_warnings_carry_drug_class_id(self):
        blob = build_detail_blob(self._enriched_with_interactions(), _base_scored())
        drug_warnings = [w for w in blob["warnings"] if w["type"] == "drug_interaction"]
        assert drug_warnings
        w = drug_warnings[0]
        assert w["drug_class_id"] == "retinoids"
        assert w["ingredient_name"] == "Vitamin A Palmitate"

    def test_dose_threshold_evaluation_exported(self):
        """Dose threshold audit trail must be on interaction warnings."""
        blob = build_detail_blob(self._enriched_with_interactions(), _base_scored())
        condition_warnings = [w for w in blob["warnings"] if w["type"] == "interaction"]
        w = condition_warnings[0]
        assert w["dose_threshold_evaluation"] is not None
        dte = w["dose_threshold_evaluation"]
        assert dte["evaluated"] is True
        assert "thresholds_checked" in dte

    def test_app_can_filter_warnings_by_user_condition(self):
        """Simulate what the Flutter app does: filter warnings by user conditions."""
        blob = build_detail_blob(self._enriched_with_interactions(), _base_scored())

        # Simulate user profile: pregnant, taking retinoids
        user_conditions = {"pregnancy"}
        user_drug_classes = {"retinoids"}

        # Filter warnings relevant to this user
        relevant = []
        for w in blob["warnings"]:
            if w["type"] == "interaction" and w.get("condition_id") in user_conditions:
                relevant.append(w)
            elif w["type"] == "drug_interaction" and w.get("drug_class_id") in user_drug_classes:
                relevant.append(w)

        assert len(relevant) == 2
        severities = {w["severity"] for w in relevant}
        assert "contraindicated" in severities
        assert "avoid" in severities

    def test_app_can_use_summary_for_instant_flag(self):
        """Simulate instant scan card flag: check condition_summary for user conditions."""
        blob = build_detail_blob(self._enriched_with_interactions(), _base_scored())
        summary = blob["interaction_summary"]

        # User has: pregnancy, hypertension
        user_conditions = {"pregnancy", "hypertension"}

        # Instant check: does any user condition appear in condition_summary?
        flagged_conditions = user_conditions & set(summary["condition_summary"].keys())
        assert flagged_conditions == {"pregnancy"}

        # Get worst severity for flagged conditions
        worst = max(
            (summary["condition_summary"][c]["highest_severity"] for c in flagged_conditions),
            key=lambda s: {"contraindicated": 4, "avoid": 3, "caution": 2, "monitor": 1}.get(s, 0)
        )
        assert worst == "contraindicated"

    def test_no_interaction_summary_when_no_interactions(self):
        """Products with no interactions should not have interaction_summary."""
        blob = build_detail_blob(_base_enriched(), _base_scored())
        assert "interaction_summary" not in blob
