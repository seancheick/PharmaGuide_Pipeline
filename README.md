<p align="center">
  <img src="https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Tests-3906+-4CAF50?style=for-the-badge&logo=pytest&logoColor=white" />
  <img src="https://img.shields.io/badge/Scoring-v3.4-FF6B35?style=for-the-badge" />
  <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" />
</p>

# PharmaGuide Pipeline

**The evidence-based supplement intelligence engine.**

A production-grade data pipeline that transforms raw NIH Dietary Supplement Label Database (DSLD) records into clinically-scored, safety-verified supplement profiles. Built to power the [PharmaGuide](https://github.com/seancheick) mobile app -- helping consumers make informed decisions about dietary supplements with the same rigor applied to pharmaceuticals.

---

## Why This Exists

The dietary supplement market is a **$60B industry** with minimal consumer transparency. Labels don't tell you if a form is bioavailable, if an ingredient has been recalled by the FDA, or if clinical evidence actually supports the claimed benefits. PharmaGuide Pipeline bridges that gap by scoring every product against 39 curated reference databases, real clinical evidence, and active FDA safety data.

---

## Architecture

```
                    NIH DSLD
                       |
                       v
            +--------------------+
            |   Stage 1: CLEAN   |   Normalize, deduplicate, standardize
            +--------------------+
                       |
                       v
            +--------------------+
            |  Stage 2: ENRICH   |   Match ingredients, classify, resolve identifiers
            +--------------------+   (UMLS CUI, PubChem CID, FDA UNII, RxNorm)
                       |
                       v
            +--------------------+
            |   Stage 3: SCORE   |   80-point arithmetic model, safety gates
            +--------------------+
                       |
                       v
            +--------------------+
            |   Final DB Build   |   Flutter-ready export + Supabase sync
            +--------------------+
                       |
                  +----+----+
                  |         |
                  v         v
              SQLite    Supabase
              (local)   (cloud)
```

Each stage is independently testable, resumable, and produces a well-defined output contract.

---

## Scoring System (v3.4)

An 80-point arithmetic model with deterministic, auditable scoring:

| Section | Max Points | What It Measures |
|---------|-----------|------------------|
| **Ingredient Quality** | 25 | Bioavailability, premium forms, delivery systems, absorption enhancers |
| **Safety & Purity** | 30 | Banned/recalled gates, contaminant penalties, allergens, dose safety |
| **Evidence & Research** | 20 | PMID-backed clinical studies, strength of evidence classification |
| **Brand Trust** | 5 | Manufacturer violations, FDA warning letters, certifications |

**Final Score:** `(raw_80 / 80) * 100` displayed as a 0-100 scale

**Verdicts** (deterministic precedence):
`BLOCKED` > `UNSAFE` > `NOT_SCORED` > `CAUTION` > `POOR` > `SAFE`

A product with a banned substance is **always** BLOCKED -- no amount of quality points overrides safety.

---

## Reference Databases

39 curated JSON databases power the scoring engine:

| Database | Entries | Purpose |
|----------|---------|---------|
| `ingredient_quality_map.json` | 588 | Quality scoring for bioavailable forms, premium ingredients |
| `backed_clinical_studies.json` | 197 | PMID-backed clinical evidence with endpoint classifications |
| `banned_recalled_ingredients.json` | 143 | FDA-sourced regulatory disqualifications |
| `harmful_additives.json` | 115 | Penalty scoring for harmful additives and excipients |
| `caers_adverse_event_signals.json` | -- | FDA CAERS pharmacovigilance signals (B8 penalty scoring) |
| `fda_unii_cache.json` | 172K | Offline FDA UNII substance registry for identity resolution |
| `rda_optimal_uls.json` | 47 | RDA/AI/UL dosing adequacy benchmarks |
| `allergens.json` | 17 | Big 8 allergen classification |
| `synergy_cluster.json` | 58 | Ingredient combination bonus scoring |
| `manufacturer_violations.json` | -- | Brand trust penalties from FDA warning letters |

All files follow a strict schema contract (`v5.0/5.1/5.2/5.3`) with `_metadata` blocks for versioning and audit trails.

---

## Quick Start

### Prerequisites

- Python 3.13+
- API keys (optional, for enrichment verification): UMLS, openFDA, PubMed

### Install

```bash
git clone https://github.com/seancheick/PharmaGuide_Pipeline.git
cd PharmaGuide_Pipeline
pip install -r requirements-dev.txt
```

### Run the Pipeline

```bash
# Full pipeline (Clean -> Enrich -> Score)
python3 scripts/run_pipeline.py <dataset_dir>

# Individual stages
python3 scripts/clean_dsld_data.py <input> <output>
python3 scripts/enrich_supplements_v3.py <cleaned_input> <output>
python3 scripts/score_supplements.py <enriched_input> <output>

# Build Flutter-ready export
python3 scripts/build_final_db.py <scored_input> <output>

# Sync to Supabase
python3 scripts/sync_to_supabase.py <build_output_dir>
```

### Run Tests

```bash
# All 3906+ tests
python3 -m pytest scripts/tests/

# Specific module
python3 -m pytest scripts/tests/test_score_supplements.py -v

# By keyword
python3 -m pytest scripts/tests/ -k "banned"
```

---

## Project Structure

```
scripts/
  run_pipeline.py              # Orchestrator: Clean -> Enrich -> Score
  clean_dsld_data.py           # Stage 1: normalize raw DSLD JSON
  enrich_supplements_v3.py     # Stage 2: ingredient matching & enrichment (12K lines)
  score_supplements.py         # Stage 3: arithmetic scoring engine (3.3K lines)
  enhanced_normalizer.py       # Core NLP normalization engine (6K lines)
  build_final_db.py            # Flutter-ready export builder
  sync_to_supabase.py          # Cloud sync with upsert logic
  batch_processor.py           # Resumable batch processing
  constants.py                 # Shared constants and mappings
  coverage_gate.py             # Quality threshold enforcement
  db_integrity_sanity_check.py # Schema and data validation
  backfill_upc.py              # UPC backfilling for existing products
  extract_product_images.py    # Product image extraction and upload
  build_interaction_db.py      # Interaction rules DB assembly
  unii_cache.py                # FDA UNII offline cache management
  shadow_score_comparison.py   # Shadow scoring comparison tool
  regression_snapshot.py       # Scoring regression snapshots
  preflight.py                 # Pre-pipeline validation checks
  unmapped_ingredient_tracker.py # Unmapped ingredient diagnostics
  config/
    cleaning_config.json       # Stage 1 configuration
    enrichment_config.json     # Stage 2 configuration
    scoring_config.json        # Stage 3 configuration (100+ tunable params)
  data/                        # 39 reference JSON databases
    curated_overrides/         # Manual CUI/PubChem/GSRS policy overrides
  api_audit/                   # External API verification tools
    verify_cui.py              # UMLS CUI verification
    verify_pubchem.py          # PubChem CID + CAS verification
    verify_unii.py             # FDA UNII and CFR verification
    verify_rda_uls.py          # RDA/UL verification against DRI tables
    verify_clinical_trials.py  # ClinicalTrials.gov NCT verification
    fda_weekly_sync.py         # FDA recall tracking (openFDA, RSS, DEA)
  tests/                       # 81 test files, 3906+ test functions
  logs/                        # Runtime logs
  reports/                     # Generated audit reports
docs/                          # Technical documentation
```

---

## API Audit Suite

Every data claim is verifiable against authoritative sources:

| Tool | External API | What It Verifies |
|------|-------------|-----------------|
| `verify_cui.py` | UMLS | Concept Unique Identifiers for ingredients |
| `verify_pubchem.py` | PubChem | Chemical identifiers (CID, CAS numbers) |
| `verify_unii.py` | FDA GSRS | Unique Ingredient Identifiers, CFR references |
| `verify_rda_uls.py` | USDA FoodData Central | RDA/AI/UL dosing benchmarks |
| `verify_clinical_trials.py` | ClinicalTrials.gov | NCT trial identifiers |
| `fda_weekly_sync.py` | openFDA + RSS + DEA | Active recalls, warning letters, scheduling |
| `enrich_chembl_bioactivity.py` | ChEMBL | Mechanism of action enrichment |
| `verify_efsa.py` | EFSA | EU regulatory ADI/opinion validation |

---

## Key Design Decisions

- **Arithmetic scoring only** -- no ML black boxes. Every point is traceable to a config value and a data source.
- **Safety gates are absolute** -- a banned substance blocks the product regardless of its quality score.
- **Offline-first architecture** -- the Flutter app loads from local SQLite cache, hydrates from Supabase on cache miss.
- **Schema-versioned data** -- every JSON file carries `_metadata` with `schema_version`, `last_updated`, and `total_entries`.
- **No bulk enrichment** -- each API-sourced enrichment is verified case-by-case before writing. Plant/compound collapses and preparation mismatches are caught at the individual level.

---

## Dependencies

```
requests>=2.32,<3    # HTTP client for all API calls
rapidfuzz>=3.9,<4    # Fuzzy string matching for ingredient resolution
pytest>=9,<10        # Test framework
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [`SCORING_ENGINE_SPEC.md`](scripts/SCORING_ENGINE_SPEC.md) | Complete scoring formulas and section logic |
| [`PIPELINE_ARCHITECTURE.md`](scripts/PIPELINE_ARCHITECTURE.md) | 3-stage pipeline design and contracts |
| [`FINAL_EXPORT_SCHEMA_V1.md`](scripts/FINAL_EXPORT_SCHEMA_V1.md) | Flutter MVP data contract |
| [`DATABASE_SCHEMA.md`](scripts/DATABASE_SCHEMA.md) | Master schema reference for all data files |
| [`SCORING_README.md`](scripts/SCORING_README.md) | Implementation guide for the scoring engine |

---

## License

[MIT](LICENSE)

---

<p align="center">
  <sub>Built with clinical rigor by <a href="https://github.com/seancheick">Sean Cheick</a></sub>
</p>
