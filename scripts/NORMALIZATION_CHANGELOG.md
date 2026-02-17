# NORMALIZATION_CHANGELOG.md

Complete record of database normalization, pipeline alignment, and integrity improvements across Phases 2-5.

---

## Phase 2: Database Normalization & Schema Hardening

### Schema Version Upgrade (v2.x → v4.0.0)
- Unified all 29 database files to `schema_version: "4.0.0"`
- Standardized `_metadata` block: `description`, `purpose`, `schema_version`, `last_updated`
- Added `total_entries` counts to all files with primary data arrays
- Added `data_source` attribution where applicable

### ingredient_quality_map.json (v3.0.0)
- **449 ingredient entries** with comprehensive form coverage
- Added `match_rules` to every entry: `priority`, `match_mode`, `exclusions`, `parent_id`, `confidence`
- Added `category_enum` standardization
- Added `data_quality` tracking: `completeness`, `missing_fields`, `review_status`
- Added `absorption_structured` to forms with detailed bioavailability data
- Resolved 38 alias collisions via migration (see `migration_report.json`)
- Expanded alias coverage: 92% reduction in unmapped ingredients

### banned_recalled_ingredients.json (v3.0)
- **140 entries** with dual classification: `legal_status_enum` + `clinical_risk_enum`
- Added `jurisdictions[]` for jurisdiction-specific rules
- Added `supersedes_ids` for entry deduplication
- Deprecated `status`, `banned_date`, `banned_by` fields (mapped to authoritative fields)
- Added `match_rules` with `exclusions` for false-positive prevention
- Audit remediation (2026-02-17):
  - Corrected `BANNED_ADD_FORMALDEHYDE` `severity_level` from `moderate` to `critical` (backup had `risk_level: critical`).
  - Confirmed `BANNED_ADD_ALUMINUM_COMPOUNDS` was already corrected to `severity_level: high` during risk-level consolidation (backup `severity_level: low`, `risk_level: high`).

### harmful_additives.json
- **71 entries** with `match_rules` for context-aware matching
- Added `severity_score` (numeric 0-10) alongside `severity_level` (string)
- Added `references_structured` for citation tracking

### allergens.json
- **32 entries** with `supplement_context` field
- Added `general_handling` guidelines
- Clarified role: consumer warnings and on-device personalization, not score penalties

### other_ingredients.json
- **254 entries** for inactive ingredient classification
- Added `clean_label_score` (0-10 scale)
- Added `is_additive`, `allergen_flag` booleans

### clinically_relevant_strains.json (v2.1.0)
- **42 probiotic strains** with clinical evidence data
- Added DSLD label text aliases for K12 and M18 strains
- Added `evidence_level` and `key_benefits` for each strain

---

## Phase 3: Pipeline Script Alignment

### enhanced_normalizer.py
- Added probiotic strain bypass: `_build_strain_lookup()`, `_match_probiotic_strain()`
- Routes clinical strains directly before generic IQM alias lookup
- Two-pass matching: exact then longest-substring (min 6 chars)
- Imported `CLINICALLY_RELEVANT_STRAINS` path from constants

### enrich_supplements_v3.py (v3.1.0)
- Fixed supplement type classifier: probiotic detection BEFORE single_nutrient fast-path
- Added name-based probiotic detection using genus terms (lactobacillus, bifidobacterium, etc.)
- Fixed double-counting guard: name-based detection only for ingredients without probiotic/bacteria category
- 24 products correctly reclassified from `single_nutrient` → `probiotic`

### score_supplements.py
- Probiotic bonus chain now operational: `supp_type == "probiotic"` → CFU, diversity, prebiotic, clinical_strains, survivability sub-bonuses
- Section A includes probiotic_bonus (up to +10 points)

### constants.py
- Added `CLINICALLY_RELEVANT_STRAINS` path constant

### Test Suite
- **868 tests passing**, 0 failures
- Added `ALLOWED_CROSS_ALIASES` for legitimate cross-ingredient aliases
- Validated probiotic fix doesn't break existing regressions

---

## Phase 4: Pipeline Integrity & End-to-End Verification

### Identity Chain Verification
- Verified dsld_id preservation: raw → cleaned → enriched → scored
- 100% identity chain integrity across all 978 products

### Matching Accuracy Spot-Check
- Legacy raw-ingredient match metric: 99.97% (8,724/8,727 ingredients)
- Current scorable coverage metric: 99.77% (definition differs from raw-match metric)
- 0 low-confidence matches
- Probiotic chain status after remediation: 23/27 probiotic-candidate products receive positive probiotic bonus (4 remain valid edge cases with 0 bonus under current scoring rules)
- 180 inactive ingredients correctly routed to IQM instead of OI
- Proprietary blend sub-ingredients: 100% mapped

### Dry Run (Lozenges Corpus)
- 978 products processed through full pipeline
- Average quality: 42.28/80 (baseline before probiotic fix)
- Verdicts: SAFE 775, POOR 138, UNSAFE 6, CAUTION 58

---

## Phase 5: Documentation & Protection

### 5.6: Probiotic Strain Matching Fix

**Root Cause:** Three-part failure chain:
1. **Cleaning:** Generic IQM "probiotics" entry caught all strain aliases
2. **Enrichment:** `active_count == 1 → single_nutrient` bypassed probiotic detection
3. **Scoring:** `supp_type != "probiotic"` gated probiotic_bonus to 0.0

**Fix:**
- Probiotic strain bypass in `enhanced_normalizer.py` (clinically_relevant_strains.json lookup)
- Probiotic-first type classification in `enrich_supplements_v3.py`
- Double-counting guard for name-based detection

**Impact:**
- 24 products reclassified `single_nutrient` → `probiotic`
- Product 13946 (OralBiotic): probiotic_bonus 0.0 → 2.0
- 34 total probiotic products classified; 23/27 probiotic-candidate products receive positive probiotic bonus under current gate/feature settings

### id_redirects.json (v2.0.0)
- Expanded from 1 to **38 redirect entries**
- Extracted all `supersedes_ids` from banned_recalled_ingredients.json
- Categories: `ADD_` (34 additives), `SPIKE_` (1 adulterant), `STATE_` (3 state bans)
- Added `lookup` object for O(1) access
- Cross-validation with banned DB: all canonical_ids verified

### user_goals_to_clusters.json
- Fixed 16 empty-string IDs → proper `GOAL_` prefixed unique IDs
- Convention: `GOAL_UPPERCASE_SNAKE_CASE`

### DATABASE_SCHEMA.md
- Complete schema documentation for all 29 database files
- Metadata contract, purpose tags, field-by-field schemas
- ID prefix conventions, cross-file relationships

### PIPELINE_ARCHITECTURE.md
- Three-stage pipeline documentation (Clean → Enrich → Score)
- Database consumption per stage
- Match ledger partitions and domains
- Scoring breakdown (80-point scale)
- CLI usage examples

### validate_database.py
- Standalone validation script: 29/29 files pass
- Per-file: JSON validity, metadata schema, total_entries accuracy, duplicate IDs, deprecated field detection, uniform record keys, severity normalization, RDA/UL consistency checks
- Cross-file: supersedes_ids ↔ id_redirects consistency

### test_pipeline_integrity.py
- Automated test suite for schema integrity, data flow, and mapping correctness

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Database files | 29 |
| Schema version | 4.0.0 (uniform) |
| IQM entries | 449 ingredients |
| Banned entries | 140 |
| ID redirects | 38 |
| Clinical strains | 42 |
| Test suite | 868+ tests passing |
| Pipeline products (Lozenges) | 978 |
| Average quality score | 41.45/80 |
| Probiotic products | 34 correctly identified |

### Score Arithmetic Note
- Final score arithmetic is: `score_80 = A + B + C + D + violation_penalty` (then clamped to [0, 80]).
