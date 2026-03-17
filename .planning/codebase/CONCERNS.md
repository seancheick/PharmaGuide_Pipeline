# CONCERNS.md — Technical Debt, Known Issues, Fragile Areas

## Safety-Critical Issues (Fix First)

### 1. Vacha / Acorus calamus — Unresolved FDA Safety Routing
- **Status:** RESOLVED (2026-03-17)
- `BANNED_CALAMUS_ACORUS_CALAMUS` entry in `banned_recalled_ingredients.json` (aliases: Vacha, vacha, Acorus calamus, Calamus, Sweet Flag). Test coverage: `test_batch41_vacha_calamus_routes_to_banned` in `test_clean_unmapped_alias_regressions.py`.

### 2. IQM ↔ Banned/Recalled Collision — No Runtime Guard
- **Status:** RESOLVED (2026-03-17)
- Added `_preflight_iqm_banned_collision_check()` to `EnhancedDSLDNormalizer.__init__`. Runs at startup after all indices are built; logs CRITICAL for each collision. Test-time guard unchanged (`test_cross_db_overlap_guard.py`, `test_banned_collision_corpus.py`).

### 3. Stereoisomer Identity Loss
- **File:** `normalization.py`, `enhanced_normalizer.py`
- **Issue:** Text normalization lowercases and strips qualifiers (D-, L-, DL-) which are chirality markers. D-Alpha-Tocopherol ≠ DL-Alpha-Tocopherol but may normalize identically.
- **Risk:** MEDIUM — incorrect form aliasing for chiral actives (vitamin E forms, amino acid enantiomers)

---

## Known Bugs

### 4. `Eicosatrienoic Acid` Still Surfaces as Unmapped (2x)
- **File:** `enhanced_normalizer.py`, `STRUCTURAL_ACTIVE_CONTEXTUAL_DISPLAY_ONLY_LEAF_NAMES`
- **Issue:** "Eicosatrienoic Acid" is in the contextual display-only set (suppressed when `isNestedIngredient=True`), but 2 products in the Softgels dataset have it as a flat (non-nested) active ingredient. The contextual check doesn't fire → surfaces as unmapped.
- **Status:** Open, needs investigation of raw DSLD structure for those 2 PIDs

### 5. Pre-Validation Marking in Batch Processor
- **Status:** RESOLVED (2026-03-17)
- `_write_batch_outputs` now returns `bool`; `_write_json_output` returns `True/False`. `process_batch` includes `"write_success"` in return dict. `process_all_files` gates `state.last_completed_batch = batch_num` on `batch_result.get("write_success", True)`.

### 6. Batch Counter Reset on Resume
- **Status:** RESOLVED (prior session — FIX C6)
- `output_batch_offset` counts existing output files and offsets new batch names. Per-file resume uses `processed_file_paths` not `last_completed_batch` as the authoritative source.

### 7. Coverage Gate Field Mismatch
- **Status:** RESOLVED (2026-03-17)
- `_collect_rda_ul_data` in `enrich_supplements_v3.py` now embeds `"conversion_evidence": conv_evidence` per `rda_data` item. `coverage_gate._check_missing_conversions` reads `ing.get("conversion_evidence", {})` per-item — now correctly populated.

---

## Technical Debt

### 8. Monolithic `enhanced_normalizer.py` (~6000+ lines)
- Single file handles clean-stage parsing, structural detection, blend classification, normalizer text processing, DB routing, and output formatting.
- **Impact:** Hard to test in isolation; slow to navigate; merge conflicts frequent
- **Recommended split:** Parser module, structural detector, routing engine, output formatter

### 9. Hardcoded Dataset Paths
- **Files:** `batch_processor.py`, `run_pipeline.py`, multiple audit scripts
- **Issue:** Raw DSLD paths like `/Users/seancheick/Documents/DataSetDsld/` are hardcoded, making the pipeline non-portable.
- **Fix:** Config-driven paths in `config/` JSON

### 10. No Lockfile / Dependency Pinning
- **Issue:** `requirements.txt` (if present) may not pin exact versions. Fuzzy matcher and normalization libraries sensitive to version changes.
- **Risk:** Silent behavior changes on dep upgrades

### 11. Batch Run Summaries Accumulating in `scripts/`
- 20+ `batch_run_summary_*.txt` files loose in `scripts/` root. No archival policy.
- **Fix:** Auto-move to `scripts/logs/` or `scripts/archive/`

### 12. Non-Deterministic Enrichment Outputs
- **File:** `enrich_supplements_v3.py`
- **Issue:** Clinical source lookup order can vary, producing different enrichment metadata for the same product across runs when multiple sources match.
- **Risk:** MEDIUM — makes regression diffs noisy

---

## Performance Bottlenecks

### 13. Full DB Load Per Worker Process
- Each batch worker loads all 7 reference DBs into memory independently. At 44K+ capsule labels, memory pressure is significant.
- **Fix:** Shared-memory DB loading or pre-loaded DB server pattern

### 14. Linear Alias Scan in Fuzzy Matcher
- `fuzzy_matcher.py` scans all aliases linearly for each lookup. At IQM scale (10K+ aliases), this is O(n) per ingredient.
- **Fix:** Pre-index aliases into a trie or inverted index at startup

---

## Fragile Areas

### 15. `_flatten_nested_ingredients()` Complexity
- **File:** `enhanced_normalizer.py:2720`
- Lines 2720–2900 contain interlocked logic for structural containers, proprietary blends, display-only detection, and leaf surfacing. Adding a new blend type requires careful insertion to avoid breaking existing detection order.
- **Mitigation:** Maintain the existing frozen set + structural code rule pattern. Do not inline new rules without tests.

### 16. DSLD Raw Field Naming Inconsistencies
- Some DSLD raw files use `nestedRows`, others use `nestedIngredients`. Some use `ingredientGroup`, others leave it null.
- **Impact:** Structural detection relying on `ingredientGroup` being present may silently fail for null-group records.
- **Fix:** Defensive `.get()` with null-group fallback (already partially done)

### 17. `Proprietary_blends` DB Has No Schema Enforcement
- Unlike IQM/OI/HA/BR, `proprietary_blends` entries are not schema-validated by any test.
- **Risk:** Malformed entries silently fail to match at runtime

### 18. Unmapped Ingredient Tracker Counts from Stale Run
- `unmapped_ingredient_tracker.py` reads the last batch run output. If rerun on partial data, counts reflect partial state without warning.

---

## Open Deferred Items (March 2026)

| Item | Risk | Owner |
|------|------|-------|
| Vacha / Acorus calamus safety routing | HIGH | DONE 2026-03-17 |
| Eicosatrienoic Acid flat occurrence (2x) | MEDIUM | DONE (resolved by IQM additions) |
| Potassium Benzoate absent from HA | MEDIUM | DONE 2026-03-17 |
| Krill Oil absent from OI | MEDIUM | DONE 2026-03-17 (dedicated IQM entry) |
| Titanium Dioxide alias variants (colour, compound) | LOW | DONE 2026-03-17 (nano+space variants added) |
| Chopchinee identity conflict (needs_verification) | LOW | Open — pending authoritative monograph |
| Pyroxide HCL / Annine identity unknown | LOW | Open — tracked in NEEDS_VERIFICATION_INACTIVE_INGREDIENTS |
| OptiBerry(R) SB entry construction | LOW | DONE 2026-03-17 (optiberry IQM entry) |
