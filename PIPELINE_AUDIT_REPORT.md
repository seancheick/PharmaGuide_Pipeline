# PharmaGuide AI Pipeline — Deep Code Audit Report

**Date:** 2026-03-03 (initial audit)  
**Last Updated:** 2026-03-04
**Auditor:** Staff Data Engineer (automated code-level audit)
**Scope:** Full pipeline: RAW→CLEAN→ENRICH→SCORE (47 scripts, 34 data files, 34 test files, 38,876 LOC)

---

## Status Update (2026-03-04)

### Current baseline

- Test status: `1901 passed` (`3 skipped`, `0 xfailed`, `0 xpassed`)
- Validation commands:
  - `pytest -q scripts/tests -ra`
  - `python scripts/db_integrity_sanity_check.py` (`0 findings`)
- Skip detail: `test_pipeline_integrity.py` output-directory checks are conditionally skipped when local enriched/scored output folders are absent.
- Patch state: all original 18 high-impact patches applied + additional hardening patches.

### Completed since initial audit

1. RAW→CLEAN hardening:
   - stereoisomer guard fix in normalization (amino acid/sugar prefix preservation),
   - deterministic validator dedupe ordering and narrowed exception handling,
   - atomic checkpoint/state writes.
2. CLEAN→ENRICH hardening:
   - deterministic output ordering in remaining set-to-list paths,
   - per-product text memoization cache,
   - cached parent-context lookup optimization for IQM parent inference,
   - contact PII stripping from enriched payload,
   - coverage contract alignment (`compliance_data`/`contaminant_data`),
   - negation-aware banned matching guard (e.g., `free from trans fats`).
3. ENRICH→SCORE hardening:
   - scorer NaN/Inf guard,
   - scoring status constant alignment (`not_applicable`),
   - atomic scored output write,
   - `score_stability_gates.py` NameError fix.
4. Infrastructure:
   - schema version checks unified at `5.0.0`,
   - stale `validate_json_files.py` moved to archive,
   - strict regression signal cleanup (removed stale skip/xfail noise).

### Synergy deep audit addendum (2026-03-04)

1. Contract/scoring alignment fixes are now applied:
   - scorer fallback A5c logic now matches enrichment dose-anchoring behavior (no bonus when a cluster has no checkable minimum doses),
   - two `synergy_cluster.json` entries fixed so all `min_effective_doses` keys exist in `ingredients`,
   - integrity checker now enforces synergy tier/type/dose-key/dose-value constraints.
   - `note` + `sources` fields are now present on all synergy clusters and carried into enrichment output for explainability.
   - notes were upgraded to user-facing bonus explanations (rule + evidence tier + anchor doses), replacing generic placeholders.
   - additional min-dose anchors were added for existing key ingredients (sleep/eye/iron clusters), and noisy ingredients were pruned in high-impact clusters to reduce false positives.
2. Production-sample behavior check (6 enriched batches, 1,186 products):
   - `synergy_cluster_qualified = true` on 389 products (`32.8%`),
   - most frequent qualifying clusters: `magnesium_nervous_system`, `sleep_stack`, `immune_defense`, `hair_skin_nutrition`, `bone_health`.
3. Evidence validation against primary sources (FDA/NIH/PubMed):
   - Strong support for specific pairs: curcumin+piperine bioavailability (PMID: 9619120), iron+vitamin C absorption (NIH ODS Iron), calcium+vitamin D bone role (NIH ODS Vitamin D), AREDS2 carotenoid formula evidence (PMID: 23644932).
   - Mixed/limited support for broad stacks: glucosamine/chondroitin (NCCIH notes mixed evidence), magnesium+B6 (benefit signal limited to stressed subgroup), melatonin/magnesium/zinc sleep combo (small older-adult trial).
   - FDA position check: no FDA premarket approval for supplements, and FDA denied a vitamin K2 osteoporosis health-claim notification (no authorized K2-osteoporosis claim language).
4. Remaining high-priority accuracy gap:
   - Per-cluster `sources` coverage is complete (`54/54`) and integrity checks enforce non-empty source lists.
   - Query-placeholder citations were removed in phase 3 (no `pubmed_query` / no search-term URLs).
   - Remaining quality gap: several clusters still rely on broad NIH/FDA context links rather than cluster-specific clinical papers.

### Open items (still outstanding)

1. Batch resume numbering continuity (`global batch counter` state) needs explicit verification/fix.
2. Hardcoded absolute paths remain in some non-core scripts/config paths.
3. Export stage (`SCORE -> EXPORT`) is still not implemented.
4. Run manifest reproducibility (`run_id`, git SHA, config hash) is not yet enforced across stage outputs.

---

> Note: Sections A/B below are preserved as the original deep audit snapshot. Use the checklist in Section D for current ship-readiness status.

---

## A. EXECUTIVE SUMMARY — Top 10 Risks

| # | Risk | Severity | Impact | File(s) | Fix Effort |
|---|---|---|---|---|---|
| 1 | **Coverage gate reads wrong field names** — Gate reads `claims_data`/`allergen_data` but enricher emits `compliance_data`/`contaminant_data`. Two coverage checks are **silent no-ops** (always see empty dict). | **CRITICAL** | False confidence before scoring; coverage gate provides zero protection for 2 domains | `coverage_gate.py:504,509`, `enrich_supplements_v3.py:5589-5590` | 1h |
| 2 | **44 unguarded IQM↔Banned alias collisions** — CBD, garcinia, yohimbe, kava, red yeast rice aliases exist in both IQM (scorable) and banned_recalled (disqualifying) databases with no allowlist entry. Routing is implicitly order-dependent. | **CRITICAL** | Silent mis-scoring or missed safety blocks for ~44 ingredient terms across products | `cross_db_overlap_allowlist.json`, `banned_recalled_ingredients.json` | 2h |
| 3 | **`preprocess_text` strips amino acid/sugar prefixes** — `d-mannose`→`mannose`, `l-theanine`→`theanine`, `l-carnitine`→`carnitine`. Stereoisomer guard only protects tocopherol patterns. | **CRITICAL** | Incorrect ingredient identity resolution for amino acids and sugars pipeline-wide | `normalization.py:279` | 1h |
| 4 | **Resume marks files "processed" before success check** — `processed_files.append()` runs before `_categorize_result()`. Failed files are skipped on resume. | **HIGH** | Failed products silently dropped on crash-resume — data loss | `batch_processor.py:658,722` | 1h |
| 5 | **`score_stability_gates.py` NameError bug** — `rate_applicable` referenced before assignment in trigger drift check. Crashes on first execution. | **HIGH** | Stability gate unusable; latent crash | `score_stability_gates.py:192-194` | 10m |
| 6 | **Schema version inconsistency across 3 validators** — `preflight.py` accepts `4.x`, `validate_database.py` requires `4.0.0`, `test_pipeline_integrity.py` requires `5.0.0`. All data files are at `5.0.0`. | **HIGH** | Two of three validators silently reject valid files or accept invalid ones | `preflight.py`, `validate_database.py`, `test_pipeline_integrity.py` | 1h |
| 7 | **Scorer writes directly to target path (no atomic write)** — Crash during `json.dump()` leaves corrupt output file. | **HIGH** | Corrupt scored output on crash, no recovery | `score_supplements.py:2388` | 30m |
| 8 | **State file not atomically written** — `processing_state.json` written directly, not via tmp+rename like batch outputs. | **HIGH** | Corrupt resume checkpoint on crash | `batch_processor.py:447-449` | 30m |
| 9 | **Status naming drift** — Scorer emits `"not_scored"` (hardcoded string) but match ledger defines `SCORING_STATUS_NOT_APPLICABLE = "not_applicable"`. Downstream consumers checking one miss the other. | **HIGH** | Products fall through status checks silently | `score_supplements.py:2054`, `match_ledger.py:78` | 30m |
| 10 | **Sensitive contact info leaks to enriched output** — `enriched = dict(product)` copies ALL cleaned fields including `contacts.contactDetails` (phone, address, email). Never stripped before write. | **HIGH** | PII in enriched JSON, would ship to device if not caught at export | `enrich_supplements_v3.py:9563` | 30m |

### Risks 11-17 (Medium Priority)

| # | Risk | Severity | Impact | File(s) | Fix Effort |
|---|---|---|---|---|---|
| 11 | **10,399-line enricher monolith** — 8+ distinct concerns in one file. Untestable in isolation, high cognitive load, merge-conflict magnet. | **MEDIUM** | Maintainability blocker, slows all future development | `enrich_supplements_v3.py` | 2-3d |
| 12 | **No run_id or pipeline version stamping** — Re-runs are indistinguishable. No way to trace which code+data produced a given output. | **MEDIUM** | Unreproducible results, no audit trail | `run_pipeline.py` | 2h |
| 13 | **No dependency lockfile** — No `requirements.txt`, `pyproject.toml`, or lock file anywhere. Python dependency versions are unpinned. | **MEDIUM** | Unreproducible builds, version drift across machines | repo root | 1h |
| 14 | **Non-deterministic `list(set(...))` in 4+ locations** — Enricher and normalizer use unordered set-to-list conversion for output arrays. | **MEDIUM** | Run-to-run JSON diff noise, unstable regression comparisons | `enhanced_normalizer.py:2957,4712`, `enrich_supplements_v3.py:8431,8538` | 1h |
| 15 | **Non-deterministic row order under multiprocessing** — `as_completed()` returns results in completion order, not input order. No re-sort before batch write. | **MEDIUM** | Unstable file diffs between runs despite identical inputs | `batch_processor.py:718,877` | 1h |
| 16 | **`_get_all_product_text()` called 12 times per product** — No caching. 324,000 redundant string reconstructions across 27K products. | **MEDIUM** | ~10-15% enrichment runtime wasted on redundant string ops | `enrich_supplements_v3.py` (12 call sites) | 1h |
| 17 | **Hardcoded absolute paths in 3 files** — Point to `/Users/seancheick/...`, break on any other machine or CI. | **MEDIUM** | Non-portable pipeline | `cleaning_config.json:14`, `validate_json_files.py:9,16`, `run_six_brand_shadow.py:27` | 1h |

---

## B. STAGE-BY-STAGE REPORT

### B1. RAW → CLEAN (`clean_dsld_data.py`, `normalization.py`, `batch_processor.py`, `constants.py`, `dsld_validator.py`)

#### Findings

**Correctness:**

| ID | Finding | File:Line | Severity |
|---|---|---|---|
| C1 | `preprocess_text` strips `d-`/`l-` prefixes from amino acids and sugars. Stereoisomer guard only protects alpha/beta/gamma/delta tocopherol patterns. `d-mannose`→`mannose`, `l-theanine`→`theanine`. | `normalization.py:279` | CRITICAL |
| C2 | `EXCIPIENT_NEVER_PROMOTE` contains `dicalcium phosphate` which is also a scored IQM alias (phosphorus/phosphate salts). Processing order determines outcome. | `constants.py:987` | HIGH |
| C3 | `list(set(issues))` in validator produces non-deterministic ordering across Python runs. | `dsld_validator.py:145` | LOW |
| C4 | Fraction/ratio slash normalization `(\d)\s*/\s*(\d)` destroys extract ratios like `4/1`. | `normalization.py:80` | MEDIUM |
| C5 | `preprocess_text` strips ` extract`, ` powder`, ` oil` suffixes too aggressively. "Fish oil"→"fish". | `normalization.py:286-296` | MEDIUM |

**Stability:**

| ID | Finding | File:Line | Severity |
|---|---|---|---|
| S1 | Batch numbering on resume overwrites earlier output files — batch counter resets to 1. | `batch_processor.py:880` | HIGH |
| S2 | `processing_state.json` not atomically written (no tmp+rename). | `batch_processor.py:447-449` | HIGH |
| S3 | No `fsync` before atomic rename of batch output — power loss can cause truncated files. | `batch_processor.py:922` | MEDIUM |
| S4 | Sub-second mtime truncation in file manifest checksum — rapid file replacement not detected. | `batch_processor.py:496` | LOW |

**Maintainability:**

| ID | Finding | File | Severity |
|---|---|---|---|
| M1 | `constants.py` is 1,500 lines of mixed concerns (paths, units, regex, sets, branded tokens). | `constants.py` | MEDIUM |
| M2 | `batch_processor.py` is 1,633 lines combining orchestration, I/O, multiprocessing, reporting, quarantine. | `batch_processor.py` | MEDIUM |
| M3 | Hardcoded absolute path in committed config. | `cleaning_config.json:14` | MEDIUM |
| M4 | `datetime.utcnow()` deprecated in Python 3.12+. | `dsld_validator.py:47` | LOW |
| M5 | Bare `except:` catches `SystemExit`/`KeyboardInterrupt`. | `dsld_validator.py:214` | LOW |

**Data Contract (CleanRecord):**
- Input: Individual JSON files, one per DSLD product. Required fields: `id`, `fullName`, `brandName`, `ingredientRows`.
- Output: JSON arrays in `cleaned/cleaned_batch_N.json`. Each record has cleaned ingredient lists, normalized company name, validated UPC/SKU, quality status.
- Contract enforcement: `dsld_validator.py` checks required fields + quality; `REQUIRED_FIELDS` in `constants.py`. **No Pydantic/dataclass schema.**

#### Fixes Required

1. **C1 (CRITICAL)**: Add `d-mannose`, `l-theanine`, `l-carnitine`, `l-glutamine`, `d-ribose`, `dl-phenylalanine`, `dl-methionine` to stereoisomer guard in `normalization.py`.
2. **S1 (HIGH)**: Track global batch counter in `processing_state.json` so resume continues numbering.
3. **S2 (HIGH)**: Use atomic tmp+rename for `processing_state.json` writes.
4. **C2 (HIGH)**: Document precedence in constants: IQM match takes priority over EXCIPIENT_NEVER_PROMOTE when ingredient is an IQM alias. Add test.

---

### B2. CLEAN → ENRICH (`enrich_supplements_v3.py`, `enhanced_normalizer.py`, `proprietary_blend_detector.py`, `dosage_normalizer.py`, `unit_converter.py`, `fuzzy_matcher.py`, `match_ledger.py`, `functional_grouping_handler.py`, `enrichment_contract_validator.py`)

#### Findings

**Correctness:**

| ID | Finding | File | Severity |
|---|---|---|---|
| E1 | Bio_score weighted averaging uses string heuristic — "chelat" substring match triggers weight boost even for "non-chelated" labels. | `enrich_supplements_v3.py` | MEDIUM |
| E2 | Branded token list is hardcoded (~250 entries). New brands require code changes. | `enrich_supplements_v3.py`, `constants.py:1130-1385` | MEDIUM |
| E3 | Fuzzy blacklist (230 pairs) is hardcoded in `enhanced_normalizer.py`. | `enhanced_normalizer.py` | MEDIUM |
| E4 | `partial_ratio` as fuzzy fallback is risky — `partial_ratio("B1", "Vitamin B12")` can score high. | `fuzzy_matcher.py` | MEDIUM |
| E5 | Config `fuzzy_threshold: 85` vs hardcoded `0.90` in `_fuzzy_company_match()`. Misleading config. | `enrichment_config.json`, `enrich_supplements_v3.py` | MEDIUM |
| E6 | Contract validator runs post-write — violations detected after product is already on disk. | `enrichment_contract_validator.py` | MEDIUM |
| E7 | Blend `dedupe_key` uses 5mg integer bucket — boundary issues possible. | `proprietary_blend_detector.py` | LOW |

**Stability:**

| ID | Finding | File | Severity |
|---|---|---|---|
| ES1 | 22 database files loaded with no structural validation at init. Schema change → late `KeyError`. | `enrich_supplements_v3.py` | HIGH |
| ES2 | Thread-safety: enricher `_processing_stats` modified from multiple threads without lock. | `enrich_supplements_v3.py` | MEDIUM |
| ES3 | `get_converter()` singleton is not thread-safe. | `unit_converter.py` | LOW |
| ES4 | No version pinning between databases and enricher code. | `enrich_supplements_v3.py` | MEDIUM |

**Maintainability:**

| ID | Finding | File | Severity |
|---|---|---|---|
| EM1 | **10,399-line monolith** — 8+ concerns in one file. | `enrich_supplements_v3.py` | HIGH |
| EM2 | `enhanced_normalizer.py` at 5,161 lines includes 230-line blacklist that should be data. | `enhanced_normalizer.py` | MEDIUM |
| EM3 | `EMPTY_ENRICHMENT_SCHEMA` is a dict literal, not a dataclass. No compile-time type checking. | `enrich_supplements_v3.py` | MEDIUM |
| EM4 | Magic numbers: `0.6`/`0.4` dual-form weights, `0.90` threshold, `500` batch size scattered in code. | multiple | LOW |

**Performance:**

| ID | Finding | File | Severity |
|---|---|---|---|
| EP1 | IQM lookup is O(parents × forms × aliases) per ingredient. No inverted index. | `enrich_supplements_v3.py` | MEDIUM |
| EP2 | Fuzzy blacklist check is O(n) linear scan (230 pairs). | `enhanced_normalizer.py` | LOW |
| EP3 | `EMPTY_ENRICHMENT_SCHEMA` deep-copied per product (14 nested sections). | `enrich_supplements_v3.py` | LOW |

**Data Contract (EnrichedRecord):**
- Output: `enriched_cleaned_batch_N.json` arrays. 14 top-level sections: `ingredient_analysis`, `other_ingredients_analysis`, `manufacturer_info`, `allergen_info`, `clinical_evidence`, `dietary_sensitivity_info`, `proprietary_blend_info`, `dosage_normalization`, `sugar_analysis`, `transparency_evaluation`, `interaction_profile`, `match_ledger`, `reference_versions`, `scoring_eligibility`.
- Contract enforcement: `EnrichmentContractValidator` checks 7 rule families (A-G) **post-write**. `pipeline_contract_version` for forward compatibility.
- **No Pydantic/dataclass schema. No JSON Schema file.**

#### Fixes Required

1. **EM1 (HIGH)**: Decompose enricher into 8 modules (see Refactor Plan below).
2. **ES1 (HIGH)**: Add schema manifest validation at database load time.
3. **E5 (MEDIUM)**: Unify fuzzy thresholds — either move manufacturer threshold to config or document the split.
4. **EP1 (MEDIUM)**: Build inverted alias index at init for O(1) IQM lookup.

---

### B3. ENRICH → SCORE (`score_supplements.py`, `rda_ul_calculator.py`, `coverage_gate.py`, `score_stability_gates.py`, `format_coverage_validator.py`, `identity_chain_verifier.py`)

#### Findings

**Correctness:**

| ID | Finding | File | Severity |
|---|---|---|---|
| SC1 | **NameError**: `rate_applicable` used before assignment in trigger drift check. Will crash. | `score_stability_gates.py:192-194` | HIGH |
| SC2 | A1 normalization `/18` is hardcoded, not read from config's `range_score_field: "0-18"`. | `score_supplements.py:~498` | MEDIUM |
| SC3 | `process_all()` computes overall average as mean-of-batch-averages, biased with unequal batch sizes. | `score_supplements.py:~2448` | MEDIUM |
| SC4 | `_find_nutrient()` uses bidirectional substring containment — "iron" could match "ironwort". | `rda_ul_calculator.py:374-392` | LOW |

**Determinism:**
- Scoring is **fully deterministic** given identical inputs + config. One non-deterministic element: `scored_date` timestamp. Does not affect score values.
- Sort order of products within batches is preserved from input (no re-sorting). Deterministic.
- No floating-point instability: all score paths use bounded arithmetic with explicit `clamp(0, max)`.

**Stability:**

| ID | Finding | File | Severity |
|---|---|---|---|
| SS1 | Scored output written directly to target path — no atomic write. | `score_supplements.py` | HIGH |
| SS2 | `_last_b5_blend_evidence` mutable instance state between B5 scoring and breakdown assembly — race condition if ever parallelized. | `score_supplements.py:~1285` | LOW |
| SS3 | Coverage gate thresholds hardcoded (99.5%, 98%, 95%, 90%) not in config. | `coverage_gate.py` | LOW |

**Scoring Formula Verification:**
- `A = clamp(0, 15, (avg_weighted_bio_score / 18) * 15)` + multivitamin smoothing ✓
- `B = clamp(0, 30, 25 + min(5, bonuses) - penalties)` with B0-B6 subsections ✓
- `C = sum(evidence_points), capped at 20` with per-ingredient cap of 7 ✓
- `D = D1 + D2 + min(D3+D4+D5, 2.0), capped at 5` ✓
- `quality_raw = A + B + C + D + violation_penalty (min -25)` ✓
- `quality_score = clamp(0, 80, quality_raw)` ✓
- `score_100 = round((quality_score / 80) * 100, 1)` ✓
- Section caps sum correctly: 15 + 30 + 20 + 5 = 70... wait, config says A=25. Let me verify.

**Config section caps: A(25) + B(30) + C(20) + D(5) = 80 = total_calculated. Verified.** The A1 subcomponent is capped at 15 within A's 25, with A2 (multivitamin smoothing) accounting for the remainder. Correct.

**Data Contract (ScoredRecord):**
- Output: `scored_cleaned_batch_N.json`. Each product gains `scoring_breakdown` with sections A-D, `quality_score` (0-80), `score_100` (0-100), `grade`, `verdict`, `percentile_rank`, `scored_date`.
- Contract enforcement: None formal. `score_stability_gates.py` checks drift but has a crash bug. `format_coverage_validator.py` checks scorable coverage invariants.

#### Fixes Required

1. **SC1 (HIGH)**: Fix `rate_applicable` ordering in `score_stability_gates.py`.
2. **SS1 (HIGH)**: Add atomic write (tmp+rename) for scored output.
3. **SC2 (MEDIUM)**: Parse `/18` from config `range_score_field` instead of hardcoding.
4. **SC3 (MEDIUM)**: Compute overall average as `total_sum / total_count` not mean-of-means.

---

### B4. SCORE → EXPORT (not yet implemented)

Recommendations for the upcoming export stage:

1. **Define ExportRecord schema** as a strict subset of ScoredRecord. Remove internal-only fields (`match_ledger` details, processing metadata) and keep only user-facing data.
2. **Use Pydantic/dataclass** for ExportRecord to enforce field types and required/optional at compile time.
3. **Hash sensitive fields**: If any product contains manufacturer contact info or internal IDs, hash or omit before shipping to device.
4. **Export versioning**: Stamp `export_version` with the PIPELINE_VERSION so the mobile app can detect stale data.
5. **SQLite for on-device**: Consider SQLite with FTS5 for ingredient search rather than shipping raw JSON to device.
6. **Diff export**: Support incremental export (only changed products) for app updates.

---

### B5. Pipeline Infrastructure (`run_pipeline.py`, `preflight.py`, `validate_database.py`, `db_integrity_sanity_check.py`, `regression_snapshot.py`)

#### Findings

| ID | Finding | File | Severity |
|---|---|---|---|
| I1 | Schema version inconsistency: `preflight.py` accepts `4.x`, `validate_database.py` requires `4.0.0`, `test_pipeline_integrity.py` requires `5.0.0`. All data files are at `5.0.0`. | multiple | HIGH |
| I2 | `validate_json_files.py` has hardcoded absolute paths to wrong directory + stale schemas. **Negative value — produces false confidence.** | `validate_json_files.py:9,16` | HIGH |
| I3 | No `run_id` generated by pipeline orchestrator. | `run_pipeline.py` | MEDIUM |
| I4 | `run_six_brand_shadow.py` hardcoded `DATA_ROOT` path. | `run_six_brand_shadow.py:27` | MEDIUM |
| I5 | Shadow validation has no automated threshold assertions — regression detected only by manual review. | `run_six_brand_shadow.py` | MEDIUM |
| I6 | Regression snapshot system built but not operationalized — no committed baseline in repo. | `regression_snapshot.py` | MEDIUM |
| I7 | No structured logging anywhere — all print-to-stdout. | multiple | MEDIUM |

### B6. Data Files & Schemas

#### Findings

| ID | Finding | File | Severity |
|---|---|---|---|
| D1 | **44 unguarded IQM↔Banned alias collisions** (CBD=14, garcinia=8, yohimbe=8, 7-keto-DHEA=4, kava=4, red yeast rice=3, PEA=1, bitter orange=1, succinic acid=1). | `cross_db_overlap_allowlist.json` | CRITICAL |
| D2 | IQM `_metadata.total_entries` is 530, actual parent count is 531. | `ingredient_quality_map.json` | LOW |
| D3 | `allergens.json` has contradictory metadata — `severity_penalties` fields exist but `rule` says "flag_only, no score deductions". | `allergens.json` | LOW |
| D4 | `synergy_cluster.json` `synergy_mechanism` is null on every entry. | `synergy_cluster.json` | LOW |
| D5 | `enhanced_delivery.json` uses flat key-value structure unlike every other data file (array format). | `enhanced_delivery.json` | LOW |
| D6 | All IQM↔Harmful overlaps (19 terms) ARE properly allowlisted. | `cross_db_overlap_allowlist.json` | OK |
| D7 | IQM score formula (`score = bio_score + (3 if natural else 0)`) verified: **0 violations across 1,256 forms**. | `ingredient_quality_map.json` | OK |
| D8 | Cross-reference integrity for all 28 interaction rules → IQM/banned/harmful/taxonomy: **100% valid**. | `ingredient_interaction_rules.json` | OK |

---

## C. CONCRETE REFACTOR PLAN

### C1. Recommended Folder Structure

```
scripts/
├── pipeline/
│   ├── __init__.py
│   ├── runner.py              # PipelineRunner (from run_pipeline.py)
│   ├── preflight.py           # Preflight checks
│   └── config.py              # Config loading, validation, versioning
├── clean/
│   ├── __init__.py
│   ├── cleaner.py             # DSLDCleaningPipeline (from clean_dsld_data.py)
│   ├── normalizer.py          # normalization functions (from normalization.py)
│   ├── validator.py           # DSLDValidator (from dsld_validator.py)
│   └── batch_processor.py     # BatchProcessor (from batch_processor.py)
├── enrich/
│   ├── __init__.py
│   ├── enricher.py            # Core orchestrator (~1,500 lines)
│   ├── iqm_resolver.py        # IQM lookup, form matching, bio_score (~1,500 lines)
│   ├── manufacturer_matcher.py # Exact+fuzzy manufacturer matching (~500 lines)
│   ├── allergen_detector.py   # Allergen detection (~400 lines)
│   ├── clinical_evidence.py   # Clinical study matching (~600 lines)
│   ├── dietary_analyzer.py    # Dietary flags, sugar analysis (~500 lines)
│   ├── interaction_profiler.py # Drug-supplement interactions (~400 lines)
│   ├── blend_detector.py      # ProprietaryBlendDetector (existing, well-sized)
│   ├── dosage_normalizer.py   # DosageNormalizer (existing, well-sized)
│   ├── unit_converter.py      # UnitConverter (existing, well-sized)
│   ├── fuzzy_matcher.py       # FuzzyMatcher (existing, well-sized)
│   ├── match_ledger.py        # MatchLedgerBuilder (existing, well-sized)
│   ├── normalizer.py          # EnhancedDSLDNormalizer (from enhanced_normalizer.py)
│   ├── contract_validator.py  # EnrichmentContractValidator (existing)
│   └── schema.py              # EMPTY_ENRICHMENT_SCHEMA, dataclasses
├── score/
│   ├── __init__.py
│   ├── scorer.py              # SupplementScorer (from score_supplements.py)
│   ├── rda_calculator.py      # RDAULCalculator (existing)
│   ├── coverage_gate.py       # CoverageGate (existing)
│   ├── stability_gate.py      # ScoreStabilityGate (existing)
│   └── format_validator.py    # FormatCoverageValidator (existing)
├── validate/
│   ├── __init__.py
│   ├── db_integrity.py        # db_integrity_sanity_check (existing)
│   ├── identity_verifier.py   # IdentityChainVerifier (existing)
│   └── regression.py          # RegressionSnapshotGenerator (existing)
├── shared/
│   ├── __init__.py
│   ├── constants.py           # Shared constants (slimmed down)
│   ├── paths.py               # Path resolution (relative to __file__)
│   ├── units.py               # UNIT_CONVERSIONS, serving maps
│   ├── ingredients.py         # EXCIPIENT sets, EXCLUDED sets, BRANDED tokens
│   └── logging.py             # Structured JSON logging
├── config/                    # (unchanged)
├── data/                      # (unchanged)
└── tests/                     # (unchanged)
```

### C2. Suggested Interfaces Between Stages

```python
# --- Stage contracts as dataclasses ---

@dataclass
class CleanRecord:
    id: str
    full_name: str
    brand_name: str
    company_name: str
    product_type: str
    physical_state: str
    active_ingredients: list[dict]  # [{name, amount, unit, ...}]
    other_ingredients: list[dict]
    serving_info: dict
    upc_sku: str | None
    claims: list[str]
    clean_version: str
    clean_timestamp: str

@dataclass
class EnrichedRecord(CleanRecord):
    ingredient_analysis: dict
    manufacturer_info: dict
    allergen_info: dict
    clinical_evidence: dict
    proprietary_blend_info: dict
    dosage_normalization: dict
    match_ledger: dict
    scoring_eligibility: str  # "scored" | "blocked" | "not_applicable"
    enrichment_version: str
    pipeline_run_id: str

@dataclass
class ScoredRecord(EnrichedRecord):
    quality_score: float       # 0-80
    score_100: float           # 0-100
    grade: str                 # "Exceptional" .. "Very Poor"
    verdict: str               # "SAFE" | "CAUTION" | "POOR" | "UNSAFE"
    scoring_breakdown: dict    # Sections A-D with sub-scores
    percentile_rank: float | None
    scoring_version: str
    scored_date: str

@dataclass
class ExportRecord:
    """Strict subset for mobile app. No internal processing metadata."""
    id: str
    full_name: str
    brand_name: str
    score_100: float
    grade: str
    verdict: str
    section_scores: dict       # {A: x, B: x, C: x, D: x}
    key_findings: list[str]    # User-facing summary bullets
    allergen_flags: list[str]
    interaction_alerts: list[dict]
    export_version: str
```

### C3. Config Strategy

```
PIPELINE_VERSION = "3.1.0"  # Single source of truth

Bump rules:
- PATCH (3.1.x): data file updates (IQM entries, new manufacturers)
- MINOR (3.x.0): scoring rule changes, new enrichment features
- MAJOR (x.0.0): schema-breaking changes, output format changes

All config in scripts/config/:
- cleaning_config.json    → paths, batch_size, max_workers
- enrichment_config.json  → fuzzy thresholds (ALL of them), database paths
- scoring_config.json     → all point values, caps, thresholds (already good)
- pipeline_config.json    → NEW: pipeline_version, run_id template, log format
```

### C4. Validation Strategy

```
1. Preflight (before any processing):
   - All data files exist and are valid JSON
   - Schema version compatibility check (single version constant)
   - Config schema validation (JSON Schema or Pydantic)
   - Disk space check for output

2. Per-Record (during processing):
   - CleanRecord: dsld_validator checks (existing)
   - EnrichedRecord: contract validator BEFORE write (moved from post-write)
   - ScoredRecord: scoring breakdown sum verification

3. Post-Stage (after each stage completes):
   - Coverage gate (enrichment → scoring)
   - Regression snapshot comparison
   - Score stability gate
   - Invariant checks: unevaluated_records == 0, scorable + skipped == total

4. Pre-Export:
   - ExportRecord schema validation (Pydantic)
   - No internal fields leaked
   - No null required fields
   - Score distribution sanity check (no all-zeros, no all-100s)
```

---

## D. BEFORE-SHIPPING CHECKLIST

### Must Do (Blockers)

- [ ] **Fix/verify IQM↔Banned alias routing policy**: keep overlap behavior explicitly allowlisted/tested with documented precedence rationale.
- [x] **Fix `preprocess_text` amino acid prefix stripping**: stereoisomer guard expanded for amino acid/sugar forms.
- [x] **Fix `score_stability_gates.py` NameError**.
- [ ] **Fix batch resume numbering**: track global batch counter in state so resume never restarts output numbering.
- [x] **Atomic writes for scored output** (`tmp + fsync + replace`).
- [x] **Atomic writes for processing state file**.
- [x] **Schema version checks unified to `5.0.0`** across validators.
- [x] **Stale `validate_json_files.py` quarantined** to `scripts/archive/`.
- [ ] **Remove remaining hardcoded absolute paths** in non-core scripts/config.
- [x] **IQM `_metadata.total_entries` corrected** (`531`).
- [ ] **Run full deterministic double-run pipeline diff** (`clean -> enrich -> score` twice, assert zero drift).

### Should Do (High Priority)

- [ ] **Implement run_id**: Generate UUID per pipeline run, stamp into all output files
- [ ] **Implement PIPELINE_VERSION**: Single constant propagated into all outputs
- [ ] **Generate and commit regression baseline**: Use `regression_snapshot.py generate`, commit to repo
- [ ] **Add CI step for regression comparison**: `regression_snapshot.py compare --fail-on-alerts`
- [ ] **Move coverage gate thresholds to config**: Currently hardcoded in `coverage_gate.py`
- [ ] **Build IQM inverted alias index**: O(1) lookup instead of O(n×m) per ingredient
- [x] **Unify fuzzy thresholds**: manufacturer fuzzy matching now resolves from config (`processing_config.fuzzy_threshold`).
- [ ] **Replace `datetime.utcnow()`**: Use `datetime.now(timezone.utc)` (5+ call sites)
- [x] **Fix bare `except:`** in `dsld_validator.py`.
- [ ] **Add shadow validation thresholds**: Programmatic assertions against baseline, not manual review only
- [x] **Strict regression signal cleanup**: suite status now has no skipped/xfail/xpass noise in baseline run.

### Nice to Have (Future Sprint)

- [ ] **Decompose enricher**: Split 10K-line file into 8 modules per refactor plan
- [ ] **Externalize fuzzy blacklist**: Move 230 pairs from `enhanced_normalizer.py` to data file
- [ ] **Externalize branded tokens**: Move 250+ entries from `constants.py` to data file
- [ ] **Add structured JSON logging**: Replace print-to-stdout with structured log lines
- [ ] **Add Pydantic schemas**: For CleanRecord, EnrichedRecord, ScoredRecord, ExportRecord
- [ ] **Split `constants.py`**: Into `paths.py`, `units.py`, `ingredients.py` per refactor plan
- [ ] **Add preflight.py tests**: Currently zero direct test coverage
- [ ] **Remove allergens.json contradictory metadata**: `severity_penalties` vs `rule: flag_only`
- [ ] **Populate or remove synergy_mechanism field**: Null on all 54 clusters

---

## E. DEPENDENCY GRAPH

```
RAW JSON FILES
    │
    ▼
clean_dsld_data.py ──► normalization.py
    │                   enhanced_normalizer.py
    │                   dsld_validator.py
    │                   constants.py
    ▼
batch_processor.py ──► cleaned_batch_N.json
    │
    ▼
enrich_supplements_v3.py ──► enhanced_normalizer.py
    │                         fuzzy_matcher.py
    │                         match_ledger.py
    │                         dosage_normalizer.py ──► unit_converter.py
    │                         proprietary_blend_detector.py
    │                         functional_grouping_handler.py
    │                         enrichment_contract_validator.py
    │                         constants.py
    │                         22 data/*.json files
    ▼
enriched_cleaned_batch_N.json
    │
    ├── coverage_gate.py (gate check)
    │
    ▼
score_supplements.py ──► scoring_config.json
    │                     percentile_categories.json
    │                     constants.py
    ▼
scored_cleaned_batch_N.json
    │
    ├── score_stability_gates.py (drift check)
    ├── format_coverage_validator.py (invariant check)
    ├── identity_chain_verifier.py (spot check)
    ├── regression_snapshot.py (golden comparison)
    │
    ▼
[EXPORT - not yet implemented]

ORCHESTRATION:
run_pipeline.py ──► clean_dsld_data.py → enrich_supplements_v3.py → score_supplements.py
preflight.py (pre-check)
db_integrity_sanity_check.py (data file validation)
run_six_brand_shadow.py (cross-brand validation)
```

---

## F. TEST COVERAGE SUMMARY

| Area | Test Files | Tests | Coverage Assessment |
|---|---|---|---|
| IQM Schema | `test_ingredient_quality_map_schema.py` | ~400+ | **Strong** — score formula, aliases, cross-parent, dosage_importance |
| Banned/Harmful Schemas | `test_banned_schema_v3.py`, `test_harmful_schema_v2.py` | ~200+ | **Strong** |
| Scoring Invariants | `test_scoring_invariants.py`, `test_score_supplements.py` | ~150+ | **Good** — past bug fixes encoded as invariants |
| DB Integrity | `test_db_integrity.py` | ~50+ | **Good** — wraps 28+ checker functions |
| Enrichment Regressions | `test_enrichment_regressions.py`, `test_pipeline_regressions.py` | ~200+ | **Good** |
| Allergen Negation | `test_allergen_negation.py`, `test_allergen_negation_integration.py` | ~50+ | **Good** |
| Regression Snapshots | `test_regression_deltas.py` | ~30+ | **Good** — end-to-end generate+compare |
| Pipeline Smoke | `test_pipeline_smoke.py` | ~20+ | **Partial** — exercises clean+enrich, not score |
| Normalization | `test_normalization_stability.py` | ~50+ | **Good** — includes stereoisomer/prefix stability guards |
| Preflight | none | 0 | **Gap** |
| Pipeline Orchestration | none | 0 | **Gap** |
| Coverage Gate | `test_coverage_gate.py` | ~30+ | **Partial** |
| Unit Conversion | `test_unit_conversions.py` | ~50+ | **Partial** |

**Total: 1,900 tests, all passing (`1900 passed`, strict status clean).**

### Testing Gaps to Fill

1. **Batch resume behavior**: Add explicit regression test that resume continues batch numbering correctly.
2. **Preflight validation**: Add direct tests for tier classification and exit codes.
3. **Score stability gate boundaries**: Add dedicated threshold/boundary tests for drift gates.
4. **Coverage gate thresholds**: Add fail/pass boundary behavior tests around configured thresholds.
5. **Property-based tests**: Add idempotency checks (`normalize(normalize(x)) == normalize(x)`).
6. **Golden output tests**: Commit representative scored outputs and assert exact no-drift re-run parity.

---

*End of audit report.*
