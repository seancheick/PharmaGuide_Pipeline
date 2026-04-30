# DATABASE_SCHEMA.md — Master Schema Reference

> Reference data schema: **5.0.0 / 5.1.0 / 5.2.0 / 5.3.0 / 6.0.0** | Export schema: **v1.4.0 (91 columns)** | Last updated: 2026-04-25 | 39 database files
>
> ## Two schemas, one document
>
> This file covers two related but distinct schemas:
>
> 1. **Reference data files** (`scripts/data/*.json`) — version 5.0.0 / 5.1.0 / 5.2.0 / 5.3.0 / 6.0.0. These are the input data the enricher consumes.
> 2. **Final DB export** (`pharmaguide_core.db` + `detail_blobs/*.json`) — version 1.4.0. This is what the mobile app consumes. Runtime source of truth: `CORE_COLUMN_COUNT` and `EXPORT_SCHEMA_VERSION` in `build_final_db.py`. Per-column contract: `FINAL_EXPORT_SCHEMA_V1.md`.
>
> The reference data schema drives what the enricher CAN compute. The export schema drives what the mobile app CAN query. They evolve independently.
>
> ## Export schema version summary
>
> - **v1.3.1** added `net_contents_quantity` (REAL) and `net_contents_unit` (TEXT) for the refill-reminder feature, and fixed the `serving_info` phantom-key bug that left `dosing_summary` and `servings_per_container` empty for every product.
> - **v1.3.2** added `calories_per_serving` (REAL) as a filter column and introduced the `nutrition_detail` and `unmapped_actives` subkeys in `detail_blobs/*.json`. (90 columns)
> - **v1.3.3** expanded interaction safety: 129 rules (was 98), 4 new drug classes, context-aware harmful scoring, 25 PMID fixes, IQM expanded to 588 entries. (90 columns)
> - **v1.3.4** added CAERS B8 penalty scoring (159 adverse event signals), offline UNII cache (172K substances), IQM UNII standardization (66%), drug label interaction mining. (90 columns)
> - **v1.4.0** added `image_thumbnail_url` TEXT column and `normalize_upc` field; image upload pipeline. (91 columns)
> - Total column count: **91**. Runtime source of truth: `CORE_COLUMN_COUNT = 91` in `build_final_db.py`. Flutter `products_core_table.dart` in the mobile repo is synced one-for-one. Supabase Postgres needs no migration because `products_core` is in the SQLite storage blob, not in Postgres.

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
| `adverse_event_signals` | caers_adverse_event_signals.json | Scoring (B8) |
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
| `drug_class_definitions` | drug_classes.json | Enrichment, Export |
| `cross_db_overlap_guard` | cross_db_overlap_allowlist.json | Enrichment |
| `percentile_categories` | percentile_categories.json | Scoring |
| `unii_lookup_cache` | fda_unii_cache.json | Enrichment |
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
**Purpose:** `evidence_scoring` | **Entries:** 197

Primary key: `backed_clinical_studies` (array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Unique ID. Prefix: `INGR_` (ingredient-human), `BRAND_` (branded-rct), `PRECLIN_` (preclinical) |
| `standard_name` | string | YES | Canonical ingredient name |
| `aliases` | string[] | YES | Alternative names for matching |
| `category` | string | YES | IQM category enum (vitamins, minerals, herbs, amino_acids, probiotics, etc.) |
| `evidence_level` | string | YES | Evidence class: `ingredient-human`, `branded-rct`, `product-human`, `strain-clinical`, `preclinical` |
| `study_type` | string | YES | Study design: `systematic_review_meta`, `rct_multiple`, `rct_single`, `clinical_strain`, `observational`, `animal_study`, `in_vitro` |
| `published_studies` | string[] | YES | Human-readable evidence mix tags (e.g. `["RCT"]`, `["systematic review", "meta-analysis"]`) |
| `published_studies_count` | int | NO | Numeric study-count field used for scoring depth bonus when a trustworthy count is available |
| `published_rct_count` | int | NO | Curated count of published randomized human trials when known |
| `published_meta_review_count` | int | NO | Curated count of published systematic reviews / meta-analyses when known |
| `registry_completed_trials_count` | int | NO | ClinicalTrials.gov completed-trial count captured by discovery/enrichment tooling |
| `score_contribution` | string | YES | Scoring tier: `tier_1` (≥3.0 pts), `tier_2` (≥1.5 pts), `tier_3` (<1.5 pts) |
| `key_endpoints` | string[] | YES | Primary measured outcomes with PMID citations (e.g., `"Reduced LDL by 15% (PMID: 12345678)"`) |
| `health_goals_supported` | string[] | YES | Mapped health goals |
| `primary_outcome` | string | NO | Primary health outcome category |
| `endpoint_relevance_tags` | string[] | NO | Coarse operator-facing endpoint tags derived from trial outcome text or curated manually |
| `effect_direction` | string | YES | 5-tier classification: `positive_strong`, `positive_weak`, `mixed`, `null`, `negative` |
| `effect_direction_confidence` | string | NO | Auditability label for effect-direction certainty (`high`, `medium`, `low`) |
| `effect_direction_rationale` | string | NO | Short evidence rationale supporting the current `effect_direction` classification |
| `total_enrollment` | int | NO | Largest trial enrollment from ClinicalTrials.gov |
| `notable_studies` | string | NO | Key study citations with NCT IDs and enrollment |
| `references_structured` | object[] | NO | PubMed-backed structured citations with PMID, DOI, publication types, MeSH terms, and verification metadata. Also accepts ClinicalTrials.gov and ChEMBL references |
| `notes` | string | NO | Clinical context — auto-populated for discovered entries, manually curated for legacy |
| `last_updated` | string | NO | ISO date |
| `exclude_aliases` | string[] | NO | Explicitly denied aliases for matching safety |

Clinical evidence notes:
- All 197 entries have PMID-backed `key_endpoints` — no empty endpoints remain.
- `references_structured` supports three reference types: `clinical_trial` (NCT ID), `pubmed` (PMID/DOI), and `chembl` (ChEMBL ID + max_phase).
- `effect_direction` is classified for all entries: 128 positive_strong, 40 positive_weak, 25 mixed, 4 null.
- `published_studies_count` is the dedicated numeric field for Section C depth bonus. Entries without a reliable count omit it; scoring does not infer counts from the human-readable `published_studies` tags.
- `registry_completed_trials_count` is discovery/enrichment metadata, not a substitute for published study counts. Keep it separate from `published_studies_count`.
- `effect_direction_rationale`, `effect_direction_confidence`, and `endpoint_relevance_tags` are auditability fields. They improve reviewability and operator trust; they are not direct scoring inputs in the current model.
- Auto-discovery (`discover_clinical_evidence.py discover --apply`) now auto-populates `key_endpoints` from ClinicalTrials.gov primary outcome measures with PubMed PMID cross-references via E-utilities.
- `study_type` should use repo-native buckets: `rct_single`, `rct_multiple`, `systematic_review_meta`, `observational`, `clinical_strain`, `animal_study`, `in_vitro`.
- `score_contribution` tier is computed from `study_base_points(study_type) * evidence_multiplier(evidence_level)`: tier_1 ≥ 3.0, tier_2 ≥ 1.5, tier_3 < 1.5.

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
**Purpose:** `safety_disqualification_and_regulatory_compliance` | **Entries:** 143 | **Schema:** 5.0.0

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
**Purpose:** `ingredient_mapping` | **Entries:** 459 | **Schema:** 5.1.0

Primary key: `botanical_ingredients` (array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Unique ID (e.g., `BOT_ECHINACEA`) |
| `standard_name` | string | YES | Canonical botanical name |
| `aliases` | string[] | YES | Common names, Latin names |
| `category` | string | YES | `herb`, `botanical`, `mushroom`, etc. |
| `notes` | string | NO | Context |
| `last_updated` | string | NO | ISO date |
| `functional_roles` | string[] | NO (added v5.1.0) | Multi-valued role IDs from `functional_roles_vocab.json` v1.0.0 — most botanicals are actives (no role assigned), but some serve as colorants (turmeric), flavorings, or carriers in formulation context. Per-entry assignment in Phase 3 backfill. |

---

### 7. cert_claim_rules.json
**Purpose:** `claims_scoring` | **Entries:** 58

Primary keys: `config` (object), `rules` (object)

`rules` sub-keys: `third_party_programs`, `gmp_certifications`, `organic_certifications`, `allergen_free_claims`, `batch_traceability`, `quality_markers`

Each rule entry contains pattern-matching criteria and scoring weights for claim detection.

---

### 8. clinical_risk_taxonomy.json
**Purpose:** `clinical_risk_taxonomy` | **Entries:** 41 | **Schema:** 5.1.0

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
**Purpose:** `cross_db_overlap_guard` | **Entries:** 31

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

### 13b. functional_roles_vocab.json
**Purpose:** `display_vocabulary` | **Entries:** 32 | **Schema:** 1.0.0 (LOCKED, clinician-signed 2026-04-30)

Primary key: `functional_roles` (array)

Controlled vocabulary of excipient/inactive-ingredient functional roles for the Flutter app's tap-to-learn UI. Single source of truth for the `functional_roles[]` field across `harmful_additives.json`, `other_ingredients.json`, and `botanical_ingredients.json`. Display-only — **no scoring impact in V1**.

Lean schema, 5 fields per role:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Stable snake_case ID — used as the value in entries' `functional_roles[]` arrays |
| `name` | string | YES | User-facing chip label (e.g. `"Lubricant"`, `"pH Regulator"`) |
| `notes` | string ≤200 char | YES | Plain-English description shown in tap modal |
| `regulatory_references` | object[] | YES | `[{jurisdiction, code}]` — tappable "Learn more" links to FDA CFR / EU E-numbers |
| `examples` | string[] | YES | 1-5 ingredient names users might recognize on labels |

Locked roles (32) by category:
- **Tablet/capsule mechanics (5):** binder, disintegrant, lubricant, glidant, coating
- **Bulk (1):** filler
- **Texture/structure (6):** emulsifier, surfactant, thickener, stabilizer, gelling_agent, humectant
- **Preservation (2):** preservative, antioxidant
- **Sensory (5):** colorant_natural, colorant_artificial, flavor_natural, flavor_artificial, flavor_enhancer
- **Sweeteners (3):** sweetener_natural, sweetener_artificial, sweetener_sugar_alcohol
- **Manufacturing aids (4):** anti_caking_agent, anti_foaming_agent, processing_aid, solvent
- **Delivery/chemistry (5):** carrier_oil, acidulant, ph_regulator, propellant, glazing_agent
- **Fiber/gut health (1):** prebiotic_fiber

**Distribution to Flutter:** vocab ships as a bundled asset in the Flutter app (`assets/data/functional_roles_vocab.json`) — **NOT embedded per-blob**. Saves ~6 KB × millions of blobs. Vocab updates ship via app release. Aligned with FDA 21 CFR 170.3(o)(1-32) + EU E-numbers + FAO/JECFA INS classes.

Adding/removing roles requires a new clinician sign-off cycle and is gated by `tests/test_functional_roles_vocab_contract.py`.

---

### 14. harmful_additives.json
**Purpose:** `penalty_scoring` | **Entries:** 115 | **Schema:** 5.2.0

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
| `functional_roles` | string[] | NO (added v5.2.0) | Multi-valued role IDs from `functional_roles_vocab.json` v1.0.0. Display-only — surfaced to Flutter inactive_ingredients[]. May be empty in V1; populated incrementally per `scripts/audits/functional_roles/batch_NN/`. **Contaminants do NOT receive functional_roles** — they are unintended impurities, not functional ingredients. |

Category enum (20 values): `colorant`, `colorant_artificial`, `colorant_natural`, `contaminant`, `emulsifier`, `excipient`, `fat_oil`, `filler`, `flavor`, `mineral_compound`, `nutrient_synthetic`, `phosphate`, `preservative`, `preservative_antioxidant`, `processing_aid`, `stimulant_laxative`, `sweetener`, `sweetener_artificial`, `sweetener_natural`, `sweetener_sugar_alcohol`

**Removed in v5.1:** `CUI` (top-level duplicate), `label_tokens`, `regex`, `exposure_context`, `entity_type` (when "ingredient"), `class_tags`, `severity_score`, `critical` severity tier.

**Added in v5.2 (2026-04-30):** `functional_roles[]` field. **Phase 4 cleanup (after backfill batches):** the 20-value `category` enum will collapse to ~12 canonical values (artificial_color → colorant_artificial, fat_oil → carrier_oil context, preservative_antioxidant split into both functional_roles), and entries `Senna`, `Synthetic B Vitamins`, `Cupric Sulfate` will move to the active-ingredient pipeline per clinician decision.

---

### 14b. caers_adverse_event_signals.json
**Purpose:** `adverse_event_signals` | **Schema:** 1.0.0 | **Source:** FDA CAERS bulk download

Primary key: `signals` (object keyed by IQM canonical_id)

B8 graduated penalty scoring — FDA pharmacovigilance data (real-world adverse event reports):

| Signal Strength | B8 Penalty | Threshold | Examples |
|----------------|-----------|-----------|----------|
| `strong` | -4.0 pts | >=100 serious reports | kratom (759 serious, 261 deaths), green tea extract (186 serious) |
| `moderate` | -2.0 pts | 25-99 serious reports | turmeric, ashwagandha, garcinia |
| `weak` | -1.0 pt | 10-24 serious reports | elderberry, boswellia |

Cap: 5.0 pts max per product. Multi-ingredient products (multivitamins, combos) are excluded during ingestion to prevent base-rate inflation.

**Distinct from harmful_additives.json** (B1 = formulation quality of excipients) and **banned_recalled_ingredients.json** (B0 = regulatory actions). CAERS = statistical volume of real-world adverse events on active ingredients.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `canonical_id` | string | YES | IQM canonical ingredient ID |
| `total_reports` | integer | YES | Total CAERS reports mentioning this ingredient |
| `serious_reports` | integer | YES | Reports with serious outcomes (hospitalization, death, ER, etc.) |
| `outcomes` | object | YES | Breakdown: `hospitalization`, `er_visit`, `life_threatening`, `death`, `disability`, `required_intervention` |
| `top_reactions` | string[] | YES | Top 10 MedDRA reaction terms |
| `signal_strength` | string | YES | `strong`, `moderate`, `weak` (minimal excluded) |
| `year_range` | string | YES | Date range of reports (e.g. "2008-2025") |

Ingestion: `scripts/api_audit/ingest_caers.py` — downloads FDA CAERS bulk data, filters to dietary supplements (industry_code 54), extracts ingredient names, matches to IQM canonical_ids, aggregates signals.

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
**Purpose:** `interaction_rules` | **Entries:** 129 | **Schema:** 5.1.0

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
**Purpose:** `quality_scoring` | **588 ingredient parents** | **588 total entries**

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
**Purpose:** `manufacturer_penalties` | **Entries:** 67

Primary key: `manufacturer_violations` (array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Unique violation ID |
| `manufacturer` | string | YES | Company name |
| `manufacturer_id` | string | YES | Canonical manufacturer ID |
| `manufacturer_family_id` | string | NO | Curated score-bearing manufacturer family ID used for repeat-violation grouping when explicitly present |
| `manufacturer_family_name` | string | NO | Human-readable family label for curated manufacturer families |
| `manufacturer_family_aliases` | string[] | NO | Optional curated aliases that describe the manufacturer family |
| `related_brand_cluster_id` | string | NO | Non-scoring related brand/product cluster ID for operator review and explainability |
| `related_brand_cluster_name` | string | NO | Human-readable label for the non-scoring related cluster |
| `related_brand_cluster_aliases` | string[] | NO | Optional aliases for the related brand/product cluster |
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
**Purpose:** `inactive_ingredient_classification` | **Entries:** 673 | **Schema:** 5.1.0

Primary key: `other_ingredients` (array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Unique ID (e.g., `OI_GELATIN`) |
| `standard_name` | string | YES | Canonical name |
| `aliases` | string[] | YES | Alternative names |
| `category` | string | YES | Will collapse to ~30 canonical values in Phase 4 cleanup (currently 241 distinct, of which 132 appear only once). |
| `additive_type` | string | DEPRECATED | **Slated for removal in Phase 4** — replaced by `functional_roles[]`. 226 distinct un-standardized values; do not add new values going forward. |
| `clean_label_score` | float | YES | Clean label quality (0-10) |
| `is_additive` | bool | YES | Whether it's an additive |
| `severity_level` | string | NO | Concern level |
| `allergen_flag` | bool | NO | Allergen warning needed |
| `functional_roles` | string[] | NO (added v5.1.0) | Multi-valued role IDs from `functional_roles_vocab.json` v1.0.0. Display-only — surfaced to Flutter `inactive_ingredients[]` via `build_final_db.py`. May be empty in V1; populated incrementally per `scripts/audits/functional_roles/batch_NN/`. **Concentration-aware in some cases:** ethanol → `["solvent","preservative"]` at ≥14-20% v/v vs `["solvent"]` at residual; activated carbon → default `["processing_aid"]`, add `colorant_natural` only when product clearly uses as black pigment. Per-entry verification (no auto-defaulting) for TiO2 and pearlescent mineral colorants. |

**Phase 4 cleanup (clinician-locked, after backfill batches):**
- `additive_type` field dropped entirely (was redundant with `category`; multi-role expression handled by `functional_roles[]`)
- 5 descriptor categories retired (~50 entries): `marketing_descriptor`, `descriptor_component`, `source_descriptor`, `phytochemical_marker`, `label_descriptor`
- Move-to-actives: `botanical_extract` (14), `animal_glandular_tissue` (10), `glandular_tissue` (4), `amino_acid_derivative` (7), branded complexes (~27), Black Pepper Extract
- New `is_branded_complex: bool` flag (V1.1) replaces `branded_botanical_complex` / `branded_complex` categories
- 132 single-occurrence categories decomposed via mechanical concatenation rule (e.g. `binder_coating_thickener` → `["binder","coating","thickener"]`) with 10% clinician spot-check per batch

---

### 24. percentile_categories.json
**Purpose:** `percentile_categories`

Defines product category assignments for percentile ranking. Used by the scorer to group products into cohorts for relative scoring.

---

### 25. proprietary_blends.json
**Purpose:** `blend_detection` | **Entries:** 19

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
**Purpose:** `synergy_bonuses` | **Entries:** 58

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
**Purpose:** `goal_mapping` | **Entries:** 18

Primary key: `user_goal_mappings` (array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | YES | Unique ID |
| `user_facing_goal` | string | YES | Goal displayed to user |
| `primary_clusters` | string[] | YES | Main synergy cluster IDs |
| `secondary_clusters` | string[] | YES | Supporting cluster IDs |

---

### 34. drug_classes.json
**Purpose:** `drug_class_definitions` | **Entries:** 28 | **Schema:** 1.0.0

Primary key: `drug_classes` (array)

Canonical drug class definitions used by `ingredient_interaction_rules.json` and the Flutter interaction layer. Each entry defines a drug class ID, label, description, and example drugs.

---

### 35. fda_unii_cache.json
**Purpose:** `unii_lookup_cache` | **Substances:** 172,431 | **Schema:** 1.0.0 | **Source:** FDA OpenFDA UNII bulk download

Structure: Object keyed by UNII code (e.g., `"GAN16C9B8O"`)

Offline cache of the FDA UNII substance registry. Enables enrichment to resolve ingredient identities without live API calls. Managed by `scripts/unii_cache.py`.

| Field | Description |
|-------|-------------|
| `unii` | FDA Unique Ingredient Identifier |
| `pt` | Preferred term (canonical substance name) |
| `rn` | CAS Registry Number (when available) |
| `inchikey` | InChI key for chemical identity (when available) |

Updated from `https://download.open.fda.gov/other/unii/other-unii-0001-of-0001.json.zip`.

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
ingredient_quality_map.json (610 parents)
  ├── forms[].aliases → enhanced_normalizer alias lookup
  ├── standard_name → enrichment ingredient matching
  ├── category → supplement type classification
  └── canonical_id → ingredient_interaction_rules.json subject_ref

clinical_risk_taxonomy.json (41 entries: 14 conditions, 9 drug classes, severity/evidence enums)
  └── enum definitions → ingredient_interaction_rules.json validation

ingredient_interaction_rules.json (129 rules)
  ├── subject_ref.canonical_id → IQM / botanical / banned / harmful / other
  ├── condition_rules[].condition_id → clinical_risk_taxonomy.conditions
  ├── drug_class_rules[].drug_class_id → clinical_risk_taxonomy.drug_classes
  └── dose_thresholds → enrichment dose evaluation

clinically_relevant_strains.json (42 strains)
  ├── aliases → enhanced_normalizer strain bypass
  └── evidence_level → scoring probiotic bonus

banned_recalled_ingredients.json (143)
  ├── supersedes_ids → id_redirects.json
  ├── aliases → enrichment banned matching
  └── match_rules → banned_match_allowlist.json

standardized_botanicals.json (239)
  └── markers → enrichment standardized botanical bonus

synergy_cluster.json (58)
  ├── ingredients → enrichment synergy detection
  └── ← user_goals_to_clusters.json

rda_optimal_uls.json (47)
  └── data → scoring dosing validation

manufacturer_violations.json (67)
  └── manufacturer_id → enrichment manufacturer matching
  └── manufacturer_family_id → repeat-violation grouping in sync/recalculation
  └── related_brand_cluster_id → non-scoring operator/explainability metadata

top_manufacturers_data.json (77)
  └── aliases → enrichment manufacturer matching

caers_adverse_event_signals.json
  └── canonical_id → scoring B8 penalty lookup (per active ingredient)

fda_unii_cache.json (172K substances)
  └── unii lookup → enrichment identity resolution (offline, via unii_cache.py)
```
