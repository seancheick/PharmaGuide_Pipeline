# PIPELINE_ARCHITECTURE.md

> Last updated: 2026-05-12 | Export schema: v1.6.0 (91 columns). Runtime source of truth: `EXPORT_SCHEMA_VERSION` and `CORE_COLUMN_COUNT` in `build_final_db.py`.

## Overview

PharmaGuide runs a 4-stage pipeline (3 compute stages + 1 export stage):

1. `clean_dsld_data.py` (Clean)
2. `enrich_supplements_v3.py` (Enrich)
3. `score_supplements.py` (Score)
4. `build_final_db.py` (Build Final DB) → `sync_to_supabase.py` (ship)

Orchestration is handled by `run_pipeline.py` for stages 1–3, and by `build_all_final_dbs.py` / `assemble_final_db_release.py` for stage 4.

```text
raw_data/*.json
  -> [CLEAN] clean_dsld_data.py  (uses enhanced_normalizer.py)
output_*/cleaned/*.json
  -> [ENRICH] enrich_supplements_v3.py
output_*_enriched/enriched/*.json
  -> [COVERAGE GATE] coverage_gate.py (optional, can block scoring)
  -> [SCORE] score_supplements.py
output_*_scored/scored/*.json
  -> [BUILD FINAL DB] build_final_db.py
final_db_output/
  ├── pharmaguide_core.db        (SQLite, 91-col products_core)
  ├── detail_blobs/*.json        (per-product JSON blobs)
  ├── detail_index.json
  ├── export_manifest.json       (schema_version="1.6.0")
  └── export_audit_report.json
  -> [SUPABASE SYNC] sync_to_supabase.py
Supabase Storage: pharmaguide/v{version}/pharmaguide_core.db
                  pharmaguide/shared/details/sha256/{hash}.json
Supabase Postgres: export_manifest row inserted via rotate_manifest RPC
  -> [FLUTTER APP] downloads SQLite + queries locally via Drift
```

### Silent-failure audit principle (2026-04 → 2026-05)

Every field must flow across all 5 stage boundaries (Raw → Clean → Enrich → Score → Final DB → Flutter) without being silently dropped. If a stage computes a signal that a downstream stage ignores, users see a mismatch between warnings and scores. A field-level cross-reference audit in 2026-04 identified and fixed 18 such drops (including the original probiotic `clinical_strain_count` bug, the `serving_info` phantom key in `build_final_db.py`, and the amount-based sugar scoring gap). The 8-phase Identity-vs-Bioactivity split (2026-05) extended this principle to alias-routing: source botanicals (kelp, marigold, citrus extract, broccoli sprout) now route to `botanical_ingredients.json` rather than IQM marker entries, with bioactive contributions surfaced through `botanical_marker_contributions.json` and emitted at blob level as `canonical_id` + `delivers_markers`. See `reports/identity_vs_bioactivity_impact_report.md` for the migration record and `FINAL_EXPORT_SCHEMA_V1.md` for the per-column contract.

## Stage Responsibilities

### Stage 1: Clean

Primary script: `clean_dsld_data.py`  
Core normalization module: `enhanced_normalizer.py`

What it does:
- Normalizes raw DSLD fields into stable canonical structure.
- Parses ingredient records and standardizes ingredient text.
- Produces cleaned product files that become the only input for enrichment.

What it must not do:
- No final section scoring arithmetic.
- No final verdict assignment.

### Stage 2: Enrich

Primary script: `enrich_supplements_v3.py`

What it does:
- Loads reference databases from `scripts/data/`.
- Performs matching and classification.
- Builds structured domain outputs used by scoring.
- Projects scorer-friendly flattened fields on each product.

What it must not do:
- No final `score_80` arithmetic.

Enrichment fail-fast critical DBs:
- `ingredient_quality_map`
- `harmful_additives`
- `allergens`
- `banned_recalled_ingredients`
- `color_indicators`

Default DB set loaded by enrichment:
- `ingredient_quality_map.json`
- `absorption_enhancers.json`
- `enhanced_delivery.json`
- `standardized_botanicals.json`
- `synergy_cluster.json`
- `banned_recalled_ingredients.json`
- `banned_match_allowlist.json`
- `harmful_additives.json`
- `allergens.json`
- `backed_clinical_studies.json`
- `top_manufacturers_data.json`
- `manufacturer_violations.json` (exact-match penalties plus curated `manufacturer_family_*` and non-scoring `related_brand_cluster_*` metadata)
- `rda_optimal_uls.json`
- `clinically_relevant_strains.json`
- `color_indicators.json`
- `cert_claim_rules.json`
- `other_ingredients.json`

Additional detector-backed data used in enrichment:
- `proprietary_blends.json` via `proprietary_blend_detector.py`
- `fda_unii_cache.json` via `unii_cache.py` — offline UNII identity resolution (172K substances, avoids live FDA API calls during enrichment)

### Stage 2.5: Coverage Gate (Optional but recommended)

Primary script: `coverage_gate.py`

What it does:
- Checks enriched outputs for coverage and quality thresholds.
- Can run in enforce or warn-only mode.

### Stage 3: Score

Primary script: `score_supplements.py`
Config: `config/scoring_config.json`

What it does:
- Arithmetic-only scoring and verdict assignment.
- Reads enriched product fields and scorer config.
- Does not perform fuzzy matching or database matching.

What it reads directly:
- Enriched JSON input files
- `scoring_config.json`

What it does not load directly:
- `scripts/data/*.json` scoring reference databases

## Enrichment-to-Scoring Contract

Scorer expects enriched domain blocks plus projected convenience fields.

Common projected fields consumed by scorer:
- `delivery_tier`
- `absorption_enhancer_paired`
- `has_standardized_botanical`
- `synergy_cluster_qualified`
- `claim_allergen_free_validated`
- `claim_gluten_free_validated`
- `claim_vegan_validated`
- `named_cert_programs`
- `gmp_level`
- `has_coa`
- `has_batch_lookup`
- `proprietary_blends`
- `has_disease_claims`
- `is_trusted_manufacturer`
- `has_full_disclosure`
- `claim_physician_formulated`
- `has_sustainable_packaging`
- `manufacturing_region`

Core domain blocks consumed by scorer:
- `ingredient_quality_data`
- `contaminant_data`
- `compliance_data`
- `certification_data`
- `evidence_data`
- `manufacturer_data`
- `probiotic_data`
- `match_ledger` (for diagnostics/flags)

## Scoring Pipeline Logic (High-Level)

`score_product()` order:

1. Validate enriched product minimum contract (`dsld_id`, `product_name`, enrichment metadata).
2. Run B0 banned/recalled gate.
3. Run mapping gate.
4. Apply regression guard for unmatched active overlapping banned `exact/alias`.
5. If early-stop conditions are met, return `BLOCKED`/`UNSAFE`/`NOT_SCORED`.
6. Score sections A/B/C/D.
7. Apply manufacturer violation deduction.
8. Clamp final score to `[0, 80]`.
9. Derive verdict by precedence.
10. Emit output with breakdown, flags, and scoring metadata.

## Current Scoring Gate Settings

From `config/scoring_config.json`:
- `require_full_mapping: true`
- `probiotic_extended_scoring: false`
- `shadow_mode: true`

Operational effect:
- Full mapping gate is enforced.
- Probiotic bonus runs in default mode (not extended mode).

## Mapping KPI Semantics (Current)

Scorer outputs both:
- `unmapped_actives_total`
- `unmapped_actives_excluding_banned_exact_alias`

Purpose:
- Distinguish true mapping gaps from unmatched actives that are already captured as banned exact/alias safety events.

Guardrail:
- If unmatched active overlaps banned `exact/alias`, scorer forces unsafe path and prevents counting this as a normal mapping miss.

## Score Structure

Quality score formula:

```text
quality_raw = A + B + C + D + violation_penalty
quality_score = clamp(0, 80, quality_raw)
```

Section caps:
- A: 25
- B: 30
- C: 20
- D: 5

For detailed formulas and subcomponents, see:
- `SCORING_ENGINE_SPEC.md`

## Stage 4: Distribute (sync_to_supabase.py)

**Input:** Build output from build_final_db.py (pharmaguide_core.db + detail_blobs/ + export_manifest.json)
**Output:** Versioned artifacts in Supabase Storage + manifest row in PostgreSQL

**Workflow:**
1. Read export_manifest.json from build directory
2. Compare version to current Supabase manifest (is_current=true)
3. If newer: upload .db file and detail blobs to Supabase Storage
4. Insert new manifest row, mark previous as not current

**Environment:** Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env

**CLI:**
```bash
python scripts/sync_to_supabase.py <build_output_dir>          # Full sync
python scripts/sync_to_supabase.py <build_output_dir> --dry-run # Preview only
```

**Safety:** Uses upsert mode. Re-running is idempotent. The Flutter app reads the manifest to detect new versions and downloads in background — never blocks the user.

## Export Schema Version History

| Version | Date | Columns | Changes |
|---------|------|---------|---------|
| v1.3.2 | 2026-04-10 | 90 | `calories_per_serving` column + `nutrition_detail` / `unmapped_actives` blob subkeys |
| v1.3.3 | 2026-04-14 | 90 | Interaction safety expansion: 129 rules (was 98), 4 new drug classes, context-aware harmful scoring, 25 PMID fixes, IQM 588 entries (was 571) |
| v1.3.4 | 2026-04-14 | 90 | CAERS B8 scoring (159 adverse event signals), UNII offline cache (172K substances), IQM UNII standardization (66%), drug label interaction mining |
| v1.4.0 | 2026-04-15 | 91 | `image_thumbnail_url` column added; `normalize_upc` field added; image upload pipeline |
| v1.5.0 | 2026-05-05 | 91 | Canonical active + inactive ingredient contract: `display_form_label`, `form_status`, `form_match_status`, `dose_status` on actives; `display_label`, `display_role_label`, `severity_status`, `is_safety_concern` on inactives. Flutter renders these without local inference; legacy `form` / `is_harmful` kept for back-compat then deprecated. |
| v1.6.0 | 2026-05-12 | 91 | `profile_gate` passthrough on `interaction` / `drug_interaction` warning entries so Flutter routes condition/drug-class hits without re-evaluating thresholds. Coverage gate: products with `unmapped_actives_total > 0` get `verdict=NOT_SCORED` and are excluded from the final DB by the Batch 3 data integrity gate. `canonical_id` + `delivers_markers` now emitted at blob level on active ingredients (identity vs bioactivity split). |

Runtime source of truth: `EXPORT_SCHEMA_VERSION` and `CORE_COLUMN_COUNT` in `build_final_db.py`. Per-column contract: `FINAL_EXPORT_SCHEMA_V1.md`.

## Utility Scripts

New scripts added to `scripts/` beyond the core pipeline stages:

| Script | Purpose |
|--------|---------|
| `backfill_upc.py` | UPC backfilling for existing products |
| `extract_product_images.py` | Product image extraction and Supabase upload |
| `build_interaction_db.py` | Assembles interaction rules reference DB for Flutter export |
| `unii_cache.py` | Manages `fda_unii_cache.json` offline UNII registry |
| `shadow_score_comparison.py` | Compares two scored outputs for regression detection |
| `regression_snapshot.py` | Takes a scoring baseline snapshot for regression testing |
| `preflight.py` | Pre-pipeline data contract validation |
| `unmapped_ingredient_tracker.py` | Tracks and reports unmapped ingredient trends |
| `release_catalog_artifact.py` | Assembles release artifacts for catalog deploys |
| `release_interaction_artifact.py` | Assembles interaction rule artifacts for release |
| `assemble_final_db_release.py` | Packages final DB release artifacts |
| `build_all_final_dbs.py` | Runs `build_final_db.py` across multiple dataset directories |

## CLI Quick Reference

```bash
# Full pipeline
python run_pipeline.py

# Run enrichment + scoring only
python run_pipeline.py --stages enrich,score

# Score-only run (requires existing enriched outputs)
python run_pipeline.py --stages score

# Skip coverage gate
python run_pipeline.py --skip-coverage-gate
```
