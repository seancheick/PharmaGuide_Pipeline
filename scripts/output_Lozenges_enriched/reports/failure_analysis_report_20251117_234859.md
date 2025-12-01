# Enrichment Failure Analysis Report

**Generated:** 2025-11-17 23:48:59 UTC
**Total Failures Analyzed:** 978

## Summary

- **Total Products Processed:** 978
- **Successful Enrichments:** 0
- **Failed Enrichments:** 978
- **Success Rate:** 0.0%

## Failure Categories

- **Unknown:** 976 failures (99.8%)
- **Data Completeness:** 2 failures (0.2%)

## Detailed Failure Analysis

### Unknown (976 failures)

#### 1. DGL (De-Glycyrrhizinated Licorice Extract) (ID: 28787)

**Brand:** NOW
**Error:** Type error: sequence item 1: expected str instance, dict found
**Recommended Actions:**
- Review error message for specific details
- Validate input data structure and completeness
- Check enrichment script logs for additional context

---

#### 2. Melatonin 1 mg Cherry (ID: 28657)

**Brand:** GNC
**Error:** Type error: sequence item 1: expected str instance, dict found
**Recommended Actions:**
- Review error message for specific details
- Validate input data structure and completeness
- Check enrichment script logs for additional context

---

#### 3. Zinc Lozenge (ID: 288596)

**Brand:** DaVinci Laboratories
**Error:** Type error: sequence item 1: expected str instance, dict found
**Recommended Actions:**
- Review error message for specific details
- Validate input data structure and completeness
- Check enrichment script logs for additional context

---

#### 4. Methyl B-12 Cherry Flavor 500 mcg (ID: 28860)

**Brand:** Jarrow Formulas
**Error:** Type error: '>' not supported between instances of 'NoneType' and 'int'
**Recommended Actions:**
- Review error message for specific details
- Validate input data structure and completeness
- Check enrichment script logs for additional context

---

#### 5. Immuni-Z + Elderberry Natural Lemon Flavor (ID: 287875)

**Brand:** Little DaVinci
**Error:** Type error: sequence item 1: expected str instance, dict found
**Recommended Actions:**
- Review error message for specific details
- Validate input data structure and completeness
- Check enrichment script logs for additional context

---

#### 6. Vitamin B-12 Lozenges (ID: 29023)

**Brand:** Nutri-West
**Error:** Type error: '>' not supported between instances of 'NoneType' and 'int'
**Recommended Actions:**
- Review error message for specific details
- Validate input data structure and completeness
- Check enrichment script logs for additional context

---

#### 7. Methyl B-12 Cherry Flavor 5000 mcg (ID: 29137)

**Brand:** Jarrow Formulas
**Error:** Type error: '>' not supported between instances of 'NoneType' and 'int'
**Recommended Actions:**
- Review error message for specific details
- Validate input data structure and completeness
- Check enrichment script logs for additional context

---

#### 8. Vitamin B-12 5000 mcg (ID: 29162)

**Brand:** PhysioLogics
**Error:** Type error: '>' not supported between instances of 'NoneType' and 'int'
**Recommended Actions:**
- Review error message for specific details
- Validate input data structure and completeness
- Check enrichment script logs for additional context

---

#### 9. Methyl B-12 Lemon Flavor 1000 mcg (ID: 29135)

**Brand:** Jarrow Formulas
**Error:** Type error: '>' not supported between instances of 'NoneType' and 'int'
**Recommended Actions:**
- Review error message for specific details
- Validate input data structure and completeness
- Check enrichment script logs for additional context

---

#### 10. Vitamin B-12 2500 mcg (ID: 29180)

**Brand:** PhysioLogics
**Error:** Type error: '>' not supported between instances of 'NoneType' and 'int'
**Recommended Actions:**
- Review error message for specific details
- Validate input data structure and completeness
- Check enrichment script logs for additional context

---

*... and 966 more failures in this category*

### Data Completeness (2 failures)

#### 1. FLORASSIST Oral Hygeine (ID: 63294)

**Brand:** Life Extension
**Error:** Enrichment failed: 'dict' object has no attribute 'lower'
**Missing Fields:** activeIngredients, activeIngredients
**Data Quality Issues:**
- No active ingredients listed
**Recommended Actions:**
- Add active ingredients data to source file
- Add missing essential fields: activeIngredients
- Fix data quality issue: No active ingredients listed

---

#### 2. Silver Lozenges Mighty Manuka Mint (ID: 201697)

**Brand:** Silver Biotics
**Error:** Enrichment failed: 'dict' object has no attribute 'lower'
**Missing Fields:** activeIngredients, activeIngredients
**Data Quality Issues:**
- No active ingredients listed
**Recommended Actions:**
- Add active ingredients data to source file
- Add missing essential fields: activeIngredients
- Fix data quality issue: No active ingredients listed

---

## Key Insights & Recommendations

### Data Completeness Issues

Found 2 products with missing essential data fields.

**Recommended Actions:**
- Review data extraction process for completeness
- Implement validation checks before enrichment
- Identify and fix data source issues

