"""
P0-1b — UL dose severity must reach the VERDICT, not just the score.

Before this, exceeding a UL was only a (capped) score penalty; a product at 300%
of a hard UL could still ship SAFE. Policy (user-specified):
  - a GATE-ELIGIBLE flag with pct_ul >= 150 → product cannot be SAFE
      - 150–199% → CAUTION
      - >= 200%  → CAUTION + a critical dose signal
  - NEVER BLOCKED/UNSAFE for dose excess (those stay for banned/recalled/adulterated)
  - gate-INELIGIBLE/material flags route to review without exceedance language
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scoring_v4.gate_safety import evaluate_safety_gate


def _prod(flags):
    return {"rda_ul_data": {"safety_flags": flags}}


def test_gate_eligible_over_ul_forces_caution():
    r = evaluate_safety_gate(_prod([{"nutrient": "Vitamin A", "pct_ul": 160, "ul_gate_eligible": True}]))
    assert r.verdict == "CAUTION"


def test_severe_over_ul_emits_critical_dose_signal():
    r = evaluate_safety_gate(_prod([{"nutrient": "Vitamin A", "pct_ul": 250, "ul_gate_eligible": True}]))
    assert r.verdict == "CAUTION"
    assert any("CRITICAL" in s.upper() for s in r.safety_signals), r.safety_signals


def test_gate_ineligible_compound_mass_forces_review_not_exceedance():
    # Compound mass is not a confirmed exceedance, but the unresolved material
    # comparison cannot ship as a clean safety assessment.
    r = evaluate_safety_gate(_prod([{"nutrient": "Magtein", "pct_ul": 571, "ul_gate_eligible": False}]))
    assert r.verdict == "CAUTION"
    assert r.needs_review is True
    assert "DOSE_SAFETY_UNRESOLVED_REVIEW" in r.safety_signals
    assert not any(signal.startswith("DOSE_OVER_UL") for signal in r.safety_signals)


def test_below_150_does_not_force_caution():
    r = evaluate_safety_gate(_prod([{"nutrient": "X", "pct_ul": 120, "ul_gate_eligible": True}]))
    assert r.verdict != "CAUTION"


def test_ul_dose_never_blocks_or_unsafe():
    r = evaluate_safety_gate(_prod([{"nutrient": "X", "pct_ul": 9999, "ul_gate_eligible": True}]))
    assert r.verdict == "CAUTION"  # dose excess never escalates past CAUTION


def test_missing_eligibility_routes_stale_flag_to_review():
    # Older enriched output has no typed eligibility. It cannot assert an
    # exceedance, but it also cannot silently look like a complete clean check.
    r = evaluate_safety_gate(_prod([{"nutrient": "X", "pct_ul": 200}]))
    assert r.verdict == "CAUTION"
    assert r.needs_review is True
    assert r.safety_signals == ["DOSE_SAFETY_UNRESOLVED_REVIEW"]


def test_indeterminate_folate_at_possible_ul_forces_review_caution():
    product = {
        "rda_ul_data": {
            "safety_flags": [],
            "ul_review_flags": [{
                "nutrient": "Folate",
                "assessment_status": "indeterminate",
                "reason": "unknown_folate_form_lineage",
                "potential_pct_ul": 100,
                "review_required": True,
            }],
        }
    }

    result = evaluate_safety_gate(product)

    assert result.verdict == "CAUTION"
    assert result.needs_review is True
    assert "FOLATE_UL_FORM_REVIEW" in result.safety_signals


def test_emergency_use_potassium_iodide_cannot_ship_safe():
    product = {
        "rda_ul_data": {
            "safety_flags": [],
            "special_use_flags": [{
                "code": "POTASSIUM_IODIDE_EMERGENCY_USE_ONLY",
                "ingredient": "Potassium Iodide",
                "amount": 130,
                "unit": "mg",
            }],
        }
    }

    result = evaluate_safety_gate(product)

    assert result.verdict == "CAUTION"
    assert "POTASSIUM_IODIDE_EMERGENCY_USE_ONLY" in result.safety_signals
