"""Contract tests for the blinded V4 reviewer benchmark freeze."""

from __future__ import annotations

import os
import sys
from collections import Counter


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from audits.v4_reviewer_benchmark_freeze import (  # noqa: E402
    FORBIDDEN_REVIEWER_FIELDS,
    _select_core,
    build_benchmark_freeze,
    prepare_benchmark_output_dir,
    reconciled_public_score,
    safe_csv_cell,
)


def _catalog_row(
    dsld_id: str,
    archetype: str,
    index: int,
) -> dict:
    tiers = ("Poor", "Weak", "Acceptable", "Strong", "Excellent", "Elite")
    score = (52, 58, 72, 82, 92, 97)[index % len(tiers)]
    return {
        "dsld_id": dsld_id,
        "product_name": f"Product {dsld_id}",
        "brand_name": f"Brand {index % 3}",
        "archetype": archetype,
        "quality_score_v4_100": score,
        "quality_tier": tiers[index % len(tiers)],
        "quality_score_status": "scored",
        "product_safety_status": (
            "caution" if index % 5 == 0 else "no_known_catalog_concern"
        ),
        "quality_assessment_status": "complete",
        "v4_confidence": ("low", "moderate", "high")[index % 3],
        "pillar_formulation_v4": 10.0,
        "pillar_dose_v4": 11.0,
        "pillar_evidence_v4": 0.0 if index % 2 == 0 else 12.0,
        "pillar_transparency_v4": 9.0,
        "pillar_verification_v4": 6.0,
        "pillar_safety_hygiene_v4": 10.0,
        "score_model_version": "v4",
        "quality_score_version": "test",
        "scoring_engine_version": "test",
        "classification_schema_version": "test",
        "v4_config_fingerprint": "test-fingerprint",
    }


def _detail_row(dsld_id: str) -> dict:
    return {
        "dsld_id": dsld_id,
        "product_name": f"Product {dsld_id}",
        "brand_name": "Visible Brand",
        "serving_info": {
            "basis_count": 1,
            "basis_unit": "capsule",
            "min_servings_per_day": 1,
            "max_servings_per_day": 2,
        },
        "ingredients": [
            {
                "name": "Example Active",
                "source_label_name": "Example Active",
                "quantity": 500,
                "unit": "mg",
                "dailyValue": None,
                "role": "active",
            }
        ],
        "inactive_ingredients": [{"name": "Rice Flour"}],
        "certification_detail": {
            "third_party_programs": {
                "programs": ["USP"],
                "count": 1,
            },
            "gmp": {
                "claimed": True,
                "gmp_certified_or_compliant": False,
            },
            "purity_verified": False,
            "heavy_metal_tested": False,
            "label_accuracy_verified": False,
        },
        "proprietary_blend": False,
        "proprietary_blend_detail": {
            "has_proprietary_blends": True,
            "blends": [
                {
                    "name": "Example Blend",
                    "disclosure_level": "partial",
                    "total_weight": 500,
                    "unit": "mg",
                    "hidden_count": 2,
                    "child_ingredients": [
                        {"name": "Alpha", "amount": None, "unit": ""},
                        {"name": "Beta", "amount": None, "unit": ""},
                    ],
                    "evidence": {
                        "penalty_applicable": -10,
                        "penalty_reason": "scorer-only",
                    },
                }
            ],
        },
    }


def _fixture_inputs() -> tuple[list[dict], dict[str, dict]]:
    catalog: list[dict] = []
    details: dict[str, dict] = {}
    for archetype_index, archetype in enumerate(("alpha", "beta")):
        for index in range(12):
            dsld_id = str(archetype_index * 100 + index + 1)
            catalog.append(_catalog_row(dsld_id, archetype, index))
            details[dsld_id] = _detail_row(dsld_id)
    return catalog, details


def test_freeze_is_balanced_deterministic_and_has_no_overlap():
    catalog, details = _fixture_inputs()

    first = build_benchmark_freeze(
        catalog,
        details,
        seed="benchmark-v1",
        freeze_id="2026-08-06-v1",
        per_archetype=4,
        core_per_archetype=2,
        tier_thresholds=[55, 70, 80, 90, 95],
    )
    second = build_benchmark_freeze(
        reversed(catalog),
        details,
        seed="benchmark-v1",
        freeze_id="2026-08-06-v1",
        per_archetype=4,
        core_per_archetype=2,
        tier_thresholds=[55, 70, 80, 90, 95],
    )

    assert [row["benchmark_id"] for row in first["baseline_key"]] == [
        row["benchmark_id"] for row in second["baseline_key"]
    ]
    assert Counter(
        row["archetype"] for row in first["baseline_key"]
    ) == {"alpha": 4, "beta": 4}
    assert Counter(
        (row["archetype"], row["sample_cohort"])
        for row in first["baseline_key"]
    ) == {
        ("alpha", "core"): 2,
        ("alpha", "challenge"): 2,
        ("beta", "core"): 2,
        ("beta", "challenge"): 2,
    }
    assert len({
        row["dsld_id"] for row in first["baseline_key"]
    }) == 8
    assert Counter(
        (row["archetype"], row["analysis_split"])
        for row in first["baseline_key"]
    ) == {
        ("alpha", "development"): 2,
        ("alpha", "holdout"): 2,
        ("beta", "development"): 2,
        ("beta", "holdout"): 2,
    }


def test_reviewer_packet_is_blinded_and_baseline_retains_engine_outputs():
    catalog, details = _fixture_inputs()

    freeze = build_benchmark_freeze(
        catalog,
        details,
        seed="benchmark-v1",
        freeze_id="2026-08-06-v1",
        per_archetype=4,
        core_per_archetype=2,
        tier_thresholds=[55, 70, 80, 90, 95],
    )

    assert len(freeze["reviewer_packet"]) == len(freeze["baseline_key"])
    for row in freeze["reviewer_packet"]:
        assert not (set(row) & FORBIDDEN_REVIEWER_FIELDS)
        assert row["benchmark_id"].startswith("PG-")
        assert row["active_ingredients_json"]
        assert row["serving_info_json"]
        blend_facts = row["proprietary_blend_facts_json"]
        assert '"has_proprietary_blends":true' in blend_facts
        assert "penalty_applicable" not in blend_facts
        assert "penalty_reason" not in blend_facts
    for row in freeze["baseline_key"]:
        assert row["dsld_id"]
        assert row["quality_score_v4_100"] is not None
        assert row["quality_tier"]
        assert row["pillar_evidence_v4"] is not None


def test_challenge_flags_are_explicit_and_holdout_is_one_core_one_challenge():
    catalog, details = _fixture_inputs()

    freeze = build_benchmark_freeze(
        catalog,
        details,
        seed="benchmark-v1",
        freeze_id="2026-08-06-v1",
        per_archetype=4,
        core_per_archetype=2,
        tier_thresholds=[55, 70, 80, 90, 95],
    )

    for archetype in ("alpha", "beta"):
        rows = [
            row
            for row in freeze["baseline_key"]
            if row["archetype"] == archetype
        ]
        challenge = [
            row for row in rows if row["sample_cohort"] == "challenge"
        ]
        assert all(row["challenge_flags"] for row in challenge)
        holdout = [
            row for row in rows if row["analysis_split"] == "holdout"
        ]
        assert Counter(row["sample_cohort"] for row in holdout) == {
            "core": 1,
            "challenge": 1,
        }


def test_missing_detail_or_insufficient_archetype_fails_closed():
    catalog, details = _fixture_inputs()
    details.pop("1")

    try:
        build_benchmark_freeze(
            catalog,
            details,
            seed="benchmark-v1",
            freeze_id="2026-08-06-v1",
            per_archetype=12,
            core_per_archetype=6,
            tier_thresholds=[55, 70, 80, 90, 95],
        )
    except ValueError as exc:
        assert "eligible products" in str(exc) or "detail" in str(exc)
    else:
        raise AssertionError("benchmark freeze accepted incomplete inputs")


def test_explicit_score_cap_reconciles_pillars_to_public_score():
    pillars = [11.2, 20.0, 17.2, 4.5, 15.0, 6.0]
    cap = {
        "id": "sports_opaque_stimulant",
        "cap": 65.0,
        "applied": True,
        "score_before_cap": 73.9,
        "score_after_cap": 65.0,
        "adjustment": -8.9,
    }

    assert reconciled_public_score(pillars, cap) == 65
    assert reconciled_public_score(pillars, None) == 74


def test_freeze_output_directory_cannot_be_overwritten(tmp_path):
    output = tmp_path / "freeze"

    prepare_benchmark_output_dir(output)
    assert output.is_dir()

    try:
        prepare_benchmark_output_dir(output)
    except FileExistsError as exc:
        assert "immutable" in str(exc)
    else:
        raise AssertionError("existing benchmark freeze was overwritten")


def test_spreadsheet_formula_payloads_are_rendered_inert():
    assert safe_csv_cell("=HYPERLINK(\"https://example.test\")") == (
        "'=HYPERLINK(\"https://example.test\")"
    )
    assert safe_csv_cell("+1+1") == "'+1+1"
    assert safe_csv_cell("\n=1+1") == "'\n=1+1"
    assert safe_csv_cell("5-HTP") == "5-HTP"
    assert safe_csv_cell(-8.9) == -8.9


def test_core_includes_rare_high_confidence_when_available():
    rows = [
        {
            "dsld_id": "low",
            "quality_tier": "Weak",
            "v4_confidence": "low",
        },
        {
            "dsld_id": "moderate",
            "quality_tier": "Weak",
            "v4_confidence": "moderate",
        },
        {
            "dsld_id": "high",
            "quality_tier": "Weak",
            "v4_confidence": "high",
        },
    ]

    selected = _select_core(
        rows,
        1,
        seed="benchmark-v1",
        archetype="alpha",
    )

    assert [row["dsld_id"] for row in selected] == ["high"]
