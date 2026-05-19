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

Current P1.4 state:
  - Router runs and decides the module (generic / probiotic / multi_or_prenatal).
  - Safety gate short-circuits BLOCKED / UNSAFE and carries CAUTION forward.
  - Completeness gate marks unscoreable rows NOT_SCORED for archive / QA.
  - Generic module emits populated generic dimensions plus manufacturer
    trust / violations and a final 0-100 score.
  - shadow_score_v4_100 mirrors the generic module result for complete
    generic products.
  - shadow_score_v4_confidence = top-level typed confidence band for
    complete generic rows; blocked_by_* for gate failures.
  - shadow_score_v4_breakdown.confidence contains typed sub-category
    levels / drivers for evidence, label_completeness, verification, identity.
  - shadow_score_v4_anchored = False (canary-set membership lands later).

Subsequent phases (per §19 P1.x slices):
  P1.1 — safety gate (Layer 1) short-circuits BLOCKED/UNSAFE/CAUTION.   [done]
  P1.2 — completeness gate (Layer 2) flags NOT_SCORED on class-specific
         field absence.                                                  [done]
  P1.3.0 — generic-module scaffold + breakdown contract.                 [done]
  P1.3.1 — Formulation 30 (bio_score + premium + delivery + absorption
           + excellence + single-ingredient + enzyme; B0/B1 penalties).
  P1.3.2 — Dose 25 (supplemental window + multi-form; B7 penalty).
  P1.3.3 — Evidence 20 (multiplicative pipeline).
  P1.3.4 — Testing & Trust 15 (B4a SKU + B4b GMP + B4c traceability).
  P1.3.5 — Transparency 10 (B3 claims; B2/B5/B6 penalties).
  P1.3.6 — Manufacturer Trust +5 + Manufacturer Violations -25
           + penalty roll-up + final 100-pt assembly + verdict reconciliation.
  P1.4   — Confidence typed sub-categories: high / moderate / low.       [done]
  P1.5   — Canary rank-order check on rows 1-9 and 19-24 of the v4 spec
           canary set; omega-vs-generic decision gate.

This module never mutates the input product dict. It returns a fresh
shadow-column dict that the caller (build_final_db.py or the scoring
batch driver) merges into the scored output.
"""

from __future__ import annotations

from typing import Any, Dict

from scoring_v4.confidence import evaluate_confidence
from scoring_v4.gate_completeness import evaluate_completeness_gate
from scoring_v4.gate_safety import evaluate_safety_gate
from scoring_v4.modules.generic import score_generic
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


def _completeness_gate_breakdown(completeness_result) -> Dict[str, Any]:
    """Render the completeness-gate result into the shadow breakdown."""
    return {
        "module": completeness_result.module,
        "is_live_eligible": completeness_result.is_live_eligible,
        "verdict": completeness_result.verdict,
        "reason": completeness_result.reason,
        "missing_fields": list(completeness_result.missing_fields),
        "mapped_coverage": completeness_result.mapped_coverage,
        "dose_coverage": completeness_result.dose_coverage,
        "checked_fields": list(completeness_result.checked_fields),
    }


def _verdict_from_score(score_100: Any, carried_verdict: Any = None) -> str:
    """Resolve the non-blocking verdict after score assembly.

    BLOCKED/UNSAFE/NOT_SCORED return earlier. CAUTION from Layer 1 wins
    over POOR/SAFE; otherwise the v4 100-point equivalent of v3's 32/80
    threshold is 40.
    """
    if carried_verdict == "CAUTION":
        return "CAUTION"
    try:
        score = float(score_100)
    except (TypeError, ValueError):
        return carried_verdict or "NOT_SCORED"
    return "POOR" if score < 40.0 else "SAFE"


def score_product_v4_shadow(enriched_product: Dict[str, Any]) -> Dict[str, Any]:
    """Score an enriched product against the v4 shadow scorer.

    Returns a dict of the six shadow columns. Never raises on malformed
    input — robustly falls back to the generic module + skeleton shape.

    Pipeline (per §4 of SCORING_V4_PROPOSAL.md):
      1. Router decides module (generic / probiotic / multi_or_prenatal).
      2. Layer 1 Safety Gate. BLOCKED/UNSAFE short-circuit scoring
         (score=None, confidence='blocked_by_safety_gate'). CAUTION
         sets verdict but scoring continues.
      3. Layer 2 Completeness Gate. Incomplete products short-circuit
         to NOT_SCORED with confidence='blocked_by_completeness_gate'.
      4. Layer 3 Scoring (per-module). Generic module emits populated
         dimensions and a final module score at P1.3.6.
         Probiotic (P2) and multi_or_prenatal (P3) modules not online yet.
      5. Layer 4 Confidence. Complete generic rows get typed confidence
         metadata plus a top-level band. Gate failures retain blocked_by_*.

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

    # Layer 2 — Completeness Gate.
    completeness = evaluate_completeness_gate(enriched_product, module)
    shadow["shadow_score_v4_breakdown"]["completeness_gate"] = (
        _completeness_gate_breakdown(completeness)
    )
    if not completeness.is_live_eligible:
        # Archive / QA verdict only. Live catalog excludes these rows
        # entirely; safety signals remain available in safety_gate.
        shadow["shadow_score_v4_verdict"] = "NOT_SCORED"
        shadow["shadow_score_v4_confidence"] = "blocked_by_completeness_gate"
        return shadow

    # Layer 3 — Per-class module. Only the generic module is online at
    # P1.3.0 (scaffold only — dimension scores are all None until P1.3.1+
    # land the per-dimension math). Probiotic (P2) and multi_or_prenatal
    # (P3) emit their own module blocks under the same `module` key.
    if module == "generic":
        module_result = score_generic(enriched_product)
        shadow["shadow_score_v4_breakdown"]["module"] = module_result.to_breakdown()
        shadow["shadow_score_v4_100"] = module_result.score_100
        shadow["shadow_score_v4_verdict"] = _verdict_from_score(
            module_result.score_100,
            shadow.get("shadow_score_v4_verdict"),
        )
        confidence = evaluate_confidence(
            enriched_product,
            module_breakdown=shadow["shadow_score_v4_breakdown"]["module"],
            safety_gate=shadow["shadow_score_v4_breakdown"].get("safety_gate", {}),
            completeness_gate=shadow["shadow_score_v4_breakdown"].get("completeness_gate", {}),
        )
        shadow["shadow_score_v4_breakdown"]["confidence"] = confidence
        shadow["shadow_score_v4_confidence"] = confidence["band"]

    return shadow
