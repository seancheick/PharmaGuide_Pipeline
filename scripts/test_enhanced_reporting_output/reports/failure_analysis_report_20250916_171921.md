# Enrichment Failure Analysis Report

**Generated:** 2025-09-16 17:19:21 UTC
**Total Failures Analyzed:** 5

## Summary

- **Total Products Processed:** 6
- **Successful Enrichments:** 1
- **Failed Enrichments:** 5
- **Success Rate:** 16.7%

## Failure Categories

- **Data Completeness:** 3 failures (60.0%)
- **Data Quality:** 1 failures (20.0%)
- **Ingredient Mapping:** 1 failures (20.0%)

## Detailed Failure Analysis

### Data Completeness (3 failures)

#### 1.  (ID: )

**Brand:** Test Brand
**Error:** Missing essential fields: id, fullName
**Missing Fields:** id, fullName
**Data Quality Issues:**
- Missing or invalid product ID
- Missing product name
**Recommended Actions:**
- Add missing essential fields: id, fullName
- Fix data quality issue: Missing or invalid product ID
- Fix data quality issue: Missing product name

---

#### 2. Test Product 2 (ID: TEST002)

**Brand:** Test Brand
**Error:** No active ingredients found - product cannot be enriched
**Missing Fields:** activeIngredients, activeIngredients
**Data Quality Issues:**
- No active ingredients listed
**Recommended Actions:**
- Add active ingredients data to source file
- Add missing essential fields: activeIngredients
- Fix data quality issue: No active ingredients listed

---

#### 3. Test Product 5 (ID: TEST005)

**Brand:** 
**Error:** Data quality validation failed: invalid quantity values
**Missing Fields:** brandName
**Data Quality Issues:**
- Missing brand name
- Active ingredient 2 missing name
**Recommended Actions:**
- Add missing essential fields: brandName
- Fix data quality issue: Missing brand name
- Fix data quality issue: Active ingredient 2 missing name

---

### Data Quality (1 failures)

#### 1. Test Product 3 (ID: TEST003)

**Brand:** Test Brand
**Error:** Ingredient structure validation failed: missing required fields
**Data Quality Issues:**
- Active ingredient 'Vitamin D' missing quantity
- Active ingredient 'Vitamin D' missing unit
- Active ingredient 2 missing name
**Recommended Actions:**
- Fix data quality issue: Active ingredient 'Vitamin D' missing quantity
- Fix data quality issue: Active ingredient 'Vitamin D' missing unit
- Fix data quality issue: Active ingredient 2 missing name

---

### Ingredient Mapping (1 failures)

#### 1. Test Product 4 (ID: TEST004)

**Brand:** Test Brand
**Error:** 2 ingredients could not be mapped to reference database
**Recommended Actions:**
- Add mappings for ingredients: SuperRareIngredient123, AnotherUnknownCompound

---

## Key Insights & Recommendations

### Data Completeness Issues

Found 3 products with missing essential data fields.

**Recommended Actions:**
- Review data extraction process for completeness
- Implement validation checks before enrichment
- Identify and fix data source issues

### Ingredient Mapping Failures

Found 1 products with unmapped ingredients.

**Recommended Actions:**
- Expand ingredient quality mapping database
- Review unmapped ingredients for common patterns
- Add aliases for commonly missed ingredient names

