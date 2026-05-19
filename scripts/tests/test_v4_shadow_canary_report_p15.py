"""P1.5 v4 shadow canary comparator tests."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def test_assign_rank_deltas_compares_v4_rank_to_v3_baseline_within_group() -> None:
    from api_audit.v4_shadow_canary_report import assign_rank_deltas

    rows = [
        {"dsld_id": "a", "primary_class": "single_nutrient", "v3_shipped_score": 90, "v4_score": 80},
        {"dsld_id": "b", "primary_class": "single_nutrient", "v3_shipped_score": 80, "v4_score": 95},
        {"dsld_id": "c", "primary_class": "single_nutrient", "v3_shipped_score": 70, "v4_score": 70},
        {"dsld_id": "d", "primary_class": "probiotic", "v3_shipped_score": 60, "v4_score": None},
    ]

    ranked = assign_rank_deltas(rows, group_key="primary_class")
    by_id = {row["dsld_id"]: row for row in ranked}

    assert by_id["a"]["expected_rank_in_group"] == 1
    assert by_id["a"]["actual_rank_in_group"] == 2
    assert by_id["a"]["rank_delta"] == 1
    assert by_id["b"]["expected_rank_in_group"] == 2
    assert by_id["b"]["actual_rank_in_group"] == 1
    assert by_id["b"]["rank_delta"] == -1
    assert by_id["d"]["actual_rank_in_group"] is None
    assert by_id["d"]["rank_delta"] is None


def test_summarize_flags_omega_review_when_rank_drift_exceeds_one() -> None:
    from api_audit.v4_shadow_canary_report import summarize_records

    rows = [
        {
            "dsld_id": "omega-a",
            "primary_class": "fish_oil",
            "v3_shipped_score": 80,
            "v4_score": 50,
            "expected_rank_in_group": 1,
            "actual_rank_in_group": 2,
            "rank_delta": 1,
        },
        {
            "dsld_id": "omega-b",
            "primary_class": "fish_oil",
            "v3_shipped_score": 70,
            "v4_score": 90,
            "expected_rank_in_group": 2,
            "actual_rank_in_group": 1,
            "rank_delta": -1,
        },
        {
            "dsld_id": "omega-c",
            "primary_class": "fish_oil",
            "v3_shipped_score": 60,
            "v4_score": 40,
            "expected_rank_in_group": 3,
            "actual_rank_in_group": 3,
            "rank_delta": 0,
        },
        {
            "dsld_id": "omega-d",
            "primary_class": "fish_oil",
            "v3_shipped_score": 50,
            "v4_score": 95,
            "expected_rank_in_group": 4,
            "actual_rank_in_group": 0,
            "rank_delta": -4,
        },
    ]

    summary = summarize_records(rows)

    assert summary["omega"]["count"] == 4
    assert summary["omega"]["max_abs_rank_delta"] == 4
    assert summary["omega"]["decision"] == "review_omega_module"


def test_summarize_passes_omega_when_rank_order_is_within_one() -> None:
    from api_audit.v4_shadow_canary_report import summarize_records

    rows = [
        {
            "dsld_id": "omega-a",
            "primary_class": "fish_oil",
            "v3_shipped_score": 80,
            "v4_score": 85,
            "expected_rank_in_group": 1,
            "actual_rank_in_group": 1,
            "rank_delta": 0,
            "v4_calibration": {"method": "affine_p15"},
        },
        {
            "dsld_id": "omega-b",
            "primary_class": "fish_oil",
            "v3_shipped_score": 70,
            "v4_score": 65,
            "expected_rank_in_group": 2,
            "actual_rank_in_group": 2,
            "rank_delta": 0,
            "v4_calibration": {"method": "affine_p15"},
        },
    ]

    summary = summarize_records(rows)

    assert summary["omega"]["decision"] == "generic_ok_for_now"
    assert summary["calibration_counts"] == {"affine_p15": 2}


def test_summarize_flags_omega_review_on_large_score_drop_even_when_rank_is_stable() -> None:
    from api_audit.v4_shadow_canary_report import summarize_records

    rows = [
        {
            "dsld_id": "omega-a",
            "primary_class": "fish_oil",
            "v3_shipped_score": 80,
            "v3_shipped_verdict": "SAFE",
            "v4_score": 60,
            "v4_verdict": "SAFE",
            "expected_rank_in_group": 1,
            "actual_rank_in_group": 1,
            "rank_delta": 0,
            "score_delta_vs_v3": -20,
        },
        {
            "dsld_id": "omega-b",
            "primary_class": "fish_oil",
            "v3_shipped_score": 70,
            "v3_shipped_verdict": "SAFE",
            "v4_score": 65,
            "v4_verdict": "SAFE",
            "expected_rank_in_group": 2,
            "actual_rank_in_group": 2,
            "rank_delta": 0,
            "score_delta_vs_v3": -5,
        },
    ]

    summary = summarize_records(rows)

    assert summary["omega"]["decision"] == "review_omega_module"
    assert "large_score_drop" in summary["omega"]["review_reasons"]


def test_summarize_flags_omega_review_on_safe_to_poor_transition() -> None:
    from api_audit.v4_shadow_canary_report import summarize_records

    rows = [
        {
            "dsld_id": "omega-a",
            "primary_class": "fish_oil",
            "v3_shipped_score": 80,
            "v3_shipped_verdict": "SAFE",
            "v4_score": 39,
            "v4_verdict": "POOR",
            "expected_rank_in_group": 1,
            "actual_rank_in_group": 1,
            "rank_delta": 0,
            "score_delta_vs_v3": -41,
        },
        {
            "dsld_id": "omega-b",
            "primary_class": "fish_oil",
            "v3_shipped_score": 70,
            "v3_shipped_verdict": "SAFE",
            "v4_score": 65,
            "v4_verdict": "SAFE",
            "expected_rank_in_group": 2,
            "actual_rank_in_group": 2,
            "rank_delta": 0,
            "score_delta_vs_v3": -5,
        },
    ]

    summary = summarize_records(rows)

    assert summary["omega"]["decision"] == "review_omega_module"
    assert "safe_to_poor_transition" in summary["omega"]["review_reasons"]


def test_mark_missing_canary_when_no_enriched_product_exists() -> None:
    from api_audit.v4_shadow_canary_report import score_canaries

    rows = score_canaries(
        [{"dsld_id": "missing", "primary_class": "single_nutrient", "v3_shipped_score": 50}],
        enriched_index={},
    )

    assert rows[0]["status"] == "missing_enriched"
    assert rows[0]["v4_score"] is None
    assert rows[0]["v4_confidence"] is None


def test_score_canaries_extracts_top_level_shadow_fields() -> None:
    from api_audit.v4_shadow_canary_report import score_canaries

    product = {
        "status": "active",
        "form_factor": "capsule",
        "supplement_type": {"type": "single_nutrient"},
        "ingredient_quality_data": {
            "total_active": 1,
            "ingredients_scorable": [
                {
                    "name": "Magnesium",
                    "standard_name": "Magnesium",
                    "canonical_id": "magnesium",
                    "mapped": True,
                    "quantity": 200,
                    "unit": "mg",
                    "bio_score": 14,
                }
            ],
        },
        "rda_ul_data": {
            "adequacy_results": [{"nutrient": "Magnesium", "pct_rda": 50, "pct_ul": 57}],
            "safety_flags": [],
        },
        "verified_cert_programs": [],
    }

    rows = score_canaries(
        [{"dsld_id": "123", "primary_class": "single_nutrient", "v3_shipped_score": 50}],
        enriched_index={"123": product},
    )

    assert rows[0]["status"] == "scored"
    assert rows[0]["v4_module"] == "generic"
    assert rows[0]["v4_score"] is not None
    assert rows[0]["v4_raw_score"] is not None
    assert rows[0]["v4_score"] == round(25.0 + 0.75 * rows[0]["v4_raw_score"], 1)
    assert rows[0]["v4_calibration"]["method"] == "affine_p15"
    assert rows[0]["v4_confidence"] in {"high", "moderate", "low"}


def test_extract_v3_sections_from_scored_breakdown() -> None:
    from api_audit.v4_shadow_canary_report import extract_v3_sections

    sections = extract_v3_sections(
        {
            "breakdown": {
                "A": {"score": 17.2},
                "B": {"score": 24.5, "bonuses": 0.0, "penalties": 0.5},
                "C": {"score": 4.5},
                "D": {"score": 3.0},
                "violation_penalty": 0.0,
            }
        }
    )

    assert sections == {
        "A": 17.2,
        "B": 24.5,
        "C": 4.5,
        "D": 3.0,
        "E": None,
        "violation_penalty": 0.0,
        "B_bonuses": 0.0,
        "B_penalties": 0.5,
    }


def test_diagnose_compression_flags_missing_v3_safety_base() -> None:
    from api_audit.v4_shadow_canary_report import diagnose_compression

    row = {
        "score_delta_vs_v3": -26.5,
        "v3_sections": {"B": 24.5, "B_bonuses": 0.0, "B_penalties": 0.5},
        "v4_dimensions": {
            "trust": 0.0,
            "transparency": 6.0,
        },
    }

    flags = diagnose_compression(row)

    assert "v3_safety_purity_base_not_represented" in flags


def test_diagnose_compression_flags_not_evaluable_dose_plus_large_drop() -> None:
    from api_audit.v4_shadow_canary_report import diagnose_compression

    row = {
        "score_delta_vs_v3": -26.5,
        "v4_dimensions": {"dose": None},
        "v4_confidence_detail": {
            "label_completeness": {
                "drivers": ["dose_window_not_evaluable_by_rda_proxy"]
            }
        },
    }

    flags = diagnose_compression(row)

    assert "dose_not_evaluable_with_large_score_drop" in flags


def test_score_canaries_attaches_v3_sections_and_compression_flags() -> None:
    from api_audit.v4_shadow_canary_report import score_canaries

    product = {
        "status": "active",
        "form_factor": "capsule",
        "supplement_type": {"type": "single_nutrient"},
        "ingredient_quality_data": {
            "total_active": 1,
            "ingredients_scorable": [
                {
                    "name": "Ashwagandha",
                    "standard_name": "Ashwagandha",
                    "canonical_id": "ashwagandha",
                    "mapped": True,
                    "quantity": 600,
                    "unit": "mg",
                    "bio_score": 14,
                }
            ],
        },
        "rda_ul_data": {
            "adequacy_results": [{"nutrient": "Ashwagandha", "pct_rda": None, "pct_ul": None}],
            "safety_flags": [],
        },
        "verified_cert_programs": [],
    }
    scored = {
        "breakdown": {
            "A": {"score": 17.2},
            "B": {"score": 24.5, "bonuses": 0.0, "penalties": 0.5},
            "C": {"score": 4.5},
            "D": {"score": 3.0},
        }
    }

    rows = score_canaries(
        [{"dsld_id": "123", "primary_class": "herbal_branded_extract", "v3_shipped_score": 61.5}],
        enriched_index={"123": product},
        scored_index={"123": scored},
    )

    assert rows[0]["v3_sections"]["B"] == 24.5
    assert "compression_flags" in rows[0]
    assert "v3_safety_purity_base_not_represented" in rows[0]["compression_flags"]
