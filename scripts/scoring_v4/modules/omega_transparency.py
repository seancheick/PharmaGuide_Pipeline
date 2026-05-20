"""P1.6.5 — Omega module Transparency dimension.

This is the P1.6.0 SKELETON stub. The real scoring math lands in P1.6.5.

Per scripts/data/omega_rubric.json:
    transparency 15 = epa_or_dha_disclosed 5
                    + form_disclosed 3
                    + source_disclosed 3
                    + oxidation_disclosed 2 (future-ready; usually 0 today)
                    + b3_claim_compliance (allergen_free/gluten_free/vegan, cap 4)
                    - b2_allergen / b5_opacity (class-aware) / b6_marketing
                    inherited from generic helpers

Per §13 architecture lock, this module does not import score_supplements (v3).
"""

from __future__ import annotations

from typing import Any, Dict


def score_transparency(product: Any) -> Dict[str, Any]:
    """P1.6.0 skeleton — returns score=None until P1.6.5 lands."""
    return {
        "score": None,
        "components": {},
        "penalties": {},
        "metadata": {
            "phase": "P1.6.0_skeleton",
            "deferred_to": "P1.6.5_omega_transparency",
        },
    }
