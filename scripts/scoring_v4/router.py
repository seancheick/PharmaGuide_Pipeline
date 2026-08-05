"""Thin public adapter for the canonical ScoringClassification route.

All routing policy lives in :mod:`scoring_input_contract`.  Keeping a second
regex-and-threshold implementation here created a false parity signal: the
production contract and its supposed baseline could drift together or require
the same fix twice.  Callers retain the stable ``class_for_product`` interface
without a second routing brain.
"""

from __future__ import annotations

from typing import Any, Dict

from scoring_input_contract import (
    SCORING_ROUTE_MODULES,
    build_scoring_classification,
)


VALID_CLASSES = (
    "generic",
    "probiotic",
    "multi_or_prenatal",
    "b_complex",
    "omega",
    "sports",
    "fiber_digestive",
)

if set(VALID_CLASSES) != set(SCORING_ROUTE_MODULES):  # pragma: no cover
    raise RuntimeError("router classes drifted from ScoringClassification")


def class_for_product(product: Dict[str, Any]) -> str:
    """Return the product's canonical v4 scoring module.

    The classification contract is total and normally returns a valid route.
    This adapter retains a defensive generic fallback for malformed direct
    callers without seeding or duplicating classification policy.
    """
    try:
        result = build_scoring_classification(product).get("route_module")
    except Exception:  # pragma: no cover - total public API boundary
        return "generic"
    return result if result in VALID_CLASSES else "generic"
