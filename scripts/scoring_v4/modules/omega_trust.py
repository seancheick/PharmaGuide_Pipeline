"""P1.6.4 — Omega module Trust dimension.

This is the P1.6.0 SKELETON stub. The real scoring math lands in P1.6.4.

Per scripts/data/omega_rubric.json and Sean's 2026-05-20 policy:
    trust 15 = b4a (IFOS sku/product_line = 10; needs_review/brand_only/
                    claimed_only/rejected = 0)
             + b4b GMP (nsf_gmp 4 / fda_registered 2 / self_attested 0, cap 4)
             + b4c traceability (1 point if has_coa OR has_batch_lookup)
             hard-clamped to 15

CRITICAL: needs_review and brand_only scopes stay 0. Per Sean's directive,
uncertainty is NOT credit. P1.7 curated overrides convert specific rows
into product_line or rejected; this dimension reads the resolved scope.

Per §13 architecture lock, this module does not import score_supplements (v3).
"""

from __future__ import annotations

from typing import Any, Dict


def score_trust(product: Any) -> Dict[str, Any]:
    """P1.6.0 skeleton — returns score=None until P1.6.4 lands."""
    return {
        "score": None,
        "components": {},
        "penalties": {},
        "metadata": {
            "phase": "P1.6.0_skeleton",
            "deferred_to": "P1.6.4_omega_trust",
        },
    }
