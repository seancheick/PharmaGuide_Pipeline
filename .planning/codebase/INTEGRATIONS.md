# External Integrations

**Analysis Date:** 2026-03-16

## APIs & External Services

**NIH DSLD (Dietary Supplement Label Database):**
- Service: National Institutes of Health - Dietary Supplement Label Database
- What it's used for: Reference supplement data and image PDF storage
- Image URL Template: `https://api.ods.od.nih.gov/dsld/s3/pdf/{}.pdf` (defined in `scripts/constants.py`)
- Integration type: Read-only, referenced in documentation and product reference data

## Data Storage

**Databases:**
- None - Project uses file-based JSON storage exclusively

**File Storage:**
- Local filesystem only
  - Primary: `scripts/data/` directory containing reference JSON databases
  - Input: User-provided JSON/CSV files from `~/Documents/DataSetDsld/`
  - Output: `scripts/output_*/` directories for processed results (regenerable, in .gitignore)
  - Logs: `scripts/logs/` for processing logs (regenerable, in .gitignore)

**Caching:**
- In-memory caching via Python's `functools.lru_cache` decorator used in `enhanced_normalizer.py` for fuzzy matching
- No persistent cache layer

## Authentication & Identity

**Auth Provider:**
- None - Project is fully local, no API authentication required
- All data is either embedded in codebase or provided as input files

## Monitoring & Observability

**Error Tracking:**
- None - Project is CLI/batch tool, no external error tracking

**Logs:**
- Local file logging to `scripts/logs/` directory
- Log format: Standard Python logging with timestamps
- Log files: `processing_state.json` for batch resumption state

## CI/CD & Deployment

**Hosting:**
- Local execution only (batch processing scripts)
- No cloud deployment - runs on developer workstations and servers with local data

**CI Pipeline:**
- None detected - project uses manual batch runs via `batch_run_all_datasets.sh`

## Environment Configuration

**Required env vars:**
- None - Project operates without environment variables
- All paths are hardcoded relative to script location or configured via CLI args

**Secrets location:**
- No secrets - Project contains no API keys, credentials, or sensitive configuration
- All data is reference material (supplement information, clinical data, FDA resources)

## Data Sources

**Reference Data Files (JSON format):**
- `ingredient_quality_map.json` (1.7 MB) - Main ingredient quality scoring database
- `harmful_additives.json` (602 KB) - Banned/unsafe additives and toxicity levels
- `banned_recalled_ingredients.json` (510 KB) - FDA banned and recalled substances
- `botanical_ingredients.json` (247 KB) - Botanical ingredient standardization and forms
- `standardized_botanicals.json` (161 KB) - Botanical name normalization
- `other_ingredients.json` (481 KB) - FDA "Other Ingredients" (non-active, non-harmful)
- `rda_optimal_uls.json` (203 KB) - Nutrient RDA and upper limit thresholds
- `synergy_cluster.json` (74 KB) - Ingredient interaction patterns
- `proprietary_blends.json` (18 KB) - Proprietary blend detection patterns
- `functional_ingredient_groupings.json` (6 KB) - Functional category mappings
- `clinically_relevant_strains.json` (25 KB) - Probiotic strain clinical data
- `backed_clinical_studies.json` (212 KB) - Clinical evidence database
- `allergens.json` (19 KB) - Common allergen definitions
- `absorption_enhancers.json` (17 KB) - Bioavailability enhancer catalog
- `color_indicators.json` (5 KB) - Natural vs. artificial color classification
- `ingredient_interaction_rules.json` (41 KB) - Drug-supplement interaction rules
- `manufacturer_violations.json` (129 KB) - Manufacturer compliance history
- `unit_conversions.json` - Nutrient-specific unit conversion tables
- `ingredient_classification.json` (3 KB) - Hierarchical source/summary/component classification

**Input Data:**
- User-provided supplement product data from `~/Documents/DataSetDsld/` (directory structure organized by brand/manufacturer)
- Format: JSON files with supplement product details (ingredients, dosages, claims)

## Webhooks & Callbacks

**Incoming:**
- None - Project is batch processing only, no incoming webhook support

**Outgoing:**
- None - Project generates no outbound webhooks or API calls

## Data Flow

**Pipeline Stages (Sequential):**

1. **CLEAN** (`scripts/clean_dsld_data.py`)
   - Reads: Raw supplement product JSON from user input directory
   - Process: Normalizes ingredient names, validates structure, removes junk data
   - Outputs: `scripts/output_*/cleaned/` JSON files

2. **ENRICH** (`scripts/enrich_supplements_v3.py`)
   - Reads: Cleaned JSON + all reference databases in `scripts/data/`
   - Process: Maps ingredients to quality tiers, detects forms, identifies interactions
   - Outputs: `scripts/output_*/enriched/` JSON files with metadata

3. **SCORE** (`scripts/score_supplements.py`)
   - Reads: Enriched JSON + clinical reference data
   - Process: Calculates supplement quality scores based on form, dosage, interactions
   - Outputs: `scripts/output_*/scored/` JSON files with final scores

**Orchestration:**
- Entry point: `scripts/run_pipeline.py` - Runs all three stages sequentially
- Batch runner: `batch_run_all_datasets.sh` - Processes multiple dataset directories, creates separate output folders
- State tracking: `processing_state.json` enables resume capability for interrupted batches

---

*Integration audit: 2026-03-16*
