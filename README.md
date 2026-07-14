<p align="center">
  <img src="https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Tests-5100+-4CAF50?style=for-the-badge&logo=pytest&logoColor=white" />
  <img src="https://img.shields.io/badge/Scoring-v4-FF6B35?style=for-the-badge" />
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
            |   Stage 3: SCORE   |   Legacy score scaffolding + safety gates
            +--------------------+
                       |
                       v
            +--------------------+
            |   Final DB Build   |   V4 six-pillar export + Supabase sync
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

## Scoring System (v4)

The production catalog score is a deterministic six-pillar /100 model. Every
point is traceable to pipeline data, verified references, or explicit fail-open
unknown-data policy.

| Pillar | Max Points | What It Measures |
|--------|-----------:|------------------|
| **Formulation** | 20 | Ingredient form quality, delivery, formulation fit |
| **Dose** | 20 | Category-aware dose adequacy and excess-dose handling |
| **Evidence** | 20 | Verified clinical support and category fit |
| **Transparency** | 15 | Label disclosure, proprietary blend opacity, completeness |
| **Verification** | 15 | Verified third-party testing, COA, GMP/certification signals |
| **Safety/Hygiene** | 10 | Product-level safety hygiene and clean-label penalties |

**Canonical shipped score:** `quality_score_v4_100`

**Status:** `quality_score_status` is `scored`, `suppressed_safety`, or `not_scored`.
Safety-suppressed products may keep audit scores internally, but Flutter must not
display those audit numbers as product quality.

**Verdicts** (deterministic precedence):
`BLOCKED` > `UNSAFE` > `NOT_SCORED` > `CAUTION` > `POOR` > `SAFE`

A product with a banned substance is **always** BLOCKED -- no amount of quality points overrides safety.

The legacy /80 scorer still runs for review queues, detail-blob scaffolding, and
audit compatibility. It is not the shipped score contract; final exports do not
contain `score_quality_80` or `score_display_80`.

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
# Full-corpus or targeted operational run (Clean -> Enrich -> Score -> snapshot -> release)
bash batch_run_all_datasets.sh
bash batch_run_all_datasets.sh --targets Garden,Doctors --stages enrich,score
bash batch_run_all_datasets.sh --root "$HOME/Documents/DataSetDsld/staging/brands"

# Rebuild the catalog/dashboard snapshot from existing brand outputs
bash scripts/rebuild_dashboard_snapshot.sh

# Release-stage work: catalog staging, product images, interaction DB, Supabase, Flutter bundle
bash scripts/release_full.sh

# Single-brand/stage iteration only
python3 scripts/run_pipeline.py --raw-dir <dataset_dir> --output-prefix scripts/products/output_<brand> --stages clean,enrich,score

# Individual stages
python3 scripts/clean_dsld_data.py <input> <output>
python3 scripts/enrich_supplements_v3.py <cleaned_input> <output>
python3 scripts/score_supplements.py <enriched_input> <output>

# Manual/internal export tools; normal shipping goes through rebuild_dashboard_snapshot.sh + release_full.sh
python3 scripts/build_final_db.py --enriched-dir <enriched_dir> --scored-dir <scored_dir> --output-dir <output_dir>
python3 scripts/sync_to_supabase.py scripts/dist --dry-run
```

### Run Tests

```bash
# All 5100+ tests
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
  run_pipeline.py              # Single-brand/stage runner: Clean -> Enrich -> Score
  audit_source_of_truth_contract.py # Strict source-of-truth and release gates
  contracts/source_of_truth_matrix.json # Owner map for clinical/data concepts
  clean_dsld_data.py           # Stage 1: normalize raw DSLD JSON
  enrich_supplements_v3.py     # Stage 2: ingredient matching & enrichment (12K lines)
  score_supplements.py         # Stage 3: legacy arithmetic scaffolding + safety gates
  scoring_v4/                  # Production six-pillar /100 scoring model
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
  shadow_score_comparison.py   # Historical comparison tool; v4 is now production
  tests/test_scoring_snapshot_v1.py # Authoritative frozen-product regression gate
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
  tests/                       # 580 test files, 5100+ tests
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
