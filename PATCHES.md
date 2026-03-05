# Pipeline Patch Tracker (Current)

**Last updated:** 2026-03-04  
**Branch state:** all planned critical/high patches from the audit are applied and validated.

## Current validation baseline

- Full suite: `1901 passed, 3 skipped` (no xfails, no xpasses)
- Last full run command: `pytest -q scripts/tests -ra`
- Runtime: ~2m22s to ~2m29s (expected for this repo and fixture size)

## Original 18 patches status

| Patch | Status | Notes |
|---|---|---|
| 1 | Applied | `score_stability_gates.py` NameError fixed (`rate_applicable`) |
| 2 | Applied | stereoisomer guard expanded in `normalization.py` |
| 3 | Applied | deterministic `sorted(set())` + narrowed exception in `dsld_validator.py` |
| 4 | Applied | atomic state-file writes in `batch_processor.py` |
| 5 | Applied | atomic scored output writes in `score_supplements.py` |
| 6 | Applied | schema version aligned to `5.0.0` in `preflight.py` + `validate_database.py` |
| 7 | Applied | stale `validate_json_files.py` quarantined to `scripts/archive/` |
| 8 | Applied | IQM metadata `total_entries` corrected |
| 9 | Applied | `as_float()` rejects NaN/Inf |
| 10 | Applied | fraction parser zero-denominator guard |
| 11 | Applied | empty `matched_forms` guard |
| 12 | Applied | blend detector failure logging includes impact context |
| 13 | Applied | narrowed import fallback to `ImportError` |
| 14 | Applied | scorer uses `SCORING_STATUS_NOT_APPLICABLE` constant |
| 15 | Applied | coverage gate reads `compliance_data` / `contaminant_data` contracts |
| 16 | Applied | resume tracking moved after successful categorization |
| 17 | Applied | PII contacts stripped from enriched payload |
| 18 | Applied | dosage conversion exceptions logged |

## Additional hardening completed after the 18 patches

1. Deterministic output ordering hardened in enrichment/normalization paths (replaced remaining `list(set(...))` output paths with stable ordering).
2. Enrichment hot path optimized with per-product text memoization cache (`_get_all_product_text*`) and tests.
3. Parent-context IQM lookup optimized with cached index while preserving deterministic tie behavior and mutable-map safety.
4. Enrichment config alignment completed:
   - `paths.input_file_pattern` now used at runtime.
   - `output_structure.*` now used for output naming/folders.
   - `options.generate_reports` is honored.
   - stale/unused enrichment config keys removed.
5. Negative phrase guard added to banned matching to prevent false positives for explicit negations (e.g., `"free from trans fats"`, `"X-free"`, `"contains no X"`).
6. Regression signal cleanup:
   - removed stale `xfail` markers that had become XPASS,
   - replaced avoidable skips with deterministic assertions,
   - suite now runs with strict clean status.

## Synergy hardening (2026-03-04)

1. `score_supplements.py` fallback logic for A5c now matches enrichment behavior:
   - clusters with `match_count >= 2` but **no checkable `min_effective_dose > 0`** no longer qualify.
   - prevents bonus drift when `synergy_cluster_qualified` is missing and scorer must evaluate raw `formulation_data`.
2. `test_score_supplements.py` updated to lock the stricter fallback contract (no implicit bonus on dose-unanchored clusters).
3. `synergy_cluster.json` contract fix:
   - added missing `zinc` aliases to `respiratory_health_lung_support` and `prostate_health` ingredient lists so `min_effective_doses` keys are valid.
4. `db_integrity_sanity_check.py` strengthened for `synergy_cluster.json`:
   - `evidence_tier` required and constrained to `int` in `{1,2,3}`,
   - `synergy_mechanism` type constrained to `str|null`,
   - every `min_effective_doses` key must exist in `ingredients`,
   - every dose must be finite and `> 0`.
5. `DATABASE_SCHEMA.md` synchronized with actual/runtime contract for synergy clusters.
6. Added explainability fields directly in `synergy_cluster.json`:
   - `note` (user-facing rationale),
   - `sources` (evidence link objects with `source_type`/`label`/`url`).
7. Enricher now propagates `note` + `sources` into matched synergy cluster output for UI details.
8. Added regression coverage for explainability propagation in enrichment (`TestSynergyExplainabilityFields`).
9. Phase-1 citation seeding completed for 8 clusters, then phase-2 expanded to full coverage.
10. Replaced generic synergy notes with user-facing explainability text:
   - explicit bonus rule (`+1`, `>=2` matched ingredients),
   - dose-qualification rule (at least half of dose-checkable ingredients),
   - evidence tier label and anchor-dose summary.
11. Added missing min-dose anchors for key ingredients already present in clusters:
   - `sleep_stack`: `zinc >= 10` (+ `zinc` aliases),
   - `eye_health`: `vitamin c >= 250`,
   - `iron_absorption`: `copper >= 0.9`.
12. Pruned noisy/non-specific terms likely to inflate false positives:
   - removed `cbd` from `sleep_stack`,
   - removed `anthocyanins` from `eye_health`,
   - removed `osteocalcin` from `bone_health`.
13. Citation coverage is now `54/54` clusters with non-empty `sources`.
14. Validation gate hardened: `sources` must be non-empty for every synergy cluster (empty list now fails integrity checks).
15. Phase-3 citation cleanup:
   - removed all query-placeholder citations (`pubmed_query` and `...?term=` URLs),
   - upgraded FDA link to current URL path,
   - added NIH/NCCIH companion references for probiotic clusters,
   - no clusters remain with FDA-only references.
16. Validation gate tightened further:
   - allowed synergy source types are now constrained to `pubmed|nih_ods|fda|nccih`,
   - PubMed search-query URLs are explicitly rejected (must be source-page links).

## Remaining open items (not patched in this cycle)

1. Implement `SCORE -> EXPORT` stage and explicit `ExportRecord` schema/validator.
2. Add run manifest stamping (`run_id`, git SHA, config hash, reference DB versions) to outputs.
3. Build deterministic double-run diff gate (`clean -> enrich -> score` twice, assert zero drift).
4. Optional architecture refactor of `enrich_supplements_v3.py` monolith into modules.

## Signed

Signed: Sean Cheick and Codex
