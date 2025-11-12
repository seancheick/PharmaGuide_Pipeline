# Best Practices for Uncertain Ingredient Classification

## Conservative Classification Framework

When encountering ingredients with uncertain regulatory status, follow this decision tree to ensure healthcare safety:

### 1. Source Context Analysis
**CRITICAL**: Always check raw data for contextual information that may have been lost during cleaning.

- **Natural vs Synthetic**: Same ingredient name can have different regulatory status
  - Example: Natural IGF-1 from deer antler velvet (legal) vs Synthetic IGF-1 (banned)
- **Dosage Context**: Amount may determine classification
  - Example: Colloidal Silver in trace amounts vs therapeutic doses
- **Product Type**: Supplement vs drug classification affects legality

### 2. Research Priority Order
1. **FDA Official Sources**: drugs.fda.gov, fda.gov dietary supplement guidance
2. **NIH Databases**: DSLD, PubMed, NIH Office of Dietary Supplements
3. **Professional Databases**: Natural Medicines, RxList, WebMD Professional
4. **Regulatory Updates**: Recent FDA warning letters, recalls

### 3. Classification Decision Matrix

#### HIGH CERTAINTY - BANNED
- FDA explicitly prohibits in supplements
- Active recall or warning letter
- Prescription drug classification
- **Action**: Add to banned_recalled_ingredients.json

#### MODERATE CERTAINTY - HARMFUL
- Safety concerns in literature
- Restricted use recommendations
- Potential drug interactions
- **Action**: Add to harmful_additives.json with appropriate risk_level

#### LOW CERTAINTY - CONSERVATIVE APPROACH
- Conflicting information
- Limited safety data
- Regulatory gray area
- **Action**: Research further before classification OR classify as harmful with notes

#### SAFE CLASSIFICATION
- Generally Recognized as Safe (GRAS)
- Long history of safe use
- Positive safety profile
- **Action**: Add to appropriate beneficial database

### 4. Documentation Requirements

For any uncertain classification, include:
```json
{
  "notes": "UNCERTAIN STATUS: [specific concern]. Research date: [YYYY-MM-DD]. Sources: [list]. Recommend periodic review.",
  "research_date": "2025-XX-XX",
  "sources": ["FDA.gov", "NIH", "etc"],
  "review_required": true,
  "confidence_level": "low|medium|high"
}
```

### 5. IGF-1 Case Study Example

**Initial Challenge**: IGF-1 found in supplement data - banned or legal?

**Research Process**:
1. **Raw Data Check**: Found "Deer Antler Velvet extract (3.3mg)" as source
2. **FDA Research**: Confirmed synthetic IGF-1 banned, natural forms legal
3. **Context Analysis**: 82.5 nanograms from natural source vs synthetic hormone
4. **Classification**:
   - Synthetic IGF-1 → banned_recalled_ingredients.json
   - Natural IGF-1 from deer antler → ingredient_quality_map.json with aliases

### 6. Preservation of Context

**Critical Rule**: Never lose regulatory context during data cleaning

**Implementation**:
- Preserve dosage information
- Maintain source/form distinctions
- Keep manufacturing method details
- Retain FDA-specific terminology

### 7. Regular Review Process

**Quarterly Reviews**:
- Check FDA warning letters
- Review recalled products
- Update uncertain classifications
- Verify research currency

**Immediate Updates**:
- FDA safety alerts
- New regulations
- Recall announcements

### 8. Healthcare Safety Priority

**When in doubt, err on the side of caution**:
- Uncertain = classify as harmful until proven safe
- Document reasoning thoroughly
- Flag for expert review
- Prioritize patient safety over convenience

### 9. Cross-Category Considerations

Some ingredients may belong in multiple databases:
- **Allergen + Harmful**: Carmine Red (allergic reactions + synthetic concerns)
- **Beneficial + Allergen**: Whey protein (nutritious + milk allergy)
- **Natural + Harmful**: Essential oils (natural + toxicity concerns)

**Rule**: Add to most restrictive category with cross-references in notes.

### 10. Implementation Checklist

Before finalizing any uncertain ingredient classification:

- [ ] Raw data context preserved
- [ ] Multiple reliable sources consulted
- [ ] Natural vs synthetic distinction clear
- [ ] Dosage context considered
- [ ] Documentation complete with sources
- [ ] Review date established
- [ ] Healthcare safety prioritized
- [ ] Cross-category implications addressed