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

    The classification contract is total (malformed products classify
    ``generic`` on their own), so a failure here is a classifier defect and
    surfaces instead of silently scoring the product on the generic route.
    """
    result = build_scoring_classification(product).get("route_module")
    if result not in VALID_CLASSES:
        raise RuntimeError(f"ScoringClassification returned unknown route {result!r}")
    return result
