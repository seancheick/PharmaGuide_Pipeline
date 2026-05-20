"""P1.6.3 — Omega module Evidence dimension.

This is the P1.6.0 SKELETON stub. The real scoring math lands in P1.6.3.

Per scripts/data/omega_rubric.json:
    evidence 20 = generic evidence pipeline with omega-specific canonicals
                  ['epa', 'dha', 'epa_dha'] prioritized for top-N selection
                + indication_relevance bonus (+5 if EPA+DHA >= 1000 mg/day,
                  AHA CVD threshold for cardiovascular indication alignment)

Per §13 architecture lock, this module does not import score_supplements (v3).
"""

from __future__ import annotations

from typing import Any, Dict


def score_evidence(product: Any) -> Dict[str, Any]:
    """P1.6.0 skeleton — returns score=None until P1.6.3 lands."""
    return {
        "score": None,
        "components": {},
        "penalties": {},
        "metadata": {
            "phase": "P1.6.0_skeleton",
            "deferred_to": "P1.6.3_omega_evidence",
        },
    }
