"""Regression tests for the v2.2 graduated total_deduction_cap.

Sean explicitly requested:
  * a test proving Pure Vitamins LLC moves from score 75 (Acceptable)
    to score 50 (Concerning) under the new cap;
  * tests proving manufacturers with 0 or 1 Class-I in 3yr stay
    unchanged at the default -25 cap floor.

Source of truth for the cap math:
  scripts/data/manufacture_deduction_expl.json :: total_deduction_cap_graduated
  scripts/score_supplements.py :: _compute_manufacturer_violation_penalty

The constants below MUST mirror that file. Drift is caught by
test_manufacture_deduction_expl_contract.py + this test.
"""

from datetime import date, timedelta
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from score_supplements import SupplementScorer  # noqa: E402


# Band cutoffs per manufacture_deduction_expl.score_thresholds
def _band(score: float) -> str:
    if score >= 85:
        return "Trusted"
    if score >= 70:
        return "Acceptable"
    if score >= 50:
        return "Concerning"
    return "High Risk"


def _today_iso(offset_days: int = 0) -> str:
    return (date.today() - timedelta(days=offset_days)).isoformat()


# ---------------------------------------------------------------------------
# Helper-function unit tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("count,expected_cap", [
    (0, -25.0),
    (1, -25.0),
    (2, -35.0),
    (3, -50.0),
    (4, -50.0),
    (10, -50.0),
])
def test_resolve_manufacturer_cap_tiers(count, expected_cap):
    """The 3-tier mapping: 0-1 → -25, 2 → -35, 3+ → -50."""
    assert SupplementScorer._resolve_manufacturer_cap(count) == expected_cap


def test_count_class_i_in_3_years_basic():
    """Counts only critical-severity entries within last 3 years."""
    items = [
        {"severity_level": "critical", "date": _today_iso(30)},      # in window
        {"severity_level": "critical", "date": _today_iso(365)},     # in window
        {"severity_level": "high",     "date": _today_iso(30)},      # not critical
        {"severity_level": "critical", "date": _today_iso(4 * 365)}, # too old
        {"severity_level": "Critical", "date": _today_iso(60)},      # case-insensitive
    ]
    assert SupplementScorer._count_class_i_in_3_years(items) == 3


def test_count_class_i_handles_malformed_dates():
    """Entries with missing or bad date strings must NOT crash and must NOT count."""
    items = [
        {"severity_level": "critical", "date": "not-a-date"},
        {"severity_level": "critical"},  # missing date
        {"severity_level": "critical", "date": None},
        {"severity_level": "critical", "date": _today_iso(10)},  # valid
    ]
    assert SupplementScorer._count_class_i_in_3_years(items) == 1


# ---------------------------------------------------------------------------
# End-to-end score movement tests — the canonical regression set
# ---------------------------------------------------------------------------


def _mfg_product(violations_list):
    """Build a minimal product dict that exercises
    `_compute_manufacturer_violation_penalty`. We only populate the fields
    that method reads."""
    total = sum(v.get("total_deduction_applied", 0.0) for v in violations_list)
    return {
        "manufacturer_data": {
            "violations": {
                "found": bool(violations_list),
                "total_deduction_applied": total,
                "violations": violations_list,
            }
        }
    }


# Module-scoped scorer to avoid re-init cost; we only call one pure method.
@pytest.fixture(scope="module")
def scorer():
    return SupplementScorer()


def test_pure_vitamins_three_class_i_movement(scorer):
    """SEAN'S REQUESTED REGRESSION: Pure Vitamins LLC has 3 concurrent
    Class-I sildenafil/tadalafil recalls (FDA H-0653/H-0654/H-0655 dated
    2026-03-13, each total_deduction_applied = -23.0, raw aggregate -69).

    Under the old -25 cap: penalty = -25 → score = 100 + (-25) = 75 (Acceptable).
    Under the v2.2 -50 cap: penalty = -50 → score = 100 + (-50) = 50 (Concerning).

    This test pins the exact movement Sean approved in the Phase 2 review.
    If the cap math changes or the deduction values change, this test fails
    loudly with a clear delta — drift is not silent."""
    pure_vitamins = [
        {
            "id": "V082",
            "manufacturer": "Pure Vitamins and Natural Supplements, LLC",
            "severity_level": "critical",
            "violation_code": "CRI_UNDRUG",
            "date": "2026-03-13",
            "total_deduction_applied": -23.0,
            "fda_recall_id": "H-0654-2026",
        },
        {
            "id": "V083",
            "manufacturer": "Pure Vitamins and Natural Supplements, LLC",
            "severity_level": "critical",
            "violation_code": "CRI_UNDRUG",
            "date": "2026-03-13",
            "total_deduction_applied": -23.0,
            "fda_recall_id": "H-0655-2026",
        },
        {
            "id": "V084",
            "manufacturer": "Pure Vitamins and Natural Supplements, LLC",
            "severity_level": "critical",
            "violation_code": "CRI_UNDRUG",
            "date": "2026-03-13",
            "total_deduction_applied": -23.0,
            "fda_recall_id": "H-0653-2026",
        },
    ]
    # Sanity: 3 Class-I in 3yr triggers the -50 tier
    assert SupplementScorer._count_class_i_in_3_years(pure_vitamins) == 3
    assert SupplementScorer._resolve_manufacturer_cap(3) == -50.0

    product = _mfg_product(pure_vitamins)
    penalty = scorer._compute_manufacturer_violation_penalty(product)

    # Penalty must be -50 (capped); the raw -69 is too far for the floor
    assert penalty == -50.0, (
        f"Expected Pure Vitamins LLC penalty to floor at -50 (3+ Class-I "
        f"in 3yr), got {penalty}. The graduated cap may have drifted."
    )

    # Final trust score = 100 + penalty = 50 (Concerning)
    assert _band(100 + penalty) == "Concerning", (
        f"Pure Vitamins LLC should land in Concerning band; computed band "
        f"{_band(100 + penalty)} for score {100 + penalty}."
    )

    # And under the OLD -25 cap they would have been at 75 Acceptable —
    # confirms the change is meaningful, not cosmetic.
    old_cap_penalty = max(sum(v["total_deduction_applied"] for v in pure_vitamins), -25.0)
    assert _band(100 + old_cap_penalty) == "Acceptable", (
        "Under the legacy -25 cap, Pure Vitamins LLC would have scored 75 "
        "Acceptable. If this stops being true, either the cap or the band "
        "thresholds shifted."
    )


def test_zero_class_i_manufacturer_unchanged(scorer):
    """Manufacturers with 0 Class-I in 3yr stay at the default -25 floor.

    Test setup: a manufacturer with one Class-II recall (severity=high)
    producing -10 raw deduction. Both old and new logic should yield the
    same penalty since -10 is well above the -25 floor."""
    one_class_ii = [
        {
            "id": "TEST_V_0CI_A",
            "manufacturer": "Test Manufacturer 0CI",
            "severity_level": "high",   # NOT critical
            "violation_code": "HIGH_CII",
            "date": _today_iso(180),
            "total_deduction_applied": -10.0,
        },
    ]
    assert SupplementScorer._count_class_i_in_3_years(one_class_ii) == 0
    assert SupplementScorer._resolve_manufacturer_cap(0) == -25.0

    product = _mfg_product(one_class_ii)
    penalty = scorer._compute_manufacturer_violation_penalty(product)
    assert penalty == -10.0, (
        f"0-Class-I manufacturer's -10 raw should NOT be capped (cap is -25); "
        f"got {penalty}. Default cap may have changed."
    )
    assert _band(100 + penalty) == "Trusted"


def test_one_class_i_manufacturer_unchanged(scorer):
    """Manufacturers with exactly 1 Class-I in 3yr stay at the default
    -25 floor. This is the most common cohort (49/82 manufacturers as of
    the Phase 2 impact report).

    Setup: one Class-I recall producing -23 raw deduction. Should not be
    affected by graduated cap because count < 2."""
    one_class_i = [
        {
            "id": "TEST_V_1CI_A",
            "manufacturer": "Test Manufacturer 1CI",
            "severity_level": "critical",
            "violation_code": "CRI_UNDRUG",
            "date": _today_iso(60),
            "total_deduction_applied": -23.0,
        },
    ]
    assert SupplementScorer._count_class_i_in_3_years(one_class_i) == 1
    assert SupplementScorer._resolve_manufacturer_cap(1) == -25.0

    product = _mfg_product(one_class_i)
    penalty = scorer._compute_manufacturer_violation_penalty(product)
    # -23 raw is above the -25 floor; passes through uncapped
    assert penalty == -23.0, (
        f"1-Class-I manufacturer's -23 raw should pass through (cap is -25); "
        f"got {penalty}."
    )
    # Score 100 + (-23) = 77 → Acceptable
    assert _band(100 + penalty) == "Acceptable"


def test_two_class_i_manufacturer_hits_minus_35_cap(scorer):
    """Forward-looking — no manufacturer has exactly 2 Class-I in 3yr
    today, but the cap structure must enforce -35 if one ever does.

    Setup: 2 Class-I recalls producing -46 raw deduction (too far for
    even the new tier — caps at -35)."""
    two_class_i = [
        {
            "id": "TEST_V_2CI_A",
            "manufacturer": "Test Manufacturer 2CI",
            "severity_level": "critical",
            "violation_code": "CRI_UNDRUG",
            "date": _today_iso(30),
            "total_deduction_applied": -23.0,
        },
        {
            "id": "TEST_V_2CI_B",
            "manufacturer": "Test Manufacturer 2CI",
            "severity_level": "critical",
            "violation_code": "CRI_UNDRUG",
            "date": _today_iso(180),
            "total_deduction_applied": -23.0,
        },
    ]
    assert SupplementScorer._count_class_i_in_3_years(two_class_i) == 2
    assert SupplementScorer._resolve_manufacturer_cap(2) == -35.0

    product = _mfg_product(two_class_i)
    penalty = scorer._compute_manufacturer_violation_penalty(product)
    assert penalty == -35.0, (
        f"2-Class-I manufacturer's -46 raw should floor at -35; got {penalty}."
    )
    # Score 100 + (-35) = 65 → Concerning
    assert _band(100 + penalty) == "Concerning"


def test_old_class_i_outside_3yr_window_does_not_trigger_graduated_cap(scorer):
    """Class-I violations older than 3 years are still counted in the
    aggregate deduction (via recency-decayed total_deduction_applied)
    but do NOT contribute to the Class-I-in-3yr count that drives the
    graduated cap. This protects manufacturers from being permanently
    penalized for a single old recall."""
    old_class_i = [
        {
            "id": "TEST_V_OLD_A",
            "manufacturer": "Test Manufacturer Old",
            "severity_level": "critical",
            "violation_code": "CRI_TOXIC",
            "date": _today_iso(5 * 365),   # 5 years old
            "total_deduction_applied": -5.0,  # recency-decayed
        },
        {
            "id": "TEST_V_OLD_B",
            "manufacturer": "Test Manufacturer Old",
            "severity_level": "critical",
            "violation_code": "CRI_TOXIC",
            "date": _today_iso(4 * 365),   # 4 years old
            "total_deduction_applied": -5.0,
        },
        {
            "id": "TEST_V_OLD_C",
            "manufacturer": "Test Manufacturer Old",
            "severity_level": "critical",
            "violation_code": "CRI_TOXIC",
            "date": _today_iso(6 * 365),   # 6 years old
            "total_deduction_applied": -5.0,
        },
    ]
    # All Class-I but all outside the 3-year lookback window
    assert SupplementScorer._count_class_i_in_3_years(old_class_i) == 0
    # So the default -25 cap applies even though there are 3 Class-I total
    assert SupplementScorer._resolve_manufacturer_cap(0) == -25.0

    product = _mfg_product(old_class_i)
    penalty = scorer._compute_manufacturer_violation_penalty(product)
    # Total -15, above -25, passes through
    assert penalty == -15.0


# ---------------------------------------------------------------------------
# JSON consistency check — the cap values in score_supplements.py MUST
# match scripts/data/manufacture_deduction_expl.json. A drift here means
# either the JSON or the Python constants got edited without the other.
# ---------------------------------------------------------------------------


def test_python_cap_constants_match_json_source_of_truth():
    """The graduated cap values in SupplementScorer must mirror the JSON.
    This is the drift-prevention contract between the data file and the
    code that consumes it."""
    import json
    path = Path(__file__).parent.parent / "data" / "manufacture_deduction_expl.json"
    blob = json.loads(path.read_text())
    graduated = blob.get("total_deduction_cap_graduated", {})
    assert graduated, (
        "manufacture_deduction_expl.json must carry total_deduction_cap_graduated "
        "block (added in v2.2). Missing block means the JSON was downgraded or "
        "the Python constants are ahead of the data file."
    )
    assert graduated.get("default") == SupplementScorer._MFG_CAP_DEFAULT
    assert graduated.get("two_class_i_in_3_years") == SupplementScorer._MFG_CAP_TWO_CLASS_I
    assert graduated.get("three_or_more_class_i_in_3_years") == SupplementScorer._MFG_CAP_THREE_OR_MORE_CLASS_I
