# PIPELINE_ARCHITECTURE.md

## Overview

Three-stage data pipeline transforming raw DSLD supplement data into scored quality assessments.

```
raw_data/*.json
  ↓ [Stage 1: CLEAN] clean_dsld_data.py + EnhancedDSLDNormalizer
output_Lozenges/cleaned/*.json
  ↓ [Stage 2: ENRICH] enrich_supplements_v3.py (SupplementEnricherV3)
output_Lozenges_enriched/enriched/*.json
  ↓ [Stage 2.5: COVERAGE GATE] coverage_gate.py (optional)
  ↓ [Stage 3: SCORE] score_supplements.py (SupplementScorer)
output_Lozenges_scored/*.json
```

**Orchestrator:** `run_pipeline.py` (PipelineRunner v1.1.0)

---

## Stage 1: Cleaning

**Script:** `clean_dsld_data.py` | **Normalizer:** `enhanced_normalizer.py`
**Config:** `config/cleaning_config.json`

### What It Does
- Normalizes raw ingredient names to standardized database entries
- Maps ingredients to IQM forms via alias lookup (first-match-wins)
- Probiotic strain bypass: routes clinical strains before generic alias lookup
- Detects allergens and assigns severity levels
- Flags harmful additives
- Extracts certifications from labels
- Assigns quality assessment tiers

### Databases Consumed
| Database | Purpose |
|----------|---------|
| `ingredient_quality_map.json` | Master ingredient + form matching |
| `clinically_relevant_strains.json` | Probiotic strain bypass |
| `harmful_additives.json` | Additive flagging |
| `allergens.json` | Allergen detection |
| `other_ingredients.json` | Inactive ingredient classification |
| `standardized_botanicals.json` | Botanical standardization |
| `color_indicators.json` | Natural vs artificial color |
| `ingredient_classification.json` | Active/inactive classification |

### Output Schema
```json
{
  "dsld_id": 13946,
  "product_name": "OralBiotic",
  "brand_name": "NOW",
  "activeIngredients": [{
    "name": "BLIS K12 Streptococcus salivarius",
    "standardName": "Probiotics",
    "amount": "1",
    "unit": "Billion CFU",
    "forms": ["blis k12"]
  }],
  "inactiveIngredients": [...],
  "allergens_detected": [...],
  "certifications_detected": [...]
}
```

### Processing: Batch 500 files / 4 workers / resume-capable

---

## Stage 2: Enrichment

**Script:** `enrich_supplements_v3.py` (SupplementEnricherV3 v3.1.0)
**Config:** `config/enrichment_config.json`

### What It Does
- Collects quality metadata WITHOUT scoring calculations
- Modular collectors for each scoring section (A/B/C/D)
- Classifies supplement type: `single_nutrient`, `targeted`, `multivitamin`, `herbal_blend`, `probiotic`, `specialty`
- Tracks all match decisions in the match ledger

### Match Ledger Partitions
5 buckets tracked per ingredient across 6 domains:

| Bucket | Description |
|--------|-------------|
| `matched` | Successfully matched to database entry |
| `unmatched` | Not found in any database |
| `rejected` | Found but explicitly rejected |
| `skipped` | Intentionally skipped (inactive) |
| `recognized_non_scorable` | Recognized but not therapeutic |

**6 Domains:** `ingredients`, `additives`, `allergens`, `manufacturer`, `delivery`, `claims`

**Match Methods:** `exact`, `normalized`, `pattern`, `contains`, `token_bounded`, `fuzzy` (85%+ threshold)

### Databases Consumed
All 18+ databases including:
- Full cleaning set (IQM, allergens, harmful additives, botanicals)
- `backed_clinical_studies.json` — evidence scoring data
- `banned_recalled_ingredients.json` — safety disqualification
- `banned_match_allowlist.json` — match overrides
- `enhanced_delivery.json` — delivery system tiers
- `absorption_enhancers.json` — bioavailability bonuses
- `synergy_cluster.json` — ingredient synergy detection
- `manufacturer_violations.json` — compliance records
- `top_manufacturers_data.json` — manufacturer quality ratings
- `rda_optimal_uls.json` — dosing reference values
- `unit_conversions.json` — unit conversion factors
- `cert_claim_rules.json` — certification validation
- `user_goals_to_clusters.json` — goal mapping
- `id_redirects.json` — deprecated ID resolution

### Output Schema
Extends cleaned data with enrichment layers:
```json
{
  "...cleaned fields...",
  "supplement_type": {"type": "probiotic", "active_count": 1, ...},
  "section_a_data": {"ingredient_quality": [...], "delivery_systems": [...]},
  "section_b_data": {"safety_flags": [...], "additive_matches": [...]},
  "section_c_data": {"clinical_evidence": [...]},
  "section_d_data": {"manufacturer_data": {...}},
  "probiotic_data": {"total_strain_count": 1, "clinical_strains": [...]},
  "match_ledger": {"ingredients": [...], "additives": [...]},
  "enrichment_metadata": {"version": "3.1.0", "timestamp": "..."}
}
```

### Processing: Batch 100 products / 4 workers

---

## Stage 2.5: Coverage Gate

**Script:** `coverage_gate.py` (CoverageGate)
**Control:** `--skip-coverage-gate` or `--coverage-gate-warn-only`

### What It Does
Validates enriched data meets coverage thresholds before scoring:
- Minimum match coverage per domain (ingredients, additives, allergens, manufacturer)
- Correctness checks for contradictions and missing conversions
- Can block individual products from scoring

### Output
- `coverage_report_TIMESTAMP.json` — machine-readable
- `coverage_report_TIMESTAMP.md` — human-readable

---

## Stage 3: Scoring

**Script:** `score_supplements.py` (SupplementScorer)
**Config:** `config/scoring_config.json`

### What It Does
Pure arithmetic scoring — no matching or NLP. Reads enriched data and calculates:

### Score Breakdown (80 points max)

| Section | Max | Components |
|---------|-----|------------|
| **A: Ingredient Quality** | 25 | A1 Bioavailability (13), A2 Premium Forms (3), A3 Delivery System (3), A4 Absorption Enhancer (3), A5 Formulation Excellence (3) |
| **A: Probiotic Bonus** | +2-10 | CFU, Diversity, Prebiotic, Clinical Strains, Survivability (gated on supp_type="probiotic") |
| **B: Safety & Purity** | 35 | Base 35 minus penalties: B1 Harmful Additives (5), B2 Allergens (2), B3 Claims (4), B4 Certs (21), B5 Blends (15), B6 Marketing (5) |
| **C: Evidence & Research** | 15 | Evidence tiers × study types, 5pt/ingredient cap |
| **D: Brand Trust** | 5 | D1 Manufacturer (2), D2 Disclosure (1), D3 Physician (0.5), D4 Region (0.5), D5 Sustainability (0.5) |

**Final arithmetic:** `score_80 = A + B + C + D + violation_penalty` (clamped to 0-80).

### Verdict Precedence (first match wins)
1. **BLOCKED** — Safety violations
2. **UNSAFE** — Manufacturer violations, banned ingredients
3. **NOT_SCORED** — Missing enrichment or scorable ingredients
4. **CAUTION** — Moderate concerns (flags present)
5. **POOR** — Score < 32
6. **SAFE** — Score >= 32, no issues

### Grade Scale (100-point equivalent)
| Grade | Range |
|-------|-------|
| Exceptional | 90+ |
| Excellent | 80-89 |
| Good | 70-79 |
| Fair | 60-69 |
| Below Average | 50-59 |
| Low | 32-49 |
| Very Poor | 0-31 |

### Processing: Batch 100 products / 4 workers

---

## Configuration Files

| Config | Stage | Key Settings |
|--------|-------|-------------|
| `config/cleaning_config.json` | Clean | batch_size=500, max_workers=4, paths |
| `config/enrichment_config.json` | Enrich | batch_size=100, max_workers=4, database_paths, fuzzy_matching=true |
| `config/scoring_config.json` | Score | feature_gates, section weights, verdict rules, grade scale |

---

## Key Modules

| Module | Role |
|--------|------|
| `batch_processor.py` | Batch handling, multiprocessing, resume |
| `enhanced_normalizer.py` | Ingredient normalization, alias lookup, strain bypass |
| `match_ledger.py` | Centralized match tracking, 6 domains, audit trail |
| `enrichment_contract_validator.py` | Validates enriched data integrity |
| `dsld_validator.py` | DSLD schema validation |
| `unit_converter.py` | Unit conversions (mg, mcg, IU, %) |
| `dosage_normalizer.py` | Dosage normalization |
| `proprietary_blend_detector.py` | Blend detection and analysis |
| `rda_ul_calculator.py` | RDA/UL sufficiency calculations |
| `normalization.py` | Single-source text normalization |
| `coverage_gate.py` | Pre-scoring coverage validation |
| `constants.py` | Centralized constants and database paths |

---

## CLI Usage

```bash
# Full pipeline
python run_pipeline.py

# Selective stages
python run_pipeline.py --stages enrich,score

# Custom output
python run_pipeline.py --output-prefix output_Vitamins

# Dry run
python run_pipeline.py --dry-run

# Skip coverage gate
python run_pipeline.py --skip-coverage-gate
```
