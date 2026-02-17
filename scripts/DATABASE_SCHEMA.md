# DATABASE_SCHEMA.md — Master Schema Reference

> Schema version: **4.0.0** | Last updated: 2026-02-16 | 29 database files

## Metadata Contract

Every database file MUST include a `_metadata` object as its first key:

```json
{
  "_metadata": {
    "description": "Human-readable description",
    "purpose": "machine_readable_purpose_tag",
    "schema_version": "4.0.0",
    "last_updated": "YYYY-MM-DD",
    "total_entries": <int|null>,
    "version": "<semver>",
    "data_source": "<string|null>"
  }
}
```

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `description` | YES | string | Human-readable file description |
| `purpose` | YES | string | Machine-readable purpose tag (see Purpose Tags below) |
| `schema_version` | YES | string | Always `"4.0.0"` |
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
| `blend_penalty_scoring` | proprietary_blends_penalty.json | Enrichment |
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
**Purpose:** `allergen_flagging` | **Entries:** 32

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
**Purpose:** `evidence_scoring` | **Entries:** 137

Primary key: `backed_clinical_studies` (array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Unique ID (e.g., `CS_VITAMIN_D`) |
| `standard_name` | string | YES | Canonical ingredient name |
| `aliases` | string[] | YES | Alternative names |
| `category` | string | YES | Ingredient category |
| `evidence_level` | string | YES | Evidence strength: `strong`, `moderate`, `emerging` |
| `evidence_tier` | string | YES | Tier: `tier_1`, `tier_2`, `tier_3` |
| `tier_points` | float | YES | Points awarded per tier |
| `study_type` | string | YES | Study design type |
| `published_studies` | int | YES | Number of published studies |
| `score_contribution` | float | YES | Base score contribution |
| `key_endpoints` | string[] | YES | Primary measured outcomes |
| `health_goals_supported` | string[] | YES | Mapped health goals |
| `notable_studies` | string | NO | Key study citations |
| `notes` | string | NO | Additional context |
| `last_updated` | string | NO | ISO date |

---

### 4. banned_match_allowlist.json
**Purpose:** `match_override` | **Version:** 1.0.0

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
**Purpose:** `safety_disqualification_and_regulatory_compliance` | **Entries:** 140

Primary key: `ingredients` (array)

Core fields (always present):

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique ID with prefix: `BANNED_`, `SPIKE_`, `RISK_`, `STATE_` |
| `standard_name` | string | Canonical substance name |
| `aliases` | string[] | Alternative names and synonyms |
| `category` | string | Substance category |
| `severity_level` | string | `critical`, `high`, `moderate`, `low` |
| `legal_status_enum` | string | `banned_federal`, `banned_state`, `controlled_substance`, `restricted`, `not_lawful_as_supplement` |
| `clinical_risk_enum` | string | `lethal_risk`, `organ_damage`, `cardiovascular_event`, `endocrine_disruption`, `moderate_adverse`, `low_risk_high_dose` |
| `jurisdictions` | object[] | Jurisdiction-specific rules |
| `supersedes_ids` | string[]/null | IDs this entry replaced |
| `match_rules` | object | Matching configuration |

---

### 6. botanical_ingredients.json
**Purpose:** `ingredient_mapping` | **Entries:** 237

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
**Purpose:** `claims_scoring`

Primary keys: `config` (object), `rules` (object)

`rules` sub-keys: `third_party_programs`, `gmp_certifications`, `organic_certifications`, `allergen_free_claims`, `batch_traceability`, `quality_markers`

Each rule entry contains pattern-matching criteria and scoring weights for claim detection.

---

### 8. clinically_relevant_strains.json
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

### 9. color_indicators.json
**Purpose:** `scoring_classification`

Primary keys (all string arrays):
- `natural_indicators` (66): Terms indicating natural color source
- `artificial_indicators` (39): Terms indicating artificial color
- `explicit_natural_dyes` (74): Known natural dye names
- `explicit_artificial_dyes` (78): Known artificial dye names

---

### 10. enhanced_delivery.json
**Purpose:** `bonus_scoring` | **Entries:** 78

Structure: Object keyed by delivery system name (e.g., `liposomal`, `chelated`, `enteric-coated`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tier` | int | YES | Quality tier (1=highest, 4=lowest) |
| `description` | string | YES | What this delivery system does |
| `category` | string | YES | Delivery category |

---

### 11. functional_ingredient_groupings.json
**Purpose:** transparency scoring

Primary keys: `functional_groupings` (array), `vague_terms_to_flag` (array), `transparency_bonuses` (array)

Used to detect and penalize vague supplement labeling (e.g., "proprietary blend") while rewarding transparent disclosures.

---

### 12. harmful_additives.json
**Purpose:** `penalty_scoring` | **Entries:** 71

Primary key: `harmful_additives` (array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Unique ID (e.g., `HA_TITANIUM_DIOXIDE`) |
| `standard_name` | string | YES | Canonical name |
| `aliases` | string[] | YES | Alternative names |
| `category` | string | YES | Additive category |
| `severity_level` | string | YES | `critical`, `high`, `moderate`, `low` |
| `severity_score` | float | YES | Numeric severity (0-10) |
| `mechanism_of_harm` | string | YES | How it causes harm |
| `regulatory_status` | string | YES | Current regulatory status |
| `match_rules` | object | YES | Matching configuration |

---

### 13. id_redirects.json
**Purpose:** `id_redirect` | **Entries:** 38 | **Version:** 2.0.0

Primary keys: `redirects` (array), `lookup` (object)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `deprecated_id` | string | YES | Old ID being redirected |
| `canonical_id` | string | YES | Current canonical ID |
| `reason` | string | YES | Why the redirect exists |

`lookup` provides O(1) access: `deprecated_id → canonical_id`

ID prefix categories: `ADD_` (additives), `SPIKE_` (adulterants), `STATE_` (state-level bans)

---

### 14. ingredient_classification.json
**Purpose:** `ingredient_classification` | **Version:** 1.0.0

Primary keys: `settings` (object), `skip_exact` (string array), `classifications` (object)

Used to classify ingredients as active vs inactive. `skip_exact` contains 20 terms to skip during classification.

---

### 15. ingredient_quality_map.json
**Purpose:** `quality_scoring` | **449 ingredient entries**

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
| `bio_score` | float | YES | Bioavailability score (1-10) |
| `natural` | bool | YES | Natural vs synthetic |
| `absorption` | string | YES | Absorption characteristic |
| `notes` | string | NO | Form-specific notes |
| `aliases` | string[] | YES | Form aliases for matching |
| `dosage_importance` | float | NO | Weight for scoring |

---

### 16. ingredient_weights.json
**Purpose:** `dosing_categories` | **Version:** 1.0.0

Primary keys: `category_weights`, `dosage_weights`, `ingredient_priorities`

Defines weight categories for 10 ingredient classes, 4 dosage tiers, and 3 priority levels.

---

### 17. manufacture_deduction_expl.json
**Purpose:** `manufacturer_deduction_explanation` | **Version:** 2.0

Primary keys: `total_deduction_cap`, `violation_categories`, `modifiers`, `calculation_rules`, `score_thresholds`

Documents the manufacturer penalty calculation framework. `total_deduction_cap` = -25 points maximum.

---

### 18. manufacturer_violations.json
**Purpose:** `manufacturer_penalties` | **Entries:** 49

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

### 19. migration_report.json
**Purpose:** `migration_audit`

Documents schema migration history. Contains counts, alias collision resolutions, relationship additions, and category normalizations applied during the v2→v4 migration.

---

### 20. other_ingredients.json
**Purpose:** `inactive_ingredient_classification` | **Entries:** 254

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

### 21. proprietary_blends_penalty.json
**Purpose:** `blend_penalty_scoring` | **Entries:** 18

Primary key: `proprietary_blend_concerns` (array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Unique ID |
| `standard_name` | string | YES | Concern name |
| `red_flag_terms` | string[] | YES | Detection patterns |
| `severity_level` | string | YES | Severity classification |
| `penalties` | object | YES | Scoring penalties |
| `penalty_levels` | object | NO | Tiered penalties |

---

### 22. rda_optimal_uls.json
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

### 23. rda_therapeutic_dosing.json
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

### 24. standardized_botanicals.json
**Purpose:** `ingredient_mapping_and_standardization` | **Entries:** 244

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

### 25. synergy_cluster.json
**Purpose:** `synergy_bonuses` | **Entries:** 54

Primary key: `synergy_clusters` (array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Unique ID (e.g., `SYN_CALCIUM_VD`) |
| `standard_name` | string | YES | Cluster name |
| `ingredients` | string[] | YES | Required ingredient set |
| `min_effective_doses` | object | NO | Minimum doses per ingredient |
| `evidence_tier` | string | YES | Evidence strength |
| `synergy_mechanism` | string | YES | How synergy works |

---

### 26. top_manufacturers_data.json
**Purpose:** `manufacturer_quality` | **Entries:** 61

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

### 27. unit_conversions.json
**Purpose:** `dosing_normalization` | **Version:** 1.0.0

Primary keys: `vitamin_conversions`, `mass_conversions`, `probiotic_conversions`, `form_detection_patterns`

Defines conversion factors for IU→mcg, mg→g, CFU→billion, and vitamin-specific conversions (D3, E, A, K, folate, etc.).

---

### 28. unit_mappings.json
**Purpose:** `unit_mapping` | **Entries:** 14

Structure: Object keyed by supplement type (e.g., `Vitamin D3`, `Omega-3 Fish Oil`, `Magnesium`)

Each entry maps dosage forms (capsule, softgel, tablet, powder) to `{amount, unit, notes}`.

---

### 29. user_goals_to_clusters.json
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
| `BANNED_` | banned_recalled_ingredients | `BANNED_SIBUTRAMINE` |
| `BANNED_ADD_` | banned_recalled_ingredients (additives) | `BANNED_ADD_BHA` |
| `SPIKE_` | banned_recalled_ingredients (adulterants) | `SPIKE_SILDENAFIL` |
| `STATE_` | banned_recalled_ingredients (state bans) | `STATE_DELTA8_THC` |
| `RISK_` | banned_recalled_ingredients (risk items) | `RISK_KRATOM_NATURAL` |
| `HA_` | harmful_additives | `HA_TITANIUM_DIOXIDE` |
| `OI_` | other_ingredients | `OI_GELATIN` |
| `CS_` | backed_clinical_studies | `CS_VITAMIN_D` |
| `ABS_` | absorption_enhancers | `ABS_PIPERINE` |
| `ALLERGEN_` | allergens | `ALLERGEN_MILK` |
| `BOT_` | botanical_ingredients | `BOT_ECHINACEA` |
| `SYN_` | synergy_cluster | `SYN_CALCIUM_VD` |
| `STRAIN_` | clinically_relevant_strains | `STRAIN_LGG` |
| `RDA_` | rda_optimal_uls | `RDA_VITAMIN_D` |
| `ADD_` | id_redirects (deprecated) | `ADD_BHA` → `BANNED_ADD_BHA` |

---

## Cross-File Relationships

```
ingredient_quality_map.json (449 ingredients)
  ├── forms[].aliases → enhanced_normalizer alias lookup
  ├── standard_name → enrichment ingredient matching
  └── category → supplement type classification

clinically_relevant_strains.json (42 strains)
  ├── aliases → enhanced_normalizer strain bypass
  └── evidence_level → scoring probiotic bonus

banned_recalled_ingredients.json (140)
  ├── supersedes_ids → id_redirects.json
  ├── aliases → enrichment banned matching
  └── match_rules → banned_match_allowlist.json

standardized_botanicals.json (244)
  └── markers → enrichment A5b standardized botanical bonus

synergy_cluster.json (54)
  ├── ingredients → enrichment synergy detection
  └── ← user_goals_to_clusters.json

rda_optimal_uls.json (47)
  └── data → scoring dosing validation

manufacturer_violations.json (49)
  └── manufacturer_id → enrichment manufacturer matching

top_manufacturers_data.json (61)
  └── aliases → enrichment manufacturer matching
```
