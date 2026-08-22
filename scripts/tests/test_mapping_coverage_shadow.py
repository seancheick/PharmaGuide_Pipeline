from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from audits.mapping_coverage_shadow import build_shadow_report  # noqa: E402
from stage_manifest import write_stage_manifest  # noqa: E402


def _mapped_row(path: str = "ingredientRows[0]") -> dict:
    return {
        "name": "Magnesium",
        "raw_source_text": "Magnesium",
        "raw_source_path": path,
        "canonical_id": "magnesium",
        "mapped": True,
        "mapped_identity": True,
        "scoreable_identity": True,
        "identity_disposition": "clean",
        "source_section": "active",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "role_classification": "active_scorable",
        "dose_class": "therapeutic_mass",
        "quantity": 100,
        "unit": "mg",
        "has_dose": True,
        "score_exclusion_reason": None,
    }


def _unmapped_row(path: str = "ingredientRows[1]") -> dict:
    return {
        "name": "Unknown Active",
        "raw_source_text": "Unknown Active",
        "raw_source_path": path,
        "canonical_id": None,
        "mapped": False,
        "mapped_identity": False,
        "scoreable_identity": False,
        "identity_disposition": "unresolved",
        "identity_decision_reason": "no_quality_map_match",
        "source_section": "active",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "role_classification": "active_unmapped",
        "dose_class": "therapeutic_mass",
        "quantity": 50,
        "unit": "mg",
        "has_dose": True,
    }


def _product(dsld_id: str, rows: list[dict]) -> dict:
    mapped = [row for row in rows if row.get("scoreable_identity") is True]
    skipped = [row for row in rows if row.get("scoreable_identity") is not True]
    return {
        "dsld_id": dsld_id,
        "fullName": f"Fixture {dsld_id}",
        "quality_score_status": "scored",
        "ingredient_quality_data": {
            "ingredients_scorable": mapped,
            "ingredients_skipped": skipped,
            "ingredients": rows,
        },
    }


def _write_stage(products_dir: Path, products: list[dict]) -> None:
    stage_dir = products_dir / "output_Test_enriched" / "enriched"
    stage_dir.mkdir(parents=True)
    batch = stage_dir / "enriched_batch_1.json"
    batch.write_text(json.dumps(products), encoding="utf-8")
    write_stage_manifest(stage_dir, "enrich", [batch], run_id="shadow-test")


def test_shadow_report_measures_real_coverage_without_mutating_eligibility(
    tmp_path: Path,
) -> None:
    products = [
        _product("perfect", [_mapped_row()]),
        _product("unresolved", [_mapped_row(), _unmapped_row()]),
    ]
    original = copy.deepcopy(products)
    _write_stage(tmp_path, products)

    report = build_shadow_report(tmp_path)

    assert products == original
    assert report["mode"] == "shadow"
    assert report["enforcement_enabled"] is False
    assert report["summary"] == {
        "product_count": 2,
        "perfect_coverage_product_count": 1,
        "below_one_product_count": 1,
        "no_score_eligible_rows_product_count": 0,
        "mapped_score_eligible_row_count": 2,
        "unmapped_score_eligible_row_count": 1,
        "strict_contract_failed_product_count": 0,
        "duplicate_product_id_count": 0,
    }
    assert report["coverage_fraction_counts"] == {"1/1": 1, "1/2": 1}
    assert report["unresolved_reason_counts"] == {"no_quality_map_match": 1}
    assert report["remediation_queue"] == [
        {
            "dsld_id": "unresolved",
            "product_name": "Fixture unresolved",
            "stage_owner": "output_Test_enriched",
            "source_file": "enriched_batch_1.json",
            "mapped_count": 1,
            "unmapped_count": 1,
            "mapped_coverage": 0.5,
            "unresolved_rows": [
                {
                    "raw_source_path": "ingredientRows[1]",
                    "label": "Unknown Active",
                    "reason_code": "no_quality_map_match",
                    "identity_reason_code": "no_quality_map_match",
                    "canonical_id": None,
                    "quantity": 50,
                    "unit": "mg",
                }
            ],
        }
    ]


def test_shadow_report_separates_products_with_no_score_eligible_rows(
    tmp_path: Path,
) -> None:
    product = _product("empty", [])
    product["quality_score_status"] = "not_scored"
    _write_stage(tmp_path, [product])

    report = build_shadow_report(tmp_path)

    assert report["coverage_fraction_counts"] == {"no_score_eligible_rows": 1}
    assert report["summary"]["no_score_eligible_rows_product_count"] == 1
    assert report["remediation_queue"] == []
    assert report["no_score_eligible_reason_counts"] == {
        "no_strict_scoring_candidates": 1
    }
    assert report["no_score_eligible_queue"] == [
        {
            "dsld_id": "empty",
            "product_name": "Fixture empty",
            "stage_owner": "output_Test_enriched",
            "source_file": "enriched_batch_1.json",
            "product_scoring_class": None,
            "primary_type": None,
            "current_quality_score_status": "not_scored",
            "ingredients_scorable_count": 0,
            "ingredients_skipped_count": 0,
            "product_scoring_evidence_count": 0,
            "zero_scorable_reason": "no_strict_scoring_candidates",
        }
    ]


def test_shadow_report_ignores_dot_prefixed_non_artifact_files(tmp_path: Path) -> None:
    _write_stage(tmp_path, [_product("owned", [_mapped_row()])])
    stage_dir = tmp_path / "output_Test_enriched" / "enriched"
    (stage_dir / ".stale.json").write_text(
        json.dumps([_product("stale", [_unmapped_row()])]),
        encoding="utf-8",
    )

    report = build_shadow_report(tmp_path)

    assert report["summary"]["product_count"] == 1
    assert report["remediation_queue"] == []
