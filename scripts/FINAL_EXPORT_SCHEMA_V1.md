# FINAL EXPORT SCHEMA V1

> Version: 1.2.0 — 2026-03-18
> Consumes: scoring v3.1.0, enrichment v3.1.0, data schema v5.1.0
> Status: FROZEN — approved by team review
> Updated: interaction_summary, dose_threshold_evaluation, condition/drug_class mapping, 45 interaction rules

## Purpose

This document defines the exact contract between the pipeline (this repo) and the
PharmaGuide Flutter app. The pipeline produces a SQLite database and per-product
detail blobs. The app consumes them.

This contract is frozen. Field renames after the app ships are expensive.

Assumptions:
- Omega-3 dose adequacy is folded into ingredient quality in pipeline scoring.
- User personalization (`score_fit_20`) is computed locally on the phone.
- V1 does not claim true product-level recall support; only ingredient-level
  recalled/banned safety logic is exported.

---

## Architecture

```
Pipeline repo (dsld-clean)
  └── build_final_db.py
        ├── pharmaguide_core.db       ← ships to phone / downloadable artifact
        │     ├── products_core       ← one row per product
        │     ├── products_fts        ← full-text search
        │     ├── reference_data      ← small rule tables for offline scoring
        │     └── export_manifest     ← version/checksum metadata
        ├── detail_blobs/             ← one JSON per product, uploaded to Supabase
        │     ├── 15123.json
        │     ├── 37323.json
        │     └── ...
        ├── export_manifest.json      ← top-level manifest for Supabase
        └── export_audit_report.json  ← safety-category counts and per-build audit
```

On the phone, the app adds local-only tables:
- `product_detail_cache` — cached detail JSON (plain TEXT in v1)
- `user_profile`
- `user_favorites`
- `user_scan_history`
- `user_stacks` / `stack_products`

---

## Table: `products_core`

```sql
CREATE TABLE products_core (
    dsld_id                       TEXT PRIMARY KEY,
    product_name                  TEXT NOT NULL,
    brand_name                    TEXT,
    upc_sku                       TEXT,
    image_url                     TEXT,    -- remote source URL; not guaranteed offline
    thumbnail_key                 TEXT,    -- optional runtime/cache key, not a device path

    product_status                TEXT,    -- active, discontinued, off_market
    discontinued_date             TEXT,    -- ISO-8601
    form_factor                   TEXT,    -- tablet, capsule, powder, gummy, liquid, etc.
    supplement_type               TEXT,    -- e.g. single_nutrient, targeted, specialty, probiotic

    score_quality_80              REAL,    -- canonical pipeline score
    score_display_80              TEXT,    -- e.g. "71.1/80"
    score_display_100_equivalent  TEXT,    -- e.g. "88.8/100"
    score_100_equivalent          REAL,    -- display convenience only; derived from quality_80
    grade                         TEXT,    -- Exceptional, Excellent, Good, Fair, Below Avg, Low, Very Poor
    verdict                       TEXT,    -- SAFE, CAUTION, POOR, UNSAFE, BLOCKED, NOT_SCORED
    safety_verdict                TEXT,    -- backward-compatible safety label
    mapped_coverage               REAL,

    score_ingredient_quality      REAL,    -- max 25
    score_ingredient_quality_max  REAL,
    score_safety_purity           REAL,    -- max 30
    score_safety_purity_max       REAL,
    score_evidence_research       REAL,    -- max 20
    score_evidence_research_max   REAL,
    score_brand_trust             REAL,    -- max 5
    score_brand_trust_max         REAL,

    percentile_rank               REAL,
    percentile_top_pct            REAL,
    percentile_category           TEXT,
    percentile_label              TEXT,
    percentile_cohort             INTEGER,

    is_gluten_free                INTEGER DEFAULT 0,
    is_dairy_free                 INTEGER DEFAULT 0,
    is_soy_free                   INTEGER DEFAULT 0,
    is_vegan                      INTEGER DEFAULT 0,
    is_vegetarian                 INTEGER DEFAULT 0,
    is_organic                    INTEGER DEFAULT 0,
    is_non_gmo                    INTEGER DEFAULT 0,   -- needs normalized enrichment export

    has_banned_substance          INTEGER DEFAULT 0,
    has_recalled_ingredient       INTEGER DEFAULT 0,   -- ingredient-level, not product recall
    has_harmful_additives         INTEGER DEFAULT 0,
    has_allergen_risks            INTEGER DEFAULT 0,
    blocking_reason               TEXT,                -- banned_ingredient, recalled_ingredient, etc.

    is_probiotic                  INTEGER DEFAULT 0,
    contains_sugar                INTEGER DEFAULT 0,
    contains_sodium               INTEGER DEFAULT 0,
    diabetes_friendly             INTEGER DEFAULT 0,   -- defaults to FALSE when data absent
    hypertension_friendly         INTEGER DEFAULT 0,   -- defaults to FALSE when data absent

    is_trusted_manufacturer       INTEGER DEFAULT 0,
    has_third_party_testing       INTEGER DEFAULT 0,
    has_full_disclosure           INTEGER DEFAULT 0,

    cert_programs                 TEXT,    -- JSON array
    badges                        TEXT,    -- JSON array
    top_warnings                  TEXT,    -- JSON array, max 5
    flags                         TEXT,    -- JSON array

    scoring_version               TEXT,
    output_schema_version         TEXT,
    enrichment_version            TEXT,
    scored_date                   TEXT,
    export_version                TEXT NOT NULL,
    exported_at                   TEXT NOT NULL
);

CREATE INDEX idx_products_core_upc ON products_core(upc_sku);
CREATE INDEX idx_products_core_name ON products_core(product_name);
CREATE INDEX idx_products_core_brand ON products_core(brand_name);
CREATE INDEX idx_products_core_verdict ON products_core(verdict);
CREATE INDEX idx_products_core_score ON products_core(score_quality_80);
CREATE INDEX idx_products_core_type ON products_core(supplement_type);
CREATE INDEX idx_products_core_status ON products_core(product_status);
```

### Column Sources

| Column | Source | Notes |
|---|---|---|
| `dsld_id` | `enriched.dsld_id` | |
| `product_name` | `enriched.product_name` | |
| `brand_name` | `enriched.brandName` | |
| `upc_sku` | `enriched.upcSku` | Barcode lookup |
| `image_url` | `enriched.imageUrl` | May be PDF, not a real image. Not offline. |
| `thumbnail_key` | NULL at export | Populated by app at runtime |
| `product_status` | `enriched.status` | DSLD lifecycle, NOT safety |
| `discontinued_date` | `enriched.discontinuedDate` | ISO date or NULL |
| `form_factor` | `enriched.form_factor` | |
| `supplement_type` | `enriched.supplement_type.type` | Current observed values include `single_nutrient`, `targeted`, `specialty`, `probiotic` |
| `score_quality_80` | `scored.score_80` | NULL if not scored |
| `score_display_80` | `scored.display` | Pre-formatted: "71.1/80" |
| `score_display_100_equivalent` | `scored.display_100` | Pre-formatted: "88.8/100" |
| `score_100_equivalent` | `scored.score_100_equivalent` | Display convenience |
| `grade` | `scored.grade` | |
| `verdict` | `scored.verdict` | SAFE/CAUTION/POOR/UNSAFE/BLOCKED/NOT_SCORED |
| `safety_verdict` | `scored.safety_verdict` | Backward-compat |
| `mapped_coverage` | `scored.mapped_coverage` | 0.0-1.0 |
| `score_ingredient_quality` | `scored.section_scores.A_ingredient_quality.score` | max 25 |
| `score_safety_purity` | `scored.section_scores.B_safety_purity.score` | max 30 |
| `score_evidence_research` | `scored.section_scores.C_evidence_research.score` | max 20 |
| `score_brand_trust` | `scored.section_scores.D_brand_trust.score` | max 5 |
| `has_banned_substance` | `contaminant_data.banned_substances.substances` | exact/alias match with `status == "banned"` only |
| `has_recalled_ingredient` | Same source, `status == "recalled"` | Ingredient recalled, NOT product |
| `blocking_reason` | Derived from exact/alias contaminant matches + verdict | Used for `CAUTION`/`UNSAFE`/`BLOCKED` safety explanation |
| `diabetes_friendly` | `enriched.dietary_sensitivity_data.diabetes_friendly` | Defaults to 0 (cautious) when absent |
| `hypertension_friendly` | `enriched.dietary_sensitivity_data.hypertension_friendly` | Defaults to 0 (cautious) when absent |
| `scoring_version` | `scored.scoring_metadata.scoring_version` | |
| `output_schema_version` | `scored.output_schema_version` | |
| `enrichment_version` | `enriched.enrichment_version` | |
| `export_version` | Build parameter | Semver TEXT, e.g. "1" |
| `exported_at` | Build timestamp | ISO-8601 |

### What Is NOT Stored

| Data | Reason |
|---|---|
| `score_fit_20` | Computed on-device per user |
| `score_combined_100` | Computed on-device per user |
| `off_market` | Redundant with `product_status` |
| Price / daily cost | User-entered |
| Product-level recall | No data source yet |
| Offline image data | Runtime concern |

---

## Table: `products_fts`

```sql
CREATE VIRTUAL TABLE products_fts USING fts5(
    product_name, brand_name,
    content='products_core', content_rowid='rowid',
    tokenize='porter unicode61'
);
```

---

## Table: `product_detail_cache` (app-side)

```sql
CREATE TABLE product_detail_cache (
    dsld_id          TEXT PRIMARY KEY,
    detail_json      TEXT NOT NULL,    -- plain JSON in v1
    cached_at        TEXT NOT NULL,
    source           TEXT NOT NULL,    -- bundled, preload, server
    detail_version   TEXT NOT NULL,    -- app stores the blob's blob_version here
    FOREIGN KEY (dsld_id) REFERENCES products_core(dsld_id)
);
```

---

## Table: `reference_data`

Small rule tables for offline Section F (user fit) scoring.

| Key | Source file | Size | Purpose |
|---|---|---|---|
| `rda_optimal_uls` | rda_optimal_uls.json | ~199KB | Dosage vs age/sex-specific RDA/UL |
| `interaction_rules` | ingredient_interaction_rules.json | ~75KB | Medical compatibility (45 rules, 14 conditions, 9 drug classes) |
| `clinical_risk_taxonomy` | clinical_risk_taxonomy.json | ~5KB | Severity classification (14 conditions incl. diabetes merged, high_cholesterol added) |
| `user_goals_clusters` | user_goals_to_clusters.json | ~11KB | Goal matching |

```sql
CREATE TABLE reference_data (
    key         TEXT PRIMARY KEY,
    version     TEXT NOT NULL,
    data        TEXT NOT NULL,    -- JSON
    updated_at  TEXT NOT NULL
);
```

---

## Table: `export_manifest`

```sql
CREATE TABLE export_manifest (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

Required rows:

| Key | Example value |
|---|---|
| `db_version` | `2026.03.17.1` |
| `pipeline_version` | `3.1.0` |
| `scoring_version` | `3.1.0` |
| `generated_at` | `2026-03-17T18:34:59Z` |
| `product_count` | `180423` |
| `checksum` | `sha256:abc123...` |
| `min_app_version` | `1.0.0` |
| `schema_version` | `1` |

---

## Detail Blob Contract

One JSON file per product, named `{dsld_id}.json`. Uploaded to Supabase.
Cached on-device in `product_detail_cache.detail_json` after first access.

### Structure

```json
{
  "dsld_id": "37323",
  "blob_version": 1,
  "ingredients": [...],
  "inactive_ingredients": [...],
  "warnings": [...],
  "score_bonuses": [...],
  "score_penalties": [...],
  "section_breakdown": {
    "ingredient_quality": {"score", "max", "sub": {..., "probiotic_breakdown": {...}}},
    "safety_purity": {"score", "max", "sub": {..., "B5_blend_evidence": [...]}},
    "evidence_research": {"score", "max", "matched_entries", "ingredient_points": {...}},
    "brand_trust": {"score", "max", "sub": {...}},
    "violation_penalty": 0.0
  },
  "compliance_detail": {...},
  "certification_detail": {...},
  "proprietary_blend_detail": {...},
  "dietary_sensitivity_detail": {...},
  "formulation_detail": {...},
  "serving_info": {...},
  "manufacturer_detail": {...},
  "probiotic_detail": {...},
  "synergy_detail": {...},
  "evidence_data": {...},
  "rda_ul_data": {...}
}
```

### Active ingredient entry

```json
{
  "raw_source_text": "Vitamin A Palmitate",
  "name": "Vitamin A Palmitate",
  "standardName": "Retinyl Palmitate",
  "normalized_key": "vitamin_a",
  "forms": [{"name": "Palmitate"}],
  "quantity": 2000.0,
  "unit": "IU",
  "standard_name": "Vitamin A",
  "form": "retinyl palmitate",
  "matched_form": "retinyl palmitate",
  "matched_forms": [...],
  "extracted_forms": [...],
  "category": "vitamins",
  "bio_score": 14,
  "natural": false,
  "score": 14,
  "notes": "The most common preformed Vitamin A in supplements...",
  "mapped": true,
  "safety_hits": [...],
  "normalized_amount": null,
  "normalized_unit": null,
  "role": "active",
  "parent_key": "vitamin_a",
  "dosage": 2000.0,
  "dosage_unit": "IU",
  "normalized_value": null,
  "is_mapped": true,
  "is_harmful": false,
  "harmful_severity": null,
  "harmful_notes": null,
  "is_banned": false,
  "is_allergen": false
}
```

### Inactive ingredient entry

```json
{
  "raw_source_text": "Soy Lecithin",
  "name": "Soy Lecithin",
  "standardName": "Soy Lecithin",
  "normalized_key": "soy_lecithin",
  "forms": [],
  "category": "emulsifier",
  "is_additive": true,
  "additive_type": "lecithin",
  "standard_name": "Soy Lecithin",
  "severity_level": "",
  "match_method": "",
  "matched_alias": "",
  "notes": "Natural emulsifier commonly used in supplements...",
  "mechanism_of_harm": "",
  "common_uses": ["emulsifier", "capsule ingredient"],
  "population_warnings": [],
  "is_harmful": false,
  "harmful_severity": null,
  "harmful_notes": null
}
```

### Warning entry

Each warning in the `warnings` array has a `type` field that determines which
additional fields are present:

```json
// banned_substance / recalled_ingredient / high_risk_ingredient / watchlist_substance
{
  "type": "banned_substance",
  "severity": "critical",
  "title": "Banned substance: DMAA",
  "detail": "FDA-banned stimulant with cardiovascular risks...",
  "source": "banned_recalled_ingredients",
  "date": "2026-01-09",
  "regulatory_date_label": "First FDA enforcement action",
  "clinical_risk": "critical"
}

// harmful_additive
{
  "type": "harmful_additive",
  "severity": "moderate",
  "title": "Contains Titanium Dioxide",
  "detail": "Nanoparticle concerns in gut epithelium...",
  "notes": "A white pigment used as an opacifier...",
  "mechanism_of_harm": "Nanoparticle concerns in gut epithelium...",
  "population_warnings": ["Children — immature gut barrier"],
  "category": "colorant",
  "source": "harmful_additives_db"
}

// allergen
{
  "type": "allergen",
  "severity": "moderate",
  "title": "Allergen: Soy & Soy Lecithin",
  "detail": "Presence: contains. Ingredient: soy lecithin",
  "notes": "Major allergen. Cross-reactivity with other legumes possible...",
  "supplement_context": "Common emulsifier/excipient and in protein products.",
  "prevalence": "high",
  "source": "allergen_db"
}

// interaction
{
  "type": "interaction",
  "severity": "avoid",
  "title": "Vitamin A / pregnancy",
  "detail": "Retinoid exposure risk during pregnancy.",
  "action": "Do not use preformed Vitamin A above 3000 mcg RAE in pregnancy.",
  "evidence_level": "established",
  "sources": ["https://ods.od.nih.gov/factsheets/VitaminA-HealthProfessional/"],
  "source": "interaction_rules"
}

// drug_interaction
{
  "type": "drug_interaction",
  "severity": "avoid",
  "title": "Vitamin A / retinoids",
  "detail": "Overlapping retinoid exposure.",
  "action": "Avoid use with retinoid medications.",
  "evidence_level": "established",
  "sources": ["https://ods.od.nih.gov/factsheets/VitaminA-HealthProfessional/"],
  "source": "interaction_rules"
}

// dietary
{
  "type": "dietary",
  "severity": "moderate",
  "title": "Diabetes",
  "detail": "Contains 5.0g sugar per serving.",
  "source": "dietary_sensitivity_data"
}

// status
{
  "type": "status",
  "severity": "info",
  "title": "Discontinued Product",
  "detail": "2025-12-31",
  "source": "dsld"
}
```

### Notes on detail blob
- Active ingredient `notes` come from IQM form notes. These are polished educational text.
- Inactive ingredient `notes` now come from `other_ingredients.json` reference data.
  `additive_type` and `common_uses` are reliable. If the ingredient matched
  `harmful_additives.json`, safety-specific `notes` and `mechanism_of_harm` take priority.
- `evidence_data` is included when enrichment produced clinical match output for the product.
- `rda_ul_data` is included when enrichment emitted an RDA/UL analysis block. It may still
  contain `collection_enabled: false` with a reason. When absent entirely, the app treats it
  as unavailable.
- `warnings` include banned/recalled/high-risk/watchlist ingredient hits, allergens, harmful
  additives, interaction warnings, drug interaction warnings, dietary warnings, and product
  status warnings. Each warning type carries specific provenance fields (see examples above).
- `score_bonuses` lists every positive scoring factor with label and score. The app can
  render these as a "What helped this score" section.
- `score_penalties` lists every negative scoring factor with per-item detail (which ingredient
  caused it, severity, reason). The app can render these as a "What hurt this score" section.
  Point values are included where available so the app can optionally show them later.
- `formulation_detail` carries the context behind A3/A4/A5 bonuses: delivery tier,
  absorption enhancers found, organic certification, standardized botanicals, synergy
  qualification, and non-GMO verification.
- `probiotic_detail` is present only for probiotic products. Includes strain composition,
  CFU data, clinical strain matches with evidence levels, prebiotic pairing, and survivability
  coating. The `probiotic_breakdown` in `section_breakdown.ingredient_quality.sub` carries
  the scoring sub-components (CFU, diversity, clinical strains, prebiotic, survivability).
- `synergy_detail` is present when synergy clusters were matched. Includes cluster names,
  matched ingredients with their doses and minimum effective dose thresholds, and
  qualification status.
- Plain JSON TEXT in v1. Switch to compressed BLOB later if needed.

---

## `top_warnings` Export Rule

Warnings selected at export time. Priority order, max 5 items:

1. Banned substance (`status == "banned"` + exact/alias match)
2. Recalled ingredient (`status == "recalled"` + exact/alias match)
3. Watchlist ingredient (`status == "watchlist"` + exact/alias match)
4. Allergen risks (from `allergen_hits`)
5. Harmful additives (from `harmful_additives`, highest severity first)
6. Interaction warnings (from `interaction_profile.ingredient_alerts`, highest severity first)
7. Dietary sensitivity (structured warnings first, sugar/sodium fallback)
8. Product status (discontinued, off-market)

Each warning is a short string for scan card display. Full explanations live in the detail blob.

---

## Runtime Flow

```
App Launch
  -> Open local SQLite
  -> Read export_manifest
  -> If online: check Supabase for newer version
  -> If newer: download delta or full artifact, apply in background
  -> Continue with local DB even if update fails

Barcode Scan
  -> Lookup upc_sku in products_core (local, instant)
  -> Render scan card from products_core
  -> Compute score_fit_20 locally from user_profile + reference_data
  -> On tap: load products_core top section instantly
  -> Check product_detail_cache
  -> If cached: render full detail instantly
  -> If not cached + online: fetch from Supabase -> cache -> render
  -> If not cached + offline: show core only, mark detail unavailable

Search
  -> Query local FTS index
  -> Return results instantly
  -> Open product from products_core
  -> Hydrate detail via cache/server as needed
```

---

## Build Tooling

### Single brand export
```bash
python3 scripts/build_final_db.py \
  --enriched-dir output_Thorne_enriched/enriched \
  --scored-dir output_Thorne_scored/scored \
  --output-dir /tmp/final_db
```

### Multi-brand auto-discovery
```bash
python3 scripts/build_all_final_dbs.py \
  --scan-dir scripts/ \
  --output-dir /tmp/final_db_all
```

### CI validation
```bash
pytest scripts/tests/test_export_gate.py -q --tb=short
# Check audit report for contract failures:
python3 -c "
import json
r = json.load(open('/tmp/final_db_all/export_audit_report.json'))
assert r['counts']['export_contract_invalid'] == 0
"
```

---

## V1 Gaps

| Gap | Status |
|---|---|
| `is_non_gmo` | Evidence exists in label text, needs normalized boolean extraction |
| Product-level recalls | Needs product/UPC-keyed FDA data source. Not faked in v1. |
| Offline images | `image_url` may be PDF. V1 uses placeholder + runtime cache. |
| `rda_ul_data` enforcement | Must decide: always collect, or treat as optional in detail blob |
