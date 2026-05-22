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
    product = {
        "dsld_id": "P1",
        "product_name": "Strict Product",
        "verdict": "SAFE",
        "quality_score": 50.0,
        "score_80": 50.0,
        "score_100_equivalent": 62.5,
        "mapped_coverage": 1.0,
        "mapped_coverage_applicable": True,
        "scoring_status": "scored",
        "score_basis": "bioactives_scored",
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


def test_scoring_audit_allows_nutrition_only_applicability_state(tmp_path: Path) -> None:
    path = tmp_path / "scored.json"
    _write(
        path,
        _scored(
            verdict="NUTRITION_ONLY",
            quality_score=None,
            score_80=None,
            score_100_equivalent=None,
            mapped_coverage=None,
            mapped_coverage_applicable=False,
            scoring_status="not_applicable",
            score_basis="nutrition_only_food_shape",
            scoring_ingredients_source=None,
        ),
    )

    assert audit_scoring(_args(path)) == []


def test_static_audit_flags_direct_v4_iqd_fallback(tmp_path: Path) -> None:
    path = tmp_path / "bad_module.py"
    path.write_text("rows = iqd.get('ingredients') or product.get('activeIngredients')\n", encoding="utf-8")

    args = argparse.Namespace(path=[str(path)], strict_release=True, matrix="")
    codes = {finding.code for finding in audit_scoring_static(args)}

    assert "V4_IQD_INGREDIENTS_FALLBACK" in codes
    assert "V4_RAW_ACTIVE_FALLBACK" in codes
