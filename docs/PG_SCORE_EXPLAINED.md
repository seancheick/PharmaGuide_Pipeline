# PharmaGuide Score Explained

> Scoring version: **3.4.0** | Data schema: spans **5.0.0 – 5.4.0** (heterogeneous, see each data file's `_metadata.schema_version`) | Last updated: 2026-05-12
>
> Section caps (A=25, B=30, C=20, D=5; E folded into A as omega-3 dose bonus), verdict precedence (BLOCKED > UNSAFE > NOT_SCORED > CAUTION > POOR > SAFE), `poor_threshold_quality_score = 32`, and grade scale all verified against `scripts/config/scoring_config.json` on 2026-05-12. The narrative below remains current — only the header was bumped.

---

## How Your Supplement Score Works

Every supplement in PharmaGuide receives a transparent quality score. No black boxes, no machine learning, no paid placements. Every point earned or lost has a documented reason.

The score has two layers:

| Layer                  | Max Points | Computed Where  | Purpose                                            |
| ---------------------- | ---------- | --------------- | -------------------------------------------------- |
| **Quality Score**      | 80         | Server pipeline | Objective product quality — same for everyone      |
| **Personal Fit Score** | 20         | Your phone      | Personalized to your age, health goals, conditions |
| **Combined Score**     | 100        | Your phone      | The number you see in the app                      |

```
Quality Score    = clamp(0, 80, Ingredient Quality + Safety + Evidence + Brand Trust + Violation Penalty)
Combined Score   = (Quality Score + Personal Fit Score) / 100 × 100
```

---

## Part 1: Quality Score (80 points, computed server-side)

This is the objective product score. Same product, same data, same score. Always.

### Overview

| Section                 | Max Points | What It Measures                      |
| ----------------------- | ---------- | ------------------------------------- |
| **Ingredient Quality**  | 25         | How good are the ingredient forms?    |
| **Safety & Purity**     | 30         | Is this product safe and clean?       |
| **Evidence & Research** | 20         | Is there clinical evidence behind it? |
| **Brand Trust**         | 5          | Is the manufacturer reputable?        |
| **Total**               | **80**     |                                       |

---

## Before Scoring: The Safety Gates

Before any points are calculated, every product must pass through **three mandatory gates**. A failure stops scoring entirely.

### Gate 1 — Banned & Recalled Substance Check

Every ingredient is scanned against our regulatory safety database.

| Substance Status | Match Type    | Outcome                         |
| ---------------- | ------------- | ------------------------------- |
| **Recalled**     | exact / alias | **BLOCKED** — cannot be scored  |
| **Banned**       | exact / alias | **UNSAFE** — cannot be scored   |
| **High Risk**    | exact / alias | -10 penalty + CAUTION verdict   |
| **Watchlist**    | exact / alias | -5 penalty + CAUTION verdict    |
| Any status       | fuzzy / token | Review flag only — no auto-fail |

Source: `banned_recalled_ingredients.json` — cross-verified against FDA, DEA, and international regulatory databases.

### Gate 2 — Ingredient Mapping Check

Every active ingredient must be recognized and mapped to our quality database. If any active ingredient is unmatched, the product gets **NOT_SCORED** status. We never assign quality points to ingredients we can't verify.

### Gate 3 — Regression Guard

If an unmatched ingredient overlaps with a known banned/recalled substance by exact name or alias, the scorer forces **UNSAFE**. This prevents dangerous substances from slipping through as "mapping misses."

---

## Ingredient Quality (max 25 points)

This section rewards products that use high-quality, bioavailable ingredient forms.

The formula separates **core quality** from **category bonuses** — core quality always dominates, bonuses enhance but never define the score.

```
core_quality     = Bioavailability + Premium Forms + Delivery System
                 + Absorption Enhancer + Formulation Excellence
                 + Single-Ingredient Efficiency

bonus_pool       = min(max_bonus_contribution,
                       Probiotic Bonus + Omega-3 Dose Bonus + [future bonuses...])

Ingredient Quality = min(25, core_quality + bonus_pool)
```

**Bonus Pool Cap** (`max_bonus_contribution`): configurable, default **5**. This ensures:

- Core quality (bioavailability, forms, delivery) always drives the score
- A product cannot game the system by stacking niche bonuses
- The pool is future-proof — adding new category bonuses (Vitamin D, Magnesium, etc.) won't inflate scores

### Bioavailability Score (max 15)

The core quality metric. Each active ingredient's form is scored on an 18-point bioavailability scale from our Ingredient Quality Map (550+ ingredients verified).

- Weighted by dosage importance (how critical that nutrient's dose is)
- **Proprietary blend containers excluded** — they're opacity signals, not real ingredients
- **Parent-total rows excluded** — prevents double-counting when a label lists both "Vitamin A 10,000 IU" and its sub-forms (Mixed Carotenes + Retinyl Palmitate)
- **Single-ingredient products**: all weights forced to 1.0
- **Multivitamins**: smoothing applied (`avg = 0.7 × avg + 0.3 × 9.0`) to prevent one poor form from tanking the whole score
- Unmapped ingredients fall back to a neutral score of 9.0

```
Bioavailability = clamp(0, 15, (weighted_avg / 18) × 15)
```

### Premium Forms Bonus (max 3)

Rewards products using top-tier ingredient forms (bioavailability score >= 14 out of 18). Deduplicated by canonical ingredient.

```
Premium Forms = clamp(0, 3, 0.5 × max(0, premium_count - 1))
```

Example: 4 premium-form ingredients → `0.5 × 3 = 1.5 pts`.

### Delivery System (max 3)

| Delivery Tier | Points | Examples                        |
| ------------- | ------ | ------------------------------- |
| Tier 1        | 3      | Liposomal, nano-emulsified      |
| Tier 2        | 2      | Enteric-coated, delayed-release |
| Tier 3        | 1      | Standard capsule, softgel       |
| None          | 0      | Basic tablet, powder            |

### Absorption Enhancer (max 3)

**+3** if the product pairs an absorption enhancer (e.g., BioPerine/piperine) with a target ingredient that benefits from it. An enhancer-only product does not qualify — it must be paired with a target.

### Formulation Excellence (max 3)

| Component              | Points | Condition                                             |
| ---------------------- | ------ | ----------------------------------------------------- |
| Organic                | +1     | USDA verified organic or valid claim path             |
| Standardized Botanical | +1     | Standardization threshold met                         |
| Synergy Cluster        | +1     | Ingredients form a recognized synergistic combination |
| Non-GMO Verified       | +0.5   | _Currently gated OFF_                                 |

### Single-Ingredient Efficiency (max 3)

Only applies to single-ingredient or single-nutrient products. Rewards using the best available form of that one ingredient:

| Bio Score | Points |
| --------- | ------ |
| >= 16     | 3      |
| >= 14     | 2      |
| >= 12     | 1      |
| < 12      | 0      |

### Category Bonuses

Category bonuses reward specialized product types for meeting category-specific quality criteria. All bonuses are pooled under the 25-point Ingredient Quality cap.

#### Probiotic Bonus (max 3 default)

For probiotic products (or non-probiotics passing strict evidence gates):

| Component          | Points | Condition                    |
| ------------------ | ------ | ---------------------------- |
| CFU Count          | +1     | > 1 billion CFU              |
| Strain Diversity   | +1     | >= 3 strains                 |
| Prebiotic Included | +1     | Contains inulin, FOS, or GOS |

**Extended mode** (currently gated OFF, max 10): Adds tiered CFU scoring up to +4, strain diversity up to +4, clinical strain recognition up to +3 (LGG, BB-12, NCFM, Reuteri, K12, M18, Coagulans, Shirota), prebiotic count up to +3, and survivability technology (delayed release, enteric coating, microencapsulation) +2.

#### Omega-3 Dose Adequacy Bonus (max 2)

For omega-3 products with explicitly labelled EPA and DHA amounts per serving. Rewards products that deliver clinically meaningful omega-3 doses.

| Daily EPA+DHA (mg) | Points | Label             | Clinical Basis                            |
| ------------------ | ------ | ----------------- | ----------------------------------------- |
| >= 4,000           | 2.0    | Prescription dose | AHA/ACC Rx for hypertriglyceridemia       |
| >= 2,000           | 2.0    | High clinical     | EFSA health claim for blood triglycerides |
| >= 1,000           | 1.5    | AHA CVD           | AHA recommendation for CVD patients       |
| >= 500             | 1.0    | General health    | FDA qualified health claim minimum        |
| >= 250             | 0.5    | EFSA AI zone      | EFSA Adequate Intake                      |
| < 250              | 0.0    | Below EFSA AI     | Below minimum threshold                   |

Not applicable (0 pts, 0 max) for products without labelled EPA/DHA. Excludes proprietary blend containers and parent-total rows. Only mg, g, and mcg units accepted.

Serving basis resolved from product label: `min_servings_per_day` / `max_servings_per_day`, with midpoint used for band matching.

---

## Safety & Purity (max 30 points)

The largest section — because safety matters most. Every product **starts at 25** and can earn up to 5 bonus points or lose points from penalties.

```
Safety & Purity = clamp(0, 30, base_score + bonuses - penalties)

base_score = 25
bonuses    = min(5, Claim Compliance + Certifications + Batch Traceability + Hypoallergenic)
penalties  = Safety Gate Penalty + Harmful Additives + Allergens
           + Proprietary Blend + Disease Claims + Dose Safety
```

### Penalties (points lost)

#### Safety Gate Penalties (from Gate 1)

| Substance Status    | Penalty |
| ------------------- | ------- |
| High-risk substance | -10     |
| Watchlist substance | -5      |

#### Harmful Additives (max -8)

Each harmful additive found is penalized by risk level. Deduplicated by additive ID (highest severity wins).

| Risk Level | Penalty Per Additive |
| ---------- | -------------------- |
| High       | -2.0                 |
| Moderate   | -1.0                 |
| Low        | -0.5                 |

Source: `harmful_additives.json` (115 entries, 20 categories, all deep-audited). Substances posing immediate hazard are handled by the Safety Gate (Gate 1) instead.

#### Allergen Presence (max -2)

| Severity | Penalty |
| -------- | ------- |
| High     | -2.0    |
| Moderate | -1.5    |
| Low      | -1.0    |

#### Proprietary Blend Penalty (max -10)

The **cost of opacity**. Products hiding ingredients behind proprietary blend labels get penalized based on how much they hide.

**Disclosure tiers (per 21 CFR 101.36):**

| Disclosure Level | What It Means                                            | Example                                                     |
| ---------------- | -------------------------------------------------------- | ----------------------------------------------------------- |
| **Full**         | Every sub-ingredient has an individual amount            | "Blend 500mg: Vitamin C 200mg, Zinc 50mg, Elderberry 250mg" |
| **Partial**      | Blend total + ingredient list, but no individual amounts | "Blend 500mg: Vitamin C, Zinc, Elderberry"                  |
| **None**         | Missing blend total, ingredient list, or both            | "Proprietary Blend" (nothing else)                          |

**How the penalty is calculated:**

```
hidden_mass = max(blend_total_mg - disclosed_child_mg_sum, 0)
impact_ratio = clamp(hidden_mass / total_active_mg, 0, 1)

blend_penalty = presence_penalty + proportional_coef × impact_ratio
```

| Disclosure | Presence Penalty | Coef | Min Total | Max Total |
| ---------- | ---------------- | ---- | --------- | --------- |
| Full       | 0.0              | 0.0  | 0.0       | 0.0       |
| Partial    | 1.0              | 3.0  | -1.3      | -4.0      |
| None       | 2.0              | 5.0  | -2.5      | -7.0      |

A blend hiding 80% of the formula gets hit much harder than one hiding 5%. Full disclosure always produces 0 penalty.

#### Disease / Marketing Claims (max -5)

If a product makes unsubstantiated disease claims (e.g., "cures cancer"), it receives **-5** and a `DISEASE_CLAIM_DETECTED` flag.

#### Dose Safety (max -3)

Penalizes products with any ingredient exceeding **150% of the highest adult Upper Tolerable Limit (UL)**.

- Per ingredient over 150% UL: **-2.0**
- Capped at **-3.0** total

Below 150%, UL enforcement is handled by your phone's personalized scoring (see Personal Fit Score → Dosage Appropriateness).

| Situation                 | Pipeline Penalty | Phone Penalty                                         |
| ------------------------- | ---------------- | ----------------------------------------------------- |
| Under all ULs             | Nothing          | Normal dosage scoring                                 |
| Over UL by < 150%         | Warning only     | **-5 penalty**                                        |
| Over UL by 150%+          | **-2.0**         | **-5 penalty** (double-count — objectively dangerous) |
| 2+ ingredients over 150%+ | **-3.0 cap**     | -5 per ingredient                                     |

### Bonuses (points earned on top of base 25)

#### Claim Compliance (max +4)

| Validated Claim            | Bonus |
| -------------------------- | ----- |
| Allergen-free validated    | +2    |
| Gluten-free validated      | +1    |
| Vegan/vegetarian validated | +1    |

Claims are verified against actual ingredient data. A "may contain" warning invalidates allergen-free claims. Gelatin/bovine in the formula invalidates vegan claims. Contradictions trigger `LABEL_CONTRADICTION_DETECTED`.

#### Quality Certifications

| Component                                    | Max | Details                                            |
| -------------------------------------------- | --- | -------------------------------------------------- |
| Named Programs (USP, NSF, ConsumerLab, etc.) | +15 | +5 per verified program                            |
| GMP Level                                    | +4  | NSF GMP certified = +4, FDA registered = +2        |
| Batch Traceability                           | +2  | Certificate of Analysis = +1, batch lookup/QR = +1 |

IFOS certification only counted for omega-like products.

All bonuses pooled under the **+5 cap** for the entire bonus pool.

#### Hypoallergenic (gated, currently OFF)

+0.5 when zero allergen penalty + no "may contain" text + at least one validated allergen-free claim.

---

## Evidence & Research (max 20 points)

Points based on clinical evidence backing each ingredient.

### Study Types and Base Points

| Study Type                        | Points |
| --------------------------------- | ------ |
| Systematic review / meta-analysis | 6      |
| Multiple RCTs                     | 5      |
| Single RCT                        | 4      |
| Clinical strain study             | 4      |
| Observational study               | 2      |
| Animal study                      | 2      |
| In vitro (lab) study              | 1      |

### Evidence Level Multipliers

How close is the evidence to THIS actual product?

| Evidence Level            | Multiplier | Meaning                                       |
| ------------------------- | ---------- | --------------------------------------------- |
| Product-level human / RCT | 1.0×       | Study used this exact product                 |
| Branded RCT               | 0.8×       | Study used this branded ingredient            |
| Ingredient-level human    | 0.65×      | Study used same ingredient, different product |
| Strain-level clinical     | 0.6×       | Study used same probiotic strain              |
| Preclinical               | 0.3×       | Animal or lab data only                       |
| Unknown                   | 0.0×       | No verifiable evidence                        |

```
Per match = study_base_points × evidence_multiplier
```

### Dose Guards

- **Sub-clinical dose**: If the product dose is below the minimum clinically studied dose, evidence points drop by **75%** (multiplied by 0.25). You can't claim clinical benefit at a homeopathic dose.
- **Supra-clinical dose**: If product dose > 3× max studied dose, a `SUPRA_CLINICAL_DOSE` flag is added (informational, no scoring impact).

Capping: max **7 points** per canonical ingredient. Section total capped at **20**.

---

## Brand Trust (max 5 points)

```
Brand Trust = min(5, Trusted Manufacturer + Full Disclosure + min(2.0, Physician + Region + Sustainability))
```

| Component                             | Points | Condition                                                                                        |
| ------------------------------------- | ------ | ------------------------------------------------------------------------------------------------ |
| Trusted Manufacturer                  | +2.0   | Exact match in trusted manufacturer database                                                     |
| Manufacturer (middle-tier, gated OFF) | +1.0   | Verifiable GMP/NSF/USP evidence                                                                  |
| Full Disclosure                       | +1.0   | All active ingredients have doses + no hidden blends                                             |
| Physician Formulated                  | +0.5   | Verified physician-formulated claim                                                              |
| High-Standard Region                  | +1.0   | Made in USA, EU, UK, Germany, Switzerland, Japan, Canada, Australia, NZ, Norway, Sweden, Denmark |
| Sustainable Packaging                 | +0.5   | Verified sustainability claim                                                                    |

Physician + Region + Sustainability collectively capped at 2.0.

---

## Manufacturer Violation Penalty (post-section)

After all sections are summed, a manufacturer-level penalty may apply for companies with documented FDA warning letters, consent decrees, or enforcement actions.

- Applied as a **negative deduction** directly to the raw score
- Floored at **-25** (maximum penalty)
- Flags `MANUFACTURER_VIOLATION`

---

## Verdicts

Every product receives a verdict. First match wins (strict precedence):

| Priority | Verdict        | Condition                                  | What It Means                   |
| -------- | -------------- | ------------------------------------------ | ------------------------------- |
| 1        | **BLOCKED**    | Recalled substance found                   | Do not use — regulatory recall  |
| 2        | **UNSAFE**     | Banned substance found                     | Do not use — safety concern     |
| 3        | **NOT_SCORED** | Mapping gate failed                        | Cannot verify ingredients       |
| 4        | **CAUTION**    | High-risk / watchlist / moderate substance | Use with awareness              |
| 5        | **POOR**       | Score < 32/100                             | Below minimum quality threshold |
| 6        | **SAFE**       | Default                                    | Scored normally                 |

## Grade Scale

For products with SAFE or CAUTION verdicts:

| Score (out of 100) | Grade         |
| ------------------ | ------------- |
| 90 – 100           | Exceptional   |
| 80 – 89            | Excellent     |
| 70 – 79            | Good          |
| 60 – 69            | Fair          |
| 50 – 59            | Below Average |
| 32 – 49            | Low           |
| 0 – 31             | Very Poor     |

## Badges

- **FULL DISCLOSURE** — "This product lists exact amounts for every active ingredient." Requires all non-blend actives to have individual doses and no partial/none proprietary blends.
- **Category Percentile** — Shows how a product ranks within its category (e.g., "Top 15% of Multivitamins"). Requires minimum cohort size of 5.

---

## Part 2: Personal Fit Score (20 points, computed on your phone)

This is the personalization layer. It's computed **fresh on your phone every time** you view a product, using your health profile. It is **never stored in the database** and **never leaves your device**.

```
Combined Score = (Quality Score + Personal Fit Score) / 100 × 100
```

### Dosage Appropriateness (max 7 points)

Compares each nutrient's dose against **your** age/sex-specific RDA and UL values.

| Dose vs Your RDA               | Points         |
| ------------------------------ | -------------- |
| Optimal range (50–200% of RDA) | +7             |
| Adequate (25–50% of RDA)       | +4             |
| Low dose (<25% of RDA)         | +2             |
| **Over your UL**               | **-5 penalty** |

Key rules:

- The **-5 UL penalty always runs**, even without a complete profile. Without age/sex, it uses the most conservative adult UL as fallback.
- Without age, dosage range defaults to 4 pts baseline (can't calculate exact RDA match).

### Goal Match (max 2 points)

Does the product align with your stated health goals? (e.g., "bone health", "energy", "heart health")

- Matched goal: +2
- No goals set: section drops out (score shown out of /98)

### Age Appropriateness (max 3 points)

Is this product formulated appropriately for your age group?

- Age-appropriate: +3
- No age set: section drops out (score shown out of /97), BUT UL penalty still runs with conservative defaults

### Medical Compatibility (max 8 points)

Evaluates the product against your declared health conditions, medications, and drug classes.

- No interactions found: **full 8 points** (no conditions = no conflicts)
- Interactions found: points reduced based on severity (contraindicated, caution, monitor)
- Source: 45 interaction rules covering pregnancy, hypertension, diabetes, high cholesterol, and more

### What Happens with an Incomplete Profile

| Profile State | Max Possible | What Happens                                                                     |
| ------------- | ------------ | -------------------------------------------------------------------------------- |
| Full profile  | /100         | All sections scored                                                              |
| No goals set  | /98          | Goal Match drops (missing 2 pts)                                                 |
| No age set    | /97          | Age Appropriateness drops (missing 3 pts), BUT UL penalty still runs             |
| No conditions | /100         | Full 8 pts for Medical Compatibility (no conditions = no conflicts)              |
| Empty profile | ~91          | UL penalty runs with conservative defaults; Goal + Age drop; Medical gets full 8 |

### What Never Leaves Your Phone

| Data                                                | Storage                                     |
| --------------------------------------------------- | ------------------------------------------- |
| Health profile (conditions, meds, goals, allergies) | Local SQLite only                           |
| Personal Fit Score                                  | Computed fresh each time — **never stored** |
| Scan history                                        | Local SQLite                                |
| Chat history                                        | Local encrypted storage                     |

---

## Part 3: Feature Gates

Feature gates are rollout controls that let us develop and ship new scoring features incrementally without breaking existing scores.

### Why They Exist

When we add a new bonus or penalty, we can't flip it on immediately — it would change scores for thousands of products overnight. Gates let us:

1. **Build** the code with the gate OFF (ready and tested, but dormant)
2. **Shadow-test** (compute the new feature silently alongside the old score, compare)
3. **Turn ON** when data quality and testing confirm the feature is ready

### Current Gate Status

| Gate                             | Status  | What It Controls                                                                 |
| -------------------------------- | ------- | -------------------------------------------------------------------------------- |
| Full Mapping Required            | **ON**  | Any unmapped active ingredient = NOT_SCORED                                      |
| Extended Probiotic Scoring       | **OFF** | Expanded probiotic bonus (max +10 instead of +3)                                 |
| Non-Probiotic Probiotic Bonus    | **ON**  | Non-probiotic products CAN earn probiotic bonus with strict evidence gates       |
| Shadow Mode                      | **ON**  | Gated features computed silently for comparison, without affecting actual scores |
| Non-GMO Bonus                    | **OFF** | +0.5 for Non-GMO Project Verified — data not fully enriched yet                  |
| Hypoallergenic Bonus             | **OFF** | +0.5 for allergen-free products — pending full validation pipeline               |
| Trusted Manufacturer Middle Tier | **OFF** | +1.0 for verifiable GMP/NSF/USP evidence — pending database expansion            |

### Gate Lifecycle

```
Feature idea
  → Code with gate OFF
  → Write tests (ON + OFF states)
  → Shadow-test (run both old + new on full product set — see Appendix B)
  → Validate: % affected, avg delta, max delta, verdict changes
  → Data quality confirmed
  → Turn gate ON
  → Feature goes live
```

When a gate is **OFF**, the code exists and is tested, but contributes **0 points**. When turned **ON**, it starts contributing to the final score. Every transition is validated by the Shadow Comparison Protocol (Appendix B) before rollout.

---

## Trust Guarantees

- **550+** verified ingredient forms in the quality database
- **2,600+** automated tests validating every scoring rule
- **34** reference data files cross-verified against FDA, NIH, PubMed, and EFSA
- **100+** configurable parameters — every threshold is documented
- **Deterministic** — same product, same data, same score. Always.
- **No paid placements** — every score is algorithmically determined
- **Privacy-first** — your health data never leaves your phone

---

## Appendix A: Internal Reference Mapping

For developers cross-referencing code and documentation.

### Naming Convention

All scorer functions follow a **semantic contract** based on their role:

| Prefix                | Role                     | Sign      | Example                               |
| --------------------- | ------------------------ | --------- | ------------------------------------- |
| `compute_*_score()`   | Core quality contributor | Positive  | `compute_bioavailability_score()`     |
| `compute_*_bonus()`   | Additive enhancer        | Positive  | `compute_probiotic_category_bonus()`  |
| `compute_*_penalty()` | Subtractive deduction    | Negative  | `compute_proprietary_blend_penalty()` |
| `evaluate_*()`        | Gate / check / decision  | Pass/fail | `evaluate_safety_gate()`              |

This makes every function self-documenting. Reading the name tells you what it does and how it affects the score.

### Full Mapping

| Human Name                     | Legacy ID   | Target Function Name                       |
| ------------------------------ | ----------- | ------------------------------------------ |
| **Ingredient Quality**         | A           | `compute_ingredient_quality_score()`       |
| → Bioavailability              | A1          | `compute_bioavailability_score()`          |
| → Premium Forms                | A2          | `compute_premium_forms_bonus()`            |
| → Delivery System              | A3          | `compute_delivery_score()`                 |
| → Absorption Enhancer          | A4          | `compute_absorption_bonus()`               |
| → Formulation Excellence       | A5          | `compute_formulation_bonus()`              |
| → Single-Ingredient Efficiency | A6          | `compute_single_efficiency_bonus()`        |
| → Probiotic Bonus              | probiotic   | `compute_probiotic_category_bonus()`       |
| → Omega-3 Dose Bonus           | omega3_dose | `compute_omega3_dose_bonus()`              |
| **Safety & Purity**            | B           | `compute_safety_purity_score()`            |
| → Safety Gate                  | B0          | `evaluate_safety_gate()`                   |
| → Harmful Additives            | B1          | `compute_harmful_additives_penalty()`      |
| → Allergen Presence            | B2          | `compute_allergen_penalty()`               |
| → Claim Compliance             | B3          | `compute_claim_compliance_bonus()`         |
| → Quality Certifications       | B4          | `compute_certifications_bonus()`           |
| → Proprietary Blend Penalty    | B5          | `compute_proprietary_blend_penalty()`      |
| → Disease Claims               | B6          | `compute_disease_claims_penalty()`         |
| → Dose Safety                  | B7          | `compute_dose_safety_penalty()`            |
| **Evidence & Research**        | C           | `compute_evidence_score()`                 |
| **Brand Trust**                | D           | `compute_brand_trust_score()`              |
| → Trusted Manufacturer         | D1          | `compute_manufacturer_trust_score()`       |
| → Full Disclosure              | D2          | `compute_disclosure_bonus()`               |
| → Physician Formulated         | D3          | `compute_physician_bonus()`                |
| → High-Standard Region         | D4          | `compute_region_bonus()`                   |
| → Sustainable Packaging        | D5          | `compute_sustainability_bonus()`           |
| **Manufacturer Violation**     | —           | `compute_manufacturer_violation_penalty()` |
| **Personal Fit Score**         | F           | Phone-side only                            |
| → Dosage Appropriateness       | E1          | `compute_dosage_fit_score()` (phone)       |
| → Goal Match                   | E2a         | `compute_goal_match_score()` (phone)       |
| → Age Appropriateness          | E2b         | `compute_age_fit_score()` (phone)          |
| → Medical Compatibility        | E2c         | `compute_medical_compat_score()` (phone)   |

---

## Appendix B: Migration & Shadow Validation

### Shadow Comparison Protocol

Before any scoring change ships, both the old and new scoring logic run in parallel on the full product set. This produces a delta report:

```
For each product:
    old_score = score_v3_2(product)
    new_score = score_v3_3(product)
    delta     = new_score - old_score

Aggregate:
    % of products affected (delta != 0)
    average delta
    max delta (worst case)
    category-specific shifts (e.g., omega-3 products, probiotics)
    verdict changes (any product that changes verdict = red flag)
```

**Rollout gate**: No scoring change ships unless:

- < 5% of products shift more than 3 points
- Zero verdict changes (SAFE→UNSAFE, etc.) that aren't intentional
- Category-specific shifts are understood and documented

`shadow_mode` in `scoring_config.json` is only a feature gate. A real shadow run now
requires an explicit baseline scorer or config difference, for example:

```bash
python3 scripts/shadow_score_comparison.py scripts/output_brand_enriched/enriched \
  --baseline-module path/to/score_supplements_v32.py \
  --candidate-module scripts/score_supplements.py
```
