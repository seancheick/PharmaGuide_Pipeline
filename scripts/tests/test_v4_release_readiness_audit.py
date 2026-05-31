from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
if str(SCRIPTS_ROOT / "api_audit") not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT / "api_audit"))

from api_audit.v4_release_readiness_audit import classify_row, summarize  # noqa: E402


def _row(**overrides):
    base = {
        "in_shipped_universe": True,
        "v3_verdict": "SAFE",
        "v3_safety_verdict": "SAFE",
        "v4_verdict": "SAFE",
        "v4_raw_score": 60.0,
        "v4_score": 70.0,
        "v4_completeness_missing": [],
        "v4_completeness_soft_missing": [],
        "v4_completeness_score_cap": None,
        "v4_completeness_verdict_ceiling": None,
    }
    base.update(overrides)
    return base


def test_safety_downgrade_is_release_blocker() -> None:
    row = _row(v3_verdict="CAUTION", v3_safety_verdict="CAUTION", v4_verdict="SAFE")

    assert classify_row(row) == "BLOCKER_SAFETY_DOWNGRADE"


def test_not_scored_is_allowed_only_for_no_usable_identity() -> None:
    allowed = _row(v4_verdict="NOT_SCORED", v4_completeness_missing=["active_identity"])
    blocked = _row(v4_verdict="NOT_SCORED", v4_completeness_missing=["dose_with_unit"])

    assert classify_row(allowed) == "OK_NOT_SCORED_NO_USABLE_IDENTITY"
    assert classify_row(blocked) == "BLOCKER_UNEXPLAINED_NOT_SCORED"


def test_score_capped_soft_disclosure_debt_requires_cap_or_ceiling() -> None:
    capped = _row(
        v4_completeness_soft_missing=["low_confidence_omega_breakdown"],
        v4_completeness_score_cap=65.0,
    )
    uncapped = _row(v4_completeness_soft_missing=["low_confidence_omega_breakdown"])

    assert classify_row(capped) == "OK_SCORED_WITH_SOFT_DISCLOSURE_CAP"
    assert classify_row(uncapped) == "BLOCKER_SOFT_DISCLOSURE_WITHOUT_CAP"


def test_blend_anchor_is_audit_tag_not_release_blocker() -> None:
    row = _row(v4_completeness_soft_missing=["conservative_blend_anchor_mass"])

    assert classify_row(row) == "OK_SCORED_WITH_SOFT_AUDIT_TAG"


def test_poor_to_safe_quality_uplift_requires_safe_v3_safety_and_raw_floor() -> None:
    reviewed = _row(
        v3_verdict="POOR",
        v3_safety_verdict="SAFE",
        v4_verdict="SAFE",
        v4_raw_score=44.0,
    )
    blocked = _row(
        v3_verdict="POOR",
        v3_safety_verdict="CAUTION",
        v4_verdict="SAFE",
        v4_raw_score=44.0,
    )

    assert classify_row(reviewed) == "REVIEW_POOR_TO_SAFE_QUALITY_UPLIFT"
    assert classify_row(blocked) == "BLOCKER_SAFETY_DOWNGRADE"


def test_summary_fails_when_any_blocker_present() -> None:
    rows = [
        {"release_classification": "OK_NO_RELEASE_CONCERN"},
        {"release_classification": "REVIEW_POOR_TO_SAFE_QUALITY_UPLIFT"},
        {"release_classification": "BLOCKER_UNEXPLAINED_NOT_SCORED"},
    ]

    out = summarize(rows)

    assert out["ready_for_v4_primary"] is False
    assert out["blocker_total"] == 1
