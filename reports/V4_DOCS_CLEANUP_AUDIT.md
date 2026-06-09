# V4 Docs Cleanup Audit — 2026-06-09

This audit lists documentation that should be deleted or archived so future
work does not drift back to the legacy V3 `/80` score contract.

## Current Docs To Trust

Pipeline repo:

- `AGENTS.md`
- `README.md`
- `scripts/FINAL_EXPORT_SCHEMA_V1.md`
- `scripts/PIPELINE_ARCHITECTURE.md`
- `scripts/SCORING_ENGINE_SPEC.md`
- `scripts/SCORING_README.md`
- `scripts/GLOSSARY.md`
- `scripts/PIPELINE_OPERATIONS_README.md`
- `scripts/DATABASE_SCHEMA.md`
- `scripts/INTERACTION_RULE_AUTHORING_SOP.md`
- `scripts/INTERACTION_RULE_SCHEMA_V6_ADR.md`
- `scripts/MATCHING_PRECEDENCE.md`

Flutter repo:

- `AGENTS.md`
- `README.md`
- `FINAL_EXPORT_SCHEMA_V1.md`
- `FLUTTER_DATA_CONTRACT_V1.md`
- `knowledge/` docs that are actively maintained by the app team

## Delete Now

These are generated, cache, or stale docs with no source-of-truth value.

Pipeline repo:

- `.pytest_cache/README.md`
- `scripts/.pytest_cache/README.md`
- `graphify-out/GRAPH_REPORT.md`
- `scripts/dist.preRC_20260519T013812Z/INTERACTION_RELEASE_NOTES.md`
- `scripts/dist.preRC_20260519T013812Z/RELEASE_NOTES.md`
- old intermediate V4 delta report directories under `reports/v4_corpus_delta*/`
  after preserving the latest release-readiness and route-consistency reports

Flutter repo:

- `.pytest_cache/README.md`
- `.dart_tool/extension_discovery/README.md`
- `graphify-out/GRAPH_REPORT.md`
- `graphify-out/obsidian/` (generated code graph notes; regenerate when needed)

## Archive Instead Of Delete

These are historically useful but should not be read as implementation truth.
Move them to an archive folder or mark them historical.

Pipeline repo:

- `.planning/v4-finalization/PLAN.md`
- `.planning/v4-finalization/REVIEW_phase2.md`
- `.planning/v4-finalization/REVIEW_phase3.md`
- `docs/plans/SCORING_V3_TO_V4_MAPPING.md`
- `docs/plans/SCORING_V4_PROPOSAL.md`
- `docs/plans/V4_CUTOVER_HANDOFF.md`
- `docs/plans/FLUTTER_V4_MIGRATION_HANDOFF.md`
- `reports/v4_side_by_side_fresh/v3_v4_side_by_side_100.md`
- `reports/v4_side_by_side_review/v3_v4_side_by_side_100.md`
- old RC score delta reports under `reports/RC_score_delta_20260519*/`
- old release-candidate reports under `reports/RC_v6/`
- old E1 release reports under `reports/e1_*`
- `scripts/PIPELINE_MAINTENANCE_SCHEDULE.md` if `docs/PIPELINE_MAINTENANCE_SCHEDULE.md`
  remains canonical
- `docs/PIPELINE_OPERATIONS_README.md` if `scripts/PIPELINE_OPERATIONS_README.md`
  remains canonical

Flutter repo:

- `2026-03-27-data-to-app-roadmap-design.md`
- `2026-03-29-flutter-app-build-design.md`
- `2026-04-07-flutter-complete-roadmap-design.md`
- `2026-04-07-pharmaguide-flutter-v1.0.md`
- `HANDOFF_2026-04-12.md`
- `HANDOFF_2026-04-21.md`
- `HANDOFF_2026-04-21_FLUTTER_TO_PIPELINE.md`
- `PharmaGuide Flutter MVP Dev.md`
- `Product_Detail_Refactor.md`
- `docs/HANDOFF_PIPELINE_SAFETY_DATA.md`
- `docs/HANDOFF_PRODUCT_IMAGES.md`
- old planning/sprint docs under `docs/plans/` and `docs/sprints/`

## Keep But Mark Historical

These contain useful history and should remain searchable, but they are not live
contracts:

- `SPRINT_TRACKER.md` in the Flutter repo
- `reports/DOCS_STALENESS_AUDIT.md` in the pipeline repo
- `reports/v4_*` adversarial reviews and calibration notes that explain why V4
  thresholds were chosen

## V4 Contract Guardrails

- Production score field: `quality_score_v4_100`
- Score visibility field: `quality_score_status`
- Score detail field: `quality_pillars_v4`
- Dropped fields: `score_quality_80`, `score_display_80`
- Do not use historical docs, graphify output, or sprint handoffs to infer current
  runtime behavior. Verify against source, generated artifacts, tests, and the
  active export contract.
