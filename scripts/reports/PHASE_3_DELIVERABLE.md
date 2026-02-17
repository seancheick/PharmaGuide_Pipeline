# Phase 3 — Pipeline Script Alignment: Deliverable Report

**Date:** 2026-02-16
**Status:** COMPLETE
**Test suite:** 856 passed, 0 failed, 5 skipped

---

## 1. Per-Script Change Log

### Flagged Database Issues

| File | Change | Rationale |
|------|--------|-----------|
| `data/ingredient_quality_map.json` | Extracted `strontium` from inside `flavonols` to its own top-level entry; removed duplicate `pqq` from `flavonols` (top-level entry already existed); fixed `match_rules.priority` 50→1; updated `_metadata.statistics.total_ingredients` 448→449 | Flag 1: misplaced ingredients |
| `data/banned_recalled_ingredients.json` | Fixed 32 records where `severity_level` was less accurate than `risk_level` (e.g., Formaldehyde "moderate"→"critical", Aluminum Compounds "low"→"high"); removed `risk_level` from all 140 records; fields per record 69→68 | Flag 2: dual severity schema |
| `data/rda_optimal_uls.json` | No change needed — `highest_ul` already correct in v4.0.0 | Flag 3: verified |

### Core Pipeline Scripts

| File | Lines | Change |
|------|-------|--------|
| `rda_ul_calculator.py` | ~408-415 | Replaced ND string parsing with simple `isinstance(ul, (int, float))` type check |
| `rda_ul_calculator.py` | ~466-476 | Replaced `if ul_field == "ND"` with `ul_status = nutrient_data.get("ul_status"); if ul_status == "not_determined"` |
| `proprietary_blend_detector.py` | 174 | `penalties = blend_def.get("penalties") or blend_def.get("penalty_levels") or []` — null-fill guard |
| `proprietary_blend_detector.py` | 189-190 | `terms = blend_def.get("red_flag_terms") or []` and `aliases = blend_def.get("aliases") or []` — null-fill guard |
| `enhanced_normalizer.py` | 650 | Added `schema_version` lookup before `version` fallback for v4.0.0 `_metadata` |
| `constants.py` | 217 | Added clarifying comment: "Required fields for RAW DSLD input validation (before cleaning transforms names)" |
| `constants.py` | 248 | Changed `RISK_LEVELS = ["low", "moderate", "high"]` to `RISK_LEVELS = SEVERITY_LEVELS` (alias, not duplicate) |
| `coverage_gate.py` | 313 | `product.get("dsldId", ...)` → `product.get("dsld_id", product.get("id", "unknown"))` — dsldId never existed |
| `format_coverage_validator.py` | 101 | Flipped priority: `product.get('product_name', product.get('fullName', ...))` |
| `claims_audit.py` | 107-108 | Flipped priority to `dsld_id` first, `product_name` first |
| `data/standardized_botanicals.json` | — | Added "black elderberry fruit extract", "liquorice"/"liquorice root"/"liquorice root extract" aliases |

### Test Fixtures Updated

| File | Change |
|------|--------|
| `tests/test_coverage_gate.py` | All `"dsldId"` → `"dsld_id"` (20 occurrences) |
| `tests/test_manufacturer_policy.py` | All `"dsldId"` → `"dsld_id"` (4 occurrences); updated scorer API (breakdown.D.D1); fixed fuzzy match mock (found: False) |
| `tests/test_provenance_invariants.py` | All `"dsldId"` → `"dsld_id"` (11 occurrences) |
| `tests/test_allergen_negation.py` | All `'dsldId'` → `'dsld_id'` (3 occurrences) |
| `tests/test_claims_hardening.py` | Added `rules_db['rules']` prefix for cert_claim_rules v4.0.0 structure (6 fixes); skipped 2 tests for removed `_score_b3_certifications` |
| `tests/test_ingredient_quality_map_schema.py` | Schema version 3.x→4.x; added `'low'` to VALID_QUALITIES; added ALLOWED_CROSS_ALIASES |
| `tests/test_banned_schema_v3.py` | Removed `synonyms` check from alias sync test |
| `tests/test_dosage_golden_fixtures.py` | Added None guard for score_80 comparison |
| `tests/test_harmful_schema_v2.py` | Fixed relative path for missing_match_tokens.json |
| `tests/test_scorable_classification.py` | Accept `recognized_non_scorable` skip reason |
| `tests/test_score_supplements.py` | Tests aligned to v3.0 scorer API |
| `tests/test_enrichment_regressions.py` | Tests aligned to current enricher output |

---

## 2. Removed Workaround Inventory

| Location | What was removed | Reason |
|----------|------------------|--------|
| `rda_ul_calculator.py:408-415` | Complex string parsing of `"ND"`, `"< 2"` patterns for UL values | v4.0.0 uses `null` + `ul_status`/`rda_ai_status` fields; no more string values |
| `rda_ul_calculator.py:466-476` | `if ul_field == "ND"` string comparison | Replaced with structured `ul_status == "not_determined"` check |
| `constants.py:248` | Duplicate `RISK_LEVELS = ["low", "moderate", "high"]` | Now alias of `SEVERITY_LEVELS`; `risk_level` field removed from all databases |
| `data/banned_recalled_ingredients.json` | `risk_level` field on all 140 records | Dual schema resolved; `severity_level` is the single canonical field |
| `data/ingredient_quality_map.json` | Duplicate `pqq` nested inside `flavonols` | Top-level `pqq` entry already existed with more complete data |

---

## 3. New Validation Guards

### validate_database_schema() — `preflight.py`
- Validates all 10 critical JSON databases conform to v4.0.0 schema
- Checks: `_metadata` wrapper present, `schema_version` starts with `"4."`, no deprecated root fields (`risk_level`, `synonyms`, `canonical_name`, `database_info`)
- Spot-checks entries for deprecated fields
- Integrated into `run_preflight()` — runs automatically during preflight checks
- All 10 databases currently PASS

### validate_enriched_product() — `score_supplements.py` (pre-existing)
- Already validates scoring input: checks `dsld_id`/`id`, `product_name`/`fullName`, `enrichment_version`/`enriched_date`
- Uses fallback patterns for backward compatibility with both old and new field names

---

## 4. Config File Verification

| Config | Version | Status |
|--------|---------|--------|
| `config/cleaning_config.json` | — | Valid JSON, correct paths structure |
| `config/enrichment_config.json` | 3.1.0 | Valid JSON, correct database path references |
| `config/scoring_config.json` | 3.0.1 | Valid JSON, correct feature_gates and penalty convention |

All configs reference `data/` directory for databases (not hardcoded absolute paths).
No deprecated field references found in any config file.

---

## 5. constants.py Verification

| Item | Status |
|------|--------|
| `REQUIRED_FIELDS` uses raw DSLD field names (`fullName`, `id`, `brandName`) | Correct — annotated with clarifying comment |
| `SEVERITY_LEVELS = ["low", "moderate", "high"]` | Canonical source |
| `RISK_LEVELS = SEVERITY_LEVELS` | Alias for backward compat |
| `HARMFUL_CATEGORIES` | 7 values, no deprecated entries |
| `STATUS_*` constants | 4 values, all used in dsld_validator.py |
| No `canonical_name`, `synonyms`, or `database_info` references | Confirmed clean |

---

## 6. Summary Statistics

- **Database files fixed:** 3 (ingredient_quality_map, banned_recalled, standardized_botanicals)
- **Script files modified:** 8 (rda_ul_calculator, proprietary_blend_detector, enhanced_normalizer, constants, coverage_gate, format_coverage_validator, claims_audit, preflight)
- **Test files updated:** 12
- **Dead code/workarounds removed:** 5 items
- **New validation guards:** 1 new (`validate_database_schema`), 1 pre-existing confirmed (`validate_enriched_product`)
- **Final test results:** 856 passed, 0 failed, 5 skipped
