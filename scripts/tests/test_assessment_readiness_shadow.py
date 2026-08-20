from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from audits.assessment_readiness_shadow import build_shadow_report  # noqa: E402
from stage_manifest import write_stage_manifest  # noqa: E402


def _row(name: str, canonical_id: str) -> dict:
    return {
        "name": name,
        "standard_name": name,
        "canonical_id": canonical_id,
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
        "raw_source_path": "ingredientRows[0]",
        "source_row_ref": "ingredientRows[0]",
    }


def _product(dsld_id: str, row: dict) -> dict:
    return {
        "dsld_id": dsld_id,
        "product_name": row["name"],
        "form_factor": "capsule",
        "supplement_taxonomy": {"primary_type": "single_nutrient"},
        "ingredient_quality_data": {
            "ingredients_scorable": [row],
            "ingredients": [row],
            "total_active": 1,
        },
        "evidence_data": {"clinical_matches": []},
        "certification_data": {
            "verification_assessment": {
                "state": "verified_absent",
                "readiness": "complete",
                "reason_code": "registry_evaluated_no_match",
                "matched_programs": [],
            }
        },
        "rda_ul_data": {
            "collection_status": "complete",
            "dose_assessments": [
                {
                    "source_row_ref": "ingredientRows[0]",
                    "canonical_id": row["canonical_id"],
                    "material": True,
                    "conversion_status": "not_required",
                    "ul_assessment_status": "no_ul_applicable",
                    "readiness": "not_applicable",
                }
            ],
        },
    }


def _write_stage(products_dir: Path, products: list[dict]) -> None:
    stage_dir = products_dir / "output_Test_enriched" / "enriched"
    stage_dir.mkdir(parents=True)
    batch = stage_dir / "enriched_batch_1.json"
    batch.write_text(json.dumps(products), encoding="utf-8")
    write_stage_manifest(stage_dir, "enrich", [batch], run_id="readiness-shadow-test")


def test_shadow_measures_readiness_without_changing_catalog_eligibility(
    tmp_path: Path,
) -> None:
    ready = _product("ready", _row("Magnesium", "magnesium"))
    incomplete = _product(
        "evidence-backlog",
        _row("Unreviewed Botanical", "unreviewed_botanical"),
    )
    products = [ready, incomplete]
    original = copy.deepcopy(products)
    _write_stage(tmp_path, products)

    report = build_shadow_report(tmp_path, generated_at="2026-08-20T00:00:00Z")

    assert products == original
    assert report["mode"] == "measure_only"
    assert report["enforcement_enabled"] is False
    assert report["catalog_eligibility_changed"] is False
    assert report["summary"] == {
        "product_count": 2,
        "live_ready_product_count": 1,
        "incomplete_product_count": 1,
        "not_yet_evaluated_material_active_count": 1,
        "verification_not_evaluated_product_count": 0,
        "legacy_dose_inference_product_count": 0,
        "duplicate_product_id_count": 0,
    }
    assert report["dimension_readiness_counts"]["evidence"] == {
        "complete": 1,
        "incomplete": 1,
    }
    assert report["evidence_state_counts"] == {
        "evaluated_supported": 1,
        "not_yet_evaluated": 1,
    }
    assert report["remediation_queue"] == [
        {
            "dsld_id": "evidence-backlog",
            "product_name": "Unreviewed Botanical",
            "stage_owner": "output_Test_enriched",
            "source_file": "enriched_batch_1.json",
            "module": "generic",
            "unavailable_reasons": ["evidence_assessment_readiness"],
            "identity_blocking_findings": [],
            "not_yet_evaluated_material_actives": [
                {
                    "source_row_ref": "ingredientRows[0]",
                    "canonical_id": "unreviewed_botanical",
                    "name": "Unreviewed Botanical",
                    "role": "claim_prominent",
                    "reason_code": "no_reviewed_evidence_assessment",
                }
            ],
            "verification_state": "verified_absent",
            "dose_assessment_source": "typed_dose_assessments",
        }
    ]


def test_shadow_reads_only_manifest_owned_files(tmp_path: Path) -> None:
    _write_stage(tmp_path, [_product("owned", _row("Magnesium", "magnesium"))])
    stage_dir = tmp_path / "output_Test_enriched" / "enriched"
    stale = _product("stale", _row("Unknown", "unknown"))
    (stage_dir / ".stale.json").write_text(json.dumps([stale]), encoding="utf-8")

    report = build_shadow_report(tmp_path)

    assert report["summary"]["product_count"] == 1
    assert report["summary"]["incomplete_product_count"] == 0
