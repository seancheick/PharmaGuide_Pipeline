# PIPELINE_ARCHITECTURE.md

## Overview

PharmaGuide runs a 3-stage pipeline:

1. `clean_dsld_data.py` (Clean)
2. `enrich_supplements_v3.py` (Enrich)
3. `score_supplements.py` (Score)

Orchestration is handled by `run_pipeline.py`.

```text
raw_data/*.json
  -> [CLEAN] clean_dsld_data.py
output_*/cleaned/*.json
  -> [ENRICH] enrich_supplements_v3.py
output_*_enriched/enriched/*.json
  -> [COVERAGE GATE] coverage_gate.py (optional, can block scoring)
  -> [SCORE] score_supplements.py
output_*_scored/scored/*.json
```

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
- `manufacturer_violations.json`
- `rda_optimal_uls.json`
- `clinically_relevant_strains.json`
- `color_indicators.json`
- `cert_claim_rules.json`
- `other_ingredients.json`

Additional detector-backed data used in enrichment:
- `proprietary_blends.json` via `proprietary_blend_detector.py`

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
- B: 35
- C: 15
- D: 5

For detailed formulas and subcomponents, see:
- `SCORING_ENGINE_SPEC.md`

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

