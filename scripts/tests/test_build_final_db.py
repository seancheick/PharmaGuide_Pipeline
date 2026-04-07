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

sys.path.insert(0, str(Path(__file__).parent.parent))

from build_final_db import (
    build_final_db,
    build_core_row,
    build_detail_blob,
    build_top_warnings,
    fetch_staged_product,
    iter_json_products,
    mark_staged_product_matched,
    remote_blob_storage_path,
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
    "allergen_summary",
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
    assert set(decision_highlights.keys()) == {"positive", "caution", "trust"}
    assert isinstance(decision_highlights["positive"], str)
    assert isinstance(decision_highlights["caution"], str)
    assert isinstance(decision_highlights["trust"], str)


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
                "evidence": "labelText.parsed.allergens: soy",
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
        }
    ]

    blob = build_detail_blob(enriched, make_scored())
    warning_types = {warning["type"] for warning in blob["warnings"]}

    assert "banned_substance" in warning_types
    assert "allergen" in warning_types
    assert "interaction" in warning_types
    assert "drug_interaction" in warning_types
    assert "dietary" in warning_types
    assert "status" in warning_types


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
