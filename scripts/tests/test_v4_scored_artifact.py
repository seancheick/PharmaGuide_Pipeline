"""Contract tests for the single v4-native Stage-3 artifact assembler."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_v4 import scored_artifact  # noqa: E402
from scoring_v4.modules import generic_formulation  # noqa: E402
from build_final_db import validate_export_contract  # noqa: E402


def _row(name: str = "Magnesium", canonical_id: str = "magnesium") -> dict:
    return {
        "name": name,
        "standard_name": name,
        "canonical_id": canonical_id,
        "mapped_identity": bool(canonical_id),
        "identity_disposition": "clean",
        "source_section": "active",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "dose_class": "therapeutic_mass",
        "role_classification": "active_scorable",
        "scoreable_identity": bool(canonical_id),
        "score_eligible": True,
        "dose": 200,
        "quantity": 200,
        "unit": "mg",
        "raw_source_path": "ingredientRows[0]",
    }


def _product(
    rows: list[dict] | None = None,
    *,
    all_rows: list[dict] | None = None,
) -> dict:
    active_rows = rows if rows is not None else [_row()]
    return {
        "dsld_id": "fixture-1",
        "product_name": "Magnesium Test",
        "brand_name": "Test Brand",
        "status": "active",
        "form_factor": "capsule",
        "primary_type": "single_mineral",
        "secondary_type": None,
        "supplement_taxonomy": {
            "primary_type": "single_mineral",
            "secondary_type": None,
            "percentile_category": "single_mineral",
            "classification_contract_version": "1.2.0",
        },
        "ingredient_quality_data": {
            "ingredients_scorable": active_rows,
            "ingredients": all_rows if all_rows is not None else active_rows,
            "total_active": len(active_rows),
        },
    }


def _canned_v4(
    *, status: str = "scored", verdict: str = "SAFE", mapped_coverage: float = 1.0
) -> dict:
    score = 82.0 if status == "scored" else None
    return {
        "quality_score_v4_100": score,
        "quality_score_status": status,
        "quality_score_suppressed_reason": None,
        "quality_score_cap_v4": None,
        "quality_score_version": "4-test",
        "quality_tier": "Strong" if score is not None else None,
        "quality_pillars_v4": {
            "formulation": {"score": 16.0, "max": 20.0},
            "dose": {"score": 17.0, "max": 20.0},
            "evidence": {"score": 16.0, "max": 20.0},
            "transparency": {"score": 12.0, "max": 15.0},
            "verification": {"score": 12.0, "max": 15.0},
            "safety_hygiene": {"score": 9.0, "max": 10.0},
        } if score is not None else None,
        "raw_score_v4_100": score,
        "v4_module": "generic",
        "v4_verdict": verdict,
        "v4_confidence": "high",
        "clean_label_flags_v4": [],
        "v4_breakdown": {
            "module": {},
            "confidence": {},
            "safety_gate": {
                "verdict": verdict,
                "blocking_reason": None,
                "safety_signals": [],
                "clean_label_hits": [],
            },
            "completeness_gate": {
                "mapped_coverage": mapped_coverage,
                "is_live_eligible": status == "scored",
                "reason": None,
            },
            "provenance": {
                "scoring_engine_version": "4-test",
                "classification_schema_version": "1.2.0",
                "config_versions": {"quality_score": "test"},
                "module_route": "generic",
                "mode": "production",
            },
        },
    }


def test_build_scored_artifact_is_v4_native(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scored_artifact, "score_product_v4", lambda _product: _canned_v4())

    artifact = scored_artifact.build_scored_artifact(_product())

    assert artifact["quality_score_v4_100"] == 82.0
    assert artifact["quality_score_status"] == "scored"
    assert artifact["quality_pillars_v4"]
    assert artifact["mapped_coverage"] == 1.0
    assert artifact["strict_scoring_contract"]["passed"] is True
    assert artifact["scoring_metadata"]["score_basis"] == "v4_six_pillar"
    assert artifact["supplement_taxonomy"]["primary_type"] == "single_mineral"
    assert artifact["category_percentile"] == {
        "category_key": "single_mineral",
        "category_label": "Single Mineral",
    }
    assert artifact["verdict"] == "SAFE"
    assert "score_80" not in artifact
    assert "section_scores" not in artifact
    issues = validate_export_contract(_product(), artifact)
    assert not any("v4-native" in issue for issue in issues)
    assert not any("v4 quality_score_status" in issue for issue in issues)
    assert not any("six v4 pillars" in issue for issue in issues)
    assert not any("mapped_coverage" in issue for issue in issues)


def test_b1_inactive_penalty_details_follow_the_scoring_decision() -> None:
    product = {
        "contaminant_data": {
            "harmful_additives": {
                "additives": [
                    {
                        "additive_id": "ADD_LOW",
                        "severity": "low",
                        "source_section": "inactive",
                    },
                    {
                        "additive_id": "ADD_MODERATE",
                        "severity": "moderate",
                        "source_section": "inactive",
                    },
                    {
                        "additive_id": "ADD_MODERATE",
                        "severity": "low",
                        "source_section": "inactive",
                    },
                    {
                        "additive_id": "ADD_ACTIVE_LOW",
                        "severity": "low",
                        "source_section": "active",
                    },
                    {
                        "additive_id": "ADD_ACTIVE_HIGH",
                        "severity": "high",
                        "source_section": "active",
                    },
                ]
            }
        }
    }

    detail = generic_formulation.shared_formulation_penalty_detail(product)

    assert detail["penalties"]["B1_harmful_additives"] == -5.5
    assert detail["metadata"]["inactive_penalty_details"] == [
        {
            "matched_rule_id": "ADD_LOW",
            "penalty_tier": "low",
            "penalty_applied": 0.5,
        },
        {
            "matched_rule_id": "ADD_MODERATE",
            "penalty_tier": "moderate",
            "penalty_applied": 2.0,
        },
    ]


def test_scored_artifact_exports_inactive_penalty_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    v4 = _canned_v4()
    v4["v4_breakdown"]["module"] = {
        "dimensions": {
            "formulation": {
                "metadata": {
                    "inactive_penalty_details": [
                        {
                            "matched_rule_id": "ADD_MALTODEXTRIN",
                            "penalty_tier": "low",
                            "penalty_applied": 0.5,
                        }
                    ]
                }
            }
        }
    }
    monkeypatch.setattr(scored_artifact, "score_product_v4", lambda _product: v4)

    artifact = scored_artifact.build_scored_artifact(_product())

    assert artifact["_v4_inactive_penalty_details"] == [
        {
            "matched_rule_id": "ADD_MALTODEXTRIN",
            "penalty_tier": "low",
            "penalty_applied": 0.5,
        }
    ]


def test_build_scored_artifact_rejects_non_product_input() -> None:
    with pytest.raises(TypeError, match="enriched product must be an object"):
        scored_artifact.build_scored_artifact([])  # type: ignore[arg-type]


def test_export_rejects_old_scorer_artifact() -> None:
    issues = validate_export_contract(
        _product(),
        {
            "score_basis": "strict_iqd",
            "verdict": "SAFE",
            "mapped_coverage": 1.0,
            "scoring_metadata": {},
            "strict_scoring_contract": {"passed": True},
        },
    )

    assert any("not v4-native" in issue for issue in issues)


def test_missing_scoring_rows_cannot_emit_safe() -> None:
    artifact = scored_artifact.build_scored_artifact(_product(rows=[]))

    assert artifact["mapped_coverage"] == 0.0
    assert artifact["quality_score_status"] == "not_scored"
    assert artifact["verdict"] == "NOT_SCORED"
    assert artifact["safety_verdict"] != "SAFE" or artifact["verdict"] != "SAFE"
    assert artifact["strict_scoring_contract"]["passed"] is True


def test_low_coverage_trust_floor_downgrades_safe_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scorable_rows = [_row()]
    all_rows = list(scorable_rows)
    for index in range(3):
        unresolved = _row(name=f"Unresolved {index}", canonical_id="")
        unresolved["raw_source_path"] = f"ingredientRows[{index + 1}]"
        unresolved.update({
            "source_section": "active",
            "cleaner_row_role": "active_scorable",
            "score_eligible_by_cleaner": True,
            "role_classification": "active_unmapped",
            "skip_reason": "no_quality_map_match",
            "has_dose": True,
            "score_eligible": False,
            "scoreable_identity": False,
            "identity_disposition": "unresolved",
        })
        all_rows.append(unresolved)
    monkeypatch.setattr(
        scored_artifact,
        "score_product_v4",
        lambda _product: _canned_v4(mapped_coverage=0.25),
    )

    artifact = scored_artifact.build_scored_artifact(
        _product(rows=scorable_rows, all_rows=all_rows)
    )

    assert artifact["mapped_coverage"] == 0.25
    assert artifact["quality_score_status"] == "scored"
    assert artifact["verdict"] == "CAUTION"
    assert artifact["safety_signal_reason"] == "low_mapped_coverage"


def test_hard_block_suppresses_every_public_score_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(scored_artifact, "score_product_v4", lambda _product: _canned_v4())
    original = scored_artifact.build_scored_artifact(_product())

    blocked = scored_artifact.suppress_scored_artifact_for_hard_block(
        original, reason="banned_substance"
    )

    assert blocked is not original
    assert original["quality_score_v4_100"] == 82.0
    assert blocked["verdict"] == "BLOCKED"
    assert blocked["safety_verdict"] == "BLOCKED"
    assert blocked["quality_score_v4_100"] is None
    assert blocked["quality_score_status"] == "suppressed_safety"
    assert blocked["score_100_equivalent"] is None
    assert blocked["display_100"] == "N/A"
    assert blocked["_v4_quality_score_100"] is None
    assert blocked["_v4_quality_status"] == "suppressed_safety"
    assert blocked["scoring_metadata"]["scoring_status"] == "suppressed_safety"
    assert blocked["_v4_safety_gate"]["verdict"] == "BLOCKED"
    assert blocked["_v4_pillars"] == original["_v4_pillars"]


def test_scoped_contract_reuse_is_output_equivalent_to_uncached_assembly() -> None:
    product = _product()
    uncached = scored_artifact.assemble_scored_artifact(
        product,
        scored_artifact.score_product_v4(product),
    )
    scoped = scored_artifact.build_scored_artifact(product)

    # Wall-clock provenance is expected to differ between sequential calls;
    # every clinical, score, verdict, and contract field must remain identical.
    uncached["scoring_metadata"].pop("scored_date", None)
    scoped["scoring_metadata"].pop("scored_date", None)
    assert scoped == uncached
