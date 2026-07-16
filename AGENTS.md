# PharmaGuide — Data Pipeline & Scoring Engine

## Project Overview

PharmaGuide is a 3-stage data pipeline (Clean → Enrich → Score) that processes dietary supplement products from the NIH DSLD database into evidence-based quality scores. The scored output feeds a Flutter mobile app for consumers.

**Repo:** github.com/seancheick/dsld_clean
**Language:** Python 3.13
**Test framework:** pytest 9

## ⚠️ Running tests — use `scripts/test.sh`, never raw `pytest`

The dev loop is **`scripts/test.sh fast`** (~3–5 min). The runner pins the
project interpreter (pyenv **3.13.3**; macOS/Xcode `python3` is 3.9 and wrong)
and skips the ~15 heavy real-catalog / V4-canary tests. Running
`python3 -m pytest scripts/tests/` directly uses the wrong interpreter **and**
runs every heavy test (one alone is ~8 min) — that is why ad-hoc runs balloon to
~1 hour.

```bash
scripts/test.sh fast            # dev loop — ~3–5 min (DEFAULT; use this)
scripts/test.sh fast -k banned  # filter by keyword
scripts/test.sh fast scripts/tests/test_v4_scored_artifact.py  # one file
scripts/test.sh release         # release gates before a ship / commit
scripts/test.sh full            # entire suite, parallel (-n auto) — pre-ship / CI
scripts/test.sh slow            # only the heavy integration tests
```

The ~15 catalog/release tests are **release gates**, not dev-loop tests — run
them via `release`/`full` before a ship, not while iterating. (conftest.py prints
a reminder if pytest is launched without the runner.)

## Commands

```bash
# Tests — ALWAYS via the runner (see "Running tests" above), NEVER raw pytest.
scripts/test.sh fast                 # dev loop (~3-5 min, pinned Python 3.13)
scripts/test.sh fast -k banned       # filter by keyword
scripts/test.sh full                 # full suite (pre-ship / CI)

# Canonical operational runs
bash batch_run_all_datasets.sh
bash batch_run_all_datasets.sh --targets Brand --stages enrich,score
bash batch_run_all_datasets.sh --root "$HOME/Documents/DataSetDsld/staging/brands"

# Rebuild dashboard/catalog snapshot from existing brand outputs
bash scripts/rebuild_dashboard_snapshot.sh

# Release-stage work: catalog staging, product images, interaction DB, Supabase, Flutter bundle
bash scripts/release_full.sh

# Single-brand/stage runner for local iteration only
python3 scripts/run_pipeline.py --raw-dir <dataset_dir> --output-prefix scripts/products/output_<brand>

# Run individual pipeline stages
python3 scripts/clean_dsld_data.py <input> <output>
python3 scripts/enrich_supplements_v3.py <cleaned_input> <output>
python3 scripts/score_products_v4.py --input-dir <enriched_dir> --output-dir <scored_dir>

# Manual/internal final DB export; normal shipping goes through rebuild_dashboard_snapshot.sh + release_full.sh
python3 scripts/build_final_db.py --enriched-dir <enriched_dir> --scored-dir <scored_dir> --output-dir <output>

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
  tests/                      # 580 test files, 5100+ tests (incl. parametrized)
  logs/                       # Runtime logs
  reports/                    # Generated audit reports
docs/                         # Technical deep-dives and infographics
.Codex/skills/fda-weekly-sync/  # Codex skill for FDA regulatory sync
```

## Key Scripts

| Script                         | Role                                                        |
| ------------------------------ | ----------------------------------------------------------- |
| `batch_run_all_datasets.sh`    | Main full-corpus / targeted operational runner               |
| `scripts/rebuild_dashboard_snapshot.sh` | Rebuilds final DB/dashboard snapshot from brand outputs |
| `scripts/release_full.sh`      | Release-stage owner: catalog, images, interaction DB, Supabase, Flutter |
| `run_pipeline.py`              | Single-brand/stage Clean → Enrich → Score runner             |
| `clean_dsld_data.py`           | Stage 1: normalize raw DSLD JSON                            |
| `enrich_supplements_v3.py`     | Stage 2: match ingredients, classify, enrich (~13K lines)   |
| `score_products_v4.py`         | Stage 3: v4 artifact batch I/O and atomic writes            |
| `scoring_v4/scored_artifact.py` | Single scored-artifact assembly and verdict/coverage contract |
| `enhanced_normalizer.py`       | Core text normalization engine (~7K lines)                  |
| `build_final_db.py`            | Internal/manual final DB builder used by snapshot/release flows |
| `audit_source_of_truth_contract.py` | Cleaner-first source-of-truth and strict release gates  |
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

## Production Scoring System (v4)

The shipped catalog score is the v4 six-pillar /100 model emitted through
`scripts/score_products_v4.py` and
`scripts/scoring_v4/scored_artifact.py`. Final DB export consumes that artifact
directly and never runs a second scorer.

- **Formulation** (20): ingredient form quality, delivery, formulation fit
- **Dose** (20): category-aware dosing adequacy and excess-dose handling
- **Evidence** (20): verified clinical support and category fit
- **Transparency** (15): disclosure, proprietary blend opacity, label completeness
- **Verification** (15): verified third-party testing, COA, GMP/certification signals
- **Safety/Hygiene** (10): product-level safety hygiene and clean-label penalties

Canonical exported fields:

- `quality_score_v4_100` — shipped /100 score
- `quality_score_status` — `scored`, `suppressed_safety`, or `not_scored`
- `quality_pillars_v4` — six-pillar detail surface for Flutter
- `score_100_equivalent` and `score_display_100_equivalent` — compatibility mirrors of the v4 score

`score_supplements.py` is retired from every operational entrypoint. It may
remain temporarily only for Phase-5 test disposition after the v4 corpus
rebuild; do not invoke it, restore it as fallback, or build compatibility
logic around it. Do not reintroduce `score_quality_80` or `score_display_80`.

Verdicts: BLOCKED > UNSAFE > NOT_SCORED > CAUTION > POOR > SAFE (deterministic precedence)

Config: `scripts/scoring_v4/config/quality_score.json` is the sole production
scoring configuration.

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
- **Score field naming is FROZEN:** use `quality_score_v4_100`, `quality_score_status`, and `quality_pillars_v4`; do not reintroduce `score_quality_80` or `score_display_80`
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
- **Deep modules over shallow ones.** Prefer few large modules with simple interfaces (Ousterhout). When working on the mega-files (`enrich_supplements_v3.py` 13K, `enhanced_normalizer.py` 7K): treat them as gray boxes — design and lock the interface, verify at the boundary with tests.
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
