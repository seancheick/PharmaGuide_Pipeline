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
        },
        {
            "dsld_id": "omega-b",
            "primary_class": "fish_oil",
            "v3_shipped_score": 70,
            "v4_score": 65,
            "expected_rank_in_group": 2,
            "actual_rank_in_group": 2,
            "rank_delta": 0,
        },
    ]

    summary = summarize_records(rows)

    assert summary["omega"]["decision"] == "generic_ok_for_now"


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
    assert rows[0]["v4_confidence"] in {"high", "moderate", "low"}
