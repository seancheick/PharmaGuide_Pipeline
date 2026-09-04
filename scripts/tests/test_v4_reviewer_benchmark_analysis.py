"""Locked-analysis contracts for the blinded V4 reviewer benchmark."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from audits.v4_reviewer_benchmark_analysis import (
    AnalysisContractError,
    analyze_benchmark,
    assert_baseline_access,
    build_response_lock,
    icc_absolute_agreement,
    validate_candidate_lock,
    validate_reviewer_registry,
    validate_and_select_responses,
    verify_response_lock,
)


PILLAR_VALUES = (16.0, 15.0, 14.0, 12.0, 11.0, 9.0)


def _spec(*, iterations: int = 50) -> dict:
    return {
        "schema_version": "1.0.0",
        "analysis_version": "2.0.0",
        "response_contract_version": "2.0.0",
        "protocol_version": "1.2.0",
        "freeze_id": "fixture-v1",
        "primary_design": {
            "panel_size": 3,
            "required_ratings": 6,
            "licensed_clinical_reviewers_required": 2,
            "licensed_clinical_credentials": [
                "pharmacist",
                "physician",
                "registered_dietitian",
            ],
            "substitutions_in_primary_analysis": False,
        },
        "rating_contract": {
            "pillar_limits": dict(zip((
                "formulation_0_20", "dose_0_20", "evidence_0_20",
                "transparency_0_15", "verification_0_15",
                "formula_quality_checks_0_10",
            ), (20, 20, 20, 15, 15, 10))),
            "confidence_values": ["high", "moderate", "low"],
            "label_sufficiency_values": ["yes", "no"],
            "attestation_values": ["yes", "no", "unknown"],
            "increment": 0.5,
            "arithmetic_tolerance": 0.000001,
            "overall_is_exact_pillar_sum": True,
            "missing_value_imputation": False,
            "primary_requires_no_protocol_deviation": True,
            "source_citation_required": True,
            "safety_source_required_for_concern": True,
        },
        "tier_order_low_to_high": [
            "Poor",
            "Weak",
            "Acceptable",
            "Strong",
            "Excellent",
            "Elite",
        ],
        "tier_thresholds": [
            {"min": 95, "name": "Elite"},
            {"min": 90, "name": "Excellent"},
            {"min": 80, "name": "Strong"},
            {"min": 70, "name": "Acceptable"},
            {"min": 55, "name": "Weak"},
            {"min": 0, "name": "Poor"},
        ],
        "safety_severity_low_to_high": [
            "no_known_catalog_concern",
            "caution",
            "unsafe",
            "blocked",
        ],
        "safety_not_assessed_value": "not_assessed",
        "metric_direction": {
            "signed_error": "engine_minus_reviewer_consensus",
            "potential_safety_undercall": (
                "any_reviewer_more_severe_than_engine"
            ),
            "potential_safety_overcall": (
                "engine_more_severe_than_all_reviewers"
            ),
        },
        "agreement": {
            "primary_icc": "ICC(A,1)",
            "panel_mean_icc": "ICC(A,3)",
            "model": "two_way_random_effects_absolute_agreement",
            "complete_fixed_panel_required": True,
        },
        "bootstrap": {
            "method": "product_cluster_percentile",
            "iterations": iterations,
            "confidence_level": 0.95,
            "seed": "fixture-seed",
        },
        "decision_thresholds": {
            "status": "not_set_pending_statistician_and_clinical_owner",
            "calibration_eligibility": False,
        },
    }


def _registry_rows() -> list[dict]:
    credentials = ("pharmacist", "physician", "research_scientist")
    return [
        {
            "reviewer_slot": str(slot),
            "reviewer_id": f"R{slot}",
            "panel_role": "primary",
            "credential_type": credentials[slot - 1],
            "credential_detail": f"Credential {slot}",
            "license_jurisdiction": "US-NY" if slot < 3 else "",
            "license_status": "active_verified" if slot < 3 else "not_applicable",
            "license_verification_source": (
                "https://official.example/license" if slot < 3 else ""
            ),
            "supplement_experience_years": "5",
            "evidence_appraisal_experience_years": "4",
            "conflicts_json": "[]",
            "training_completed_on": "2026-08-07",
            "training_assessment_score": "95",
            "protocol_version": "1.2.0",
            "independence_attested_on": "2026-08-07",
            "data_use_attested_on": "2026-08-07",
            "registered_on": "2026-08-07",
        }
        for slot in (1, 2, 3)
    ]


def _response(
    benchmark_id: str,
    sequence: int,
    slot: int,
    *,
    overall_adjustment: float = 0.0,
    safety: str = "no_known_catalog_concern",
    review_round: int = 1,
    correction_reason: str = "",
) -> dict:
    values = list(PILLAR_VALUES)
    values[0] += overall_adjustment
    return {
        "benchmark_id": benchmark_id,
        "review_sequence": str(sequence),
        "reviewer_slot": str(slot),
        "reviewer_id": f"R{slot}",
        "reviewer_order": str(sequence),
        "review_round": str(review_round),
        "correction_reason": correction_reason,
        "ai_assistance_used": "no",
        "prior_ai_review_seen": "no",
        "engine_output_seen": "no",
        "formulation_0_20": str(values[0]),
        "dose_0_20": str(values[1]),
        "evidence_0_20": str(values[2]),
        "transparency_0_15": str(values[3]),
        "verification_0_15": str(values[4]),
        "formula_quality_checks_0_10": str(values[5]),
        "overall_0_100": str(sum(values)),
        "product_safety_status": safety,
        "safety_concern_driver": (
            "Fixture ingredient at the disclosed dose."
            if safety in {"caution", "unsafe", "blocked"}
            else ""
        ),
        "assessment_confidence": "high",
        "label_facts_sufficient": "yes",
        "source_citations_json": json.dumps([
            {
                "type": "internal_test_fixture",
                "id": "fixture-source-1",
                "supports": "fixture conclusion",
            }
        ]),
        "rationale": "Independent source-backed fixture review.",
        "protocol_deviation": "",
    }


def _benchmark_map() -> dict[str, int]:
    return {"PG-A": 1, "PG-B": 2}


def _responses() -> list[dict]:
    return [
        _response(bid, sequence, slot)
        for bid, sequence in _benchmark_map().items()
        for slot in (1, 2, 3)
    ]


def _blinded_inputs() -> dict:
    return {
        "reviewer_packet_rows": [
            {"benchmark_id": bid, "review_sequence": sequence}
            for bid, sequence in _benchmark_map().items()
        ],
        "reviewer_template_rows": _responses(),
    }


def _baseline() -> list[dict]:
    rows = []
    for index, (bid, sequence) in enumerate(_benchmark_map().items()):
        rows.append({
            "benchmark_id": bid,
            "review_sequence": str(sequence),
            "dsld_id": str(100 + index),
            "archetype": "generic_single_molecule",
            "sample_cohort": "core" if index == 0 else "challenge",
            "analysis_split": "development",
            "quality_score_v4_100": "78",
            "quality_tier": "Acceptable",
            "product_safety_status": "no_known_catalog_concern",
            "pillar_formulation_v4": "15",
            "pillar_dose_v4": "14",
            "pillar_evidence_v4": "13",
            "pillar_transparency_v4": "12",
            "pillar_verification_v4": "11",
            "pillar_safety_hygiene_v4": "9",
        })
    return rows


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_registry_requires_one_fixed_conflict_free_panel():
    panel = validate_reviewer_registry(_registry_rows(), _spec())

    assert tuple(panel) == (1, 2, 3)
    assert panel[1]["reviewer_id"] == "R1"

    conflicted = _registry_rows()
    conflicted[0]["conflicts_json"] = '[{"brand_name":"Example"}]'
    with pytest.raises(AnalysisContractError, match="conflict-free"):
        validate_reviewer_registry(conflicted, _spec())

    rotating = _registry_rows()
    rotating[2]["reviewer_slot"] = "2"
    with pytest.raises(AnalysisContractError, match="slots"):
        validate_reviewer_registry(rotating, _spec())


def test_registry_requires_two_verified_clinical_credentials():
    rows = _registry_rows()
    rows[1]["credential_type"] = "research_scientist"
    rows[1]["license_status"] = "not_applicable"
    rows[1]["license_verification_source"] = ""

    with pytest.raises(AnalysisContractError, match="licensed clinical"):
        validate_reviewer_registry(rows, _spec())


def test_append_only_response_rounds_select_latest_with_reason():
    rows = _responses()
    rows.append(
        _response(
            "PG-A",
            1,
            1,
            overall_adjustment=0.5,
            review_round=2,
            correction_reason="Corrected arithmetic transcription.",
        )
    )

    selected = validate_and_select_responses(
        rows,
        validate_reviewer_registry(_registry_rows(), _spec()),
        _benchmark_map(),
        _spec(),
    )

    assert len(selected) == 6
    corrected = next(
        row for row in selected
        if row["benchmark_id"] == "PG-A" and row["reviewer_slot"] == 1
    )
    assert corrected["review_round"] == 2
    assert corrected["formulation_0_20"] == 16.5

    rows[-1]["correction_reason"] = ""
    with pytest.raises(AnalysisContractError, match="correction_reason"):
        validate_and_select_responses(
            rows,
            validate_reviewer_registry(_registry_rows(), _spec()),
            _benchmark_map(),
            _spec(),
        )


def test_response_validation_fails_closed_on_arithmetic_or_sources():
    rows = _responses()
    rows[0]["overall_0_100"] = "99"
    with pytest.raises(AnalysisContractError, match="pillar sum"):
        validate_and_select_responses(
            rows,
            validate_reviewer_registry(_registry_rows(), _spec()),
            _benchmark_map(),
            _spec(),
        )

    rows = _responses()
    rows[0]["source_citations_json"] = "[]"
    with pytest.raises(AnalysisContractError, match="source citation"):
        validate_and_select_responses(
            rows,
            validate_reviewer_registry(_registry_rows(), _spec()),
            _benchmark_map(),
            _spec(),
        )

    rows = _responses()
    rows[0]["product_safety_status"] = "caution"
    with pytest.raises(AnalysisContractError, match="safety_concern_driver"):
        validate_and_select_responses(
            rows,
            validate_reviewer_registry(_registry_rows(), _spec()),
            _benchmark_map(),
            _spec(),
        )


def test_response_validation_requires_complete_reviewer_order_permutation():
    rows = _responses()
    rows[3]["reviewer_order"] = "1"

    with pytest.raises(AnalysisContractError, match="reviewer_order"):
        validate_and_select_responses(
            rows,
            validate_reviewer_registry(_registry_rows(), _spec()),
            _benchmark_map(),
            _spec(),
        )


def test_icc_absolute_agreement_is_one_for_identical_raters():
    result = icc_absolute_agreement([
        [10.0, 10.0, 10.0],
        [20.0, 20.0, 20.0],
        [30.0, 30.0, 30.0],
    ])

    assert result["icc_a1"] == pytest.approx(1.0)
    assert result["icc_ak"] == pytest.approx(1.0)


def test_analysis_reports_engine_minus_consensus_and_freezes_calibration():
    result = analyze_benchmark(
        _baseline(),
        _responses(),
        _registry_rows(),
        _spec(),
        stage="development",
        **_blinded_inputs(),
    )

    assert result["status"] == "descriptive_only_calibration_frozen"
    assert result["sample"]["analyzed_products"] == 2
    # Reviewer consensus is 77; engine is 78.
    assert result["overall"]["mean_signed_error"] == pytest.approx(1.0)
    assert result["overall"]["mean_absolute_error"] == pytest.approx(1.0)
    assert result["overall"]["signed_error_direction"] == (
        "engine_minus_reviewer_consensus"
    )
    assert result["calibration"]["eligible"] is False


def test_development_analysis_filters_locked_holdout_responses():
    development_baseline = [_baseline()[0]]
    full_responses = _responses()
    spec = _spec()
    spec["primary_design"]["required_ratings"] = 6

    result = analyze_benchmark(
        development_baseline,
        full_responses,
        _registry_rows(),
        spec,
        stage="development",
        **_blinded_inputs(),
    )

    assert result["sample"]["analyzed_products"] == 1
    assert result["sample"]["selected_ratings"] == 3


def test_protocol_deviation_excludes_product_and_keeps_sensitivity_record():
    rows = _responses()
    rows[0]["protocol_deviation"] = "Accidental score exposure."

    result = analyze_benchmark(
        _baseline(),
        rows,
        _registry_rows(),
        _spec(),
        stage="development",
        **_blinded_inputs(),
    )

    assert result["sample"]["analyzed_products"] == 1
    assert result["sample"]["excluded_products"] == 1
    assert result["sample"]["excluded_benchmark_ids"] == ["PG-A"]
    assert result["sensitivity_all_locked_responses"]["products"] == 2


def test_any_more_severe_reviewer_creates_safety_undercall_queue():
    rows = _responses()
    rows[0]["product_safety_status"] = "caution"
    rows[0]["safety_concern_driver"] = (
        "Fixture ingredient at the disclosed dose."
    )

    result = analyze_benchmark(
        _baseline(),
        rows,
        _registry_rows(),
        _spec(),
        stage="development",
        **_blinded_inputs(),
    )

    assert result["safety"]["potential_undercalls"] == 1
    assert result["safety"]["potential_overcalls"] == 0
    assert result["safety"]["requires_blinded_adjudication"] is True
    assert result["safety"]["undercall_queue"] == [
        {
            "benchmark_id": "PG-A",
            "engine_status": "no_known_catalog_concern",
            "reviewer_statuses": [
                "caution",
                "no_known_catalog_concern",
                "no_known_catalog_concern",
            ],
        }
    ]


def test_development_access_guard_rejects_holdout_before_file_read(tmp_path):
    sealed = tmp_path / "SEALED_HOLDOUT_KEY.csv"

    with pytest.raises(AnalysisContractError, match="refuses sealed holdout"):
        assert_baseline_access(sealed, stage="development")
    assert not sealed.exists()


def test_response_lock_detects_post_lock_mutation(tmp_path):
    registry_path = tmp_path / "reviewer_registry.csv"
    responses_path = tmp_path / "responses.csv"
    packet_path = tmp_path / "reviewer_packet.csv"
    template_path = tmp_path / "reviewer_response_template.csv"
    spec_path = tmp_path / "ANALYSIS_SPEC.json"
    script_path = tmp_path / "analysis.py"
    manifest_path = tmp_path / "manifest.json"

    _write_csv(registry_path, _registry_rows())
    _write_csv(responses_path, _responses())
    _write_csv(template_path, _responses())
    _write_csv(
        packet_path,
        [
            {"benchmark_id": bid, "review_sequence": seq}
            for bid, seq in _benchmark_map().items()
        ],
    )
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    script_path.write_text("# frozen fixture\n", encoding="utf-8")
    manifest_path.write_text(json.dumps({
        "freeze_id": "fixture-v1",
        "analysis_contract": {
            "response_contract_version": "2.0.0",
            "analysis_spec_sha256": _sha256(spec_path),
            "analysis_script_sha256": _sha256(script_path),
        },
        "artifacts": {
            "reviewer_packet.csv": {"sha256": _sha256(packet_path)},
            "reviewer_response_template.csv": {"sha256": _sha256(template_path)},
        },
    }), encoding="utf-8")

    lock = build_response_lock(
        manifest_path=manifest_path,
        analysis_spec_path=spec_path,
        analysis_script_path=script_path,
        reviewer_packet_path=packet_path,
        reviewer_template_path=template_path,
        reviewer_registry_path=registry_path,
        responses_path=responses_path,
        locked_on="2026-08-08",
    )
    verify_response_lock(
        lock,
        manifest_path=manifest_path,
        analysis_spec_path=spec_path,
        analysis_script_path=script_path,
        reviewer_packet_path=packet_path,
        reviewer_template_path=template_path,
        reviewer_registry_path=registry_path,
        responses_path=responses_path,
    )

    responses_path.write_text(
        responses_path.read_text() + "\n",
        encoding="utf-8",
    )
    with pytest.raises(AnalysisContractError, match="responses_sha256"):
        verify_response_lock(
            lock,
            manifest_path=manifest_path,
            analysis_spec_path=spec_path,
            analysis_script_path=script_path,
            reviewer_packet_path=packet_path,
            reviewer_template_path=template_path,
            reviewer_registry_path=registry_path,
            responses_path=responses_path,
        )


def test_candidate_lock_requires_approvals_and_expected_direction():
    response_lock = {
        "status": "locked",
        "freeze_id": "fixture-v1",
        "analysis_spec_sha256": "spec-hash",
        "analysis_script_sha256": "script-hash",
    }
    candidate_lock = {
        "status": "locked",
        "freeze_id": "fixture-v1",
        "response_lock_sha256": "response-hash",
        "analysis_spec_sha256": "spec-hash",
        "analysis_script_sha256": "script-hash",
        "approved_by_statistician": "Statistician A, 2026-08-10",
        "approved_by_clinical_owner": "Clinical Owner B, 2026-08-10",
        "candidates": [
            {
                "candidate_id": "candidate-1",
                "implementation_commit": "abc1234",
                "expected_direction": "decrease_engine_score",
                "mechanistic_link": "Correct denominator for one pillar.",
                "changed_parameters": ["generic.evidence.reference"],
                "safety_regression_gate": "must_not_worsen",
            }
        ],
    }

    validate_candidate_lock(
        candidate_lock,
        response_lock=response_lock,
        response_lock_sha256="response-hash",
        spec=_spec(),
    )

    del candidate_lock["candidates"][0]["expected_direction"]
    with pytest.raises(AnalysisContractError, match="expected_direction"):
        validate_candidate_lock(
            candidate_lock,
            response_lock=response_lock,
            response_lock_sha256="response-hash",
            spec=_spec(),
        )
