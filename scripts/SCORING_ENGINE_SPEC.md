# SCORING_ENGINE_SPEC.md

## Scope

This document specifies the current server-side scoring behavior implemented in:
- `score_supplements.py`
- `config/scoring_config.json`

**Scoring version: 3.0.1**
Code-accurate as of 2026-02-20.

## Scorer Contract

Scorer is arithmetic-only. Matching and NLP are performed in enrichment. The scorer
consumes fully-enriched products and computes scores from their canonical fields.

Required product-level fields:
- `dsld_id`
- `product_name`
- `enrichment_version` (or `enriched_date`)

If required product identity fields are missing, scorer returns `NOT_SCORED` error payload.

## Final Score Formula

```text
quality_raw = A + B + C + D + violation_penalty
quality_score = clamp(0, 80, quality_raw)
score_80 = quality_score
score_100_equivalent = (quality_score / 80) * 100
```

Section caps:
- A max 25
- B max 35
- C max 15
- D max 5

## Grade Scale

Applied post-verdict. Not assigned for `BLOCKED`, `UNSAFE`, or `NOT_SCORED`.

| score_100_equivalent | Grade |
|---|---|
| ≥ 90 | Exceptional |
| ≥ 80 | Excellent |
| ≥ 70 | Good |
| ≥ 60 | Fair |
| ≥ 50 | Below Avg |
| ≥ 32 | Low |
| < 32 | Very Poor |

## Pre-Section Gates

Order in `score_product()`:

1. B0 gate (banned/recalled immediate fail checks)
2. Mapping gate
3. Regression guard on unmatched + banned exact/alias overlap

### B0 Gate

Input path:
- `contaminant_data.banned_substances.substances[]`

Match-type semantics:
- Hard-fail eligible types: `exact`, `alias`
- Non-hard-fail types: `token_bounded` and any other value → review-only flag

Rules:
- `status in {"recalled","both"}` + exact/alias → `BLOCKED`
- `severity_level in {"critical","high"}` + exact/alias → `UNSAFE`
- `severity_level == "moderate"` + exact/alias → B0 moderate penalty `10`; adds `B0_MODERATE_SUBSTANCE`
- `severity_level == "low"` + exact/alias → advisory only; adds `B0_LOW_SUBSTANCE`
- Any review-only (non exact/alias) hit → `BANNED_MATCH_REVIEW_NEEDED`

Note: if a hard fail fires, all moderate/low flags are stripped from that evaluation.

### Mapping Gate

Input paths:
- `ingredient_quality_data.total_active`
- `ingredient_quality_data.unmapped_count`
- `ingredient_quality_data.ingredients[]`

Outputs:
- `mapped_coverage`
- `unmapped_actives` (true mapping gap names, banned-overlap excluded)
- `unmapped_actives_total`
- `unmapped_actives_excluding_banned_exact_alias`
- `unmapped_actives_banned_exact_alias`

Also checks `match_ledger.domains.ingredients.entries` for rejected/unmatched inactive
entries; adds `UNMAPPED_INACTIVE_INGREDIENT` flag when found (non-blocking).

Stop conditions:
- `total_active <= 0` → stop with `NO_ACTIVES_DETECTED`
- if `feature_gates.require_full_mapping == true` and `mapped_coverage < 1.0` → stop with `UNMAPPED_ACTIVE_INGREDIENT`

Current config state:
- `require_full_mapping: true`

### Regression Guard

If an unmatched active overlaps banned substances with `exact/alias` match type:
- scorer forces unsafe path (unless already blocked/unsafe by B0)
- adds `UNMAPPED_BANNED_EXACT_ALIAS_GUARD`

Purpose: avoid labeling safety-caught unmatched actives as mapping misses; enforce
`UNSAFE/BLOCKED` behavior for this overlap case.

---

## Section A: Ingredient Quality (max 25)

```text
A = min(25, A1 + A2 + A3 + A4 + A5 + probiotic_bonus)
```

### A1 Bioavailability Form (max 13)

Input:
- `ingredient_quality_data.ingredients_scorable` fallback `ingredient_quality_data.ingredients`

**Blend container exclusion:** entries with `is_proprietary_blend: true` are excluded from
A1 entirely. Blend containers are opacity signals — their cost is captured by B5. Including
them in A1 would double-penalise and contaminate the quality average with a meaningless stub
score of 5.

Per ingredient (non-blend):
- mapped: use `score` and `dosage_importance`
- unmapped: fallback `score=9.0`, `weight=1.0`

Supplement-type effects:
- `single` / `single_nutrient`: all weights forced to `1.0`
- `multivitamin`: smoothing applied — `avg = 0.7×avg + 0.3×9.0`

Final:
```text
A1 = clamp(0, 13, (weighted_avg / 18) × 13)
```

### A2 Premium Forms (max 3)

Rule:
- Count unique canonical ingredients with `score >= 14`
- `A2 = clamp(0, 3, 0.5 × max(0, count - 1))`

### A3 Delivery System (max 3)

Input:
- `delivery_tier` fallback `delivery_data.highest_tier`

Map:
- tier 1 → 3
- tier 2 → 2
- tier 3 → 1
- else → 0

### A4 Absorption Enhancer (max 3)

Input:
- `absorption_enhancer_paired` fallback `absorption_data.qualifies_for_bonus`

Rule:
- true → 3
- false → 0

Note: enricher uses `standard_name` field (not `name`) when looking up enhancers in
`absorption_enhancers.json`. Bonus requires an absorptive enhancer paired with a target
ingredient; an enhancer-only product does not qualify.

### A5 Formulation Excellence (max 3)

Subcomponents:
- A5a organic: +1 when USDA verified or valid claim path
- A5b standardized botanical: +1 when threshold/flag met
- A5c synergy cluster: +1 when cluster qualifying logic met

`A5 = A5a + A5b + A5c` (max 3)

### Probiotic Bonus

Applies when `supp_type == "probiotic"` or when non-probiotic products pass strict
evidence gates and `allow_non_probiotic_probiotic_bonus_with_strict_gate` is enabled.

Gate: `feature_gates.probiotic_extended_scoring` — current config state: `false`

**Default mode (max 3):**
- CFU: +1 when total_billion > 1
- Diversity: +1 when strain_count >= 3
- Prebiotic: +1 when ingredient names contain inulin / FOS / GOS (or `prebiotic_present` flag)

**Extended mode (max 10)** — when gate enabled:

| Component | Condition | Points |
|---|---|---|
| CFU | ≥ 50B | 4 |
| CFU | ≥ 10B | 3 |
| CFU | > 1B | 2 |
| CFU | > 0 | 1 |
| Diversity | ≥ 10 strains | 4 |
| Diversity | ≥ 6 strains | 3 |
| Diversity | ≥ 3 strains | 2 |
| Diversity | > 0 strains | 1 |
| Clinical strains | ≥ 5 known | 3 |
| Clinical strains | ≥ 3 known | 2 |
| Clinical strains | ≥ 1 known | 1 |
| Prebiotic | count capped to 3 | up to 3 |
| Survivability | delayed release / enteric / acid resistant / microencapsulated | 2 |

Known clinical strain tokens: `lgg`, `bb-12`, `ncfm`, `reuteri`, `k12`, `m18`,
`coagulans`, `shirota`.

---

## Section B: Safety & Purity (max 35)

```text
B_raw = 35 + bonuses - penalties
B = clamp(0, 35, B_raw)

bonuses  = B3 + B4a + B4b + B4c
penalties = B0_moderate + B1 + B2 + B5 + B6
```

### B1 Harmful Additives (max penalty 5)

Input:
- `contaminant_data.harmful_additives.additives[]`

Severity map:
- high: 2.0
- moderate: 1.0
- low: 0.5
- none: 0.0

Summed and capped at 5.

### B2 Allergen Presence (max penalty 2)

Input:
- `contaminant_data.allergens.allergens[]`

Severity map:
- high: 2.0
- moderate: 1.5
- low: 1.0

Summed and capped at 2.

### B3 Claim Compliance (max bonus 4)

Primary booleans (explicit enricher output):
- `claim_allergen_free_validated`
- `claim_gluten_free_validated`
- `claim_vegan_validated`

Fallback derives from `compliance_data` fields with contradiction detection:
- A "may contain" warning invalidates allergen-free or gluten-free claims
- Conflicts mentioning allergen terms invalidate the relevant claim
- Gelatin/bovine/porcine in conflicts invalidates vegan claim
- Adds `LABEL_CONTRADICTION_DETECTED` when conflict exists alongside active claims

Points:
- allergen-free validated: +2
- gluten-free validated: +1
- vegan or vegetarian validated: +1

### B4 Quality Certifications (max bonus 21)

#### B4a Named Programs (max 15)
- +5 per named program; cap 15
- IFOS only counted for omega-like products (supplement type "specialty" or any active ingredient with "omega" in name)
- Input: `named_cert_programs` fallback `certification_data.third_party_programs.programs[]`

#### B4b GMP (max 4)
- NSF GMP certified (`nsf_gmp` or `gmp.claimed`) or `gmp_level == "certified"`: 4
- FDA registered (`fda_registered`) or `gmp_level == "fda_registered"`: 2
- None: 0

#### B4c Batch Traceability (max 2)
- COA (`has_coa`): +1
- Batch lookup or QR code (`has_batch_lookup` / `has_qr_code`): +1

### B5 Proprietary Blend Disclosure Penalty (max penalty 10)

**Design intent:** A1 measures ingredient quality for disclosed ingredients. B5 is the
cost of opacity — it penalises products that hide their formula behind blend labels.
These two sections measure different things and must not overlap.

Inputs:
- `proprietary_blends` fallback `proprietary_data.blends[]`
- Each blend requires `disclosure_level`, `total_weight` or `nested_count`
- `blend.evidence.severity_level` from enricher (detector-sourced blends only)

Deduplication: blend identity key = `(canon_key(name), norm_text(level), total_weight, nested_count)`.
Exact-duplicate blends from detector + cleaning are merged before scoring.

**Per-blend penalty formula:**

```text
presence_penalty = {full: 0.0, partial: 1.0, none: 2.0}
prop_coef        = {full: 0.0, partial: 3.0, none: 5.0}

impact = mg_share if total_weight and total_active_mg available,
         else hidden_count / total_active_count,
         else 1.0
impact = clamp(0, 1, impact)

blend_penalty = (presence + prop_coef × impact) × risk_mult

risk_mult = severity_level → {high: 1.5, medium: 1.2, low/unknown: 1.0}
```

`severity_level` comes from `blend.evidence.severity_level` (set by the blend detector
for stimulant / testosterone / weight-loss / nootropic category blends). Cleaning-sourced
blends have `evidence: null` and get `risk_mult = 1.0` by default.

Full disclosure (`full`) always produces `blend_penalty = 0.0` and is skipped.

Penalty ranges by disclosure level and risk:

| Disclosure | Risk | Min (tiny blend) | Max (100% of product) |
|---|---|---|---|
| none | low | 2.0 | 7.0 |
| none | medium | 2.4 | 8.4 |
| none | high | 3.0 | 10.0 (capped) |
| partial | low | 1.0 | 4.0 |
| partial | high | 1.5 | 6.0 |
| full | — | 0.0 | 0.0 |

```text
B5 = clamp(0, 10, Σ blend_penalty)
```

Adds flag `PROPRIETARY_BLEND_PRESENT` when any blend is detected.

### B6 Marketing Claims Penalty (max penalty 5)

Input paths (first true wins):
1. `has_disease_claims`
2. `product_signals.has_disease_claims`
3. `evidence_data.unsubstantiated_claims.found`

If true: penalty = 5.0, adds flag `DISEASE_CLAIM_DETECTED`.

---

## Section C: Evidence & Research (max 15)

Input:
- `evidence_data.clinical_matches[]`

Deduplication: entries deduplicated by `id` / `study_id` / composite key before scoring.

Per match:
```text
raw = study_base_points(study_type) × evidence_multiplier(evidence_level)
```

Study base points:

| study_type | points |
|---|---|
| systematic_review_meta | 6 |
| rct_multiple | 5 |
| rct_single | 4 |
| clinical_strain | 4 |
| observational | 2 |
| animal_study | 2 |
| in_vitro | 1 |

Evidence multipliers:

| evidence_level | multiplier |
|---|---|
| product-human / product-rct / product | 1.0 |
| branded-rct | 0.8 |
| ingredient-human | 0.65 |
| strain-clinical | 0.6 |
| preclinical | 0.3 |
| unknown | 0.0 |

Dose guard: when `min_clinical_dose` is present and the product dose (after unit conversion)
is below that threshold, `raw` is multiplied by `0.25`. Adds `SUB_CLINICAL_DOSE_DETECTED`.
Unit conversion supports mass units (g / mg / mcg / ug) only; IU and CFU conversions are
skipped (returns None = no dose guard applied).

Capping:
- max 5 points per canonical ingredient
- `C = clamp(0, 15, Σ per_ingredient_points)`

---

## Section D: Brand Trust (max 5)

```text
D = min(5, D1 + D2 + min(1.5, D3 + D4 + D5))
```

Components:

| Component | Condition | Points |
|---|---|---|
| D1 Trusted manufacturer | `is_trusted_manufacturer == true` OR `top_manufacturer.found == true` with `match_type == "exact"` | 2.0 |
| D2 Full disclosure | All active ingredients have a dose AND no hidden/partial blends | 1.0 |
| D3 Physician formulated | `claim_physician_formulated` or `bonus_features.physician_formulated` | 0.5 |
| D4 High-standard region | `country_of_origin.high_regulation_country` or known high-standard region | 0.5 |
| D5 Sustainable packaging | `has_sustainable_packaging` or `bonus_features.sustainability_claim` | 0.5 |

High-standard regions: USA, EU, UK, Germany, Switzerland, Japan, Canada, Australia,
New Zealand, Norway, Sweden, Denmark.

`D3 + D4 + D5` are collectively capped at 1.5. Total D capped at 5.

---

## Manufacturer Violation Penalty (Post-Section)

Input (preference order):
1. `manufacturer_data.violations.total_deduction_applied` (top-level sum, preferred)
2. Sum of `total_deduction_applied` on each item in `violations.violations[]`
3. Legacy fallback: `total_deduction` on each item (older enrichment outputs)

Rules:
- Stored as a negative float
- Added directly to `quality_raw` after section sum
- Floor at `-25.0`
- Adds flag `MANUFACTURER_VIOLATION` when non-zero deduction applied

---

## Verdict Derivation

Precedence (first match wins):

| Priority | Verdict | Condition |
|---|---|---|
| 1 | `BLOCKED` | `b0.blocked == true` |
| 2 | `UNSAFE` | `b0.unsafe == true` |
| 3 | `NOT_SCORED` | mapping gate stopped |
| 4 | `CAUTION` | `B0_MODERATE_SUBSTANCE` or `BANNED_MATCH_REVIEW_NEEDED` in flags |
| 5 | `POOR` | `quality_score < 32` |
| 6 | `SAFE` | default |

Backward-compatible `safety_verdict` mapping (for downstream consumers):
- `POOR` → `SAFE`
- `NOT_SCORED` → `CAUTION`
- All others mirror `verdict`

---

## Output Fields (Core)

Top-level score fields:
- `quality_score` / `score_80` — raw score out of 80
- `score_100_equivalent` — `(score_80 / 80) × 100`
- `display` — `"X.X/80"`
- `display_100` — `"X.X/100"`
- `grade` — word label (Exceptional → Very Poor)
- `verdict` — primary verdict
- `safety_verdict` — backward-compatible verdict
- `scoring_status` — `"scored"` / `"blocked"` / `"not_scored"`
- `score_basis` — reason enum
- `evaluation_stage` — `"scoring"` or `"safety"`
- `breakdown` — per-section details (A, B, C, D with sub-scores)
- `flags` — sorted, deduplicated list of all signal flags
- `supp_type` — classified type
- `mapped_coverage`
- `unmapped_actives` — list of unmapped ingredient names (banned-overlap excluded)
- `unmapped_actives_total`
- `unmapped_actives_excluding_banned_exact_alias`

Metadata block (`scoring_metadata`):
- `scoring_version`
- `output_schema_version`
- `scored_date`
- `enrichment_version`
- `scoring_status`
- `score_basis`
- `verdict`
- `flags`
- `unmapped_actives_total`
- `unmapped_actives_excluding_banned_exact_alias`
- `mapped_coverage`
- `reason`

Section scores shorthand (`section_scores`):
- `A_ingredient_quality.score` / `.max`
- `B_safety_purity.score` / `.max`
- `C_evidence_research.score` / `.max`
- `D_brand_trust.score` / `.max`

---

## Feature Gates (from `config/scoring_config.json`)

| Gate | Current | Effect when true |
|---|---|---|
| `require_full_mapping` | **true** | Any unmapped active returns `NOT_SCORED` |
| `probiotic_extended_scoring` | false | Use extended probiotic bonus module (max +10 instead of +3) |
| `allow_non_probiotic_probiotic_bonus_with_strict_gate` | true | Non-probiotic products may earn probiotic bonus if strict evidence gates pass |
| `shadow_mode` | true | Scoring runs but outputs may be non-public |

---

## Known Flags Reference

| Flag | Source | Meaning |
|---|---|---|
| `BANNED_MATCH_REVIEW_NEEDED` | B0 | Non-exact/alias banned substance match found — human review needed |
| `B0_LOW_SUBSTANCE` | B0 | Low-severity banned substance exact/alias hit |
| `B0_MODERATE_SUBSTANCE` | B0 | Moderate-severity banned substance hit; triggers CAUTION verdict + 10pt penalty |
| `DISEASE_CLAIM_DETECTED` | B6 | Product makes unsubstantiated disease claims |
| `LABEL_CONTRADICTION_DETECTED` | B3 | Compliance claims contradict other label text |
| `MANUFACTURER_VIOLATION` | Post-section | Manufacturer has documented violations; deduction applied |
| `NO_ACTIVES_DETECTED` | Mapping gate | Zero active ingredients found |
| `PROPRIETARY_BLEND_PRESENT` | B5 | At least one proprietary blend detected |
| `SUB_CLINICAL_DOSE_DETECTED` | C | At least one ingredient is below its established clinical dose threshold |
| `UNMAPPED_ACTIVE_INGREDIENT` | Mapping gate | Active ingredient(s) not in IQM; NOT_SCORED when `require_full_mapping=true` |
| `UNMAPPED_BANNED_EXACT_ALIAS_GUARD` | Regression guard | Unmatched active overlaps a banned substance exact/alias match |
| `UNMAPPED_INACTIVE_INGREDIENT` | Mapping gate | Inactive ingredient(s) not matched; advisory only, non-blocking |

---

## Production Monitoring Controls

1. `unmapped_actives_excluding_banned_exact_alias` trend by category — leading indicator of IQM coverage gaps
2. `NOT_SCORED` rate by category — expected to increase when full-mapping gate is on
3. `BANNED_MATCH_REVIEW_NEEDED` volume — token-bounded review queue load
4. Verdict drift across runs (`SAFE/POOR/CAUTION/UNSAFE/BLOCKED`) — regression signal
5. B5 average by category — monitor that stimulant/weight-loss blend products correctly hit higher penalties
