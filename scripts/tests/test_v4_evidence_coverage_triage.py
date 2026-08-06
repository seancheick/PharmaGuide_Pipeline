"""Phase 5 evidence-coverage triage contract.

The audit classifies only unique products in the released catalog. It must not
inflate the queue with duplicate Stage-3 rows, and it must never infer that
clinical evidence exists merely because a product has a recognizable name.
"""

from __future__ import annotations

import csv
import json
import os
import sqlite3
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from audits.v4_evidence_coverage_triage import (  # noqa: E402
    build_triage_report,
    main,
)


def _catalog_product(dsld_id: str, *, evidence_score: float = 0.0) -> dict:
    return {
        "dsld_id": dsld_id,
        "product_name": "Psyllium Husk",
        "brand_name": "Example",
        "v4_module": "fiber_digestive",
        "quality_score_status": "scored",
        "quality_score_v4_100": 69,
        "quality_tier": "Weak",
        "pillar_evidence_v4": evidence_score,
        "key_nutrients_summary": [
            {"name": "Psyllium Husk", "amount": 1400, "unit": "mg"}
        ],
        "ingredient_fingerprint": {
            "nutrients": {},
            "herbs": [],
            "categories": ["fibers"],
        },
    }


def _scored_product(dsld_id: str) -> dict:
    return {
        "dsld_id": dsld_id,
        "quality_score_status": "scored",
        "_v4_pillars": {"evidence": {"score": 0.0}},
        "_v4_module": "fiber_digestive",
        "_v4_module_breakdown": {
            "dimensions": {
                "evidence": {
                    "score": 0.0,
                    "metadata": {
                        "matched_entries": 0,
                        "flags": [],
                        "sub_clinical_canonicals": [],
                    },
                }
            }
        },
        "_v4_confidence_detail": {
            "identity": {
                "level": "low",
                "drivers": ["ingredient_identity_confidence_below_80_percent"],
            }
        },
    }


def test_verified_human_evidence_that_failed_to_project_is_identity_linkage_bucket():
    catalog = [
        _catalog_product("1"),
        _catalog_product("2", evidence_score=4.0),
    ]
    scored = [
        _scored_product("1"),
        _scored_product("1"),  # duplicate Stage-3 row must not inflate release scope
        _scored_product("2"),
    ]
    evidence_entries = [
        {
            "id": "INGR_PSYLLIUM_HUSK",
            "standard_name": "Psyllium Husk",
            "aliases": ["psyllium"],
            "study_type": "systematic_review_meta",
            "evidence_level": "ingredient-human",
            "effect_direction": "positive_strong",
            "references_structured": [{"pmid": "12345678"}],
        }
    ]

    report = build_triage_report(catalog, scored, evidence_entries)

    assert report["summary"]["released_zero_evidence_products"] == 1
    assert report["summary"]["stage3_zero_evidence_rows"] == 3
    assert report["summary"]["stage3_unique_zero_evidence_products"] == 2
    assert report["summary"]["duplicate_stage3_zero_evidence_rows"] == 1
    assert report["summary"]["stage3_zero_evidence_products_not_released"] == 1
    assert len(report["products"]) == 1
    assert report["products"][0]["dsld_id"] == "1"
    assert (
        report["products"][0]["bucket"]
        == "evidence_exists_identity_or_linkage_failed"
    )
    assert report["products"][0]["matched_evidence_entry_ids"] == [
        "INGR_PSYLLIUM_HUSK"
    ]


def test_zero_credit_reference_match_is_reference_or_mechanism_only_bucket():
    product = _catalog_product("1")
    product["product_name"] = "Liquid Chlorophyll"
    product["key_nutrients_summary"] = [
        {"name": "Copper", "amount": 4, "unit": "mg"}
    ]
    scored = _scored_product("1")
    scored["_v4_module_breakdown"]["dimensions"]["evidence"]["metadata"][
        "matched_entries"
    ] = 1
    reference_entry = {
        "id": "INGR_COPPER",
        "standard_name": "Copper",
        "aliases": [],
        "study_type": "reference",
        "evidence_level": "reference",
        "effect_direction": "positive_weak",
        "references_structured": [{"url": "https://example.test/reference"}],
    }

    report = build_triage_report([product], [scored], [reference_entry])

    assert report["products"][0]["bucket"] == "reference_or_mechanism_only"
    assert report["products"][0]["matched_evidence_entry_ids"] == [
        "INGR_COPPER"
    ]


def test_matched_human_evidence_with_dose_guard_is_not_comparable_bucket():
    product = _catalog_product("1")
    scored = _scored_product("1")
    evidence_metadata = scored["_v4_module_breakdown"]["dimensions"]["evidence"][
        "metadata"
    ]
    evidence_metadata.update(
        {
            "matched_entries": 1,
            "flags": ["SUB_CLINICAL_DOSE_DETECTED"],
            "sub_clinical_canonicals": ["psyllium_husk"],
        }
    )
    evidence_entry = {
        "id": "INGR_PSYLLIUM_HUSK",
        "standard_name": "Psyllium Husk",
        "aliases": ["psyllium"],
        "study_type": "systematic_review_meta",
        "evidence_level": "ingredient-human",
        "effect_direction": "positive_strong",
        "references_structured": [{"pmid": "12345678"}],
    }

    report = build_triage_report([product], [scored], [evidence_entry])

    assert (
        report["products"][0]["bucket"]
        == "evidence_exists_product_not_comparable"
    )
    assert report["products"][0]["dose_form_population_reasons"] == [
        "SUB_CLINICAL_DOSE_DETECTED",
        "sub_clinical:psyllium_husk",
    ]


def test_only_source_backed_verified_review_decisions_can_resolve_pending_bucket():
    product = _catalog_product("1")
    product["product_name"] = "L-Glutamine"
    product["key_nutrients_summary"] = [
        {"name": "L-Glutamine", "amount": 5, "unit": "g"}
    ]
    product["ingredient_fingerprint"] = {
        "nutrients": {"l_glutamine": {"amount": 5, "unit": "g"}},
        "herbs": [],
    }
    invalid_decision = {
        "id": "glutamine_without_sources",
        "identity_keys": ["l_glutamine"],
        "bucket": "evidence_exists_knowledge_base_missing",
        "review_status": "verified",
        "reviewed_by": "clinical-reviewer",
        "reviewed_on": "2026-08-06",
        "sources": [],
    }

    pending = build_triage_report(
        [product],
        [_scored_product("1")],
        [],
        review_decisions=[invalid_decision],
    )

    assert (
        pending["products"][0]["bucket"]
        == "external_literature_review_required"
    )
    assert pending["summary"]["invalid_review_decisions"] == 1

    valid_decision = {
        **invalid_decision,
        "id": "glutamine_verified_gap",
        "sources": [
            {
                "type": "pubmed",
                "pmid": "12345678",
                "verification": "content_verified",
            }
        ],
    }
    resolved = build_triage_report(
        [product],
        [_scored_product("1")],
        [],
        review_decisions=[valid_decision],
    )

    assert (
        resolved["products"][0]["bucket"]
        == "evidence_exists_knowledge_base_missing"
    )
    assert resolved["products"][0]["review_decision_id"] == (
        "glutamine_verified_gap"
    )


def test_cli_writes_reproducible_release_scoped_report(tmp_path):
    catalog_db = tmp_path / "catalog.db"
    with sqlite3.connect(catalog_db) as conn:
        conn.execute(
            "CREATE TABLE products_core ("
            "dsld_id TEXT, product_name TEXT, brand_name TEXT, "
            "v4_module TEXT, quality_score_status TEXT, "
            "quality_score_v4_100 INTEGER, quality_tier TEXT, "
            "pillar_evidence_v4 REAL, key_nutrients_summary TEXT, "
            "ingredient_fingerprint TEXT)"
        )
        row = _catalog_product("1")
        conn.execute(
            "INSERT INTO products_core VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                row["dsld_id"],
                row["product_name"],
                row["brand_name"],
                row["v4_module"],
                row["quality_score_status"],
                row["quality_score_v4_100"],
                row["quality_tier"],
                row["pillar_evidence_v4"],
                json.dumps(row["key_nutrients_summary"]),
                json.dumps(row["ingredient_fingerprint"]),
            ),
        )

    scored_root = tmp_path / "products" / "output_example_scored" / "scored"
    scored_root.mkdir(parents=True)
    (scored_root / "scored_batch_1.json").write_text(
        json.dumps([_scored_product("1")]),
        encoding="utf-8",
    )
    (scored_root / ".stage_manifest.json").write_text(
        json.dumps({"stage": "score", "processing_complete": True}),
        encoding="utf-8",
    )
    detail_dir = tmp_path / "detail_blobs"
    detail_dir.mkdir()
    (detail_dir / "1.json").write_text(
        json.dumps(
            {
                "dsld_id": "1",
                "ingredients": [
                    {
                        "name": "Psyllium Husk",
                        "canonical_id": "psyllium_husk",
                        "role": "active",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    evidence_db = tmp_path / "backed_clinical_studies.json"
    evidence_db.write_text(
        json.dumps(
            {
                "backed_clinical_studies": [
                    {
                        "id": "INGR_PSYLLIUM_HUSK",
                        "standard_name": "Psyllium Husk",
                        "aliases": ["psyllium"],
                        "study_type": "systematic_review_meta",
                        "evidence_level": "ingredient-human",
                        "effect_direction": "positive_strong",
                        "references_structured": [{"pmid": "12345678"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    scoring_config = tmp_path / "quality_score.json"
    scoring_config.write_text(
        json.dumps(
            {
                "tiers": [
                    {"min": 70, "name": "Acceptable"},
                    {"min": 55, "name": "Weak"},
                    {"min": 0, "name": "Poor"},
                ]
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "report"

    assert main(
        [
            "--catalog-db",
            str(catalog_db),
            "--scored-root",
            str(tmp_path / "products"),
            "--detail-blobs-dir",
            str(detail_dir),
            "--evidence-db",
            str(evidence_db),
            "--scoring-config",
            str(scoring_config),
            "--output-dir",
            str(output_dir),
        ]
    ) == 0

    summary = json.loads(
        (output_dir / "summary.json").read_text(encoding="utf-8")
    )
    assert summary["summary"]["released_zero_evidence_products"] == 1
    assert summary["inputs"]["catalog_db"]["sha256"]
    assert summary["inputs"]["detail_blobs"]["aggregate_sha256"]
    assert summary["inputs"]["detail_blobs"]["file_count"] == 1
    assert "files" not in summary["inputs"]["detail_blobs"]
    assert summary["inputs"]["scoring_config"]["sha256"]
    assert (
        summary["summary"][
            "released_zero_evidence_missing_detail_blob_context"
        ]
        == 0
    )
    assert "products" not in summary
    with (output_dir / "products.csv").open(encoding="utf-8", newline="") as handle:
        product_rows = list(csv.DictReader(handle))
    assert float(product_rows[0]["priority_score"]) == 0.4
    assert (output_dir / "review_groups.csv").is_file()
    assert b"\r\n" not in (output_dir / "products.csv").read_bytes()
    assert b"\r\n" not in (output_dir / "review_groups.csv").read_bytes()


def test_branded_evidence_generic_alias_does_not_leak_to_unbranded_product():
    product = _catalog_product("1")
    product["product_name"] = "Ashwagandha"
    product["key_nutrients_summary"] = [
        {"name": "Ashwagandha", "amount": 600, "unit": "mg"}
    ]
    branded_entry = {
        "id": "BRAND_KSM66",
        "standard_name": "KSM-66 Ashwagandha",
        "aliases": ["ashwagandha"],
        "brand_tokens": ["KSM-66", "KSM66"],
        "study_type": "rct_multiple",
        "evidence_level": "branded-rct",
        "effect_direction": "positive_strong",
        "references_structured": [{"pmid": "12345678"}],
    }

    report = build_triage_report(
        [product],
        [_scored_product("1")],
        [branded_entry],
    )

    assert (
        report["products"][0]["bucket"]
        == "external_literature_review_required"
    )
    assert report["products"][0]["matched_evidence_entry_ids"] == []


def test_priority_uses_catalog_prevalence_and_configured_tier_proximity():
    first = _catalog_product("1")
    second = _catalog_product("2")
    first_scored = _scored_product("1")
    second_scored = _scored_product("2")
    for scored in (first_scored, second_scored):
        scored["_v4_confidence_detail"]["identity"] = {
            "level": "high",
            "drivers": [],
        }
    evidence_entry = {
        "id": "INGR_PSYLLIUM_HUSK",
        "standard_name": "Psyllium Husk",
        "aliases": ["psyllium"],
        "study_type": "systematic_review_meta",
        "evidence_level": "ingredient-human",
        "effect_direction": "positive_strong",
        "references_structured": [{"pmid": "12345678"}],
    }

    report = build_triage_report(
        [first, second],
        [first_scored, second_scored],
        [evidence_entry],
        tier_thresholds=[55, 70, 80, 90, 95],
    )

    assert report["summary"]["priority_method"]["scan_frequency"] == (
        "catalog prevalence proxy; product scan telemetry unavailable"
    )
    for product in report["products"]:
        assert product["catalog_prevalence_proxy"] == 2
        assert product["tier_boundary_distance"] == 1.0
        assert product["priority_score"] == 2.0
    assert report["review_groups"] == [
        {
            "bucket": "evidence_exists_identity_or_linkage_failed",
            "review_key": "INGR_PSYLLIUM_HUSK",
            "product_count": 2,
            "max_priority_score": 2.0,
            "closest_tier_boundary": 1.0,
            "identity_confidence_counts": {"high": 2},
            "sample_dsld_ids": ["1", "2"],
        }
    ]


def test_detail_blob_active_identity_replaces_lossy_catalog_fingerprint():
    product = _catalog_product("1")
    product["product_name"] = "Ipriflavone 200 mg"
    product["key_nutrients_summary"] = [
        {"name": "Dietary Fiber", "amount": 1, "unit": "g"}
    ]
    detail = {
        "dsld_id": "1",
        "ingredients": [
            {
                "name": "Ipriflavone",
                "standard_name": "Ipriflavone",
                "canonical_id": "ipriflavone",
                "role": "active",
            }
        ],
    }

    report = build_triage_report(
        [product],
        [_scored_product("1")],
        [],
        detail_products=[detail],
    )

    assert report["products"][0]["candidate_identity_keys"] == ["ipriflavone"]
    assert report["products"][0]["review_key"] == "ipriflavone"


def test_human_studies_with_null_effect_are_score_eligible_linkage_failures():
    product = _catalog_product("1")
    product["product_name"] = "Saw Palmetto"
    product["key_nutrients_summary"] = [
        {"name": "Saw Palmetto", "amount": 320, "unit": "mg"}
    ]
    scored = _scored_product("1")
    scored["_v4_module_breakdown"]["dimensions"]["evidence"]["metadata"][
        "matched_entries"
    ] = 1
    null_entry = {
        "id": "INGR_SAW_PALMETTO",
        "standard_name": "Saw Palmetto",
        "aliases": [],
        "study_type": "systematic_review_meta",
        "evidence_level": "ingredient-human",
        "effect_direction": "null",
        "references_structured": [{"pmid": "12345678"}],
    }

    report = build_triage_report([product], [scored], [null_entry])

    assert (
        report["products"][0]["bucket"]
        == "evidence_exists_identity_or_linkage_failed"
    )
    assert report["products"][0]["matched_evidence_entry_ids"] == [
        "INGR_SAW_PALMETTO"
    ]


def test_human_studies_with_negative_effect_correctly_retain_zero_credit():
    product = _catalog_product("1")
    scored = _scored_product("1")
    scored["_v4_module_breakdown"]["dimensions"]["evidence"]["metadata"][
        "matched_entries"
    ] = 1
    negative_entry = {
        "id": "INGR_PSYLLIUM_HUSK",
        "standard_name": "Psyllium Husk",
        "aliases": [],
        "study_type": "systematic_review_meta",
        "evidence_level": "ingredient-human",
        "effect_direction": "negative",
        "references_structured": [{"pmid": "12345678"}],
    }

    report = build_triage_report([product], [scored], [negative_entry])

    assert report["products"][0]["bucket"] == "evidence_truly_absent"
    assert report["products"][0]["matched_evidence_entry_ids"] == [
        "INGR_PSYLLIUM_HUSK"
    ]


def test_nested_generic_evidence_metadata_is_used_for_classification():
    product = _catalog_product("1")
    product["key_nutrients_summary"] = [
        {"name": "Copper", "amount": 4, "unit": "mg"}
    ]
    scored = _scored_product("1")
    scored["_v4_module_breakdown"]["dimensions"]["evidence"]["metadata"] = {
        "generic_evidence_metadata": {
            "matched_entries": 1,
            "flags": ["SUB_CLINICAL_DOSE_DETECTED"],
            "sub_clinical_canonicals": ["copper"],
        }
    }
    reference_entry = {
        "id": "INGR_COPPER",
        "standard_name": "Copper",
        "aliases": [],
        "study_type": "reference",
        "evidence_level": "reference",
        "effect_direction": "positive_weak",
        "references_structured": [{"url": "https://example.test/reference"}],
    }

    report = build_triage_report([product], [scored], [reference_entry])

    assert report["products"][0]["bucket"] == "reference_or_mechanism_only"
    assert report["products"][0]["dose_form_population_reasons"] == [
        "SUB_CLINICAL_DOSE_DETECTED",
        "sub_clinical:copper",
    ]


def test_conflicting_verified_review_decisions_fail_closed():
    product = _catalog_product("1")
    decisions = [
        {
            "id": "psyllium_absent",
            "identity_keys": ["psyllium_husk"],
            "bucket": "evidence_truly_absent",
            "review_status": "verified",
            "reviewed_by": "reviewer-a",
            "reviewed_on": "2026-08-06",
            "sources": [
                {
                    "pmid": "12345678",
                    "verification": "content_verified",
                }
            ],
        },
        {
            "id": "psyllium_kb_gap",
            "identity_keys": ["psyllium_husk"],
            "bucket": "evidence_exists_knowledge_base_missing",
            "review_status": "verified",
            "reviewed_by": "reviewer-b",
            "reviewed_on": "2026-08-06",
            "sources": [
                {
                    "pmid": "23456789",
                    "verification": "content_verified",
                }
            ],
        },
    ]

    report = build_triage_report(
        [product],
        [_scored_product("1")],
        [],
        review_decisions=decisions,
    )

    row = report["products"][0]
    assert row["bucket"] == "external_literature_review_required"
    assert row["review_decision_id"] is None
    assert row["conflicting_review_decision_ids"] == [
        "psyllium_absent",
        "psyllium_kb_gap",
    ]
    assert report["summary"]["conflicting_review_decision_products"] == 1
