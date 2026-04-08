# PharmaGuide — Data Pipeline & Scoring Engine

## Project Overview

PharmaGuide is a 3-stage data pipeline (Clean → Enrich → Score) that processes dietary supplement products from the NIH DSLD database into evidence-based quality scores. The scored output feeds a Flutter mobile app for consumers.

**Repo:** github.com/seancheick/dsld_clean
**Language:** Python 3.13
**Test framework:** pytest 9

## Commands

```bash
# Run all tests (3065+ tests, ~81 files)
python3 -m pytest scripts/tests/

# Run a single test file
python3 -m pytest scripts/tests/test_score_supplements.py -v

# Run tests matching a keyword
python3 -m pytest scripts/tests/ -k "banned"

# Run the full pipeline on a dataset folder
python3 scripts/run_pipeline.py <dataset_dir>

# Run individual pipeline stages
python3 scripts/clean_dsld_data.py <input> <output>
python3 scripts/enrich_supplements_v3.py <cleaned_input> <output>
python3 scripts/score_supplements.py <enriched_input> <output>

# Build final DB export for Flutter
python3 scripts/build_final_db.py <scored_input> <output>

# Sync pipeline output to Supabase
python3 scripts/sync_to_supabase.py <build_output_dir>

# Dry run (preview without uploading)
python3 scripts/sync_to_supabase.py <build_output_dir> --dry-run

# FDA weekly sync (regulatory recall updates)
bash scripts/run_fda_sync.sh

# Data integrity check
python3 scripts/db_integrity_sanity_check.py

# Enrichment contract validation
python3 scripts/enrichment_contract_validator.py <enriched_file>

# Coverage gate (quality thresholds)
python3 scripts/coverage_gate.py <scored_file>
```

## Project Structure

```
scripts/
  *.py                        # Core pipeline scripts (~30 files)
  api_audit/                  # External API verification tools (UMLS, FDA, PubMed, ChEMBL, EFSA)
  config/                     # cleaning_config.json, enrichment_config.json, scoring_config.json
  data/                       # 34 reference JSON databases (schema v5.0/5.1)
  data/curated_overrides/     # Manual CUI/PubChem/GSRS policy overrides
  tests/                      # 81 test files, 3065+ test functions
  logs/                       # Runtime logs
  reports/                    # Generated audit reports
docs/                         # Technical deep-dives and infographics
.claude/skills/fda-weekly-sync/  # Claude Code skill for FDA regulatory sync
```

## Key Scripts

| Script                         | Role                                                        |
| ------------------------------ | ----------------------------------------------------------- |
| `run_pipeline.py`              | Orchestrates Clean → Enrich → Score                         |
| `clean_dsld_data.py`           | Stage 1: normalize raw DSLD JSON                            |
| `enrich_supplements_v3.py`     | Stage 2: match ingredients, classify, enrich (~12K lines)   |
| `score_supplements.py`         | Stage 3: arithmetic scoring, verdict assignment (~3K lines) |
| `enhanced_normalizer.py`       | Core text normalization engine (~6K lines)                  |
| `build_final_db.py`            | Final export for Flutter app                                |
| `constants.py`                 | Shared constants and mappings (~1.5K lines)                 |
| `batch_processor.py`           | Batch processing with resume capability                     |
| `db_integrity_sanity_check.py` | Schema and data validation (~1.5K lines)                    |
| `coverage_gate.py`             | Quality/coverage threshold enforcement                      |

## Key Data Files (scripts/data/)

| File                               | Purpose                                                         |
| ---------------------------------- | --------------------------------------------------------------- |
| `ingredient_quality_map.json`      | Quality scoring for 563 IQM parents (largest file)              |
| `banned_recalled_ingredients.json` | Regulatory safety disqualifications or penalties (143 entries)  |
| `harmful_additives.json`           | Penalty scoring for harmful additives (115 entries)             |
| `backed_clinical_studies.json`     | Clinical evidence bonus points (197 entries, all PMID-backed)    |
| `allergens.json`                   | Allergen classification (Big 8 types)                           |
| `rda_optimal_uls.json`             | Dosing adequacy benchmarks                                      |
| `manufacturer_violations.json`     | Brand trust penalties                                           |
| `synergy_cluster.json`             | Ingredient synergy bonuses                                      |

All data files use the `_metadata` contract with `schema_version`, `last_updated`, `total_entries`.

## API Audit Tools (scripts/api_audit/)

Verification scripts that call external APIs to validate data accuracy:

- `verify_cui.py` — UMLS CUI verification
- `verify_pubchem.py` — PubChem CID + CAS verification
- `verify_unii.py` — FDA UNII and CFR verification
- `verify_rda_uls.py` — RDA/AI/UL verification against National Academies DRI tables + USDA FoodData Central API
- `verify_efsa.py` — EU regulatory ADI/opinion validation
- `verify_clinical_trials.py` — ClinicalTrials.gov NCT ID verification
- `fda_weekly_sync.py` — FDA recall tracking (openFDA, RSS, DEA)
- `enrich_chembl_bioactivity.py` — ChEMBL mechanism of action enrichment
- `audit_banned_recalled_accuracy.py` — Release gate for banned/recalled data
- `audit_clinical_evidence_strength.py` — Evidence strength classification

## Scoring System (v3.2.0)

80-point arithmetic model with section breakdown:

- **Ingredient Quality** (max 25): bioavailability, premium forms, delivery, absorption
- **Safety & Purity** (max 30): banned/recalled gate, contaminants, allergens, dose safety (B7: 150%+ UL)
- **Evidence & Research** (max 20): clinical backing, strength of evidence
- **Brand Trust** (max 5): manufacturer reputation, certifications
- **Dose Adequacy** (max 2): EPA/DHA dosing for omega-3 (additive)

Final: `score_100_equivalent = (quality_score / 80) * 100`
Verdicts: BLOCKED > UNSAFE > MODERATE > REVIEW > RECOMMENDED (deterministic precedence)

Config: `scripts/config/scoring_config.json` (100+ tunable parameters)

## Key Documentation

| File                                | What it covers                                |
| ----------------------------------- | --------------------------------------------- |
| `scripts/DATABASE_SCHEMA.md`        | Master schema reference for all 34 data files |
| `scripts/SCORING_ENGINE_SPEC.md`    | Detailed scoring formulas and section logic   |
| `scripts/SCORING_README.md`         | Implementation guide for the scorer           |
| `scripts/PIPELINE_ARCHITECTURE.md`  | 3-stage pipeline design and contracts         |
| `scripts/FINAL_EXPORT_SCHEMA_V1.md` | Flutter MVP data contract                     |
| `scripts/api_audit/README.md`       | API audit tooling reference                   |

## Conventions

- **Data schema version:** 5.0.0 / 5.1.0 — every JSON data file has `_metadata` block
- **Score field naming is FROZEN:** use `score_quality_80`, `score_display_100_equivalent`, NOT "sections A-E" in exports
- **Safety distinction:** `has_banned_substance` / `has_recalled_ingredient` for ingredient-level. Never use `is_recalled` (implies product-level recall, not supported in v1)
- **Tests are mandatory:** every data file change, scoring logic change, or enrichment change must have test coverage
- **No linter configured** — follow existing code style (snake_case, type hints encouraged but not enforced)
- **API keys:** loaded via `scripts/env_loader.py` from `.env` (UMLS, openFDA, PubMed keys)
- **Offline-first architecture:** phone loads from local SQLite cache first, hydrates from Supabase on cache miss

## Dependencies

```
requests>=2.32,<3    # HTTP client for all API calls
rapidfuzz>=3.9,<4    # Fuzzy string matching for ingredient resolution
pytest>=9,<10        # Test framework
```

Install: `pip install -r requirements-dev.txt`

---

# gstack

Use the `/browse` skill from gstack for all web browsing. Never use `mcp__claude-in-chrome__*` tools.

## Available gstack skills

- `/office-hours` — YC-style startup diagnostic and builder brainstorm
- `/plan-ceo-review` — CEO-level strategy review
- `/plan-eng-review` — Engineering architecture review
- `/plan-design-review` — Design audit (report only)
- `/design-consultation` — Design system from scratch
- `/review` — PR code review
- `/ship` — Create PR, run review, prepare for merge
- `/land-and-deploy` — Merge, deploy, canary verify
- `/canary` — Post-deploy monitoring loop
- `/benchmark` — Performance regression detection
- `/browse` — Headless browser for QA, dogfooding, site testing
- `/qa` — QA testing with fixes
- `/qa-only` — QA testing (report only, no fixes)
- `/design-review` — Visual design audit with fix loop
- `/setup-browser-cookies` — One-time browser cookie config
- `/setup-deploy` — One-time deploy config
- `/retro` — Retrospective
- `/investigate` — Systematic root-cause debugging
- `/document-release` — Post-ship documentation updates
- `/codex` — Multi-AI second opinion via OpenAI Codex CLI
- `/cso` — OWASP Top 10 + STRIDE security audit
- `/autoplan` — Auto-review pipeline (CEO, design, eng)
- `/careful` — Production safety mode
- `/freeze` — Scoped edit restrictions
- `/guard` — Production guard rails
- `/unfreeze` — Remove edit restrictions
- `/gstack-upgrade` — Upgrade gstack to latest
