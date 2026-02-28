# SCORING_ENGINE_SPEC.md

> Scoring version: **3.1.0** — aligned to current `score_supplements.py` and `config/scoring_config.json`.

## Scope

This document specifies the current server-side scoring behavior implemented in:
- `score_supplements.py`
- `config/scoring_config.json`

## Scorer Contract

Scorer is arithmetic-only. Matching and NLP are performed in enrichment. The scorer
consumes fully-enriched products and computes scores from their canonical fields.

All section caps and point values are config-driven via `scoring_config.json`. The scorer
reads caps through `_section_max()` helper and individual config lookups with hardcoded
defaults as fallback only when config keys are absent.

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

Section caps (v3.1):
- A max 25
- B max 30
- C max 20
- D max 5
- Total: 80

## Grade Scale

Applied post-verdict. Not assigned for `BLOCKED`, `UNSAFE`, or `NOT_SCORED`.

| score_100_equivalent | Grade |
|---|---|
| >= 90 | Exceptional |
| >= 80 | Excellent |
| >= 70 | Good |
| >= 60 | Fair |
| >= 50 | Below Avg |
| >= 32 | Low |
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
- Non-hard-fail types: `token_bounded` and any other value -> review-only flag

Rules:
- `status in {"recalled","both"}` + exact/alias -> `BLOCKED`
- `severity_level in {"critical","high"}` + exact/alias -> `UNSAFE`
- `severity_level == "moderate"` + exact/alias -> B0 moderate penalty `10`; adds `B0_MODERATE_SUBSTANCE`
- `severity_level == "low"` + exact/alias -> advisory only; adds `B0_LOW_SUBSTANCE`
- Any review-only (non exact/alias) hit -> `BANNED_MATCH_REVIEW_NEEDED`

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
- `total_active <= 0` -> stop with `NO_ACTIVES_DETECTED`
- if `feature_gates.require_full_mapping == true` and `mapped_coverage < 1.0` -> stop with `UNMAPPED_ACTIVE_INGREDIENT`

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
A = min(25, A1 + A2 + A3 + A4 + A5 + A6 + probiotic_bonus)
```

### A1 Bioavailability Form (max 15)

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
- `multivitamin`: smoothing applied — `avg = 0.7*avg + 0.3*9.0`

Final:
```text
A1 = clamp(0, 15, (weighted_avg / 18) * 15)
```

### A2 Premium Forms (max 3)

Rule:
- Count unique canonical ingredients with `score >= 14`
- `A2 = clamp(0, 3, 0.5 * max(0, count - 1))`

### A3 Delivery System (max 3)

Input:
- `delivery_tier` fallback `delivery_data.highest_tier`

Map:
- tier 1 -> 3
- tier 2 -> 2
- tier 3 -> 1
- else -> 0

### A4 Absorption Enhancer (max 3)

Input:
- `absorption_enhancer_paired` fallback `absorption_data.qualifies_for_bonus`

Rule:
- true -> 3
- false -> 0

Note: enricher uses `standard_name` field (not `name`) when looking up enhancers in
`absorption_enhancers.json`. Bonus requires an absorptive enhancer paired with a target
ingredient; an enhancer-only product does not qualify.

### A5 Formulation Excellence (max 3)

Subcomponents:
- A5a organic: +1 when USDA verified or valid claim path
- A5b standardized botanical: +1 when threshold/flag met
- A5c synergy cluster: +1 when cluster qualifying logic met
- A5d non-GMO verified: +0.5 (gated — requires `enable_non_gmo_bonus: true`)

`A5 = min(3, A5a + A5b + A5c + A5d)`

### A6 Single-Ingredient Efficiency (max 3)

Applies only when `supp_type in {"single", "single_nutrient"}`.

Uses the highest bio score among scorable ingredients:

| bio_score threshold | Points |
|---|---|
| >= 16 | 3 |
| >= 14 | 2 |
| >= 12 | 1 |
| < 12 | 0 |

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
| Survivability | delayed release / enteric / acid resistant / microencapsulated | 2 |

Known clinical strain tokens: `lgg`, `bb-12`, `ncfm`, `reuteri`, `k12`, `m18`,
`coagulans`, `shirota`.

---

## Section B: Safety & Purity (max 30)

Sign convention: penalties are positive magnitudes and are subtracted once.

```text
B_raw = base_score + bonuses - penalties
B = clamp(0, 30, B_raw)

base_score = 25
bonuses  = min(5, B3 + B4a + B4b + B4c + B_hypoallergenic)
penalties = B0_moderate + B1 + B2 + B5 + B6
```

- `base_score` (25) and `bonus_pool_cap` (5) are read from config
- Optional `B_hypoallergenic` (+0.5) feeds into the bonus pool (gated — requires `enable_hypoallergenic_bonus: true`; also requires zero allergen penalty, no "may contain" text, no contradictions, and at least one validated allergen-free/gluten-free claim)

### B1 Harmful Additives (max penalty 5)

Input:
- `contaminant_data.harmful_additives.additives[]`

Severity map (config-overridable):
- critical: 3.0
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
- +5 per named program; cap 15 (config-driven)
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
- Each blend requires `disclosure_level`, `blend_total_mg` (or `total_weight`), `nested_count`
- `proprietary_data.total_active_mg` (or fallback sum from active ingredients)

Deduplication: blend identity key = `(canon_key(name), sorted(child_names), total_weight, source_field)`.
Exact-duplicate blends from detector + cleaning are merged before scoring.

**Disclosure tier definitions (three-tier model per 21 CFR 101.36):**

| Tier | Definition | Example |
|---|---|---|
| `full` | Every sub-ingredient has an individual amount listed | "Proprietary Blend 500mg: Vitamin C 200mg, Zinc 50mg, Elderberry 250mg" |
| `partial` | Blend total declared AND sub-ingredients listed, but individual amounts missing | "Proprietary Blend 500mg: Vitamin C, Zinc, Elderberry" |
| `none` | Missing blend total, OR missing sub-ingredient list, OR vague/no disclosure | "Proprietary Blend" or "Proprietary Blend: [no ingredients listed]" |

Disclosure tier is assigned upstream (cleaner + detector) and consumed by the scorer as-is.

**Hidden-mass impact calculation:**

```text
disclosed_child_mg_sum = sum(mg for each child with individual amount)
hidden_mass_mg = max(blend_total_mg - disclosed_child_mg_sum, 0)

# mg-share path (preferred when blend_total_mg and total_active_mg available)
impact = clamp(0, 1, hidden_mass_mg / total_active_mg)

# count-share fallback (when mg-share unavailable)
impact = clamp(0, 1, hidden_count / max(total_active_count, 8))

# minimum impact floor
if hidden_mass_mg > 0 and impact < 0.1:
    impact = 0.1
```

**Per-blend penalty formula:**

```text
presence_penalty = {full: 0.0, partial: 1.0, none: 2.0}
prop_coef        = {full: 0.0, partial: 3.0, none: 5.0}

blend_penalty = presence_penalty + prop_coef * impact
```

Count-share denominator uses `max(total_active_count, 8)` to prevent small-formula
products from being over-penalised by a single blend. This value (8) is a constant.

Full disclosure (`full`) always produces `blend_penalty = 0.0` and is skipped.

**Penalty ranges by disclosure level:**

| Disclosure | Min (tiny blend, floor=0.1) | Max (100% of product) |
|---|---|---|
| none | 2.5 | 7.0 |
| partial | 1.3 | 4.0 |
| full | 0.0 | 0.0 |

```text
B5 = clamp(0, 10, sum(blend_penalty))
```

Adds flag `PROPRIETARY_BLEND_PRESENT` when any blend is detected.

**Edge rules:**
- Blend containers excluded from A1 (scored only in B5).
- Disclosed child without individual amount: does NOT count toward `disclosed_child_mg_sum`.
- Disclosed child WITH individual amount: counts toward `disclosed_child_mg_sum` AND gets A1 quality credit.
- Zero or negative `total_weight` is treated as no declared total (scorer normalises to None).

**B5 evidence payload (per penalized blend):**

| Field | Description |
|---|---|
| `blend_name` | Normalised blend name |
| `disclosure_tier` | full / partial / none |
| `blend_total_mg` | Total blend weight in mg (null if unavailable) |
| `disclosed_child_mg_sum` | Sum of individually-declared child amounts |
| `hidden_mass_mg` | blend_total_mg - disclosed_child_mg_sum (or null) |
| `impact_ratio` | Computed impact (0.0 – 1.0) |
| `impact_source` | "mg_share" or "count_share" |
| `impact_floor_applied` | Boolean — true when 0.1 floor was used |
| `presence_penalty` | Presence component of penalty |
| `proportional_coef` | Proportional coefficient for disclosure tier |
| `computed_blend_penalty` | Signed penalty (negative) |
| `computed_blend_penalty_magnitude` | Positive magnitude |
| `dedupe_fingerprint` | Hash used for deduplication |

### B6 Marketing Claims Penalty (max penalty 5)

Input paths (first true wins):
1. `has_disease_claims`
2. `product_signals.has_disease_claims`
3. `evidence_data.unsubstantiated_claims.found`

If true: penalty = 5.0, adds flag `DISEASE_CLAIM_DETECTED`.

---

## Section C: Evidence & Research (max 20)

Input:
- `evidence_data.clinical_matches[]`

Deduplication: entries deduplicated by `id` / `study_id` / composite key before scoring.

Per match:
```text
raw = study_base_points(study_type) * evidence_multiplier(evidence_level)
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

Supra-clinical flag: adds `SUPRA_CLINICAL_DOSE` when product dose > 3x max studied dose
(informational only, no scoring impact). Multiplier configurable via `supra_clinical_multiple`.

Capping:
- max 7 points per canonical ingredient
- `C = clamp(0, 20, sum(per_ingredient_points))`

---

## Section D: Brand Trust (max 5)

```text
D = min(5, D1 + D2 + min(2.0, D3 + D4 + D5))
```

Components:

| Component | Condition | Points |
|---|---|---|
| D1 Trusted manufacturer | `is_trusted_manufacturer == true` OR `top_manufacturer.found == true` with `match_type == "exact"` | 2.0 |
| D1 Middle-tier (gated) | `enable_d1_middle_tier: true` + verifiable NSF/USP/GMP evidence | 1.0 |
| D2 Full disclosure | All active ingredients have a dose AND no hidden/partial blends | 1.0 |
| D3 Physician formulated | `claim_physician_formulated` or `bonus_features.physician_formulated` | 0.5 |
| D4 High-standard region | `country_of_origin.high_regulation_country` or known high-standard region | 1.0 |
| D5 Sustainable packaging | `has_sustainable_packaging` or `bonus_features.sustainability_claim` | 0.5 |

D1 logic:
- `is_trusted_manufacturer == true` -> 2.0 (enricher-set flag for exact match)
- `top_manufacturer.found == true` with `match_type == "exact"` -> 2.0 (fallback)
- When `enable_d1_middle_tier: true` and manufacturer has verifiable GMP/NSF/USP/named cert evidence -> 1.0
- Otherwise -> 0.0

High-standard regions: USA, EU, UK, Germany, Switzerland, Japan, Canada, Australia,
New Zealand, Norway, Sweden, Denmark.

`D3 + D4 + D5` are collectively capped at 2.0. Total D capped at 5.

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
- `POOR` -> `SAFE`
- `NOT_SCORED` -> `CAUTION`
- All others mirror `verdict`

---

## Output Fields (Core)

Top-level score fields:
- `quality_score` / `score_80` — raw score out of 80
- `score_100_equivalent` — `(score_80 / 80) * 100`
- `display` — `"X.X/80"`
- `display_100` — `"X.X/100"`
- `grade` — word label (Exceptional -> Very Poor)
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
| `enable_non_gmo_bonus` | false | A5d: +0.5 for Non-GMO Project Verified products |
| `enable_hypoallergenic_bonus` | false | B bonus pool: +0.5 for hypoallergenic products with zero allergen penalty |
| `enable_d1_middle_tier` | false | D1: +1.0 for manufacturers with verifiable GMP/NSF/USP evidence (non-exact match) |

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
| `SUPRA_CLINICAL_DOSE` | C | At least one ingredient exceeds 3x max studied dose (informational) |
| `UNMAPPED_ACTIVE_INGREDIENT` | Mapping gate | Active ingredient(s) not in IQM; NOT_SCORED when `require_full_mapping=true` |
| `UNMAPPED_BANNED_EXACT_ALIAS_GUARD` | Regression guard | Unmatched active overlaps a banned substance exact/alias match |
| `UNMAPPED_INACTIVE_INGREDIENT` | Mapping gate | Inactive ingredient(s) not matched; advisory only, non-blocking |

---

## v3.0 -> v3.1 Change Summary

| Area | v3.0 | v3.1 |
|---|---|---|
| A1 max | 13 | 15 |
| A6 | not present | single-ingredient efficiency bonus (max 3) |
| B section max | 35 | 30 |
| B base_score | 35 | 25 |
| B bonus_pool_cap | (bonuses uncapped) | 5 |
| B1 risk_map | missing "critical" | critical: 3.0 added |
| B5 count-share denominator | total_active_count | max(total_active_count, 8) |
| C section max | 15 | 20 |
| C per-ingredient cap | 5 | 7 |
| D3+D4+D5 combined cap | 1.5 | 2.0 |
| D4 points | 0.5 | 1.0 |
| Section caps | partially hardcoded | fully config-driven via `_section_max()` |
| Feature gates | 4 gates | 7 gates (added non_gmo, hypoallergenic, d1_middle_tier) |

---

## Production Monitoring Controls

1. `unmapped_actives_excluding_banned_exact_alias` trend by category — leading indicator of IQM coverage gaps
2. `NOT_SCORED` rate by category — expected to increase when full-mapping gate is on
3. `BANNED_MATCH_REVIEW_NEEDED` volume — token-bounded review queue load
4. Verdict drift across runs (`SAFE/POOR/CAUTION/UNSAFE/BLOCKED`) — regression signal
5. B5 average by category — monitor that stimulant/weight-loss blend products correctly hit higher penalties
