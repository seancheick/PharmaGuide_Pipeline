#!/usr/bin/env python3
"""
Regression tests for the final DB export builder.

These tests freeze the app-facing export contract so the generated SQLite
database and detail blobs stay aligned with the real clean -> enrich -> score
pipeline outputs.
"""

import json
import sqlite3
import tempfile
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from build_final_db import (
    build_final_db,
    build_core_row,
    build_detail_blob,
    build_top_warnings,
    fetch_staged_product,
    generate_dosing_summary,
    iter_json_products,
    mark_staged_product_matched,
    remote_blob_storage_path,
    resolve_other_ingredient_reference,
    resolve_export_supplement_type,
    stage_products_by_id,
    validate_export_contract,
)


PRODUCTS_CORE_COLUMNS = [
    "dsld_id",
    "product_name",
    "brand_name",
    "upc_sku",
    "image_url",
    "image_is_pdf",
    "thumbnail_key",
    "detail_blob_sha256",
    "interaction_summary_hint",
    "decision_highlights",
    "product_status",
    "discontinued_date",
    "form_factor",
    "supplement_type",
    "score_quality_80",
    "score_display_80",
    "score_display_100_equivalent",
    "score_100_equivalent",
    "grade",
    "verdict",
    "safety_verdict",
    "mapped_coverage",
    "score_ingredient_quality",
    "score_ingredient_quality_max",
    "score_safety_purity",
    "score_safety_purity_max",
    "score_evidence_research",
    "score_evidence_research_max",
    "score_brand_trust",
    "score_brand_trust_max",
    "percentile_rank",
    "percentile_top_pct",
    "percentile_category",
    "percentile_label",
    "percentile_cohort",
    "is_gluten_free",
    "is_dairy_free",
    "is_soy_free",
    "is_vegan",
    "is_vegetarian",
    "is_organic",
    "is_non_gmo",
    "has_banned_substance",
    "has_recalled_ingredient",
    "has_harmful_additives",
    "has_allergen_risks",
    "blocking_reason",
    "is_probiotic",
    "contains_sugar",
    "contains_sodium",
    "diabetes_friendly",
    "hypertension_friendly",
    "is_trusted_manufacturer",
    "has_third_party_testing",
    "has_full_disclosure",
    "cert_programs",
    "badges",
    "top_warnings",
    "flags",
    # v1.3.0 additions (22 new columns)
    "ingredient_fingerprint",
    "key_nutrients_summary",
    "contains_stimulants",
    "contains_sedatives",
    "contains_blood_thinners",
    "share_title",
    "share_description",
    "share_highlights",
    "share_og_image_url",
    "primary_category",
    "secondary_categories",
    "contains_omega3",
    "contains_probiotics",
    "contains_collagen",
    "contains_adaptogens",
    "contains_nootropics",
    "key_ingredient_tags",
    "goal_matches",
    "goal_match_confidence",
    "dosing_summary",
    "servings_per_container",
    "net_contents_quantity",
    "net_contents_unit",
    "allergen_summary",
    # v1.3.2 additions (1 new column)
    "calories_per_serving",
    # v1.4.0 additions (1 new column)
    "image_thumbnail_url",
    # metadata
    "scoring_version",
    "output_schema_version",
    "enrichment_version",
    "scored_date",
    "export_version",
    "exported_at",
]


def row_as_dict(row):
    return dict(zip(PRODUCTS_CORE_COLUMNS, row))


def test_iter_json_products_yields_objects_from_mixed_json_files():
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp) / "data"
        data_dir.mkdir()

        (data_dir / "single.json").write_text(json.dumps({"dsld_id": "1", "name": "single"}), encoding="utf-8")
        (data_dir / "batch.json").write_text(
            json.dumps([{"dsld_id": "2", "name": "a"}, {"dsld_id": "3", "name": "b"}]),
            encoding="utf-8",
        )

        products = list(iter_json_products([str(data_dir)]))

    assert [product["dsld_id"] for product in products] == ["2", "3", "1"]


def test_stage_products_by_id_supports_lookup_and_unmatched_count():
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp) / "scored"
        data_dir.mkdir()
        (data_dir / "batch.json").write_text(
            json.dumps([
                {"dsld_id": "100", "verdict": "SAFE"},
                {"dsld_id": "200", "verdict": "CAUTION"},
            ]),
            encoding="utf-8",
        )

        conn = sqlite3.connect(":memory:")
        try:
            staged = stage_products_by_id(conn, "scored_stage", [str(data_dir)])
            assert staged == 2

            product = fetch_staged_product(conn, "scored_stage", "100")
            assert product["verdict"] == "SAFE"

            assert mark_staged_product_matched(conn, "scored_stage", "100") is True

            unmatched = conn.execute(
                "SELECT COUNT(*) FROM scored_stage WHERE matched = 0"
            ).fetchone()[0]
            assert unmatched == 1
        finally:
            conn.close()


def test_build_final_db_streaming_path_preserves_last_write_wins_duplicates():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        enriched_dir = root / "enriched"
        scored_dir = root / "scored"
        output_dir = root / "out"
        enriched_dir.mkdir()
        scored_dir.mkdir()

        first = make_enriched()
        first["product_name"] = "Older Name"
        latest = make_enriched()
        latest["product_name"] = "Newest Name"
        scored = make_scored()
        scored["dsld_id"] = "999"

        (enriched_dir / "batch.json").write_text(
            json.dumps([first, latest]),
            encoding="utf-8",
        )
        (scored_dir / "batch.json").write_text(
            json.dumps([scored]),
            encoding="utf-8",
        )

        result = build_final_db(
            [str(enriched_dir)],
            [str(scored_dir)],
            str(output_dir),
            str(Path(__file__).parent.parent),
        )

        assert result["product_count"] == 1
        assert result["error_count"] == 0
        assert (output_dir / "detail_index.json").exists()

        conn = sqlite3.connect(output_dir / "pharmaguide_core.db")
        try:
            row = conn.execute(
                "SELECT product_name FROM products_core WHERE dsld_id = ?",
                ("999",),
            ).fetchone()
        finally:
            conn.close()

        assert row == ("Newest Name",)

        detail_index = json.loads((output_dir / "detail_index.json").read_text(encoding="utf-8"))
        entry = detail_index["999"]
        assert entry["storage_path"] == remote_blob_storage_path(entry["blob_sha256"])
        assert entry["storage_path"].startswith("shared/details/sha256/")
        assert len(entry["blob_sha256"]) == 64

        manifest = json.loads((output_dir / "export_manifest.json").read_text(encoding="utf-8"))
        assert manifest["detail_blob_count"] == 1
        assert manifest["detail_blob_unique_count"] == 1
        assert manifest["detail_index_checksum"].startswith("sha256:")


def test_build_core_row_includes_flutter_convenience_fields():
    enriched = make_enriched()
    scored = make_scored()

    row = row_as_dict(build_core_row(enriched, scored, "2026-04-02T12:00:00Z"))

    assert row["image_is_pdf"] == 1
    assert row["detail_blob_sha256"] is None

    interaction_hint = json.loads(row["interaction_summary_hint"])
    assert interaction_hint["has_any"] is True
    assert interaction_hint["highest_severity"] == "avoid"
    assert interaction_hint["condition_ids"] == ["pregnancy"]
    assert interaction_hint["drug_class_ids"] == ["retinoids"]

    decision_highlights = json.loads(row["decision_highlights"])
    # Sprint E1.1.1: added 'danger' bucket (list[str]) for red-banner routing.
    assert set(decision_highlights.keys()) == {"positive", "caution", "danger", "trust"}
    assert isinstance(decision_highlights["positive"], str)
    assert isinstance(decision_highlights["caution"], str)
    assert isinstance(decision_highlights["danger"], list)
    assert isinstance(decision_highlights["trust"], str)


def test_export_prefers_resolved_supplement_type_over_stale_specialty():
    enriched = make_enriched()
    enriched["supplement_type"] = {"type": "specialty", "active_count": 0}
    enriched["product_name"] = "Restore"
    enriched["probiotic_data"] = {
        "is_probiotic_product": True,
        "has_cfu": True,
        "total_billion_count": 5.0,
        "total_strain_count": 3,
    }
    enriched["ingredient_quality_data"]["ingredients"] = [
        {
            "raw_source_text": "Lactobacillus gasseri",
            "name": "Lactobacillus gasseri",
            "parent_key": "lactobacillus_gasseri",
            "form": "",
            "category": "probiotics",
            "bio_score": 10,
            "natural": True,
            "score": 10.0,
            "mapped": True,
            "standard_name": "Lactobacillus Gasseri",
            "notes": "",
            "matched_form": "",
            "matched_forms": [],
            "extracted_forms": [],
            "safety_hits": [],
        }
    ]
    scored = make_scored()
    scored["supp_type"] = "probiotic"

    assert resolve_export_supplement_type(enriched, scored) == "probiotic"
    row = row_as_dict(build_core_row(enriched, scored, "2026-04-09T00:00:00Z"))
    assert row["supplement_type"] == "probiotic"
    assert row["primary_category"] == "probiotic"
    assert row["contains_probiotics"] == 1


def test_other_ingredient_reference_prefers_standard_name_over_generic_alias():
    ref = resolve_other_ingredient_reference("Hypromellose", "Hydroxypropyl Methylcellulose")

    assert ref["standard_name"] == "Hydroxypropyl Methylcellulose"
    # Phase 4c canonicalized capsule_shell → coating (functional_roles carries
    # the prebiotic_fiber/capsule-material nuance; category is the lean enum).
    assert ref["category"] == "coating"


def test_non_gmo_project_verified_flows_to_core_row_and_blob_audit():
    enriched = make_enriched()
    enriched["labelText"] = {
        "parsed": {
            "certifications": ["Non-GMO-Project"],
            "cleanLabelClaims": ["Non-GMO Project Verified"],
        }
    }
    scored = make_scored()
    scored["breakdown"]["A"]["A5d"] = 0.5

    row = row_as_dict(build_core_row(enriched, scored, "2026-04-10T12:00:00Z"))
    blob = build_detail_blob(enriched, scored)

    assert row["is_non_gmo"] == 1
    assert blob["non_gmo_audit"]["project_verified"] is True
    assert blob["non_gmo_audit"]["score_eligible"] is True
    assert blob["formulation_detail"]["claim_non_gmo_verified"] is True
    assert any(bonus["id"] == "A5d" for bonus in blob["score_bonuses"])


def test_generic_non_gmo_claim_does_not_silently_become_verified():
    enriched = make_enriched()
    enriched["labelText"] = {
        "parsed": {
            "certifications": ["Non-GMO-General"],
            "cleanLabelClaims": ["Non-GMO"],
        }
    }

    row = row_as_dict(build_core_row(enriched, make_scored(), "2026-04-10T12:00:00Z"))
    blob = build_detail_blob(enriched, make_scored())

    assert row["is_non_gmo"] == 0
    assert blob["non_gmo_audit"]["claim_present"] is True
    assert blob["non_gmo_audit"]["project_verified"] is False
    assert blob["non_gmo_audit"]["reason"] == "generic_claim_only"


def test_omega3_export_flags_follow_canonical_epa_dha_signals():
    enriched = make_enriched()
    enriched["ingredient_quality_data"]["ingredients"] = [
        {
            "raw_source_text": "Eicosapentaenoic Acid",
            "name": "Eicosapentaenoic Acid",
            "standard_name": "EPA (Eicosapentaenoic Acid)",
            "canonical_id": "epa",
            "category": "fatty_acids",
            "mapped": True,
        },
        {
            "raw_source_text": "Docosahexaenoic Acid",
            "name": "Docosahexaenoic Acid",
            "standard_name": "DHA (Docosahexaenoic Acid)",
            "canonical_id": "dha",
            "category": "fatty_acids",
            "mapped": True,
        },
    ]
    scored = make_scored()
    scored["breakdown"]["A"]["omega3_dose_bonus"] = 1.5
    scored["breakdown"]["A"]["omega3_breakdown"] = {
        "applicable": True,
        "omega3_dose_bonus": 1.5,
        "dose_band": "aha_cvd",
        "per_day_mid_mg": 1000.0,
    }

    row = row_as_dict(build_core_row(enriched, scored, "2026-04-10T12:00:00Z"))
    blob = build_detail_blob(enriched, scored)

    assert row["primary_category"] == "omega-3"
    assert row["contains_omega3"] == 1
    assert blob["omega3_audit"]["contains_omega3"] is True
    assert blob["omega3_audit"]["bonus_score"] == 1.5
    assert any(bonus["id"] == "omega3" for bonus in blob["score_bonuses"])


def make_enriched():
    return {
        "dsld_id": "999",
        "product_name": "Regression Product",
        "brandName": "Test Brand",
        "upcSku": "0123456789012",
        "imageUrl": "https://example.test/label.pdf",
        "status": "active",
        "discontinuedDate": None,
        "form_factor": "capsule",
        "supplement_type": {"type": "targeted"},
        "enrichment_version": "3.1.0",
        "is_certified_organic": False,
        "is_trusted_manufacturer": True,
        "manufacturing_region": "USA",
        "named_cert_programs": ["NSF Sport"],
        "has_full_disclosure": True,
        "compliance_data": {
            "gluten_free": True,
            "dairy_free": False,
            "soy_free": False,
            "vegan": False,
            "vegetarian": True,
        },
        "probiotic_data": {"is_probiotic_product": False},
        "contaminant_data": {
            "banned_substances": {
                "substances": []
            }
        },
        "harmful_additives": [
            {
                "ingredient": "Vitamin A Palmitate",
                "raw_source_text": "Vitamin A Palmitate",
                "additive_name": "Vitamin A Palmitate",
                "severity_level": "high",
                "category": "retinoid",
            }
        ],
        "allergen_hits": [
            {
                "allergen_id": "ALLERGEN_SOY",
                "allergen_name": "Soy Lecithin",
                "presence_type": "contains",
                "evidence": "Contains: Soy",
                "matched_text": "soy",
                "severity_level": "low",
            }
        ],
        "interaction_profile": {
            "ingredient_alerts": [
                {
                    "ingredient_name": "Vitamin A Palmitate",
                    "condition_hits": [
                        {
                            "condition_id": "pregnancy",
                            "severity": "high",
                            "mechanism": "Retinoid exposure risk.",
                        }
                    ],
                    "drug_class_hits": [
                        {
                            "drug_class_id": "retinoids",
                            "severity": "avoid",
                            "mechanism": "Overlapping retinoid exposure.",
                        }
                    ],
                }
            ]
        },
        "dietary_sensitivity_data": {
            "sugar": {
                "amount_g": 5.0,
                "level": "high",
                "level_display": "High Sugar",
            },
            "sodium": {
                "amount_mg": 240.0,
                "level": "moderate",
                "level_display": "Moderate Sodium",
            },
            "sweeteners": {"high_glycemic": ["glucose"]},
            "warnings": [
                {
                    "type": "diabetes",
                    "severity": "moderate",
                    "message": "Contains 5.0g sugar per serving.",
                },
                {
                    "type": "hypertension",
                    "severity": "moderate",
                    "message": "Contains 240mg sodium per serving.",
                },
            ],
            "contains_sugar": True,
            "contains_sodium": True,
            "diabetes_friendly": False,
            "hypertension_friendly": False,
        },
        "activeIngredients": [
            {
                "name": "Vitamin A Palmitate",
                "standardName": "Retinyl Palmitate",
                "normalized_key": "vitamin_a",
                "raw_source_text": "Vitamin A Palmitate",
                "forms": [{"name": "Palmitate"}],
                "quantity": 2000,
                "unit": "IU",
            },
            {
                "name": "Soy Lecithin",
                "standardName": "Soy Lecithin",
                "normalized_key": "soy_lecithin",
                "raw_source_text": "Soy Lecithin",
                "forms": [{"name": "Lecithin"}],
                "quantity": 50,
                "unit": "mg",
            },
        ],
        "ingredient_quality_data": {
            "ingredients": [
                {
                    "raw_source_text": "Vitamin A Palmitate",
                    "name": "Vitamin A Palmitate",
                    "standard_name": "Retinyl Palmitate",
                    "parent_key": "vitamin_a",
                    "form": "retinyl palmitate",
                    "category": "vitamins",
                    "bio_score": 14,
                    "natural": False,
                    "score": 14.0,
                    "mapped": True,
                    "notes": "Preformed vitamin A form.",
                    "matched_form": "retinyl palmitate",
                    "matched_forms": [{"form_key": "retinyl_palmitate", "bio_score": 14, "natural": False, "score": 14}],
                    "extracted_forms": [{"raw_form_text": "Palmitate", "percent_share": 1.0}],
                    "safety_hits": [],
                },
                {
                    "raw_source_text": "Soy Lecithin",
                    "name": "Soy Lecithin",
                    "standard_name": "Soy Lecithin",
                    "parent_key": "soy_lecithin",
                    "form": "lecithin",
                    "category": "other",
                    "bio_score": 4,
                    "natural": True,
                    "score": 6.0,
                    "mapped": True,
                    "notes": "Soy-derived emulsifier.",
                    "matched_form": "lecithin",
                    "matched_forms": [{"form_key": "lecithin", "bio_score": 4, "natural": True, "score": 6}],
                    "extracted_forms": [{"raw_form_text": "Lecithin", "percent_share": 1.0}],
                    "safety_hits": [],
                }
            ]
        },
        "dosage_normalization": {
            "normalized_ingredients": [
                {
                    "original_name": "Vitamin A Palmitate",
                    "normalized_amount": 600,
                    "normalized_unit": "mcg RAE",
                }
            ]
        },
        "inactiveIngredients": [
            {
                "name": "Soy Lecithin",
                "raw_source_text": "Soy Lecithin",
                "category": "emulsifier",
                "isAdditive": True,
                "additiveType": "lecithin",
            }
        ],
        "certification_data": {
            "third_party_programs": ["NSF Sport"],
            "gmp": {"status": "certified"},
            "purity_verified": True,
            "heavy_metal_tested": True,
            "label_accuracy_verified": True,
        },
        "proprietary_data": {
            "has_proprietary_blends": False,
            "blends": [],
        },
        "serving_basis": {
            "basis_count": 2,
            "basis_unit": "capsules",
            "min_servings_per_day": 1,
            "max_servings_per_day": 2,
        },
        "manufacturer_data": {
            "violations": {"fda_warning_letters": 0}
        },
        "evidence_data": {
            "match_count": 1,
            "clinical_matches": [
                {
                    "ingredient_name": "Vitamin A",
                    "evidence_level": "moderate",
                }
            ],
            "unsubstantiated_claims": [],
        },
        "rda_ul_data": {
            "collection_enabled": True,
            "ingredients_with_rda": 1,
            "analyzed_ingredients": 1,
            "count": 1,
            "adequacy_results": [
                {
                    "ingredient_name": "Vitamin A",
                    "daily_amount": 600,
                    "daily_amount_unit": "mcg RAE",
                    "adequacy_band": "adequate",
                }
            ],
            "conversion_evidence": [],
            "safety_flags": [],
            "has_over_ul": False,
        },
    }


def make_scored(verdict="SAFE"):
    return {
        "score_80": 60.0,
        "display": "60.0/80",
        "display_100": "75.0/100",
        "score_100_equivalent": 75.0,
        "grade": "Good",
        "verdict": verdict,
        "safety_verdict": verdict,
        "mapped_coverage": 1.0,
        "badges": [{"id": "FULL_DISCLOSURE", "label": "Full Disclosure"}],
        "flags": ["TEST_FLAG"],
        "section_scores": {
            "A_ingredient_quality": {"score": 20.0, "max": 25.0},
            "B_safety_purity": {"score": 18.0, "max": 30.0},
            "C_evidence_research": {"score": 15.0, "max": 20.0},
            "D_brand_trust": {"score": 4.0, "max": 5.0},
        },
        "category_percentile": {
            "available": True,
            "percentile_rank": 90.0,
            "top_percent": 10.0,
            "category_key": "targeted_capsule",
            "category_label": "Targeted Capsules",
            "cohort_size": 100,
        },
        "scoring_metadata": {
            "scoring_version": "3.1.0",
            "output_schema_version": "5.0.0",
            "scored_date": "2026-03-17T18:00:00Z",
        },
        "breakdown": {
            "A": {"score": 20.0, "max": 25.0, "A1": 5.0},
            "B": {"score": 18.0, "max": 30.0, "B0": 0.0},
            "C": {"score": 15.0, "max": 20.0, "matched_entries": 1},
            "D": {"score": 4.0, "max": 5.0, "D1": 1.0},
            "violation_penalty": 0.0,
        },
    }


def test_high_risk_exact_match_sets_caution_blocking_reason_without_banned_flag():
    enriched = make_enriched()
    enriched["contaminant_data"]["banned_substances"]["substances"] = [
        {
            "ingredient": "Vitamin A Palmitate",
            "banned_name": "Vitamin A Palmitate",
            "status": "high_risk",
            "match_type": "exact",
        }
    ]
    scored = make_scored(verdict="CAUTION")

    row = row_as_dict(build_core_row(enriched, scored, "2026-03-17T19:00:00Z"))

    assert row["has_banned_substance"] == 0
    assert row["has_recalled_ingredient"] == 0
    assert row["blocking_reason"] == "high_risk_ingredient"


def test_recalled_exact_match_sets_recalled_flag_but_not_banned_flag():
    enriched = make_enriched()
    enriched["contaminant_data"]["banned_substances"]["substances"] = [
        {
            "ingredient": "Vitamin A Palmitate",
            "banned_name": "Vitamin A Palmitate",
            "status": "recalled",
            "match_type": "alias",
        }
    ]
    scored = make_scored(verdict="UNSAFE")

    row = row_as_dict(build_core_row(enriched, scored, "2026-03-17T19:00:00Z"))

    assert row["has_banned_substance"] == 0
    assert row["has_recalled_ingredient"] == 1
    assert row["blocking_reason"] == "recalled_ingredient"


def test_detail_blob_includes_optional_rda_and_evidence_sections_when_present():
    blob = build_detail_blob(make_enriched(), make_scored())

    assert "rda_ul_data" in blob
    assert blob["rda_ul_data"]["collection_enabled"] is True
    assert "evidence_data" in blob
    assert blob["evidence_data"]["match_count"] == 1


def test_detail_blob_preserves_real_upstream_field_names_for_active_ingredients():
    blob = build_detail_blob(make_enriched(), make_scored())
    ingredient = blob["ingredients"][0]

    expected_keys = {
        "raw_source_text",
        "name",
        "standardName",
        "normalized_key",
        "forms",
        "quantity",
        "unit",
        "standard_name",
        "form",
        "matched_form",
        "matched_forms",
        "extracted_forms",
        "bio_score",
        "natural",
        "score",
        "notes",
        "category",
        "mapped",
        "safety_hits",
    }
    assert expected_keys.issubset(set(ingredient.keys()))
    assert ingredient["score"] == 14.0
    assert ingredient["standardName"] == "Retinyl Palmitate"


def test_detail_blob_marks_ingredient_flags_from_enriched_safety_data():
    enriched = make_enriched()
    enriched["contaminant_data"]["banned_substances"]["substances"] = [
        {
            "ingredient": "Vitamin A Palmitate",
            "banned_name": "Vitamin A Palmitate",
            "status": "banned",
            "match_type": "exact",
            # Sprint E1.1.3: realistic fixture matches Dr Pham's 143/143
            # authored-copy coverage; validator requires at least one copy field.
            "reason": "Test regulatory context.",
        
        "safety_warning": "Test Dr Pham long-form safety warning body copy for fixtures.",
        "safety_warning_one_liner": "Test Dr Pham one-liner safety copy.",
    }
    ]

    blob = build_detail_blob(enriched, make_scored())
    by_name = {ingredient["name"]: ingredient for ingredient in blob["ingredients"]}
    vitamin_a = by_name["Vitamin A Palmitate"]
    soy = by_name["Soy Lecithin"]

    assert vitamin_a["is_harmful"] is True
    assert vitamin_a["is_banned"] is True
    assert soy["is_allergen"] is True
    assert any(hit["status"] == "banned" for hit in vitamin_a["safety_hits"])
    assert any(hit["kind"] == "allergen" for hit in soy["safety_hits"])


def test_detail_blob_warnings_cover_banned_allergen_interaction_dietary_and_status():
    # Sprint E1.5.X-4 — status is no longer emitted as a warning; it's
    # surfaced via the dedicated `product_status_detail` top-level field
    # so Flutter can render it as a neutral concern chip rather than a
    # safety warning. This test verifies warnings[] still covers the
    # safety types AND product_status_detail is populated for discontinued.
    enriched = make_enriched()
    enriched["status"] = "discontinued"
    enriched["discontinuedDate"] = "2025-12-31"
    enriched["contaminant_data"]["banned_substances"]["substances"] = [
        {
            "ingredient": "Vitamin A Palmitate",
            "banned_name": "Vitamin A Palmitate",
            "status": "banned",
            "match_type": "exact",
            "reason": "Regulatory ban.",

        "safety_warning": "Test Dr Pham long-form safety warning body copy for fixtures.",
        "safety_warning_one_liner": "Test Dr Pham one-liner safety copy.",
    }
    ]

    blob = build_detail_blob(enriched, make_scored())
    warning_types = {warning["type"] for warning in blob["warnings"]}

    assert "banned_substance" in warning_types
    assert "allergen" in warning_types
    assert "interaction" in warning_types
    assert "drug_interaction" in warning_types
    assert "dietary" in warning_types
    # E1.5.X-4 contract: status is NOT in warnings[] anymore.
    assert "status" not in warning_types, (
        "product status must not appear in warnings[] — use top-level "
        "product_status dict instead"
    )
    # Discontinued products carry a populated top-level product_status.
    # Schema: {type, date, display} — `type` (not `status`) for future
    # extensibility to reformulated/limited_availability/seasonal/etc.
    ps = blob.get("product_status")
    assert ps is not None
    assert ps["type"] == "discontinued"
    assert ps["date"] == "2025-12-31"


def test_detail_blob_emits_structured_allergens_array():
    """Phase 8: detail_blob.allergens[] is the structured contract for
    Flutter's personalized allergen matcher (matchAllergens against
    profile.allergens). Distinct from the legacy warnings[] array which
    powers the generic display banner.
    """
    enriched = make_enriched()
    enriched["allergen_hits"] = [
        {
            "allergen_id": "ALLERGEN_SOY",
            "allergen_name": "Soy & Soy Lecithin",
            "presence_type": "contains",
            "severity_level": "low",
            "evidence": "Contains: Soy",
        },
        {
            "allergen_id": "ALLERGEN_TREE_NUTS",
            "allergen_name": "Tree Nuts",
            "presence_type": "may_contain",
            "severity_level": "high",
            "evidence": "May contain tree nuts",
        },
        {
            "allergen_id": "ALLERGEN_PEANUTS",
            "allergen_name": "Peanuts",
            "presence_type": "manufactured_in_facility",
            "severity_level": "high",
            "evidence": "Manufactured in a facility that also processes peanuts",
        },
    ]

    blob = build_detail_blob(enriched, make_scored())
    allergens = blob["allergens"]

    assert len(allergens) == 3
    # Sort: contains → may_contain → manufactured_in_facility
    assert allergens[0]["allergen_id"] == "ALLERGEN_SOY"
    assert allergens[0]["presence_type"] == "contains"
    assert allergens[1]["allergen_id"] == "ALLERGEN_TREE_NUTS"
    assert allergens[1]["presence_type"] == "may_contain"
    assert allergens[2]["allergen_id"] == "ALLERGEN_PEANUTS"
    assert allergens[2]["presence_type"] == "manufactured_in_facility"
    # Field passthrough — exact field names Flutter consumes.
    assert allergens[0]["display_name"] == "Soy & Soy Lecithin"
    assert allergens[0]["severity_level"] == "low"
    assert allergens[0]["evidence"] == "Contains: Soy"


def test_detail_blob_allergens_empty_when_no_hits():
    enriched = make_enriched()
    enriched["allergen_hits"] = []
    blob = build_detail_blob(enriched, make_scored())
    assert blob["allergens"] == []


def test_detail_blob_allergens_skips_entries_missing_allergen_id():
    """Defensive: hits without an `allergen_id` cannot be matched to a
    user profile (which stores canonical IDs), so they are skipped from
    the structured array. They still count for the legacy warnings[]
    summary because the display string only needs `allergen_name`."""
    enriched = make_enriched()
    enriched["allergen_hits"] = [
        {
            "allergen_name": "Unknown Allergen",
            "presence_type": "contains",
            "severity_level": "moderate",
            # no allergen_id — should be skipped
        },
        {
            "allergen_id": "ALLERGEN_MILK",
            "allergen_name": "Milk",
            "presence_type": "contains",
            "severity_level": "moderate",
        },
    ]
    blob = build_detail_blob(enriched, make_scored())
    assert len(blob["allergens"]) == 1
    assert blob["allergens"][0]["allergen_id"] == "ALLERGEN_MILK"


def test_detail_blob_emits_gluten_free_validated_flag():
    """Phase 8: positive gluten-free signal — orthogonal to the negative
    allergen flow. True when the label carries a validated gluten-free
    claim AND no contradicting wheat/gluten ingredient hits.
    """
    # Note: build_final_db's safe_bool returns int (1/0) for SQLite
    # interop, not Python True/False. Truthiness is what matters.
    enriched = make_enriched()
    enriched["claim_gluten_free_validated"] = True
    blob = build_detail_blob(enriched, make_scored())
    assert bool(blob["gluten_free_validated"]) is True

    enriched["claim_gluten_free_validated"] = False
    blob = build_detail_blob(enriched, make_scored())
    assert bool(blob["gluten_free_validated"]) is False

    # Missing (older blobs) → defaults to False
    enriched.pop("claim_gluten_free_validated", None)
    blob = build_detail_blob(enriched, make_scored())
    assert bool(blob["gluten_free_validated"]) is False


def test_watchlist_is_exported_as_warning_but_not_blocking_reason():
    enriched = make_enriched()
    enriched["contaminant_data"]["banned_substances"]["substances"] = [
        {
            "ingredient": "Vitamin A Palmitate",
            "banned_name": "Vitamin A Palmitate",
            "status": "watchlist",
            "match_type": "exact",
            "reason": "Policy watchlist item.",
            "severity_level": "moderate",
        }
    ]
    scored = make_scored(verdict="CAUTION")

    row = row_as_dict(build_core_row(enriched, scored, "2026-03-17T19:00:00Z"))
    blob = build_detail_blob(enriched, scored)
    warnings = build_top_warnings(enriched)

    assert row["blocking_reason"] is None
    assert any("Watchlist ingredient:" in warning for warning in warnings)
    assert any(w["type"] == "watchlist_substance" for w in blob["warnings"])


def test_top_warnings_priority_prefers_safety_before_dietary_and_status():
    enriched = make_enriched()
    enriched["status"] = "discontinued"
    enriched["discontinuedDate"] = "2025-12-31"
    enriched["contaminant_data"]["banned_substances"]["substances"] = [
        {
            "ingredient": "Vitamin A Palmitate",
            "banned_name": "Vitamin A Palmitate",
            "status": "banned",
            "match_type": "exact",
        
        "safety_warning": "Test Dr Pham long-form safety warning body copy for fixtures.",
        "safety_warning_one_liner": "Test Dr Pham one-liner safety copy.",
    },
        {
            "ingredient": "Soy Lecithin",
            "banned_name": "Soy Lecithin",
            "status": "recalled",
            "match_type": "alias",
        },
    ]

    warnings = build_top_warnings(enriched)

    assert len(warnings) == 5
    assert warnings[0].startswith("Banned substance:")
    assert warnings[1].startswith("Recalled ingredient:")
    assert any(w.startswith("Allergen:") for w in warnings)
    assert any("Interaction:" in w for w in warnings)
    assert all("Discontinued" not in warning for warning in warnings)


def test_export_contract_validator_fails_loudly_when_real_upstream_field_is_missing():
    enriched = make_enriched()
    del enriched["ingredient_quality_data"]["ingredients"][0]["score"]

    issues = validate_export_contract(enriched, make_scored())

    assert any("ingredient_quality_data.ingredients[0].score" in issue for issue in issues)


def test_banned_warning_includes_source_urls_from_references_structured():
    enriched = make_enriched()
    enriched["contaminant_data"]["banned_substances"]["substances"] = [
        {
            "ingredient": "Ephedra",
            "banned_name": "Ephedra",
            "status": "banned",
            "match_type": "exact",
            "reason": "FDA-banned stimulant.",
            "regulatory_date": "2004-04-12",
            "regulatory_date_label": "FDA ban effective",
            "clinical_risk_enum": "critical",
            "references_structured": [
                {
                    "type": "fda_advisory",
                    "title": "FDA Bans Ephedra",
                    "url": "https://www.fda.gov/ephedra-ban",
                    "evidence_grade": "R",
                },
                {
                    "type": "clinical_review",
                    "title": "Ephedra safety review",
                    "url": "https://pubmed.ncbi.nlm.nih.gov/99999999/",
                    "evidence_grade": "A",
                },
            ],
        
        "safety_warning": "Test Dr Pham long-form safety warning body copy for fixtures.",
        "safety_warning_one_liner": "Test Dr Pham one-liner safety copy.",
    }
    ]

    blob = build_detail_blob(enriched, make_scored())
    banned_warnings = [w for w in blob["warnings"] if w["type"] == "banned_substance"]
    assert len(banned_warnings) == 1

    warning = banned_warnings[0]
    assert "source_urls" in warning
    assert len(warning["source_urls"]) == 2
    assert warning["source_urls"][0]["url"] == "https://www.fda.gov/ephedra-ban"
    assert warning["source_urls"][0]["title"] == "FDA Bans Ephedra"
    assert warning["source_urls"][1]["evidence_grade"] == "A"
    assert warning["date"] == "2004-04-12"
    assert warning["regulatory_date_label"] == "FDA ban effective"


def test_export_contract_validator_allows_optional_form_tracking_fields_to_default():
    enriched = make_enriched()
    del enriched["ingredient_quality_data"]["ingredients"][0]["extracted_forms"]
    del enriched["ingredient_quality_data"]["ingredients"][0]["matched_forms"]

    issues = validate_export_contract(enriched, make_scored())

    assert not any("extracted_forms" in issue for issue in issues)
    assert not any("matched_forms" in issue for issue in issues)


def test_build_final_db_strict_mode_raises_on_enriched_scored_mismatch():
    """strict=True raises ValueError when enriched products have no matching scored output."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        enriched_dir = root / "enriched"
        scored_dir = root / "scored"
        output_dir = root / "out"
        enriched_dir.mkdir()
        scored_dir.mkdir()

        # Create 2 enriched products but only 1 scored
        enriched1 = make_enriched()  # dsld_id = "999"
        enriched2 = make_enriched()
        enriched2["dsld_id"] = "888"
        enriched2["product_name"] = "Unscored Product"

        scored1 = make_scored()
        scored1["dsld_id"] = "999"  # matches enriched1 only; enriched2 ("888") has no scored pair

        (enriched_dir / "batch.json").write_text(
            json.dumps([enriched1, enriched2]), encoding="utf-8"
        )
        (scored_dir / "batch.json").write_text(
            json.dumps([scored1]), encoding="utf-8"
        )

        # strict=True should raise
        with pytest.raises(ValueError, match="Strict mode"):
            build_final_db(
                [str(enriched_dir)], [str(scored_dir)], str(output_dir),
                str(Path(__file__).parent.parent),
                strict=True,
            )


def test_build_final_db_default_mode_allows_enriched_scored_mismatch():
    """Default (non-strict) mode exports matched products without raising."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        enriched_dir = root / "enriched"
        scored_dir = root / "scored"
        output_dir = root / "out"
        enriched_dir.mkdir()
        scored_dir.mkdir()

        enriched1 = make_enriched()
        enriched2 = make_enriched()
        enriched2["dsld_id"] = "888"
        enriched2["product_name"] = "Unscored Product"

        scored1 = make_scored()
        scored1["dsld_id"] = "999"  # matches enriched1 only; enriched2 ("888") has no scored pair

        (enriched_dir / "batch.json").write_text(
            json.dumps([enriched1, enriched2]), encoding="utf-8"
        )
        (scored_dir / "batch.json").write_text(
            json.dumps([scored1]), encoding="utf-8"
        )

        # Default mode should NOT raise
        result = build_final_db(
            [str(enriched_dir)], [str(scored_dir)], str(output_dir),
            str(Path(__file__).parent.parent),
        )
        assert result["product_count"] == 1  # only the matched one exported

        # Verify integrity block in manifest
        manifest = json.loads((output_dir / "export_manifest.json").read_text(encoding="utf-8"))
        integrity = manifest["integrity"]
        assert integrity["enriched_only_count"] == 1
        assert integrity["exported_count"] == 1
        assert integrity["strict_mode"] is False


# ────────────────────────────────────────────────────────────────────────────
# Dosing + net_contents export regression tests (bugfix: generate_dosing_summary
# used to read a nonexistent "serving_info" key, silently dropping real serving
# data and leaving servings_per_container NULL. These tests lock down the real
# cleaner-emitted fields.)
# ────────────────────────────────────────────────────────────────────────────


def test_generate_dosing_summary_reads_real_fields():
    enriched = {
        "servingsPerContainer": 90,
        "servingSizes": [
            {
                "minQuantity": 2,
                "maxQuantity": 2,
                "unit": "Capsule(s)",
                "minDailyServings": 1,
                "maxDailyServings": 1,
                "normalizedServing": 2,
                "servingQuantitySource": "label",
                "dailyServingsSource": "label",
            }
        ],
        "form_factor": "capsule",
    }

    dosing = generate_dosing_summary(enriched)

    assert dosing["servings_per_container"] == 90
    summary = dosing["dosing_summary"]
    assert summary
    assert summary != "See product label"
    # Should describe the real 2-capsule single-daily serving.
    assert "2" in summary
    assert "capsule" in summary.lower()


def test_generate_dosing_summary_range_quantity_reads_min_and_max():
    enriched = {
        "servingsPerContainer": 60,
        "servingSizes": [
            {
                "minQuantity": 1,
                "maxQuantity": 2,
                "unit": "Softgel(s)",
                "minDailyServings": 1,
                "maxDailyServings": 2,
            }
        ],
        "form_factor": "softgel",
    }

    dosing = generate_dosing_summary(enriched)

    assert dosing["servings_per_container"] == 60
    summary = dosing["dosing_summary"].lower()
    assert "softgel" in summary
    # Range 1-2 should appear verbatim.
    assert "1" in summary and "2" in summary


def test_generate_dosing_summary_twice_daily_from_max_daily_servings():
    enriched = {
        "servingsPerContainer": 180,
        "servingSizes": [
            {
                "minQuantity": 3,
                "maxQuantity": 3,
                "unit": "Capsule(s)",
                "minDailyServings": 2,
                "maxDailyServings": 2,
            }
        ],
        "form_factor": "capsule",
    }

    dosing = generate_dosing_summary(enriched)

    assert dosing["servings_per_container"] == 180
    summary = dosing["dosing_summary"].lower()
    assert "twice" in summary or "2 times" in summary or "2x" in summary


def test_generate_dosing_summary_gummy_form():
    enriched = {
        "servingsPerContainer": 60,
        "servingSizes": [
            {
                "minQuantity": 2,
                "maxQuantity": 2,
                "unit": "Gummie(s)",
                "minDailyServings": 1,
                "maxDailyServings": 1,
            }
        ],
        "form_factor": "gummy",
    }

    dosing = generate_dosing_summary(enriched)

    assert dosing["servings_per_container"] == 60
    summary = dosing["dosing_summary"].lower()
    assert "chew" in summary or "gummy" in summary or "gummies" in summary
    assert "2" in dosing["dosing_summary"]


def test_generate_dosing_summary_handles_missing_fields():
    # Empty servingSizes, no servingsPerContainer. Must not crash.
    enriched = {"servingSizes": [], "form_factor": "capsule"}

    dosing = generate_dosing_summary(enriched)

    # Graceful fallback: no real serving data means generic label pointer.
    assert dosing["dosing_summary"] == "See product label"
    # servings_per_container uses the existing None convention when absent.
    assert dosing["servings_per_container"] is None


def test_generate_dosing_summary_handles_completely_empty_enriched():
    # Totally empty dict — should not crash and returns fallback.
    dosing = generate_dosing_summary({})

    assert dosing["dosing_summary"] == "See product label"
    assert dosing["servings_per_container"] is None


def test_build_core_row_includes_net_contents_columns():
    enriched = make_enriched()
    enriched["netContents"] = [
        {"order": 1, "quantity": 90, "unit": "Capsule(s)", "display": "90 Capsule(s)"}
    ]
    scored = make_scored()

    row = row_as_dict(build_core_row(enriched, scored, "2026-04-10T12:00:00Z"))

    assert row["net_contents_quantity"] == 90.0
    assert row["net_contents_unit"] == "Capsule(s)"


def test_build_core_row_handles_missing_net_contents():
    enriched = make_enriched()
    # No netContents at all.
    enriched.pop("netContents", None)
    row = row_as_dict(build_core_row(enriched, make_scored(), "2026-04-10T12:00:00Z"))
    assert row["net_contents_quantity"] is None
    assert row["net_contents_unit"] is None

    # Empty list should also produce NULLs.
    enriched["netContents"] = []
    row = row_as_dict(build_core_row(enriched, make_scored(), "2026-04-10T12:00:00Z"))
    assert row["net_contents_quantity"] is None
    assert row["net_contents_unit"] is None


def test_build_core_row_net_contents_preserves_non_integer_quantities():
    enriched = make_enriched()
    enriched["netContents"] = [
        {"order": 1, "quantity": 10.2, "unit": "oz.", "display": "10.2 oz."},
        {"order": 2, "quantity": 288, "unit": "g", "display": "288 g"},
    ]

    row = row_as_dict(build_core_row(enriched, make_scored(), "2026-04-10T12:00:00Z"))

    # Index [0] is the primary entry.
    assert row["net_contents_quantity"] == 10.2
    assert row["net_contents_unit"] == "oz."


def test_final_db_has_91_columns():
    # Tuple emitted by build_core_row must match the 91-column schema (v1.4.0).
    enriched = make_enriched()
    enriched["servingsPerContainer"] = 60
    enriched["servingSizes"] = [
        {
            "minQuantity": 1,
            "maxQuantity": 1,
            "unit": "Capsule(s)",
            "minDailyServings": 1,
            "maxDailyServings": 1,
        }
    ]
    enriched["netContents"] = [
        {"order": 1, "quantity": 60, "unit": "Capsule(s)", "display": "60 Capsule(s)"}
    ]
    row = build_core_row(enriched, make_scored(), "2026-04-10T12:00:00Z")
    assert len(row) == 91
    assert len(PRODUCTS_CORE_COLUMNS) == 91


def test_dosing_summary_not_empty_for_real_product():
    """Smoke test mirroring Thorne Restore (dsld 15581): 1 capsule, 30/container."""
    enriched = make_enriched()
    enriched["dsld_id"] = "15581"
    enriched["product_name"] = "Restore"
    enriched["brandName"] = "Thorne"
    enriched["form_factor"] = "capsule"
    enriched["servingsPerContainer"] = 30
    enriched["servingSizes"] = [
        {
            "minQuantity": 1.0,
            "maxQuantity": 1.0,
            "unit": "Capsule(s)",
            "minDailyServings": 1,
            "maxDailyServings": 1,
            "normalizedServing": 1.0,
            "servingQuantitySource": "label",
            "dailyServingsSource": "label",
        }
    ]
    enriched["netContents"] = [
        {"order": 1, "quantity": 30, "unit": "Capsule(s)", "display": "30 Capsule(s)"}
    ]

    row = row_as_dict(build_core_row(enriched, make_scored(), "2026-04-10T12:00:00Z"))

    assert row["servings_per_container"] == 30
    assert row["dosing_summary"]
    assert row["dosing_summary"] != "See product label"
    assert "capsule" in row["dosing_summary"].lower()
    assert row["net_contents_quantity"] == 30.0
    assert row["net_contents_unit"] == "Capsule(s)"


# ─────────────────────────────────────────────────────────────────────────────
# TDD: Change A + Change B  (schema v1.3.2 — 90 columns)
# ─────────────────────────────────────────────────────────────────────────────

from build_final_db import CORE_COLUMN_COUNT, EXPORT_SCHEMA_VERSION  # noqa: E402


class TestDetailBlobNutritionAndUnmapped:
    """Verifies that detail_blob gains nutrition_detail and unmapped_actives subkeys."""

    def _enriched_with_nutrition(self, calories=120.0, carbs=10.0, fat=5.0, protein=8.0, fiber=2.0):
        e = make_enriched()
        e["nutrition_summary"] = {
            "calories_per_serving": calories,
            "total_carbohydrates_g": carbs,
            "total_fat_g": fat,
            "protein_g": protein,
            "dietary_fiber_g": fiber,
        }
        return e

    def _scored_with_unmapped(self, names=None):
        s = make_scored()
        names = names or []
        s["unmapped_actives"] = names
        s["unmapped_actives_total"] = len(names)
        s["unmapped_actives_excluding_banned_exact_alias"] = len(names)
        return s

    def test_detail_blob_contains_nutrition_detail_subkey(self):
        enriched = self._enriched_with_nutrition()
        blob = build_detail_blob(enriched, make_scored())
        assert "nutrition_detail" in blob
        nd = blob["nutrition_detail"]
        assert nd["calories_per_serving"] == 120.0
        assert nd["total_carbohydrates_g"] == 10.0
        assert nd["total_fat_g"] == 5.0
        assert nd["protein_g"] == 8.0
        assert nd["dietary_fiber_g"] == 2.0

    def test_detail_blob_nutrition_detail_empty_when_missing(self):
        enriched = make_enriched()
        # No nutrition_summary key at all
        enriched.pop("nutrition_summary", None)
        blob = build_detail_blob(enriched, make_scored())
        assert "nutrition_detail" in blob
        nd = blob["nutrition_detail"]
        assert nd["calories_per_serving"] is None
        assert nd["total_carbohydrates_g"] is None
        assert nd["total_fat_g"] is None
        assert nd["protein_g"] is None
        assert nd["dietary_fiber_g"] is None

    def test_detail_blob_contains_unmapped_actives_subkey_empty(self):
        blob = build_detail_blob(make_enriched(), make_scored())
        assert "unmapped_actives" in blob
        ua = blob["unmapped_actives"]
        assert ua["names"] == []
        assert ua["total"] == 0
        assert ua["excluding_banned_exact_alias"] == 0

    def test_detail_blob_contains_unmapped_actives_subkey_populated(self):
        scored = self._scored_with_unmapped(["Exotic Extract", "Typo Ingredient"])
        blob = build_detail_blob(make_enriched(), scored)
        ua = blob["unmapped_actives"]
        assert ua["names"] == ["Exotic Extract", "Typo Ingredient"]
        assert ua["total"] == 2
        assert ua["excluding_banned_exact_alias"] == 2

    def test_core_row_has_calories_per_serving_column(self):
        enriched = self._enriched_with_nutrition(calories=100.0)
        row = build_core_row(enriched, make_scored(), "2026-04-10T12:00:00Z")
        # calories_per_serving must be in the module-level column list and tuple
        assert "calories_per_serving" in PRODUCTS_CORE_COLUMNS
        idx = PRODUCTS_CORE_COLUMNS.index("calories_per_serving")
        assert row[idx] == 100.0

    def test_core_row_calories_null_when_missing(self):
        enriched = make_enriched()
        enriched.pop("nutrition_summary", None)
        row = build_core_row(enriched, make_scored(), "2026-04-10T12:00:00Z")
        assert "calories_per_serving" in PRODUCTS_CORE_COLUMNS
        idx = PRODUCTS_CORE_COLUMNS.index("calories_per_serving")
        assert row[idx] is None

    def test_core_row_column_count_is_91(self):
        row = build_core_row(make_enriched(), make_scored(), "2026-04-10T12:00:00Z")
        assert len(row) == 91
        assert CORE_COLUMN_COUNT == 91

    def test_schema_version_bumped_to_150(self):
        assert EXPORT_SCHEMA_VERSION == "1.5.0"

    def test_end_to_end_nutrition_and_unmapped_both_populate(self):
        """Smoke: realistic enriched with calories + unmapped actives → column and blob both correct."""
        enriched = self._enriched_with_nutrition(calories=120.0, protein=6.0)
        scored = self._scored_with_unmapped(["Mystery Herb"])

        row = build_core_row(enriched, scored, "2026-04-10T12:00:00Z")
        blob = build_detail_blob(enriched, scored)

        # Column check
        assert "calories_per_serving" in PRODUCTS_CORE_COLUMNS
        cal_idx = PRODUCTS_CORE_COLUMNS.index("calories_per_serving")
        assert row[cal_idx] == 120.0

        # Blob nutrition_detail check
        assert blob["nutrition_detail"]["calories_per_serving"] == 120.0
        assert blob["nutrition_detail"]["protein_g"] == 6.0

        # Blob unmapped_actives check
        assert blob["unmapped_actives"]["names"] == ["Mystery Herb"]
        assert blob["unmapped_actives"]["total"] == 1
