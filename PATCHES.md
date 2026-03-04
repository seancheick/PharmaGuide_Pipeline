# Pipeline Patch Tracker (Current)

**Last updated:** 2026-03-04  
**Branch state:** all planned critical/high patches from the audit are applied and validated.

## Current validation baseline

- Full suite: `1900 passed` (no skips, no xfails, no xpasses)
- Last full run command: `pytest -q scripts/tests -ra`
- Runtime: ~2m20s (expected for this repo and fixture size)

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

## Remaining open items (not patched in this cycle)

1. Implement `SCORE -> EXPORT` stage and explicit `ExportRecord` schema/validator.
2. Add run manifest stamping (`run_id`, git SHA, config hash, reference DB versions) to outputs.
3. Build deterministic double-run diff gate (`clean -> enrich -> score` twice, assert zero drift).
4. Optional architecture refactor of `enrich_supplements_v3.py` monolith into modules.

## Signed

Signed: Sean Cheick and Codex
