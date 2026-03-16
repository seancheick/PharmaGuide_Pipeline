# Architecture

**Analysis Date:** 2026-03-16

## Pattern Overview

**Overall:** Three-stage data processing pipeline (Clean → Enrich → Score) with modular separation of concerns and contract-based communication between stages.

**Key Characteristics:**
- Single-pass transformation at each stage (no circular dependencies)
- Orchestrated by `run_pipeline.py` with optional coverage gating between stages
- Heavy use of reference databases in data-driven fashion
- Batch processing with multiprocessing support and resume capability
- Clear separation: normalization (stage 1), classification/matching (stage 2), arithmetic scoring (stage 3)

## Layers

**Orchestration Layer:**
- Purpose: Manage pipeline execution, validation, and error handling
- Location: `scripts/run_pipeline.py`
- Contains: PipelineRunner class orchestrating all three stages
- Depends on: Individual stage scripts, coverage_gate module
- Used by: CLI entry point, external automation scripts

**Data Cleaning & Normalization (Stage 1):**
- Purpose: Transform raw DSLD label data into canonicalized structure
- Location: `scripts/clean_dsld_data.py` (entry), `scripts/enhanced_normalizer.py` (core)
- Contains: DSLDCleaningPipeline orchestrator, EnhancedDSLDNormalizer processor, batch handling, validation
- Depends on: Reference data (IQM, harmful additives, allergens, botanicals), fuzzy matching libraries
- Used by: Produces cleaned JSON consumed by enrichment stage

**Enrichment & Classification (Stage 2):**
- Purpose: Collect and organize data from reference databases for scoring
- Location: `scripts/enrich_supplements_v3.py` (entry), supporting detectors (proprietary_blend_detector.py, unit_converter.py, dosage_normalizer.py)
- Contains: Enricher, data collectors (quality/contaminants/compliance/evidence/manufacturer), projectors
- Depends on: Reference databases (>15 JSON files), specialized detector modules
- Used by: Produces enriched JSON with scoring-friendly flattened fields, consumed by scoring

**Batch Processing & Utilities:**
- Purpose: Distributed file processing, logging, validation, state management
- Location: `scripts/batch_processor.py` (batch coordinator), `scripts/dsld_validator.py` (schema validation)
- Contains: PerformanceTracker, ProcessingResult, BatchState, resume logic
- Depends on: ProcessPoolExecutor for parallelization
- Used by: Cleaning and enrichment stages for file-level processing

**Scoring Engine (Stage 3):**
- Purpose: Apply arithmetic formulas to enriched data, assign verdicts
- Location: `scripts/score_supplements.py`
- Contains: SupplementScorer class with A/B/C/D section logic, gating rules, verdict derivation
- Depends on: Only enriched JSON (no reference database loads), scoring_config.json
- Used by: Produces final scored products with quality_score, verdict, and diagnostic flags

**Reference Databases:**
- Purpose: Provide authoritative ingredient/manufacturer/compliance data for matching and enrichment
- Location: `scripts/data/*.json` (~35 files)
- Contains: ingredient_quality_map (main taxonomy), harmful_additives, banned_recalled_ingredients, allergens, etc.
- Key files: `ingredient_quality_map.json` (1.7MB master DB), `harmful_additives.json` (602KB), `other_ingredients.json` (481KB)
- Used by: Cleaning (fuzzy matching), Enrichment (classification/matching)

**Configuration Management:**
- Purpose: Control pipeline behavior via JSON configs rather than code changes
- Location: `scripts/config/` (cleaning_config.json, enrichment_config.json, scoring_config.json)
- Contains: Batch sizes, thresholds, feature flags (shadow_mode, require_full_mapping)
- Used by: Each stage reads its corresponding config at startup

## Data Flow

**Full Pipeline Flow:**

```
raw_data/*.json (DSLD label data)
    ↓ [STAGE 1: CLEAN]
    • EnhancedDSLDNormalizer.normalize_product()
    • Fuzzy match ingredients to IQM
    • Detect allergens, harmful additives
    • Normalize dosages, units, serving sizes
    • Extract certifications, claims
    • Build canonical structure
    ↓
output_*/cleaned/*.json (Canonicalized JSON)
    ↓ [STAGE 2: ENRICH]
    • Load all reference databases
    • Match ingredients to quality tiers
    • Detect proprietary blends
    • Collect contaminant data
    • Extract compliance/certification facts
    • Normalize dosages via UnitConverter
    • Collect clinical evidence references
    • Project convenience fields for scorer
    ↓
output_*_enriched/enriched/*.json (Enriched with metadata)
    ↓ [OPTIONAL STAGE 2.5: COVERAGE GATE]
    • CoverageGate.check_batch()
    • Validate coverage % and correctness
    • Can block scoring if thresholds not met
    ↓
output_*_scored/scored/*.json (Final scored products)
```

**Per-Product Processing Flow:**

1. **Clean Stage (per file in batch):**
   - Load raw JSON
   - Parse ingredient lists
   - Apply EnhancedDSLDNormalizer.normalize_product()
   - Validate structure
   - Write cleaned JSON
   - Track validation errors, unmapped ingredients

2. **Enrich Stage (per cleaned product):**
   - Load enriched_product() in sequence
   - Create domain blocks (ingredient_quality_data, contaminant_data, etc.)
   - Perform ingredient-to-IQM matching
   - Apply classification rules (scorable vs non-scorable)
   - Collect evidence from backed_clinical_studies
   - Project convenience fields
   - Return enriched product dict

3. **Score Stage (per enriched product):**
   - Validate enriched contract
   - Check banned/recalled gate (B0)
   - Check mapping gate (if require_full_mapping=true)
   - Score sections A (ingredient profile), B (safety/compliance), C (manufacturing), D (transparency)
   - Apply manufacturer violation deduction
   - Clamp to [0, 80]
   - Derive verdict by precedence
   - Emit with breakdown details

**State Management:**

- Batch processing maintains BatchState (progress file at `.batch_state.json`)
- Resume capability: If pipeline interrupted, can restart at last incomplete batch
- PerformanceTracker collects file-level timing for diagnostics
- ProcessingResult dataclass tracks per-file status, unmapped details, validation errors

**Error Handling Contracts:**

- Clean stage: Catches JSON load errors, normalization errors, validation errors
- Enrich stage: Graceful degradation if reference DB load fails (logged but not fatal)
- Score stage: Early gates return NOT_APPLICABLE or BLOCKED; arithmetic errors logged but clamped
- Overall: Pipeline halts on stage failure unless --dry-run mode active

## Key Abstractions

**EnhancedDSLDNormalizer:**
- Purpose: Single-source normalization of ingredient text and product metadata
- Examples: `scripts/enhanced_normalizer.py` (800+ lines)
- Pattern: Method per category (normalize_ingredient_text, normalize_dosages, extract_allergens)
- Used by: Clean stage, directly invoked in batch processor loops

**SupplementScorer:**
- Purpose: Encapsulates all scoring logic (sections A/B/C/D, gates, verdicts)
- Examples: `scripts/score_supplements.py` (2500+ lines)
- Pattern: score_product() orchestrates sub-scorers for each section
- State: Carries enriched product dict + config through all scoring decisions

**Reference Database Loaders:**
- Purpose: Load and cache JSON databases at startup
- Examples: Constants module loads IQM, harmful_additives, allergens
- Pattern: Load once at module initialization, reuse via imports
- Invariant: All reference data must validate schema before pipeline proceeds

**UnitConverter & DosageNormalizer:**
- Purpose: Normalize ingredient dosages to canonical forms for scoring
- Examples: `scripts/unit_converter.py`, `scripts/dosage_normalizer.py`
- Pattern: Conversion rules + context-aware (vitamin D IU to mcg varies by form)
- Used by: Enrichment stage projects normalized_dosage field

**ProprietaryBlendDetector:**
- Purpose: Identify and analyze proprietary blend structures (blend headers, weight-loss formulas)
- Examples: `scripts/proprietary_blend_detector.py`
- Pattern: Regex-based detection + formula weighting
- Consumed by: Enrichment builds proprietary_blends array field

**CoverageGate:**
- Purpose: Validate enriched products meet quality/coverage thresholds before scoring
- Examples: `scripts/coverage_gate.py`
- Pattern: Batch-level check; can block or warn-only based on config
- Invariant: Optional but recommended; enforced by run_pipeline.py if not skipped

**MatchLedger:**
- Purpose: Track ingredient matching decisions (which IQM entries matched, confidence, why skipped)
- Examples: `scripts/match_ledger.py`
- Pattern: Dataclass with scoring status enums (SCORED, BLOCKED, NOT_APPLICABLE)
- Consumed by: Score stage uses match_ledger diagnostics for verdict logic

## Entry Points

**Pipeline Orchestrator:**
- Location: `scripts/run_pipeline.py`
- Triggers: Manual CLI invocation, scheduled jobs
- Responsibilities: Validate preflight, execute stages in sequence, collect results, report timing

**Clean Stage Entry:**
- Location: `scripts/clean_dsld_data.py`
- Triggers: run_pipeline.py or direct invocation
- Responsibilities: Initialize DSLDCleaningPipeline, load config, call BatchProcessor.process()

**Enrich Stage Entry:**
- Location: `scripts/enrich_supplements_v3.py`
- Triggers: run_pipeline.py or direct invocation
- Responsibilities: Load reference databases, iterate cleaned files, call Enricher.enrich_product()

**Score Stage Entry:**
- Location: `scripts/score_supplements.py`
- Triggers: run_pipeline.py or direct invocation
- Responsibilities: Initialize SupplementScorer, iterate enriched files, emit scored JSON

**Coverage Gate Entry (Optional):**
- Location: `scripts/coverage_gate.py`
- Triggers: run_pipeline.py between enrich and score (unless --skip-coverage-gate)
- Responsibilities: Load enriched batch, check thresholds, return can_proceed boolean

## Error Handling

**Strategy:** Fail fast on critical preflight checks; graceful degradation during processing; detailed error logging for diagnostics.

**Patterns:**

- **Preflight Validation:** Check data directory exists before running pipeline (`scripts/data/` critical files validated in run_pipeline.py:_validate_data_dir())
- **Per-File Error Handling:** Each file wrapped in try-except; errors collected in ProcessingResult.validation_errors
- **Database Load Errors:** Reference databases logged but don't halt (warning level) unless critical dependency missing
- **Stage Failure:** If clean/enrich fails mid-batch, pipeline halts with non-zero exit code; progress saved for resume
- **Scoring Errors:** Arithmetic errors clamped to defaults; blocked products marked as NOT_APPLICABLE rather than crashing
- **Output Validation:** Scored products validated schema before writing; invalid products written to separate rejection file

## Cross-Cutting Concerns

**Logging:**
- Framework: Python logging module
- Configuration: LOG_FORMAT, LOG_DATE_FORMAT defined in `scripts/constants.py`
- Levels: DEBUG (entry/exit), INFO (progress), WARNING (skipped items), ERROR (failures)
- Output: stdout (streaming) + log files in `scripts/logs/`

**Validation:**
- Cleaning: DSLDValidator checks canonical structure (required fields, type correctness)
- Enrichment: Enricher validates output has minimum scoring contract (dsld_id, product_name, ingredient metadata)
- Scoring: SupplementScorer validates enriched product before processing
- Overall: schema_version field tracked to detect incompatible data contracts

**Ingredient Matching:**
- Primary: IQM lookup (exact + fuzzy match via fuzzywuzzy or rapidfuzz)
- Fallback: Enhanced normalizer applies alias expansion, standardization patterns
- Tracking: match_ledger records match confidence, skip reasons for diagnostics
- Precision: Fuzzy threshold tunable via FUZZY_MATCHING_THRESHOLDS in constants

**Performance:**
- Batching: Configurable batch_size (default 100) in cleaning_config.json
- Parallelization: ProcessPoolExecutor with num_workers tuned to CPU count
- Profiling: PerformanceTracker logs per-file timing, identifies slowest files
- Memory: Optional psutil integration tracks peak memory usage during runs

**Configuration:**
- Paths: All relative to scripts/ directory (absolute paths also supported)
- Overrides: CLI args override config JSON (e.g., --output-prefix overrides paths.output_prefix)
- Validation: Config schema validated at load time in DSLDCleaningPipeline._load_config()

---

*Architecture analysis: 2026-03-16*
