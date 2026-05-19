"""v4 shadow scorer entry point.

Per the architecture lock in `docs/plans/SCORING_V4_PROPOSAL.md` §13:
this is a SEPARATE scoring entry point from `score_supplements.py`. v3
remains production truth through the entire v4 build; this module
emits `shadow_score_v4_*` columns side-by-side. Cutover to v4 happens
at §19 P5 as a config decision, not a scorer rewrite.

Shared with v3: the enriched input contract from `enrich_supplements_v3.py`,
plus stable shared helpers (cert_resolver, enhanced_normalizer lookups).
NOT shared: the scoring policy itself — `scoring_v4/` owns rubrics,
gates, modules, and confidence rules independently.

At P1.0 (this commit) — scaffold only:
  - Router runs and decides the module (generic / probiotic / multi_or_prenatal).
  - shadow_score_v4_100 = None
  - shadow_score_v4_verdict = None
  - shadow_score_v4_confidence = "skeleton"
  - shadow_score_v4_breakdown = {}
  - shadow_score_v4_anchored = False

Subsequent phases (per §19 P1.x slices):
  P1.1 — safety gate (Layer 1) short-circuits BLOCKED/UNSAFE/CAUTION.
  P1.2 — completeness gate (Layer 2) flags NOT_SCORED on class-specific
         field absence.
  P1.3 — generic module + rubric (5 v4 dimensions: Formulation 25 /
         Dose 25 / Evidence 20 / Trust 15 / Transparency 15).
  P1.4 — confidence typed sub-categories (Layer 4): high / moderate /
         low / insufficient_data.
  P1.5 — wire the whole pipeline; canary rank-order check on rows 1-9
         and 19-24 of the v4 spec canary set.

This module never mutates the input product dict. It returns a fresh
shadow-column dict that the caller (build_final_db.py or the scoring
batch driver) merges into the scored output.
"""

from __future__ import annotations

from typing import Any, Dict

from scoring_v4.gate_safety import evaluate_safety_gate
from scoring_v4.router import class_for_product


# Schema lock — these are the six shadow columns documented in §14 of
# SCORING_V4_PROPOSAL.md. Order and names are part of the public contract
# (Flutter / audit / score-delta tooling reads against this shape).
SHADOW_KEYS = (
    "shadow_score_v4_100",
    "shadow_score_v4_module",
    "shadow_score_v4_verdict",
    "shadow_score_v4_confidence",
    "shadow_score_v4_breakdown",
    "shadow_score_v4_anchored",
)


def _empty_shadow(module: str) -> Dict[str, Any]:
    """Skeleton shadow output — module routed, but no scoring math yet.
    Subsequent slices fill the score/breakdown in.
    """
    return {
        "shadow_score_v4_100": None,
        "shadow_score_v4_module": module,
        "shadow_score_v4_verdict": None,
        "shadow_score_v4_confidence": "skeleton",
        "shadow_score_v4_breakdown": {},
        "shadow_score_v4_anchored": False,
    }


def _safety_gate_breakdown(safety_result) -> Dict[str, Any]:
    """Render the safety-gate result into the shadow breakdown dict.
    Carries explainability fields for the Flutter UI + audit reports."""
    return {
        "verdict": safety_result.verdict,
        "blocking_reason": safety_result.blocking_reason,
        "matched_substance": safety_result.matched_substance,
        "safety_signals": list(safety_result.safety_signals),
        "needs_review": safety_result.needs_review,
        "short_circuits_scoring": safety_result.short_circuits_scoring,
    }


def score_product_v4_shadow(enriched_product: Dict[str, Any]) -> Dict[str, Any]:
    """Score an enriched product against the v4 shadow scorer.

    Returns a dict of the six shadow columns. Never raises on malformed
    input — robustly falls back to the generic module + skeleton shape.

    Pipeline (per §4 of SCORING_V4_PROPOSAL.md):
      1. Router decides module (generic / probiotic / multi_or_prenatal).
      2. Layer 1 Safety Gate. BLOCKED/UNSAFE short-circuit scoring
         (score=None, confidence='blocked_by_safety_gate'). CAUTION
         sets verdict but scoring continues.
      3. Layer 2 Completeness Gate. [P1.2 — not online yet]
      4. Layer 3 Scoring (per-module). [P1.3 — not online yet]
      5. Layer 4 Confidence. [P1.4 — not online yet]

    Note on `shadow_score_v4_anchored`: per §14, this flag means the
    product is in the §12 canary set — NOT that the safety gate is
    final. Safety-gate finality is captured by
    `breakdown.safety_gate.short_circuits_scoring` + the
    `blocked_by_safety_gate` confidence value. The canary-membership
    decision belongs to a later slice; until then `anchored=False`
    for every product.

    Args:
        enriched_product: A product dict as produced by
            `enrich_supplements_v3.py`. Same contract as v3's
            `SupplementScorer.score_product()` consumes.

    Returns:
        Dict with exactly the six SHADOW_KEYS. The caller is responsible
        for merging this into the scored-product blob (or persisting as
        side-by-side columns in pharmaguide_core.db).
    """
    if not isinstance(enriched_product, dict):
        enriched_product = {}

    module = class_for_product(enriched_product)
    shadow = _empty_shadow(module)

    # Layer 1 — Safety Gate.
    safety = evaluate_safety_gate(enriched_product)
    shadow["shadow_score_v4_breakdown"]["safety_gate"] = _safety_gate_breakdown(safety)

    if safety.short_circuits_scoring:
        # BLOCKED / UNSAFE — final decision, no scoring math runs.
        # `anchored` stays False — per §14 it's reserved for canary-set
        # membership; safety-gate finality lives in the breakdown
        # (`safety_gate.short_circuits_scoring`) + the confidence value.
        shadow["shadow_score_v4_verdict"] = safety.verdict
        shadow["shadow_score_v4_confidence"] = "blocked_by_safety_gate"
        return shadow

    if safety.verdict == "CAUTION":
        # CAUTION carries forward but does not short-circuit. Scoring
        # math still runs in P1.3+; the verdict will be reconciled with
        # the score-band rules (CAUTION > POOR > SAFE) at output time.
        shadow["shadow_score_v4_verdict"] = "CAUTION"

    # Layer 2 / 3 / 4 not online yet — return skeleton.
    return shadow
