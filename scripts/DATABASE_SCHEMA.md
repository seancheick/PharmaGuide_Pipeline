# DATABASE_SCHEMA.md — Master Schema Reference

> Schema version: **5.0.0 / 5.1.0** | Last updated: 2026-03-22 | 33 database files

## Metadata Contract

Every database file MUST include a `_metadata` object as its first key:

```json
{
  "_metadata": {
    "description": "Human-readable description",
    "purpose": "machine_readable_purpose_tag",
    "schema_version": "5.0.0",
    "last_updated": "YYYY-MM-DD",
    "total_entries": "<int|null>",
    "version": "<semver>",
    "data_source": "<string|null>"
  }
}
```

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `description` | YES | string | Human-readable file description |
| `purpose` | YES | string | Machine-readable purpose tag (see Purpose Tags below) |
| `schema_version` | YES | string | Always `"5.0.0"` (or `"5.1.0"` for clinical files) |
| `last_updated` | YES | string | ISO date `YYYY-MM-DD` |
| `total_entries` | NO | int/null | Count of primary data entries |
| `version` | NO | string | File-level semver (e.g., `"2.1.0"`) |
| `data_source` | NO | string/null | Attribution for external data |

---

## Numeric Type Policy

- Unless a field is explicitly marked otherwise, numeric fields accept both `int` and `float`.
- Validation treats `10` and `10.0` as equivalent numeric values.
- Nullability rules still apply exactly as documented per field (for example `null` vs numeric with status companions).

---

## Purpose Tags

| Tag | File(s) | Pipeline Stage |
|-----|---------|----------------|
| `quality_scoring` | ingredient_quality_map.json | Cleaning, Scoring |
| `ingredient_mapping` | botanical_ingredients.json | Cleaning |
| `ingredient_mapping_and_standardization` | standardized_botanicals.json | Cleaning, Enrichment |
| `inactive_ingredient_classification` | other_ingredients.json | Cleaning |
| `scoring_classification` | color_indicators.json | Cleaning |
| `ingredient_classification` | ingredient_classification.json | Cleaning |
| `allergen_flagging` | allergens.json | Enrichment |
| `safety_disqualification_and_regulatory_compliance` | banned_recalled_ingredients.json | Enrichment |
| `penalty_scoring` | harmful_additives.json | Enrichment |
| `match_override` | banned_match_allowlist.json | Enrichment |
| `evidence_scoring` | backed_clinical_studies.json | Enrichment |
| `probiotic_strain_validation` | clinically_relevant_strains.json | Cleaning, Enrichment |
| `bioavailability_bonuses` | absorption_enhancers.json | Enrichment |
| `bonus_scoring` | enhanced_delivery.json | Enrichment |
| `synergy_bonuses` | synergy_cluster.json | Enrichment |
| `blend_detection` | proprietary_blends.json | Enrichment |
| `dosing_validation` | rda_optimal_uls.json | Enrichment, Scoring |
| `dosing_categories` | ingredient_weights.json | Enrichment |
| `dosing_normalization` | unit_conversions.json | Enrichment |
| `unit_mapping` | unit_mappings.json | Enrichment |
| `manufacturer_quality` | top_manufacturers_data.json | Enrichment |
| `manufacturer_penalties` | manufacturer_violations.json | Enrichment, Scoring |
| `manufacturer_deduction_explanation` | manufacture_deduction_expl.json | Scoring |
| `claims_scoring` | cert_claim_rules.json | Enrichment |
| `goal_mapping` | user_goals_to_clusters.json | Enrichment |
| `id_redirect` | id_redirects.json | Enrichment |
| `clinical_risk_taxonomy` | clinical_risk_taxonomy.json | Enrichment, Export |
| `interaction_rules` | ingredient_interaction_rules.json | Enrichment, Export |
| `cross_db_overlap_guard` | cross_db_overlap_allowlist.json | Enrichment |
| `percentile_categories` | percentile_categories.json | Scoring |
| `migration_audit` | migration_report.json | Internal |

---

## File-by-File Schema

### 1. absorption_enhancers.json
**Purpose:** `bioavailability_bonuses` | **Entries:** 23

Primary key: `absorption_enhancers` (array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Unique ID (e.g., `ABS_PIPERINE`) |
| `standard_name` | string | YES | Canonical name |
| `aliases` | string[] | YES | Alternative names |
| `category` | string | YES | Functional category |
| `enhances` | string[] | YES | Nutrients this enhances |
| `mechanism` | string | YES | How it works |
| `typical_dose` | string | YES | Typical dosage |
| `boost_factor` | float | YES | Bioavailability multiplier |
| `score_contribution` | float | YES | Scoring impact |

---

### 2. allergens.json
**Purpose:** `allergen_flagging` | **Entries:** 17

Primary key: `allergens` (array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Unique ID (e.g., `ALLERGEN_MILK`) |
| `standard_name` | string | YES | Canonical allergen name |
| `aliases` | string[] | YES | Detection terms |
| `prevalence` | string | YES | Population prevalence level |
| `severity_level` | string | YES | Clinical severity |
| `regulatory_status` | string | YES | Regulatory classification |
| `supplement_context` | string | YES | Relevance to supplements |
| `category` | string | YES | Allergen category |
| `general_handling` | string | YES | Handling guidelines |
| `notes` | string | NO | Additional context |
| `last_updated` | string | NO | ISO date |

---

### 3. backed_clinical_studies.json
**Purpose:** `evidence_scoring` | **Entries:** 177

Primary key: `backed_clinical_studies` (array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Unique ID (e.g., `CS_VITAMIN_D`) |
| `standard_name` | string | YES | Canonical ingredient name |
| `aliases` | string[] | YES | Alternative names |
| `category` | string | YES | Ingredient category |
| `evidence_level` | string | YES | Evidence class: `ingredient-human`, `branded-rct`, `product-human`, `strain-clinical`, `preclinical` |
| `study_type` | string | YES | Study design type |
| `published_studies` | string[] | YES | Evidence mix tags such as `RCT`, `meta-analysis`, `systematic_review`, `brand` |
| `score_contribution` | string | YES | Scoring tier label such as `tier_1`, `tier_2`, `tier_3` |
| `key_endpoints` | string[] | YES | Primary measured outcomes |
| `health_goals_supported` | string[] | YES | Mapped health goals |
| `notable_studies` | string | NO | Key study citations |
| `references_structured` | object[] | NO | PubMed-backed structured citations with PMID, DOI, publication types, MeSH terms, and verification metadata. Curated non-PubMed references are also allowed for nutrient fact sheets or formulary/regulatory records when PubMed is not the right anchor |
| `notes` | string | NO | Additional context |
| `last_updated` | string | NO | ISO date |
| `exclude_aliases` | string[] | NO | Explicitly denied aliases for matching safety |

Clinical evidence notes:
- `references_structured` is the normalized evidence layer. PubMed is the default evidence source, but curated non-PubMed refs are allowed when a nutrient, formulary, or regulatory source is the correct anchor.
- `study_type` should use repo-native buckets such as `rct_single`, `rct_multiple`, `systematic_review_meta`, `observational`, `clinical_strain`, `animal_study`, and `in_vitro`.

---

### 4. banned_match_allowlist.json
**Purpose:** `match_override` | **Entries:** 5

Primary keys: `allowlist` (array), `denylist` (array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Unique rule ID |
| `canonical_id` | string | YES | Banned DB canonical ID |
| `canonical_term` | string | YES | Human-readable banned term |
| `match_policy` | string | YES | `allow_exact` or `deny_fuzzy` |
| `variants` | string[] | allowlist only | Allowed variant terms |
| `pattern` | string | denylist only | Regex pattern to deny |
| `notes` | string | YES | Justification |
| `created_at` | string | YES | ISO date |
| `updated_at` | string | YES | ISO date |

---

### 5. banned_recalled_ingredients.json
**Purpose:** `safety_disqualification_and_regulatory_compliance` | **Entries:** 139 | **Schema:** 5.0.0

Primary key: `ingredients` (array)

B0 safety gate — runs first in scoring. Status determines outcome:

| Status | Outcome | Penalty |
|--------|---------|---------|
| `banned` (90) | PRODUCT FAIL (`UNSAFE`) | Disqualified |
| `recalled` (12) | PRODUCT FAIL (`BLOCKED`) | Disqualified |
| `high_risk` (26) | `CAUTION` | -10 pts |
| `watchlist` (11) | `CAUTION` | -5 pts |

Core fields (always present):

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique ID with prefix: `BANNED_`, `SPIKE_`, `RISK_`, `HM_`, `RECALLED_` |
| `standard_name` | string | Canonical substance name |
| `aliases` | string[] | Alternative names and synonyms |
| `cui` | string/null | UMLS Concept Unique Identifier (re-added 2026-03-22, populated via API) |
| `status` | string | `banned`, `recalled`, `high_risk`, `watchlist` |
| `legal_status_enum` | string | `banned_federal`, `banned_state`, `controlled_substance`, `restricted`, `not_lawful_as_supplement`, `adulterant`, `contaminant_risk`, `high_risk` |
| `clinical_risk_enum` | string | `critical`, `high`, `moderate`, `low`, `dose_dependent` |
| `jurisdictions` | object[] | Jurisdiction-specific rules |
| `match_rules` | object | Matching configuration (includes `negative_match_terms`) |
| `reason` | string | Why this ingredient is banned/recalled (shown to user) |
| `review` | object | Governance metadata |

---

### 6. botanical_ingredients.json
**Purpose:** `ingredient_mapping` | **Entries:** 428

Primary key: `botanical_ingredients` (array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Unique ID (e.g., `BOT_ECHINACEA`) |
| `standard_name` | string | YES | Canonical botanical name |
| `aliases` | string[] | YES | Common names, Latin names |
| `category` | string | YES | `herb`, `botanical`, `mushroom`, etc. |
| `notes` | string | NO | Context |
| `last_updated` | string | NO | ISO date |

---

### 7. cert_claim_rules.json
**Purpose:** `claims_scoring` | **Entries:** 45

Primary keys: `config` (object), `rules` (object)

`rules` sub-keys: `third_party_programs`, `gmp_certifications`, `organic_certifications`, `allergen_free_claims`, `batch_traceability`, `quality_markers`

Each rule entry contains pattern-matching criteria and scoring weights for claim detection.

---

### 8. clinical_risk_taxonomy.json
**Purpose:** `clinical_risk_taxonomy` | **Entries:** 36 | **Schema:** 5.1.0

Controlled enums for the interaction rule system:

| Key | Count | Values |
|-----|-------|--------|
| `conditions` | 14 | `pregnancy`, `lactation`, `ttc`, `surgery_scheduled`, `hypertension`, `heart_disease`, `diabetes`, `bleeding_disorders`, `kidney_disease`, `liver_disease`, `thyroid_disorder`, `autoimmune`, `seizure_disorder`, `high_cholesterol` |
| `drug_classes` | 9 | `anticoagulants`, `antiplatelets`, `nsaids`, `antihypertensives`, `hypoglycemics`, `thyroid_medications`, `sedatives`, `immunosuppressants`, `statins` |
| `severity_levels` | 5 | `contraindicated`, `avoid`, `caution`, `monitor`, `info` |
| `evidence_levels` | 4 | `established`, `probable`, `theoretical`, `insufficient` |

Each condition and drug class includes `id`, `label`, `description`, `app_category`, and `sort_order`.

---

### 9. clinically_relevant_strains.json
**Purpose:** `probiotic_strain_validation` | **Entries:** 42 | **Version:** 2.1.0

Primary keys: `clinically_relevant_strains` (array), `prebiotics` (object)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Unique ID (e.g., `STRAIN_LGG`) |
| `standard_name` | string | YES | Full strain name with designation |
| `aliases` | string[] | YES | Alternative names, ATCC numbers |
| `evidence_level` | string | YES | `high`, `moderate`, `emerging` |
| `key_benefits` | string[] | YES | Clinical benefit areas |
| `notable_studies` | string | NO | Key research citations |

---

### 10. color_indicators.json
**Purpose:** `scoring_classification` | **Entries:** 66

Primary keys (all string arrays):
- `natural_indicators` (66): Terms indicating natural color source
- `artificial_indicators` (39): Terms indicating artificial color
- `explicit_natural_dyes` (74): Known natural dye names
- `explicit_artificial_dyes` (78): Known artificial dye names

---

### 11. cross_db_overlap_allowlist.json
**Purpose:** `cross_db_overlap_guard` | **Entries:** 23

Allowlist for ingredients that legitimately appear in multiple databases (e.g., an ingredient in both IQM and botanical_ingredients). Prevents false-positive overlap warnings during enrichment.

---

### 12. enhanced_delivery.json
**Purpose:** `bonus_scoring` | **Entries:** 78

Structure: Object keyed by delivery system name (e.g., `liposomal`, `chelated`, `enteric-coated`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tier` | int | YES | Quality tier (1=highest, 4=lowest) |
| `description` | string | YES | What this delivery system does |
| `category` | string | YES | Delivery category |

---

### 13. functional_ingredient_groupings.json
**Purpose:** transparency scoring | **Entries:** 8

Primary keys: `functional_groupings` (array), `vague_terms_to_flag` (array), `transparency_bonuses` (array)

Used to detect and penalize vague supplement labeling (e.g., "proprietary blend") while rewarding transparent disclosures.

---

### 14. harmful_additives.json
**Purpose:** `penalty_scoring` | **Entries:** 107 | **Schema:** 5.1.0

Primary key: `harmful_additives` (array)

B1 graduated penalty scoring — cumulative deductions:

| Severity | B1 Penalty | Count | Examples |
|----------|-----------|-------|----------|
| `high` (18) | -2.0 pts | 18 | Trans fats, IARC 2A/2B carcinogens, heavy metals |
| `moderate` (46) | -1.0 pt | 46 | Artificial sweeteners, synthetic colorants, emulsifiers |
| `low` (43) | -0.5 pts | 43 | GRAS excipients, flow agents, natural thickeners |

No `critical` tier — substances posing immediate hazards belong in `banned_recalled_ingredients.json` (B0 gate).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Unique ID with `ADD_` prefix |
| `standard_name` | string | YES | Canonical name |
| `aliases` | string[] | YES | E-numbers, CAS, IUPAC, brand names |
| `cui` | string/null | YES | UMLS Concept Unique Identifier |
| `category` | string | YES | One of 20 values (see below) |
| `severity_level` | string | YES | `high`, `moderate`, `low` |
| `mechanism_of_harm` | string | YES | Biochemical/toxicological pathway |
| `regulatory_status` | object | YES | `{US, EU}` with CFR/EFSA citations and ADI values |
| `population_warnings` | string[] | NO | At-risk populations |
| `notes` | string | NO | Consumer-readable summary |
| `scientific_references` | string[] | NO | DOIs and citations |
| `match_rules` | object | YES | `match_mode`, `fuzzy_threshold`, `case_sensitive`, `preferred_alias` |
| `references_structured` | object[] | YES | Structured citations with `evidence_grade` |
| `external_ids` | object | NO | `{cas, pubchem_cid}` — present only when non-null |
| `jurisdictional_statuses` | object[] | NO | Per-jurisdiction status codes |
| `review` | object | YES | Governance metadata with `change_log` |
| `confidence` | string | YES | `high`, `medium`, `low` |
| `dose_thresholds` | object/null | NO | ADI/TDI with value, unit, source |

Category enum (20 values): `colorant`, `colorant_artificial`, `colorant_natural`, `contaminant`, `emulsifier`, `excipient`, `fat_oil`, `filler`, `flavor`, `mineral_compound`, `nutrient_synthetic`, `phosphate`, `preservative`, `preservative_antioxidant`, `processing_aid`, `stimulant_laxative`, `sweetener`, `sweetener_artificial`, `sweetener_natural`, `sweetener_sugar_alcohol`

**Removed in v5.1:** `CUI` (top-level duplicate), `label_tokens`, `regex`, `exposure_context`, `entity_type` (when "ingredient"), `class_tags`, `severity_score`, `critical` severity tier.

---

### 15. id_redirects.json
**Purpose:** `id_redirect` | **Entries:** 16

Primary keys: `redirects` (array), `lookup` (object)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `deprecated_id` | string | YES | Old ID being redirected |
| `canonical_id` | string | YES | Current canonical ID |
| `reason` | string | YES | Why the redirect exists |

`lookup` provides O(1) access: `deprecated_id → canonical_id`

---

### 16. ingredient_classification.json
**Purpose:** `ingredient_classification` | **Entries:** 34

Primary keys: `settings` (object), `skip_exact` (string array), `classifications` (object)

Used to classify ingredients as active vs inactive.

---

### 17. ingredient_interaction_rules.json
**Purpose:** `interaction_rules` | **Entries:** 45 | **Schema:** 5.1.0

Primary key: `interaction_rules` (array)

Each rule is keyed by `subject_ref: {db, canonical_id}` linking to one of the 5 ingredient databases.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Rule ID (e.g., `RULE_INGREDIENT_CAFFEINE`) |
| `subject_ref` | object | YES | `{db, canonical_id}` — ingredient identity |
| `condition_rules` | object[] | NO | Per-condition interaction details |
| `drug_class_rules` | object[] | NO | Per-drug-class interaction details |
| `dose_thresholds` | object[] | NO | Dose-dependent severity escalation |
| `pregnancy_lactation` | object/null | NO | Pregnancy/lactation specific data |
| `form_scope` | string/null | NO | Form-specific rule (e.g., "preformed" for vitamin A) |
| `last_reviewed` | string | YES | ISO date |
| `review_owner` | string | YES | Reviewer identity |

Supported `subject_ref.db` values: `ingredient_quality_map`, `other_ingredients`, `harmful_additives`, `banned_recalled_ingredients`, `botanical_ingredients`

---

### 18. ingredient_quality_map.json
**Purpose:** `quality_scoring` | **549 ingredient parents** | **~550 total entries**

Structure: Object keyed by ingredient slug (e.g., `vitamin_a`, `omega_3`, `ashwagandha`)

Each ingredient entry:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `standard_name` | string | YES | Canonical display name |
| `category` | string | YES | `vitamin`, `mineral`, `botanical`, `amino_acid`, `fatty_acid`, etc. |
| `cui` | string | NO | UMLS CUI identifier |
| `rxcui` | string | NO | RxNorm identifier |
| `forms` | object | YES | Keyed by form name |
| `match_rules` | object | YES | Priority, match_mode, exclusions |
| `category_enum` | string | NO | Standardized category |
| `data_quality` | object | NO | Completeness tracking |

Each **form** within `forms`:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `score` | float | YES | Quality score (1-18 scale) |
| `bio_score` | float | YES | Bioavailability score (1-15) |
| `natural` | bool | YES | Natural vs synthetic |
| `absorption` | string | YES | Absorption characteristic |
| `notes` | string | NO | Form-specific notes |
| `aliases` | string[] | YES | Form aliases for matching |
| `dosage_importance` | float | NO | Weight for scoring |

---

### 19. ingredient_weights.json
**Purpose:** `dosing_categories` | **Entries:** 4

Primary keys: `category_weights`, `dosage_weights`, `ingredient_priorities`

Defines weight categories for ingredient classes, dosage tiers, and priority levels.

---

### 20. manufacture_deduction_expl.json
**Purpose:** `manufacturer_deduction_explanation` | **Entries:** 5

Primary keys: `total_deduction_cap`, `violation_categories`, `modifiers`, `calculation_rules`, `score_thresholds`

Documents the manufacturer penalty calculation framework. `total_deduction_cap` = -25 points maximum.

---

### 21. manufacturer_violations.json
**Purpose:** `manufacturer_penalties` | **Entries:** 66

Primary key: `manufacturer_violations` (array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Unique violation ID |
| `manufacturer` | string | YES | Company name |
| `manufacturer_id` | string | YES | Canonical manufacturer ID |
| `violation_type` | string | YES | Violation category |
| `severity_level` | string | YES | `critical`, `high`, `moderate`, `low` |
| `base_deduction` | float | YES | Points deducted |
| `date` | string | YES | Violation date |
| `is_resolved` | bool | YES | Resolution status |
| `fda_action` | string | YES | FDA enforcement action |

---

### 22. migration_report.json
**Purpose:** `migration_audit` | **Entries:** 38

Documents schema migration history. Contains counts, alias collision resolutions, relationship additions, and category normalizations applied during schema migrations.

---

### 23. other_ingredients.json
**Purpose:** `inactive_ingredient_classification` | **Entries:** 656

Primary key: `other_ingredients` (array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Unique ID (e.g., `OI_GELATIN`) |
| `standard_name` | string | YES | Canonical name |
| `aliases` | string[] | YES | Alternative names |
| `category` | string | YES | `filler`, `binder`, `coating`, `sweetener`, etc. |
| `additive_type` | string | YES | Additive classification |
| `clean_label_score` | float | YES | Clean label quality (0-10) |
| `is_additive` | bool | YES | Whether it's an additive |
| `severity_level` | string | NO | Concern level |
| `allergen_flag` | bool | NO | Allergen warning needed |

---

### 24. percentile_categories.json
**Purpose:** `percentile_categories`

Defines product category assignments for percentile ranking. Used by the scorer to group products into cohorts for relative scoring.

---

### 25. proprietary_blends.json
**Purpose:** `blend_detection` | **Entries:** 14

Primary key: `proprietary_blend_concerns` (array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Unique ID |
| `standard_name` | string | YES | Concern name |
| `blend_terms` | string[] | YES | Detection patterns |
| `risk_factors` | object | YES | Risk classification and mapping |
| `notes` | string | NO | Additional context |

---

### 26. rda_optimal_uls.json
**Purpose:** `dosing_validation` | **Entries:** 47

Primary key: `nutrient_recommendations` (array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Unique ID (e.g., `RDA_VITAMIN_D`) |
| `standard_name` | string | YES | Nutrient name |
| `unit` | string | YES | Canonical dosing unit |
| `optimal_range` | object | YES | Min/max optimal range |
| `highest_ul` | float/null | YES | Upper tolerable limit |
| `data` | object | YES | Age/sex-specific RDA values |
| `warnings` | string[] | NO | Dosing warnings |

---

### 27. rda_therapeutic_dosing.json
**Purpose:** non-RDA dosing | **Entries:** 44

Primary key: `therapeutic_dosing` (array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Unique ID |
| `standard_name` | string | YES | Ingredient name |
| `aliases` | string[] | YES | Alternative names |
| `unit` | string | YES | Dosing unit |
| `typical_dosing_range` | object | YES | Min/max therapeutic range |
| `common_serving_size` | string | YES | Typical serving |
| `upper_limit` | float/null | YES | Safety ceiling |
| `evidence_tier` | string | YES | Evidence strength |

---

### 28. standardized_botanicals.json
**Purpose:** `ingredient_mapping_and_standardization` | **Entries:** 239

Primary key: `standardized_botanicals` (array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Unique ID |
| `standard_name` | string | YES | Canonical botanical name |
| `aliases` | string[] | YES | Alternative names |
| `markers` | object[] | NO | Standardization markers |
| `min_threshold` | float | NO | Minimum marker % |
| `category` | string | NO | Botanical category |
| `priority` | int | NO | Matching priority |
| `standardization_type` | string | NO | Extract type |

---

### 29. synergy_cluster.json
**Purpose:** `synergy_bonuses` | **Entries:** 54

Primary key: `synergy_clusters` (array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Unique ID (e.g., `SYN_CALCIUM_VD`) |
| `standard_name` | string | YES | Cluster name |
| `ingredients` | string[] | YES | Required ingredient set |
| `min_effective_doses` | object | YES | Minimum doses per ingredient |
| `evidence_tier` | int | YES | Evidence strength tier (`1`, `2`, or `3`) |
| `synergy_mechanism` | string/null | NO | Mechanism summary |
| `note` | string | YES | User-facing explanation |
| `sources` | object[] | YES | Evidence links |

---

### 30. top_manufacturers_data.json
**Purpose:** `manufacturer_quality` | **Entries:** 77

Primary key: `top_manufacturers` (array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Unique ID |
| `standard_name` | string | YES | Manufacturer name |
| `aliases` | string[] | YES | Known brand aliases |
| `evidence` | object | YES | Quality certifications |
| `notes` | string | NO | Additional info |
| `last_updated` | string | NO | ISO date |

---

### 31. unit_conversions.json
**Purpose:** `dosing_normalization` | **Entries:** 20

Primary keys: `vitamin_conversions`, `mass_conversions`, `probiotic_conversions`, `form_detection_patterns`

Defines conversion factors for IU→mcg, mg→g, CFU→billion, and vitamin-specific conversions.

---

### 32. unit_mappings.json
**Purpose:** `unit_mapping` | **Entries:** 14

Structure: Object keyed by supplement type (e.g., `Vitamin D3`, `Omega-3 Fish Oil`, `Magnesium`)

Each entry maps dosage forms (capsule, softgel, tablet, powder) to `{amount, unit, notes}`.

---

### 33. user_goals_to_clusters.json
**Purpose:** `goal_mapping` | **Entries:** 16

Primary key: `user_goal_mappings` (array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Unique ID |
| `user_facing_goal` | string | YES | Goal displayed to user |
| `primary_clusters` | string[] | YES | Main synergy cluster IDs |
| `secondary_clusters` | string[] | YES | Supporting cluster IDs |

---

## ID Prefix Conventions

| Prefix | Database | Example |
|--------|----------|---------|
| `ADD_` | harmful_additives | `ADD_ASPARTAME`, `ADD_BHA` |
| `BANNED_` | banned_recalled_ingredients | `BANNED_SIBUTRAMINE` |
| `BANNED_ADD_` | banned_recalled_ingredients (additives) | `BANNED_ADD_FORMALDEHYDE` |
| `HM_` | banned_recalled_ingredients (heavy metals) | `HM_CHROMIUM_HEXAVALENT` |
| `SPIKE_` | banned_recalled_ingredients (adulterants) | `SPIKE_SILDENAFIL` |
| `RECALLED_` | banned_recalled_ingredients (products) | `RECALLED_OXYELITE_PRO` |
| `RISK_` | banned_recalled_ingredients (risk items) | `RISK_KRATOM_NATURAL` |
| `ADULTERANT_` | banned_recalled_ingredients (pharma adulterants) | `ADULTERANT_MELOXICAM` |
| `OI_` | other_ingredients | `OI_GELATIN` |
| `CS_` | backed_clinical_studies | `CS_VITAMIN_D` |
| `ABS_` | absorption_enhancers | `ABS_PIPERINE` |
| `ALLERGEN_` | allergens | `ALLERGEN_MILK` |
| `BOT_` | botanical_ingredients | `BOT_ECHINACEA` |
| `SYN_` | synergy_cluster | `SYN_CALCIUM_VD` |
| `STRAIN_` | clinically_relevant_strains | `STRAIN_LGG` |
| `RDA_` | rda_optimal_uls | `RDA_VITAMIN_D` |
| `RULE_` | ingredient_interaction_rules | `RULE_INGREDIENT_CAFFEINE` |

---

## Cross-File Relationships

```
ingredient_quality_map.json (549 parents)
  ├── forms[].aliases → enhanced_normalizer alias lookup
  ├── standard_name → enrichment ingredient matching
  ├── category → supplement type classification
  └── canonical_id → ingredient_interaction_rules.json subject_ref

clinical_risk_taxonomy.json (14 conditions, 9 drug classes)
  └── enum definitions → ingredient_interaction_rules.json validation

ingredient_interaction_rules.json (45 rules)
  ├── subject_ref.canonical_id → IQM / botanical / banned / harmful / other
  ├── condition_rules[].condition_id → clinical_risk_taxonomy.conditions
  ├── drug_class_rules[].drug_class_id → clinical_risk_taxonomy.drug_classes
  └── dose_thresholds → enrichment dose evaluation

clinically_relevant_strains.json (42 strains)
  ├── aliases → enhanced_normalizer strain bypass
  └── evidence_level → scoring probiotic bonus

banned_recalled_ingredients.json (139)
  ├── supersedes_ids → id_redirects.json
  ├── aliases → enrichment banned matching
  └── match_rules → banned_match_allowlist.json

standardized_botanicals.json (239)
  └── markers → enrichment standardized botanical bonus

synergy_cluster.json (54)
  ├── ingredients → enrichment synergy detection
  └── ← user_goals_to_clusters.json

rda_optimal_uls.json (47)
  └── data → scoring dosing validation

manufacturer_violations.json (66)
  └── manufacturer_id → enrichment manufacturer matching

top_manufacturers_data.json (77)
  └── aliases → enrichment manufacturer matching
```
