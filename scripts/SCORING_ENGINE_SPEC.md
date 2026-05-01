# SCORING_ENGINE_SPEC.md

> Scoring version: **3.5.0** / Data schema: **5.3.0** / Last updated: **2026-04-29**
> Aligned to current `score_supplements.py` and `config/scoring_config.json`.

## v3.5.0 highlights

- **Banned-substance role gate** (enricher): `match_mode='active'` entries no longer
  fire on inactive-section ingredients. Eliminates ~2,000+ FP HIGH_RISK fires
  (talc/TiO2/simethicone as excipients).
- **Section C retune**: `ingredient-human` 0.65 → 0.80, `branded-rct` 0.80 → 0.90,
  `top_n_weights` [1.0, 0.5, 0.25] → [1.0, 0.7, 0.5, 0.3]. Rewards evidence-rich
  formulations (Thorne / PE / Transparent Labs) without multivitamin inflation.
- **Final-DB data integrity gate**: NOT_SCORED + null-score products are quarantined
  to `excluded_by_gate` (review_queue) instead of leaking into final_db with
  NULL scores. BLOCKED / UNSAFE / CAUTION / POOR / SAFE / NUTRITION_ONLY all ship.
- **Heavy-metal alias hardening**: removed risky `as`/`pb`/`hg`/`cd` chemistry-symbol
  aliases from heavy-metal entries.

## Scope

This document specifies the current server-side scoring behavior implemented in:
- `score_supplements.py`
- `config/scoring_config.json`

## Scorer Contract

Scorer is arithmetic-only. Matching and NLP are performed in enrichment. The scorer
consumes fully-enriched products and computes scores from their canonical fields.

### Config-Driven Design

The scorer is **almost fully config-driven**. Every numeric value the scorer uses —
section caps, subsection caps, tier points, thresholds, multipliers, bands,
penalties, bonuses, gate toggles, dedupe constants, and accepted-value lists —
lives in `config/scoring_config.json`. Hardcoded literals in the Python remain
**only as last-resort defaults** when a config key is missing (e.g.
`as_float(cfg.get("max"), 15.0)`). Changing scoring behavior does not require
code edits for:

- All section maxes (A 25 / B 30 / C 20 / D 5) via `_section_max()`
- All subsection caps (`A1.max`, `A2.max`, `B1.cap`, `B5.cap`, `B7.cap`, `B8.cap`, `C.cap_total`, `C.cap_per_ingredient`, ...)
- All point values, tier points, penalty magnitudes, band thresholds
- Feature gates (`require_full_mapping`, `probiotic_extended_scoring`, `enable_non_gmo_bonus`, `enable_hypoallergenic_bonus`, `enable_d1_middle_tier`)
- Category bonus pool cap (`category_bonus_pool.max_contribution`)
- Section C diminishing-returns weights (`top_n_weights`), evidence multipliers, effect-direction multipliers, enrollment and depth bonus bands
- B5 count-share denominator constant (`count_share_min_denominator_constant`)
- B8 CAERS data file path (`B8_caers_adverse_events.data_file`)
- D4 accepted regions list, probiotic prebiotic-term list, probiotic strict-gate parameters
- Omega-3 EPA/DHA bands, parent-mass-fallback fraction, eligible parent blends
- Enzyme recognition gating + per-enzyme points + activity-unit allow-list
- Probiotic CFU adequacy tier points and clinical-support-level caps
- B1 dietary sugar level penalty magnitudes
- Grade-scale cutoffs, verdict POOR threshold

What is **not** config-driven (structural behavior, not tunable values):

- Final-score formula shape (`quality_raw = A + B + C + D + violation_penalty`)
- Verdict precedence order and safety-verdict back-compat mapping
- Gate ordering (B0 → mapping gate → regression guard → sections)
- Output payload shape, flag names, badge structure
- Per-section aggregation algorithms (e.g. the mg-share-before-count-share B5 fallback)

In short: **point values and gates live in config; the scorer performs arithmetic only.**

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

Section caps (v3.4):
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

Status-based rules (v5.0 schema, primary path):
- `status == "banned"` + exact/alias -> `UNSAFE`
- `status == "recalled"` + exact/alias -> `BLOCKED`
- `status == "high_risk"` + exact/alias -> B0 penalty `10`; adds `B0_HIGH_RISK_SUBSTANCE`
- `status == "watchlist"` + exact/alias -> B0 penalty `5`; adds `B0_WATCHLIST_SUBSTANCE`

Severity-based fallback (pre-5.0 enriched data):
- `severity_level in {"critical","high"}` + exact/alias -> `UNSAFE`
- `severity_level == "moderate"` + exact/alias -> B0 moderate penalty `10`; adds `B0_MODERATE_SUBSTANCE`
- `severity_level == "low"` + exact/alias -> advisory only; adds `B0_LOW_SUBSTANCE`

Common rules:
- Any review-only (non exact/alias) hit -> `BANNED_MATCH_REVIEW_NEEDED`
- If a hard fail fires (blocked/unsafe), all moderate/low/watchlist flags are stripped from that evaluation.

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
core_quality         = A1 + A2 + A3 + A4 + A5 + A6
category_bonus_total = min(category_bonus_pool.max_contribution,   # default 5
                           probiotic_bonus
                         + omega3_dose_bonus
                         + enzyme_recognition_bonus
                         + probiotic_cfu_adequacy_uplift)
A                    = min(25, core_quality + category_bonus_total)
```

Design intent: core quality (A1–A6) always dominates. Niche category bonuses
(probiotic, omega-3 dose adequacy, enzyme recognition, CFU adequacy) are pooled
under a shared cap so they enhance, not define, ingredient-quality differentiation.

### A1 Bioavailability Form (max 18)

Input:
- `ingredient_quality_data.ingredients_scorable` fallback `ingredient_quality_data.ingredients`

**Blend container exclusion:** entries with `is_proprietary_blend: true` are excluded from
A1 entirely. Blend containers are opacity signals — their cost is captured by B5. Including
them in A1 would double-penalise and contaminate the quality average with a meaningless stub
score of 5.

**Parent-total exclusion:** entries with `is_parent_total: true` are excluded from A1 and A2.
When DSLD labels list a nutrient total alongside its sub-forms (e.g., "Vitamin A 10,000 IU"
as total + "Mixed Carotenes 8,000 IU" + "Retinyl Palmitate 2,000 IU" as children), only the
children are scored. The parent total is an informational/sum row that would double-count the
nutrient. Detection uses cleaned-data structural fields (`is_nested_ingredient`, `parent_blend`)
propagated through enrichment and resolved in a post-pass by `_mark_parent_total_rows()`.

Per ingredient (non-blend, non-parent-total):
- mapped: use `score` and `dosage_importance`
- unmapped: fallback `score=9.0`, `weight=1.0`

Supplement-type effects:
- `single` / `single_nutrient`: all weights forced to `1.0`
- `multivitamin`: smoothing applied — `avg = 0.7*avg + 0.3*9.0`

**Dose-anchored rule:** rows without a usable individual dose (`_has_usable_individual_dose`)
are skipped. This prevents opaque blend children without per-item amounts from contributing
to A1.

Final (both cap and range driven by `A1_bioavailability_form.max` / `range_score_field`):
```text
A1 = clamp(0, max_points, (weighted_avg / range_max) * max_points)
# current config: max_points = 18, range_max = 18 (from "0-18")
```

### A2 Premium Forms (max 5)

Config: `A2_premium_forms.{max, threshold_score, points_per_additional_premium_form, skip_first_premium_form}`.

Rule (fully config-driven):
- Count unique canonical ingredients with `score >= threshold_score` (default 14)
- Excludes `is_proprietary_blend`, `is_parent_total`, and rows without a usable
  individual dose (same dose-anchored rule as A1/A6)
- Deduplicated by `canon_key(canonical_id or standard_name)` via set
- `effective = max(0, count - 1)` when `skip_first_premium_form: true`, else `count`
- `A2 = clamp(0, max, points_per_additional_premium_form * effective)`
- Current config: `max=5`, `points_per_additional_premium_form=0.5`, `skip_first=true`
  → stacking 4+ premium forms (e.g. chelated Mg + methylated B12 + K2-MK7 + D3)
  can reach the full 5 pts.

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

### Probiotic CFU Adequacy Uplift (category bonus, max 5)

Config: `section_A_ingredient_quality.probiotic_cfu_adequacy`. Config-driven
per-strain CFU adequacy credit layered on top of `probiotic_bonus`. Points follow
confidence — only single-strain blends with knowable per-strain CFU receive
points; multi-strain blends and `tier=None` always contribute 0.

- `tier_points`: `low=0`, `adequate=1`, `good=2`, `excellent=3`
- `support_level_caps` (by `clinical_support_level`): `high=1.0x`, `moderate=0.75x`, `weak=0.5x`
- `per_product_max_uplift`: 5.0
- Hard gates (non-negotiable): blend-member without individual dose → 0;
  `adequacy_tier=None` → 0; blend-total inference → forbidden.

Feeds the Section A category bonus pool (not standalone).

### Omega-3 Dose Bonus (category bonus, max 2)

Config: `section_A_ingredient_quality.omega3_dose_bonus`. EPA+DHA daily dose
adequacy bonus for products with explicit labelled EPA and/or DHA amounts.
Formerly standalone Section E; now a Section A category bonus.

- Applicable when `ingredient_quality_data.ingredients` contains `canonical_id in {epa, dha, epa_dha}` with a usable quantity field
- Lookup: `per_day_mid = ((min_serving/day + max_serving/day) / 2) * (EPA + DHA mg per unit)`
- Highest-matching band wins (config-driven, current bands):

| min_mg_day | score | label | flag |
|---|---|---|---|
| ≥ 4000 | 2.0  | prescription_dose | `PRESCRIPTION_DOSE_OMEGA3` |
| ≥ 2000 | 1.75 | high_clinical | — |
| ≥ 1000 | 1.6  | aha_cvd | — |
| ≥ 500  | 1.0  | general_health | — |
| ≥ 250  | 0.5  | efsa_ai_zone | — |
| ≥ 0    | 0.0  | below_efsa_ai | — |

**Cap rationale (clinician decision 2026-05-01):** AHA evidence-based dose for cardiovascular protection is 1g/day. Above that, marginal benefit is unclear and bleeding risk rises (anticoagulant interaction). The 80-pt quality-led model shouldn't be derailed by a single nutrient's dose, and prescription-dose products still surface the `PRESCRIPTION_DOSE_OMEGA3` flag for visibility. Bands redistributed within 0–2 to preserve tier differentiation rather than expanding to 3.0.

**Krill-specific composition fields:** krill_oil entries carry per-form `epa_percent` / `dha_percent` (Aker BioMarine + Neptune published composition; ~12-13% EPA, ~7% DHA; `confidence_level=inferred`). Used by the parent-mass fallback when EPA/DHA are not individually labelled but a krill-oil parent mass is.

**Opacity transparency flag:** when EPA/DHA bonus is 0 because the omega-class ingredient is buried in an opaque proprietary blend (`disclosure_level=none`), the scorer emits `bonus_missed_due_to_opacity=true` + flag `OMEGA3_BONUS_MISSED_OPAQUE_BLEND` so the UI can distinguish "doesn't contain omega-3" from "contains omega-3 but undisclosed." This honors the deterministic principle (no estimation) while still surfacing the cause.

**Parent-mass fallback** (`fish_oil_parent_mass_fallback`, enabled): when EPA
and DHA are individually NP but the parent fish-oil / krill-oil row carries a
total mass, infer `EPA+DHA = parent_mass_mg * epa_dha_fraction_of_parent`
(default 0.5). Adds `omega3_dose_source="inferred_from_parent_mass"` for
transparency. `eligible_parent_blends` list is config-driven.

### Enzyme Recognition Bonus (category bonus, max 2.5)

Config: `section_A_ingredient_quality.enzyme_recognition` (enabled). Small
recognition credit for enzyme-containing products whose individual enzyme doses
are labelled NP, preventing misleading Section A = 0 on enzyme-dominated
formulas.

- `per_enzyme_points`: 0.5 (deduped by canonical enzyme name)
- `max_points`: 2.5
- `require_named_enzyme`: true
- `min_activity_gate`: currently `enabled=false` (placeholder). When flipped on,
  only enzymes with activity values ≥ `min_value` in `allowed_units`
  (`DU, HUT, FIP, ALU, CU, SKB, FCC-PU, HCU, BGU, GalU`) are credited.

### Category Bonus Pool (`category_bonus_pool.max_contribution`, default 5)

All four category bonuses above (`probiotic_bonus`, `probiotic_cfu_adequacy`,
`omega3_dose_bonus`, `enzyme_recognition`) are summed then clamped to
`max_contribution` before being added to `core_quality`. Prevents niche bonuses
from dominating ingredient quality.

---

## Section B: Safety & Purity (max 30)

Sign convention: penalties are positive magnitudes and are subtracted once.

```text
B_raw = base_score + bonuses - penalties
B = clamp(0, 30, B_raw)

base_score = 25
bonuses  = min(5, B3 + B4a + B4b + B4c + B_hypoallergenic)
penalties = B0_moderate + B1 + B2 + B5 + B6 + B7 + B8   # B8 = 0 since 2026-04-30 (disabled, see B8 section)
```

- `base_score` (25) and `bonus_pool_cap` (5) are read from config
- Optional `B_hypoallergenic` (+0.5) feeds into the bonus pool (gated — requires `enable_hypoallergenic_bonus: true`; also requires zero allergen penalty, no "may contain" text, no contradictions, and at least one validated allergen-free/gluten-free claim)

### B1 Harmful Additives (max penalty 15)

Config: `section_B_safety_purity.B1_harmful_additives` + `B1_dietary_sugar_penalty`.

Input:
- `contaminant_data.harmful_additives.additives[]` (named-sweetener / additive path)
- `dietary_sensitivity_data.sugar.{level, amount_g}` (amount-based sugar path)

**Named-additive severity map** (config-overridable, `risk_points`):
- critical: 3.0  *(accepted for backward compat; no entries use it in schema 5.1)*
- high: 2.0
- moderate: 1.0
- low: 0.5
- none: 0.0

Source-aware suppression: low/moderate additives sourced from the
Supplement Facts active panel are suppressed (already captured via IQM
quality scoring). High/critical still fire for actives (genuine safety).

Deduplicated by `additive_id` (highest severity wins per ID).

**Dietary sugar amount penalty** (`B1_dietary_sugar_penalty`, enabled, layered
on top of the named path):
- `moderate` level (3g < sugar_g ≤ 5g) → `-0.5`
- `high` level (sugar_g > 5g) → `-1.5`
- `sugar_free` / `low` / missing → 0
- Emits `SUGAR_LEVEL_MODERATE` / `SUGAR_LEVEL_HIGH` + evidence entry
- Config-driven magnitudes enable future per-profile personalization (e.g.
  stronger penalty for diabetic users) without code change.

Total B1 = clamp(0, `B1_harmful_additives.cap`, named_penalty + sugar_level_penalty).
Current cap = **15** (raised from 8 so products stacking 5+ critical additives
take the full penalty without being compressed).

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

### B7 Dose Safety Penalty (max penalty 3)

**Design intent:** Products with any ingredient exceeding 150% of the most conservative
adult UL (`highest_ul` from `rda_optimal_uls.json`) are objectively dangerous regardless
of who takes them. Below 150%, UL enforcement is a personalisation concern handled on-device
(Section E1 in the Flutter app, using the user's age/sex-specific UL).

Input:
- `rda_ul_data.safety_flags[]` — computed by the enricher, each flag has `pct_ul`, `nutrient`, `amount`, `ul`

```text
for each safety_flag where pct_ul >= threshold_pct (default 150):
    ingredient_penalty = single_penalty (default 2.0)
    add flag OVER_UL_{nutrient}

B7 = min(cap, sum(ingredient_penalties))
```

Config defaults (scoring_config.json → B7_dose_safety):
- `threshold_pct`: 150 — only penalise at 150%+ of highest_ul
- `single_penalty`: 2.0 — per ingredient
- `cap`: 3.0 — maximum total B7 penalty

**Pipeline vs phone separation:**

| Condition | Pipeline (B7) | Phone (E1) |
|---|---|---|
| Under all ULs | Nothing | Normal dosage scoring (0-7 pts) |
| Over highest_ul by <150% | Warning in `top_warnings` only | -5 pt penalty (user's UL or highest_ul fallback) |
| Over highest_ul by 150%+ | -2.0 penalty + warning | -5 pt penalty (intentional double-count — objectively dangerous) |
| 2+ ingredients over 150%+ | -3.0 cap + warnings | -5 per ingredient |

Evidence payload (per penalized ingredient):
```json
{
  "nutrient": "Vitamin A",
  "amount": 7500,
  "ul": 3000,
  "pct_ul": 250.0,
  "penalty": 2.0
}
```

---

### B8 CAERS Adverse Event Penalty — DISABLED 2026-04-30 (formerly max penalty 5)

**Status:** disabled in production (`B8_caers_adverse_events.enabled = false`).
Penalty math, data file, and Section B output keys (`B8_penalty`, `B8_caers_evidence`)
remain wired for forward compatibility — `B8_penalty` always emits `0.0` and
`B8_caers_evidence` emits `[]`. No code or schema changes required to re-enable;
flip the config flag once the dataset is normalized.

**Why disabled:** raw CAERS report counts are exposure-confounded — they measure
*popularity* far more than *risk*. The original `strong` tier (≥100 serious reports → −4.0)
penalized RDA staples at the same magnitude as genuinely dangerous substances:

| ingredient | serious_reports | reality |
|---|---|---|
| calcium | 2,145 | RDA staple, in every multivitamin |
| vitamin D | 1,301 | RDA staple |
| fiber | 1,252 | benign |
| fish-oil omega-3 | 831 | clinically beneficial |
| **kratom** | **759** | **261 deaths attributed** |
| magnesium | 610 | RDA staple |
| protein | 505 | inert macro |

A plain multivitamin (Ca + D + Mg + Zn + Fe) hit the −5.0 cap instantly with zero
attributable risk, while kratom got the same penalty bucket. ~1,966 SAFE-tier
products in the corpus were dragged below 50 by this base-rate confound.

Genuinely dangerous CAERS-flagged ingredients (kratom, ephedra, yohimbe, garcinia
cambogia, DMAA, DHEA at high dose, comfrey, kava) are already enforced by:
- **B0 banned_recalled** — regulatory actions, BLOCKED/UNSAFE verdicts
- **B1 harmful_additives** — formulation-level hazards

So disabling B8 does not weaken safety enforcement; it removes a popularity tax.

**Re-enabling (future work):** require either
1. **PRR/ROR-normalized signals** — divide each ingredient's reports by total CAERS
   volume (proportional reporting ratio / reporting odds ratio) so popularity
   cancels out, OR
2. **Curated causally-attributable allowlist** — only penalize ingredients with
   ≥1 death/transplant/hospitalization with established causation (≈10–15 entries:
   kratom, ephedra, yohimbe, garcinia, green-tea-extract at hepatotoxic doses,
   DHEA, 5-HTP, black cohosh, licorice, goldenseal, raspberry ketones).

**Preserved for reference (the disabled formula):**

```text
for each ingredient with a CAERS signal:
    if signal_strength == "strong" (>=100 serious reports): penalty = 4.0
    if signal_strength == "moderate" (25-99 serious reports): penalty = 2.0
    if signal_strength == "weak" (10-24 serious reports):    penalty = 1.0
    add flag CAERS_SIGNAL_{ingredient}

B8 = min(cap, sum(ingredient_penalties))   # cap = 5.0
```

Config (`scoring_config.json → B8_caers_adverse_events`):
- `enabled`: **false** *(was true; disabled 2026-04-30)*
- `strong_penalty`: 4.0, `moderate_penalty`: 2.0, `weak_penalty`: 1.0, `cap`: 5.0
- `data_file`: `data/caers_adverse_event_signals.json` (159 ingredients, schema 1.0.0, retained)

Evidence payload (per penalized ingredient, when re-enabled):
```json
{
  "ingredient": "kratom",
  "signal_strength": "strong",
  "serious_reports": 759,
  "total_reports": 801,
  "penalty": 4.0
}
```

**Note on prior base-rate filtering:** the ingestion script (`ingest_caers.py`)
already drops multi-ingredient combo products (multivitamins, "Centrum", "One A
Day", products with >3 extracted ingredients) to limit noise — but this filters
the *report* side only, not the *exposure* side, which is why the popularity
confound persisted at scoring time and is the reason for full disablement.

---

## Section C: Evidence & Research (max 20)

Input:
- `evidence_data.clinical_matches[]`

Reference database: `backed_clinical_studies.json` — 197 entries (as of 2026-04-02).
All entries carry PMID-backed `key_endpoints`, `references_structured` citations,
`effect_direction` classification, and `notable_studies` text. Numeric study-count
signals for depth bonus are read from `published_studies_count` when available;
the human-readable `published_studies` tags are not interpreted as counts.
Operator-facing auditability fields such as `effect_direction_rationale`,
`effect_direction_confidence`, `registry_completed_trials_count`, and
`endpoint_relevance_tags` travel through enrichment for explainability, but are
not direct scoring inputs in the current Section C formula.

Auto-discovery pipeline (`discover_clinical_evidence.py discover --apply`):
- Queries ClinicalTrials.gov API v2 for completed trials, enrollment, phases,
  and primary/secondary outcome measures
- Cross-references each NCT ID against PubMed via E-utilities (`"{NCT_ID}"[si]`)
  to resolve published PMIDs
- Auto-populates `key_endpoints` with formatted outcome measure strings including
  NCT ID, enrollment, and PMID when available
- Queries ChEMBL for compound safety flags (withdrawn, black_box_warning)
- Only adds entries with >= `--min-trials` completed trials and no safety flags

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
| branded-rct | **0.9** *(v3.5: was 0.8 — branded RCTs on the actual product warrant near-product-tier credit)* |
| ingredient-human | **0.8** *(v3.5: was 0.65 — generic ingredient-form RCTs are still high-quality evidence; old multiplier under-rewarded the bulk of the corpus)* |
| strain-clinical | 0.65 |
| preclinical | 0.3 |
| unknown | 0.0 |

Dose guard: when `min_clinical_dose` is present and the product dose (after unit conversion)
is below `sub_clinical_dose_guard_multiplier * min_clinical_dose` (default 0.25), `raw` is
multiplied by that same factor. Adds `SUB_CLINICAL_DOSE_DETECTED`.
Unit conversion supports mass units (g / mg / mcg / ug) only; IU and CFU conversions are
skipped (returns None = no dose guard applied).

Supra-clinical flag: adds `SUPRA_CLINICAL_DOSE` when product dose > `supra_clinical_multiple`
× max studied dose (default 3.0, informational only, no scoring impact).

**Effect-direction multiplier** (config: `effect_direction_multipliers`, new in v3.4):

| effect_direction | multiplier |
|---|---|
| positive_strong (default) | 1.0 |
| positive_weak | 0.85 |
| mixed | 0.6 |
| null | 0.25 |
| negative | 0.0 |

Applied as `raw *= effect_direction_multiplier`. Entries without `effect_direction`
default to `positive_strong (1.0x)` for backward compatibility.

**Enrollment quality bands** (config: `enrollment_quality_bands`, RCT / meta only):

| enrollment | multiplier |
|---|---|
| < 50 | 0.6x |
| 50 – 199 | 0.8x |
| 200 – 499 | 1.0x |
| 500 – 999 | 1.1x |
| ≥ 1000 | 1.2x (default) |

Observational / preclinical entries bypass enrollment quality adjustment.

**Top-N diminishing-returns aggregation** (config: `top_n_weights`, **v3.5
default `[1.0, 0.7, 0.5, 0.3]`**, was `[1.0, 0.5, 0.25]` pre-v3.5): after
per-ingredient caps, the per-ingredient scores are sorted descending and each
rank is multiplied by its positional weight before summing. Prevents
multivitamin inflation while still rewarding evidence-rich targeted formulations
— the best ingredient scores at 100%, 2nd at 70%, 3rd at 50%, 4th at 30%, 5th+
at 0% (truncated to weights list length). The pre-v3.5 [1.0, 0.5, 0.25] curve
collapsed too aggressively: a 4-ingredient stack with strong evidence on each
was indistinguishable from a 1-ingredient product, under-crediting honest
combination products. The v3.5 curve restores ~50% headroom on ranks 2-4 while
still asymptoting to zero.

**Depth bonus** (config: `depth_bonus_bands`, discrete thresholds):

| published_studies_count | bonus |
|---|---|
| 0 – 19 | +0.0 |
| 20 – 39 | +0.25 |
| ≥ 40 | +0.5 |

Uses `published_studies_count` from the matched reference entry (not the
human-readable `published_studies` text). Added after top-N aggregation and
before the section cap.

Capping (config-driven):
- max `cap_per_ingredient` points per canonical ingredient (default 7)
- `C = clamp(0, cap_total, sum(top_n_weighted_per_ingredient_points) + depth_bonus)` (default cap_total 20)

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
| 4 | `CAUTION` | `B0_MODERATE_SUBSTANCE`, `B0_HIGH_RISK_SUBSTANCE`, `B0_WATCHLIST_SUBSTANCE`, or `BANNED_MATCH_REVIEW_NEEDED` in flags |
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
| `shadow_mode` | true | **DEPRECATED / UNUSED.** Present in `scoring_config.json.feature_gates` for historical reasons but never read by the scoring engine. If shadow-mode publication gating is needed in the future, enforce it in `sync_to_supabase.py` or `build_final_db.py`, not here. |
| `enable_non_gmo_bonus` | true | A5d: +0.5 for Non-GMO Project Verified products |
| `enable_hypoallergenic_bonus` | false | B bonus pool: +0.5 for hypoallergenic products with zero allergen penalty |
| `enable_d1_middle_tier` | **true** | D1: +1 for manufacturers with verifiable mid-tier evidence (NSF GMP, FDA registered, USP, named GMP cert) |

Non-gate configurable switches (same file, different sections):

| Config path | Current | Effect |
|---|---|---|
| `section_A_ingredient_quality.enzyme_recognition.enabled` | true | Enzyme recognition bonus active (max 2.5) |
| `section_A_ingredient_quality.enzyme_recognition.min_activity_gate.enabled` | false | When true, only enzymes with valid activity units + values credit |
| `section_A_ingredient_quality.probiotic_cfu_adequacy.enabled` | true | Per-strain CFU adequacy uplift active (max 5) |
| `section_A_ingredient_quality.omega3_dose_bonus.fish_oil_parent_mass_fallback.enabled` | true | Infer EPA+DHA from parent fish/krill oil mass when individual NP |
| `section_B_safety_purity.B1_dietary_sugar_penalty.enabled` | true | Amount-based sugar penalty layered on B1 |
| `section_B_safety_purity.B8_caers_adverse_events.enabled` | **false** | DISABLED 2026-04-30 — raw CAERS counts confound popularity with risk (calcium 2,145 reports vs kratom 759 hit same penalty bucket); genuine danger covered by B0 + B1. Re-enable only with PRR/ROR-normalized data or curated allowlist. |

---

## Known Flags Reference

| Flag | Source | Meaning |
|---|---|---|
| `BANNED_MATCH_REVIEW_NEEDED` | B0 | Non-exact/alias banned substance match found — human review needed |
| `B0_HIGH_RISK_SUBSTANCE` | B0 | High-risk substance (v5.0 status); triggers CAUTION verdict + 10pt penalty |
| `B0_WATCHLIST_SUBSTANCE` | B0 | Watchlist substance (v5.0 status); triggers CAUTION verdict + 5pt penalty |
| `B0_LOW_SUBSTANCE` | B0 | Low-severity banned substance exact/alias hit (pre-5.0 fallback) |
| `B0_MODERATE_SUBSTANCE` | B0 | Moderate-severity banned substance hit (pre-5.0 fallback); triggers CAUTION verdict + 10pt penalty |
| `DISEASE_CLAIM_DETECTED` | B6 | Product makes unsubstantiated disease claims |
| `OVER_UL_{nutrient}` | B7 | Ingredient exceeds 150% of highest adult UL (e.g. `OVER_UL_Vitamin A`) |
| `CAERS_SIGNAL_{ingredient}` | B8 | FDA CAERS adverse event signal found for ingredient (e.g. `CAERS_SIGNAL_kratom`) |
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

## Enriched Ingredient Structural Fields

These fields are set by the enricher on each `ingredients_scorable` entry and consumed
by the scorer to prevent double-counting of parent nutrient totals.

| Field | Type | Source | Description |
|---|---|---|---|
| `is_nested_ingredient` | `bool` | Cleaned data (`isNestedIngredient`) | `True` for sub-form rows listed under a parent nutrient total. Propagated directly from cleaned ingredient object. |
| `parent_blend` | `str\|null` | Cleaned data (`parentBlend`) | Name of the parent nutrient this sub-form belongs to (e.g., `"Folate"` for a Folic Acid child row). `null` for top-level rows. |
| `is_parent_total` | `bool` | Enricher post-pass (`_mark_parent_total_rows`) | `True` when a top-level active+mapped row shares a `canonical_id` with nested children whose `parent_blend` matches this row's name (via `_normalize_text`). Default `False`. |

**Detection criteria** (all must be true to flag `is_parent_total`):
1. `source_section == "active"` (not promoted-from-inactive)
2. `mapped == True` and `canonical_id` is present
3. `is_nested_ingredient == False` (top-level row)
4. At least one sibling in the same `canonical_id` group has `is_nested_ingredient == True`
5. That sibling's `parent_blend` matches this row's `name` after `_normalize_text()` normalization

**Scorer behavior**: A1 and A2 skip rows with `is_parent_total == True`. B5 and other
sections are unaffected. Old enriched files without these fields degrade gracefully
(`.get("is_parent_total")` returns `None`/falsy, so no rows are skipped).

**Migration note**: This fix only applies after re-enrichment. Old enriched files
without `is_parent_total` retain old A1 behavior.

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
| B1 cap | 5 | 8 |
| B1 dedup | none | by `additive_id` (highest severity wins) |
| Subsection caps | hardcoded | all config-driven |

## v3.2 / v3.3 / v3.4 Change Summary

| Area | Pre-3.2 | v3.2 | v3.3 | v3.4 |
|---|---|---|---|---|
| A1 max | 15 | 15 | 15 | **18** (plus range anchored to `range_score_field`) |
| A2 max | 3 | 3 | 3 | **5** (stacking 4+ premium forms reaches full) |
| B1 cap | 8 | 8 | 8 | **15** |
| Section E (EPA/DHA) | separate standalone bonus | introduced, max 2.0 | folded into Section A as `omega3_dose_bonus`; legacy output preserved | max raised to 3.0 |
| Category bonus pool | n/a | n/a | introduced (`max_contribution`, default 5) | unchanged |
| `is_parent_total` dedup | not applied | A1/A2 skip parent-total rows | unchanged | unchanged |
| `B1_dietary_sugar_penalty` | n/a | n/a | n/a | added — amount-based sugar penalty layered on B1 |
| `enzyme_recognition` bonus | n/a | n/a | n/a | added — max 2.5 (Sprint E1.3.4) |
| `probiotic_cfu_adequacy` uplift | n/a | n/a | n/a | added — per-strain CFU adequacy, max 5 (Sprint E1.3.2.c) |
| `fish_oil_parent_mass_fallback` | n/a | n/a | n/a | added — infer EPA+DHA from parent mass (Sprint E1.3.3) |
| Section C aggregation | simple sum of per-ingredient points | same | same | v3.4: **Top-N diminishing returns** (`top_n_weights`, default `[1.0, 0.5, 0.25]`); **v3.5: retuned to `[1.0, 0.7, 0.5, 0.3]`** + multiplier bumps (`branded-rct` 0.8→0.9, `ingredient-human` 0.65→0.8) |
| Section C effect direction | ignored | ignored | ignored | **`effect_direction_multipliers`** applied per match |
| Section C enrollment quality | ignored | ignored | ignored | **`enrollment_quality_bands`** (RCT / meta only) |
| Section C depth bonus | n/a | n/a | n/a | **`depth_bonus_bands`** from `published_studies_count` |
| B8 CAERS pharmacovigilance | n/a | n/a | n/a | added v3.4 — per-ingredient FDA adverse-event penalty, max 5; **DISABLED v3.5 (2026-04-30)** — raw counts confound popularity with risk; genuine danger covered by B0 + B1 |

---

## Data Schema v5.0 Changes (affecting scorer)

| Area | Before v5.0 | v5.0 |
|---|---|---|
| B0 primary logic | `severity_level` based (critical/high/moderate/low) | `status` based (banned/recalled/high_risk/watchlist) |
| B0 `"both"` status | Treated as recalled | Removed; entries migrated to `recalled` |
| Enricher hit payload | `severity_level` from banned entry | `severity_level` derived from `status` via `_STATUS_TO_SEVERITY` map |
| Banned entry `match_mode` | Not present | `active`/`disabled`/`historical` — enricher skips non-active |
| Banned `severity_level` field | Present on entries | Removed; scorer falls back to severity-based logic only for pre-5.0 enriched data |

---

## Data Schema v5.1 Changes (affecting scorer)

| Area | v5.0 | v5.1 |
|---|---|---|
| harmful_additives entries | 108 | 107 (Chromium VI migrated to banned_recalled) |
| harmful_additives severity tiers | `critical`, `high`, `moderate`, `low` | `high`, `moderate`, `low` only |
| harmful_additives categories | 43 (fragmented) | 20 (normalized enum) |
| harmful_additives CUI field | Top-level `CUI` + `external_ids.umls_cui` (duplicate) | Top-level `cui` only (lowercase) |
| harmful_additives `external_ids` | Always present (often all-null) | Present only when `cas` or `pubchem_cid` is non-null |
| harmful_additives removed fields | — | `label_tokens`, `regex`, `exposure_context`, `entity_type`, `class_tags`, `severity_score` |
| harmful_additives ID prefix | Mix of `ADD_` and `BANNED_ADD_` | `ADD_` only (8 entries renamed) |
| banned_recalled entries | 138 | 139 (Chromium VI added as `HM_CHROMIUM_HEXAVALENT`) |
| banned_recalled `cui` field | Removed in v5.0 | Re-added and populated via UMLS API (87/139 non-null) |
| B1 risk_map `critical` | 3.0 (no entries used it) | Removed from data; code accepts for backward compat |
| B1 scoring_rule metadata | "Critical: -5, High: -3" (stale) | "High: -2.0, Moderate: -1.0, Low: -0.5" (matches code) |

---

## Production Monitoring Controls

1. `unmapped_actives_excluding_banned_exact_alias` trend by category — leading indicator of IQM coverage gaps
2. `NOT_SCORED` rate by category — expected to increase when full-mapping gate is on
3. `BANNED_MATCH_REVIEW_NEEDED` volume — token-bounded review queue load
4. Verdict drift across runs (`SAFE/POOR/CAUTION/UNSAFE/BLOCKED`) — regression signal
5. B5 average by category — monitor that stimulant/weight-loss blend products correctly hit higher penalties
