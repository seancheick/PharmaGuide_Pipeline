from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from audits.v4_absorbed_penalty_report import _quality_tier, analyze_dimension


def test_analyze_dimension_reports_shared_absorption_without_inventing_attribution() -> None:
    finding = analyze_dimension(
        {
            "score": 13.4,
            "max": 15.0,
            "components": {
                "identity_disclosure": 8.0,
                "dose_disclosure": 5.0,
                "claim_compliance": 4.0,
            },
            "penalties": {
                "B2_false_allergen_free_claim": -2.0,
                "B5_proprietary_blend_opacity": -1.6,
            },
        }
    )

    assert finding is not None
    assert finding["gross_positive_credit"] == 17.0
    assert finding["dimension_cap"] == 15.0
    assert finding["total_penalty_amount"] == 3.6
    assert finding["absorbed_amount"] == 2.0
    assert finding["current_dimension_score"] == 13.4
    assert finding["alternative_dimension_score"] == 11.4
    assert finding["penalty_policy_class"] == "contains_never_absorbable_material_defect"
    assert finding["absorption_attribution"] == "shared_headroom_not_uniquely_attributable"
    assert finding["penalties"][0]["absorbed_amount"] is None
    assert finding["penalties"][1]["absorbed_amount"] is None


def test_analyze_dimension_omits_penalty_when_positive_headroom_absorbs_nothing() -> None:
    assert (
        analyze_dimension(
            {
                "score": 11.0,
                "max": 15.0,
                "components": {"disclosure": 12.0},
                "penalties": {"B5_proprietary_blend_opacity": -1.0},
            }
        )
        is None
    )


def test_report_uses_the_production_quality_tier_thresholds() -> None:
    assert _quality_tier(56.1) == "Weak"
    assert _quality_tier(70.0) == "Acceptable"
