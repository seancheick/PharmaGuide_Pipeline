# PharmaGuide — Data Pipeline & Scoring Engine

## Project Overview

PharmaGuide is a 3-stage data pipeline (Clean → Enrich → Score) that processes dietary supplement products from the NIH DSLD database into evidence-based quality scores. The scored output feeds a Flutter mobile app for consumers.

**Repo:** github.com/seancheick/dsld_clean
**Language:** Python 3.13
**Test framework:** pytest 9

## Commands

```bash
# Run all tests (5100+ tests, 169 files)
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
  data/                       # 39 reference JSON databases (schema v5.0-5.3, 6.0 for user_goals)
  data/curated_overrides/     # Manual CUI/PubChem/GSRS policy overrides
  tests/                      # 169 test files, 5100+ tests (incl. parametrized)
  logs/                       # Runtime logs
  reports/                    # Generated audit reports
docs/                         # Technical deep-dives and infographics
.Codex/skills/fda-weekly-sync/  # Codex skill for FDA regulatory sync
```

## Key Scripts

| Script                         | Role                                                        |
| ------------------------------ | ----------------------------------------------------------- |
| `run_pipeline.py`              | Orchestrates Clean → Enrich → Score                         |
| `clean_dsld_data.py`           | Stage 1: normalize raw DSLD JSON                            |
| `enrich_supplements_v3.py`     | Stage 2: match ingredients, classify, enrich (~13K lines)   |
| `score_supplements.py`         | Stage 3: arithmetic scoring, verdict assignment (~4K lines) |
| `enhanced_normalizer.py`       | Core text normalization engine (~7K lines)                  |
| `build_final_db.py`            | Final export for Flutter app                                |
| `constants.py`                 | Shared constants and mappings (~1.5K lines)                 |
| `batch_processor.py`           | Batch processing with resume capability                     |
| `db_integrity_sanity_check.py` | Schema and data validation (~1.5K lines)                    |
| `coverage_gate.py`             | Quality/coverage threshold enforcement                      |

## Key Data Files (scripts/data/)

| File                               | Purpose                                                         |
| ---------------------------------- | --------------------------------------------------------------- |
| `ingredient_quality_map.json`      | Quality scoring for 610 IQM parents (largest file)              |
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

## Scoring System (v3.4.0)

80-point arithmetic model with section breakdown:

- **Ingredient Quality** (max 25): bioavailability, premium forms, delivery, absorption
- **Safety & Purity** (max 30): banned/recalled gate, contaminants, allergens, dose safety (B7: 150%+ UL)
- **Evidence & Research** (max 20): clinical backing, strength of evidence
- **Brand Trust** (max 5): manufacturer reputation, certifications
- **Dose Adequacy** (max 2): EPA/DHA dosing for omega-3 (additive)

Final: `score_100_equivalent = (quality_score / 80) * 100`
Verdicts: BLOCKED > UNSAFE > NOT_SCORED > CAUTION > POOR > SAFE (deterministic precedence)

Config: `scripts/config/scoring_config.json` (100+ tunable parameters)

## Key Documentation

| File                                | What it covers                                |
| ----------------------------------- | --------------------------------------------- |
| `scripts/DATABASE_SCHEMA.md`        | Master schema reference for all 39 data files |
| `scripts/SCORING_ENGINE_SPEC.md`    | Detailed scoring formulas and section logic   |
| `scripts/SCORING_README.md`         | Implementation guide for the scorer           |
| `scripts/PIPELINE_ARCHITECTURE.md`  | 4-stage pipeline design and contracts         |
| `scripts/FINAL_EXPORT_SCHEMA_V1.md` | Flutter MVP data contract                     |
| `scripts/api_audit/README.md`       | API audit tooling reference                   |

## Documentation truth priority

When you need to know how the pipeline behaves, consult sources in this
order:

1. **Python source files in `scripts/`** — the code is the truth.
2. **Generated artifacts** in `scripts/final_db_output/` or `/tmp/pharmaguide_release_build*/` — what actually ships.
3. **Tests + audit reports** under `scripts/tests/` and `reports/`.
4. **Schema docs** (`FINAL_EXPORT_SCHEMA_V1.md`, `SCORING_ENGINE_SPEC.md`, etc.) — only after cross-checking against 1–3.

Do NOT use `docs/archive/*`, `docs/superpowers/*`, or top-level historical
bug-fix `.md` as implementation truth. They are conversational history,
not specifications. If in doubt, run
`scripts/audit_contract_sync.py` and `scripts/audit_raw_to_final.py`
against a fresh `build_final_db.py` output to get an objective state
snapshot.

## Active audit + verification scripts

These are the data-integrity gates the pipeline relies on. Run any of
them against `scripts/final_db_output` or a fresh
`/tmp/pharmaguide_release_build*/` to verify the contract.

| Script                                          | What it gates                                                |
| ----------------------------------------------- | ------------------------------------------------------------ |
| `scripts/audit_contract_sync.py`                | v1.5.0/v1.6.x blob-contract field emit rates (GREEN/YELLOW/RED) |
| `scripts/audit_raw_to_final.py`                 | Raw → blob reconciliation; 23 finding codes; canary set       |
| `scripts/audit_inactive_safety.py`              | Banned-in-inactives have safety signal; notes-text FP catcher; unknown-role counter (CI gate) |
| `scripts/db_integrity_sanity_check.py`          | SQLite schema + data validation                              |
| `scripts/coverage_gate.py`                      | Quality / coverage threshold enforcement                     |
| `scripts/coverage_gate_functional_roles.py`     | functional_roles coverage on inactives                       |
| `scripts/enrichment_contract_validator.py`      | Enrichment output contract                                   |
| `scripts/tests/test_inactive_ingredient_resolver.py` | Resolver unit + canary suite (20 tests)                |
| `scripts/tests/test_canonical_id_delivers_markers_emit.py` | Active-side canonical_id + delivers_markers contract |
| `scripts/tests/test_capsimax_display_label_fidelity.py` | Branded botanical display fidelity              |
| `scripts/tests/test_vitamin_a_form_aware_normalization.py` | Vitamin A IU→mcg RAE form detection         |
| `scripts/tests/test_label_fidelity_contract.py` | 8 invariants for blob ↔ label fidelity                       |
| `scripts/tests/test_active_count_reconciliation.py` | E1.2.5 drop-reason enum                                 |

## Conventions

- **Data schema version:** 5.0.0 – 5.3.0 (with 6.0.0 for `user_goals_to_clusters.json`) — every JSON data file has a `_metadata` block
- **Score field naming is FROZEN:** use `score_quality_80`, `score_display_100_equivalent`, NOT "sections A-E" in exports
- **Safety distinction:** `has_banned_substance` / `has_recalled_ingredient` for ingredient-level. Never use `is_recalled` (implies product-level recall, not supported in v1)
- **Tests are mandatory:** every data file change, scoring logic change, or enrichment change must have test coverage
- **No linter configured** — follow existing code style (snake_case, type hints encouraged but not enforced)
- **API keys:** loaded via `scripts/env_loader.py` from `.env` (UMLS, openFDA, PubMed keys)
- **Offline-first architecture:** phone loads from local SQLite cache first, hydrates from Supabase on cache miss

## Engineering Principles

These override speed when they conflict.

- **No hallucinated identifiers — ever.** PMIDs, CUIs, RXCUIs, UNIIs, NCT IDs, CAS, CIDs must be content-verified against the live API (PubMed/UMLS/RxNorm/FDA/ClinicalTrials.gov). Existence is not enough — a real PMID about the wrong topic is a *ghost reference* and is a defect. Use `scripts/api_audit/verify_*.py`. This is a clinical product; one corrupt entry = a red flag for the whole product. See `critical_no_hallucinated_citations` and `critical_clinical_data_integrity` memories.
- **Code is not cheap.** AI velocity is real, but bad code is *more* expensive than ever because AI works best in good codebases. Optimize for maintainability and the next reader, not lines-per-minute. Boring, idiomatic code beats clever code.
- **Small batches, decomposed problems.** Solve one thing at a time. Atomic commits. Localize blast radius. The IQM batch cadence is the right shape — keep it.
- **Deep modules over shallow ones.** Prefer few large modules with simple interfaces (Ousterhout). When working on the mega-files (`enrich_supplements_v3.py` 13K, `score_supplements.py` 4K, `enhanced_normalizer.py` 7K): treat them as gray boxes — design and lock the interface, delegate implementation, verify at the boundary with tests.
- **Watch for cognitive debt and code bloat.** Generating code is nearly free; understanding it isn't. If a change adds volume without removing complexity, push back. If a CLAUDE.md / doc / config grows without being read, slim it.
- **AI is an amplifier, not a fixer.** Discipline doesn't get optional with AI — it gets more important. Specs-to-code without humans reviewing produces entropy.

## Workflow Patterns

### Codebase navigation
- For structural questions (call graphs, cross-file refs, blast radius), check `graphify-out/GRAPH_REPORT.md` and `graphify-out/graph.json` first.
- Fall back to Grep/Read for runtime behavior, recent uncommitted code, or actual data values.
- Re-run `/graphify` after major refactors or once a few IQM batches have shipped (graph drifts).

### Before non-trivial work
- For audits, refactors, or cross-file features: ask clarifying questions until shared understanding before any tool calls or edits. This is upstream of plan mode — better than the eager "create a plan and start" default.
- Reference `scripts/GLOSSARY.md` for IQM/scoring terminology — every term used in code, tests, and conversation should match the glossary. Add new terms to the glossary first.

### IQM audit batches (ongoing pattern)
- **Cache research per-batch** in `scripts/audits/batch_NN/research.md` (verified PMIDs + abstracts) before writing the fix script. Delete or archive when batch ships — research rots.
- **Test-first**: write the failing regression assertion in `scripts/tests/test_<topic>_integrity.py` *before* the fix. Confirm it fails on current data, then apply the fix.
- **Atomic commit per batch** with summary in commit message (parents corrected, ghost references found, framework errors caught).
- Memory entries (`feedback_*`, `project_*`) capture *why* and *what surprised us*, not just what was done.

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
