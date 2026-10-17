# ADR-0002 — One public quality scorer

**Status:** ACCEPTED. It records the v4 cutover (f3bed2f2, 2026-07-16) and Sean's redesign rule
(2026-09-22).
**Date:** 2026-09-25
**Matrix concepts:** `quality_score_v4_contract`, `scoring_input_contract`, `verdict_contract`

## Decision

Exactly one scorer produces the public quality score at any time:
`scripts/score_supplements_v4.py::score_product_v4` → `scripts/scoring_v4/scored_artifact.py`,
configured only by `scripts/scoring_v4/config/quality_score.json`. Export (`build_final_db.py`)
consumes the scored artifact and never scores again. The Flutter app renders
`quality_score_v4_100` and never recomputes it.

## Context

The v3 scorer ran beside v4 as a shadow until f3bed2f2 ("cut Stage 3 over to one v4 artifact
producer"). Two scorers gave two answers for one product, and residual v3 reads kept leaking into
export.

## Consequences

- A replacement scorer is built unreleased and replaces v4 in one cutover, at a coverage threshold
  Sean approves. The current example is the purpose-quality redesign on
  `codex/product-quality-redesign`. It never ships beside v4 and never falls back to v4 per
  product.
- New score fields go through the Owner Check (AGENTS.md "One brain"). `score` beside `score_new`
  is a defect.

## Rejected

Keeping v3 as a fallback; per-product fallback between scorers; app-side score adjustments.


## October 1, 2026 — independent quality and safety (Sean-approved)

`quality_tier` rates product quality. `product_safety_status` reports assessed
catalog safety; banned/recalled reasons remain attached to hard findings.
Quality assembly never rewrites a safety disposition when a score crosses a tier.
Legacy `verdict` remains a compatibility/readiness field, with POOR readable only
in older catalogs and never newly emitted. Flutter and release comparison consume
the independent owners. A quality improvement cannot be called a safer product.
This extends existing owners and fields; it creates no second scorer or registry.

## Declared-serving Dose quality — Sean, October 17, 2026

Product Dose quality assesses one declared Facts-panel serving across every
category. Higher labeled daily use remains a separate safety assessment. A
manufacturer's maximum does not establish what a person actually takes.

The existing scoring input contract projects reference percentages using their
recorded frequency and units. Every route calls the shared Dose wrapper and
opens a declared-serving scope at the existing frequency owner. The one typed
UL evaluator handles both contexts: serving quality for Dose, original maximum
labeled daily exposure for the safety gate. Source directions, quantities,
identity and applicability guards remain intact; intermittent directions cannot
erase a high-serving quality deduction. The other five pillars, clinical limits
and Verification policy are unchanged.

This keeps the product score tied to a visible reference amount while retaining
higher-use concerns. The app renders those concerns with their assessment basis,
groups explanations for one nutrient without losing severity, and never
recalculates a pipeline UL decision. This is not a personal dose recommendation.
Config 1.27.0 and engine 4.6.0 identify the change. The existing LEDGER records the
cause-grouped measurement and validation; publication still requires fresh
pipeline artifacts and the normal release checks.
