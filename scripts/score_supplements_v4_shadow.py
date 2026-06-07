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

Current P3.6 / P2.6 / P1.6.6 state:
  - Router runs and decides the module (generic / probiotic / omega /
    multi_or_prenatal).
  - Safety gate short-circuits BLOCKED / UNSAFE and carries CAUTION forward.
  - Completeness gate marks unscoreable rows NOT_SCORED for archive / QA.
  - Generic, probiotic, omega, sports, and multi_or_prenatal modules emit
    populated dimensions plus manufacturer trust / violations and final 0-100
    rubric scores.
  - shadow_score_v4_100 mirrors the module result for complete products in
    all four online modules.
  - shadow_score_v4_confidence = top-level typed confidence band for
    complete scoreable rows; blocked_by_* for gate failures.
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
from scoring_v4.modules.multi_prenatal import score_multi_prenatal
from scoring_v4.modules.omega import score_omega
from scoring_v4.modules.probiotic import score_probiotic
from scoring_v4.modules.sports import score_sports
from scoring_v4.router import class_for_product
from scoring_v4.display_calibration import calibrate_display


# Schema lock — these are the six shadow fields documented in §14 of
# SCORING_V4_PROPOSAL.md. They are a pipeline/audit contract while v3 remains
# production truth; they are not exported into products_core until an explicit
# P5 cutover decision.
SHADOW_KEYS = (
    "shadow_score_v4_100",
    "shadow_score_v4_module",
    "shadow_score_v4_verdict",
    "shadow_score_v4_confidence",
    "shadow_score_v4_breakdown",
    "shadow_score_v4_anchored",
    # Display-layer top-band calibration (raw is never mutated; this is the
    # consumer-facing score). breakdown["display_calibration"] carries provenance.
    "shadow_score_v4_display_100",
)

# Scoring-engine provenance (Phase 0 config-driven calibration). Stamped into
# breakdown["provenance"] on EVERY scored artifact so an audit / score dispute
# can reconstruct exactly what produced a score: the engine version, the
# classification-schema version, and the version+fingerprint of every config
# rubric consumed. Bump SCORING_ENGINE_VERSION on a material ALGORITHM change;
# config-value changes are captured by the per-rubric fingerprints, not here.
# SCORING_MODE stays 'shadow' until the §P5 cutover decision flips it.
SCORING_ENGINE_VERSION = "4.0.0"
SCORING_MODE = "shadow"


def _provenance_block(module: str) -> Dict[str, Any]:
    """Reproducibility stamp for a scored artifact (engine + schema + config)."""
    from scoring_input_contract import SCORING_CLASSIFICATION_SCHEMA_VERSION
    from scoring_v4.config_registry import all_config_provenance

    return {
        "scoring_engine_version": SCORING_ENGINE_VERSION,
        "classification_schema_version": SCORING_CLASSIFICATION_SCHEMA_VERSION,
        "config_versions": all_config_provenance(),
        "module_route": module,
        "mode": SCORING_MODE,
    }


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
        "soft_missing": list(getattr(completeness_result, "soft_missing", [])),
        "mapped_coverage": completeness_result.mapped_coverage,
        "dose_coverage": completeness_result.dose_coverage,
        "checked_fields": list(completeness_result.checked_fields),
        "score_cap": getattr(completeness_result, "score_cap", None),
        "verdict_ceiling": getattr(completeness_result, "verdict_ceiling", None),
    }


def _verdict_from_score(
    score_100: Any,
    carried_verdict: Any = None,
    raw_score_100: Any = None,
) -> str:
    """Resolve the non-blocking verdict after score assembly.

    BLOCKED/UNSAFE/NOT_SCORED return earlier. CAUTION from Layer 1 wins
    over POOR/SAFE. Since Phase 9, the user-facing score is the raw rubric
    score; the raw-score guard remains for compatibility with direct module
    callers and any completeness cap applied after module assembly.
    """
    if carried_verdict == "CAUTION":
        return "CAUTION"
    try:
        score = float(score_100)
    except (TypeError, ValueError):
        return carried_verdict or "NOT_SCORED"
    try:
        raw_score = float(raw_score_100)
    except (TypeError, ValueError):
        raw_score = None
    if raw_score is not None and raw_score < 40.0:
        return "POOR"
    return "POOR" if score < 40.0 else "SAFE"


def _score_after_completeness_policy(score_100: Any, completeness_result: Any) -> Any:
    """Apply completeness score caps without mutating module internals."""
    cap = getattr(completeness_result, "score_cap", None)
    if cap is None:
        return score_100
    try:
        score = float(score_100)
        cap_value = float(cap)
    except (TypeError, ValueError):
        return score_100
    return min(score, cap_value)


def _carried_verdict_with_completeness_policy(shadow: Dict[str, Any], completeness_result: Any) -> Any:
    carried = shadow.get("shadow_score_v4_verdict")
    ceiling = getattr(completeness_result, "verdict_ceiling", None)
    if ceiling == "CAUTION":
        return "CAUTION"
    return carried


def score_product_v4_shadow(enriched_product: Dict[str, Any]) -> Dict[str, Any]:
    """Score an enriched product against the v4 shadow scorer.

    Returns a dict of the six shadow columns. Never raises on malformed
    input — robustly falls back to the generic module + skeleton shape.

    Pipeline (per §4 of SCORING_V4_PROPOSAL.md):
      1. Router decides module (generic / probiotic / omega /
         multi_or_prenatal).
      2. Layer 1 Safety Gate. BLOCKED/UNSAFE short-circuit scoring
         (score=None, confidence='blocked_by_safety_gate'). CAUTION
         sets verdict but scoring continues.
      3. Layer 2 Completeness Gate. Incomplete products short-circuit
         to NOT_SCORED with confidence='blocked_by_completeness_gate'.
      4. Layer 3 Scoring (per-module). Generic, probiotic, omega, and
         multi_or_prenatal modules emit populated dimensions and final scores.
      5. Layer 4 Confidence. Complete scoreable rows get typed confidence
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
        Dict with exactly the six SHADOW_KEYS. Audit tools consume this
        contract for v3-v4 comparisons; the final app catalog still ships one
        production score contract at a time.
    """
    if not isinstance(enriched_product, dict):
        enriched_product = {}

    module = class_for_product(enriched_product)
    shadow = _empty_shadow(module)
    # Provenance stamped before any early return, so BLOCKED / NOT_SCORED
    # artifacts carry the same engine+config fingerprint as fully scored ones.
    shadow["shadow_score_v4_breakdown"]["provenance"] = _provenance_block(module)

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

    # Layer 3 — Per-class module dispatch. Generic, probiotic, omega,
    # sports, and multi_or_prenatal are wired as complete score-producing
    # modules.
    if module == "generic":
        module_result = score_generic(enriched_product)
        shadow["shadow_score_v4_breakdown"]["module"] = module_result.to_breakdown()
        shadow["shadow_score_v4_100"] = _score_after_completeness_policy(
            module_result.score_100,
            completeness,
        )
        shadow["shadow_score_v4_verdict"] = _verdict_from_score(
            shadow["shadow_score_v4_100"],
            _carried_verdict_with_completeness_policy(shadow, completeness),
            module_result.raw_score_100,
        )
        confidence = evaluate_confidence(
            enriched_product,
            module_breakdown=shadow["shadow_score_v4_breakdown"]["module"],
            safety_gate=shadow["shadow_score_v4_breakdown"].get("safety_gate", {}),
            completeness_gate=shadow["shadow_score_v4_breakdown"].get("completeness_gate", {}),
        )
        shadow["shadow_score_v4_breakdown"]["confidence"] = confidence
        shadow["shadow_score_v4_confidence"] = confidence["band"]
    elif module == "probiotic":
        # P2.6: full probiotic pipeline online — all 5 dimensions populate,
        # manufacturer trust/violations apply, and score_100 is the rubric
        # production score with verdict + typed confidence band.
        probiotic_result = score_probiotic(enriched_product)
        shadow["shadow_score_v4_breakdown"]["module"] = probiotic_result.to_breakdown()
        shadow["shadow_score_v4_100"] = _score_after_completeness_policy(
            probiotic_result.score_100,
            completeness,
        )
        shadow["shadow_score_v4_verdict"] = _verdict_from_score(
            shadow["shadow_score_v4_100"],
            _carried_verdict_with_completeness_policy(shadow, completeness),
            probiotic_result.raw_score_100,
        )
        confidence = evaluate_confidence(
            enriched_product,
            module_breakdown=shadow["shadow_score_v4_breakdown"]["module"],
            safety_gate=shadow["shadow_score_v4_breakdown"].get("safety_gate", {}),
            completeness_gate=shadow["shadow_score_v4_breakdown"].get("completeness_gate", {}),
        )
        shadow["shadow_score_v4_breakdown"]["confidence"] = confidence
        shadow["shadow_score_v4_confidence"] = confidence["band"]
    elif module == "multi_or_prenatal":
        # P3.6: full multi/prenatal pipeline online — all 5 dimensions
        # populate, manufacturer trust/violations apply, and score_100 is
        # the rubric production score with verdict + typed confidence.
        multi_result = score_multi_prenatal(enriched_product)
        shadow["shadow_score_v4_breakdown"]["module"] = multi_result.to_breakdown()
        shadow["shadow_score_v4_100"] = _score_after_completeness_policy(
            multi_result.score_100,
            completeness,
        )
        shadow["shadow_score_v4_verdict"] = _verdict_from_score(
            shadow["shadow_score_v4_100"],
            _carried_verdict_with_completeness_policy(shadow, completeness),
            multi_result.raw_score_100,
        )
        confidence = evaluate_confidence(
            enriched_product,
            module_breakdown=shadow["shadow_score_v4_breakdown"]["module"],
            safety_gate=shadow["shadow_score_v4_breakdown"].get("safety_gate", {}),
            completeness_gate=shadow["shadow_score_v4_breakdown"].get("completeness_gate", {}),
        )
        shadow["shadow_score_v4_breakdown"]["confidence"] = confidence
        shadow["shadow_score_v4_confidence"] = confidence["band"]
    elif module == "omega":
        # P1.6.6: full omega pipeline online — all 5 dimensions populate,
        # manufacturer trust/violations apply, and score_100 is the rubric
        # production score with verdict + typed confidence.
        omega_result = score_omega(enriched_product)
        shadow["shadow_score_v4_breakdown"]["module"] = omega_result.to_breakdown()
        shadow["shadow_score_v4_100"] = _score_after_completeness_policy(
            omega_result.score_100,
            completeness,
        )
        shadow["shadow_score_v4_verdict"] = _verdict_from_score(
            shadow["shadow_score_v4_100"],
            _carried_verdict_with_completeness_policy(shadow, completeness),
            omega_result.raw_score_100,
        )
        confidence = evaluate_confidence(
            enriched_product,
            module_breakdown=shadow["shadow_score_v4_breakdown"]["module"],
            safety_gate=shadow["shadow_score_v4_breakdown"].get("safety_gate", {}),
            completeness_gate=shadow["shadow_score_v4_breakdown"].get("completeness_gate", {}),
        )
        shadow["shadow_score_v4_breakdown"]["confidence"] = confidence
        shadow["shadow_score_v4_confidence"] = confidence["band"]
    elif module == "sports":
        sports_result = score_sports(enriched_product)
        shadow["shadow_score_v4_breakdown"]["module"] = sports_result.to_breakdown()
        shadow["shadow_score_v4_100"] = _score_after_completeness_policy(
            sports_result.score_100,
            completeness,
        )
        shadow["shadow_score_v4_verdict"] = _verdict_from_score(
            shadow["shadow_score_v4_100"],
            _carried_verdict_with_completeness_policy(shadow, completeness),
            sports_result.raw_score_100,
        )
        confidence = evaluate_confidence(
            enriched_product,
            module_breakdown=shadow["shadow_score_v4_breakdown"]["module"],
            safety_gate=shadow["shadow_score_v4_breakdown"].get("safety_gate", {}),
            completeness_gate=shadow["shadow_score_v4_breakdown"].get("completeness_gate", {}),
        )
        shadow["shadow_score_v4_breakdown"]["confidence"] = confidence
        shadow["shadow_score_v4_confidence"] = confidence["band"]

    # Layer 5 — display-layer top-band calibration. Adds shadow_score_v4_display_100
    # (consumer score) + breakdown["display_calibration"] provenance. raw
    # (shadow_score_v4_100) is NEVER modified; gated so only SAFE, well-disclosed,
    # raw>=80 products lift. No-op for null/blocked scores.
    shadow = calibrate_display(shadow)

    return shadow
