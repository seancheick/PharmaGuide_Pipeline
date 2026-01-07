# DSLD Supplement Scoring System - Complete Scoring Logic

**Version:** 3.4.0
**Last Updated:** 2025-12-04
**Author:** PharmaGuide Team

---

## Table of Contents
1. [Overview](#overview)
2. [Section A: Ingredient Quality (0-30 pts)](#section-a-ingredient-quality-0-30-pts)
3. [Section B: Safety & Purity (0-45 pts)](#section-b-safety--purity-0-45-pts)
4. [Section C: Evidence & Research (0-15 pts)](#section-c-evidence--research-0-15-pts)
5. [Section D: Brand Trust (0-8 pts)](#section-d-brand-trust-0-8-pts)
6. [Probiotic Bonus (0-10 pts)](#probiotic-bonus-0-10-pts)
7. [Section E: User Profile (0-20 pts)](#section-e-user-profile-0-20-pts)
8. [Score Calculation & Grade Scale](#score-calculation--grade-scale)
9. [Important Rules](#important-rules)

---

## Overview

### Total Score Structure
| Component | Max Points | Calculated Where |
|-----------|------------|------------------|
| Section A: Ingredient Quality | 30 | Server |
| Section B: Safety & Purity | 45 | Server |
| Section C: Evidence & Research | 15 | Server |
| Section D: Brand Trust | 8 | Server |
| **Subtotal (Server)** | **80** | Server |
| Probiotic Bonus | +10 | Server (applies before ceiling) |
| Section E: User Profile | 20 | On-device |
| **Total Maximum** | **100** | Combined |

### Key Principle
- Server calculates 80 points (Sections A-D)
- Probiotic products can earn up to +10 bonus, but final server score is **capped at 80**
- Section E (20 pts) is calculated on-device based on user health goals
- Display format: `65/80` with `/100 equivalent` shown underneath

---

## Section A: Ingredient Quality (0-30 pts)

Section A evaluates the bioavailability, quality, and formulation excellence of ingredients.

### A1: Bioavailability & Form Quality (0-15 pts)

**Calculation:** Weighted average of ingredient scores × dosage importance

```
Score = Σ(ingredient_score × dosage_importance) / Σ(dosage_importance)
```

| Factor | Description |
|--------|-------------|
| `ingredient_score` | bio_score (0-15) + natural_bonus (0-3) |
| `dosage_importance` | Weight based on clinical dosage (0.0-2.0) |
| Cap | Maximum 15 points |

**Special Rule - Multivitamin Floor:**
- Multivitamins get a floor of `15 × 0.7 = 10.5` minimum
- Prevents unfairly penalizing diverse formulas with many low-bioavailability ingredients

---

### A2: Multiple Premium Forms (0-3 pts)

**Bonus for high-quality ingredient forms**

| Condition | Points |
|-----------|--------|
| Each ingredient with `bio_score > 12` | +0.5 pts |
| **Maximum** | 3 pts |

**Example:** 6 premium forms = 6 × 0.5 = 3 pts (capped)

---

### A3: Enhanced Delivery System (0-3 pts)

**Points based on delivery system tier (matched from `data/enhanced_delivery.json`)**

| Tier | Points | Systems |
|------|--------|---------|
| Tier 1 | 3 | liposomal, lypospheric, vesisorb, capsoil, nanoemulsion, phytosome, double liposomal, capsule-in-capsule |
| Tier 2 | 2 | lozenge, sublingual, oral spray, chelated, traacs, albion, enteric-coated, micronized, time-release, sustained-release, liquid, tincture |
| Tier 3 | 1 | gummy, powder, effervescent, softgel, microencapsulation, beadlet, cold-processed, hydrolyzed, fermented |
| No match | 0 | Standard tablets, capsules without special tech |

**Rule:** Only the highest-tier delivery system counts. Matching is done against product name, label text, and ingredient forms (case-insensitive).

---

### A4: Absorption Enhancer Present (0-3 pts)

**Bonus when absorption enhancer enhances a nutrient present in the product**

| Condition | Points |
|-----------|--------|
| Enhancer present AND enhanced nutrient present | +3 pts |
| Otherwise | 0 pts |

**Examples of enhancers:**
- BioPerine (piperine) enhances curcumin, CoQ10, vitamin B6
- Black pepper extract enhances turmeric absorption
- Vitamin C enhances iron absorption

**Rule:** Award once only, even if multiple enhancers present.

---

### A5: Formulation Excellence (0-9 pts)

#### A5a: USDA Organic Certified (+2 pts)
| Condition | Points |
|-----------|--------|
| USDA Organic seal verified | +2 pts |

#### A5b: Standardized Botanicals (+2 pts)
| Condition | Points |
|-----------|--------|
| At least 1 standardized botanical extract | +2 pts |

**What qualifies:** Extracts with guaranteed active compound percentages (e.g., "standardized to 95% curcuminoids")

#### A5c: Synergy Clusters (0-5 pts)

**Points based on number of synergistic ingredients in a cluster**

| Ingredients in Cluster | Points |
|------------------------|--------|
| 5+ | 5 pts |
| 4 | 3 pts |
| 3 | 2 pts |
| 2 | 1 pt |

**Synergy cluster examples:**
- Bone Health: Calcium + Vitamin D + Vitamin K2 + Magnesium
- Antioxidant: Vitamin C + Vitamin E + Selenium + CoQ10
- B-Complex: B1 + B2 + B6 + B12 + Folate

**Rule:** Only the best-matching cluster counts (not cumulative).

---

## Section B: Safety & Purity (0-45 pts)

Section B evaluates product safety through penalties and bonuses. **Starts at 45, then adjusts.**

### B1: Contaminants & Additives (Deductions Only)

#### B1a: Banned/Recalled Substances

| Severity | Penalty | Effect |
|----------|---------|--------|
| Critical | -20 pts | **IMMEDIATE FAIL** flag set |
| High | -15 pts | |
| Moderate | -10 pts | |

**Critical substances:** Ephedra, DMAA, BMPEA, phenolphthalein

---

#### B1b: Harmful Additives

| Severity | Penalty per Additive |
|----------|---------------------|
| High | -2 pts |
| Moderate | -1 pt |
| Low | -0.5 pts |

**Total Cap:** -5 pts maximum (prevents over-penalization)

**Deduplication Rule:** Additives with same `additive_id` only count once.
- Example: Magnesium Stearate + Stearic Acid = 1 penalty (same ADD_STEARIC_ACID)

---

#### B1c: Undeclared Allergens

| Severity | Penalty |
|----------|---------|
| High | -2 pts |
| Moderate | -1.5 pts |
| Low | -1 pt |

**Total Cap:** -2 pts maximum

---

### B2: Allergen & Dietary Compliance (0-4 pts max)

| Certification | Points |
|--------------|--------|
| Allergen-Free Claim (verified) | +2 pts |
| Gluten-Free Certified | +1 pt |
| Vegan/Vegetarian | +1 pt |
| "May Contain" Warning | -2 pts |

---

### B3: Quality Certifications (0-16 pts max)

#### Third-Party Testing (0-10 pts)

| Certification | Points | Max |
|--------------|--------|-----|
| Each recognized program | +5 pts | 2 programs max |

**Recognized Programs:**
- NSF International
- USP Verified
- ConsumerLab Approved
- BSCG Certified Drug Free
- Informed Sport

**Example:** NSF + USP = 5 + 5 = 10 pts

---

#### GMP Certified Facility (+4 pts)

| Condition | Points |
|-----------|--------|
| cGMP certified manufacturing | +4 pts |

---

#### Batch Traceability / COA (+2 pts)

| Condition | Points |
|-----------|--------|
| COA publicly available, QR code, or lot lookup | +2 pts |

---

### B4: Proprietary Blend Penalty (0 to -15 pts)

**Penalty scales based on hidden ingredient ratio**

| Hidden Ratio | Penalty |
|-------------|---------|
| 75%+ of ingredients hidden | -15 pts |
| 50-74% hidden | -10 pts |
| 25-49% hidden | -5 pts |
| Under 25% hidden | -2 pts |
| No proprietary blends | 0 pts |

#### Clinical Evidence Mitigation

**Penalty reduction for clinically-validated blends:**

| Evidence Type | Penalty Multiplier |
|--------------|-------------------|
| Probiotic with clinical strains (K12, LGG, etc.) | × 0.5 (50% reduction) |
| Herbal blend with Tier 1/2 clinical evidence | × 0.6 (40% reduction) |
| Contains standardized botanical extracts | × 0.7 (30% reduction) |

**Rationale:** Per Labdoor/ConsumerLab methodology - clinically-validated formulations are protecting IP, not deceiving consumers.

**Example:**
- Raw penalty: -10 pts (50% hidden)
- Contains clinical probiotic strains
- Reduced penalty: -10 × 0.5 = -5 pts

---

## Section C: Evidence & Research (0-15 pts)

**v3.4.0 - Enhanced Evidence Hierarchy**

Section C rewards clinical evidence supporting ingredient efficacy using a hierarchy aligned with industry best practices from EFSA, Natural Medicines (TRC), GRADE (NIH/WHO), and Examine.com.

### Evidence Hierarchy (NEW in v3.4.0)

The key insight: **Product-level clinical trials are more valuable than ingredient-level studies.**

| Hierarchy Level | Multiplier | Description |
|----------------|------------|-------------|
| **Product-Level** | 1.0x | Clinical trials on the exact finished product (gold standard) |
| **Branded Ingredient** | 0.8x | Patented ingredient with own RCTs (e.g., KSM-66, Meriva, Longvida) |
| **Ingredient-Human** | 0.65x | Generic ingredient human studies (e.g., "vitamin D" any form) |
| **Strain-Level Probiotic** | 0.6x | Individual strain evidence (not the exact product combo) |
| **Preclinical** | 0.3x | Animal/in vitro studies only |

### Base Points by Study Type

| Study Type | Base Points |
|------------|-------------|
| Systematic Review / Meta-Analysis | 6 pts |
| Multiple RCTs (2+) | 5 pts |
| Single RCT | 4 pts |
| Observational Study | 2 pts |
| Clinical Strain (probiotic) | 4 pts |
| Animal Study | 2 pts |
| In Vitro | 1 pt |

### Score Calculation

```
Score = Base Points × Hierarchy Multiplier
```

**Examples:**
| Evidence | Base | Multiplier | Score |
|----------|------|------------|-------|
| Seed DS-01 product RCT | 5 | 1.0 | 5.0 |
| KSM-66 branded meta-analysis | 6 | 0.8 | 4.8 |
| Generic Vitamin D RCT | 4 | 0.65 | 2.6 |
| LGG strain clinical | 4 | 0.6 | 2.4 |
| New herb animal study | 2 | 0.3 | 0.6 |

---

### Special Bonuses & Penalties

#### Product Trial Bonus (+2 pts)
| Condition | Bonus |
|-----------|-------|
| Product has its own published RCT(s) | +2 pts |

This rewards companies like Seed Health that invest in product-specific clinical trials.

---

#### Per-Ingredient Cap (5 pts max)
No single ingredient can contribute more than 5 pts. Prevents one well-studied vitamin from maxing out the score.

---

#### Consistency Penalty (-1 pt)
| Condition | Penalty |
|-----------|---------|
| Evidence for ingredient is mixed/inconsistent | -1 pt |

Per Examine.com methodology - inconsistent findings reduce confidence.

---

### Unsubstantiated Claims Penalty

| Condition | Penalty |
|-----------|---------|
| Product has unsubstantiated health claims | -5 pts |

**Applied once only** regardless of number of claims.

---

### Why This Hierarchy Matters

**Probiotic Example:** A product containing LGG (clinically studied strain) gets 0.6x multiplier because:
- Per Frontiers 2018 meta-analysis: efficacy is strain-specific AND formulation-specific
- A multi-strain product may behave differently than individual strain studies
- Only products with their own trials (like Seed DS-01) get 1.0x + bonus

**Branded vs Generic Example:**
- KSM-66 Ashwagandha (branded, patented, with RCTs) → 0.8x multiplier
- Generic ashwagandha root extract → 0.65x multiplier (still human studies, but less specific)

**Sources:**
- [EFSA Health Claims](https://www.efsa.europa.eu/en/topics/topic/health-claims)
- [Natural Medicines (TRC)](https://naturalmedicines.therapeuticresearch.com/safety-and-effectiveness-rating.aspx)
- [Examine.com Grades](https://examine.com/about/grades/)
- [GRADE (NIH/WHO)](https://pmc.ncbi.nlm.nih.gov/articles/PMC2981887/)
- [Probiotic Strain-Specificity (Frontiers)](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0209205)

---

## Section D: Brand Trust (0-8 pts)

Section D evaluates manufacturer reputation and transparency.

### D1: Top-Tier Manufacturer (+3 pts)

| Condition | Points |
|-----------|--------|
| Matched to top manufacturers list | +3 pts |
| Fuzzy match with confidence < 85% | 0 pts |

**Top Manufacturers List includes:** Thorne, NOW Foods, Jarrow Formulas, Life Extension, Pure Encapsulations, Garden of Life, Nordic Naturals, etc.

---

### D2: Physician/Formulator Credibility (+1 pt)

| Condition | Points |
|-----------|--------|
| Physician-formulated or credentialed formulator | +1 pt |

---

### D3: High-Regulation Country (+1 pt)

| Condition | Points |
|-----------|--------|
| Made in high-regulation country | +1 pt |

**Qualifying Countries:** USA, EU, Canada, Australia, Japan, UK, Germany, Switzerland

---

### D4: Sustainable Packaging (+1 pt)

| Condition | Points |
|-----------|--------|
| Sustainable/recyclable packaging claim | +1 pt |

---

### D5: Manufacturer Violations (Deductions)

| Condition | Penalty |
|-----------|---------|
| Violations in last 10 years | Sum of deductions |
| **Cap** | -20 pts maximum |

**Violation Examples:**
- FDA Warning Letter: -5 to -15 pts
- Product Recall: -10 pts
- Consent Decree: -20 pts

---

### Note on Full Disclosure

**REMOVED from scoring (was +2 pts)** - Double-counting issue.
- The absence of proprietary blends already rewards by NOT getting the -15 penalty in B4
- Adding +2 for "full disclosure" would reward the same thing twice

---

## Probiotic Bonus (0-10 pts)

**Only applies if `is_probiotic_product = true`**

### CFU Bonus (+4 pts)

| Condition | Points |
|-----------|--------|
| ≥10 Billion CFU **guaranteed at expiration** | +4 pts |
| ≥10 Billion at manufacture (not expiration) | 0 pts |

**Important:** Must be guaranteed at EXPIRATION, not time of manufacture.

---

### Strain Diversity (0-4 pts)

| Distinct Strains | Points |
|-----------------|--------|
| 8+ strains | +4 pts |
| 4-7 strains | +2 pts |
| < 4 strains | 0 pts |

---

### Clinical Strains (+3 pts)

| Condition | Points |
|-----------|--------|
| Contains clinically studied strain(s) | +3 pts |

**Clinically Studied Strains Include:**
- Lactobacillus rhamnosus GG (LGG)
- Lactobacillus reuteri
- Bifidobacterium BB-12
- Lactobacillus acidophilus NCFM
- Streptococcus salivarius K12 & M18
- Bacillus coagulans GBI-30
- Lactobacillus casei Shirota

---

### Prebiotic Pairing (+3 pts)

| Condition | Points |
|-----------|--------|
| Contains prebiotic fiber/compound | +3 pts |

**Prebiotics Include:** Inulin, FOS, GOS, lactulose, resistant starch

---

### Survivability Coating (+2 pts)

| Condition | Points |
|-----------|--------|
| Delayed-release, enteric coating, or patented delivery | +2 pts |

**Examples:** BIO-tract, DRcaps, MAKTrek 3-D

---

### Probiotic Bonus Maximum

| Total Possible | Cap |
|----------------|-----|
| 4 + 4 + 3 + 3 + 2 = 16 pts | Capped at 10 pts |

---

## Section E: User Profile (0-20 pts)

**Calculated on-device, not in this script**

Section E personalizes scores based on user health goals and conditions.

| Factor | Points |
|--------|--------|
| Matches primary health goal | Up to +10 pts |
| Matches secondary health goals | Up to +5 pts |
| Ingredient interactions with user medications | Deductions |
| Allergen conflicts with user profile | Deductions |

---

## Score Calculation & Grade Scale

### Final Score Calculation

```python
# 1. Calculate raw sections
raw_total = Section_A + Section_B + Section_C + Section_D

# 2. Add probiotic bonus (if applicable)
if is_probiotic:
    raw_total += probiotic_bonus

# 3. Apply floor and ceiling
final_score = max(min(raw_total, 80), 10)

# 4. Convert to 100-point equivalent
score_100 = (final_score / 80) * 100
```

### Score Boundaries

| Boundary | Value |
|----------|-------|
| Floor | 10/80 (no product below this) |
| Ceiling | 80/80 (server max) |
| With Section E | 100/100 possible |

---

### Letter Grade Scale

Based on 100-point equivalent:

| Grade | Score Range | Description |
|-------|-------------|-------------|
| A+ | 90-100 | Exceptional |
| A | 85-89 | Excellent |
| A- | 80-84 | Very Good |
| B+ | 77-79 | Good |
| B | 73-76 | Above Average |
| B- | 70-72 | Average |
| C+ | 67-69 | Below Average |
| C | 63-66 | Fair |
| C- | 60-62 | Poor |
| D | 50-59 | Very Poor |
| F | 0-49 | Fail |

---

## Important Rules

### 1. No Double-Counting
A bonus or penalty should only apply ONCE.
- ❌ Award +2 for "no proprietary blend" AND avoid -15 penalty
- ✅ Only avoid the -15 penalty (absence is the reward)

### 2. Config-Driven
ALL point values come from `scoring_config.json`. No hardcoded numbers in Python.

### 3. Every Subcategory Appears
All subcategories appear in output, even if score is 0 or N/A.

### 4. Penalty Caps
Caps prevent over-penalization from a single issue:
- Harmful additives: max -5 pts
- Undeclared allergens: max -2 pts
- Proprietary blends: max -15 pts
- Manufacturer violations: max -20 pts

### 5. Deduplication
Duplicate items (same ID) only count once for penalties.

### 6. Immediate Fail Flag
Critical banned substances set `immediate_fail = true`. Product still gets scored but flagged for review.

---

## Quick Reference: All Points

### Bonuses (Positive Points)

| Category | Item | Max Points |
|----------|------|------------|
| A1 | Bioavailability | +15 |
| A2 | Premium Forms | +3 |
| A3 | Delivery System | +3 |
| A4 | Absorption Enhancer | +3 |
| A5a | USDA Organic | +2 |
| A5b | Standardized Botanicals | +2 |
| A5c | Synergy Clusters | +5 |
| B2 | Allergen-Free Claim | +2 |
| B2 | Gluten-Free | +1 |
| B2 | Vegan/Vegetarian | +1 |
| B3 | Third-Party Testing | +10 |
| B3 | GMP Certified | +4 |
| B3 | Batch Traceability | +2 |
| C | Clinical Evidence | +15 |
| D | Top Manufacturer | +3 |
| D | Physician-Formulated | +1 |
| D | High-Reg Country | +1 |
| D | Sustainable Packaging | +1 |
| Probiotic | CFU ≥10B at Expiration | +4 |
| Probiotic | Strain Diversity | +4 |
| Probiotic | Clinical Strains | +3 |
| Probiotic | Prebiotic Pairing | +3 |
| Probiotic | Survivability Coating | +2 |

### Penalties (Negative Points)

| Category | Item | Penalty |
|----------|------|---------|
| B1 | Critical Banned Substance | -20 + FAIL |
| B1 | High Severity Banned | -15 |
| B1 | Moderate Banned | -10 |
| B1 | Harmful Additives | -0.5 to -2 each (cap -5) |
| B1 | Undeclared Allergens | -1 to -2 each (cap -2) |
| B2 | "May Contain" Warning | -2 |
| B4 | Proprietary Blend 75%+ | -15 |
| B4 | Proprietary Blend 50-74% | -10 |
| B4 | Proprietary Blend 25-49% | -5 |
| B4 | Proprietary Blend <25% | -2 |
| C | Unsubstantiated Claims | -5 |
| D | Manufacturer Violations | varies (cap -20) |

---

## Example Score Calculation

**Product:** "Premium Probiotic Plus with Organic Elderberry"

### Section A: Ingredient Quality
- A1: Weighted avg bioavailability = 11.5/15
- A2: 2 premium forms × 0.5 = 1.0/3
- A3: Lozenge (Tier 2) = 2/3
- A4: No absorption enhancer = 0/3
- A5: USDA Organic (+2) + Synergy 3-cluster (+2) = 4/9
- **Section A Total: 18.5/30**

### Section B: Safety & Purity (starts at 45)
- B1: No banned, 1 moderate additive = -1 (capped)
- B2: Gluten-free (+1), Vegan (+1) = +2
- B3: NSF certified (+5), GMP (+4) = +9
- B4: No proprietary blends = 0
- **Section B Total: 45 - 1 + 2 + 9 = 55 → capped at 45/45**

### Section C: Evidence & Research
- 3 ingredients with RCTs = 3 × 3 = 9/15
- **Section C Total: 9/15**

### Section D: Brand Trust
- Top manufacturer (+3)
- Made in USA (+1)
- Sustainable packaging (+1)
- **Section D Total: 5/8**

### Probiotic Bonus
- 12B CFU at expiration (+4)
- 6 strains (+2)
- Contains LGG (+3)
- Prebiotic inulin (+3)
- **Probiotic Bonus: 12 → capped at 10**

### Final Calculation
```
Raw: 18.5 + 45 + 9 + 5 + 10 = 87.5
After ceiling: 80/80
100-equivalent: 100/100
Grade: A+
```

---

*Document generated by PharmaGuide Scoring System v3.4.0*
