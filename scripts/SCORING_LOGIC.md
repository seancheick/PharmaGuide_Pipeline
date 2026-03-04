# DSLD Supplement Scoring System - Complete Scoring Logic

**Version:** 5.0.0
**Last Updated:** 2026-03-03
**Author:** PharmaGuide Team

---

## Table of Contents
1. [Overview](#overview)
2. [Section A: Ingredient Quality (0-25 pts)](#section-a-ingredient-quality-0-25-pts)
3. [Section B: Safety & Purity (0-30 pts)](#section-b-safety--purity-0-30-pts)
4. [Section C: Evidence & Research (0-20 pts)](#section-c-evidence--research-0-20-pts)
5. [Section D: Brand Trust (0-5 pts)](#section-d-brand-trust-0-5-pts)
6. [Probiotic Bonus (0-10 pts)](#probiotic-bonus-0-10-pts)
7. [Section E: User Profile (0-20 pts)](#section-e-user-profile-0-20-pts)
8. [Score Calculation & Grade Scale](#score-calculation--grade-scale)
9. [Important Rules](#important-rules)

---

## Overview

### Total Score Structure
| Component | Max Points | Calculated Where |
|-----------|------------|------------------|
| Section A: Ingredient Quality | 25 | Server |
| Section B: Safety & Purity | 30 | Server |
| Section C: Evidence & Research | 20 | Server |
| Section D: Brand Trust | 5 | Server |
| **Subtotal (Server)** | **80** | Server |
| Probiotic Bonus | +10 | Server (folded into Section A) |
| Section E: User Profile | 20 | On-device |
| **Total Maximum** | **100** | Combined |

### Key Principle
- Server calculates 80 points (Sections A-D)
- Probiotic products can earn up to +10 bonus, but final server score is **capped at 80**
- Section E (20 pts) is calculated on-device based on user health goals
- Display format: `65/80` with `/100 equivalent` shown underneath

---

## Section A: Ingredient Quality (0-25 pts)

Section A evaluates the bioavailability, quality, and formulation excellence of ingredients.

```
A = min(25, A1 + A2 + A3 + A4 + A5 + A6 + probiotic_bonus)
```

### A1: Bioavailability & Form Quality (0-15 pts)

**Calculation:** Weighted average of ingredient scores × dosage importance

```
Score = Σ(ingredient_score × dosage_importance) / Σ(dosage_importance)
A1 = clamp(0, 15, (weighted_avg / 18) * 15)
```

| Factor | Description |
|--------|-------------|
| `ingredient_score` | IQM score field (0-18) |
| `dosage_importance` | Weight based on clinical dosage (0.0-2.0) |
| Cap | Maximum 15 points |

**Exclusions:** Blend containers (`is_proprietary_blend: true`) are excluded from A1. Their cost is captured by B5.

**Supplement-type effects:**
- `single` / `single_nutrient`: all weights forced to `1.0`
- `multivitamin`: smoothing applied — `avg = 0.7*avg + 0.3*9.0`
- Unmapped ingredients: fallback `score=9.0`, `weight=1.0`

---

### A2: Multiple Premium Forms (0-3 pts)

**Bonus for high-quality ingredient forms**

| Condition | Points |
|-----------|--------|
| Count unique ingredients with `score >= 14` (minus 1) × 0.5 | up to 3 pts |
| **Maximum** | 3 pts |

**Note:** Excludes blend containers and requires usable individual dose.

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

### A5: Formulation Excellence (0-3 pts)

```
A5 = min(3, A5a + A5b + A5c + A5d)
```

#### A5a: USDA Organic Certified (+1 pt)
| Condition | Points |
|-----------|--------|
| USDA Organic seal verified or valid claim path | +1 pt |

#### A5b: Standardized Botanicals (+1 pt)
| Condition | Points |
|-----------|--------|
| At least 1 standardized botanical extract | +1 pt |

**What qualifies:** Extracts with guaranteed active compound percentages (e.g., "standardized to 95% curcuminoids")

#### A5c: Synergy Clusters (+1 pt)
| Condition | Points |
|-----------|--------|
| Qualifying synergy cluster detected | +1 pt |

**Synergy cluster examples:**
- Bone Health: Calcium + Vitamin D + Vitamin K2 + Magnesium
- Antioxidant: Vitamin C + Vitamin E + Selenium + CoQ10

#### A5d: Non-GMO Verified (+0.5 pts, gated)
| Condition | Points |
|-----------|--------|
| Non-GMO Project Verified (requires `enable_non_gmo_bonus: true`) | +0.5 pts |

---

### A6: Single-Ingredient Efficiency (0-3 pts)

**Only applies when `supp_type in {"single", "single_nutrient"}`**

Uses the highest bio score among scorable ingredients:

| bio_score threshold | Points |
|---------------------|--------|
| >= 16 | 3 pts |
| >= 14 | 2 pts |
| >= 12 | 1 pt |
| < 12 | 0 pts |

---

## Section B: Safety & Purity (0-30 pts)

Section B evaluates product safety through penalties and bonuses.

```
B_raw = base_score + bonuses - penalties
B = clamp(0, 30, B_raw)

base_score = 25
bonuses  = min(5, B3 + B4a + B4b + B4c + B_hypoallergenic)
penalties = B0_moderate + B1 + B2 + B5 + B6
```

### B0: Immediate Safety Gate (Pre-Section)

The B0 gate runs before scoring. It checks `contaminant_data.banned_substances.substances[]`.

**Match-type semantics:**
- Hard-fail eligible types: `exact`, `alias`
- Non-hard-fail types: `token_bounded` and others -> review-only flag

**Status-based logic (v5.0 schema):**

| Status | Effect | Flag |
|--------|--------|------|
| `banned` + exact/alias | Immediate `UNSAFE` verdict | — |
| `recalled` + exact/alias | Immediate `BLOCKED` verdict | — |
| `high_risk` + exact/alias | -10 pt penalty, `CAUTION` verdict | `B0_HIGH_RISK_SUBSTANCE` |
| `watchlist` + exact/alias | -5 pt penalty, `CAUTION` verdict | `B0_WATCHLIST_SUBSTANCE` |
| Any non-exact/alias match | Review only | `BANNED_MATCH_REVIEW_NEEDED` |

**Fallback for pre-5.0 enriched data (severity-based):**

| severity_level | Effect | Flag |
|----------------|--------|------|
| `critical` / `high` | Immediate `UNSAFE` verdict | — |
| `moderate` | -10 pt penalty | `B0_MODERATE_SUBSTANCE` |
| `low` | Advisory only | `B0_LOW_SUBSTANCE` |

If a hard fail fires (blocked/unsafe), all moderate/low/watchlist flags are stripped.

---

### B1: Contaminants & Additives (Deductions Only)

#### B1a: Banned/Recalled Substances (status-based, v5.0)

| Status | Penalty | Effect |
|----------|---------|--------|
| banned | **FAIL** | Immediate UNSAFE verdict |
| recalled | **FAIL** | Immediate BLOCKED verdict |
| high_risk | -10 pts | CAUTION verdict |
| watchlist | -5 pts | CAUTION verdict |

**Banned substances:** Ephedra, DMAA, BMPEA, phenolphthalein, sibutramine

---

#### B1b: Harmful Additives

| Severity | Penalty per Additive |
|----------|---------------------|
| Critical | -3 pts |
| High | -2 pts |
| Moderate | -1 pt |
| Low | -0.5 pts |

**Total Cap:** -8 pts maximum (prevents over-penalization)

**Deduplication Rule:** Additives with same `additive_id` only count once (highest severity wins).
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

### B2: Allergen Presence (max penalty -2 pts)

| Severity | Penalty |
|----------|---------|
| High | -2 pts |
| Moderate | -1.5 pts |
| Low | -1 pt |

**Total Cap:** -2 pts maximum

---

### B3: Claim Compliance (bonus, feeds into shared bonus pool)

| Certification | Points |
|--------------|--------|
| Allergen-Free Claim (verified) | +2 pts |
| Gluten-Free Certified | +1 pt |
| Vegan/Vegetarian | +1 pt |

**Contradiction detection:** "May contain" warnings invalidate allergen-free/gluten-free claims. Gelatin/bovine/porcine invalidates vegan claim. Adds `LABEL_CONTRADICTION_DETECTED` flag.

---

### B4: Quality Certifications (bonus, feeds into shared bonus pool)

#### B4a: Named Programs (max 15 pts)
| Certification | Points | Max |
|--------------|--------|-----|
| Each recognized program | +5 pts | 3 programs max |

**Recognized Programs:** NSF, USP, ConsumerLab, BSCG, Informed Sport, IFOS (omega products only)

#### B4b: GMP (+4 pts max)
| Condition | Points |
|-----------|--------|
| NSF GMP certified or `gmp_level == "certified"` | +4 pts |
| FDA registered or `gmp_level == "fda_registered"` | +2 pts |

#### B4c: Batch Traceability (+2 pts max)
| Condition | Points |
|-----------|--------|
| COA publicly available | +1 pt |
| Batch lookup or QR code | +1 pt |

**Shared bonus pool cap:** All B3 + B4 bonuses combined are capped at 5 pts total.

---

### B5: Proprietary Blend Disclosure Penalty (0 to -10 pts)

**Three-tier disclosure model (per 21 CFR 101.36):**

| Disclosure Level | Definition | Presence Penalty | Proportional Coef |
|-----------------|-----------|-----------------|-------------------|
| `full` | Every sub-ingredient has individual amount | 0 | 0 |
| `partial` | Total declared + subs listed, no individual amounts | 1 | 3 |
| `none` | Missing total, or missing sub-list | 2 | 5 |

**Per-blend penalty formula:**
```
hidden_mass_mg = max(blend_total_mg - disclosed_child_mg_sum, 0)
impact = clamp(0, 1, hidden_mass_mg / total_active_mg)
if hidden_mass_mg > 0 and impact < 0.1: impact = 0.1

blend_penalty = presence_penalty + proportional_coef * impact
B5 = clamp(0, 10, sum(blend_penalty))
```

**Penalty ranges by disclosure level:**

| Disclosure | Min (tiny blend) | Max (100% of product) |
|---|---|---|
| none | 2.5 | 7.0 |
| partial | 1.3 | 4.0 |
| full | 0.0 | 0.0 |

---

## Section C: Evidence & Research (0-20 pts)

Section C rewards clinical evidence supporting ingredient efficacy using a hierarchy aligned with industry best practices from EFSA, Natural Medicines (TRC), GRADE (NIH/WHO), and Examine.com.

### Evidence Hierarchy

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

#### Per-Ingredient Cap (7 pts max)
No single ingredient can contribute more than 7 pts. Prevents one well-studied vitamin from maxing out the score.

---

#### Consistency Penalty (-1 pt)
| Condition | Penalty |
|-----------|---------|
| Evidence for ingredient is mixed/inconsistent | -1 pt |

Per Examine.com methodology - inconsistent findings reduce confidence.

---

### B6: Marketing Claims Penalty (max -5 pts)

| Condition | Penalty |
|-----------|---------|
| Product has unsubstantiated disease/health claims | -5 pts |

**Applied once only** regardless of number of claims. Adds `DISEASE_CLAIM_DETECTED` flag.

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

## Section D: Brand Trust (0-5 pts)

Section D evaluates manufacturer reputation and transparency.

```
D = min(5, D1 + D2 + min(2.0, D3 + D4 + D5))
```

### D1: Trusted Manufacturer (+2 pts)

| Condition | Points |
|-----------|--------|
| Exact match to trusted manufacturers list | +2 pts |
| Middle-tier (gated, requires `enable_d1_middle_tier: true`) | +1 pt |
| No match | 0 pts |

**Top Manufacturers List includes:** Thorne, NOW Foods, Jarrow Formulas, Life Extension, Pure Encapsulations, Garden of Life, Nordic Naturals, etc.

---

### D2: Full Disclosure (+1 pt)

| Condition | Points |
|-----------|--------|
| All active ingredients have a dose AND no hidden/partial blends | +1 pt |

---

### D3: Physician/Formulator Credibility (+0.5 pts)

| Condition | Points |
|-----------|--------|
| Physician-formulated or credentialed formulator | +0.5 pts |

---

### D4: High-Regulation Country (+1 pt)

| Condition | Points |
|-----------|--------|
| Made in high-regulation country | +1 pt |

**Qualifying Countries:** USA, EU, UK, Germany, Switzerland, Japan, Canada, Australia, New Zealand, Norway, Sweden, Denmark

---

### D5: Sustainable Packaging (+0.5 pts)

| Condition | Points |
|-----------|--------|
| Sustainable/recyclable packaging claim | +0.5 pts |

**Note:** D3 + D4 + D5 combined are capped at 2.0. Total D capped at 5.

---

### Manufacturer Violation Penalty (Post-Section)

| Condition | Penalty |
|-----------|---------|
| Manufacturer has documented violations | Sum of deductions |
| **Floor** | -25 pts maximum |

Applied directly to `quality_raw` after section sum. Adds `MANUFACTURER_VIOLATION` flag.

---

## Probiotic Bonus (folded into Section A)

Applies when `supp_type == "probiotic"` or when non-probiotic products pass strict evidence gates (if `allow_non_probiotic_probiotic_bonus_with_strict_gate` enabled).

### Default Mode (max 3 pts, current)

Gate: `probiotic_extended_scoring: false` (current config)

| Component | Condition | Points |
|-----------|-----------|--------|
| CFU | total_billion > 1 | +1 pt |
| Diversity | strain_count >= 3 | +1 pt |
| Prebiotic | Contains inulin/FOS/GOS | +1 pt |

---

### Extended Mode (max 10 pts, gated)

Gate: `probiotic_extended_scoring: true`

| Component | Condition | Points |
|-----------|-----------|--------|
| CFU | >= 50B | 4 |
| CFU | >= 10B | 3 |
| CFU | > 1B | 2 |
| CFU | > 0 | 1 |
| Diversity | >= 10 strains | 4 |
| Diversity | >= 6 strains | 3 |
| Diversity | >= 3 strains | 2 |
| Diversity | > 0 strains | 1 |
| Clinical strains | >= 5 known | 3 |
| Clinical strains | >= 3 known | 2 |
| Clinical strains | >= 1 known | 1 |
| Prebiotic | count capped to 3 | up to 3 |
| Survivability | delayed release / enteric / acid resistant | 2 |

**Known clinical strain tokens:** `lgg`, `bb-12`, `ncfm`, `reuteri`, `k12`, `m18`, `coagulans`, `shirota`

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
quality_raw = Section_A + Section_B + Section_C + Section_D + violation_penalty

# 2. Clamp to [0, 80]
quality_score = clamp(0, 80, quality_raw)

# 3. Convert to 100-point equivalent
score_100_equivalent = (quality_score / 80) * 100
```

### Score Boundaries

| Boundary | Value |
|----------|-------|
| Floor | 0/80 |
| Ceiling | 80/80 (server max) |
| With Section E | 100/100 possible |

---

### Grade Scale

Based on 100-point equivalent. Not assigned for `BLOCKED`, `UNSAFE`, or `NOT_SCORED` verdicts.

| score_100_equivalent | Grade |
|---------------------|-------|
| >= 90 | Exceptional |
| >= 80 | Excellent |
| >= 70 | Good |
| >= 60 | Fair |
| >= 50 | Below Avg |
| >= 32 | Low |
| < 32 | Very Poor |

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
- Allergen presence: max -2 pts
- Proprietary blend disclosure: max -10 pts
- Disease/marketing claims: max -5 pts
- Manufacturer violations: floor -25 pts

### 5. Deduplication
Duplicate items (same ID) only count once for penalties.

### 6. Immediate Fail / Block
- `banned` status -> `UNSAFE` verdict (score = 0)
- `recalled` status -> `BLOCKED` verdict (score = null)
- `high_risk` / `watchlist` -> `CAUTION` verdict with point penalty

---

## Quick Reference: All Points

### Bonuses (Positive Points)

| Category | Item | Max Points |
|----------|------|------------|
| A1 | Bioavailability | +15 |
| A2 | Premium Forms | +3 |
| A3 | Delivery System | +3 |
| A4 | Absorption Enhancer | +3 |
| A5 | Formulation Excellence (organic, botanical, synergy, non-GMO) | +3 |
| A6 | Single-Ingredient Efficiency | +3 |
| B3 | Claim Compliance (allergen-free, gluten-free, vegan) | +4 |
| B4a | Named Cert Programs | +15 |
| B4b | GMP Certified | +4 |
| B4c | Batch Traceability | +2 |
| B bonus pool cap | All B bonuses combined | capped at 5 |
| C | Clinical Evidence | +20 |
| D1 | Trusted Manufacturer | +2 |
| D2 | Full Disclosure | +1 |
| D3 | Physician-Formulated | +0.5 |
| D4 | High-Reg Country | +1 |
| D5 | Sustainable Packaging | +0.5 |
| Probiotic (default) | CFU + Diversity + Prebiotic | +3 |
| Probiotic (extended, gated) | Full probiotic module | +10 |

### Penalties (Negative Points)

| Category | Item | Penalty |
|----------|------|---------|
| B0 | Banned substance | UNSAFE verdict |
| B0 | Recalled substance | BLOCKED verdict |
| B0 | High-risk substance | -10 pts + CAUTION |
| B0 | Watchlist substance | -5 pts + CAUTION |
| B1 | Harmful Additives | -0.5 to -3 each (cap -8) |
| B2 | Allergen Presence | -1 to -2 each (cap -2) |
| B5 | Proprietary Blend (none disclosure) | -2.5 to -7 each |
| B5 | Proprietary Blend (partial disclosure) | -1.3 to -4 each |
| B5 | Proprietary Blend total cap | -10 |
| B6 | Disease/Marketing Claims | -5 |
| Post | Manufacturer Violations | varies (floor -25) |

---

## Example Score Calculation

**Product:** "Premium Probiotic Plus with Organic Elderberry"

### Section A: Ingredient Quality
- A1: Weighted avg bioavailability = 11.5/15
- A2: 2 premium forms × 0.5 = 0.5/3
- A3: Lozenge (Tier 2) = 2/3
- A4: No absorption enhancer = 0/3
- A5: Organic (+1) + Synergy (+1) = 2/3
- A6: Not single-ingredient = 0/3
- Probiotic bonus (default): CFU (+1) + Diversity (+1) + Prebiotic (+1) = 3
- **Section A Total: min(25, 19.0) = 19.0/25**

### Section B: Safety & Purity (base_score = 25)
- B1: 1 moderate additive = -1
- B2: No allergens = 0
- Bonuses: Gluten-free (+1), Vegan (+1), NSF (+5), GMP (+4) = 11 → capped at 5
- B5: No proprietary blends = 0
- B6: No disease claims = 0
- **Section B Total: clamp(0, 30, 25 + 5 - 1) = 29.0/30**

### Section C: Evidence & Research
- 3 ingredients with RCTs (ingredient-human level) = 3 × (4 × 0.65) = 7.8/20
- **Section C Total: 7.8/20**

### Section D: Brand Trust
- D1: Top manufacturer (+2)
- D2: Full disclosure (+1)
- D4: Made in USA (+1)
- D5: Sustainable packaging (+0.5)
- D3+D4+D5: min(2.0, 1.5) = 1.5
- **Section D Total: min(5, 2 + 1 + 1.5) = 4.5/5**

### Final Calculation
```
quality_raw: 19.0 + 29.0 + 7.8 + 4.5 = 60.3
quality_score: clamp(0, 80, 60.3) = 60.3
score_100_equivalent: (60.3/80) * 100 = 75.4
Grade: Good
Verdict: SAFE
```

---

## Verdict Derivation

Precedence (first match wins):

| Priority | Verdict | Condition |
|----------|---------|-----------|
| 1 | `BLOCKED` | B0 blocked (recalled substance) |
| 2 | `UNSAFE` | B0 unsafe (banned substance) |
| 3 | `NOT_SCORED` | Mapping gate stopped |
| 4 | `CAUTION` | `B0_HIGH_RISK_SUBSTANCE`, `B0_WATCHLIST_SUBSTANCE`, `B0_MODERATE_SUBSTANCE`, or `BANNED_MATCH_REVIEW_NEEDED` in flags |
| 5 | `POOR` | `quality_score < 32` |
| 6 | `SAFE` | Default |

---

*Document generated by PharmaGuide Scoring System v5.0.0*
