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
    generate_allergen_summary,
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


def test_allergen_summary_reads_enricher_allergen_name_contract():
    enriched = {
        "allergen_hits": [
            {"allergen_name": "Soy", "presence_type": "contains"},
            {"allergen_name": "Tree Nuts", "presence_type": "contains"},
        ]
    }

    assert generate_allergen_summary(enriched) == "Contains: Soy, Tree Nuts"


def test_allergen_summary_preserves_presence_language():
    enriched = {
        "allergen_hits": [
            {"allergen_name": "Milk", "presence_type": "contains"},
            {"allergen_name": "Soy", "presence_type": "may_contain"},
            {
                "allergen_name": "Tree Nuts",
                "presence_type": "manufactured_in_facility",
            },
        ]
    }

    assert generate_allergen_summary(enriched) == (
        "Contains: Milk. May contain: Soy. "
        "Made in a facility that also handles: Tree Nuts"
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
        assert manifest["scoring_version"] == "4.1.0"
        assert manifest["quality_score_config_checksum"].startswith("sha256:")
        assert "scoring_config_checksum" not in manifest
        assert "scoring_config_checksum" not in manifest["integrity"]


def test_build_backfills_v4_category_percentiles(monkeypatch):
    """End-to-end: after the build, products_core carries a V4 percentile ranked
    over the shipped quality_score_v4_100 within each percentile_category cohort.
    Cohorts < 5 stay NULL. The backfill runs AFTER UPC dedup, so the five ranked
    products carry distinct UPCs to all survive into the cohort.
    """
    ranked = [("801", 95.0), ("802", 85.0), ("803", 75.0), ("804", 65.0), ("805", 55.0)]
    canned = {pid: _canned_v4(status="scored", quality_100=sc) for pid, sc in ranked}
    canned["806"] = _canned_v4(status="scored", quality_100=70.0)  # solo cohort -> unranked

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
        return _artifact_from_canned(pid, canned[pid])

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


def test_export_uses_taxonomy_over_stale_compatibility_values():
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
    enriched["supplement_taxonomy"] = {
        "primary_type": "probiotic",
        "secondary_type": None,
        "classification_confidence": 0.9,
        "classification_reasons": ["probiotic identity"],
    }
    enriched["primary_type"] = "probiotic"

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
    pillars = {
        "formulation": {"score": 15.0, "max": 20.0},
        "dose": {"score": 15.0, "max": 20.0},
        "evidence": {"score": 15.0, "max": 20.0},
        "transparency": {"score": 10.0, "max": 15.0},
        "verification": {"score": 10.0, "max": 15.0},
        "safety_hygiene": {"score": 10.0, "max": 10.0},
    }
    return {
        "score_80": 60.0,
        "display": "60.0/80",
        "display_100": "75.0/100",
        "score_100_equivalent": 75.0,
        "grade": "Good",
        "verdict": verdict,
        "safety_verdict": verdict,
        "mapped_coverage": 1.0,
        "score_basis": "v4_six_pillar",
        "output_schema_version": "4.0.0",
        "quality_score_v4_100": 75.0,
        "quality_score_status": "scored",
        "quality_pillars_v4": pillars,
        "_score_model_version": "v4",
        "_v4_quality_score_100": 75.0,
        "_v4_quality_status": "scored",
        "_v4_quality_tier": "Good",
        "_v4_raw_score_100": 75.0,
        "_v4_module": "generic",
        "_v4_confidence": "high",
        "_v4_quality_version": "test",
        "_v4_scoring_engine_version": "4.1.0",
        "_v4_classification_schema_version": "1.2.0",
        "_v4_pillars": pillars,
        "_v4_safety_gate": {"verdict": verdict, "safety_signals": []},
        "_v4_completeness_gate": {"mapped_coverage": 1.0},
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
    assert row["quality_score_status"] == "suppressed_safety"
    assert row["quality_score_v4_100"] is None
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


def test_inactive_display_tone_uses_public_scoring_penalty_outcome():
    enriched = make_enriched()
    enriched["inactiveIngredients"] = [
        {
            "name": "Maltodextrin",
            "raw_source_text": "Maltodextrin",
            "standardName": "Maltodextrin",
        }
    ]
    scored = make_scored()
    scored["_v4_inactive_penalty_details"] = [
        {
            "matched_rule_id": "ADD_MALTODEXTRIN",
            "penalty_tier": "low",
            "penalty_applied": 0.5,
        }
    ]

    blob = build_detail_blob(enriched, scored)

    assert blob["inactive_ingredients"][0]["display_tone"] == "light_orange"


def test_clean_label_flags_do_not_masquerade_as_inactive_penalties():
    enriched = make_enriched()
    enriched["inactiveIngredients"] = [
        {
            "name": "Maltodextrin",
            "raw_source_text": "Maltodextrin",
            "standardName": "Maltodextrin",
        }
    ]
    scored = make_scored()
    scored["_v4_clean_label_flags"] = [
        {
            "matched_rule_id": "ADD_MALTODEXTRIN",
            "penalty_applied": 3.0,
        }
    ]

    blob = build_detail_blob(enriched, scored)

    assert blob["inactive_ingredients"][0]["display_tone"] is None


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
    # Blob flag fields are a JSON contract: real true/false via json_bool,
    # NOT safe_bool's 0/1 (which is for SQLite core columns).
    enriched = make_enriched()
    enriched["claim_gluten_free_validated"] = True
    blob = build_detail_blob(enriched, make_scored())
    assert blob["gluten_free_validated"] is True

    enriched["claim_gluten_free_validated"] = False
    blob = build_detail_blob(enriched, make_scored())
    assert blob["gluten_free_validated"] is False

    # Missing (older blobs) → defaults to False
    enriched.pop("claim_gluten_free_validated", None)
    blob = build_detail_blob(enriched, make_scored())
    assert blob["gluten_free_validated"] is False


def test_detail_blob_flag_fields_are_real_json_booleans():
    """Contract: blob flag fields serialize as JSON true/false, never int 0/1.

    Root cause of the Flutter blend/GMP misreads: build_final_db emitted these
    via safe_bool (0/1). They now go through json_bool. Guard both the Python
    type (bool, not just int-truthy) and the JSON serialization so the contract
    can't silently drift back to ints. bool is an int subclass in Python, so
    `type(x) is bool` is the assertion that actually pins it.
    """
    import json as _json

    enriched = make_enriched()
    enriched["proprietary_data"]["has_proprietary_blends"] = True
    blob = build_detail_blob(enriched, make_scored())

    cert = blob["certification_detail"]
    flag_values = {
        "certification_detail.purity_verified": cert["purity_verified"],
        "certification_detail.heavy_metal_tested": cert["heavy_metal_tested"],
        "certification_detail.label_accuracy_verified": cert["label_accuracy_verified"],
        "manufacturer_detail.is_trusted": blob["manufacturer_detail"]["is_trusted"],
        "proprietary_blend_detail.has_proprietary_blends": blob[
            "proprietary_blend_detail"
        ]["has_proprietary_blends"],
        "gluten_free_validated": blob["gluten_free_validated"],
    }
    # Row-level flags — same field must not ship mixed int/bool across products.
    for row in blob["ingredients"]:
        flag_values[f"ingredients[].is_mapped:{row['name']}"] = row["is_mapped"]
        flag_values[f"ingredients[].mapped:{row['name']}"] = row["mapped"]
    for row in blob["inactive_ingredients"]:
        flag_values[f"inactive[].is_additive:{row['name']}"] = row["is_additive"]

    for label, value in flag_values.items():
        assert type(value) is bool, f"{label} shipped {type(value).__name__}, not bool"

    # Serialization: a positive flag must render as JSON `true`, not `1`.
    assert '"has_proprietary_blends": true' in _json.dumps(blob)
    assert blob["proprietary_blend_detail"]["has_proprietary_blends"] is True


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
    assert any("Watchlist ingredient:" in warning["title"] for warning in warnings)
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
    assert warnings[0]["title"].startswith("Banned substance:")
    assert warnings[1]["title"].startswith("Recalled ingredient:")
    assert not any(w["title"].startswith("Allergen:") for w in warnings)
    assert any("Interaction:" in w["title"] for w in warnings)
    assert any("sugar" in w["title"].lower() for w in warnings)
    assert all("Discontinued" not in warning["title"] for warning in warnings)


def test_top_warnings_include_rda_ul_safety_flags():
    enriched = make_enriched()
    enriched["rda_ul_data"] = {
        "safety_flags": [
            {"nutrient": "Vitamin B6", "pct_ul": 588, "severity": "high"},
        ]
    }

    warnings = build_top_warnings(enriched)

    assert any(
        warning["title"] == "Upper-limit warning: Vitamin B6 at 588% of UL"
        for warning in warnings
    )


def test_top_warnings_preserve_structured_identity_for_flutter():
    enriched = make_enriched()
    enriched["rda_ul_data"] = {
        "safety_flags": [
            {"nutrient": "Vitamin B6", "pct_ul": 588, "severity": "high"},
        ]
    }

    warnings = build_top_warnings(enriched)

    assert {
        "type": "dose_safety",
        "severity": "high",
        "title": "Upper-limit warning: Vitamin B6 at 588% of UL",
    } in warnings


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
        assert EXPORT_SCHEMA_VERSION == "2.1.0"

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
# v4-native scored-artifact integration (export schema v2.0.0)
# ─────────────────────────────────────────────────────────────────────────────


def _canned_v4(status="scored", quality_100=88.0, verdict="SAFE", tier="Strong",
               safety_verdict=None, blocking_reason=None, suppressed_reason=None):
    ratio = float(quality_100 or 0.0) / 100.0
    pillars = {
        "formulation": {"score": round(20.0 * ratio, 3), "max": 20.0},
        "dose": {"score": round(20.0 * ratio, 3), "max": 20.0},
        "evidence": {"score": round(20.0 * ratio, 3), "max": 20.0},
        "transparency": {"score": round(15.0 * ratio, 3), "max": 15.0},
        "verification": {"score": round(15.0 * ratio, 3), "max": 15.0},
        "safety_hygiene": {"score": round(10.0 * ratio, 3), "max": 10.0},
    }
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
        "quality_pillars_v4": pillars if status == "scored" else None,
        "quality_tier": tier,
        "quality_score_status": status,
        "quality_score_suppressed_reason": suppressed_reason,
        "clean_label_flags_v4": None,
        "quality_score_version": "1.0.0-test",
    }


def _artifact_from_canned(dsld_id: str, v4_result: dict) -> dict:
    """Build a native Stage-3 artifact without invoking a second scorer."""
    from scoring_v4.scored_artifact import assemble_scored_artifact

    row = {
        "name": "Magnesium",
        "standard_name": "Magnesium",
        "canonical_id": "magnesium",
        "mapped_identity": True,
        "identity_disposition": "clean",
        "source_section": "active",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "dose_class": "therapeutic_mass",
        "role_classification": "active_scorable",
        "scoreable_identity": True,
        "quantity": 200,
        "unit": "mg",
        "raw_source_path": "ingredientRows[0]",
    }
    product = {
        "dsld_id": dsld_id,
        "product_name": f"Fixture {dsld_id}",
        "supplement_taxonomy": {
            "primary_type": "single_mineral",
            "percentile_category": "single_mineral",
        },
        "ingredient_quality_data": {
            "ingredients": [row],
            "ingredients_scorable": [row],
        },
    }
    return assemble_scored_artifact(product, v4_result)


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
    scored_live = _canned_v4(status="scored", quality_100=88.0, verdict="SAFE", tier="Strong")
    scored_live["quality_score_cap_v4"] = {
        "id": "generic_astaxanthin_single",
        "cap": 85.0,
        "applied": True,
    }
    s1 = _artifact_from_canned("999", scored_live)
    s2 = _artifact_from_canned(
        "888",
        _canned_v4(status="suppressed_safety", quality_100=None, verdict="BLOCKED",
                   tier=None, safety_verdict="BLOCKED",
                   blocking_reason="banned_ingredient", suppressed_reason="banned_ingredient"),
    )
    s3 = _artifact_from_canned(
        "777", _canned_v4(status="not_scored", quality_100=None, verdict="NOT_SCORED", tier=None)
    )
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

    # The real scorer always emits all six pillars for a scored product; the
    # shared _canned_v4 only carries two, so build a six-pillar result here.
    scored_v4 = _canned_v4(status="scored", quality_100=88.0)
    scored_v4["quality_pillars_v4"] = {
        "formulation": {"score": 18.0, "max": 20},
        "dose": {"score": 18.0, "max": 20},
        "evidence": {"score": 16.0, "max": 20},
        "transparency": {"score": 13.0, "max": 15},
        "verification": {"score": 13.0, "max": 15},
        "safety_hygiene": {"score": 10.0, "max": 10},
    }
    s1 = _artifact_from_canned("999", scored_v4)
    s2 = _artifact_from_canned(
        "888",
        _canned_v4(status="suppressed_safety", quality_100=None, verdict="BLOCKED",
                   tier=None, safety_verdict="BLOCKED",
                   blocking_reason="banned_ingredient", suppressed_reason="banned_ingredient"),
    )

    with tempfile.TemporaryDirectory() as tmp:
        _result, out = _run_build(tmp, [e1, e2], [s1, s2])
        rows = _core_rows(out, ["dsld_id"] + pillar_cols)

        # Scored: all six columns populated, each within [0, max], matching scores.
        scored = rows["999"]
        assert scored["pillar_formulation_v4"] == 18.0
        assert scored["pillar_dose_v4"] == 18.0
        assert scored["pillar_evidence_v4"] == 16.0
        assert scored["pillar_transparency_v4"] == 13.0
        assert scored["pillar_verification_v4"] == 13.0
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
    s1 = _artifact_from_canned(
        "999", _canned_v4(status="scored", quality_100=70.0, verdict="SAFE", tier="Acceptable")
    )
    s2 = _artifact_from_canned(
        "888", _canned_v4(status="suppressed_safety", quality_100=None, verdict="BLOCKED",
                          tier=None, safety_verdict="BLOCKED", blocking_reason="banned_ingredient")
    )
    with tempfile.TemporaryDirectory() as tmp:
        _result, out = _run_build(tmp, [e_scored, e_blocked], [s1, s2])
        rows = _core_rows(out, ["dsld_id"])
        # The scored product wins the UPC group; the BLOCKED twin is deduped away.
        assert set(rows) == {"999"}


def test_build_always_stamps_v4_score_model(monkeypatch):
    e = make_enriched()
    s = _artifact_from_canned(
        "999", _canned_v4(status="scored", quality_100=75.0, verdict="SAFE", tier="Strong")
    )
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
    # v4 *scoring* gate did NOT block it — it returns a finite scored result
    # (the real divergence: v4's gate is narrower than the export banned signal).
    s = _artifact_from_canned(
        "999", _canned_v4(status="scored", quality_100=70.5, verdict="SAFE", tier="Acceptable")
    )
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
    scored = [
        _artifact_from_canned(d, _canned_v4()) for d in ("999", "888", "777")
    ]
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


# ---------------------------------------------------------------------------
# Label-native identity export (Task 5): the final blob presents the label-first
# identity the enricher resolved, never the canonical standard_name, and carries
# the identity audit trail. 179681 is the pinned regression: the source text is
# the wrong "Docosahexaenoic Acid Ethyl Ester" but structured label evidence
# repairs it to EPA / as Ethyl Esters with canonical epa.
# ---------------------------------------------------------------------------


def _enriched_with_label_identity(dsld_id="179681", disposition="repaired"):
    enriched = make_enriched()
    enriched["dsld_id"] = dsld_id
    enriched["activeIngredients"] = [
        {
            "name": "EPA",
            "standardName": "Eicosapentaenoic Acid",
            "raw_source_text": "Docosahexaenoic Acid Ethyl Ester",
            "forms": [{"name": "Ethyl Esters"}],
            "quantity": 360,
            "unit": "mg",
            "canonical_id": "epa",
        }
    ]
    enriched["ingredient_quality_data"] = {
        "ingredients": [
            {
                "raw_source_text": "Docosahexaenoic Acid Ethyl Ester",
                "name": "EPA",
                "standard_name": "Eicosapentaenoic Acid",
                "canonical_id": "epa",
                "canonical_id_before": "dha",
                "canonical_id_after": "epa",
                "identity_disposition": disposition,
                "source_label_key": "epa|as ethyl esters",
                "source_label_name": "EPA",
                "source_label_form": "as Ethyl Esters",
                "label_display_name": "EPA",
                "label_display_form": "as Ethyl Esters",
                "identity_resolution_rationale": (
                    "Unambiguous structured line identity replaced 'dha' with 'epa'."
                ),
                "identity_taxonomy_coherent": True,
                "scoreable_identity": True,
                "mapped": True,
                "matched_form": "ethyl esters",
                "bio_score": 20,
            }
        ]
    }
    return enriched


def test_label_identity_display_label_prefers_label_over_canonical():
    ingredient = build_detail_blob(_enriched_with_label_identity(), make_scored())["ingredients"][0]
    assert ingredient["display_label"] == "EPA"
    # The canonical standard_name must never become the display.
    assert ingredient["display_label"] != "Eicosapentaenoic Acid"
    assert ingredient["canonical_id"] == "epa"


def test_label_identity_display_form_prefers_label_display_form():
    ingredient = build_detail_blob(_enriched_with_label_identity(), make_scored())["ingredients"][0]
    assert ingredient["display_form_label"] == "as Ethyl Esters"
    assert ingredient["form_status"] == "known"


def test_label_identity_emits_audit_trail_fields():
    ingredient = build_detail_blob(_enriched_with_label_identity(), make_scored())["ingredients"][0]
    assert ingredient["identity_disposition"] == "repaired"
    assert ingredient["canonical_id_before"] == "dha"
    assert ingredient["source_label_key"] == "epa|as ethyl esters"
    assert ingredient["label_display_name"] == "EPA"
    assert ingredient["label_display_form"] == "as Ethyl Esters"
    assert ingredient["identity_resolution_rationale"]


def test_label_identity_179681_locks_epa_display_with_epa_canonical():
    blob = build_detail_blob(_enriched_with_label_identity("179681"), make_scored())
    ingredient = blob["ingredients"][0]
    assert ingredient["display_label"] == "EPA"
    assert ingredient["display_form_label"] == "as Ethyl Esters"
    assert ingredient["canonical_id"] == "epa"
    # Canonical identity is retained on its own field, never as the display.
    assert ingredient["standard_name"] == "Eicosapentaenoic Acid"


def test_label_identity_conflict_row_never_borrows_canonical_standard_name():
    from build_final_db import _compute_display_label

    ing = {"name": "", "raw_source_text": "Marine Lipid Concentrate", "standard_name": "Eicosapentaenoic Acid"}
    match = {
        "identity_disposition": "identity_conflict",
        "label_display_name": "Marine Lipid Concentrate",
        "source_label_name": "Marine Lipid Concentrate",
    }
    assert _compute_display_label(ing, match) == "Marine Lipid Concentrate"


def test_label_identity_missing_display_never_uses_canonical_standard_name():
    from build_final_db import _compute_display_label

    ing = {"name": "", "raw_source_text": "", "standard_name": "Eicosapentaenoic Acid"}
    match = {"identity_disposition": "missing_display_label", "label_display_name": None, "source_label_name": None}
    result = _compute_display_label(ing, match)
    assert result != "Eicosapentaenoic Acid"
    assert result == ""


def test_label_identity_matches_duplicate_raw_rows_by_source_path():
    enriched = make_enriched()
    enriched["activeIngredients"] = [
        {
            "name": "Omega-3",
            "raw_source_text": "Omega-3",
            "raw_source_path": "activeIngredients[0]",
            "quantity": 360,
            "unit": "mg",
        },
        {
            "name": "Omega-3",
            "raw_source_text": "Omega-3",
            "raw_source_path": "activeIngredients[1]",
            "quantity": 300,
            "unit": "mg",
        },
    ]
    enriched["ingredient_quality_data"] = {
        "ingredients": [
            {
                "raw_source_text": "Omega-3",
                "raw_source_path": "activeIngredients[0]",
                "name": "EPA",
                "standard_name": "Eicosapentaenoic Acid",
                "canonical_id": "epa",
                "identity_disposition": "clean",
                "source_label_key": "label:epa:omega-3:360:mg",
                "source_label_name": "EPA",
                "label_display_name": "EPA",
                "label_display_form": "as Ethyl Esters",
                "matched_form": "ethyl esters",
                "mapped": True,
            },
            {
                "raw_source_text": "Omega-3",
                "raw_source_path": "activeIngredients[1]",
                "name": "DHA",
                "standard_name": "Docosahexaenoic Acid",
                "canonical_id": "dha",
                "identity_disposition": "clean",
                "source_label_key": "label:dha:omega-3:300:mg",
                "source_label_name": "DHA",
                "label_display_name": "DHA",
                "label_display_form": "as Ethyl Esters",
                "matched_form": "ethyl esters",
                "mapped": True,
            },
        ]
    }

    ingredients = build_detail_blob(enriched, make_scored())["ingredients"]

    assert [(item["display_label"], item["canonical_id"]) for item in ingredients] == [
        ("EPA", "epa"),
        ("DHA", "dha"),
    ]


def test_export_contract_rejects_unresolved_identity_before_blob_publication():
    enriched = _enriched_with_label_identity(disposition="identity_conflict")
    enriched["ingredient_quality_data"]["ingredients"][0]["canonical_id_after"] = None
    enriched["ingredient_quality_data"]["ingredients"][0]["canonical_id"] = None

    issues = validate_export_contract(enriched, make_scored())

    assert any("identity integrity" in issue for issue in issues)


# ---------------------------------------------------------------------------
# Canonical source-label ledger (Label Truth P0 Task 1)
# ---------------------------------------------------------------------------


def test_cleaner_label_ledger_prefers_reviewed_correction_over_source_snapshot():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    normalizer._label_corrections_by_dsld_id = {
        "LABEL-CORRECTION": {
            "raw_ingredient_text": "Magneisum",
            "corrected_ingredient_text": "Magnesium",
            "provenance_tag": "reviewed_label_correction",
        },
    }
    normalized = normalizer.normalize_product({
        "id": "LABEL-CORRECTION",
        "fullName": "Reviewed Label Correction",
        "brandName": "Test Brand",
        "ingredientRows": [
            {
                "order": 1,
                "name": "Magneisum",
                "ingredientGroup": "Magnesium",
                "quantity": [{"quantity": 100, "unit": "mg"}],
            },
        ],
        "otheringredients": {"ingredients": []},
    })

    assert normalized["display_ingredients"][0]["label_display_name"] == "Magnesium"
    assert normalized["display_ingredients"][0]["raw_source_text"] == "Magneisum"
    assert normalized["activeIngredients"][0]["source_correction"] == {
        "provenance_tag": "reviewed_label_correction",
        "original_ingredient_text": "Magneisum",
        "corrected_ingredient_text": "Magnesium",
    }


def test_cleaner_correction_updates_nested_parent_lineage_and_allows_folate_fold():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    normalizer._label_corrections_by_dsld_id = {
        "NESTED-LABEL-CORRECTION": {
            "raw_ingredient_text": "Foltae",
            "corrected_ingredient_text": "Folate",
            "provenance_tag": "reviewed_label_correction",
        },
    }
    normalized = normalizer.normalize_product({
        "id": "NESTED-LABEL-CORRECTION",
        "fullName": "Reviewed Nested Label Correction",
        "brandName": "Test Brand",
        "ingredientRows": [
            {
                "order": 1,
                "name": "Foltae",
                "ingredientGroup": "Folate",
                "category": "vitamin",
                "quantity": [{"quantity": 665, "unit": "mcg DFE"}],
                "nestedRows": [
                    {
                        "order": 2,
                        "name": "Folic Acid",
                        "ingredientGroup": "Folate",
                        "category": "vitamin",
                        "quantity": [{"quantity": 400, "unit": "mcg"}],
                    },
                ],
            },
        ],
        "otheringredients": {"ingredients": []},
    })

    rows = normalized["display_ingredients"]
    assert len(rows) == 1
    assert rows[0]["label_display_name"] == "Folate"
    assert rows[0]["raw_source_text"] == "Foltae"
    assert rows[0]["parenthetical_dose_text"] == "400 mcg folic acid"
    assert rows[0]["folded_label_components"][0]["label_display_name"] == "Folic Acid"
    assert rows[0]["folded_label_components"][0]["parent_label"] == "Folate"


def test_final_ledger_folds_multi_serving_probiotic_headers_into_one_parent():
    from build_final_db import _fold_probiotic_serving_headers

    ledger = [
        {
            "label_display_name": "Probiotic Blend",
            "raw_source_text": "Probiotic Blend",
            "raw_source_path": "ingredientRows[0]",
            "source_section": "activeIngredients",
            "nested_depth": 0,
            "label_order": 0,
        },
        {
            "label_display_name": "Probiotic Blend",
            "raw_source_text": "Probiotic Blend",
            "raw_source_path": "ingredientRows[1]",
            "source_section": "activeIngredients",
            "nested_depth": 0,
            "label_order": 1,
            "children": ["Bifidobacterium bifidum (Bb-06)"],
        },
        {
            "label_display_name": "Bifidobacterium bifidum (Bb-06)",
            "raw_source_path": "ingredientRows[1].nestedRows[0]",
            "source_section": "activeIngredients",
            "nested_depth": 1,
            "parent_label": "Probiotic Blend",
            "label_order": 2,
        },
        {
            "label_display_name": "Rice Starch",
            "raw_source_path": "otheringredients.ingredients[0]",
            "source_section": "inactiveIngredients",
            "nested_depth": 0,
            "label_order": 3,
        },
    ]
    enriched = {
        "servingSizes": [
            {"order": 1, "normalizedServing": 0.25, "unit": "Gram(s)", "notes": "Ages 1-3 (1/2 scoop)"},
            {"order": 2, "normalizedServing": 0.5, "unit": "Gram(s)", "notes": "Ages 4 and up (1 scoop)"},
        ],
        "activeIngredients": [
            {
                "raw_source_path": "ingredientRows[0]",
                "notes": "Probiotic Blend Note: (providing:) (1.12 billion CFU)",
                "raw_taxonomy": {"quantityVariants": [{"serving_size_order": 1, "serving_size_quantity": 0.25, "serving_size_unit": "Gram(s)"}]},
            },
            {
                "raw_source_path": "ingredientRows[1]",
                "notes": "Probiotic Blend Note: (providing:) (2.25 billion CFU)",
                "raw_taxonomy": {"quantityVariants": [{"serving_size_order": 2, "serving_size_quantity": 0.5, "serving_size_unit": "Gram(s)"}]},
            },
        ],
        "probiotic_data": {
            "total_billion_count": 2.25,
            "probiotic_blends": [
                {
                    "name": "Probiotic Blend",
                    "raw_source_path": "ingredientRows[1]",
                    "is_blend_header_total": True,
                },
            ],
        },
    }

    rows = _fold_probiotic_serving_headers(enriched, ledger)

    assert [row["label_display_name"] for row in rows] == [
        "Probiotic Blend",
        "Bifidobacterium bifidum (Bb-06)",
        "Rice Starch",
    ]
    assert rows[0]["raw_source_path"] == "ingredientRows[1]"
    assert rows[0]["display_type"] == "structural_container"
    assert rows[0]["exact_dose_text"] == "2.25 billion CFU"
    assert rows[0]["serving_variants"] == [
        {
            "serving_size_order": 1,
            "serving_size_quantity": 0.25,
            "serving_size_unit": "Gram(s)",
            "serving_note": "Ages 1-3 (1/2 scoop)",
            "exact_dose_text": "1.12 billion CFU",
            "is_canonical": False,
        },
        {
            "serving_size_order": 2,
            "serving_size_quantity": 0.5,
            "serving_size_unit": "Gram(s)",
            "serving_note": "Ages 4 and up (1 scoop)",
            "exact_dose_text": "2.25 billion CFU",
            "is_canonical": True,
        },
    ]
    assert rows[0]["folded_label_components"][0]["omission_reason"] == "alternate_serving_variant"


def test_final_ledger_folds_general_audience_servings_without_summing():
    from build_final_db import _fold_general_serving_variants

    ledger = [
        {
            "label_display_name": "Zinc",
            "raw_source_path": "ingredientRows[2]",
            "source_section": "activeIngredients",
            "nested_depth": 0,
            "label_order": 0,
            "exact_dose_text": "22 mg",
            "serving_size_order": 2,
            "serving_size_quantity": 2,
            "serving_size_unit": "Gummy(ies)",
        },
        {
            "label_display_name": "Zinc",
            "raw_source_path": "ingredientRows[6]",
            "source_section": "activeIngredients",
            "nested_depth": 0,
            "label_order": 1,
            "exact_dose_text": "11 mg",
            "serving_size_order": 1,
            "serving_size_quantity": 1,
            "serving_size_unit": "Gummy(ies)",
        },
    ]
    enriched = {
        "servingSizes": [
            {"order": 1, "notes": "Children 9 years of age and older"},
            {"order": 2, "notes": "Adults"},
        ]
    }

    rows = _fold_general_serving_variants(enriched, ledger)

    assert len(rows) == 1
    assert rows[0]["label_display_name"] == "Zinc"
    assert rows[0]["exact_dose_text"] == ""
    assert rows[0]["serving_variants"] == [
        {
            "serving_size_order": 1,
            "serving_size_quantity": 1,
            "serving_size_unit": "Gummy(ies)",
            "serving_note": "Children 9 years of age and older",
            "exact_dose_text": "11 mg",
            "is_canonical": False,
        },
        {
            "serving_size_order": 2,
            "serving_size_quantity": 2,
            "serving_size_unit": "Gummy(ies)",
            "serving_note": "Adults",
            "exact_dose_text": "22 mg",
            "is_canonical": False,
        },
    ]
    assert rows[0]["folded_label_components"][0]["omission_reason"] == "alternate_serving_variant"


def test_final_ledger_does_not_fold_same_name_rows_for_one_serving():
    from build_final_db import _fold_general_serving_variants

    ledger = [
        {
            "label_display_name": "Protease",
            "raw_source_path": "ingredientRows[18]",
            "source_section": "activeIngredients",
            "nested_depth": 0,
            "label_order": 0,
            "exact_dose_text": "3,030 HUT · high pH",
            "serving_size_order": 1,
        },
        {
            "label_display_name": "Protease",
            "raw_source_path": "ingredientRows[19]",
            "source_section": "activeIngredients",
            "nested_depth": 0,
            "label_order": 1,
            "exact_dose_text": "25 SAPU · low pH",
            "serving_size_order": 1,
        },
    ]

    rows = _fold_general_serving_variants(
        {"servingSizes": [{"order": 1, "notes": "Adults"}]},
        ledger,
    )

    assert len(rows) == 2
    assert [row["exact_dose_text"] for row in rows] == [
        "3,030 HUT · high pH",
        "25 SAPU · low pH",
    ]


def test_label_dose_text_normalizes_dsld_units_and_preserves_enzyme_activity():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = object.__new__(EnhancedDSLDNormalizer)

    assert normalizer._exact_label_dose_text(
        {"quantity": [{"quantity": 20, "unit": "Calorie(s)"}]}
    ) == "20 Calories"
    assert normalizer._exact_label_dose_text(
        {"quantity": [{"quantity": 4, "unit": "Gram(s)"}]}
    ) == "4 g"
    assert normalizer._exact_label_dose_text(
        {
            "quantity": [{"quantity": 0, "unit": "NP"}],
            "notes": "Protease Note: (high pH) (3,030 HUT) (Dairy Digesting)",
        }
    ) == "3,030 HUT · high pH"


def test_warning_dedup_merges_active_and_inactive_producers_for_one_hazard():
    from build_final_db import _dedup_warnings

    rows = _dedup_warnings(
        [
            {
                "type": "banned_substance",
                "source": "inactive_ingredient_resolver",
                "matched_rule_id": "BANNED_DHEA",
                "ingredient_name": "DHEA",
                "severity": "caution",
                "display_mode_default": "critical",
                "title": "High-risk hormonal ingredient",
                "sources": ["https://example.test/inactive"],
            },
            {
                "type": "high_risk_ingredient",
                "source": "banned_recalled",
                "matched_rule_id": "BANNED_DHEA",
                "ingredient_name": "DHEA",
                "severity": "avoid",
                "display_mode_default": "critical",
                "alert_headline": "Avoid DHEA",
                "alert_body": "DHEA has material hormonal activity.",
                "sources": ["https://example.test/active"],
            },
        ]
    )

    assert len(rows) == 1
    assert rows[0]["severity"] == "avoid"
    assert rows[0]["alert_headline"] == "Avoid DHEA"
    assert rows[0]["sources"] == [
        "https://example.test/active",
        "https://example.test/inactive",
    ]
    assert rows[0]["source_producers"] == [
        "banned_recalled",
        "inactive_ingredient_resolver",
    ]


def test_final_ledger_keeps_distinct_same_name_probiotic_headers():
    from build_final_db import _fold_probiotic_serving_headers

    ledger = [
        {
            "label_display_name": "Probiotic Blend",
            "raw_source_path": "ingredientRows[0]",
            "source_section": "activeIngredients",
            "nested_depth": 0,
            "label_order": 0,
        },
        {
            "label_display_name": "Probiotic Blend",
            "raw_source_path": "ingredientRows[1]",
            "source_section": "activeIngredients",
            "nested_depth": 0,
            "label_order": 1,
        },
    ]
    enriched = {
        "probiotic_data": {
            "probiotic_blends": [
                {"name": "Probiotic Blend", "raw_source_path": "ingredientRows[0]", "is_blend_header_total": True},
                {"name": "Probiotic Blend", "raw_source_path": "ingredientRows[1]", "is_blend_header_total": True},
            ],
        },
    }

    rows = _fold_probiotic_serving_headers(enriched, ledger)

    assert len(rows) == 2


def test_cleaner_label_ledger_preserves_omega_order_hierarchy_and_exact_doses():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalized = EnhancedDSLDNormalizer().normalize_product({
        "id": "LABEL-LEDGER-OMEGA",
        "fullName": "Label Ledger Omega",
        "brandName": "Test Brand",
        "ingredientRows": [
            {
                "order": 1,
                "name": "Fish Oil",
                "ingredientGroup": "Fish Oil",
                "quantity": [{"quantity": 2400, "unit": "mg"}],
                "forms": [{"name": "Fish Oil"}],
                "nestedRows": [
                    {
                        "order": 2,
                        "name": "Total Omega-3 Fatty Acids",
                        "ingredientGroup": "Omega-3",
                        "category": "fatty acid",
                        "quantity": [{"quantity": 720, "unit": "mg"}],
                        "nestedRows": [
                            {
                                "order": 3,
                                "name": "EPA",
                                "ingredientGroup": "EPA",
                                "category": "fatty acid",
                                "quantity": [{"quantity": 360, "unit": "mg"}],
                            },
                            {
                                "order": 4,
                                "name": "DHA",
                                "ingredientGroup": "DHA",
                                "category": "fatty acid",
                                "quantity": [{"quantity": 240, "unit": "mg"}],
                            },
                            {
                                "order": 5,
                                "name": "Other Omega-3 Fatty Acids",
                                "ingredientGroup": "Omega-3",
                                "category": "fatty acid",
                                "quantity": [{"quantity": 120, "unit": "mg"}],
                            },
                        ],
                    },
                ],
            },
        ],
        "otheringredients": {"ingredients": []},
    })

    rows = normalized["display_ingredients"]
    assert [row["label_display_name"] for row in rows] == [
        "Fish Oil",
        "Total Omega-3 Fatty Acids",
        "EPA",
        "DHA",
        "Other Omega-3 Fatty Acids",
    ]
    assert [row["label_order"] for row in rows] == [0, 1, 2, 3, 4]
    assert [row["nested_depth"] for row in rows] == [0, 1, 2, 2, 2]
    assert [row["parent_label"] for row in rows] == [
        None,
        "Fish Oil",
        "Total Omega-3 Fatty Acids",
        "Total Omega-3 Fatty Acids",
        "Total Omega-3 Fatty Acids",
    ]
    assert [row["exact_dose_text"] for row in rows] == [
        "2,400 mg",
        "720 mg",
        "360 mg",
        "240 mg",
        "120 mg",
    ]
    assert [row["score_included"] for row in rows] == [True, False, True, True, False]
    assert [row["is_label_context"] for row in rows] == [False, True, False, False, True]
    assert len({row["raw_source_path"] for row in rows}) == 5
    assert rows[0].get("label_display_form") is None
    assert rows[0]["form_display_state"] == "not_disclosed"


def test_cleaner_keeps_same_name_display_rows_from_distinct_parent_branches():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalized = EnhancedDSLDNormalizer().normalize_product({
        "id": "REPEATED-OMEGA-TOTALS",
        "fullName": "Fish and Krill Oil",
        "brandName": "Test Brand",
        "ingredientRows": [
            {
                "order": 1,
                "name": "Fish Oil",
                "ingredientGroup": "Fish Oil",
                "quantity": [{"quantity": 2400, "unit": "mg"}],
                "nestedRows": [
                    {
                        "order": 2,
                        "name": "Total Omega-3 Fatty Acids",
                        "ingredientGroup": "Omega-3",
                        "category": "fatty acid",
                        "quantity": [{"quantity": 720, "unit": "mg"}],
                        "nestedRows": [
                            {
                                "order": 3,
                                "name": "EPA",
                                "ingredientGroup": "EPA",
                                "category": "fatty acid",
                                "quantity": [{"quantity": 360, "unit": "mg"}],
                            },
                        ],
                    },
                ],
            },
            {
                "order": 4,
                "name": "Krill Oil",
                "ingredientGroup": "Krill Oil",
                "quantity": [{"quantity": 1000, "unit": "mg"}],
                "nestedRows": [
                    {
                        "order": 5,
                        "name": "Total Omega-3 Fatty Acids",
                        "ingredientGroup": "Omega-3",
                        "category": "fatty acid",
                        "quantity": [{"quantity": 500, "unit": "mg"}],
                        "nestedRows": [
                            {
                                "order": 6,
                                "name": "DHA",
                                "ingredientGroup": "DHA",
                                "category": "fatty acid",
                                "quantity": [{"quantity": 250, "unit": "mg"}],
                            },
                        ],
                    },
                ],
            },
        ],
        "otheringredients": {"ingredients": []},
    })

    totals = [
        row
        for row in normalized["display_ingredients"]
        if row["label_display_name"] == "Total Omega-3 Fatty Acids"
    ]
    assert [
        (row["parent_label"], row["raw_source_path"], row["exact_dose_text"])
        for row in totals
    ] == [
        ("Fish Oil", "ingredientRows[0].nestedRows[0]", "720 mg"),
        ("Krill Oil", "ingredientRows[1].nestedRows[0]", "500 mg"),
    ]


def test_cleaner_mixed_path_and_pathless_candidates_claim_distinct_source_rows():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    normalizer._display_source_rows = [
        {
            "raw_source_text": "Total Omega-3 Fatty Acids",
            "label_display_name": "Total Omega-3 Fatty Acids",
            "raw_source_path": "ingredientRows[0]",
            "source_section": "activeIngredients",
            "label_order": 0,
            "nested_depth": 0,
            "parent_label": "Fish Oil",
            "exact_dose_text": "100 mg",
        },
        {
            "raw_source_text": "Total Omega-3 Fatty Acids",
            "label_display_name": "Total Omega-3 Fatty Acids",
            "raw_source_path": "ingredientRows[1]",
            "source_section": "activeIngredients",
            "label_order": 1,
            "nested_depth": 0,
            "parent_label": "Krill Oil",
            "exact_dose_text": "200 mg",
        },
    ]
    normalizer._display_ingredients_buffer = [
        {
            "raw_source_text": "Total Omega-3 Fatty Acids",
            "display_name": "Total Omega-3 Fatty Acids",
            "source_section": "activeIngredients",
            "display_type": "summary_wrapper",
            "resolution_type": "suppressed_parent",
            "score_included": False,
            "children": [],
        },
    ]

    rows = normalizer._build_display_ingredients(
        [
            {
                "name": "Total Omega-3 Fatty Acids",
                "raw_source_text": "Total Omega-3 Fatty Acids",
                "raw_source_path": "ingredientRows[0]",
                "quantity": 100,
                "unit": "mg",
                "canonical_id": "omega_3_fatty_acids",
            },
        ],
        [],
    )

    assert [
        (
            row["raw_source_path"],
            row["exact_dose_text"],
            row["score_included"],
        )
        for row in rows
    ] == [
        ("ingredientRows[0]", "100 mg", True),
        ("ingredientRows[1]", "200 mg", False),
    ]


def test_cleaner_merges_annotations_for_same_group_blend_source_occurrence():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalized = EnhancedDSLDNormalizer().normalize_product({
        "id": "WELLBODY-ONE-SOURCE",
        "fullName": "WellBody Blend",
        "brandName": "Test Brand",
        "ingredientRows": [
            {
                "order": 1,
                "name": "WellBody 365",
                "ingredientGroup": "Blend (Mineral)",
                "category": "blend",
                "quantity": [{"quantity": 500, "unit": "mg"}],
                "nestedRows": [
                    {
                        "order": 2,
                        "name": "Magnesium",
                        "ingredientGroup": "Magnesium",
                        "category": "mineral",
                        "quantity": [{"quantity": 100, "unit": "mg"}],
                    },
                ],
            },
        ],
        "otheringredients": {"ingredients": []},
    })

    wellbody_rows = [
        row
        for row in normalized["display_ingredients"]
        if row["label_display_name"] == "WellBody 365"
    ]
    assert len(wellbody_rows) == 1
    assert wellbody_rows[0]["raw_source_path"] == "ingredientRows[0]"
    assert wellbody_rows[0]["exact_dose_text"] == "500 mg"


def test_cleaner_preserves_distinct_inactive_string_form_siblings():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalized = EnhancedDSLDNormalizer().normalize_product({
        "id": "CAPSULE-STRING-FORMS",
        "fullName": "Capsule String Forms",
        "brandName": "Test Brand",
        "ingredientRows": [],
        "otheringredients": {
            "ingredients": [
                {
                    "order": 1,
                    "name": "Capsule Ingredients",
                    "forms": ["Gelatin", "Glycerin"],
                },
            ],
        },
    })

    other_rows = [
        row
        for row in normalized["display_ingredients"]
        if row["source_section"] == "inactiveIngredients"
    ]
    assert [row["label_display_name"] for row in other_rows] == [
        "Gelatin",
        "Glycerin",
    ]
    assert len({row["raw_source_path"] for row in other_rows}) == 2
    parent_source_path = "otheringredients.ingredients[0]"
    assert [
        (
            row["nested_depth"],
            row["parent_label"],
            row["parent_source_path"],
        )
        for row in other_rows
    ] == [
        (1, "Capsule Ingredients", parent_source_path),
        (1, "Capsule Ingredients", parent_source_path),
    ]
    assert normalized["label_ledger_omissions"] == [
        {
            "raw_source_path": parent_source_path,
            "raw_source_text": "Capsule Ingredients",
            "omission_reason": "decorative_or_header_text",
        },
    ]

    blob = build_detail_blob(normalized, make_scored())
    final_other_rows = [
        row
        for row in blob["display_ingredients"]
        if row["source_section"] == "inactiveIngredients"
    ]
    assert [
        (
            row["label_display_name"],
            row["nested_depth"],
            row["parent_label"],
            row["parent_source_path"],
        )
        for row in final_other_rows
    ] == [
        ("Gelatin", 1, "Capsule Ingredients", parent_source_path),
        ("Glycerin", 1, "Capsule Ingredients", parent_source_path),
    ]
    assert blob["label_ledger_omissions"] == normalized["label_ledger_omissions"]


def test_cleaner_audits_empty_structural_header_omission():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalized = EnhancedDSLDNormalizer().normalize_product({
        "id": "EMPTY-STRUCTURAL-HEADER",
        "fullName": "Empty Structural Header",
        "brandName": "Test Brand",
        "ingredientRows": [],
        "otheringredients": {
            "ingredients": [
                {
                    "order": 1,
                    "name": "Less than 2% of:",
                    "forms": [],
                },
            ],
        },
    })

    assert all(
        row["label_display_name"] != "Less than 2% of:"
        for row in normalized["display_ingredients"]
    )
    expected_omissions = [
        {
            "raw_source_path": "otheringredients.ingredients[0]",
            "raw_source_text": "Less than 2% of:",
            "omission_reason": "decorative_or_header_text",
        },
    ]
    assert normalized["label_ledger_omissions"] == expected_omissions

    blob = build_detail_blob(normalized, make_scored())
    assert all(
        row["label_display_name"] != "Less than 2% of:"
        for row in blob["display_ingredients"]
    )
    assert blob["label_ledger_omissions"] == expected_omissions


def test_cleaner_audits_blank_active_and_other_source_occurrences():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalized = EnhancedDSLDNormalizer().normalize_product({
        "id": "BLANK-SOURCE-OCCURRENCES",
        "fullName": "Blank Source Occurrences",
        "brandName": "Test Brand",
        "ingredientRows": [
            {
                "order": 1,
                "name": "",
            },
        ],
        "otheringredients": {
            "ingredients": [
                {
                    "order": 2,
                    "name": "   ",
                },
            ],
        },
    })

    assert normalized["display_ingredients"] == []
    expected_omissions = [
        {
            "raw_source_path": "ingredientRows[0]",
            "raw_source_text": "",
            "omission_reason": "empty_source_text",
        },
        {
            "raw_source_path": "otheringredients.ingredients[0]",
            "raw_source_text": "   ",
            "omission_reason": "empty_source_text",
        },
    ]
    assert normalized["label_ledger_omissions"] == expected_omissions

    blob = build_detail_blob(normalized, make_scored())
    assert blob["display_ingredients"] == []
    assert blob["label_ledger_omissions"] == expected_omissions


def _omega_label_ledger_enriched():
    enriched = make_enriched()
    enriched["harmful_additives"] = []
    enriched["allergen_hits"] = []
    enriched["activeIngredients"] = [
        {
            "name": "Fish Oil",
            "raw_source_text": "Fish Oil",
            "raw_source_path": "ingredientRows[0]",
            "quantity": 2400,
            "unit": "mg",
            "canonical_id": "fish_oil",
        },
        {
            "name": "EPA",
            "raw_source_text": "EPA",
            "raw_source_path": "ingredientRows[0].nestedRows[0].nestedRows[0]",
            "quantity": 360,
            "unit": "mg",
            "canonical_id": "epa",
            "parentBlend": "Total Omega-3 Fatty Acids",
            "isNestedIngredient": True,
        },
        {
            "name": "DHA",
            "raw_source_text": "DHA",
            "raw_source_path": "ingredientRows[0].nestedRows[0].nestedRows[1]",
            "quantity": 240,
            "unit": "mg",
            "canonical_id": "dha",
            "parentBlend": "Total Omega-3 Fatty Acids",
            "isNestedIngredient": True,
        },
    ]
    enriched["ingredient_quality_data"] = {
        "ingredients": [
            {
                "name": "Fish Oil",
                "raw_source_text": "Fish Oil",
                "raw_source_path": "ingredientRows[0]",
                "standard_name": "Fish Oil",
                "canonical_id": "fish_oil",
                "parent_key": "fish_oil",
                "matched_form": "fish oil",
                "mapped": True,
                "bio_score": 8,
            },
            {
                "name": "EPA",
                "raw_source_text": "EPA",
                "raw_source_path": "ingredientRows[0].nestedRows[0].nestedRows[0]",
                "standard_name": "Eicosapentaenoic Acid",
                "canonical_id": "epa",
                "parent_key": "epa",
                "matched_form": "standard",
                "mapped": True,
                "bio_score": 10,
            },
            {
                "name": "DHA",
                "raw_source_text": "DHA",
                "raw_source_path": "ingredientRows[0].nestedRows[0].nestedRows[1]",
                "standard_name": "Docosahexaenoic Acid",
                "canonical_id": "dha",
                "parent_key": "dha",
                "matched_form": "standard",
                "mapped": True,
                "bio_score": 10,
            },
        ],
    }
    names = [
        "Fish Oil",
        "Total Omega-3 Fatty Acids",
        "EPA",
        "DHA",
        "Other Omega-3 Fatty Acids",
    ]
    doses = ["2,400 mg", "720 mg", "360 mg", "240 mg", "120 mg"]
    depths = [0, 1, 2, 2, 2]
    parents = [
        None,
        "Fish Oil",
        "Total Omega-3 Fatty Acids",
        "Total Omega-3 Fatty Acids",
        "Total Omega-3 Fatty Acids",
    ]
    score_included = [True, False, True, True, False]
    enriched["display_ingredients"] = [
        {
            "label_display_name": name,
            "raw_source_text": name,
            "raw_source_path": f"label[{index}]",
            "label_order": index,
            "nested_depth": depths[index],
            "parent_label": parents[index],
            "exact_dose_text": doses[index],
            "score_included": score_included[index],
            "is_label_context": not score_included[index],
            "display_disposition": "scored" if score_included[index] else "label_context",
        }
        for index, name in enumerate(names)
    ]
    enriched["display_ingredients"][0]["label_display_form"] = "Fish Oil"
    enriched["display_ingredients"][0]["form_display_state"] = "assessed"
    return enriched


def test_final_blob_uses_label_ledger_without_promoting_context_into_analysis():
    blob = build_detail_blob(_omega_label_ledger_enriched(), make_scored())
    rows = blob["display_ingredients"]

    assert [row["label_display_name"] for row in rows] == [
        "Fish Oil",
        "Total Omega-3 Fatty Acids",
        "EPA",
        "DHA",
        "Other Omega-3 Fatty Acids",
    ]
    assert [row["exact_dose_text"] for row in rows] == [
        "2,400 mg",
        "720 mg",
        "360 mg",
        "240 mg",
        "120 mg",
    ]
    assert [row["score_included"] for row in rows] == [True, False, True, True, False]
    assert [row["is_label_context"] for row in rows] == [False, True, False, False, True]
    assert len(rows) == len({row["ledger_fingerprint"] for row in rows})
    assert {row["display_label"] for row in blob["ingredients"]} == {"Fish Oil", "EPA", "DHA"}
    assert rows[1]["analysis"] is None
    assert rows[4]["analysis"] is None
    assert rows[0]["analysis"] == {
        "canonical_id": "fish_oil",
        "display_label": "Fish Oil",
        "form_display_state": "not_disclosed",
        "identity_integrity_state": "clean",
        "display_form_label": None,
        "standard_name": "Fish Oil",
        "bio_score": 8.0,
        "quantity": 2400.0,
        "unit": "mg",
        "below_clinical_dose": False,
        "is_safety_concern": False,
    }
    assert rows[2]["analysis"]["bio_score"] == 10.0
    assert rows[2]["analysis"]["quantity"] == 360.0
    assert rows[3]["analysis"]["quantity"] == 240.0
    assert rows[0].get("label_display_form") is None
    assert rows[0]["form_display_state"] == "not_disclosed"

    fish_oil = next(row for row in blob["ingredients"] if row["display_label"] == "Fish Oil")
    assert fish_oil["display_form_label"] is None
    assert fish_oil["form_status"] == "unknown"


def test_final_ledger_uses_unmapped_analysis_over_stale_assessed_form_state():
    from build_final_db import _build_canonical_label_ledger

    rows = _build_canonical_label_ledger(
        [
            {
                "label_display_name": "Magnesium",
                "label_display_form": "as Citrate",
                "form_display_state": "assessed",
                "raw_source_text": "Magnesium",
                "raw_source_path": "ingredientRows[0]",
                "label_order": 0,
                "nested_depth": 0,
                "exact_dose_text": "100 mg",
                "score_included": True,
                "display_disposition": "scored",
                "identity_integrity_state": "clean",
            },
        ],
        [
            {
                "raw_source_text": "Magnesium",
                "raw_source_path": "ingredientRows[0]",
                "display_label": "Magnesium",
                "display_form_label": "as Citrate",
                "form_match_status": "unmapped",
                "canonical_id": "magnesium",
                "identity_disposition": "clean",
            },
        ],
        [],
    )

    assert rows[0]["label_display_form"] == "as Citrate"
    assert rows[0]["form_display_state"] == "listed_not_assessed"
    assert rows[0]["analysis"]["form_display_state"] == "listed_not_assessed"


def test_final_ledger_preserves_vitamin_totals_with_nested_label_components():
    from build_final_db import _build_canonical_label_ledger

    source_rows = [
        ("Vitamin A", "1.05 mg", 0, None),
        ("Beta-Carotene", "450 mcg", 1, "Vitamin A"),
        ("Vitamin A Palmitate", "600 mcg", 1, "Vitamin A"),
        ("Vitamin K", "400 mcg", 0, None),
        ("Vitamin K1", "200 mcg", 1, "Vitamin K"),
        ("Vitamin K2", "200 mcg", 1, "Vitamin K"),
    ]
    display_rows = [
        {
            "raw_source_text": name,
            "display_name": name,
            "raw_source_path": f"ingredientRows[{index}]",
            "label_order": index,
            "nested_depth": depth,
            "parent_label": parent,
            "exact_dose_text": dose,
            "source_section": "activeIngredients",
            "score_included": True,
        }
        for index, (name, dose, depth, parent) in enumerate(source_rows)
    ]
    analysis_rows = [
        {
            "raw_source_text": name,
            "raw_source_path": f"ingredientRows[{index}]",
            "display_label": name,
            "display_dose_label": dose,
            "canonical_id": "vitamin_a" if index < 3 else "vitamin_k",
            "identity_disposition": "clean",
        }
        for index, (name, dose, _depth, _parent) in enumerate(source_rows)
    ]

    rows = _build_canonical_label_ledger(display_rows, analysis_rows, [])

    assert [row["label_display_name"] for row in rows] == [
        name for name, _dose, _depth, _parent in source_rows
    ]
    assert [row["nested_depth"] for row in rows] == [0, 1, 1, 0, 1, 1]
    assert [row["parent_label"] for row in rows] == [
        None,
        "Vitamin A",
        "Vitamin A",
        None,
        "Vitamin K",
        "Vitamin K",
    ]


def test_form_contract_does_not_treat_canonical_standard_name_as_label_identity():
    from build_final_db import _compute_form_contract

    contract = _compute_form_contract(
        {
            "name": "Magnesium",
            "raw_source_text": "Magnesium",
            "forms": [{"name": "Magnesium Citrate"}],
        },
        {
            "standard_name": "Magnesium Citrate",
            "matched_form": "magnesium citrate",
            "identity_disposition": "clean",
        },
    )

    assert contract["display_form_label"] == "Magnesium Citrate"
    assert contract["form_status"] == "known"


def test_final_blob_folds_folate_dfe_equivalence_into_one_logical_label_row():
    enriched = make_enriched()
    enriched["harmful_additives"] = []
    enriched["allergen_hits"] = []
    enriched["activeIngredients"] = [
        {
            "name": "Folate",
            "raw_source_text": "Folate",
            "raw_source_path": "ingredientRows[0]",
            "quantity": 665,
            "unit": "mcg DFE",
            "canonical_id": "vitamin_b9_folate",
        },
        {
            "name": "Folic Acid",
            "raw_source_text": "Folic Acid",
            "raw_source_path": "ingredientRows[0].nestedRows[0]",
            "quantity": 400,
            "unit": "mcg",
            "canonical_id": "vitamin_b9_folate",
            "parentBlend": "Folate",
            "isNestedIngredient": True,
        },
    ]
    enriched["ingredient_quality_data"] = {
        "ingredients": [
            {
                "name": row["name"],
                "raw_source_text": row["raw_source_text"],
                "raw_source_path": row["raw_source_path"],
                "standard_name": "Folate",
                "canonical_id": "vitamin_b9_folate",
                "parent_key": "vitamin_b9_folate",
                "matched_form": "folic acid" if row["name"] == "Folic Acid" else "standard",
                "mapped": True,
            }
            for row in enriched["activeIngredients"]
        ],
    }
    enriched["display_ingredients"] = [
        {
            "label_display_name": "Folate",
            "raw_source_text": "Folate",
            "raw_source_path": "ingredientRows[0]",
            "label_order": 0,
            "nested_depth": 0,
            "parent_label": None,
            "exact_dose_text": "665 mcg DFE",
            "score_included": False,
            "is_label_context": True,
            "display_disposition": "label_context",
            "canonical_id": "vitamin_b9_folate",
        },
        {
            "label_display_name": "Folic Acid",
            "raw_source_text": "Folic Acid",
            "raw_source_path": "ingredientRows[0].nestedRows[0]",
            "label_order": 1,
            "nested_depth": 1,
            "parent_label": "Folate",
            "exact_dose_text": "400 mcg",
            "score_included": True,
            "is_label_context": False,
            "display_disposition": "scored",
            "canonical_id": "vitamin_b9_folate",
        },
    ]

    rows = build_detail_blob(enriched, make_scored())["display_ingredients"]

    assert len(rows) == 1
    assert rows[0]["label_display_name"] == "Folate"
    assert rows[0]["exact_dose_text"] == "665 mcg DFE"
    assert rows[0]["parenthetical_dose_text"] == "400 mcg folic acid"
    assert rows[0]["score_included"] is True
    assert rows[0]["is_label_context"] is False
    assert rows[0]["display_disposition"] == "scored"
    assert rows[0]["score_participation_source"] == "Folic Acid"
    assert rows[0]["identity_integrity_state"] != "taxonomy_only"
    assert rows[0]["form_display_state"] != "not_applicable"
    assert rows[0]["analysis"]["identity_integrity_state"] == rows[0]["identity_integrity_state"]
    assert rows[0]["analysis"]["form_display_state"] == rows[0]["form_display_state"]


# ---------------------------------------------------------------------------
# Mandatory label-ledger reconciliation audit (Label Truth P0 Task 2B)
# ---------------------------------------------------------------------------


def test_cleaner_and_final_blob_emit_label_source_inventory_and_complete_audit():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalized = EnhancedDSLDNormalizer().normalize_product({
        "id": "LABEL-AUDIT-FLAT",
        "fullName": "Magnesium Capsule",
        "brandName": "Test Brand",
        "ingredientRows": [
            {
                "order": 1,
                "name": "Magnesium",
                "quantity": [{"quantity": 100, "unit": "mg"}],
            },
        ],
        "otheringredients": {
            "ingredients": [{"order": 2, "name": "Gelatin"}],
        },
    })

    assert normalized["label_source_rows"] == [
        {
            "raw_source_path": "ingredientRows[0]",
            "raw_source_text": "Magnesium",
            "source_section": "activeIngredients",
        },
        {
            "raw_source_path": "otheringredients.ingredients[0]",
            "raw_source_text": "Gelatin",
            "source_section": "inactiveIngredients",
        },
    ]
    assert normalized["label_ledger_audit"] == {
        "support_status": "supported",
        "source_structure": "flat_supplement_facts",
        "meaningful_source_rows": 2,
        "displayed_rows": 2,
        "omitted_rows": 0,
        "completeness_percentage": 100.0,
        "completeness_status": "complete",
    }

    blob = build_detail_blob(normalized, make_scored())
    assert blob["label_source_rows"] == normalized["label_source_rows"]
    assert blob["label_ledger_audit"] == normalized["label_ledger_audit"]


@pytest.mark.parametrize(
    "source_structure,ingredient_rows,other_ingredients",
    [
        (
            "flat_supplement_facts",
            [
                {
                    "name": "Creatine Monohydrate",
                    "quantity": [{"quantity": 5, "unit": "g"}],
                },
            ],
            [],
        ),
        (
            "vitamin_mineral_panel",
            [
                {
                    "name": "Vitamin C",
                    "category": "vitamin",
                    "ingredientGroup": "Vitamin C",
                    "quantity": [{"quantity": 100, "unit": "mg"}],
                },
                {
                    "name": "Magnesium",
                    "category": "mineral",
                    "ingredientGroup": "Magnesium",
                    "quantity": [{"quantity": 50, "unit": "mg"}],
                },
            ],
            [],
        ),
        (
            "omega_parent_component",
            [
                {
                    "name": "Fish Oil",
                    "quantity": [{"quantity": 2400, "unit": "mg"}],
                    "nestedRows": [
                        {
                            "name": "Total Omega-3 Fatty Acids",
                            "quantity": [{"quantity": 720, "unit": "mg"}],
                            "nestedRows": [
                                {
                                    "name": "EPA",
                                    "quantity": [{"quantity": 360, "unit": "mg"}],
                                },
                                {
                                    "name": "DHA",
                                    "quantity": [{"quantity": 240, "unit": "mg"}],
                                },
                            ],
                        },
                    ],
                },
            ],
            [],
        ),
        (
            "folate_dfe_equivalent",
            [
                {
                    "name": "Folate",
                    "quantity": [{"quantity": 665, "unit": "mcg DFE"}],
                    "nestedRows": [
                        {
                            "name": "Folic Acid",
                            "quantity": [{"quantity": 400, "unit": "mcg"}],
                        },
                    ],
                },
            ],
            [],
        ),
        (
            "elemental_mineral_source_compound",
            [
                {
                    "name": "Magnesium",
                    "category": "mineral",
                    "ingredientGroup": "Magnesium",
                    "quantity": [{"quantity": 100, "unit": "mg"}],
                    "forms": [
                        {
                            "name": "Magnesium Citrate",
                            "category": "source material",
                        },
                    ],
                },
            ],
            [],
        ),
        (
            "proprietary_blend",
            [
                {
                    "name": "Botanical Blend",
                    "ingredientGroup": "Blend (Botanical)",
                    "quantity": [{"quantity": 500, "unit": "mg"}],
                    "nestedRows": [{"name": "Ashwagandha Root Extract"}],
                },
            ],
            [],
        ),
        (
            "botanical_plant_part_extract",
            [
                {
                    "name": "Ashwagandha Root Extract",
                    "category": "botanical",
                    "ingredientGroup": "Ashwagandha",
                    "quantity": [{"quantity": 300, "unit": "mg"}],
                },
            ],
            [],
        ),
        (
            "probiotic_strain_cfu",
            [
                {
                    "name": "Lactobacillus rhamnosus GG",
                    "category": "probiotic",
                    "ingredientGroup": "Probiotic",
                    "quantity": [{"quantity": 10, "unit": "Billion CFU"}],
                },
            ],
            [],
        ),
        (
            "other_ingredients",
            [],
            [{"name": "Gelatin"}, {"name": "Glycerin"}],
        ),
        (
            "empty_panel",
            [],
            [],
        ),
    ],
)
def test_cleaner_audit_classifies_first_release_label_archetypes(
    source_structure, ingredient_rows, other_ingredients
):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrichment_contract_validator import EnrichmentContractValidator

    normalized = EnhancedDSLDNormalizer().normalize_product({
        "id": f"ARCHETYPE-{source_structure}",
        "fullName": "Label Archetype Fixture",
        "brandName": "Test Brand",
        "ingredientRows": ingredient_rows,
        "otheringredients": {"ingredients": other_ingredients},
    })

    assert normalized["label_ledger_audit"]["source_structure"] == source_structure
    assert normalized["label_ledger_audit"]["completeness_percentage"] == 100.0
    assert normalized["label_ledger_audit"]["completeness_status"] == "complete"

    source_paths = {row["raw_source_path"] for row in normalized["label_source_rows"]}
    resolved_paths = {
        row["raw_source_path"] for row in normalized["display_ingredients"]
    } | {
        row["raw_source_path"] for row in normalized["label_ledger_omissions"]
    }
    assert source_paths == resolved_paths

    validator = EnrichmentContractValidator()
    assert not [
        violation
        for violation in validator.validate(normalized)
        if violation.rule.startswith("H.")
    ]

    final_input = dict(normalized)
    final_input.pop("label_ledger_audit")
    final_blob = build_detail_blob(final_input, make_scored())
    assert final_blob["label_ledger_audit"]["source_structure"] == source_structure
    assert not [
        violation
        for violation in validator.validate(final_blob)
        if violation.rule.startswith("H.")
    ]


def test_cleaner_audit_tracks_blank_header_and_string_form_source_occurrences():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalized = EnhancedDSLDNormalizer().normalize_product({
        "id": "LABEL-AUDIT-OMISSIONS",
        "fullName": "Capsule Fixture",
        "brandName": "Test Brand",
        "ingredientRows": [{"name": ""}],
        "otheringredients": {
            "ingredients": [
                {"name": "Less than 2% of:", "forms": []},
                {"name": "Capsule Ingredients", "forms": ["Gelatin", "Glycerin"]},
            ],
        },
    })

    assert {
        (row["raw_source_path"], row["source_section"])
        for row in normalized["label_source_rows"]
    } == {
        ("ingredientRows[0]", "activeIngredients"),
        ("otheringredients.ingredients[0]", "inactiveIngredients"),
        ("otheringredients.ingredients[1]", "inactiveIngredients"),
        ("otheringredients.ingredients[1].forms[0]", "inactiveIngredients"),
        ("otheringredients.ingredients[1].forms[1]", "inactiveIngredients"),
    }
    assert {
        (row["raw_source_path"], row["omission_reason"])
        for row in normalized["label_ledger_omissions"]
    } == {
        ("ingredientRows[0]", "empty_source_text"),
        ("otheringredients.ingredients[0]", "decorative_or_header_text"),
        ("otheringredients.ingredients[1]", "decorative_or_header_text"),
    }
    assert normalized["label_ledger_audit"] == {
        "support_status": "supported",
        "source_structure": "other_ingredients",
        "meaningful_source_rows": 2,
        "displayed_rows": 2,
        "omitted_rows": 3,
        "completeness_percentage": 100.0,
        "completeness_status": "complete",
    }


def test_cleaner_and_final_blob_make_malformed_source_completeness_unavailable():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrichment_contract_validator import EnrichmentContractValidator

    normalized = EnhancedDSLDNormalizer().normalize_product({
        "id": "LABEL-AUDIT-UNSUPPORTED",
        "fullName": "Malformed Fixture",
        "brandName": "Test Brand",
        "ingredientRows": {"name": "Unexpected mapping instead of rows"},
        "otheringredients": {"ingredients": []},
    })

    assert normalized["label_source_rows"] == [
        {
            "raw_source_path": "ingredientRows",
            "raw_source_text": "Unexpected mapping instead of rows",
            "source_section": "activeIngredients",
        },
    ]
    assert normalized["label_ledger_omissions"] == [
        {
            "raw_source_path": "ingredientRows",
            "raw_source_text": "Unexpected mapping instead of rows",
            "omission_reason": "unsupported_source_structure",
        },
    ]
    assert normalized["label_ledger_audit"] == {
        "support_status": "unsupported",
        "source_structure": "unsupported_source_structure",
        "meaningful_source_rows": 0,
        "displayed_rows": 0,
        "omitted_rows": 1,
        "completeness_percentage": None,
        "completeness_status": "unavailable",
    }

    final_blob = build_detail_blob(normalized, make_scored())
    assert final_blob["label_source_rows"] == normalized["label_source_rows"]
    assert final_blob["label_ledger_audit"] == normalized["label_ledger_audit"]
    validator = EnrichmentContractValidator()
    assert not [
        violation
        for violation in validator.validate(final_blob)
        if violation.rule.startswith("H.")
    ]


def test_cleaner_marks_nested_malformed_source_structure_unsupported():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalized = EnhancedDSLDNormalizer().normalize_product({
        "id": "LABEL-AUDIT-NESTED-UNSUPPORTED",
        "fullName": "Malformed Nested Fixture",
        "brandName": "Test Brand",
        "ingredientRows": [
            {
                "name": "Botanical Blend",
                "nestedRows": {"name": "Unexpected mapping instead of rows"},
            },
        ],
        "otheringredients": {"ingredients": []},
    })

    assert {
        row["raw_source_path"] for row in normalized["label_source_rows"]
    } == {"ingredientRows[0]", "ingredientRows[0].nestedRows"}
    assert normalized["label_ledger_omissions"] == [
        {
            "raw_source_path": "ingredientRows[0].nestedRows",
            "raw_source_text": "Unexpected mapping instead of rows",
            "omission_reason": "unsupported_source_structure",
        },
    ]
    assert normalized["label_ledger_audit"]["support_status"] == "unsupported"
    assert normalized["label_ledger_audit"]["completeness_percentage"] is None
    assert normalized["label_ledger_audit"]["completeness_status"] == "unavailable"


def test_final_blob_recomputes_label_audit_from_final_folded_ledger():
    from enrichment_contract_validator import EnrichmentContractValidator

    enriched = _omega_label_ledger_enriched()
    enriched["label_source_rows"] = [
        {
            "raw_source_path": row["raw_source_path"],
            "raw_source_text": row["raw_source_text"],
            "source_section": "activeIngredients",
        }
        for row in enriched["display_ingredients"]
    ]
    enriched["label_ledger_omissions"] = []
    enriched["label_ledger_audit"] = {
        "support_status": "supported",
        "source_structure": "omega_parent_component",
        "meaningful_source_rows": 999,
        "displayed_rows": 999,
        "omitted_rows": 999,
        "completeness_percentage": 1.0,
        "completeness_status": "incomplete",
    }

    blob = build_detail_blob(enriched, make_scored())

    assert blob["label_ledger_audit"] == {
        "support_status": "supported",
        "source_structure": "omega_parent_component",
        "meaningful_source_rows": 5,
        "displayed_rows": 5,
        "omitted_rows": 0,
        "completeness_percentage": 100.0,
        "completeness_status": "complete",
    }
    validator = EnrichmentContractValidator()
    assert not [
        violation
        for violation in validator.validate(blob)
        if violation.rule in {"H.7", "H.8"}
    ]


def test_final_ledger_prefers_authoritative_identity_conflict_over_clean_source():
    from audit_identity_integrity import audit_product
    from enrichment_contract_validator import EnrichmentContractValidator

    enriched = _enriched_with_label_identity(disposition="identity_conflict")
    enriched["activeIngredients"][0]["raw_source_path"] = "ingredientRows[0]"
    enriched["ingredient_quality_data"]["ingredients"][0][
        "raw_source_path"
    ] = "ingredientRows[0]"
    enriched["display_ingredients"] = [
        {
            "raw_source_text": "Docosahexaenoic Acid Ethyl Ester",
            "display_name": "EPA",
            "label_display_name": "EPA",
            "label_display_form": "as Ethyl Esters",
            "raw_source_path": "ingredientRows[0]",
            "source_section": "activeIngredients",
            "display_type": "mapped_ingredient",
            "resolution_type": "direct_mapped",
            "label_order": 0,
            "nested_depth": 0,
            "exact_dose_text": "360 mg",
            "score_included": True,
            "is_label_context": False,
            "display_disposition": "scored",
            "identity_integrity_state": "clean",
            "form_display_state": "assessed",
        },
    ]

    blob = build_detail_blob(enriched, make_scored())
    row = blob["display_ingredients"][0]

    assert row["identity_integrity_state"] == "identity_conflict"
    assert row["form_display_state"] == "needs_review"
    assert row["analysis"]["identity_integrity_state"] == "identity_conflict"
    assert row["analysis"]["form_display_state"] == "needs_review"

    violations = EnrichmentContractValidator().validate_release_integrity(blob)
    assert any(
        violation.evidence.get("audit_code")
        == "score_included_identity_conflict"
        for violation in violations
    )
    assert any(
        record.violation == "score_included_identity_conflict"
        for record in audit_product(blob, classify=lambda _product: "generic")
    )


@pytest.mark.parametrize(
    "collection_name",
    [
        "display_ingredients",
        "label_ledger_omissions",
        "label_source_rows",
    ],
)
def test_final_builder_rejects_duplicate_upstream_label_source_paths(
    collection_name,
):
    enriched = _omega_label_ledger_enriched()
    duplicate_path = "label[0]"
    if collection_name == "display_ingredients":
        enriched[collection_name].append(dict(enriched[collection_name][0]))
    elif collection_name == "label_ledger_omissions":
        enriched[collection_name] = [
            {
                "raw_source_path": duplicate_path,
                "raw_source_text": "Header",
                "omission_reason": "decorative_or_header_text",
            },
            {
                "raw_source_path": duplicate_path,
                "raw_source_text": "Header repeated",
                "omission_reason": "duplicate_source_line",
            },
        ]
    else:
        enriched[collection_name] = [
            {
                "raw_source_path": duplicate_path,
                "raw_source_text": "Fish Oil",
                "source_section": "activeIngredients",
            },
            {
                "raw_source_path": duplicate_path,
                "raw_source_text": "Fish Oil repeated",
                "source_section": "activeIngredients",
            },
        ]

    with pytest.raises(
        ValueError,
        match=rf"duplicate upstream {collection_name} raw_source_path: label\[0\]",
    ):
        build_detail_blob(enriched, make_scored())


@pytest.mark.parametrize(
    ("interpretation_type", "score_included", "structural_dose", "mapped_dose"),
    [
        ("mapped_ingredient", True, (720, "mg"), (720.0, "mg")),
        ("nutrition_fact", False, (720, "mg"), (720, "mg")),
        ("mapped_ingredient", True, (None, ""), (0.0, "NP")),
    ],
)
def test_final_builder_reconciles_complementary_views_of_same_blend_row(
    interpretation_type,
    score_included,
    structural_dose,
    mapped_dose,
):
    enriched = _omega_label_ledger_enriched()
    structural = {
        "raw_source_text": "Marine Lipid Blend",
        "display_name": "Marine Lipid Blend",
        "raw_source_path": "ingredientRows[9]",
        "label_order": 9,
        "nested_depth": 0,
        "quantity": structural_dose[0],
        "unit": structural_dose[1],
        "source_section": "activeIngredients",
        "display_type": "structural_container",
        "resolution_type": "structural_parent",
        "score_included": False,
        "children": ["EPA", "DHA"],
    }
    scored = {
        **structural,
        "display_type": interpretation_type,
        "resolution_type": (
            "direct_mapped"
            if interpretation_type == "mapped_ingredient"
            else "display_only"
        ),
        "score_included": score_included,
        "quantity": mapped_dose[0],
        "unit": mapped_dose[1],
        "mapped_to": {
            "standard_name": "Marine Lipid Blend",
            "raw_source_path": "ingredientRows[9]",
        },
    }
    enriched["display_ingredients"].extend([structural, scored])

    blob = build_detail_blob(enriched, make_scored())
    rows = [
        row
        for row in blob["display_ingredients"]
        if row["raw_source_path"] == "ingredientRows[9]"
    ]

    assert len(rows) == 1
    assert rows[0]["score_included"] is score_included
    assert rows[0]["display_type"] == "structural_container"
    assert rows[0]["children"] == ["EPA", "DHA"]
    assert rows[0]["mapped_to"]["standard_name"] == "Marine Lipid Blend"
    if structural_dose[0] is None:
        assert rows[0]["quantity"] is None
        assert rows[0]["unit"] == ""
        assert rows[0]["exact_dose_text"] in {"", "—"}


def test_final_builder_legacy_fallback_emits_complete_canonical_label_contract():
    from enrichment_contract_validator import EnrichmentContractValidator

    enriched = make_enriched()
    for field_name in (
        "display_ingredients",
        "label_source_rows",
        "label_ledger_omissions",
        "label_ledger_audit",
    ):
        enriched.pop(field_name, None)
    for source_row in (
        enriched["activeIngredients"] + enriched["inactiveIngredients"]
    ):
        source_row.pop("raw_source_path", None)
    for analysis_row in enriched["ingredient_quality_data"]["ingredients"]:
        analysis_row.pop("raw_source_path", None)

    blob = build_detail_blob(enriched, make_scored())
    rows = blob["display_ingredients"]

    assert [row["raw_source_path"] for row in rows] == [
        "activeIngredients[0]",
        "activeIngredients[1]",
        "inactiveIngredients[0]",
    ]
    assert [row["source_section"] for row in rows] == [
        "activeIngredients",
        "activeIngredients",
        "inactiveIngredients",
    ]
    assert [row["display_type"] for row in rows] == [
        "mapped_ingredient",
        "mapped_ingredient",
        "inactive_ingredient",
    ]
    assert [row["resolution_type"] for row in rows] == [
        "direct_mapped",
        "direct_mapped",
        "inactive_mapped",
    ]
    required_fields = {
        "raw_source_path",
        "raw_source_text",
        "display_name",
        "label_display_name",
        "label_order",
        "nested_depth",
        "source_section",
        "display_type",
        "resolution_type",
        "score_included",
        "display_disposition",
        "form_display_state",
        "identity_integrity_state",
        "ledger_fingerprint",
    }
    assert all(required_fields <= row.keys() for row in rows)
    assert [row["raw_source_path"] for row in blob["label_source_rows"]] == [
        "activeIngredients[0]",
        "activeIngredients[1]",
        "inactiveIngredients[0]",
    ]
    assert blob["label_ledger_audit"] == {
        "support_status": "supported",
        "source_structure": "flat_supplement_facts",
        "meaningful_source_rows": 3,
        "displayed_rows": 3,
        "omitted_rows": 0,
        "completeness_percentage": 100.0,
        "completeness_status": "complete",
    }
    assert not [
        violation
        for violation in EnrichmentContractValidator().validate(blob)
        if violation.rule.startswith("H.")
    ]


# ---------------------------------------------------------------------------
# Defensible label provenance + formula versions (Label Truth P1 Task 12)
# ---------------------------------------------------------------------------


def _copy_json(value):
    return json.loads(json.dumps(value))


def test_formula_fingerprint_is_deterministic_and_ignores_analysis_scores_and_map_order():
    enriched = _omega_label_ledger_enriched()
    scored = make_scored()
    first = build_detail_blob(enriched, scored)["label_record"][
        "formula_fingerprint"
    ]

    reordered = _copy_json(enriched)
    reordered["display_ingredients"] = [
        dict(reversed(list(row.items())))
        for row in reordered["display_ingredients"]
    ]
    rescored = _copy_json(scored)
    rescored["score_100_equivalent"] = 1
    rescored["section_scores"] = {"evidence": {"score": 0}}
    second = build_detail_blob(reordered, rescored)["label_record"][
        "formula_fingerprint"
    ]

    assert len(first) == 64
    assert first == second


@pytest.mark.parametrize(
    "mutation",
    [
        "identity",
        "dose",
        "form",
        "order",
    ],
)
def test_formula_fingerprint_changes_with_label_formula_identity(mutation):
    baseline_enriched = _omega_label_ledger_enriched()
    baseline = build_detail_blob(baseline_enriched, make_scored())[
        "label_record"
    ]["formula_fingerprint"]
    changed = _copy_json(baseline_enriched)

    if mutation == "identity":
        changed["display_ingredients"][2]["label_display_name"] = "EPA concentrate"
    elif mutation == "dose":
        changed["display_ingredients"][2]["exact_dose_text"] = "361 mg"
    elif mutation == "form":
        changed["display_ingredients"][0]["label_display_form"] = "Ethyl ester"
    else:
        changed["display_ingredients"][0]["label_order"] = 1
        changed["display_ingredients"][1]["label_order"] = 0

    fingerprint = build_detail_blob(changed, make_scored())["label_record"][
        "formula_fingerprint"
    ]
    assert fingerprint != baseline


def test_label_record_emits_only_present_source_metadata_and_product_status():
    enriched = _omega_label_ledger_enriched()
    enriched.update(
        {
            "productVersionCode": "7",
            "entryDate": "2024-01-02",
            "updatedDate": "2025-03-04T10:11:12Z",
            "label_record_metadata": {
                "label_source_url": "https://api.ods.od.nih.gov/dsld/v9/label/999?view=full",
                "product_status": "discontinued",
            },
        }
    )

    record = build_detail_blob(enriched, make_scored())["label_record"]

    assert record["source_name"] == "NIH DSLD"
    assert record["source_record_id"] == "999"
    assert record["catalog_version"] == "7"
    assert record["source_date"] == "2024-01-02"
    assert record["source_updated_date"] == "2025-03-04T10:11:12Z"
    assert record["product_status"] == "discontinued"
    assert record["label_source_url"] == (
        "https://api.ods.od.nih.gov/dsld/v9/label/999?view=full"
    )
    assert record["lineage_key"] == "dsld:999"
    assert record["field_statuses"] == {
        "source_name": "available",
        "source_record_id": "available",
        "catalog_version": "available",
        "formula_fingerprint": "available",
        "source_date": "available",
        "source_updated_date": "available",
        "product_status": "available",
        "label_source_url": "available",
        "lineage_key": "available",
    }


def test_label_record_marks_optional_metadata_unavailable_without_synthesizing_it():
    enriched = _omega_label_ledger_enriched()
    enriched["offMarket"] = 0
    enriched["enriched_date"] = "2026-07-19T12:00:00Z"
    enriched["imageUrl"] = "https://example.test/bottle-2026-07-19.jpg"

    record = build_detail_blob(enriched, make_scored())["label_record"]

    assert record["catalog_version"] is None
    assert record["source_date"] is None
    assert record["source_updated_date"] is None
    assert record["product_status"] is None
    assert record["label_source_url"] is None
    assert record["field_statuses"]["catalog_version"] == "unavailable"
    assert record["field_statuses"]["source_date"] == "unavailable"
    assert record["field_statuses"]["source_updated_date"] == "unavailable"
    assert record["field_statuses"]["product_status"] == "unavailable"
    assert record["field_statuses"]["label_source_url"] == "unavailable"
    assert record["metadata_status"] == "partial"
    assert record["formula_history"] == []
    assert record["history_status"] == "unavailable"


@pytest.mark.parametrize(
    ("raw_status", "canonical_status"),
    [
        ("ACTIVE", "active"),
        ("Limited Availability", "limited_availability"),
        ("off-market", "off_market"),
    ],
)
def test_label_record_normalizes_documented_product_statuses(
    raw_status,
    canonical_status,
):
    enriched = _omega_label_ledger_enriched()
    enriched["label_record_metadata"] = {"product_status": raw_status}

    record = build_detail_blob(enriched, make_scored())["label_record"]

    assert record["product_status"] == canonical_status


@pytest.mark.parametrize("raw_status", [123, "ACTIVE-ish", "pending"])
def test_label_record_rejects_undocumented_product_statuses(raw_status):
    enriched = _omega_label_ledger_enriched()
    enriched["label_record_metadata"] = {"product_status": raw_status}

    with pytest.raises(ValueError, match="product_status"):
        build_detail_blob(enriched, make_scored())


def test_label_record_metadata_cannot_be_available_without_source_name():
    enriched = _omega_label_ledger_enriched()
    enriched.update(
        {
            "source_type": "external_manual",
            "dsld_id": "manual-record",
            "entryDate": "2024-01-02",
            "updatedDate": "2025-03-04",
            "label_record_metadata": {
                "source_record_id": "publisher-123",
                "catalog_version": "7",
                "product_status": "active",
                "label_source_url": "https://example.test/label/123",
                "lineage_key": "publisher:123",
            },
        }
    )

    record = build_detail_blob(enriched, make_scored())["label_record"]

    assert record["source_name"] is None
    assert record["field_statuses"]["source_name"] == "unavailable"
    assert "unavailable:source_name" in record["metadata_issues"]
    assert record["metadata_status"] == "partial"


def test_label_record_derives_discontinued_only_from_non_default_source_evidence():
    enriched = _omega_label_ledger_enriched()
    enriched["offMarket"] = True

    record = build_detail_blob(enriched, make_scored())["label_record"]

    assert record["product_status"] == "discontinued"
    assert record["field_statuses"]["product_status"] == "available"


@pytest.mark.parametrize("source_type", ["external_manual", "EXTERNAL_MANUAL"])
def test_external_manual_label_record_does_not_promote_local_slug_or_verification_time(
    source_type,
):
    enriched = _omega_label_ledger_enriched()
    enriched.update(
        {
            "source_type": source_type,
            "dsld_id": "manual-magnesium-glycinate-200-mg",
            "manual_product_provenance": {
                "label_verified_at": "2026-07-19T12:00:00Z",
            },
        }
    )

    record = build_detail_blob(enriched, make_scored())["label_record"]

    assert record["source_updated_date"] is None
    assert record["source_record_id"] is None
    assert record["lineage_key"] is None
    assert record["field_statuses"]["source_record_id"] == "unavailable"
    assert record["field_statuses"]["source_updated_date"] == "unavailable"
    assert record["field_statuses"]["lineage_key"] == "unavailable"
    assert record["metadata_status"] == "partial"


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("entryDate", "newest-label", "source_date"),
        ("updatedDate", "recent", "source_updated_date"),
        ("label_source_url", "javascript:alert(1)", "label_source_url"),
    ],
)
def test_label_record_malformed_metadata_fails_closed(field_name, value, message):
    enriched = _omega_label_ledger_enriched()
    if field_name == "label_source_url":
        enriched["label_record_metadata"] = {field_name: value}
    else:
        enriched[field_name] = value

    with pytest.raises(ValueError, match=message):
        build_detail_blob(enriched, make_scored())


def test_formula_history_requires_explicit_matching_lineage_and_real_snapshots():
    enriched = _omega_label_ledger_enriched()
    older_ledger = _copy_json(enriched["display_ingredients"])
    older_ledger[2]["exact_dose_text"] = "300 mg"
    undated_ledger = _copy_json(enriched["display_ingredients"])
    undated_ledger[3]["exact_dose_text"] = "200 mg"
    enriched["label_record_snapshots"] = [
        {
            "snapshot_id": "dsld-999-v5",
            "source_record_id": "999",
            "lineage_key": "dsld:999",
            "catalog_version": "5",
            "source_date": "2023-05-06",
            "display_ingredients": older_ledger,
        },
        {
            "snapshot_id": "formula-2024-07-08",
            "source_record_id": "999",
            "lineage_key": "dsld:999",
            "catalog_version": "6",
            "display_ingredients": undated_ledger,
        },
        {
            "snapshot_id": "different-record",
            "source_record_id": "OTHER",
            "lineage_key": "dsld:OTHER",
            "source_date": "2022-01-01",
            "display_ingredients": older_ledger,
        },
        {
            "snapshot_id": "same-lineage-wrong-source-record",
            "source_record_id": "OTHER",
            "lineage_key": "dsld:999",
            "source_date": "2022-02-02",
            "display_ingredients": older_ledger,
        },
        {
            "snapshot_id": "name-only-2021-01-01",
            "source_record_id": "999",
            "display_ingredients": older_ledger,
        },
    ]

    record = build_detail_blob(enriched, make_scored())["label_record"]

    assert record["history_status"] == "available"
    assert [entry["snapshot_id"] for entry in record["formula_history"]] == [
        "dsld-999-v5",
        "formula-2024-07-08",
    ]
    assert record["formula_history"][0]["source_date"] == "2023-05-06"
    assert record["formula_history"][1]["source_date"] is None
    assert record["formula_history"][1]["source_updated_date"] is None
    assert all(
        entry["lineage_key"] == "dsld:999"
        for entry in record["formula_history"]
    )
    assert all(
        len(entry["formula_fingerprint"]) == 64
        for entry in record["formula_history"]
    )


def test_malformed_formula_history_container_fails_closed():
    enriched = _omega_label_ledger_enriched()
    enriched["label_record_snapshots"] = {
        "formula-2024": {"display_ingredients": enriched["display_ingredients"]}
    }

    with pytest.raises(ValueError, match="label_record_snapshots"):
        build_detail_blob(enriched, make_scored())


def test_duplicate_formula_history_snapshot_id_fails_closed():
    enriched = _omega_label_ledger_enriched()
    ledger = _copy_json(enriched["display_ingredients"])
    enriched["label_record_snapshots"] = [
        {
            "snapshot_id": "dsld-999-v1",
            "source_record_id": "999",
            "lineage_key": "dsld:999",
            "display_ingredients": ledger,
        },
        {
            "snapshot_id": "dsld-999-v1",
            "source_record_id": "999",
            "lineage_key": "dsld:999",
            "display_ingredients": ledger,
        },
    ]

    with pytest.raises(ValueError, match="duplicate snapshot_id"):
        build_detail_blob(enriched, make_scored())


def test_formula_history_rejects_undocumented_snapshot_product_status():
    enriched = _omega_label_ledger_enriched()
    enriched["label_record_snapshots"] = [
        {
            "snapshot_id": "dsld-999-v1",
            "source_record_id": "999",
            "lineage_key": "dsld:999",
            "product_status": "ACTIVE-ish",
            "display_ingredients": _copy_json(enriched["display_ingredients"]),
        }
    ]

    with pytest.raises(ValueError, match="product_status"):
        build_detail_blob(enriched, make_scored())


def test_formula_history_order_is_deterministic_from_explicit_dates_and_snapshot_id():
    enriched = _omega_label_ledger_enriched()
    ledger = _copy_json(enriched["display_ingredients"])
    snapshots = [
        {
            "snapshot_id": "dsld-999-v2",
            "source_record_id": "999",
            "lineage_key": "dsld:999",
            "source_date": "2024-01-02",
            "display_ingredients": ledger,
        },
        {
            "snapshot_id": "dsld-999-v1",
            "source_record_id": "999",
            "lineage_key": "dsld:999",
            "source_date": "2024-01-01",
            "display_ingredients": ledger,
        },
        {
            "snapshot_id": "undated",
            "source_record_id": "999",
            "lineage_key": "dsld:999",
            "display_ingredients": ledger,
        },
    ]
    enriched["label_record_snapshots"] = snapshots
    first = build_detail_blob(enriched, make_scored())["label_record"][
        "formula_history"
    ]
    enriched["label_record_snapshots"] = list(reversed(snapshots))
    second = build_detail_blob(enriched, make_scored())["label_record"][
        "formula_history"
    ]

    assert first == second
    assert [entry["snapshot_id"] for entry in first] == [
        "dsld-999-v1",
        "dsld-999-v2",
        "undated",
    ]
    assert len({entry["formula_fingerprint"] for entry in first}) == 1
