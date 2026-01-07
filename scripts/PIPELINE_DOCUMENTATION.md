# PharmaGuide DSLD Data Pipeline Documentation

## Overview

The PharmaGuide supplement data pipeline transforms raw DSLD (Dietary Supplement Label Database) data into scored, enriched supplement profiles. The pipeline has **3 stages**:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  CLEANING   │ ──▶ │ ENRICHMENT  │ ──▶ │  SCORING    │
│             │     │             │     │             │
│ Normalizes  │     │ Adds data   │     │ Calculates  │
│ & validates │     │ from DBs    │     │ final score │
└─────────────┘     └─────────────┘     └─────────────┘
     │                    │                   │
     ▼                    ▼                   ▼
  cleaned/           enriched/            scored/
  batch_*.json       batch_*.json         batch_*.json
     │
     ▼
  unmapped/
  unmapped_*.json
```

---

## Stage 1: CLEANING

**Script:** `clean_dsld_data.py`
**Config:** `config/cleaning_config.json`
**Input:** Raw DSLD JSON files
**Output:** `output_*/cleaned/cleaned_batch_*.json` + `output_*/unmapped/*.json`

### What It Does

1. **Validates** raw DSLD product data structure
2. **Normalizes** ingredient names to standard forms
3. **Maps** ingredients to reference databases (quality, additives, botanicals)
4. **Classifies** ingredients by hierarchy (source → summary → component)
5. **Tracks unmapped** ingredients for later database updates

### Key Normalization Rules

- Lowercase conversion
- Removes parenthetical forms: `"Vitamin C (Ascorbic Acid)"` → `"vitamin c"`
- Strips dosage info: `"Fish Oil 1000mg"` → `"fish oil"`
- Handles "as" forms: `"Zinc (as Zinc Gluconate)"` → mapped to zinc gluconate form

### Output Structure (Cleaned Product)

```json
{
  "id": 12345,
  "fullName": "Product Name",
  "brandName": "Brand",
  "activeIngredients": [
    {
      "ingredientId": 12345,
      "name": "Vitamin D3",
      "standardName": "vitamin d3",
      "quantity": 5000,
      "unit": "IU",
      "mapped": true,
      "hierarchyType": {
        "type": "component",
        "category": "vitamins",
        "scoring_rule": "score_this"
      }
    }
  ],
  "inactiveIngredients": [
    {
      "name": "Gelatin",
      "standardName": "gelatin",
      "mapped": true,
      "isAdditive": true,
      "additiveType": "capsule_material"
    }
  ],
  "nutritionalInfo": {
    "sugars": {"amount": 0, "unit": "g"},
    "sodium": {"amount": 10, "unit": "mg"}
  }
}
```

---

## Stage 2: ENRICHMENT

**Script:** `enrich_supplements_v3.py`
**Config:** `config/enrichment_config.json`
**Input:** Cleaned batch files
**Output:** `output_*/enriched/enriched_*.json`

### What It Does

1. **Collects quality data** for each ingredient (bioavailability, forms, scores)
2. **Identifies certifications** (NSF, USP, GMP, third-party testing)
3. **Detects** enhanced delivery systems (liposomal, phytosome, etc.)
4. **Checks** for banned/recalled ingredients
5. **Evaluates** harmful additives
6. **Matches** clinical evidence (branded ingredients, RCTs)
7. **Assesses** manufacturer reputation
8. **Adds dietary sensitivity flags** (sugar, sodium for diabetes/hypertension)
9. **Adds safety verification flags** (purity, heavy metal testing, label accuracy)

### Enrichment Data Sections

| Section | Purpose | Key Fields |
|---------|---------|------------|
| `ingredient_quality_data` | Form quality & bioavailability | `quality_scores`, `mapped_count`, `unmapped_count` |
| `delivery_data` | Enhanced absorption systems | `systems_found`, `tier`, `description` |
| `absorption_data` | Absorption enhancers present | `enhancers`, `pairs_found` |
| `formulation_data` | Synergy clusters detected | `clusters_matched` |
| `contaminant_data` | Banned/harmful ingredients | `banned_found`, `harmful_additives` |
| `compliance_data` | Regulatory compliance | `fda_warnings`, `recalls` |
| `certification_data` | Third-party testing | `third_party_programs`, `gmp`, `purity_verified` |
| `evidence_data` | Clinical backing | `branded_ingredients`, `rct_backed` |
| `manufacturer_data` | Brand reputation | `is_top_manufacturer`, `violations` |
| `dietary_sensitivity_data` | Sugar/sodium flags | `diabetes_friendly`, `hypertension_friendly` |
| `probiotic_data` | CFU counts & strains | `total_cfu`, `strain_count`, `clinical_strains` |

### Output Structure (Enriched Product)

```json
{
  "...cleaned fields...",
  "enrichment_version": "3.0.0",
  "enriched_date": "2025-12-08T15:00:00Z",

  "supplement_type": {
    "type": "multivitamin",
    "active_count": 12,
    "total_count": 18
  },

  "ingredient_quality_data": {
    "total_active": 12,
    "mapped_count": 11,
    "unmapped_count": 1,
    "quality_scores": [
      {"name": "Vitamin D3", "form": "cholecalciferol", "score": 9, "bio_score": 9}
    ]
  },

  "certification_data": {
    "third_party_programs": {"count": 2, "programs": [{"name": "NSF Sport"}]},
    "gmp": {"detected": true},
    "purity_verified": true,
    "heavy_metal_tested": true,
    "label_accuracy_verified": false
  },

  "dietary_sensitivity_data": {
    "sugar": {"amount_g": 3.0, "level": "low", "level_display": "Low Sugar"},
    "sodium": {"amount_mg": 10.0, "level": "very_low"},
    "diabetes_friendly": true,
    "hypertension_friendly": true,
    "warnings": []
  }
}
```

---

## Stage 3: SCORING

**Script:** `score_supplements.py`
**Config:** `config/scoring_config.json`
**Input:** Enriched batch files
**Output:** `output_*/scored/scored_*.json`

### What It Does

Calculates a **0-80 point server-side score** (+ 20 points user profile on device = 100 total)

### Scoring Sections

| Section | Max Points | What It Measures |
|---------|------------|------------------|
| **A: Ingredient Quality** | 30 | Form quality, bioavailability, dosing, delivery systems |
| **B: Safety & Purity** | 25 | Contaminants, certifications, transparency |
| **C: Evidence & Research** | 15 | Clinical studies, branded ingredients |
| **D: Brand Trust** | 10 | Manufacturer reputation, violations |
| **Probiotic Bonus** | +5 | (Only for probiotic products) |

### Scoring Logic Example

```
Section A (30 max):
  A1: Ingredient Forms (15)  → avg quality score × 15/10
  A2: Bioavailability (8)    → delivery system tier bonus
  A3: Dosing Precision (5)   → RDA compliance
  A4: Synergy (2)            → absorption enhancer pairs

Section B (25 max):
  B1: Contaminants (-20)     → banned ingredients penalty
  B2: Harmful Additives (-8) → artificial colors, sweeteners
  B3: Certifications (+10)   → NSF, USP, GMP bonuses
  B4: Transparency (+5)      → no proprietary blends

Section C (15 max):
  C1: Product Evidence (8)   → product-specific RCTs
  C2: Ingredient Evidence (5)→ ingredient-level studies
  C3: Strain Evidence (2)    → probiotic strain studies

Section D (10 max):
  D1: Manufacturer Rep (6)   → top manufacturer bonus
  D2: Violations (-10)       → recalls, FDA warnings
```

### Output Structure (Scored Product)

```json
{
  "...enriched fields...",
  "scoring_version": "3.4.0",
  "scored_date": "2025-12-08T16:00:00Z",

  "score_80": 62.5,
  "score_100_equivalent": 78.1,
  "grade": "B+",

  "section_scores": {
    "A": {"score": 24.5, "max": 30, "details": {...}},
    "B": {"score": 20.0, "max": 25, "details": {...}},
    "C": {"score": 10.0, "max": 15, "details": {...}},
    "D": {"score": 8.0, "max": 10, "details": {...}}
  },

  "scoring_notes": ["Top manufacturer detected", "NSF certified"]
}
```

---

## Reference Database Files

All located in `scripts/data/`

### 1. `ingredient_quality_map.json` (386 entries)
**Purpose:** Maps ingredients to quality forms with bioavailability scores

```json
{
  "vitamin_d3": {
    "standard_name": "Vitamin D3",
    "category": "vitamins",
    "forms": {
      "cholecalciferol": {
        "bio_score": 9,
        "natural": true,
        "score": 9,
        "aliases": ["vitamin d3", "cholecalciferol", "d3"]
      },
      "ergocalciferol": {
        "bio_score": 5,
        "natural": false,
        "score": 5,
        "aliases": ["vitamin d2", "ergocalciferol"]
      }
    }
  }
}
```

### 2. `harmful_additives.json` (102 entries)
**Purpose:** Identifies harmful additives with risk levels and warnings

```json
{
  "harmful_additives": [
    {
      "id": "ADD_ASPARTAME",
      "standard_name": "Aspartame",
      "aliases": ["aspartame", "E951", "NutraSweet", "Equal"],
      "risk_level": "high",
      "category": "sweetener_artificial",
      "mechanism_of_harm": "Metabolizes into...",
      "population_warnings": [
        "People with PKU - Contains phenylalanine",
        "People prone to headaches - May trigger migraines"
      ]
    }
  ]
}
```

### 3. `other_ingredients.json` (234 entries)
**Purpose:** Classifies inactive ingredients (excipients, fillers, coatings)

```json
{
  "other_ingredients": [
    {
      "id": "NHA_CELLULOSE",
      "standard_name": "Cellulose",
      "aliases": ["cellulose", "microcrystalline cellulose", "MCC"],
      "risk_level": "none",
      "category": "binder",
      "clean_label_score": 9,
      "notes": "Plant-derived fiber, very safe"
    }
  ]
}
```

### 4. `banned_recalled_ingredients.json` (17 categories)
**Purpose:** Flags banned, recalled, or dangerous ingredients

```json
{
  "permanently_banned": [
    {
      "id": "BANNED_EPHEDRA",
      "standard_name": "Ephedra",
      "aliases": ["ma huang", "ephedrine", "ephedra sinica"],
      "banned_date": "2004-04-12",
      "reason": "FDA banned due to cardiovascular risks",
      "penalty_points": -20
    }
  ],
  "sarms_prohibited": [...],
  "high_risk_ingredients": [...]
}
```

### 5. `backed_clinical_studies.json` (126 entries)
**Purpose:** Branded ingredients with clinical evidence

```json
{
  "backed_clinical_studies": [
    {
      "id": "BRAND_MERIVA",
      "standard_name": "Meriva Curcumin Phytosome",
      "aliases": ["meriva", "curcumin phytosome"],
      "evidence_level": "branded-rct",
      "study_type": "rct_multiple",
      "key_endpoints": ["joint pain", "inflammation"],
      "score_contribution": "tier_1"
    }
  ]
}
```

### 6. `enhanced_delivery.json` (47 entries)
**Purpose:** Identifies advanced delivery systems that improve bioavailability

```json
{
  "liposomal": {
    "tier": 1,
    "description": "Phospholipid encapsulation – 300-1000%+ bioavailability increase",
    "category": "delivery"
  },
  "phytosome": {
    "tier": 1,
    "description": "Phospholipid complex for enhanced absorption"
  }
}
```

### 7. `top_manufacturers_data.json` (61 entries)
**Purpose:** Trusted manufacturers for reputation scoring

```json
{
  "top_manufacturers": [
    {
      "id": "MANUF_THORNE",
      "standard_name": "Thorne Research",
      "aliases": ["Thorne", "Thorne Research"],
      "evidence": ["NSF Certified for Sport", "No FDA warnings"],
      "notes": "Premium quality, physician-grade supplements"
    }
  ]
}
```

### 8. `clinically_relevant_strains.json` (strain database)
**Purpose:** Probiotic strains with clinical evidence

```json
{
  "clinically_relevant_strains": [
    {
      "strain": "Lactobacillus rhamnosus GG",
      "aliases": ["LGG", "L. rhamnosus GG"],
      "evidence_level": "strong",
      "studied_benefits": ["gut health", "immune support", "diarrhea prevention"],
      "clinical_trials": 500
    }
  ]
}
```

### 9. `allergens.json` (38 allergens)
**Purpose:** Flags common allergens (FDA Big 9 + EU allergens)

```json
{
  "common_allergens": [
    {
      "name": "Milk",
      "aliases": ["milk", "dairy", "lactose", "casein", "whey"],
      "severity": "high",
      "regulatory": "FDA Major Allergen"
    }
  ]
}
```

### 10. `ingredient_classification.json`
**Purpose:** Hierarchical classification to prevent double-scoring

```json
{
  "omega_fatty_acids": {
    "sources": ["fish oil", "krill oil", "algal oil"],
    "summaries": ["total omega-3", "omega-3 fatty acids"],
    "components": ["EPA", "DHA", "ALA"],
    "scoring_rule": "Score components only, skip sources and summaries"
  }
}
```

### 11. `synergy_cluster.json` (42 clusters)
**Purpose:** Ingredient combinations that work synergistically

```json
{
  "synergy_clusters": [
    {
      "name": "Curcumin Absorption",
      "id": "curcumin_absorption",
      "ingredients": ["curcumin", "piperine", "black pepper"],
      "min_effective_doses": {"curcumin": 500, "piperine": 5},
      "evidence_tier": "high"
    }
  ]
}
```

### 12. `absorption_enhancers.json` (23 enhancers)
**Purpose:** Compounds that enhance absorption of other ingredients

```json
{
  "absorption_enhancers": [
    {
      "name": "Black Pepper",
      "aliases": ["piperine", "bioperine"],
      "enhances": ["Turmeric", "CoQ10", "Beta-carotene"],
      "mechanism": "Inhibits glucuronidation, improves permeability"
    }
  ]
}
```

---

## Unmapped Ingredients Workflow

### How Unmapped Tracking Works

During cleaning, any ingredient that doesn't match a reference database is tracked:

```
output_*/unmapped/
├── unmapped_active_ingredients.json    # Active ingredients not in quality_map
└── unmapped_inactive_ingredients.json  # Inactive not in other_ingredients/harmful
```

### Unmapped File Structure

```json
{
  "metadata": {
    "generated_at": "2025-12-08T20:10:27Z",
    "total_unmapped": 464,
    "total_occurrences": 838
  },
  "unmapped_ingredients": {
    "Isomalto-Oligosaccharides": 20,   // appears in 20 products
    "Vitamin K-2": 17,
    "Total EPA & DHA": 14,
    "Tribasic Calcium Phosphate": 13
  }
}
```

### Process to Achieve 100% Mapping

1. **Run cleaning** → generates unmapped files
2. **Review unmapped list** by occurrence count (prioritize high-count items)
3. **Classify each ingredient:**
   - Is it a quality form? → Add to `ingredient_quality_map.json`
   - Is it an additive? → Add to `other_ingredients.json`
   - Is it harmful? → Add to `harmful_additives.json`
   - Is it a botanical? → Add to `botanical_ingredients.json`
   - Is it a hierarchy item (Total X, Source)? → Add to `ingredient_classification.json`
4. **Re-run cleaning** → check if unmapped count decreased
5. **Repeat** until unmapped count is 0 or only edge cases remain

### Example: Adding an Unmapped Ingredient

**Unmapped:** `"Isomalto-Oligosaccharides": 20`

1. Research what it is → It's a prebiotic fiber (IMO)
2. Determine which database → `other_ingredients.json` (it's an inactive ingredient)
3. Add entry:

```json
{
  "id": "NHA_IMO",
  "standard_name": "Isomalto-Oligosaccharides",
  "aliases": [
    "isomalto-oligosaccharides",
    "IMO",
    "isomaltooligosaccharides",
    "isomalto-oligosaccharide"
  ],
  "risk_level": "none",
  "category": "fiber_prebiotic",
  "clean_label_score": 8,
  "notes": "Prebiotic fiber, may cause digestive issues in sensitive individuals",
  "last_updated": "2025-12-08"
}
```

4. Re-run cleaning → 20 products now show this as mapped

---

## Running the Pipeline

### Full Pipeline Run

```bash
# From scripts/ directory

# Step 1: Clean
python clean_dsld_data.py --input-dir /path/to/raw/dsld --output-dir output_ProductType

# Step 2: Enrich
python enrich_supplements_v3.py --input-dir output_ProductType/cleaned --output-dir output_ProductType

# Step 3: Score
python score_supplements.py --input-dir output_ProductType/enriched --output-dir output_ProductType
```

### Check Unmapped After Cleaning

```bash
cat output_ProductType/unmapped/unmapped_inactive_ingredients.json | python -m json.tool
```

### Dry Run (Test Without Writing)

```bash
python clean_dsld_data.py --dry-run
python enrich_supplements_v3.py --dry-run
```

---

## Config Files Summary

| File | Purpose |
|------|---------|
| `config/cleaning_config.json` | Paths, normalization rules, validation settings |
| `config/enrichment_config.json` | Database paths, matching rules, feature flags |
| `config/scoring_config.json` | Point allocations, section weights, thresholds |

---

## Key Concepts

### Hierarchy Classification
Prevents double-scoring of related ingredients:
- **Source:** Fish Oil, Krill Oil → Skip (just the carrier)
- **Summary:** Total Omega-3, Omega-3 Fatty Acids → Skip (just a label)
- **Component:** EPA, DHA → Score these!

### Quality Forms
Same ingredient has different quality levels:
- Vitamin D3 (Cholecalciferol) → Score 9 (best)
- Vitamin D2 (Ergocalciferol) → Score 5 (lower absorption)

### Bioavailability Tiers
Enhanced delivery systems boost scores:
- Tier 1: Liposomal, Phytosome (+8 points)
- Tier 2: Micronized, Chelated (+5 points)
- Tier 3: Standard forms (+0 points)

---

## Quick Reference

| Stage | Input | Output | Key Database Files |
|-------|-------|--------|-------------------|
| Clean | Raw DSLD | cleaned/*.json + unmapped/*.json | ingredient_quality_map, other_ingredients, harmful_additives |
| Enrich | cleaned/*.json | enriched/*.json | All 18 databases |
| Score | enriched/*.json | scored/*.json | scoring_config.json |

---

*Last Updated: 2025-12-08*
*Pipeline Version: 3.0*
