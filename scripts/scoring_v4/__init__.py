"""v4 shadow scoring package.

Companion to `score_supplements.py` (v3, production truth). Per the
architecture lock in `docs/plans/SCORING_V4_PROPOSAL.md` §13:

  - v4 ships as a SEPARATE scorer at `scripts/score_supplements_v4_shadow.py`.
  - This package owns the v4 scoring policy (router, gates, modules,
    rubrics, confidence). v3 is untouched.
  - Both scorers consume the same enriched input contract from
    `enrich_supplements_v3.py`. Stable shared helpers (cert_resolver,
    enhanced_normalizer lookups) are imported by both.
  - v4 emits `shadow_score_v4_*` columns side-by-side with v3 columns;
    v3 stays authoritative through the v4 build.

Phased migration (§19):
  P1   — router + gates + generic module (this is what's online).
  P1.5 — omega decision gate.
  P2   — probiotic module.
  P3   — multi_or_prenatal module.
  P4   — AI panel rank-order check + API ground truth.
  P5   — Flutter cutover.
"""

__all__ = ["router", "gate_safety", "gate_completeness", "confidence", "modules"]
