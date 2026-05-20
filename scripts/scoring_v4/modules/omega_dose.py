"""P1.6.2 — Omega module Dose dimension.

This is the P1.6.0 SKELETON stub. The real scoring math lands in P1.6.2.

Per scripts/data/omega_rubric.json:
    dose 25 = epa_dha_band (/20, lifted from scoring_config omega3_dose_bonus.bands)
            + ratio_sanity (/5, EPA:DHA in 1:3..3:1 range)

Per §13 architecture lock, this module does not import score_supplements (v3).
The v3 omega3_dose_bonus formulas are independently reimplemented here.
"""

from __future__ import annotations

from typing import Any, Dict


def score_dose(product: Any) -> Dict[str, Any]:
    """P1.6.0 skeleton — returns score=None until P1.6.2 lands."""
    return {
        "score": None,
        "components": {},
        "penalties": {},
        "metadata": {
            "phase": "P1.6.0_skeleton",
            "deferred_to": "P1.6.2_omega_dose",
        },
    }
