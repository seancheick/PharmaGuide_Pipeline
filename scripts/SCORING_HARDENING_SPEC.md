# Scoring Hardening Specification

**Version:** 1.0.0
**Created:** 2026-01-07
**Status:** Implementation Ready
**Priority Order:** P0 → P1 → P2

---

## Executive Summary

This document specifies the technical requirements for hardening the supplement scoring system. Each feature follows the **4-deliverable rule**:

1. Versioned reference DB (if applicable)
2. Evidence fields in enriched/scored output
3. Contract validation rules (fail-fast)
4. Unit + integration tests + batch audit report

---

## Table of Contents

1. [P0-1: Unit Conversion Database](#p0-1-unit-conversion-database)
2. [P0-2: Serving Basis + Dosage Normalization](#p0-2-serving-basis--dosage-normalization)
3. [P0-3: DV/RDA/UL Scoring](#p0-3-dvrdaul-scoring)
4. [P0-4: Proprietary Blend Disclosure Penalty](#p0-4-proprietary-blend-disclosure-penalty)
5. [P1-1: Probiotic Scoring](#p1-1-probiotic-scoring)
6. [P1-2: Clinical Evidence Tier Scoring](#p1-2-clinical-evidence-tier-scoring)
7. [P1-3: Harmful Additive Penalties](#p1-3-harmful-additive-penalties)
8. [P2-1: Synergy Clusters](#p2-1-synergy-clusters)
9. [P2-2: Manufacturer Violations](#p2-2-manufacturer-violations)
10. [Appendix: Test Fixtures](#appendix-test-fixtures)

---

## P0-1: Unit Conversion Database

**Priority:** P0 (prerequisite for all dosage scoring)
**File:** `data/unit_conversions.json`
**Why:** Incorrect unit conversions are the #1 source of scoring errors.

### Schema

```json
{
  "database_info": {
    "version": "1.0.0",
    "last_updated": "2026-01-XX",
    "description": "Nutrient + form specific unit conversions",
    "sources": [
      "https://ods.od.nih.gov/HealthInformation/nutrientrecommendations.aspx",
      "https://www.fda.gov/media/129863/download"
    ]
  },

  "conversions": {
    "vitamin_d3": {
      "standard_name": "Vitamin D3 (Cholecalciferol)",
      "iu_to_mcg": 0.025,
      "mcg_to_iu": 40,
      "canonical_unit": "mcg",
      "fda_label_unit": "mcg",
      "notes": "FDA requires mcg on labels since 2020; IU may appear in parentheses"
    },

    "vitamin_d2": {
      "standard_name": "Vitamin D2 (Ergocalciferol)",
      "iu_to_mcg": 0.025,
      "mcg_to_iu": 40,
      "canonical_unit": "mcg",
      "notes": "Same conversion as D3"
    },

    "vitamin_e_d_alpha_tocopherol": {
      "standard_name": "Vitamin E (d-alpha-tocopherol, natural)",
      "iu_to_mg": 0.67,
      "mg_to_iu": 1.49,
      "canonical_unit": "mg",
      "notes": "Natural form - higher bioavailability"
    },

    "vitamin_e_dl_alpha_tocopherol": {
      "standard_name": "Vitamin E (dl-alpha-tocopherol, synthetic)",
      "iu_to_mg": 0.45,
      "mg_to_iu": 2.22,
      "canonical_unit": "mg",
      "notes": "Synthetic form - lower bioavailability than natural"
    },

    "vitamin_a_retinol": {
      "standard_name": "Vitamin A (Retinol/Retinyl esters)",
      "iu_to_mcg_rae": 0.3,
      "mcg_rae_to_iu": 3.33,
      "canonical_unit": "mcg RAE",
      "notes": "Preformed vitamin A - UL applies to this form",
      "warnings": ["UL of 3000 mcg RAE applies to preformed vitamin A only"]
    },

    "vitamin_a_beta_carotene_food": {
      "standard_name": "Vitamin A (Beta-carotene from food)",
      "iu_to_mcg_rae": 0.05,
      "mcg_rae_to_iu": 20,
      "canonical_unit": "mcg RAE",
      "notes": "Food-source beta-carotene has lower conversion efficiency"
    },

    "vitamin_a_beta_carotene_supplement": {
      "standard_name": "Vitamin A (Beta-carotene from supplements)",
      "iu_to_mcg_rae": 0.1,
      "mcg_rae_to_iu": 10,
      "canonical_unit": "mcg RAE",
      "notes": "Supplemental beta-carotene - higher absorption than food"
    },

    "folate_folic_acid": {
      "standard_name": "Folate (as Folic Acid)",
      "mcg_to_mcg_dfe": 1.7,
      "canonical_unit": "mcg DFE",
      "notes": "Folic acid taken on empty stomach: 1 mcg = 1.7 mcg DFE"
    },

    "folate_food": {
      "standard_name": "Folate (from food)",
      "mcg_to_mcg_dfe": 1.0,
      "canonical_unit": "mcg DFE",
      "notes": "Food folate: 1 mcg = 1 mcg DFE"
    },

    "niacin": {
      "standard_name": "Niacin (Vitamin B3)",
      "mg_ne_conversion": "1 mg niacin = 1 mg NE; 60 mg tryptophan = 1 mg NE",
      "canonical_unit": "mg NE",
      "notes": "NE = Niacin Equivalents"
    }
  },

  "mass_conversions": {
    "_description": "Standard mass unit conversions (nutrient-independent)",
    "g_to_mg": 1000,
    "mg_to_mcg": 1000,
    "g_to_mcg": 1000000,
    "mcg_to_mg": 0.001,
    "mg_to_g": 0.001
  },

  "probiotic_conversions": {
    "_description": "CFU normalization",
    "billion_cfu_to_cfu": 1000000000,
    "million_cfu_to_cfu": 1000000,
    "viable_cells_equals_cfu": true,
    "canonical_unit": "CFU",
    "display_unit": "billion CFU"
  }
}
```

### Critical Rule: Vitamin A Form Detection

**NEVER use a single vitamin A conversion factor.** The enrichment must:

1. Detect the vitamin A form from ingredient name/description
2. Apply the correct conversion factor
3. Output `vitamin_a_form_detected` in evidence

| Label Text | Form | IU → mcg RAE |
|------------|------|--------------|
| "Vitamin A (as Retinyl Palmitate)" | retinol | × 0.3 |
| "Vitamin A (as Beta-Carotene)" | beta_carotene_supplement | × 0.1 |
| "Vitamin A" (no form specified) | UNKNOWN | Flag for review |

### Evidence Output

```python
"dosage_conversion_evidence": {
    "original_value": 10000,
    "original_unit": "IU",
    "converted_value": 3000,
    "converted_unit": "mcg RAE",
    "conversion_rule_id": "vitamin_a_retinol",
    "conversion_factor": 0.3,
    "form_detected": "retinyl_palmitate",
    "form_detection_source": "ingredient_name",
    "confidence": "high"
}
```

### Done When

- [ ] 25+ unit test cases covering:
  - Vitamin D IU ↔ mcg (both directions)
  - Vitamin E natural vs synthetic
  - Vitamin A all 3 forms + unknown handling
  - Folate DFE conversions
  - Mass unit conversions (g/mg/mcg)
  - CFU/billion CFU normalization
- [ ] Contract validator rejects unknown vitamin A form without flag
- [ ] Batch audit shows 0 conversion errors on 100-product sample

---

## P0-2: Serving Basis + Dosage Normalization

**Priority:** P0
**Why:** "Per 2 gummies" vs "per serving" ambiguity causes incorrect dosing calculations.

### Serving Size Selection Policy

When a product has multiple serving size options, use this priority:

1. **Recommended daily serving** (if explicitly stated)
2. **Single serving** (e.g., "1 capsule", "1 gummy")
3. **Minimum of range** (if "1-2 capsules", use 1)

### Normalization Requirements

```python
"dosage_normalized": {
    "serving_basis": {
        "quantity": 2,
        "unit": "gummies",
        "servings_per_container": 30,
        "servings_per_day_min": 1,
        "servings_per_day_max": 2,
        "servings_per_day_used": 1,  # Policy: use minimum
        "source_field": "servingSizes[0]"
    },
    "per_serving": {
        "vitamin_d3": {
            "amount": 50,
            "unit": "mcg",
            "converted_from": {"amount": 2000, "unit": "IU"}
        }
    },
    "per_day_min": {
        "vitamin_d3": {"amount": 50, "unit": "mcg"}
    },
    "per_day_max": {
        "vitamin_d3": {"amount": 100, "unit": "mcg"}
    }
}
```

### Tricky Cases to Handle

| Case | Example | Handling |
|------|---------|----------|
| Multiple serving sizes | "1 or 2 capsules" | Use minimum (1) for scoring |
| Fractional servings | "1/2 teaspoon" | Convert to decimal |
| Age-based servings | "Adults: 2, Children: 1" | Use adult serving |
| Time-based | "1 AM, 1 PM" | Sum for daily total |
| "As directed" | No quantity | Flag as missing, don't score |

### Done When

- [ ] 20+ unit tests for serving size parsing
- [ ] Integration test: clean → enrich → score produces stable results for fixed fixtures
- [ ] Output includes `dosage_normalized` and `dosage_basis_evidence`
- [ ] Contract validator rejects products with unparseable serving size

---

## P0-3: DV/RDA/UL Scoring

**Priority:** P0
**Reference File:** `data/rda_optimal_uls.json`
**Why:** Core differentiator - must not be wrong.

### Scoring Function Requirements

```python
def compute_nutrient_adequacy(
    nutrient: str,
    amount_normalized: float,
    unit: str,
    age_group: str = "19-50",
    sex: str = "both"
) -> Dict:
    """
    Returns:
    - pct_rda: percentage of RDA/AI
    - pct_ul: percentage of UL (or None if no UL)
    - adequacy_band: "deficient" | "suboptimal" | "optimal" | "high" | "excessive"
    - over_ul: bool
    - over_ul_amount: float (if applicable)
    - scoring_eligible: bool
    - notes: list of explanatory strings
    """
```

### Adequacy Bands (E1 Scoring)

| Band | % of RDA | Points |
|------|----------|--------|
| Deficient | < 25% | 0 |
| Suboptimal | 25-74% | +1 |
| Optimal | 75-150% | +3 |
| High | 151-300% | +2 |
| Excessive | > 300% or > UL | 0 + warning |

### "No UL" Policy

**Critical:** Some nutrients have no established UL (e.g., Vitamin B12, Thiamin, Riboflavin).

```python
# Policy: If UL is None or "not established"
if ul is None or ul == "not_established":
    over_ul = False  # Cannot penalize
    over_ul_note = "No UL established for this nutrient"
    # Optionally flag if amount > 10x RDA as informational
```

### Over-UL Safety Penalty

```python
"safety_flags": {
    "over_ul_nutrients": [
        {
            "nutrient": "Vitamin A",
            "amount": 4500,
            "unit": "mcg RAE",
            "ul": 3000,
            "pct_ul": 150,
            "penalty_applied": -3,
            "warning": "Exceeds Tolerable Upper Intake Level"
        }
    ]
}
```

### Done When

- [ ] 30+ fixtures covering:
  - Below RDA (all bands)
  - Optimal band
  - High dose (above RDA, below UL)
  - Over UL (with penalty)
  - No UL nutrients (B12, etc.)
  - Missing dose (not scored)
  - Age/sex specific values
- [ ] Batch audit: "over UL" flags look plausible (spot check)
- [ ] Contract validator enforces unit conversion before UL comparison

---

## P0-4: Proprietary Blend Disclosure Penalty

**Priority:** P0
**Reference File:** `data/proprietary_blends_penalty.json`
**Why:** Penalty can swing scores heavily; must be consistent and explainable.

### Disclosure Levels

| Level | Definition | Penalty |
|-------|------------|---------|
| **Full** | Each sub-ingredient has individual quantity | 0 |
| **Partial** | Blend total stated, subs listed, individual amounts missing | -5 |
| **None** | No quantities at all, or vague "proprietary blend" | -10 |

### Detection Requirements

Enrichment must detect:

1. **Blend presence** - "Proprietary Blend", "Complex", "Matrix", etc.
2. **Total weight** - Was the blend total declared?
3. **Sub-ingredients** - Were they listed?
4. **Individual amounts** - Were sub-ingredient quantities provided?

### Evidence Output (Required)

```python
"proprietary_blend_evidence": {
    "blends_detected": [
        {
            "blend_name": "Proprietary Energy Blend",
            "blend_total_declared": true,
            "blend_total_amount": 500,
            "blend_total_unit": "mg",
            "blend_ingredients_listed": true,
            "blend_ingredient_count": 5,
            "blend_amounts_present": "none",  # none | partial | full
            "ingredients_with_amounts": [],
            "ingredients_without_amounts": [
                "Caffeine", "Green Tea Extract", "Guarana",
                "Yerba Mate", "Synephrine"
            ],
            "matched_text": "Proprietary Energy Blend 500mg: Caffeine, Green Tea Extract...",
            "source_field": "supplementFacts[3]",
            "risk_category": "stimulant",
            "disclosure_level": "none",
            "penalty_applied": -10,
            "penalty_reason": "No individual ingredient amounts disclosed in stimulant blend"
        }
    ],
    "total_blend_penalty": -10,
    "penalty_cap_applied": false,
    "penalty_cap": -10
}
```

### Risk Categories (from proprietary_blends_penalty.json)

| Category | Severity | Concern |
|----------|----------|---------|
| Stimulant | HIGH | Hidden caffeine, synergistic effects |
| Testosterone | HIGH | Undisclosed hormonal compounds |
| Weight Loss | HIGH | Hidden stimulants, diuretics |
| Nootropic | MEDIUM | Unverified cognitive compounds |
| Adaptogen | LOW | Generally safer herbs |

### Done When

- [ ] Tests for:
  - Fully disclosed blend (no penalty)
  - Partially disclosed (total + list, no individual amounts)
  - No disclosure (vague blend)
  - Multiple blends with correct scaling
  - Cap enforcement (-10 max)
- [ ] Integration test: penalty scales exactly per spec
- [ ] Evidence includes `matched_text` and `source_field`

---

## P1-1: Probiotic Scoring

**Priority:** P1
**Reference File:** `data/clinically_relevant_strains.json`
**Why:** CFU, strain specificity, and survivability are key quality indicators.

### CFU Thresholds

| CFU Range | Points | Notes |
|-----------|--------|-------|
| < 1 billion | 0 | Below ISAPP minimum |
| 1-5 billion | +1 | Meets minimum |
| 5-10 billion | +2 | Good range |
| 10-50 billion | +3 | Clinical efficacy range |
| > 50 billion | +4 | High potency |

### CFU Confidence Levels

**Critical:** "At expiration" vs "at manufacture" matters.

| Statement | Confidence | Scoring Modifier |
|-----------|------------|------------------|
| "X billion CFU at expiration" | HIGH | Full points |
| "X billion CFU guaranteed through expiration" | HIGH | Full points |
| "X billion CFU at time of manufacture" | MEDIUM | -1 point (die-off expected) |
| "X billion CFU" (no qualifier) | LOW | -1 point (assume at manufacture) |

### Strain Matching

Strain matching must be **strict** (exact or normalized strain IDs):

```python
"probiotic_evidence": {
    "cfu_detected": {
        "amount": 50000000000,
        "display": "50 billion CFU",
        "qualifier": "at_expiration",
        "confidence": "high",
        "source_field": "supplementFacts[0].amount"
    },
    "strains_matched": [
        {
            "detected_name": "Lactobacillus rhamnosus GG",
            "matched_strain_id": "STRAIN_LGG",
            "match_type": "exact",
            "match_confidence": "high",
            "evidence_level": "high",
            "key_benefits": ["gut health", "immune support"]
        }
    ],
    "strains_unmatched": [
        {
            "detected_name": "Lactobacillus acidophilus",
            "reason": "Species-level only, no strain ID",
            "scoring_impact": "Not eligible for strain bonus"
        }
    ],
    "survivability_coating": {
        "detected": true,
        "coating_type": "enteric",
        "matched_text": "acid-resistant capsule",
        "bonus_applied": +1
    },
    "scoring": {
        "cfu_points": 4,
        "strain_bonus": 2,
        "survivability_bonus": 1,
        "total": 7,
        "max_possible": 8
    }
}
```

### Survivability Detection (Bonus Modifier)

| Indicator | Bonus |
|-----------|-------|
| "Enteric coated" | +1 |
| "Acid-resistant" | +1 |
| "Delayed release" | +1 |
| "Survivability guaranteed" | +1 |
| None detected | 0 |

**Note:** Survivability is a bonus modifier, not a hard requirement.

### Done When

- [ ] Tests covering:
  - CFU parsing: "50 billion", "50B CFU", "5×10^10"
  - "Viable cells" = CFU equivalence
  - At expiration vs at manufacture confidence
  - Strain matching (exact, alias, unmatched)
  - Species-level detection (not scored for strain bonus)
  - Survivability coating detection
- [ ] Batch audit: CFU distribution looks reasonable

---

## P1-2: Clinical Evidence Tier Scoring

**Priority:** P1
**Reference File:** `data/backed_clinical_studies.json`
**Why:** Stable scoring if driven purely from evidence DB + ingredient presence.

### Evidence Tiers

| Tier | Evidence Type | Points per Match |
|------|---------------|------------------|
| 1 | Meta-analysis / Systematic Review | +3 |
| 2 | RCT (Randomized Controlled Trial) | +2 |
| 3 | Observational / Cohort Study | +1 |

### Scoring Rules

- **Cap:** Maximum 15 points from clinical evidence
- **No double-counting:** Same study cannot be counted twice
- **Ingredient match required:** Must match through standard ingredient mapping

### Evidence Output

```python
"clinical_evidence_data": {
    "matches": [
        {
            "ingredient_matched": "Curcumin",
            "study_id": "STUDY_CURCUMIN_META_2023",
            "study_type": "meta_analysis",
            "evidence_tier": 1,
            "points_awarded": 3,
            "condition": "inflammation",
            "source": "Cochrane Database"
        }
    ],
    "match_count": 5,
    "unique_studies": 5,
    "total_points": 12,
    "cap_applied": false,
    "cap_limit": 15
}
```

### Done When

- [ ] Tests for:
  - Single ingredient match
  - Multiple ingredient matches
  - Cap at 15 points
  - No double-counting same study
  - Ingredient alias matching
- [ ] Output includes `evidence_data.match_count` and list of matched studies

---

## P1-3: Harmful Additive Penalties

**Priority:** P1
**Reference File:** `data/harmful_additives.json`
**Why:** Easy to misapply and cause disputes.

### Risk Level → Deduction

| Risk Level | Deduction |
|------------|-----------|
| High | -3 |
| Moderate | -2 |
| Low | -1 |

### Cap Enforcement

**Critical:** Total harmful additive penalty MUST NOT exceed -5.

```python
# Enforcement
total_additive_penalty = sum(penalties)
capped_penalty = max(total_additive_penalty, -5)  # Cap at -5
```

### Evidence Output

```python
"harmful_additive_evidence": {
    "additives_detected": [
        {
            "additive_id": "TITANIUM_DIOXIDE",
            "matched_name": "Titanium Dioxide",
            "risk_level": "moderate",
            "penalty": -2,
            "matched_text": "titanium dioxide",
            "source_field": "otherIngredients[3]",
            "concerns": ["Potential carcinogen", "Banned in EU for food"]
        }
    ],
    "total_penalty_raw": -7,
    "cap_applied": true,
    "total_penalty_capped": -5,
    "notes": ["Penalty capped at -5 per scoring rules"]
}
```

### Exclusions

Do NOT flag as harmful:
- Natural colors (beet juice, turmeric, etc.)
- Colors already scored in color_indicators.json with "natural" category

### Done When

- [ ] Tests for:
  - Multiple additives with cap enforcement
  - Low/moderate/high scoring
  - Natural colors NOT flagged
  - Evidence includes matched_text and source_field
- [ ] Batch audit: Top 20 additives frequency looks reasonable

---

## P2-1: Synergy Clusters

**Priority:** P2 (only after P0 dosage normalization is complete)
**Reference File:** `data/synergy_cluster.json`
**Why:** Powerful but dependent on correct dosing.

### Prerequisites

- [ ] P0-1 Unit Conversion complete
- [ ] P0-2 Serving Basis Normalization complete
- [ ] P0-3 DV/RDA/UL Scoring complete

### Scoring Rules

Synergy bonus only applies if:
1. 2+ ingredients from same cluster are present
2. Each ingredient meets minimum effective dose threshold

### Schema Enhancement Needed

Add `min_effective_dose` to synergy_cluster.json:

```json
{
  "cluster_id": "BONE_HEALTH",
  "ingredients": [
    {
      "name": "Calcium",
      "min_effective_dose": 500,
      "unit": "mg"
    },
    {
      "name": "Vitamin D3",
      "min_effective_dose": 25,
      "unit": "mcg"
    },
    {
      "name": "Vitamin K2",
      "min_effective_dose": 45,
      "unit": "mcg"
    }
  ],
  "synergy_bonus": 3,
  "notes": "D3 enhances calcium absorption; K2 directs calcium to bones"
}
```

### Done When

- [ ] Tests for:
  - 2+ ingredient match with adequate doses
  - Underdosed ingredients (no bonus)
  - Tiered points based on completeness
- [ ] Dependency on P0 items verified

---

## P2-2: Manufacturer Violations

**Priority:** P2
**Reference Files:** `data/manufacturer_violations.json`, `data/top_manufacturers_data.json`
**Why:** Deterministic but requires robust name normalization.

### Manufacturer Name Normalization

- Create alias table for common variations
- Strip legal suffixes (Inc., LLC, Corp.)
- Handle parent/subsidiary relationships

### Recency Multipliers

| Violation Age | Multiplier |
|---------------|------------|
| < 1 year | 1.0 |
| 1-2 years | 0.8 |
| 2-3 years | 0.5 |
| 3-5 years | 0.3 |
| > 5 years | 0.1 |

### Penalty Cap

**Maximum:** -25 points (disqualification threshold)

### Done When

- [ ] Tests for:
  - Recency multipliers
  - Repeat violation modifier
  - Unresolved violation modifier
  - Cap enforcement at -25
  - Manufacturer alias matching
- [ ] Batch audit: Known violators correctly flagged

---

## Appendix: Test Fixtures

### Fixture Naming Convention

```
test_fixtures/
├── unit_conversion/
│   ├── vitamin_d_iu_to_mcg.json
│   ├── vitamin_a_forms.json
│   ├── vitamin_e_natural_vs_synthetic.json
│   └── cfu_normalization.json
├── serving_basis/
│   ├── single_serving.json
│   ├── multiple_serving_range.json
│   ├── fractional_serving.json
│   └── missing_serving.json
├── rda_ul/
│   ├── below_rda.json
│   ├── optimal_band.json
│   ├── over_ul.json
│   ├── no_ul_nutrient.json
│   └── age_sex_specific.json
├── proprietary_blend/
│   ├── full_disclosure.json
│   ├── partial_disclosure.json
│   ├── no_disclosure.json
│   └── multiple_blends.json
├── probiotic/
│   ├── high_cfu_at_expiration.json
│   ├── medium_cfu_at_manufacture.json
│   ├── strain_matched.json
│   ├── species_only.json
│   └── survivability_coating.json
├── clinical_evidence/
│   ├── single_match.json
│   ├── multiple_matches.json
│   ├── cap_at_15.json
│   └── no_double_count.json
└── harmful_additives/
    ├── multiple_with_cap.json
    ├── natural_colors_excluded.json
    └── risk_level_tiers.json
```

### Fixture Format

```json
{
  "fixture_id": "vitamin_d_iu_to_mcg_001",
  "description": "Convert 2000 IU Vitamin D3 to mcg",
  "input": {
    "nutrient": "Vitamin D3",
    "amount": 2000,
    "unit": "IU"
  },
  "expected_output": {
    "converted_amount": 50,
    "converted_unit": "mcg",
    "conversion_factor": 0.025,
    "conversion_rule_id": "vitamin_d3"
  }
}
```

---

## Contract Validation Rules

Add to `enrichment_contract_validator.py`:

```python
# P0-1: Unit Conversion
"vitamin_a_form_must_be_detected": {
    "condition": "If vitamin_a amount present, form must be detected or flagged",
    "fail_action": "reject"
}

# P0-3: RDA/UL
"ul_comparison_requires_normalized_units": {
    "condition": "UL comparison only valid after unit conversion to canonical unit",
    "fail_action": "reject"
}

# P0-4: Proprietary Blend
"blend_evidence_required": {
    "condition": "If penalty applied, evidence must include matched_text and source_field",
    "fail_action": "reject"
}

# P1-1: Probiotic
"cfu_confidence_required": {
    "condition": "CFU scoring must include confidence level",
    "fail_action": "warn"
}

# P1-3: Harmful Additives
"additive_cap_enforcement": {
    "condition": "Total additive penalty cannot exceed -5",
    "fail_action": "reject"
}
```

---

## Implementation Checklist

### Phase 1: Foundation (Week 1-2)
- [ ] Create `data/unit_conversions.json`
- [ ] Implement unit conversion functions with tests
- [ ] Update enrichment to output `dosage_conversion_evidence`

### Phase 2: Dosage Scoring (Week 2-3)
- [ ] Implement serving basis normalization
- [ ] Implement RDA/UL scorer with "no UL" handling
- [ ] Add `dosage_normalized` to enriched output

### Phase 3: Penalty Scoring (Week 3-4)
- [ ] Harden proprietary blend detection
- [ ] Add structured `proprietary_blend_evidence`
- [ ] Verify cap enforcement

### Phase 4: Enhancement Scoring (Week 4-5)
- [ ] Complete probiotic scoring with CFU confidence
- [ ] Implement clinical evidence tier scoring
- [ ] Harden harmful additive penalties with cap

### Phase 5: Validation (Week 5-6)
- [ ] Run batch audit on 500+ products
- [ ] Review all evidence outputs
- [ ] Fix edge cases identified in audit

---

## Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| Technical Lead | | | |
| QA Lead | | | |
| Product Owner | | | |

---

*Generated: 2026-01-07*
*Next Review: After Phase 1 completion*
