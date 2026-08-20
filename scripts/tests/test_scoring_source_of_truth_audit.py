from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from audit_source_of_truth_contract import audit_scoring, audit_scoring_static  # noqa: E402


def _args(path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        product_file=[str(path)],
        enriched_file=[],
        enriched_dir=[],
        products_dir=None,
        dist_dir=None,
        strict_release=True,
        matrix=str(SCRIPTS_ROOT / "contracts" / "source_of_truth_matrix.json"),
    )


def _write(path: Path, product: dict) -> None:
    path.write_text(json.dumps([product]), encoding="utf-8")


def _scored(**overrides) -> dict:
    assessment_readiness = {
        "enforcement_mode": "enforced",
        "is_live_ready": True,
        "unavailable_reasons": [],
        "identity": {"readiness": "complete", "migration_inference": False},
        "dose": {"readiness": "complete", "migration_inference": False},
        "evidence": {"readiness": "complete", "migration_inference": False},
        "verification": {"readiness": "complete", "migration_inference": False},
        "route": {"readiness": "complete", "migration_inference": False},
    }
    product = {
        "dsld_id": "P1",
        "product_name": "Strict Product",
        "verdict": "SAFE",
        "quality_score": 50.0,
        "score_80": 50.0,
        "score_100_equivalent": 62.5,
        "mapped_coverage": 1.0,
        "scoring_status": "scored",
        "quality_score_status": "scored",
        "score_basis": "bioactives_scored",
        "_v4_completeness_gate": {
            "is_live_eligible": True,
            "verdict": None,
        },
        "assessment_readiness": assessment_readiness,
        "_v4_assessment_readiness": assessment_readiness,
        "scoring_ingredients_source": "ingredient_quality_data.ingredients_scorable",
        "scoring_fallbacks_used": [],
        "strict_scoring_contract": {"passed": True, "findings": []},
        "iqd_contract_diagnostics": {
            "scoring_ingredients_source": "ingredient_quality_data.ingredients_scorable",
            "iqd_ingredients_fallback_used": False,
            "scoring_fallbacks_used": [],
        },
    }
    product.update(overrides)
    return product


def test_scoring_audit_passes_strict_scored_product(tmp_path: Path) -> None:
    path = tmp_path / "scored.json"
    _write(path, _scored())

    assert audit_scoring(_args(path)) == []


def test_scoring_audit_products_dir_reads_only_scored_outputs(tmp_path: Path) -> None:
    products_dir = tmp_path / "products"
    scored = products_dir / "output_Test_scored" / "scored" / "scored_batch_1.json"
    cleaned = products_dir / "output_Test" / "cleaned" / "cleaned_batch_1.json"
    enriched = products_dir / "output_Test_enriched" / "enriched" / "enriched_batch_1.json"
    report = products_dir / "output_Test_scored" / "reports" / "scoring_summary.json"

    for path, payload in (
        (scored, _scored()),
        (cleaned, {"dsld_id": "C1", "product_name": "Cleaned only"}),
        (enriched, {"dsld_id": "E1", "product_name": "Enriched only"}),
    ):
        path.parent.mkdir(parents=True)
        _write(path, payload)
    report.parent.mkdir(parents=True)
    report.write_text(json.dumps({"summary": "not a scored product payload"}), encoding="utf-8")

    args = argparse.Namespace(
        product_file=[],
        enriched_file=[],
        enriched_dir=[],
        products_dir=str(products_dir),
        dist_dir=None,
        strict_release=True,
        matrix=str(SCRIPTS_ROOT / "contracts" / "source_of_truth_matrix.json"),
    )

    assert audit_scoring(args) == []


def test_scoring_audit_rejects_iqd_ingredients_fallback(tmp_path: Path) -> None:
    path = tmp_path / "scored.json"
    product = _scored(
        scoring_ingredients_source="ingredient_quality_data.ingredients",
        iqd_contract_diagnostics={
            "scoring_ingredients_source": "ingredient_quality_data.ingredients",
            "iqd_ingredients_fallback_used": True,
            "scoring_fallbacks_used": [
                {"fallback_class": "old_batch_compatibility", "fallback_reason": "legacy"}
            ],
        },
    )
    _write(path, product)

    codes = {finding.code for finding in audit_scoring(_args(path))}
    assert "SCORING_SOURCE_FORBIDDEN" in codes
    assert "SCORING_USED_IQD_FALLBACK" in codes


def test_scoring_audit_rejects_failed_strict_contract(tmp_path: Path) -> None:
    path = tmp_path / "scored.json"
    _write(
        path,
        _scored(
            strict_scoring_contract={
                "passed": False,
                "findings": ["missing_required_fields:raw_source_path"],
            }
        ),
    )

    codes = {finding.code for finding in audit_scoring(_args(path))}
    assert "SCORING_STRICT_CONTRACT_FAILED" in codes


def test_scoring_audit_rejects_safe_below_mapping_threshold(tmp_path: Path) -> None:
    path = tmp_path / "scored.json"
    _write(path, _scored(mapped_coverage=0.2))

    codes = {finding.code for finding in audit_scoring(_args(path))}
    assert "SCORING_SAFE_LOW_COVERAGE" in codes


def test_scoring_audit_requires_full_mapping_for_scored_product(tmp_path: Path) -> None:
    path = tmp_path / "scored.json"
    _write(path, _scored(mapped_coverage=0.9999))

    codes = {finding.code for finding in audit_scoring(_args(path))}
    assert "SCORING_LIVE_MAPPING_INCOMPLETE" in codes


def test_scoring_audit_requires_typed_readiness_for_scored_product(tmp_path: Path) -> None:
    path = tmp_path / "scored.json"
    product = _scored()
    product.pop("assessment_readiness")
    product.pop("_v4_assessment_readiness")
    _write(path, product)

    codes = {finding.code for finding in audit_scoring(_args(path))}
    assert "SCORING_ASSESSMENT_READINESS_MISSING" in codes


def test_scoring_audit_rejects_legacy_readiness_inference(tmp_path: Path) -> None:
    path = tmp_path / "scored.json"
    product = _scored()
    product["assessment_readiness"]["dose"]["migration_inference"] = True
    _write(path, product)

    codes = {finding.code for finding in audit_scoring(_args(path))}
    assert "SCORING_ASSESSMENT_MIGRATION_INFERENCE" in codes


def test_scoring_audit_rejects_shadow_mode_readiness(tmp_path: Path) -> None:
    path = tmp_path / "scored.json"
    product = _scored()
    product["assessment_readiness"]["enforcement_mode"] = "shadow"
    _write(path, product)

    codes = {finding.code for finding in audit_scoring(_args(path))}
    assert "SCORING_ASSESSMENT_READINESS_NOT_ENFORCED" in codes


def test_scoring_audit_rejects_unresolved_dose_on_safety_suppressed_product(
    tmp_path: Path,
) -> None:
    path = tmp_path / "scored.json"
    product = _scored(
        verdict="BLOCKED",
        quality_score_status="suppressed_safety",
        scoring_status="suppressed_safety",
    )
    product["assessment_readiness"]["is_live_ready"] = False
    product["assessment_readiness"]["unavailable_reasons"] = [
        "dose_assessment_readiness"
    ]
    product["assessment_readiness"]["dose"]["readiness"] = "incomplete"
    _write(path, product)

    codes = {finding.code for finding in audit_scoring(_args(path))}
    assert "SCORING_SUPPRESSED_SAFETY_DOSE_INCOMPLETE" in codes


def test_scoring_audit_rejects_retired_nutrition_only_verdict(tmp_path: Path) -> None:
    path = tmp_path / "scored.json"
    _write(
        path,
        _scored(
            verdict="NUTRITION_ONLY",
            quality_score=None,
            score_80=None,
            score_100_equivalent=None,
            mapped_coverage=None,
            scoring_status="not_applicable",
            quality_score_status="not_scored",
            score_basis="nutrition_only_food_shape",
            scoring_ingredients_source=None,
            _v4_completeness_gate={
                "is_live_eligible": False,
                "verdict": "NOT_SCORED",
            },
        ),
    )

    codes = {finding.code for finding in audit_scoring(_args(path))}
    assert "SCORING_RETIRED_NUTRITION_ONLY" in codes


def test_scoring_audit_uses_live_eligibility_not_nullable_gate_verdict(
    tmp_path: Path,
) -> None:
    path = tmp_path / "scored.json"
    _write(
        path,
        _scored(
            _v4_completeness_gate={
                "is_live_eligible": True,
                "verdict": None,
            }
        ),
    )

    assert audit_scoring(_args(path)) == []


def test_scoring_audit_rejects_scored_product_that_is_not_live_eligible(
    tmp_path: Path,
) -> None:
    path = tmp_path / "scored.json"
    _write(
        path,
        _scored(
            _v4_completeness_gate={
                "is_live_eligible": False,
                "verdict": "NOT_SCORED",
            }
        ),
    )

    codes = {finding.code for finding in audit_scoring(_args(path))}
    assert "SCORING_COMPLETENESS_STATUS_MISMATCH" in codes


def test_static_audit_flags_direct_v4_iqd_fallback(tmp_path: Path) -> None:
    path = tmp_path / "bad_module.py"
    path.write_text("rows = iqd.get('ingredients') or product.get('activeIngredients')\n", encoding="utf-8")

    args = argparse.Namespace(path=[str(path)], strict_release=True, matrix="")
    codes = {finding.code for finding in audit_scoring_static(args)}

    assert "V4_IQD_INGREDIENTS_FALLBACK" in codes
    assert "V4_RAW_ACTIVE_FALLBACK" in codes


def test_static_audit_current_v4_modules_have_no_forbidden_fallbacks() -> None:
    args = argparse.Namespace(
        path=[str(SCRIPTS_ROOT / "scoring_v4")],
        strict_release=True,
        matrix="",
    )

    assert audit_scoring_static(args) == []
