# Probiotic Strain Matching Fix — Phase 5.6 Report

## Problem Statement

17 of 19 probiotic strain ingredients were being generalized to "Probiotics" during cleaning, losing strain-level clinical identity. This broke the probiotic bonus chain: products with probiotic strains received `probiotic_bonus = 0.0` because they were classified as `single_nutrient` instead of `probiotic`.

## Root Cause: Three-Part Failure Chain

### 1. Cleaning — Generic IQM Catchall
The `ingredient_quality_map.json` entry for generic "probiotics" contained form aliases that matched all strain names (e.g., "lactobacillus acidophilus", "bifidobacterium lactis"). The alias lookup used first-match-wins, so the generic entry registered before strain-specific entries.

**Result:** `standardName = "Probiotics"` for all strain ingredients.

### 2. Enrichment — Single-Nutrient Fast-Path
`_classify_supplement_type()` had `active_count == 1 → single_nutrient` as the first check, before any probiotic detection. Single-strain probiotic products (1 active ingredient) were always classified as `single_nutrient`.

**Result:** `supplement_type = "single_nutrient"` for single-strain probiotics.

### 3. Scoring — Probiotic Bonus Gate
`_score_probiotic_bonus()` gates on `supp_type != "probiotic"` → returns 0.0 for all sub-components (CFU, diversity, prebiotic, clinical_strains, survivability).

**Result:** `probiotic_bonus = 0.0` for all affected products.

## Fix Implementation

### Fix 1: Probiotic Strain Bypass in Cleaning (`enhanced_normalizer.py`)
- Added `_build_strain_lookup()` method: builds normalized alias→strain_name lookup from all 42 clinical strains in `clinically_relevant_strains.json`
- Added `_match_probiotic_strain()` method: two-pass matching (exact then longest-substring, min 6 chars)
- Injected bypass in `_perform_ingredient_mapping()` BEFORE standard alias lookup
- Imported `CLINICALLY_RELEVANT_STRAINS` path from `constants.py`

### Fix 2: Probiotic-First Type Classification (`enrich_supplements_v3.py`)
- Added name-based probiotic detection using genus terms: `lactobacillus`, `bifidobacterium`, `streptococcus`, `bacillus`, `saccharomyces`, `limosilactobacillus`, `lacticaseibacillus`
- Moved probiotic classification BEFORE `single_nutrient` fast-path
- Added double-counting guard: name-based detection only counts ingredients whose category is NOT already `probiotic`/`bacteria`

### Fix 3: Alias Expansion (`clinically_relevant_strains.json`, `ingredient_quality_map.json`)
- Added DSLD label text aliases for K12 and M18 strains
- Added `bifidobacterium animalis lactis` aliases to `bifidobacterium_lactis` entry

## Before/After Comparison

### Product 13946 — NOW OralBiotic (BLIS K12 + FOS)

| Metric | Before | After |
|--------|--------|-------|
| supplement_type | single_nutrient | **probiotic** |
| probiotic_bonus | 0.0 | **2.0** |
| probiotic_bonus.cfu | 0.0 | **1.0** |
| probiotic_bonus.prebiotic | 0.0 | **1.0** |
| quality_score | ~51.2 | **53.2** |
| verdict | SAFE | SAFE |

### Product 15351 — Nature's Plus ENT K12 Probiotics

| Metric | Before | After |
|--------|--------|-------|
| supplement_type | single_nutrient | **probiotic** |
| probiotic_bonus | 0.0 | **1.0** |
| probiotic_bonus.cfu | 0.0 | **1.0** |
| quality_score | ~23.3 | **24.3** |
| verdict | POOR | POOR |

### Product 15258 — Protocol For Life Balance E.N.T. Biotic

| Metric | Before | After |
|--------|--------|-------|
| supplement_type | single_nutrient | **probiotic** |
| probiotic_bonus | 0.0 | **1.0** |
| probiotic_bonus.prebiotic | 0.0 | **1.0** |
| quality_score | ~51.2 | **52.2** |
| verdict | SAFE | SAFE |

## Impact on Score Distribution

### Reclassification Impact
- **24 products** reclassified from `single_nutrient` → `probiotic`
- Reclassified products average score: 43.1 (mostly SAFE: 19/24)
- Probiotic bonus adds 1.0–2.0 points per product

### Supplement Type Distribution (978 products)

| Type | Count | % |
|------|-------|---|
| targeted | 460 | 47.0% |
| single_nutrient | 415 | 42.4% |
| specialty | 69 | 7.1% |
| probiotic | 34 | 3.5% |

### Probiotic vs Single Nutrient Average Scores

| Type | Avg Score | Min | Max |
|------|-----------|-----|-----|
| probiotic (34) | 40.31 | 21.3 | 54.9 |
| single_nutrient (415) | 42.26 | 0.0 | 53.4 |

### Overall Distribution Shift
The broader shift (SAFE 775→735, CAUTION 58→90, UNSAFE 6→15) is primarily driven by scoring hardening modules (new safety flags: `BANNED_MATCH_REVIEW_NEEDED`, `B0_MODERATE_SUBSTANCE`, `MANUFACTURER_VIOLATION`), NOT the probiotic reclassification.

## Test Results

- **856 tests passed, 0 failures**
- 5 skipped, 2 xfailed, 6 xpassed

## Files Changed

| File | Change |
|------|--------|
| `scripts/constants.py` | Added `CLINICALLY_RELEVANT_STRAINS` path constant |
| `scripts/enhanced_normalizer.py` | Added strain bypass: `_build_strain_lookup()`, `_match_probiotic_strain()`, bypass in `_perform_ingredient_mapping()` |
| `scripts/enrich_supplements_v3.py` | Probiotic-first type classification with name-based detection |
| `scripts/data/clinically_relevant_strains.json` | Added DSLD label text aliases for K12 and M18 |
| `scripts/data/ingredient_quality_map.json` | Added B. animalis lactis aliases |
| `scripts/tests/test_ingredient_quality_map_schema.py` | Updated `ALLOWED_CROSS_ALIASES` for new IQM aliases |
