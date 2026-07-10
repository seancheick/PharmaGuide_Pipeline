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
    classify_product_categories,
    fetch_staged_product,
    generate_share_metadata,
    generate_ingredient_fingerprint,
    generate_key_nutrients_summary,
    generate_dosing_summary,
    has_banned_substance,
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
    "score_display_100_equivalent",
    "score_100_equivalent",
    "grade",
    "verdict",
    "safety_verdict",
    "mapped_coverage",
    # v2.0.0 v4 scoring contract.
    "quality_score_v4_100",
    "quality_score_status",
    "quality_tier",
    "quality_score_suppressed_reason",
    "raw_score_v4_100",
    "v4_module",
    "v4_confidence",
    "score_model_version",
    "quality_score_version",
    "scoring_engine_version",
    "classification_schema_version",
    "v4_config_fingerprint",
    "pillar_formulation_v4",
    "pillar_dose_v4",
    "pillar_evidence_v4",
    "pillar_transparency_v4",
    "pillar_verification_v4",
    "pillar_safety_hygiene_v4",
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
    "safety_signal_reason",
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
    # v1.6.x addition (1 new column, 2026-05-12 — aggregated ingredient names for FTS)
    "ingredients_text",
    "goal_matches",
    "goal_match_confidence",
    # v2.x addition (1 new column — goals present but below effective dose)
    "goal_matches_underdosed",
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


def test_build_final_db_streaming_path_preserves_last_write_wins_duplicates(monkeypatch):
    _patch_v4_by_id(monkeypatch, {"999": _canned_v4()})
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


def test_build_backfills_v4_category_percentiles(monkeypatch):
    """End-to-end: after the build, products_core carries a V4 percentile ranked
    over the shipped quality_score_v4_100 within each percentile_category cohort.
    Cohorts < 5 stay NULL. The backfill runs AFTER UPC dedup, so the five ranked
    products carry distinct UPCs to all survive into the cohort.
    """
    ranked = [("801", 95.0), ("802", 85.0), ("803", 75.0), ("804", 65.0), ("805", 55.0)]
    canned = {pid: _canned_v4(status="scored", quality_100=sc) for pid, sc in ranked}
    canned["806"] = _canned_v4(status="scored", quality_100=70.0)  # solo cohort -> unranked
    _patch_v4_by_id(monkeypatch, canned)

    def _enriched(pid, upc, category):
        e = make_enriched()
        e["dsld_id"] = pid
        e["upcSku"] = upc
        e["supplement_taxonomy"] = {
            "primary_type": "omega_3",
            "percentile_category": category,
            "classification_confidence": 0.95,
        }
        return e

    def _scored(pid):
        s = make_scored()
        s["dsld_id"] = pid
        return s

    enriched_list = [
        _enriched(pid, f"11111111{i:05d}", "fish_oil") for i, (pid, _) in enumerate(ranked)
    ]
    enriched_list.append(_enriched("806", "1111111199999", "solo_cat"))
    scored_list = [_scored(pid) for pid, _ in ranked] + [_scored("806")]

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        enriched_dir = root / "enriched"
        enriched_dir.mkdir()
        scored_dir = root / "scored"
        scored_dir.mkdir()
        output_dir = root / "out"
        (enriched_dir / "batch.json").write_text(json.dumps(enriched_list), encoding="utf-8")
        (scored_dir / "batch.json").write_text(json.dumps(scored_list), encoding="utf-8")

        result = build_final_db(
            [str(enriched_dir)],
            [str(scored_dir)],
            str(output_dir),
            str(Path(__file__).parent.parent),
        )
        assert result["product_count"] == 6, result

        conn = sqlite3.connect(output_dir / "pharmaguide_core.db")
        try:
            rows = {
                r[0]: r
                for r in conn.execute(
                    "SELECT dsld_id, percentile_rank, percentile_top_pct, "
                    "percentile_cohort FROM products_core"
                ).fetchall()
            }
        finally:
            conn.close()

    # Five fish_oil products form a cohort of 5, ranked by v4 score.
    assert rows["801"][3] == 5 and rows["805"][3] == 5
    # Top scorer (95): higher=0, equal=1 -> rank=1.0 -> top%=20.0 -> prank=80.0
    assert rows["801"][1] == 80.0 and rows["801"][2] == 20.0
    # Bottom scorer (55): higher=4, equal=1 -> rank=5.0 -> top%=100.0 -> prank=0.0
    assert rows["805"][1] == 0.0 and rows["805"][2] == 100.0
    # Solo-category product: cohort of 1 (<5) -> unranked, all three columns NULL.
    assert rows["806"][1] is None and rows["806"][2] is None and rows["806"][3] is None


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


def test_share_metadata_evidence_copy_uses_grammatical_v4_signal():
    enriched = {
        "product_name": "Clinical Probe",
        "brand_name": "Test Brand",
        "compliance_data": {},
    }
    base_scored = {
        "grade": "Strong",
        "score_100_equivalent": 82,
        "verdict": "SAFE",
    }

    mid = generate_share_metadata(
        enriched,
        {**base_scored, "_v4_pillars": {"evidence": {"score": 12.0, "max": 20}}},
    )
    assert "Clinically-backed ingredients" in mid["share_highlights"]
    assert "clinical evidence" not in mid["share_description"]
    assert "clinically-backed" not in mid["share_description"]

    high = generate_share_metadata(
        enriched,
        {**base_scored, "_v4_pillars": {"evidence": {"score": 15.0, "max": 20}}},
    )
    assert "with clinical evidence" in high["share_description"]
    assert "with clinically-backed" not in high["share_description"]


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
    # v4 cutover: the A5d Non-GMO bonus is sourced from the v4 formulation
    # component, not the v3 A5d section sub-score.
    scored["_v4_module_breakdown"] = {
        "dimensions": {"formulation": {"components": {"A5d_non_gmo": 0.5}}}
    }

    row = row_as_dict(build_core_row(enriched, scored, "2026-04-10T12:00:00Z"))
    blob = build_detail_blob(enriched, scored)

    assert row["is_non_gmo"] == 1
    assert blob["non_gmo_audit"]["project_verified"] is True
    assert blob["non_gmo_audit"]["score_eligible"] is True
    assert blob["formulation_detail"]["claim_non_gmo_verified"] is True
    assert any(bonus["id"] == "A5d" for bonus in blob["score_bonuses"])


def test_non_gmo_project_rules_db_evidence_flows_to_core_row_and_blob_audit():
    enriched = make_enriched()
    enriched["compliance_data"] = {
        "evidence_based": {
            "allergen_free_claims": [
                {
                    "rule_id": "CLAIM_NON_GMO_PROJECT",
                    "dedupe_key": "dietary:non_gmo_project",
                    "display_name": "Non-GMO Project Verified",
                    "score_eligible": True,
                    "matched_text": "Non-GMO Project Verified",
                }
            ]
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
    enriched["supplement_taxonomy"] = {
        "primary_type": "omega_3",
        "secondary_type": "fish_oil_epa_dha",
        "percentile_category": "fish_oil",
        "classification_confidence": 0.95,
        "classification_reasons": ["omega-3: ids=['epa', 'dha']"],
        "quantified_active_count": 2,
        "non_quantified_base_count": 0,
        "category_breakdown": {"fatty_acid": 2},
    }
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

    assert row["primary_category"] == "omega_3"
    assert row["contains_omega3"] == 1
    assert blob["omega3_audit"]["contains_omega3"] is True
    assert blob["omega3_audit"]["bonus_score"] == 1.5
    # v4 cutover: the standalone "omega3" tradeoff chip is retired (no discrete
    # v4 component). Omega-3 dose quality is preserved in omega3_audit /
    # omega3_detail and reflected in the dose pillar score.


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
            "reference_data_version": "5.0.0-2026-06-28",
            "reference_data_fingerprint": "sha256:test-reference",
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
        "strict_scoring_contract": {
            "passed": True,
            "findings": [],
            "zero_scorable_reason": None,
            "mapped_coverage_applicable": True,
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


def test_dietary_sugar_penalty_exports_to_tradeoffs():
    enriched = make_enriched()
    enriched["dietary_sensitivity_data"]["sugar"] = {
        "amount_g": 0.0,
        "level": "low",
        "level_display": "Low Sugar",
        "contains_sugar": True,
        "has_added_sugar": True,
        "sugar_sources": ["Glucose Syrup"],
    }
    enriched["dietary_sensitivity_data"]["sweeteners"] = {
        "high_glycemic": ["Glucose Syrup"],
        "sugar_alcohols": [],
    }

    blob = build_detail_blob(enriched, make_scored())

    sugar_penalty = next(
        item for item in blob["score_penalties"] if item["id"] == "B1_dietary_sugar"
    )
    assert sugar_penalty["score"] == -2.0
    assert sugar_penalty["severity"] == "moderate"
    assert sugar_penalty["reason"] == "high_glycemic_or_syrup"


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


def test_banned_inactive_forces_blocked_core_verdict_when_scorer_says_safe():
    enriched = make_enriched()
    enriched["inactiveIngredients"] = [
        {
            "name": "Brominated Vegetable Oil",
            "raw_source_text": "Brominated Vegetable Oil",
            "standardName": "Brominated Vegetable Oil",
        }
    ]
    scored = make_scored(verdict="SAFE")

    blob = build_detail_blob(enriched, scored)
    row = row_as_dict(
        build_core_row(
            enriched,
            scored,
            "2026-03-17T19:00:00Z",
            detail_blob=blob,
        )
    )

    assert row["has_banned_substance"] == 1
    assert row["verdict"] == "BLOCKED"
    assert row["safety_verdict"] == "BLOCKED"
    assert row["blocking_reason"] == "banned_ingredient"
    assert row["score_100_equivalent"] is None
    assert row["score_display_100_equivalent"] == "N/A"
    assert row["score_safety_purity"] == 0.0
    assert any(
        w.get("type") == "banned_substance" and w.get("severity") == "critical"
        for w in blob["warnings_profile_gated"]
    )


def test_critical_banned_blob_warning_cannot_coexist_with_safe_core_verdict():
    enriched = make_enriched()
    scored = make_scored(verdict="SAFE")
    blob = {
        "warnings_profile_gated": [
            {"type": "banned_substance", "severity": "critical"}
        ]
    }

    row = row_as_dict(
        build_core_row(
            enriched,
            scored,
            "2026-03-17T19:00:00Z",
            detail_blob=blob,
        )
    )

    assert row["verdict"] == "BLOCKED"
    assert row["safety_verdict"] == "BLOCKED"
    assert row["blocking_reason"] == "banned_ingredient"


def test_excipient_acceptable_inactive_uses_calibrated_warning_posture():
    enriched = make_enriched()
    enriched["inactiveIngredients"] = [
        {
            "name": "Titanium Dioxide",
            "raw_source_text": "Titanium Dioxide",
            "standardName": "Titanium Dioxide",
        }
    ]
    scored = make_scored(verdict="SAFE")

    blob = build_detail_blob(enriched, scored)
    row = row_as_dict(
        build_core_row(
            enriched,
            scored,
            "2026-03-17T19:00:00Z",
            detail_blob=blob,
        )
    )
    warning = next(
        w for w in blob["warnings_profile_gated"]
        if w.get("matched_rule_id") == "BANNED_ADD_TITANIUM_DIOXIDE"
    )

    # Verdict posture updated 2026-06-09 (commit e22c7286, supersedes the
    # 2026-05-29 watchlist-widening posture): a watchlist substance whose
    # entry says inactive_policy=excipient_acceptable (Titanium Dioxide E171
    # as a capsule excipient, simethicone as antifoam) is warning-only — it
    # does NOT downgrade the base verdict. The user-visible warning persists
    # (never silent), but ubiquitous low-risk excipient use is not a CAUTION.
    # Active-role watchlist matches still disqualify SAFE — locked by
    # test_v4_safety_parity_release::test_active_watchlist_warning_still_
    # disqualifies_safe.
    assert row["verdict"] == "SAFE"
    assert row["safety_verdict"] == "SAFE"
    assert row["blocking_reason"] is None
    # Warning copy stays calibrated/informational — only the verdict moved.
    assert warning["type"] == "watchlist_substance"
    assert warning["severity"] == "moderate"
    assert warning["display_mode_default"] == "informational"
    assert warning["inactive_policy"] == "excipient_acceptable"


def test_safety_source_inactive_does_not_export_safety_standard_name_as_identity():
    enriched = make_enriched()
    enriched["inactiveIngredients"] = [
        {
            "name": "Titanium Dioxide",
            "raw_source_text": "Titanium Dioxide",
            "standardName": "Titanium Dioxide (E171)",
            "standard_name": "Titanium Dioxide (E171)",
        }
    ]

    blob = build_detail_blob(enriched, make_scored())
    inactive = blob["inactive_ingredients"][0]

    assert inactive["standardName"] == "Titanium Dioxide"
    assert inactive["standard_name"] == "Titanium Dioxide"
    assert inactive["display_label"] == "Titanium Dioxide"
    assert inactive["matched_rule_id"] == "BANNED_ADD_TITANIUM_DIOXIDE"
    assert any(
        flag.get("entry_id") == "BANNED_ADD_TITANIUM_DIOXIDE"
        for flag in inactive.get("safety_flags", [])
    )


def test_inactive_display_label_preserves_label_wording_with_resolved_identity_metadata():
    enriched = make_enriched()
    enriched["inactiveIngredients"] = [
        {
            "name": "Ascorbyl Palmitate",
            "raw_source_text": "Ascorbyl Palmitate",
            "standardName": "Natural Preservatives",
        }
    ]

    blob = build_detail_blob(enriched, make_scored())
    inactive = blob["inactive_ingredients"][0]

    assert inactive["name"] == "Ascorbyl Palmitate"
    assert inactive["display_label"] == "Ascorbyl Palmitate"
    assert inactive["label_display"] == "Ascorbyl Palmitate"
    assert inactive["resolved_display_label"] == "Natural Preservatives"
    assert inactive["standardName"] == "Natural Preservatives"
    assert inactive["display_role_label"] == "Preservative natural"
    assert inactive["label_row_disposition"] == "standard"


def test_label_descriptor_inactive_row_stays_visible_but_marked_nonstandard():
    enriched = make_enriched()
    enriched["inactiveIngredients"] = [
        {
            "name": "Phospholipids",
            "raw_source_text": "Phospholipids",
            "standardName": "Phospholipid Descriptor",
            "forms": [
                {
                    "name": "purified Sunflower seed Lecithin",
                    "prefix": "from",
                }
            ],
        }
    ]
    enriched["raw_inactives_count"] = 1

    blob = build_detail_blob(enriched, make_scored())
    inactive = blob["inactive_ingredients"][0]

    assert inactive["name"] == "Phospholipids"
    assert inactive["display_label"] == "Phospholipids"
    assert inactive["label_display"] == "Phospholipids"
    assert inactive["standardName"] == "Phospholipid Descriptor"
    assert inactive["resolved_display_label"] == "Phospholipid Descriptor"
    assert inactive["matched_rule_id"] == "PII_PHOSPHOLIPID_DESCRIPTOR"
    assert inactive["label_row_disposition"] == "label_descriptor"
    assert inactive["is_label_descriptor"] is True
    assert inactive["functional_roles"] == []


def test_safety_source_active_without_canonical_keeps_label_identity():
    enriched = make_enriched()
    enriched["activeIngredients"] = [
        {
            "name": "Bitter Orange Citrus Bioflavonoids",
            "raw_source_text": "Bitter Orange Citrus Bioflavonoids",
            "standardName": "Bitter Orange",
            "standard_name": "Bitter Orange",
            "canonical_id": None,
            "mapped": False,
            "safety_flags": [
                {
                    "entry_id": "RISK_BITTER_ORANGE",
                    "source_db": "banned_recalled_ingredients",
                    "status": "high_risk",
                    "severity": "high",
                    "match_type": "alias",
                    "matched_variant": "Bitter Orange",
                    "evidence_text": "Bitter Orange Citrus Bioflavonoids",
                    "confidence": "high",
                }
            ],
        }
    ]
    enriched["ingredient_quality_data"]["ingredients"] = []

    ingredient = build_detail_blob(enriched, make_scored())["ingredients"][0]

    assert ingredient["standardName"] == "Bitter Orange Citrus Bioflavonoids"
    assert ingredient["standard_name"] == "Bitter Orange Citrus Bioflavonoids"
    assert ingredient["matched_rule_id"] == "RISK_BITTER_ORANGE"
    assert ingredient["safety_flags"][0]["entry_id"] == "RISK_BITTER_ORANGE"


def test_inactive_form_terms_emit_banned_preflight_detail():
    enriched = make_enriched()
    enriched["activeIngredients"] = []
    enriched["ingredient_quality_data"]["ingredients"] = []
    enriched["inactiveIngredients"] = [
        {
            "name": "Creamer",
            "raw_source_text": "Creamer",
            "standardName": "Creamer",
            "forms": [
                {"name": "Corn Syrup Solids"},
                {"name": "Partially Hydrogenated Soybean Oil"},
            ],
        }
    ]

    blob = build_detail_blob(enriched, make_scored())
    inactive = blob["inactive_ingredients"][0]

    assert inactive["standardName"] == "Creamer"
    assert inactive["standard_name"] == "Creamer"
    assert inactive["matched_rule_id"] == "BANNED_PHO"
    assert inactive["is_banned"] is True
    assert blob["banned_substance_detail"]["substance_name"] == "Partially Hydrogenated Oils (PHOs)"
    assert blob["banned_substance_detail"]["safety_warning_one_liner"]
    assert blob["banned_substance_detail"]["safety_warning"]


def test_active_safety_flag_uses_reference_copy_for_banned_detail():
    enriched = make_enriched()
    enriched["activeIngredients"] = [
        {
            "name": "Red Yeast Rice powder",
            "raw_source_text": "Red Yeast Rice powder",
            "standardName": "Red Yeast Rice powder",
            "mapped": False,
            "safety_flags": [
                {
                    "entry_id": "BANNED_RED_YEAST_RICE",
                    "source_db": "banned_recalled_ingredients",
                    "status": "banned",
                    "severity": "critical",
                    "match_type": "token_bounded",
                    "matched_variant": "red yeast rice",
                    "evidence_text": "Red Yeast Rice powder",
                    "confidence": "medium",
                }
            ],
        }
    ]
    enriched["ingredient_quality_data"]["ingredients"] = []
    enriched["contaminant_data"]["banned_substances"] = {
        "found": True,
        "substances": [],
        "safety_flags": enriched["activeIngredients"][0]["safety_flags"],
    }

    blob = build_detail_blob(enriched, make_scored())
    ingredient = blob["ingredients"][0]

    assert ingredient["matched_rule_id"] == "BANNED_RED_YEAST_RICE"
    assert blob["banned_substance_detail"]["safety_warning_one_liner"]
    assert blob["banned_substance_detail"]["safety_warning"]


def test_iso_phos_acronym_flag_is_not_banned_evidence():
    enriched = make_enriched()
    stale_flag = {
        "entry_id": "BANNED_PHO",
        "source_db": "banned_recalled_ingredients",
        "status": "banned",
        "severity": "critical",
        "match_type": "token_bounded",
        "matched_variant": "PHOs",
        "evidence_text": "Iso-Phos",
        "confidence": "medium",
    }
    enriched["activeIngredients"] = [
        {
            "name": "Iso-Phos",
            "raw_source_text": "Iso-Phos",
            "standardName": "Phosphatidylserine",
            "canonical_id": "phosphatidylserine",
            "mapped": True,
            "forms": [{"name": "Phosphatidylserine Isolate"}],
            "safety_flags": [stale_flag],
        }
    ]
    enriched["ingredient_quality_data"]["ingredients"] = [
        {
            "raw_source_text": "Iso-Phos",
            "name": "Iso-Phos",
            "standard_name": "Phosphatidylserine",
            "canonical_id": "phosphatidylserine",
            "mapped": True,
            "score": 10,
        }
    ]
    enriched["contaminant_data"]["banned_substances"] = {
        "found": True,
        "substances": [],
        "safety_flags": [stale_flag],
    }

    assert has_banned_substance(enriched) is False

    ingredient = build_detail_blob(enriched, make_scored())["ingredients"][0]

    assert ingredient["matched_rule_id"] is None
    assert ingredient["is_banned"] is False
    assert ingredient["safety_flags"] == []


def test_core_row_honors_scorer_emitted_high_risk_blocking_reason():
    enriched = make_enriched()
    enriched["inactiveIngredients"] = [
        {
            "name": "DHEA",
            "raw_source_text": "DHEA",
            "standardName": "DHEA",
        }
    ]
    scored = make_scored(verdict="CAUTION")
    scored["blocking_reason"] = "high_risk_ingredient"

    blob = build_detail_blob(enriched, scored)
    row = row_as_dict(
        build_core_row(
            enriched,
            scored,
            "2026-03-17T19:00:00Z",
            detail_blob=blob,
        )
    )

    assert row["verdict"] == "CAUTION"
    assert row["safety_verdict"] == "CAUTION"
    assert row["blocking_reason"] == "high_risk_ingredient"
    assert any(
        w.get("type") == "high_risk_ingredient"
        and w.get("severity") == "high"
        and w.get("display_mode_default") == "critical"
        and w.get("inactive_policy") == "penalize_anyway"
        for w in blob["warnings_profile_gated"]
    )


def test_core_row_exports_scored_caution_safety_signal_reason_separately():
    enriched = make_enriched()
    scored = make_scored(verdict="CAUTION")
    scored["safety_signal_reason"] = "B0_HIGH_RISK_SUBSTANCE"

    row = row_as_dict(build_core_row(enriched, scored, "2026-03-17T19:00:00Z"))

    assert row["verdict"] == "CAUTION"
    assert row["blocking_reason"] is None
    assert row["safety_signal_reason"] == "B0_HIGH_RISK_SUBSTANCE"


def test_detail_blob_includes_optional_rda_and_evidence_sections_when_present():
    blob = build_detail_blob(make_enriched(), make_scored())

    assert "rda_ul_data" in blob
    assert blob["rda_ul_data"]["collection_enabled"] is True
    assert blob["rda_ul_data"]["reference_data_version"] == "5.0.0-2026-06-28"
    assert blob["rda_ul_data"]["reference_data_fingerprint"] == "sha256:test-reference"
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
        # v1.5.x: legacy `form` field deleted (deprecation cleanup);
        # consumers read `display_form_label` from the canonical contract.
        "display_form_label",
        "form_status",
        "form_match_status",
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


def test_detail_blob_does_not_mark_active_mapped_without_canonical_id():
    enriched = make_enriched()
    enriched["activeIngredients"] = [
        {
            "name": "from Green Tea Leaf Extract",
            "standardName": "from Green Tea Leaf Extract",
            "raw_source_text": "from Green Tea Leaf Extract",
            "quantity": 56,
            "unit": "mg",
            "mapped": False,
        }
    ]
    enriched["ingredient_quality_data"]["ingredients"] = [
        {
            "name": "from Green Tea Leaf Extract",
            "raw_source_text": "from Green Tea Leaf Extract",
            "standard_name": "from Green Tea Leaf Extract",
            "mapped": True,
            "canonical_id": None,
            "recognized_non_scorable": True,
            "role_classification": "recognized_non_scorable",
            "recognition_reason": "source_descriptor_child_row",
            "score": 9,
            "category": "herbs",
        }
    ]

    ingredient = build_detail_blob(enriched, make_scored())["ingredients"][0]

    assert ingredient["canonical_id"] == ""
    assert ingredient["mapped"] is False
    assert ingredient["is_mapped"] is False


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

    # v1.5.x: is_harmful retired in favor of is_safety_concern (semantic)
    # + harmful_severity (raw enum). Vitamin A Palmitate is high severity
    # in the test fixture so is_safety_concern fires.
    assert vitamin_a["is_safety_concern"] is True
    assert vitamin_a["harmful_severity"] == "high"
    assert vitamin_a["is_banned"] is True
    assert soy["is_allergen"] is True
    assert any(hit["status"] == "banned" for hit in vitamin_a["safety_hits"])
    assert any(hit["kind"] == "allergen" for hit in soy["safety_hits"])


def test_detail_blob_warnings_cover_banned_interaction_dietary_and_status_not_allergens():
    # Sprint E1.5.X-4 — status is no longer emitted as a warning; it's
    # surfaced via the dedicated `product_status_detail` top-level field
    # so Flutter can render it as a neutral concern chip rather than a
    # safety warning. This test verifies warnings[] still covers the
    # safety types, does not duplicate structured allergens, AND
    # product_status_detail is populated for discontinued.
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
    assert "allergen" not in warning_types
    assert "interaction" in warning_types
    assert "drug_interaction" in warning_types
    assert "dietary" in warning_types
    assert blob["allergens"], "allergen facts belong in structured allergens[]"
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
    profile.allergens). Distinct from warnings[], which is reserved for
    non-allergen safety warnings and profile-gated interaction warnings.
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


def test_key_ingredient_tags_emit_all_mapped_canonical_ids_for_interactions():
    enriched = make_enriched()
    enriched["activeIngredients"] = []
    enriched["ingredient_quality_data"]["ingredients"] = [
        {
            "name": "Potassium",
            "standard_name": "Potassium",
            "canonical_id": "potassium",
            "parent_key": "potassium",
            "category": "mineral",
            "mapped": True,
            "dosage": 99,
            "dosage_unit": "mg",
        },
        {
            "name": "Potassium Gluconate",
            "standard_name": "Potassium",
            "canonical_id": "potassium",
            "parent_key": "potassium_gluconate",
            "category": "mineral",
            "mapped": True,
            "dosage": 595,
            "dosage_unit": "mg",
        },
        {
            "name": "Magnesium",
            "standard_name": "Magnesium",
            "canonical_id": "magnesium",
            "parent_key": "magnesium",
            "category": "mineral",
            "mapped": True,
            "dosage": 100,
            "dosage_unit": "mg",
        },
    ]

    categories = classify_product_categories(enriched, make_scored())

    assert categories["key_ingredient_tags"] == ["potassium", "magnesium"]


def test_export_uses_strict_scoring_rows_not_flattened_blend_children():
    enriched = make_enriched()
    enriched["product_name"] = "Vitamin D3 + K2"
    enriched["supplement_taxonomy"] = {
        "primary_type": "multi_or_complex",
        "secondary_type": "",
    }
    enriched["probiotic_data"] = {"is_probiotic_product": True}
    enriched["activeIngredients"] = [
        {
            "name": "Vitamin D3",
            "standardName": "Vitamin D3",
            "normalized_key": "vitamin_d",
            "canonical_id": "vitamin_d",
            "raw_source_text": "Vitamin D3",
            "raw_source_path": "activeIngredients[0]",
            "quantity": 125,
            "unit": "mcg",
        },
        {
            "name": "Vitamin K2",
            "standardName": "Vitamin K2",
            "normalized_key": "vitamin_k",
            "canonical_id": "vitamin_k",
            "raw_source_text": "Vitamin K2",
            "raw_source_path": "activeIngredients[1]",
            "quantity": 50,
            "unit": "mcg",
        },
        {
            "name": "QPower",
            "standardName": "Quercetin",
            "normalized_key": "quercetin",
            "canonical_id": "quercetin",
            "raw_source_text": "QPower",
            "raw_source_path": "activeIngredients[2].child_ingredients[0]",
            "quantity": 0,
            "unit": "NP",
        },
        {
            "name": "Rhodiola",
            "standardName": "Rhodiola",
            "normalized_key": "rhodiola",
            "canonical_id": "rhodiola",
            "raw_source_text": "Rhodiola",
            "raw_source_path": "activeIngredients[2].child_ingredients[1]",
            "quantity": 0,
            "unit": "NP",
        },
    ]

    def scoring_row(index, name, canonical_id, quantity, unit):
        return {
            "raw_source_text": name,
            "name": name,
            "standard_name": name,
            "canonical_id": canonical_id,
            "parent_key": canonical_id,
            "source_section": "active",
            "raw_source_path": f"activeIngredients[{index}]",
            "cleaner_row_role": "active_scorable",
            "score_eligible_by_cleaner": True,
            "dose_class": "measured_mass",
            "role_classification": "active_scorable",
            "scoreable_identity": True,
            "mapped_identity": True,
            "mapped": True,
            "quantity": quantity,
            "unit": unit,
            "category": "vitamins",
            "bio_score": 14,
            "natural": False,
            "score": 14.0,
            "notes": "",
            "safety_hits": [],
        }

    enriched["ingredient_quality_data"] = {
        "ingredients_scorable": [
            scoring_row(0, "Vitamin D3", "vitamin_d", 125, "mcg"),
            scoring_row(1, "Vitamin K2", "vitamin_k", 50, "mcg"),
        ],
        "ingredients_recognized_non_scorable": [
            {
                "raw_source_text": "QPower",
                "name": "QPower",
                "standard_name": "Quercetin",
                "canonical_id": "quercetin",
                "raw_source_path": "activeIngredients[2].child_ingredients[0]",
                "cleaner_row_role": "nested_display_only",
                "score_eligible_by_cleaner": False,
                "role_classification": "recognized_non_scorable",
                "scoreable_identity": False,
            },
            {
                "raw_source_text": "Rhodiola",
                "name": "Rhodiola",
                "standard_name": "Rhodiola",
                "canonical_id": "rhodiola",
                "raw_source_path": "activeIngredients[2].child_ingredients[1]",
                "cleaner_row_role": "nested_display_only",
                "score_eligible_by_cleaner": False,
                "role_classification": "recognized_non_scorable",
                "scoreable_identity": False,
            },
        ],
        "ingredients_skipped": [
            {
                "raw_source_text": "QPower",
                "name": "QPower",
                "standard_name": "Quercetin",
                "canonical_id": "quercetin",
                "parent_key": "quercetin",
                "raw_source_path": "activeIngredients[2].child_ingredients[0]",
                "cleaner_row_role": "nested_display_only",
                "score_exclusion_reason": "nested_display_only",
                "score_eligible_by_cleaner": False,
                "role_classification": "recognized_non_scorable",
                "scoreable_identity": False,
                "mapped_identity": True,
                "mapped": True,
                "raw_taxonomy": {"category": "botanical"},
            },
            {
                "raw_source_text": "Rhodiola",
                "name": "Rhodiola",
                "standard_name": "Rhodiola",
                "canonical_id": "rhodiola",
                "parent_key": "rhodiola",
                "raw_source_path": "activeIngredients[2].child_ingredients[1]",
                "cleaner_row_role": "nested_display_only",
                "score_exclusion_reason": "nested_display_only",
                "score_eligible_by_cleaner": False,
                "role_classification": "recognized_non_scorable",
                "scoreable_identity": False,
                "mapped_identity": True,
                "mapped": True,
                "raw_taxonomy": {"category": "botanical"},
            },
        ],
        "ingredients": [
            scoring_row(0, "Vitamin D3", "vitamin_d", 125, "mcg"),
            scoring_row(1, "Vitamin K2", "vitamin_k", 50, "mcg"),
        ],
    }

    blob = build_detail_blob(enriched, make_scored())
    row = row_as_dict(build_core_row(
        enriched,
        make_scored(),
        "2026-04-10T12:00:00Z",
        detail_blob=blob,
    ))
    categories = classify_product_categories(enriched, make_scored())

    assert [ing["canonical_id"] for ing in blob["ingredients"]] == ["vitamin_d", "vitamin_k"]
    assert json.loads(row["key_ingredient_tags"]) == ["vitamin_d", "vitamin_k"]
    assert categories["contains_adaptogens"] == 0
    assert categories["contains_probiotics"] == 0
    assert "QPower" not in row["ingredients_text"]
    assert "Rhodiola" not in row["ingredients_text"]


def test_export_empty_strict_primary_contract_does_not_fallback_to_blend_children():
    enriched = make_enriched()
    enriched["product_name"] = "Nature Blend"
    enriched["supplement_taxonomy"] = {
        "primary_type": "multi_or_complex",
        "secondary_type": "",
    }
    enriched["activeIngredients"] = [
        {
            "name": "QPower",
            "standardName": "Quercetin",
            "normalized_key": "quercetin",
            "canonical_id": "quercetin",
            "raw_source_text": "QPower",
            "raw_source_path": "activeIngredients[0].child_ingredients[0]",
            "quantity": 0,
            "unit": "NP",
        },
        {
            "name": "Rhodiola",
            "standardName": "Rhodiola",
            "normalized_key": "rhodiola",
            "canonical_id": "rhodiola",
            "raw_source_text": "Rhodiola",
            "raw_source_path": "activeIngredients[0].child_ingredients[1]",
            "quantity": 0,
            "unit": "NP",
        },
    ]
    skipped_rows = [
        {
            "raw_source_text": "QPower",
            "name": "QPower",
            "standard_name": "Quercetin",
            "canonical_id": "quercetin",
            "parent_key": "quercetin",
            "raw_source_path": "activeIngredients[0].child_ingredients[0]",
            "cleaner_row_role": "nested_display_only",
            "score_exclusion_reason": "nested_display_only",
            "score_eligible_by_cleaner": False,
            "role_classification": "recognized_non_scorable",
            "scoreable_identity": False,
            "mapped_identity": True,
            "mapped": True,
            "raw_taxonomy": {"category": "botanical"},
        },
        {
            "raw_source_text": "Rhodiola",
            "name": "Rhodiola",
            "standard_name": "Rhodiola",
            "canonical_id": "rhodiola",
            "parent_key": "rhodiola",
            "raw_source_path": "activeIngredients[0].child_ingredients[1]",
            "cleaner_row_role": "nested_display_only",
            "score_exclusion_reason": "nested_display_only",
            "score_eligible_by_cleaner": False,
            "role_classification": "recognized_non_scorable",
            "scoreable_identity": False,
            "mapped_identity": True,
            "mapped": True,
            "raw_taxonomy": {"category": "botanical"},
        },
    ]
    enriched["ingredient_quality_data"] = {
        "ingredients_scorable": [],
        "ingredients_recognized_non_scorable": skipped_rows,
        "ingredients_skipped": skipped_rows,
        "ingredients": [],
    }

    blob = build_detail_blob(enriched, make_scored())
    row = row_as_dict(build_core_row(
        enriched,
        make_scored(),
        "2026-04-10T12:00:00Z",
        detail_blob=blob,
    ))
    categories = classify_product_categories(enriched, make_scored())

    assert blob["ingredients"] == []
    assert json.loads(row["key_ingredient_tags"]) == []
    assert categories["contains_adaptogens"] == 0
    assert "QPower" not in row["ingredients_text"]
    assert "Rhodiola" not in row["ingredients_text"]


def test_ingredients_text_includes_as_form_compound_for_bare_mineral_active():
    # DSLD labels Sodium-compound SKUs (Sodium BHB, Sodium D-Aspartate) with a
    # bare mineral name="Sodium" and the real compound in an "as" form
    # (forms[0].name). The activeIngredients search-token fallback collected only
    # the bare name fields → ingredients_text read "Sodium sodium" and the compound
    # was unsearchable. The "as" form name must be a search token.
    enriched = make_enriched()
    enriched["product_name"] = "Sodium BHB"
    enriched["activeIngredients"] = [
        {
            "name": "Sodium",
            "standardName": "Sodium",
            "normalized_key": "sodium",
            "canonical_id": "sodium",
            "raw_source_text": "Sodium",
            "raw_source_path": "ingredientRows[0]",
            "quantity": 125,
            "unit": "mg",
            "forms": [{"name": "Sodium Beta-Hydroxybutyrate", "prefix": "as"}],
        }
    ]
    # Empty IQD → the active routes through the activeIngredients fallback loop.
    enriched["ingredient_quality_data"] = {"ingredients": [], "ingredients_scorable": []}

    blob = build_detail_blob(enriched, make_scored())
    row = row_as_dict(build_core_row(
        enriched, make_scored(), "2026-04-10T12:00:00Z", detail_blob=blob,
    ))
    assert "Sodium Beta-Hydroxybutyrate" in row["ingredients_text"], (
        f"the 'as' form compound must be searchable; got {row['ingredients_text']!r}"
    )


def test_key_ingredient_tags_use_clean_identity_for_red_yeast_rice_safety_canonical():
    enriched = make_enriched()
    enriched["activeIngredients"] = [
        {
            "name": "Red Yeast Rice powder",
            "standardName": "Red Yeast Rice",
            "normalized_key": "red_yeast_rice_powder",
            "canonical_id": "BANNED_RED_YEAST_RICE",
            "raw_source_text": "Red Yeast Rice powder",
            "quantity": 600,
            "unit": "mg",
        }
    ]
    enriched["ingredient_quality_data"]["ingredients"] = []

    categories = classify_product_categories(enriched, make_scored())

    assert categories["key_ingredient_tags"] == ["red_yeast_rice"]


def test_key_ingredient_tags_merge_iqm_and_active_canonicals_without_dropping_clean_safety_identities():
    enriched = make_enriched()
    enriched["activeIngredients"] = [
        {
            "name": "Red Yeast Rice",
            "standardName": "Red Yeast Rice",
            "normalized_key": "red_yeast_rice",
            "canonical_id": "BANNED_RED_YEAST_RICE",
            "raw_source_text": "Red Yeast Rice",
            "quantity": 1200,
            "unit": "mg",
        },
        {
            "name": "CoQ10",
            "standardName": "CoQ10",
            "normalized_key": "coq10",
            "canonical_id": "coq10",
            "raw_source_text": "CoQ10",
            "quantity": 100,
            "unit": "mg",
        },
    ]
    enriched["ingredient_quality_data"]["ingredients"] = [
        {
            "name": "CoQ10",
            "standard_name": "CoQ10",
            "canonical_id": "coq10",
            "parent_key": "coq10",
            "category": "antioxidants",
            "mapped": True,
            "dosage": 100,
            "dosage_unit": "mg",
        }
    ]

    categories = classify_product_categories(enriched, make_scored())

    assert categories["key_ingredient_tags"] == ["coq10", "red_yeast_rice"]


def test_key_ingredient_tags_emit_cbd_identity_from_cannabidiol_label_text():
    enriched = make_enriched()
    enriched["product_name"] = "CBD 10 mg Softgels"
    enriched["activeIngredients"] = [
        {
            "name": "Hemp Extract",
            "standardName": "Broad Spectrum Hemp Extract Blend",
            "normalized_key": "hemp_extract",
            "canonical_id": "nha_hemp_extract",
            "raw_source_text": "Broad Spectrum Hemp Extract Blend with Cannabidiol",
            "quantity": 10,
            "unit": "mg",
        }
    ]
    enriched["ingredient_quality_data"]["ingredients"] = []

    categories = classify_product_categories(enriched, make_scored())

    assert "cbd" in categories["key_ingredient_tags"]


def test_key_ingredient_tags_emit_vinpocetine_identity_when_safety_active_lacks_canonical():
    enriched = make_enriched()
    enriched["activeIngredients"] = [
        {
            "name": "Vinpocetine",
            "standardName": "Vinpocetine",
            "normalized_key": "vinpocetine",
            "raw_source_text": "Vinpocetine 20 mg",
            "quantity": 20,
            "unit": "mg",
        }
    ]
    enriched["ingredient_quality_data"]["ingredients"] = []

    categories = classify_product_categories(enriched, make_scored())

    assert categories["key_ingredient_tags"] == ["vinpocetine"]


def test_key_ingredient_tags_fall_back_to_cleaner_normalized_key_for_unmapped_active():
    enriched = make_enriched()
    enriched["product_name"] = "Ultra Soya Lecithin 1200 mg"
    enriched["activeIngredients"] = [
        {
            "name": "Soya Lecithin",
            "standardName": "Soya Lecithin",
            "normalized_key": "soya_lecithin",
            "canonical_id": None,
            "raw_source_text": "Soya Lecithin",
            "quantity": 1200,
            "unit": "mg",
            "mapped": False,
        }
    ]
    enriched["ingredient_quality_data"]["ingredients"] = []

    categories = classify_product_categories(enriched, make_scored())

    assert categories["key_ingredient_tags"] == ["soya_lecithin"]


def test_ingredients_text_includes_active_canonicals_when_iqm_is_empty():
    enriched = make_enriched()
    enriched["activeIngredients"] = [
        {
            "name": "Cannabidiol",
            "standardName": "CBD (Cannabidiol)",
            "normalized_key": "cannabidiol",
            "canonical_id": "BANNED_CBD_US",
            "raw_source_text": "Cannabidiol",
            "quantity": 5,
            "unit": "mg",
        }
    ]
    enriched["ingredient_quality_data"]["ingredients"] = []

    row = row_as_dict(build_core_row(enriched, make_scored(), "2026-04-10T12:00:00Z"))

    assert "Cannabidiol" in row["ingredients_text"]
    assert "CBD (Cannabidiol)" in row["ingredients_text"]
    assert "BANNED_CBD_US" in row["ingredients_text"]


def test_validate_export_contract_ships_unidentified_active_with_flag():
    """79301899: an unidentified/opaque active is no longer quarantined out of
    the export. The recall/ship-don't-drop principle ships it (no identity-gate
    issue) and the blob carries an unverified_ingredient / proprietary_blend flag
    so the user still sees the product. Was: quarantine on missing identity."""
    enriched = make_enriched()
    enriched["activeIngredients"] = [
        {
            "name": "Tea Trio(R) Blend",
            "standardName": "Tea Trio Blend",
            "normalized_key": "tea_trio_blend",
            "raw_source_text": "Tea Trio(R) Blend",
            "quantity": 1,
            "unit": "serving",
        }
    ]
    enriched["ingredient_quality_data"]["ingredients"] = []

    issues = validate_export_contract(enriched, make_scored())

    assert not any("missing required active identity" in issue for issue in issues)


def test_validate_export_contract_allows_mapped_blend_identity():
    enriched = make_enriched()
    enriched["activeIngredients"] = [
        {
            "name": "Mapped Superfood Blend",
            "standardName": "Mapped Superfood Blend",
            "normalized_key": "mapped_superfood_blend",
            "canonical_id": "blend_superfood",
            "raw_source_text": "Mapped Superfood Blend",
            "quantity": 1,
            "unit": "serving",
        }
    ]
    enriched["ingredient_quality_data"]["ingredients"] = []

    issues = validate_export_contract(enriched, make_scored())
    categories = classify_product_categories(enriched, make_scored())

    assert not any("missing required active identity" in issue for issue in issues)
    assert categories["key_ingredient_tags"] == ["blend_superfood"]


def test_ingredient_fingerprint_uses_canonical_ids_and_singular_categories():
    enriched = make_enriched()
    enriched["ingredient_quality_data"]["ingredients"] = [
        {
            "name": "Potassium",
            "standard_name": "Potassium",
            "canonical_id": "potassium",
            "category": "mineral",
            "mapped": True,
            "quantity": 99,
            "unit": "mg",
        },
        {
            "name": "Ashwagandha Root",
            "standard_name": "Ashwagandha",
            "canonical_id": "ashwagandha",
            "category": "botanical",
            "mapped": True,
            "quantity": 300,
            "unit": "mg",
        },
    ]

    fingerprint = generate_ingredient_fingerprint(enriched)

    assert "potassium" in fingerprint["nutrients"]
    assert "Potassium" not in fingerprint["nutrients"]
    assert fingerprint["nutrients"]["potassium"] == {"amount": 99.0, "unit": "mg"}
    assert fingerprint["herbs"] == ["ashwagandha"]
    assert "mineral" in fingerprint["categories"]
    assert "botanical" in fingerprint["categories"]


def test_ingredient_fingerprint_sums_same_unit_forms_with_one_canonical_id():
    enriched = make_enriched()
    enriched["ingredient_quality_data"]["ingredients"] = [
        {
            "name": "Vitamin K1",
            "standard_name": "Vitamin K1",
            "canonical_id": "vitamin_k",
            "category": "vitamins",
            "quantity": 100,
            "unit": "mcg",
        },
        {
            "name": "Vitamin K2",
            "standard_name": "Vitamin K2",
            "canonical_id": "vitamin_k",
            "category": "vitamins",
            "quantity": 30,
            "unit": "mcg",
        },
    ]

    fingerprint = generate_ingredient_fingerprint(enriched)

    assert fingerprint["nutrients"]["vitamin_k"] == {
        "amount": 130.0,
        "unit": "mcg",
    }


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


def test_resolver_only_watchlist_warning_keeps_watchlist_semantics():
    enriched = make_enriched()
    enriched["activeIngredients"] = []
    enriched["inactiveIngredients"] = [
        {
            "name": "Phthalates",
            "raw_source_text": "Phthalates",
            "standardName": "Phthalates",
        }
    ]
    enriched["contaminant_data"]["banned_substances"]["substances"] = []
    scored = make_scored(verdict="CAUTION")

    blob = build_detail_blob(enriched, scored)

    warnings = [
        w for w in blob["warnings_profile_gated"]
        if w.get("source") == "inactive_ingredient_resolver"
    ]
    assert any(
        w.get("matched_rule_id") == "BANNED_ADD_PHTHALATES"
        and w.get("type") == "watchlist_substance"
        and w.get("severity") == "moderate"
        and w.get("display_mode_default") == "informational"
        for w in warnings
    )


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

    assert len(warnings) <= 5
    assert warnings[0].startswith("Banned substance:")
    assert warnings[1].startswith("Recalled ingredient:")
    assert not any(w.startswith("Allergen:") for w in warnings)
    assert any("Interaction:" in w for w in warnings)
    assert any("sugar" in w.lower() for w in warnings)
    assert all("Discontinued" not in warning for warning in warnings)


def test_top_warnings_include_rda_ul_safety_flags():
    enriched = make_enriched()
    enriched["rda_ul_data"] = {
        "safety_flags": [
            {"nutrient": "Vitamin B6", "pct_ul": 588, "severity": "high"},
        ]
    }

    warnings = build_top_warnings(enriched)

    assert any(
        warning == "Upper-limit warning: Vitamin B6 at 588% of UL"
        for warning in warnings
    )


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


def test_build_final_db_default_mode_allows_enriched_scored_mismatch(monkeypatch):
    """Default (non-strict) mode exports matched products without raising."""
    _patch_v4_by_id(monkeypatch, {"999": _canned_v4()})
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

        # Default (non-strict) mode should NOT raise.
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


def test_generate_dosing_summary_converts_mg_powder_serving_to_grams():
    enriched = {
        "servingsPerContainer": 60,
        "serving_basis": {
            "basis_count": 2500,
            "basis_unit": "mg",
            "max_servings_per_day": 4,
        },
        "form_factor_canonical": "powder",
    }

    dosing = generate_dosing_summary(enriched)

    assert dosing["dosing_summary"] == "Mix 2.5 grams four times daily"


def test_generate_dosing_summary_hides_implausible_collagen_weight_serving():
    enriched = {
        "product_name": "Collagen Peptides Powder",
        "serving_basis": {
            "basis_count": 2500,
            "basis_unit": "g",
            "max_servings_per_day": 4,
        },
        "form_factor_canonical": "powder",
    }

    dosing = generate_dosing_summary(enriched)

    assert dosing["dosing_summary"] == "See product label"


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


def test_final_db_has_110_columns():
    # Tuple emitted by build_core_row must match the 110-column schema
    # (v2.0.0 + 6 v4 pillar component columns + safety_signal_reason
    # + goal_matches_underdosed).
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
    assert len(row) == 110
    assert len(PRODUCTS_CORE_COLUMNS) == 110


def test_products_core_exports_production_v4_columns():
    assert "quality_score_v4_100" in PRODUCTS_CORE_COLUMNS
    assert "quality_score_status" in PRODUCTS_CORE_COLUMNS
    assert "v4_module" in PRODUCTS_CORE_COLUMNS
    assert "v4_confidence" in PRODUCTS_CORE_COLUMNS
    assert not any(col.startswith("shadow_") for col in PRODUCTS_CORE_COLUMNS)


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

    def test_key_nutrients_summary_includes_dietary_fiber_from_nutrition_facts(self):
        enriched = self._enriched_with_nutrition(fiber=7.0)

        summary = generate_key_nutrients_summary(enriched)

        assert {
            "name": "Dietary Fiber",
            "amount": 7.0,
            "unit": "g",
        } in summary

    def test_key_nutrients_summary_includes_scored_fiber_ingredient(self):
        enriched = make_enriched()
        enriched["ingredient_quality_data"] = {
            "ingredients": [
                {
                    "standard_name": "Psyllium Husk",
                    "category": "fiber",
                    "normalized_amount": 5.0,
                    "normalized_unit": "g",
                }
            ]
        }

        summary = generate_key_nutrients_summary(enriched)

        assert {
            "name": "Psyllium Husk",
            "amount": 5.0,
            "unit": "g",
        } in summary

    def test_key_nutrients_summary_reads_modern_scorable_b_complex_rows(self):
        enriched = make_enriched()
        enriched["ingredient_quality_data"] = {
            "ingredients_scorable": [
                {
                    "standard_name": "Vitamin B6",
                    "canonical_id": "vitamin_b6_pyridoxine",
                    "category": "vitamins",
                    "quantity": 10,
                    "unit": "mg",
                },
                {
                    "standard_name": "Folate",
                    "canonical_id": "vitamin_b9_folate",
                    "category": "vitamins",
                    "quantity": 400,
                    "unit": "mcg",
                },
                {
                    "standard_name": "Vitamin B12",
                    "canonical_id": "vitamin_b12_cobalamin",
                    "category": "vitamins",
                    "quantity": 500,
                    "unit": "mcg",
                },
                {
                    "standard_name": "Niacin",
                    "canonical_id": "vitamin_b3_niacin",
                    "category": "vitamins",
                    "quantity": 20,
                    "unit": "mg",
                },
            ]
        }

        summary = generate_key_nutrients_summary(enriched)
        names = [item["name"] for item in summary]

        assert names[:4] == ["Niacin", "Vitamin B6", "Folate", "Vitamin B12"]
        assert {"name": "Folate", "amount": 400.0, "unit": "mcg"} in summary

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

    def test_core_row_column_count_is_110(self):
        row = build_core_row(make_enriched(), make_scored(), "2026-04-10T12:00:00Z")
        assert len(row) == 110
        assert CORE_COLUMN_COUNT == 110

    def test_schema_version_bumped_to_200(self):
        assert EXPORT_SCHEMA_VERSION == "2.0.0"

    def test_detail_blob_emits_demoted_absorption_enhancers(self):
        """Sprint E1.23 follow-up (2026-05-09): the enricher produces
        `ingredient_quality_data.demoted_absorption_enhancers`; the build
        step must promote it to the detail blob so the Flutter
        `formulation_detail_section` can render bioavailability-aid
        chips. Pre-fix, this list was silently dropped on the floor.
        """
        enriched = make_enriched()
        existing_iqd = enriched.get("ingredient_quality_data") or {}
        enriched["ingredient_quality_data"] = {
            **existing_iqd,
            "demoted_absorption_enhancers": [
                {"name": "BioPerine", "quantity": 5.0, "unit": "mg"},
            ],
        }
        blob = build_detail_blob(enriched, make_scored())
        assert "ingredient_quality_data" in blob, (
            'Pipeline must emit ingredient_quality_data so Flutter can '
            'read demoted_absorption_enhancers'
        )
        iqd = blob["ingredient_quality_data"]
        assert iqd["demoted_absorption_enhancers"] == [
            {"name": "BioPerine", "quantity": 5.0, "unit": "mg"},
        ]

    def test_detail_blob_omits_ingredient_quality_data_when_no_demoted(self):
        """Empty list → key not emitted (cleaner blob, less wire bytes).
        Flutter handles missing key the same as empty list via `?? const {}`.
        """
        enriched = make_enriched()
        existing_iqd = enriched.get("ingredient_quality_data") or {}
        enriched["ingredient_quality_data"] = {
            **existing_iqd,
            "demoted_absorption_enhancers": [],
        }
        blob = build_detail_blob(enriched, make_scored())
        assert "ingredient_quality_data" not in blob

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


# ─────────────────────────────────────────────────────────────────────────────
# v4 export wiring integration (export schema v2.0.0)
#
# build_final_db runs the export adapter, which calls score_product_v4.
# We monkeypatch that scorer with canned, per-dsld_id results so the test
# deterministically exercises the FULL wiring (overlay
# → review-queue gate → build_core_row → build_detail_blob → dedup) without
# depending on whether a synthetic fixture happens to be v4-complete.
# ─────────────────────────────────────────────────────────────────────────────

from scoring_v4 import export_adapter as _v4_export_adapter  # noqa: E402


def _canned_v4(status="scored", quality_100=88.0, verdict="SAFE", tier="Strong",
               safety_verdict=None, blocking_reason=None, suppressed_reason=None):
    return {
        "raw_score_v4_100": quality_100 if quality_100 is not None else 88.0,
        "v4_module": "generic",
        "v4_verdict": verdict,
        "v4_confidence": "high",
        "v4_anchored": False,
        "v4_display_100": 92.0,  # experimental — must be IGNORED
        "v4_breakdown": {
            "provenance": {
                "scoring_engine_version": "4.0.0",
                "classification_schema_version": "5.3.0",
                "config_versions": {"quality_score": "1.0.0"},
                "module_route": "generic",
                "mode": "production",
            },
            "safety_gate": {"verdict": safety_verdict, "blocking_reason": blocking_reason,
                            "clean_label_hits": []},
            "completeness_gate": {"module": "generic", "is_live_eligible": status != "not_scored"},
            "confidence": {
                "band": "high",
                "evidence": {"level": "high", "drivers": []},
                "label_completeness": {"level": "high", "drivers": []},
                "verification": {"level": "high", "drivers": []},
                "identity": {"level": "high", "drivers": []},
                "score_uncertainty_pts": 1,
            },
            "module": {"dimensions": {"formulation": {"score": 18}}},
        },
        "raw_score_v4_100": quality_100,
        "quality_score_v4_100": quality_100,
        "quality_pillars_v4": (
            {"formulation": {"score": 18.0, "max": 20, "reason": "good purpose-fit"},
             "evidence": {"score": 10.0, "max": 20, "reason": "moderate evidence"}}
            if status == "scored" else None
        ),
        "quality_tier": tier,
        "quality_score_status": status,
        "quality_score_suppressed_reason": suppressed_reason,
        "clean_label_flags_v4": None,
        "quality_score_version": "1.0.0-test",
    }


def _patch_v4_by_id(monkeypatch, by_id):
    """Make the export adapter's v4 scorer return canned results keyed by dsld_id."""
    def fake(enriched):
        return by_id[str(enriched.get("dsld_id"))]
    monkeypatch.setattr(_v4_export_adapter, "score_product_v4", fake)


def test_v4_overlay_removes_stale_omega_form_flag_when_v4_detects_form(monkeypatch):
    """The exported legacy flags must not contradict v4's omega form detector."""
    scored_v4 = _canned_v4(status="scored", quality_100=90.3, verdict="SAFE", tier="Excellent")
    scored_v4["v4_module"] = "omega"
    scored_v4["v4_breakdown"]["provenance"]["module_route"] = "omega"
    scored_v4["v4_breakdown"]["module"] = {
        "dimensions": {
            "formulation": {"metadata": {"form_detected": "rtg"}},
            "transparency": {"components": {"form_disclosed": 3.0}},
        }
    }
    monkeypatch.setattr(_v4_export_adapter, "score_product_v4", lambda _enriched: scored_v4)

    overlaid = _v4_export_adapter.overlay_v4_scored(
        {"dsld_id": "omega-rtg"},
        {"flags": ["OMEGA3_FORM_NOT_DISCLOSED", "SUPPLEMENT_TYPE_REINFERRED"]},
    )

    assert overlaid["flags"] == ["SUPPLEMENT_TYPE_REINFERRED"]


def test_v4_overlay_keeps_omega_form_flag_when_v4_form_is_undefined(monkeypatch):
    """True undefined-form omega products should still carry the disclosure flag."""
    scored_v4 = _canned_v4(status="scored", quality_100=85.9, verdict="SAFE", tier="Strong")
    scored_v4["v4_module"] = "omega"
    scored_v4["v4_breakdown"]["provenance"]["module_route"] = "omega"
    scored_v4["v4_breakdown"]["module"] = {
        "dimensions": {
            "formulation": {"metadata": {"form_detected": "undefined"}},
            "transparency": {"components": {}},
        }
    }
    monkeypatch.setattr(_v4_export_adapter, "score_product_v4", lambda _enriched: scored_v4)

    overlaid = _v4_export_adapter.overlay_v4_scored({"dsld_id": "omega-undefined"}, {"flags": []})

    assert overlaid["flags"] == ["OMEGA3_FORM_NOT_DISCLOSED"]


def test_v4_overlay_removes_stale_section_a_zero_flag_when_v4_scores(monkeypatch):
    """Legacy v3 Section-A-zero flags must not ship on v4-live products."""
    scored_v4 = _canned_v4(status="scored", quality_100=90.7, verdict="SAFE", tier="Excellent")
    scored_v4["v4_module"] = "fiber_digestive"
    scored_v4["v4_breakdown"]["provenance"]["module_route"] = "fiber_digestive"
    scored_v4["v4_breakdown"]["completeness_gate"] = {
        "module": "fiber_digestive",
        "is_live_eligible": True,
    }
    monkeypatch.setattr(_v4_export_adapter, "score_product_v4", lambda _enriched: scored_v4)

    overlaid = _v4_export_adapter.overlay_v4_scored(
        {"dsld_id": "psyllium-live"},
        {"flags": ["SECTION_A_ZERO_NO_SCORABLE_INGREDIENTS", "SUPPLEMENT_TYPE_REINFERRED"]},
    )

    assert overlaid["flags"] == ["SUPPLEMENT_TYPE_REINFERRED"]


def test_build_core_row_reconciles_stale_v3_flags_from_v4_contract():
    """The final products_core flags column must follow v4, not stale v3 diagnostics."""
    enriched = make_enriched()
    scored = make_scored()
    scored.update({
        "flags": [
            "SECTION_A_ZERO_NO_SCORABLE_INGREDIENTS",
            "OMEGA3_FORM_NOT_DISCLOSED",
            "PROPRIETARY_BLEND_PRESENT",
            "SUPPLEMENT_TYPE_REINFERRED",
        ],
        "_v4_quality_status": "scored",
        "_v4_quality_score_100": 90.7,
        "_v4_module": "omega",
        "_v4_module_breakdown": {
            "dimensions": {
                "formulation": {"metadata": {"form_detected": "rtg"}},
                "transparency": {
                    "components": {
                        "form_disclosed": 3.0,
                        "strain_identities_named": 8.0,
                        "per_strain_cfu_on_label": 7.0,
                    },
                },
            },
        },
    })

    row = row_as_dict(build_core_row(enriched, scored, "2026-06-30T12:00:00Z"))

    assert json.loads(row["flags"]) == [
        "PROPRIETARY_BLEND_PRESENT",
        "SUPPLEMENT_TYPE_REINFERRED",
    ]


def test_build_core_row_reconciles_probiotic_proprietary_flag_from_v4_contract():
    """Fully disclosed probiotic labels must not ship stale proprietary-blend flags."""
    enriched = make_enriched()
    scored = make_scored()
    scored.update({
        "flags": ["PROPRIETARY_BLEND_PRESENT", "SUPPLEMENT_TYPE_REINFERRED"],
        "_v4_quality_status": "scored",
        "_v4_quality_score_100": 91.2,
        "_v4_module": "probiotic",
        "_v4_module_breakdown": {
            "dimensions": {
                "transparency": {
                    "components": {
                        "strain_identities_named": 8.0,
                        "per_strain_cfu_on_label": 7.0,
                    },
                },
            },
        },
    })

    row = row_as_dict(build_core_row(enriched, scored, "2026-06-30T12:00:00Z"))

    assert json.loads(row["flags"]) == ["SUPPLEMENT_TYPE_REINFERRED"]


def _run_build(tmp, enriched_list, scored_list):
    root = Path(tmp)
    enriched_dir = root / "enriched"; enriched_dir.mkdir()
    scored_dir = root / "scored"; scored_dir.mkdir()
    output_dir = root / "out"
    (enriched_dir / "batch.json").write_text(json.dumps(enriched_list), encoding="utf-8")
    (scored_dir / "batch.json").write_text(json.dumps(scored_list), encoding="utf-8")
    result = build_final_db([str(enriched_dir)], [str(scored_dir)], str(output_dir),
                            str(Path(__file__).parent.parent))
    return result, output_dir


def _core_rows(output_dir, cols):
    """Return {dsld_id: {col: value}} for the selected columns (cols[0] must be dsld_id)."""
    conn = sqlite3.connect(output_dir / "pharmaguide_core.db")
    try:
        rows = conn.execute(f"SELECT {', '.join(cols)} FROM products_core").fetchall()
    finally:
        conn.close()
    return {r[0]: dict(zip(cols, r)) for r in rows}


def test_v4_build_populates_columns_and_quarantines_not_scored(monkeypatch):
    e1 = make_enriched()  # dsld_id 999
    e2 = make_enriched(); e2["dsld_id"] = "888"; e2["product_name"] = "Blocked P"
    e3 = make_enriched(); e3["dsld_id"] = "777"; e3["product_name"] = "NotScored P"
    # Distinct UPCs so the three are not collapsed by UPC dedup.
    e1["upcSku"] = "111111111111"; e2["upcSku"] = "222222222222"; e3["upcSku"] = "333333333333"
    s1 = make_scored(); s1["dsld_id"] = "999"
    s2 = make_scored(); s2["dsld_id"] = "888"
    s3 = make_scored(); s3["dsld_id"] = "777"
    scored_live = _canned_v4(status="scored", quality_100=88.0, verdict="SAFE", tier="Strong")
    scored_live["quality_score_cap_v4"] = {
        "id": "generic_astaxanthin_single",
        "cap": 85.0,
        "applied": True,
    }
    _patch_v4_by_id(monkeypatch, {
        "999": scored_live,
        "888": _canned_v4(status="suppressed_safety", quality_100=None, verdict="BLOCKED",
                          tier=None, safety_verdict="BLOCKED",
                          blocking_reason="banned_ingredient", suppressed_reason="banned_ingredient"),
        "777": _canned_v4(status="not_scored", quality_100=None, verdict="NOT_SCORED", tier=None),
    })
    with tempfile.TemporaryDirectory() as tmp:
        _result, out = _run_build(tmp, [e1, e2, e3], [s1, s2, s3])
        cols = ["dsld_id", "quality_score_v4_100", "quality_score_status", "quality_tier",
                "score_model_version", "verdict", "score_100_equivalent",
                "scoring_engine_version", "raw_score_v4_100"]
        rows = _core_rows(out, cols)

        # NOT_SCORED is quarantined; SAFE (scored) and BLOCKED (reason is the data) ship.
        assert set(rows) == {"999", "888"}

        scored = rows["999"]
        assert scored["quality_score_v4_100"] == 88.0
        assert scored["quality_score_status"] == "scored"
        assert scored["quality_tier"] == "Strong"
        assert scored["score_model_version"] == "v4"
        assert scored["score_100_equivalent"] == 88.0  # /100 compat mirror
        assert scored["scoring_engine_version"] == "4.0.0"
        assert scored["raw_score_v4_100"] == 88.0
        # a profile-gated hard-safety warning may flip SAFE→CAUTION; both are non-suppressed.
        assert scored["verdict"] in {"SAFE", "CAUTION"}

        blocked = rows["888"]
        assert blocked["quality_score_v4_100"] is None
        assert blocked["quality_score_status"] == "suppressed_safety"
        assert blocked["verdict"] == "BLOCKED"
        assert blocked["score_100_equivalent"] is None

        # The scored product's detail blob carries the six pillars + provenance + explanation.
        blob = json.loads((out / "detail_blobs" / "999.json").read_text(encoding="utf-8"))
        assert blob["quality_pillars_v4"]
        assert blob["v4_score_provenance"]["score_model_version"] == "v4"
        assert blob["v4_confidence_detail"]["band"] == "high"
        assert blob["v4_confidence_detail"]["score_uncertainty_pts"] == 1
        assert blob["quality_score_cap_v4"]["id"] == "generic_astaxanthin_single"
        assert "v4_score_explanation" in blob
        assert blob["raw_score_v4_100"] == 88.0


def test_v4_pillar_columns_projected_for_scored_and_null_for_suppressed(monkeypatch):
    """Contract: build_final_db projects every quality_pillars_v4 score into the
    products_core pillar_*_v4 columns for scored products (each within [0, max]),
    and leaves all six NULL for suppressed products.

    Regression guard for the 2026-06-14 stale-DB incident: the shipped DB was
    built *before* the pillar-projection commit (6f02c4f8) and went out with the
    six pillar columns absent — invisible to the dashboard's six-pillar audits.
    Selecting the pillar columns below also fails loudly ("no such column") if a
    future schema change drops them, so this guards both projection and schema.
    """
    pillar_cols = [
        "pillar_formulation_v4", "pillar_dose_v4", "pillar_evidence_v4",
        "pillar_transparency_v4", "pillar_verification_v4", "pillar_safety_hygiene_v4",
    ]
    pillar_max = dict(zip(pillar_cols, [20, 20, 20, 15, 15, 10]))

    e1 = make_enriched()  # dsld_id 999 — scored
    e2 = make_enriched(); e2["dsld_id"] = "888"; e2["product_name"] = "Blocked P"
    e1["upcSku"] = "111111111111"; e2["upcSku"] = "222222222222"
    s1 = make_scored(); s1["dsld_id"] = "999"
    s2 = make_scored(); s2["dsld_id"] = "888"

    # The real scorer always emits all six pillars for a scored product; the
    # shared _canned_v4 only carries two, so build a six-pillar result here.
    scored_v4 = _canned_v4(status="scored", quality_100=88.0)
    scored_v4["quality_pillars_v4"] = {
        "formulation": {"score": 18.0, "max": 20},
        "dose": {"score": 16.0, "max": 20},
        "evidence": {"score": 10.0, "max": 20},
        "transparency": {"score": 12.0, "max": 15},
        "verification": {"score": 9.0, "max": 15},
        "safety_hygiene": {"score": 10.0, "max": 10},
    }
    _patch_v4_by_id(monkeypatch, {
        "999": scored_v4,
        "888": _canned_v4(status="suppressed_safety", quality_100=None, verdict="BLOCKED",
                          tier=None, safety_verdict="BLOCKED",
                          blocking_reason="banned_ingredient", suppressed_reason="banned_ingredient"),
    })

    with tempfile.TemporaryDirectory() as tmp:
        _result, out = _run_build(tmp, [e1, e2], [s1, s2])
        rows = _core_rows(out, ["dsld_id"] + pillar_cols)

        # Scored: all six columns populated, each within [0, max], matching scores.
        scored = rows["999"]
        assert scored["pillar_formulation_v4"] == 18.0
        assert scored["pillar_dose_v4"] == 16.0
        assert scored["pillar_evidence_v4"] == 10.0
        assert scored["pillar_transparency_v4"] == 12.0
        assert scored["pillar_verification_v4"] == 9.0
        assert scored["pillar_safety_hygiene_v4"] == 10.0
        for col in pillar_cols:
            assert scored[col] is not None, f"scored product missing {col}"
            assert 0 <= scored[col] <= pillar_max[col], f"{col}={scored[col]} out of [0,{pillar_max[col]}]"

        # Suppressed: no _v4_pillars overlaid → every pillar column NULL.
        blocked = rows["888"]
        for col in pillar_cols:
            assert blocked[col] is None, f"suppressed product should have NULL {col}, got {blocked[col]}"


def test_v4_dedup_keeps_scored_over_blocked_same_upc(monkeypatch):
    e_scored = make_enriched()  # 999
    e_blocked = make_enriched(); e_blocked["dsld_id"] = "888"
    upc = "012345678905"
    e_scored["upcSku"] = upc; e_scored["status"] = "active"
    e_blocked["upcSku"] = upc; e_blocked["status"] = "active"
    s1 = make_scored(); s1["dsld_id"] = "999"
    s2 = make_scored(); s2["dsld_id"] = "888"
    _patch_v4_by_id(monkeypatch, {
        "999": _canned_v4(status="scored", quality_100=70.0, verdict="SAFE", tier="Acceptable"),
        "888": _canned_v4(status="suppressed_safety", quality_100=None, verdict="BLOCKED",
                          tier=None, safety_verdict="BLOCKED", blocking_reason="banned_ingredient"),
    })
    with tempfile.TemporaryDirectory() as tmp:
        _result, out = _run_build(tmp, [e_scored, e_blocked], [s1, s2])
        rows = _core_rows(out, ["dsld_id"])
        # The scored product wins the UPC group; the BLOCKED twin is deduped away.
        assert set(rows) == {"999"}


def test_build_always_stamps_v4_score_model(monkeypatch):
    e = make_enriched()
    s = make_scored(verdict="SAFE"); s["dsld_id"] = "999"
    _patch_v4_by_id(monkeypatch, {
        "999": _canned_v4(status="scored", quality_100=75.0, verdict="SAFE", tier="Strong"),
    })
    with tempfile.TemporaryDirectory() as tmp:
        result, out = _run_build(tmp, [e], [s])
        assert result["product_count"] == 1
        rows = _core_rows(out, ["dsld_id", "score_model_version", "quality_score_v4_100",
                                "quality_score_status", "score_100_equivalent", "verdict"])
        r = rows["999"]
        assert r["score_model_version"] == "v4"
        assert r["quality_score_status"] is not None
        assert r["score_100_equivalent"] is not None
        assert r["verdict"] == "SAFE"


def test_v4_banned_substance_suppresses_score_even_when_v4_gate_scored(monkeypatch):
    """SAFETY INVARIANT (regression for the full-corpus cutover divergence):

    A product the export's banned-substance gate flags (``has_banned_substance``)
    must NEVER ship a finite v4 consumer score, even when the v4 *scoring* safety
    gate did not block it (the v4 gate is narrower — e.g. it does not block Boron /
    partially-hydrogenated-oils that ``banned_recalled_ingredients.json`` flags). The
    full v3→v4 build leaked 8 such products (Boron/PHO banned, v4-scored 58.9–70.5),
    which would then rank by ``quality_score_v4_100`` in the catalog index/dedup.

    The export must force these into the v4 ``suppressed_safety`` state — null score,
    BLOCKED verdict — preserving the v3 invariant that a banned product ships no
    consumer score. Both the catalog ROW and the detail BLOB must agree.
    """
    e = make_enriched()  # dsld_id 999
    e["upcSku"] = "111111111111"
    # Real banned-substance fixture (same shape as the active-safety-flag tests):
    # has_banned_substance(enriched) → True and the blob gets banned_substance_detail.
    e["activeIngredients"] = [
        {
            "name": "Red Yeast Rice powder",
            "raw_source_text": "Red Yeast Rice powder",
            "standardName": "Red Yeast Rice powder",
            "mapped": False,
            "safety_flags": [
                {
                    "entry_id": "BANNED_RED_YEAST_RICE",
                    "source_db": "banned_recalled_ingredients",
                    "status": "banned",
                    "severity": "critical",
                    "match_type": "token_bounded",
                    "matched_variant": "red yeast rice",
                    "evidence_text": "Red Yeast Rice powder",
                    "confidence": "medium",
                }
            ],
        }
    ]
    e["ingredient_quality_data"]["ingredients"] = []
    e["contaminant_data"]["banned_substances"] = {
        "found": True,
        "substances": [],
        "safety_flags": e["activeIngredients"][0]["safety_flags"],
    }
    s = make_scored(); s["dsld_id"] = "999"
    # v4 *scoring* gate did NOT block it — it returns a finite scored result
    # (the real divergence: v4's gate is narrower than the export banned signal).
    _patch_v4_by_id(monkeypatch, {
        "999": _canned_v4(status="scored", quality_100=70.5, verdict="SAFE", tier="Acceptable"),
    })
    with tempfile.TemporaryDirectory() as tmp:
        _result, out = _run_build(tmp, [e], [s])
        rows = _core_rows(out, ["dsld_id", "quality_score_v4_100", "quality_score_status",
                                "quality_tier", "verdict", "score_100_equivalent",
                                "has_banned_substance", "raw_score_v4_100"])
        r = rows["999"]
        assert r["has_banned_substance"] == 1
        assert r["verdict"] == "BLOCKED"
        # THE INVARIANT — no finite consumer score ships for a banned product:
        assert r["quality_score_v4_100"] is None, \
            f"banned product leaked a finite v4 score: {r['quality_score_v4_100']}"
        assert r["quality_score_status"] == "suppressed_safety"
        assert r["quality_tier"] is None
        assert r["score_100_equivalent"] is None
        # raw_score_v4_100 stays as an audit trail (never the shipped score).
        assert r["raw_score_v4_100"] == 70.5

        # The detail BLOB must agree — no "scored" v4 breakdown for a banned product.
        blob = json.loads((out / "detail_blobs" / "999.json").read_text(encoding="utf-8"))
        assert blob["v4_score_provenance"]["quality_score_status"] == "suppressed_safety"


def test_registry_verified_certs_drive_third_party_display_columns(monkeypatch):
    """2026-06-09 badge-inversion fix: a registry-verified (sku/product_line)
    cert must light has_third_party_testing and appear in cert_programs even
    when the label carries no parseable cert claim. Before this fix, Thorne
    Super EPA (two NSF SKU registry matches) shipped cert_programs=[] and
    has_third_party_testing=0 while a label-claim-only product showed the
    badge — the most-verified products displayed as least-verified.

    Cross-brand registry rows must NOT light the badge (same token-subset
    brand guard as the scoring layer; deliberately duplicated per the
    stale-artifact defense doctrine)."""
    e1 = make_enriched()  # dsld_id 999 — registry-verified only, no label claims
    e1["named_cert_programs"] = []
    e1["verified_cert_programs"] = [
        {"program": "NSF Certified", "scope": "sku", "matched_brand": "Test Brand"},
        {"program": "NSF Sport", "scope": "sku", "matched_brand": "Unrelated Megacorp"},  # cross-brand: excluded
        {"program": "USP Verified", "scope": "claimed_only"},  # unverified: excluded
    ]
    e2 = make_enriched(); e2["dsld_id"] = "888"; e2["product_name"] = "No Cert P"
    e2["upcSku"] = "0123456789888"  # distinct UPC — make_enriched's default collides in dedup
    e2["named_cert_programs"] = []
    e2["verified_cert_programs"] = []
    e3 = make_enriched(); e3["dsld_id"] = "777"; e3["product_name"] = "Label+Registry P"
    e3["upcSku"] = "0123456789777"
    e3["named_cert_programs"] = ["NSF Certified"]  # label names it too — no dupe
    e3["verified_cert_programs"] = [
        {"program": "NSF Certified", "scope": "product_line", "matched_brand": "Test Brand, Inc."},
    ]
    scored = []
    for d in ("999", "888", "777"):
        s = make_scored(); s["dsld_id"] = d; scored.append(s)
    _patch_v4_by_id(monkeypatch, {d: _canned_v4() for d in ("999", "888", "777")})
    with tempfile.TemporaryDirectory() as tmp:
        _result, out = _run_build(tmp, [e1, e2, e3], scored)
        rows = _core_rows(out, ["dsld_id", "has_third_party_testing", "cert_programs"])
        r1 = rows["999"]
        assert r1["has_third_party_testing"] == 1, (
            "registry-verified sku cert must light has_third_party_testing"
        )
        assert json.loads(r1["cert_programs"]) == ["NSF Certified"], (
            "cert_programs must list the registry-verified program and exclude "
            "cross-brand and claimed_only rows"
        )
        assert rows["888"]["has_third_party_testing"] == 0
        assert json.loads(rows["888"]["cert_programs"]) == []
        assert json.loads(rows["777"]["cert_programs"]) == ["NSF Certified"], (
            "label-named + registry-verified same program must not duplicate"
        )
