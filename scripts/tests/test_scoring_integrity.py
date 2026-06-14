"""Unit tests for the V4 scoring-anomaly detection functions.

These cover the pure DataFrame->DataFrame helpers behind the Scoring Integrity
and Module Health dashboard views, so the anomaly logic is verified without a
populated DB or a running Streamlit.
"""
import pandas as pd

from scripts.dashboard.views.scoring_integrity import (
    find_reconciliation_mismatches,
    find_zero_pillars,
    find_out_of_range,
    pillars_present,
)
from scripts.dashboard.views.module_health import module_pillar_summary


# Six pillar columns: formulation 20, dose 20, evidence 20, transparency 15,
# verification 15, safety_hygiene 10 (= 100).
def _row(dsld, total, f, d, e, t, v, s, module="generic", status="scored"):
    return {
        "dsld_id": dsld, "product_name": f"P{dsld}", "brand_name": "B",
        "v4_module": module, "quality_score_status": status,
        "score_v4": total, "score": total, "quality_score_v4_100": total,
        "pillar_formulation_v4": f, "pillar_dose_v4": d, "pillar_evidence_v4": e,
        "pillar_transparency_v4": t, "pillar_verification_v4": v,
        "pillar_safety_hygiene_v4": s,
    }


def _frame(rows):
    return pd.DataFrame(rows)


def test_reconciliation_passes_when_pillars_sum_to_total():
    # 11.2+20+18.9+15+6+10 = 81.1
    df = _frame([_row("1", 81.1, 11.2, 20.0, 18.9, 15.0, 6.0, 10.0)])
    assert find_reconciliation_mismatches(df).empty


def test_reconciliation_flags_when_pillars_do_not_sum():
    # pillars sum to 81.1 but total claims 90.0 -> mismatch
    df = _frame([_row("1", 90.0, 11.2, 20.0, 18.9, 15.0, 6.0, 10.0)])
    out = find_reconciliation_mismatches(df)
    assert len(out) == 1
    assert abs(out.iloc[0]["recon_delta"] - (81.1 - 90.0)) < 0.01


def test_reconciliation_respects_tolerance():
    # off by 0.05 — within default 0.1 tolerance -> not flagged
    df = _frame([_row("1", 81.15, 11.2, 20.0, 18.9, 15.0, 6.0, 10.0)])
    assert find_reconciliation_mismatches(df).empty


def test_zero_pillars_detects_exact_zero():
    df = _frame([
        _row("1", 71.1, 0.0, 20.0, 18.9, 15.0, 6.0, 10.0),   # formulation 0
        _row("2", 81.1, 11.2, 20.0, 18.9, 15.0, 6.0, 10.0),  # clean
    ])
    zeros = find_zero_pillars(df)
    assert len(zeros) == 1
    assert zeros.iloc[0]["pillar"] == "Formulation"
    assert zeros.iloc[0]["dsld_id"] == "1"


def test_zero_pillars_empty_when_none_zero():
    df = _frame([_row("1", 81.1, 11.2, 20.0, 18.9, 15.0, 6.0, 10.0)])
    assert find_zero_pillars(df).empty


def test_zero_pillars_flags_verification_zero_as_anomaly():
    # Verification is the only fail-open pillar (neutral_baseline 6.0), so it can
    # never legitimately reach 0 — a 0 here is a true anomaly.
    df = _frame([_row("1", 65.1, 11.2, 20.0, 18.9, 15.0, 0.0, 10.0)])  # verification 0
    zeros = find_zero_pillars(df)
    assert len(zeros) == 1
    assert zeros.iloc[0]["pillar"] == "Verification"
    assert bool(zeros.iloc[0]["is_anomaly"]) is True


def test_zero_pillars_marks_non_failopen_zero_as_legitimate_low():
    # formulation/dose/evidence/transparency/safety_hygiene legitimately reach 0
    # (basic forms, off-range dose, no clinical evidence, opaque blend, flagged
    # ingredient) — these are low scores, not bugs.
    df = _frame([_row("1", 71.1, 0.0, 20.0, 18.9, 15.0, 6.0, 10.0)])  # formulation 0
    zeros = find_zero_pillars(df)
    assert len(zeros) == 1
    assert zeros.iloc[0]["pillar"] == "Formulation"
    assert bool(zeros.iloc[0]["is_anomaly"]) is False


def test_zero_pillars_safety_hygiene_zero_is_legitimate_low():
    # safety_hygiene == 0 is a real safety signal (flagged ingredient), not a bug.
    df = _frame([_row("1", 71.1, 11.2, 20.0, 18.9, 15.0, 6.0, 0.0)])  # safety_hygiene 0
    zeros = find_zero_pillars(df)
    assert len(zeros) == 1
    assert zeros.iloc[0]["pillar"] == "Safety & Hygiene"
    assert bool(zeros.iloc[0]["is_anomaly"]) is False


def test_out_of_range_flags_pillar_over_max():
    df = _frame([_row("1", 85.0, 25.0, 20.0, 18.9, 15.0, 6.0, 10.0)])  # formulation 25 > 20
    out = find_out_of_range(df)
    assert len(out) == 1
    assert "Formulation > 20" in out.iloc[0]["issues"]


def test_out_of_range_flags_negative_and_total_off_range():
    df = _frame([_row("1", 120.0, -1.0, 20.0, 18.9, 15.0, 6.0, 10.0)])
    out = find_out_of_range(df)
    assert len(out) == 1
    assert "Formulation < 0" in out.iloc[0]["issues"]
    assert "total outside [0,100]" in out.iloc[0]["issues"]


def test_out_of_range_flags_scored_but_null_pillar():
    rows = [_row("1", 81.1, 11.2, 20.0, 18.9, 15.0, 6.0, 10.0)]
    df = _frame(rows)
    df.loc[0, "pillar_dose_v4"] = None  # scored but dose NULL
    out = find_out_of_range(df)
    assert len(out) == 1
    assert "scored but Dose is NULL" in out.iloc[0]["issues"]


def test_out_of_range_clean_frame_is_empty():
    df = _frame([_row("1", 81.1, 11.2, 20.0, 18.9, 15.0, 6.0, 10.0)])
    assert find_out_of_range(df).empty


def test_pillars_present_true_false():
    df = _frame([_row("1", 81.1, 11.2, 20.0, 18.9, 15.0, 6.0, 10.0)])
    assert pillars_present(df) is True
    empty = df.copy()
    for c in ["pillar_formulation_v4", "pillar_dose_v4", "pillar_evidence_v4",
              "pillar_transparency_v4", "pillar_verification_v4", "pillar_safety_hygiene_v4"]:
        empty[c] = None
    assert pillars_present(empty) is False


def test_module_pillar_summary_groups_and_means():
    df = _frame([
        _row("1", 80.0, 10.0, 20.0, 18.0, 15.0, 7.0, 10.0, module="omega"),
        _row("2", 90.0, 20.0, 20.0, 20.0, 15.0, 5.0, 10.0, module="omega"),
        _row("3", 70.0, 10.0, 10.0, 18.0, 15.0, 7.0, 10.0, module="generic"),
    ])
    summary = module_pillar_summary(df)
    assert set(summary["v4_module"]) == {"omega", "generic"}
    omega = summary[summary["v4_module"] == "omega"].iloc[0]
    assert omega["products"] == 2
    assert omega["Formulation"] == 15.0  # (10+20)/2
    assert omega["mean_total"] == 85.0
