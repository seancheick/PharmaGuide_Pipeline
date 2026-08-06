"""Production v4 scoring package.

The operational Stage-3 entry point is ``score_products_v4.py``. It invokes
``score_supplements_v4.py`` once per enriched product and emits the canonical
six-pillar artifact consumed by final export. This package owns v4 gates,
modules, rubrics, confidence, and the thin public route adapter; the actual
routing policy has one source of truth in ``scoring_input_contract.py``.
"""

__all__ = ["router", "gate_safety", "gate_completeness", "confidence", "modules"]
