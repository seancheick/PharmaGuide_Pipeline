# PharmaGuide Scoring Integrity Candidate — 2026-08-21

Status: **verified preproduction candidate; not published**

The scoring-integrity unification is implemented across the pipeline and Flutter reader. The full 15,412-product corpus was rebuilt, every required audit and test suite passed, Supabase and Flutter import were exercised in dry-run mode only, and no production action was performed.

## Release decision

This is a material catalog change and needs operator approval before publication:

- Baseline app catalog: **13,271** products.
- Candidate app catalog: **6,637** products.
- Candidate quarantine: **8,775** products.
- Main cause: incomplete evidence assessment on **8,445 products**, covering **19,671 material active rows** not yet evaluated.
- Safety-policy sign-off: **12 products**—nine vinpocetine products and three synthetic-anabolic-steroid-class products.

The strict mapping policy itself is clean: all **84,492 score-eligible active rows are mapped**, no scored product is below 100% mapping coverage, and no duplicate row ownership or unexplained drop survives the release gates.

## What changed

- One v4 scoring contract now owns route, safety, dose, readiness, confidence, and export behavior. Frozen score fields remain unchanged; scoring version advances from 4.2.0 to 4.3.0.
- `NUTRITION_ONLY` and `mapped_coverage_applicable` are retired from production; non-scoreable products now become quarantined `NOT_SCORED` QA records.
- Row-level source reconciliation replaces aggregate drop heuristics. Every label row receives a stable owner and explicit destination.
- Safety matching is shared across active, normalization, and inactive paths, with negative-term and role/form protections preserved. Blocking explanations come from the winning structured decision.
- Dose conversion and UL handling use typed outcomes; raw-value fallbacks and silent `has_over_ul=false` behavior are removed.
- Routing is derived from measured label intent. All **538 route changes** are in the reviewed gold set, and stamped versus recomputed routes match for all 15,412 products.
- Evidence and verification now distinguish evaluated, absent/limited, not evaluated, and not applicable. Pillar weights were not recalibrated.
- Schema 2.4 supplies the compatibility bridge to Flutter; prepared schema 3 removes redundant payload families only after warning equivalence is proven.
- Core `product_status` is canonical, score confidence has only high/moderate/low/null, and route confidence and score-unavailable reasons are separate.

## Verification

- Full corpus pipeline: **37 datasets passed**.
- Pipeline fast suite: **11,781 passed, 123 skipped**.
- Candidate-targeted release suite: **109 passed, 3 skipped**.
- Candidate-targeted full suite: **14,261 passed, 169 skipped, 2 documented expected failures**.
- Flutter: static analysis passed; **3,230 tests passed**.
- Raw-to-final: **0 blocker and 0 high findings**. Six medium blend-child dose-disclosure observations and 516 low inactive-display-contract notices remain documented.
- Warning equivalence: **70,663 checks, 0 failures**.
- Prepared schema-3 payload: **348,314,829 bytes smaller**, a **39.0842%** reduction from the schema-2.4 candidate.
- Supabase sync dry run passed with no upload; Flutter import dry run passed with no files written.

## Open work before publication

1. Review the 8,775-product quarantine impact; evidence curation is the dominant backlog.
2. Sign off or retain quarantine for the 12 ambiguous US-policy cases recorded in the machine report.
3. Approve this candidate, then run production publication as a separate explicitly authorized operation.

Calibration is intentionally excluded. It should remain a later scoring release after the readiness backlog is resolved.

## Integrity and artifacts

The machine-readable report is SHA-256 integrity-sealed using canonical JSON with the `integrity` object excluded. This is an integrity seal, not an identity signature.

- Machine report: `docs/release_candidates/scoring_integrity_candidate_2026_08_21.json`
- Machine-report integrity SHA-256: `b112872e7ad5e58c31beafe33d2e90dcd2ce66c8ad5006dbde123aec0fc11004`
- Candidate snapshot integrity SHA-256: `ca7f39618133a8b2a0d379efe074d0720d193b242254f3ef232dd74177a3d0ee`
- Baseline snapshot integrity SHA-256: `38dd5d8802f1ba86efed072652b31f59c9af85b7d9f96ae1504b253bd0cdd58d`
- Candidate core database SHA-256: `0bf69ad811e9541107e46b2aff087196bef49b73544377f8fcfc9f790e874d87`
- Candidate blob-tree SHA-256: `cc743e2d23dad9ae0baaa8e2779fe8df4c9f65374d23f6d84b296f84246197fc`

No Supabase upload, Flutter bundle mutation, push, cleanup, or production promotion was performed.
