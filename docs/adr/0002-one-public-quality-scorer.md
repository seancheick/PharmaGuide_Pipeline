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

## Directed daily Dose quality — current policy clarification, November 6, 2026

Dose adequacy uses the **minimum directed daily use**; safety uses the maximum.
When directions are absent, the default is one Facts-panel serving per day.
Neither manufacturer directions nor the catalog assessment establishes a
person's actual intake. This is the existing Dose V4.1 policy, including the
October 22 ceiling clarification, not a new scoring decision.

The earlier declared-serving policy was superseded by Dose V4.1 and no longer
describes current behavior. The historical engine 4.6.0 decision remains valid
as history; engine 4.7.0 records its replacement. The current description is
[scripts/SCORING_ENGINE_SPEC.md](../../scripts/SCORING_ENGINE_SPEC.md), with
ownership and invariants in the `quality_pillars_v4_contract` matrix entry.
All routes call `generic_helpers.score_directed_daily_dose`; Dose and the safety
gate consume the same typed `DoseSafetyResult`. Source quantities, frequency,
identity, applicability and warning facts remain source-owned. Flutter renders
the resulting assessments without recomputing exposure or deductions.

The original config 1.27.0 / engine 4.6.0 identifiers are historical provenance;
read current versions from the executable owners. Publication still requires
fresh pipeline artifacts and the normal release checks.
