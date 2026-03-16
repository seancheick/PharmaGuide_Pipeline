# STRUCTURE.md — Directory Layout & Key Locations

## Root Layout

```
peaceful-ritchie/                    # git worktree root
├── scripts/                         # ALL pipeline code lives here
│   ├── data/                        # Ingredient reference DBs (JSON)
│   ├── tests/                       # All test files (pytest)
│   ├── config/                      # Pipeline config JSON
│   ├── logs/                        # Runtime logs
│   ├── archive/                     # Archived audit/analysis scripts
│   ├── output_<dataset>/            # Cleaned output batches per dataset
│   ├── output_<dataset>_enriched/   # Enriched output per dataset
│   ├── output_<dataset>_scored/     # Scored output per dataset
│   └── *.py / *.md                  # Pipeline scripts + documentation
├── docs/
│   └── plans/                       # SOP and planning docs
├── .planning/
│   └── codebase/                    # GSD codebase map (this directory)
└── UNMAPPED_RESOLUTION_PROMPT.md    # Active SOP for unmapped resolution
```

## `scripts/data/` — Reference Databases

```
data/
├── ingredient_quality_map.json      # IQM: active scorable ingredients (primary routing)
├── other_ingredients.json           # OI: excipients, carriers, inactive (OI_* / NHA_* / PII_*)
├── harmful_additives.json           # HA: harmful additives (ADD_* / BANNED_ADD_*)
├── banned_recalled_ingredients.json # BR: FDA-banned / recalled substances
├── botanical_ingredients.json       # BOT: botanical actives with species data
├── standardized_botanicals.json     # SB: branded multi-botanical extracts
└── ingredient_classification.json   # Classification metadata
```

**DB routing hierarchy (priority order):**
IQM → OI → HA → BR → BOT → SB → proprietary_blends

## `scripts/tests/` — Test Suite (47 files)

### By Domain
| File | Coverage Area |
|------|--------------|
| `test_pipeline_regressions.py` | End-to-end pipeline regression suite |
| `test_clean_unmapped_alias_regressions.py` | Unmapped ingredient alias fixes |
| `test_db_integrity.py` | Cross-DB consistency and schema |
| `test_banned_collision_corpus.py` | IQM ↔ BR collision detection |
| `test_banned_matching.py` | Banned ingredient matching logic |
| `test_blend_merge_pipeline.py` | Proprietary blend handling |
| `test_coverage_gate.py` | Coverage gate pass/fail logic |
| `test_enrichment_regressions.py` | Enrichment stage regressions |
| `test_dosage_golden_fixtures.py` | Dosage calculation golden tests |
| `test_ingredient_quality_map_schema.py` | IQM schema validation |
| `test_harmful_schema_v2.py` | HA DB schema contract |
| `test_banned_schema_v3.py` | BR DB schema contract |
| `test_normalization_stability.py` | Normalizer stability (same input → same output) |
| `test_fuzzy_matching.py` | Fuzzy matcher accuracy |
| `test_unit_conversions.py` | Unit conversion correctness |
| `test_scoring_invariants.py` | Score monotonicity and invariants |
| `test_scorable_classification.py` | Scorable vs. display-only classification |
| `test_cross_db_overlap_guard.py` | No entry exists in two DBs simultaneously |
| `test_allergen_negation.py` | Allergen negation parsing |
| `test_capsule_unmapped_resolution.py` | Capsule dataset unmapped resolution |

**Total:** ~1085+ test cases across 47 files

## `scripts/` — Core Pipeline Scripts

| Script | Role |
|--------|------|
| `enhanced_normalizer.py` | Stage 1 clean: raw DSLD → normalized ingredients |
| `enrich_supplements_v3.py` | Stage 2 enrich: normalized → enriched with clinical data |
| `score_supplements.py` | Stage 3 score: enriched → scored output |
| `batch_processor.py` | Orchestrates batch runs across datasets |
| `run_pipeline.py` | Single-product pipeline runner |
| `unmapped_ingredient_tracker.py` | Tracks and reports unmapped ingredients |
| `fuzzy_matcher.py` | Fuzzy name matching for alias resolution |
| `coverage_gate.py` | Enforces minimum mapping coverage thresholds |
| `dosage_normalizer.py` | Unit normalization and dosage parsing |
| `fda_weekly_sync.py` | Syncs FDA recall/ban data into BR DB |
| `normalization.py` | Text normalization utilities |
| `constants.py` | Shared constants and frozen sets |
| `preflight.py` | Pre-run validation checks |

## `scripts/output_<dataset>/` — Per-Dataset Output

```
output_<dataset>/
├── cleaned_batch_<N>.json           # Cleaned products (batches of ~500)
├── unmapped/
│   ├── unmapped_active_ingredients.json
│   ├── unmapped_inactive_ingredients.json
│   ├── needs_verification_active_ingredients.json
│   └── needs_verification_inactive_ingredients.json
└── batch_run_summary_*.txt          # Run summaries
```

## Active Datasets (as of 2026-03-16)

| Dataset | Labels | Status |
|---------|--------|--------|
| `Softgels-19416labels-8-6-25` | 19,416 | Active (current focus) |
| `Capsules-44920labels-2019-2025-8-6-25` | 44,920 | Active |
| `Gummies-Jellies-4562-labels-11-11-25` | 4,562 | Active |
| `Garden-of-Life-2-17-26-L1132` | 1,132 | Brand audit |
| `Nordic-Naturals-2-17-26-L511` | 511 | Brand audit |
| `Thorne-2-17-26` | ~827 | Brand audit |
| `Pure-Encapsulations-2-17-26-L2123` | 2,123 | Brand audit |

## Naming Conventions

| Pattern | Meaning |
|---------|---------|
| `OI_*` | Other Ingredient entry (neutral excipient) |
| `NHA_*` | Non-Harmful Additive (safe food additive) |
| `PII_*` | Pipeline Inactive Ingredient (carrier/filler) |
| `ADD_*` | Harmful Additive (flagged) |
| `BANNED_ADD_*` | Banned/Recalled substance |
| `STRUCTURAL_ACTIVE_*` | Normalizer frozen set for structural filtering |
| `output_*_enriched` | Post-enrichment output directory |
| `output_*_scored` | Post-scoring output directory |
| `cleaned_batch_<N>.json` | Clean stage output, zero-indexed batch number |
