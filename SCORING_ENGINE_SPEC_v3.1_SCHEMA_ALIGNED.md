# PharmaGuide AI — Scoring Engine Specification v3.1 (Schema-Aligned)

**Status:** Authoritative engineering reference (rewrite)
**Scope:** `scripts/score_supplements.py`, `scripts/config/scoring_config.json`
**Version target:** `3.1.0`
**Date:** 2026-02-25

---

## 1. Scope and Contract

This document defines scorer behavior against the current pipeline schema. Matching/NLP/classification are enrichment responsibilities. Scorer is arithmetic + deterministic gates.

### 1.1 Required Product Identity Fields

Scorer requires:
- `dsld_id`
- `product_name`
- `enrichment_version` or `enriched_date`

If required identity fields are missing, scorer returns failed/`NOT_SCORED` payload.

### 1.2 Final Score Formula

```text
quality_raw = A + B + C + D + violation_penalty
quality_score = clamp(0, 80, quality_raw)
score_80 = quality_score
score_100_equivalent = (quality_score / 80) * 100
```

### 1.3 Section Caps (v3.1)

| Section | Max | Was (v3.0.1) | Change |
|---|---:|---:|---:|
| A — Ingredient Quality | 25 | 25 | internal restructure |
| B — Safety & Purity | 30 | 35 | -5 |
| C — Evidence & Research | 20 | 15 | +5 |
| D — Brand Trust | 5 | 5 | minor restructure |
| Total | 80 | 80 | unchanged |

### 1.4 Grade Scale (post-verdict)

No grade for `BLOCKED`, `UNSAFE`, `NOT_SCORED`.

| score_100_equivalent | Grade |
|---:|---|
| >= 90 | Exceptional |
| >= 80 | Excellent |
| >= 70 | Good |
| >= 60 | Fair |
| >= 50 | Below Avg |
| >= 32 | Low |
| < 32 | Very Poor |

---

## 2. Pre-Section Gates

Execution order in `score_product()`:
1. B0 gate
2. Mapping gate
3. Unmapped+banned exact/alias regression guard
4. Section scoring

### 2.1 B0 Gate

Input:
- `contaminant_data.banned_substances.substances[]`

Match-type normalization fields:
- `match_type` (primary)
- `match_method` (fallback)

Hard-fail eligible:
- `exact`, `alias`

Review-only:
- `token_bounded` and any non-exact/alias value

Rules:
- `status in {recalled, both}` + exact/alias -> `BLOCKED`
- `severity_level in {critical, high}` + exact/alias -> `UNSAFE`
- `severity_level == moderate` + exact/alias -> +10 penalty, `B0_MODERATE_SUBSTANCE`
- `severity_level == low` + exact/alias -> advisory, `B0_LOW_SUBSTANCE`
- non-exact/alias hit -> `BANNED_MATCH_REVIEW_NEEDED`

### 2.2 Mapping Gate

Inputs:
- `ingredient_quality_data.total_active`
- `ingredient_quality_data.ingredients[]`

Derived KPI paths in scorer output:
- `unmapped_actives_total`
- `unmapped_actives_excluding_banned_exact_alias`
- `unmapped_actives_banned_exact_alias`
- `mapped_coverage`

Stop conditions:
- `total_active <= 0` -> `NO_ACTIVES_DETECTED`
- if `feature_gates.require_full_mapping == true` and `mapped_coverage < 1.0` -> `UNMAPPED_ACTIVE_INGREDIENT`

### 2.3 Regression Guard

If any unmapped active overlaps banned substances with exact/alias semantics, force unsafe path and add:
- `UNMAPPED_BANNED_EXACT_ALIAS_GUARD`

---

## 3. Section A — Ingredient Quality (Max 25)

```text
A = min(25, A1 + A2 + A3 + A4 + A5 + A6 + probiotic_bonus)
```

### 3.1 A1 — Bioavailability Form Score (max 15)

Input:
- primary: `ingredient_quality_data.ingredients_scorable[]`
- fallback: `ingredient_quality_data.ingredients[]`

Critical rules:
1. Exclude blend containers from A1:
   - `is_proprietary_blend == true` -> excluded.
2. Exclude non-dose-anchored rows:
   - ingredient must have usable individual dose (`quantity > 0` and usable unit) to count.
3. Per ingredient:
   - mapped -> use `score`, weight `dosage_importance`
   - unmapped -> fallback `score=9.0`, weight `1.0`
4. Supplement-type effects:
   - `supp_type in {single, single_nutrient}` -> force all weights to `1.0`
   - `supp_type == multivitamin` -> smoothing: `avg = 0.7*avg + 0.3*9.0`

Final formula:

```text
A1 = clamp(0, 15, (weighted_avg / 18) * 15)
```

Example (same profile, v3.0 vs v3.1 A1 only):

| Product profile | Bio score | v3.0 A1 | v3.1 A1 | Delta |
|---|---:|---:|---:|---:|
| Creatine mono | 14 | 10.11 | 11.67 | +1.56 |
| Perfect bioavailability | 18 | 13.00 | 15.00 | +2.00 |
| Generic form | 9 | 6.50 | 7.50 | +1.00 |
| Low-quality form | 5 | 3.61 | 4.17 | +0.56 |

### 3.2 A2 — Premium Forms Bonus (max 3)

Count unique canonical ingredients with `score >= 14`.

```text
A2 = clamp(0, 3, 0.5 * max(0, count_premium - 1))
```

### 3.3 A3 — Delivery System (max 3)

Input: `delivery_tier` (fallback `delivery_data.highest_tier`)

- Tier 1 -> 3
- Tier 2 -> 2
- Tier 3 -> 1
- None -> 0

### 3.4 A4 — Absorption Enhancer (max 3)

Input: `absorption_enhancer_paired` (fallback `absorption_data.qualifies_for_bonus`)

- true -> 3
- false -> 0

### 3.5 A5 — Formulation Excellence (max 3)

Sub-components:
- `A5a` organic +1
- `A5b` standardized botanical +1
- `A5c` synergy cluster +1
- `A5d` Non-GMO Project Verified +0.5 (gated, default off)

```text
A5 = min(3, A5a + A5b + A5c + A5d)
```

### 3.6 A6 — Single-Ingredient Efficiency Bonus (max 3)

Gate:
- `supp_type in {single, single_nutrient}`

Bonus tiers:
- bio score >= 16 -> +3
- bio score >= 14 -> +2
- bio score >= 12 -> +1
- bio score < 12 -> 0

### 3.7 Probiotic Bonus

Gate:
- `supp_type == probiotic`
- or non-probiotic strict gate if `allow_non_probiotic_probiotic_bonus_with_strict_gate == true`

Default mode (max 3): CFU +1, diversity +1, prebiotic +1.
Extended mode (max 10): gated by `probiotic_extended_scoring`.

---

## 4. Section B — Safety & Purity (Max 30)

### 4.1 Structural Formula (sign-consistent)

Penalties are positive magnitudes and are subtracted once.

```text
B_raw = B_base + B_bonus - penalties
B = clamp(0, 30, B_raw)

B_base = 25
B_bonus = min(5, B3 + B4a + B4b + B4c + B_hypoallergenic)
penalties = B0_moderate + B1 + B2 + B5 + B6
```

### 4.2 B1 — Harmful Additives (max penalty 5)

Input: `contaminant_data.harmful_additives.additives[]`

Magnitude map:
- high: 2.0
- moderate: 1.0
- low: 0.5

### 4.3 B2 — Allergen Presence (max penalty 2)

Input: `contaminant_data.allergens.allergens[]`

Magnitude map:
- high: 2.0
- moderate: 1.5
- low: 1.0

### 4.4 B3 — Claim Compliance (max bonus 4 in shared pool)

Points:
- allergen-free validated: +2
- gluten-free validated: +1
- vegan/vegetarian validated: +1

`LABEL_CONTRADICTION_DETECTED` should be emitted for claim contradictions.

Hypoallergenic +0.5 (gated):
- gate: `enable_hypoallergenic_bonus` (default false)
- requires all:
  - no allergen hits
  - no may-contain warning
  - no contradiction flag
  - allergen-free and/or gluten-free validation context

### 4.5 B4 — Quality Certifications (in shared 5-point pool)

Internal values remain:
- `B4a` named programs: +5 per program (internal cap 15)
- `B4b` GMP: certified +4, FDA registered +2
- `B4c` batch traceability: COA +1, lookup/QR +1

### 4.6 B5 — Proprietary Blend Disclosure Penalty (max 10)

Design intent:
- A1 scores known, dose-anchored ingredient quality.
- B5 penalizes hidden formula opacity.

#### 4.6.1 Inputs
- `proprietary_blends[]` (fallback `proprietary_data.blends[]`)
- blend fields: disclosure level, blend total mass (if available), child ingredient amounts (if available)

#### 4.6.2 Disclosure Tier Definitions (LOCKED)

| Tier | Definition |
|---|---|
| full | every child has individual amount |
| partial | blend total declared + child list, but incomplete child amounts; includes descending-order lists with no child mg |
| none | missing blend total and/or missing meaningful child list, or vague proprietary wording only |

#### 4.6.3 Labeling Examples (LOCKED)

| Label text | Tier | Rationale |
|---|---|---|
| `Caffeine 180mg, Taurine 200mg, Rhodiola 100mg` | full | all child amounts listed |
| `Proprietary Blend 1,200mg: Caffeine, Taurine, Rhodiola` | partial | total + children, no child mg |
| `Energy Complex` | none | no meaningful breakdown |
| `Energy Complex (Caffeine 180mg, Green Tea 200mg, Blend 1,000mg...)` | partial | some child amounts but incomplete |

#### 4.6.4 Hidden-Mass Impact

```text
disclosed_child_mg_sum = sum(child mg for children with individual amounts)
hidden_mass_mg = max(blend_total_mg - disclosed_child_mg_sum, 0)

if blend_total_mg and total_active_mg > 0:
    impact = clamp(hidden_mass_mg / total_active_mg, 0, 1)
    if hidden_mass_mg > 0:
        impact = max(impact, 0.1)
else:
    impact = clamp(hidden_count / max(total_active_count, 8), 0, 1)
```

Deterministic rule for count-share denominator:
- `max(total_active_count, 8)` is a **constant**, not configurable.
- Must be applied everywhere count-share fallback is used in scorer.

#### 4.6.5 Per-Blend Penalty Magnitude

Constants:
- presence penalty: `{full:0, partial:1, none:2}`
- proportional coefficient: `{full:0, partial:3, none:5}`

```text
blend_penalty = presence_penalty + proportional_coef * impact
```

Aggregate:

```text
B5 = clamp(0, 10, sum(blend_penalty across deduped blends))
```

#### 4.6.6 Deduplication

Fingerprint fields:
- normalized blend name
- sorted normalized child names
- normalized blend total mg key
- source path/field

Penalty applied once per unique fingerprint.

#### 4.6.7 Edge Rules

- blend containers excluded from A1
- child without individual amount:
  - does not add to disclosed_child_mg_sum
  - does not get A1 quality credit
- child with individual amount:
  - contributes to disclosed mass
  - can be scored in A1

#### 4.6.8 Required B5 Evidence Payload

Per processed blend, output:
- `blend_name`
- `disclosure_tier`
- `blend_total_mg`
- `disclosed_child_mg_sum`
- `hidden_mass_mg`
- `impact_ratio`
- `impact_source`
- `impact_floor_applied`
- `presence_penalty`
- `proportional_coef`
- `computed_blend_penalty` (signed display value)
- `computed_blend_penalty_magnitude` (positive magnitude)
- `dedupe_fingerprint`
- `unit_conversion_failed`
- `children_with_amount_count`
- `children_without_amount_count`

#### 4.6.9 B5 Sanity-Check Math Table

Assume `total_active_mg = 2000`.

| Scenario | Impact | Presence | Proportional term | Penalty magnitude | Signed contribution |
|---|---:|---:|---:|---:|---:|
| Partial blend 400mg, no children disclosed | 0.20 | 1.0 | 3*0.2=0.6 | 1.6 | -1.6 |
| No-disclosure blend 1200mg | 0.60 | 2.0 | 5*0.6=3.0 | 5.0 | -5.0 |
| No-disclosure 1200mg + partial 600mg (no child amounts disclosed) | 0.6 / 0.3 | 2+1 | 3.0+0.9 | 6.9 | -6.9 |
| No-disclosure 1900mg | 0.95 | 2.0 | 5*0.95=4.75 | 6.75 | -6.75 |
| Partial 1200mg, 800mg disclosed | 0.20 | 1.0 | 3*0.2=0.6 | 1.6 | -1.6 |
| Tiny no-disclosure 50mg | floor 0.10 | 2.0 | 5*0.1=0.5 | 2.5 | -2.5 |

### 4.7 B6 — Disease/Marketing Claims Penalty

If any disease-claim signal true:
- penalty magnitude = 5
- add `DISEASE_CLAIM_DETECTED`

Priority of sources:
1. `has_disease_claims`
2. `product_signals.has_disease_claims`
3. `evidence_data.unsubstantiated_claims.found`

---

## 5. Section C — Evidence & Research (Max 20)

**Critical prerequisite:** C rebalance only delivers value if `backed_clinical_studies.json` is populated with high-quality generic entries for major studied ingredients. Without this, C remains sparse and under-expressive.

### 5.1 Input

- `evidence_data.clinical_matches[]`

Dedup key priority:
- `id` -> `study_id` -> deterministic composite key

### 5.2 Per-Match Raw

```text
raw = study_base_points(study_type) * evidence_multiplier(evidence_level)
```

Study base points:
- systematic_review_meta: 6
- rct_multiple: 5
- rct_single: 4
- clinical_strain: 4
- observational: 2
- animal_study: 2
- in_vitro: 1

Evidence multipliers:
- product-human/product-rct/product: 1.0
- branded-rct: 0.8
- ingredient-human: 0.65
- strain-clinical: 0.6
- preclinical: 0.3
- unknown: 0.0

### 5.3 Dose Guard

If `min_clinical_dose` exists and converted product dose is below threshold:
- multiply raw by 0.25
- add `SUB_CLINICAL_DOSE_DETECTED`

### 5.4 Supra-Clinical Flag (NEW)

If product dose > `3x max_studied_clinical_dose`:
- add `SUPRA_CLINICAL_DOSE`
- no scoring penalty (informational only)

### 5.5 Caps

- per-ingredient cap: 7
- section cap: 20

```text
C = clamp(0, 20, sum(min(per_ingredient_points, 7)))
```

---

## 6. Section D — Brand Trust (Max 5)

Updated per your request to make max 5 reachable.

```text
D = min(5, D1 + D2 + min(2.0, D3 + D4 + D5))
```

Component values:
- `D1` trusted manufacturer: `2 / 1 / 0`
- `D2` full disclosure: `1`
- `D3` physician formulated: `0.5`
- `D4` high-standard region: `1.0` (bumped)
- `D5` sustainability: `0.5`

Tail cap:
- `D3 + D4 + D5` capped at `2.0`

D1 middle tier (gated):
- gate `enable_d1_middle_tier` default false
- score 1 only for verifiable GMP/NSF/USP evidence path

---

## 7. Post-Section Manufacturer Violation Penalty

Source field:
- `manufacturer_data.violations.total_deduction_applied`

Applied after section sum:
- stored negative
- floor at `-25.0`
- add `MANUFACTURER_VIOLATION` when non-zero

---

## 8. Verdict Derivation

Precedence:
1. `BLOCKED`
2. `UNSAFE`
3. `NOT_SCORED`
4. `CAUTION` (B0 moderate or banned review-needed)
5. `POOR` (`quality_score < 32`)
6. `SAFE`

Backward-compatible `safety_verdict`:
- `POOR -> SAFE`
- `NOT_SCORED -> CAUTION`
- else mirror `verdict`

---

## 9. Feature Gates (target)

- `require_full_mapping` (true)
- `probiotic_extended_scoring` (false)
- `allow_non_probiotic_probiotic_bonus_with_strict_gate` (true)
- `shadow_mode` (true)
- `enable_non_gmo_bonus` (false)
- `enable_hypoallergenic_bonus` (false)
- `enable_d1_middle_tier` (false)

---

## 10. Required Unit Tests (detailed)

### 10.1 B5 Blend Penalty Tests

1. Single blend, none, 100% formula
- Input: `blend_total_mg=2000`, `total_active_mg=2000`, `disclosed_child_mg_sum=0`, `disclosure=none`
- Expect: `hidden_mass=2000`, `impact=1.0`, penalty magnitude `7.0`, signed contribution `-7.0`
- Expect A1 excludes blend container.

2. Partial blend with disclosed children
- Input: `blend_total_mg=1200`, `total_active_mg=2000`, disclosed children `200mg + 150mg`
- Expect: `hidden_mass=850`, `impact=0.425`, penalty magnitude `2.275`, signed `-2.275`
- Expect disclosed children can be scored in A1.

3. Partial blend child without amount
- Input: `blend_total_mg=1000`, children `Caffeine 200mg, L-Theanine (no amount), Rhodiola (no amount)`
- Expect: `disclosed_sum=200`, `hidden_mass=800`
- L-Theanine/Rhodiola get no A1 dose-anchored quality credit.

4. Duplicate parsing, same blend fingerprint
- Expect one applied penalty.

5. Two different blends near cap
- Example magnitudes `5.0 + 4.5 = 9.5`; if >10 then clamp to 10.

6. Tiny blend floor
- Input: `blend_total_mg=50`, `total_active_mg=2000`, disclosure none
- Raw impact `0.025`, floor to `0.1`
- Penalty magnitude `2.5`, signed `-2.5`

7. Full disclosure blend
- Expect B5 `0`; children scored normally in A1.

8. No mg data fallback
- Input: hidden_count `4`, total_active_count `10`
- Expect `impact = 4 / max(10, 8) = 0.4`

### 10.2 A1 / A6 Tests

9. Blend container excluded from A1
- Product with blend container + 3 non-blend actives
- Expect A1 computed from non-blend dose-anchored rows only.

10. Non-dose-anchored exclusion
- Product row with missing/invalid individual dose
- Expect row excluded from A1.

11. A6 for single
- `supp_type=single`, bio score 14 -> `A6=2`

12. A6 for single_nutrient
- `supp_type=single_nutrient`, bio score 14 -> `A6=2`

13. A6 blocked for multi
- non-single types -> `A6=0`

### 10.3 Section B Restructure Tests

14. Clean no-certs
- No penalties, no certs -> `B=25`

15. Clean with over-cap bonuses
- Example `B3=3`, `B4a=5`, `B4b=4` -> bonus pool clamps to 5 -> `B=30`

### 10.4 Section C Tests

16. Per-ingredient cap 7
- Raw 7.15 -> capped to 7.0

17. Sub-clinical dose guard
- Below threshold -> `*0.25`, add `SUB_CLINICAL_DOSE_DETECTED`

18. Supra-clinical flag
- `dose > 3x max studied` -> add `SUPRA_CLINICAL_DOSE`, no point deduction

### 10.5 Section D Reachability Test

19. D max reachability
- Example: `D1=2`, `D2=1`, `D3=0.5`, `D4=1`, `D5=0.5`
- Tail `= min(2, 2.0)=2.0`, total `= min(5, 3+2)=5`

---

## 11. Implementation Priority

1. Add/validate clinical DB entries (top studied ingredients)
2. Finalize A1/A6 updates
3. Implement B restructure to 30 with pool logic
4. Finalize B5 sign-consistent hidden-mass implementation + payload
5. Implement C cap changes + supra-clinical flag
6. Implement D changes (D4=1, tail cap=2) and keep D1-middle-tier gated off
7. Full regression + shadow scoring

---

## 12. Shadow Scoring Validation (required)

Run v3.0 vs v3.1 shadow on same enriched corpus.

Track:
- score drift distribution
- verdict drift
- NOT_SCORED rate by category
- B5 distribution by category
- top-100 rank stability
- category mean shifts

Required validation brands:
- Thorne
- Nordic Naturals
- Garden of Life
- Optimum Nutrition
- Olly
- NOW Foods

Required form factors:
- Lozenges
- Gummies
- Softgels
- Capsules
- Tablets
- Powders

Recommended fail checks:
- arithmetic mismatch > 0 -> fail
- unexplained safety verdict flips -> fail
- extreme top-rank churn without evidence explanation -> investigate

---

## 13. Production Monitoring Controls

Track continuously:
- `unmapped_actives_excluding_banned_exact_alias` trend by category
- `NOT_SCORED` rate by category
- `BANNED_MATCH_REVIEW_NEEDED` volume
- verdict drift across runs
- B5 average and distribution by category
- Section C mean by category
- **Section C linkage check:** when `backed_clinical_studies.json` grows, verify affected ingredient cohorts actually show expected C-score lift (catch matching/connectivity failures)
