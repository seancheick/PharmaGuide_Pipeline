"""Schema-3 byte accounting and warning-equivalence report contract."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from audits.schema3_payload_report import build_schema3_payload_report  # noqa: E402


RULE_ID = "RULE_TEST_MAGNESIUM_DIABETES"
RULE = {
    "id": RULE_ID,
    "subject_ref": {"canonical_id": "magnesium"},
    "condition_rules": [
        {
            "condition_id": "diabetes",
            "severity": "caution",
            "evidence_level": "probable",
            "mechanism": "Magnesium may affect glucose control.",
            "action": "Monitor glucose with your clinician.",
            "sources": [],
            "direction": "harmful",
            "materiality": "presence",
        }
    ],
    "drug_class_rules": [],
}


def _warning() -> dict:
    return {
        "type": "interaction",
        "severity": "caution",
        "severity_contextual": "informational",
        "display_mode_default": "suppress",
        "title": "Magnesium / diabetes",
        "detail": "Magnesium may affect glucose control.",
        "action": "Monitor glucose with your clinician.",
        "alert_headline": None,
        "alert_body": None,
        "informational_note": None,
        "condition_ids": ["diabetes"],
        "drug_class_ids": [],
        "ingredient_name": "Magnesium",
        "ingredient_canonical_id": "magnesium",
        "evidence_level": "probable",
        "sources": [],
        "dose_threshold_evaluation": None,
        "dose_decision": None,
        "direction": "harmful",
        "materiality": "presence",
        "min_effective_dose": None,
        "dose_floor_status": None,
        "source": "interaction_rules",
        "source_rule_id": RULE_ID,
        "profile_gate": None,
    }


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    build = tmp_path / "build"
    blobs = build / "detail_blobs"
    blobs.mkdir(parents=True)
    (build / "export_manifest.json").write_text(
        json.dumps({"schema_version": "2.4.0", "detail_blob_count": 1}),
        encoding="utf-8",
    )
    conn = sqlite3.connect(build / "pharmaguide_core.db")
    try:
        conn.execute("CREATE TABLE products_core (dsld_id TEXT PRIMARY KEY)")
        conn.execute("INSERT INTO products_core VALUES ('p1')")
        conn.commit()
    finally:
        conn.close()
    (blobs / "p1.json").write_text(
        json.dumps(
            {
                "dsld_id": "p1",
                "ingredients": [
                    {"canonical_id": "magnesium", "safety_hits": [{"x": 1}]}
                ],
                "warnings": [_warning()],
                "warnings_profile_gated": [_warning()],
                "section_breakdown": {"legacy": True},
                "rda_ul_data": {
                    "ingredients_with_rda": [{"canonical_id": "magnesium"}],
                    "adequacy_results": [{"canonical_id": "magnesium"}],
                    "analyzed_ingredients": [
                        {"canonical_id": "magnesium", "data_by_group": [1, 2]}
                    ],
                },
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    rules = tmp_path / "rules.json"
    rules.write_text(
        json.dumps(
            {
                "_metadata": {"schema_version": "test", "total_entries": 1},
                "interaction_rules": [RULE],
            }
        ),
        encoding="utf-8",
    )
    return build, rules


def test_report_accounts_bytes_and_proves_warning_equivalence(tmp_path: Path) -> None:
    build, rules = _fixture(tmp_path)

    report = build_schema3_payload_report(build, rules)

    assert report["source_schema_version"] == "2.4.0"
    assert report["product_count"] == 1
    assert report["warning_equivalence"] == {
        "checked": 1,
        "failures": 0,
        "failure_samples": [],
    }
    assert report["bytes"]["schema2"] > report["bytes"]["schema3"]
    assert report["bytes"]["saved"] > 0
    assert report["removed_families"]["ingredient_safety_hits"]["bytes"] > 0
    assert report["removed_families"]["rda_duplicates"]["bytes"] > 0
    assert len(report["input_fingerprint_sha256"]) == 64


def test_report_rejects_blob_outside_core_manifest_ownership(tmp_path: Path) -> None:
    build, rules = _fixture(tmp_path)
    (build / "detail_blobs" / "orphan.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="manifest ownership"):
        build_schema3_payload_report(build, rules)
