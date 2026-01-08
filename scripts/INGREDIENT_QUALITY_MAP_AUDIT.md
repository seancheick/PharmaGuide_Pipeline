# Ingredient Quality Map Audit Report

**File**: `scripts/data/ingredient_quality_map.json`
**Date**: 2026-01-08
**Schema Version**: 2.0.0

---

## Executive Summary

The ingredient_quality_map.json is a comprehensive database with **432 ingredients** and **1,221 forms**. While the core structure is sound, there are several data quality issues that need attention for production readiness.

### Critical Issues (P0)

| Issue | Count | Impact |
|-------|-------|--------|
| Cross-ingredient duplicate aliases | 45 | **HIGH** - Causes ambiguous matching |
| Forms with empty aliases | 67 | **HIGH** - Cannot be matched |
| Invalid/missing CUI values | 217 (50%) | **MEDIUM** - Limits cross-referencing |
| Invalid/missing RxCUI values | 345 (80%) | **MEDIUM** - Limits drug interaction checks |

### Moderate Issues (P1)

| Issue | Count | Impact |
|-------|-------|--------|
| Missing risk_level field | 212 (49%) | MEDIUM - Cannot assess safety |
| Absorption value inconsistency | 200+ formats | MEDIUM - Cannot programmatically use |
| Category naming inconsistencies | 5 pairs | LOW - Minor classification issues |
| Empty notes fields | 58 | LOW - Missing documentation |

---

## Detailed Findings

### 1. Database Structure

**Top-Level Fields** (per ingredient):
```
Field               Present   Percentage  Status
─────────────────────────────────────────────────
standard_name       432       100.0%      ✓ Required
category            432       100.0%      ✓ Required
cui                 432       100.0%      ⚠ 50% invalid
rxcui               432       100.0%      ⚠ 80% invalid
forms               432       100.0%      ✓ Required
risk_level          220       50.9%       ⚠ Missing ~50%
source              219       50.7%       ⚠ Missing ~50%
priority            219       50.7%       ⚠ Missing ~50%
description         219       50.7%       ⚠ Missing ~50%
dosage_importance   219       50.7%       ⚠ Missing ~50%
aliases             22        5.1%        ✗ Mostly in forms
rda_ul_ref          15        3.5%        ✗ Rare
notes               13        3.0%        ✗ Rare
```

**Form-Level Fields** (per form):
```
Field               Present   Percentage  Status
─────────────────────────────────────────────────
bio_score           1221      100.0%      ✓ Required
natural             1221      100.0%      ✓ Required
score               1221      100.0%      ✓ Required
absorption          1221      100.0%      ⚠ Inconsistent format
notes               1221      100.0%      ✓ 58 empty
aliases             1221      100.0%      ⚠ 67 empty
dosage_importance   1199      98.2%       ✓ Good
```

### 2. Alias Coverage Issues

**Critical Finding**: 94.5% of forms have aliases (good), BUT there are **45 cross-ingredient duplicate aliases** that cause matching ambiguity.

**Examples of Problematic Duplicates**:
| Alias | Maps To |
|-------|---------|
| "nicotinamide riboside" | vitamin_b3_niacin, nicotinamide_riboside |
| "nicotinamide mononucleotide" | vitamin_b3_niacin, nmn |
| "naringin" | citrus_bioflavonoids, naringin |
| "quercetin" | citrus_bioflavonoids, quercetin |
| "flaxseed oil" | omega_3, flaxseed |
| "curcumin phytosome" | curcumin, turmeric |
| "liposomal curcumin" | curcumin, turmeric |

**Impact**: When a product label contains "nicotinamide riboside", the matcher cannot determine if it should map to the vitamin_b3 entry or the standalone nicotinamide_riboside entry.

**Recommendation**: Implement priority-based matching or merge duplicate alias targets.

### 3. CUI/RxCUI Quality

**CUI (Concept Unique Identifier)**:
- Valid: 215 (50%)
- Invalid (null, empty, "none"): 217 (50%)

**RxCUI (RxNorm Concept Unique Identifier)**:
- Valid: 87 (20%)
- Invalid: 345 (80%)

**Sample Missing CUIs**:
- hmb, rice_protein, red_wine_extract, gamma_linolenic_acid, 27_deoxyactein, etc.

**Recommendation**: Research and populate CUIs for botanical/novel ingredients. For truly novel compounds without UMLS entries, document as `"cui": null, "cui_note": "No UMLS entry - [reason]"`.

### 4. Absorption Value Inconsistency

**Critical Finding**: Over **200 different absorption value formats** exist, making programmatic use impossible.

**Format Categories**:
| Type | Count | Examples |
|------|-------|----------|
| "unknown" | 449 | "unknown" |
| Percentage ranges | 338 | "20-40%", "8.7-65%", "80-100%" |
| Text qualitative | 434 | "high", "excellent", "moderate", "poor" |
| Mixed formats | various | "good (~50-60%)", "2–3x better", "78%" |

**Sample Value Chaos**:
```
"unknown"                    449
"good"                       67
"excellent"                  59
"moderate"                   46
"good (~50-60%)"            14
"superior (~2–3x)"          12
"excellent (~90-95%)"        9
"2–3x better"               5
"65x standard"              1
```

**Recommendation**: Standardize to structured format:
```json
"absorption": {
  "value": 0.5,           // 0-1 normalized
  "range_low": 0.4,       // optional
  "range_high": 0.6,      // optional
  "quality": "good",      // enum: poor|moderate|good|excellent|superior
  "notes": "compared to standard form"
}
```

### 5. Category Normalization

**Inconsistent Singular/Plural**:
| Singular | Plural | Recommendation |
|----------|--------|----------------|
| adaptogen | adaptogens | Use "adaptogens" |
| fatty_acid | fatty_acids | Use "fatty_acids" |
| protein | proteins | Use "proteins" |
| functional_food | functional_foods | Use "functional_foods" |
| fiber | fibers | Use "fibers" |

**Category Distribution**:
```
antioxidants           197
herbs                  58
amino_acids            25
other                  22
minerals               19
fatty_acids            16
vitamins               15
probiotics             14
adaptogens             9+1
phytonutrients         7
fatty_acid             6    <- merge into fatty_acids
enzymes                5
functional_foods       5+1
fibers                 4+1
...
```

### 6. Scoring System Validation

**bio_score** (range 1-15):
- Distribution is appropriate
- Higher scores (14-15) for premium forms
- No invalid values found

**natural** (boolean):
- True: 454 forms
- False: 767 forms
- Valid boolean values throughout

**dosage_importance**:
- 0.5: 87 forms
- 1.0: 956 forms (default)
- 1.3-1.5: 156 forms (enhanced)
- Valid range throughout

### 7. Overlapping Ingredients

**39 ingredient pairs** where one name contains another:
| Ingredient | Related To |
|------------|------------|
| vitamin_k | vitamin_k1 |
| creatine_monohydrate | creatine |
| l_carnitine | acetyl_l_carnitine |
| curcumin | curcuminoids, bisdemethoxycurcumin |
| glutathione | glutathione_peroxidase |
| ginkgo | ginkgolides |
| alkaloids | oxindole_alkaloids, erythrina_alkaloids |

**Impact**: Not necessarily duplicates - these are often parent/child relationships (e.g., curcumin is a specific curcuminoid). However, matching logic should handle parent-child priority.

---

## Recommended Schema Updates (v3.0)

### 1. Add Match Rules Block
```json
{
  "match_rules": {
    "priority": 1,                    // Lower = higher priority
    "match_mode": "alias_and_fuzzy",
    "exclusions": [],                 // Terms that should NOT match
    "parent_id": null,                // For child ingredients
    "confidence": "high"
  }
}
```

### 2. Standardize Absorption Format
```json
{
  "absorption": {
    "value": 0.65,
    "range": [0.50, 0.80],
    "quality": "good",
    "compared_to": "standard_form",
    "notes": "With fat for optimal absorption"
  }
}
```

### 3. Add Entity Relationships
```json
{
  "relationships": [
    {"type": "parent_of", "target_id": "curcuminoids"},
    {"type": "active_in", "target_id": "turmeric"},
    {"type": "precursor_to", "target_id": "glutathione"}
  ]
}
```

### 4. Add Data Quality Block
```json
{
  "data_quality": {
    "completeness": 0.85,
    "missing_fields": ["cui"],
    "review_status": "validated",
    "last_reviewed_at": "2026-01-08"
  }
}
```

### 5. Normalize Categories
Standardize to plural forms with defined enum:
```json
"category_enum": [
  "vitamins", "minerals", "amino_acids", "fatty_acids",
  "antioxidants", "probiotics", "prebiotics", "fibers",
  "herbs", "adaptogens", "enzymes", "proteins",
  "phytonutrients", "nutraceuticals", "functional_foods",
  "metabolites", "hormones", "other"
]
```

---

## Implementation Priority

### Phase 1 (P0 - Critical for Matching)
1. **Resolve duplicate aliases** - Create alias priority map
2. **Fill empty aliases** - Add aliases to 67 forms with empty arrays
3. **Add match_rules block** - Enable priority-based matching

### Phase 2 (P1 - Data Quality)
4. **Standardize absorption values** - Convert to structured format
5. **Normalize categories** - Merge singular/plural variants
6. **Populate missing CUIs** - Research and add where possible

### Phase 3 (P2 - Schema Evolution)
7. **Add entity relationships** - Link parent/child ingredients
8. **Add data_quality blocks** - Track completeness per entry
9. **Add review workflow** - Similar to banned ingredients

---

## Verification Queries

```python
# Check for duplicate aliases
python -c "import json; d=json.load(open('data/ingredient_quality_map.json')); ..."

# Validate schema after updates
python -m pytest tests/test_ingredient_quality_schema.py -v

# Run matching tests
python -m pytest tests/test_ingredient_matching.py -v
```

---

## Summary

| Metric | Current | Target |
|--------|---------|--------|
| Total Ingredients | 432 | 432+ |
| Total Forms | 1,221 | 1,221+ |
| Alias Coverage | 94.5% | 100% |
| Duplicate Aliases | 45 | 0 |
| Valid CUIs | 50% | 80%+ |
| Standardized Absorption | 0% | 100% |
| Category Consistency | ~90% | 100% |

**Overall Assessment**: The database is functional but needs P0 fixes for reliable matching. The duplicate alias issue is the most critical blocker for production use.
