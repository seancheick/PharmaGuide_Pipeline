---
paths:
  - "scripts/scoring_v4/**"
  - "scripts/scoring_input_contract.py"
  - "scripts/score_products_v4.py"
  - "scripts/score_supplements_v4.py"
---

# Scoring rules (loaded when working on the v4 scorer)

**Invariants**

- There is one public scorer: `score_supplements_v4.py::score_product_v4` →
  `scoring_v4/scored_artifact.py`.
- Every magnitude lives in `scoring_v4/config/quality_score.json`. Recalibrate there, never with
  literals in code.
- **Complexity creates obligations, not bonuses.**
  - No ingredient-count or single-only bonuses or floors.
  - Adding an ingredient never raises a score by its presence.
  - Materiality comes from semantic roles (primary / supporting / trace), not raw mass.
- **A specific clinical lock beats a generic floor.** Exempt and pin the generic test; never raise
  a score to satisfy it.
- **Pillar = 0 can be a legitimate low.** Verification is the one that fails open: when its evidence
  tier is `unknown`, `quality_score.py` falls back to `verification_subscale.neutral_baseline` in
  the config and reports `fail_open_neutral`. Read the driver field before calling any pillar a bug.
- **Retiring a component moves its explanation too.** Scoring it 0 while leaving its copy and
  pins behind ships a contradiction.
- Safety verdicts (BLOCKED/UNSAFE) are separate from quality. Never let a quality change hide or
  soften a safety verdict.

**Measuring a change** (never re-run the ~45-min full pipeline just to measure)

1. Owner Check (AGENTS.md), then a failing regression test.
2. Probe one real product at the scored layer, printing the driver field, before and after.
3. Targeted brand probe on a few brands that exercise the path.
4. For enricher-side changes, measure through `enrich_product`. Calling `_collect_*` directly
   invents regressions.
5. Before claiming a routing or scoring fix: a before/after rescore of stored inputs from a clean
   HEAD worktree, the full-corpus route/score diff, and an explanation of the top movers.
   Synthetic tests alone hide over-promotion.
6. Never run a pipeline while the tree has uncommitted scoring edits; its outputs are invalid.
