# PharmaGuide Scoring README (v3.4.0 / Data Schema 5.1.0)

> Last updated: 2026-04-22

This document is the implementation-facing guide for the current scorer:

- Code: `scripts/score_supplements.py`
- Config: `scripts/config/scoring_config.json`
- Spec: `scripts/SCORING_ENGINE_SPEC.md`

It is aligned to the current `v3.4.0` behavior in code and config.

## 1) What The Scorer Does

The scorer is deterministic arithmetic + gate logic + batch-level percentile post-processing.
It does not perform enrichment/matching NLP.

### Is scoring fully config-driven?

**Almost.** Every numeric value — section caps, subsection caps, tier points,
penalty magnitudes, bonus values, thresholds, multipliers, bands, accepted-region
lists, prebiotic-term lists, eligible-parent-blend lists, enzyme activity units,
grade scale cutoffs, verdict POOR threshold — lives in
`config/scoring_config.json`. Hardcoded literals in Python remain **only as
safety defaults** when a config key is missing (`as_float(cfg.get("max"), 15.0)`).

Retuning the scorer (rebalancing caps, adding a new category bonus, toggling a
gate, changing B1 sugar penalties, adjusting C evidence multipliers, moving D4
region list, swapping CAERS data file) requires **only a JSON edit** — no code
changes.

Not config-driven (structural, not values): the final-score formula shape,
verdict precedence order, gate ordering (B0 → mapping → regression guard →
sections), per-section aggregation algorithms, output payload shape, flag
names, badge structure.

It consumes enriched products and produces:

- `quality_score` (`score_80`)
- `score_100_equivalent`
- `verdict` / `safety_verdict`
- `badges` (including `FULL_DISCLOSURE` when applicable)
- `category_percentile` (batch-cohort percentile context)
- `percentile_category*` audit fields from enrichment (`category`, `label`, `source`, `confidence`, `signals`)
- section breakdown (`A`, `B`, `C`, `D`, `E`)
- scoring flags and metadata

## 2) Run Commands

From `/scripts`:

```bash
python3 score_supplements.py
python3 score_supplements.py --input-dir path/to/enriched --output-dir path/to/scored
python3 score_supplements.py --dry-run
```

From repo root:

```bash
python3 scripts/score_supplements.py
python3 scripts/score_supplements.py --input-dir scripts/path/to/enriched --output-dir scripts/path/to/scored
```

## 3) High-Level Scoring Flow

For each product:

1. Validate required product identity (`dsld_id`, `product_name`, enrichment metadata).
2. Run B0 immediate safety gate (blocked/unsafe/moderate/review semantics).
3. Run mapping gate (`require_full_mapping` behavior).
4. Apply unmapped+banned exact/alias regression guard.
5. Score sections A/B/C/D.
6. Compute omega-3 dose adequacy inside Section A when applicable, then emit legacy `E_dose_adequacy` output for backward compatibility.
7. Apply manufacturer violation penalty.
8. Derive final verdict and output payload.

## 4) Score Model (v3.4)

Final score:

```text
quality_raw = A + B + C + D + violation_penalty
quality_score = clamp(0, 80, quality_raw)
score_100_equivalent = (quality_score / 80) * 100
```

Section caps:

| Section                | Max    | Notes                                                               |
| ---------------------- | ------ | ------------------------------------------------------------------- |
| A: Ingredient Quality  | 25     |                                                                     |
| B: Safety & Purity     | 30     |                                                                     |
| C: Evidence & Research | 20     |                                                                     |
| D: Brand Trust         | 5      |                                                                     |
| E: Dose Adequacy       | 3      | Legacy output only; score contribution is now folded into Section A |
| **Total ceiling**      | **80** | All sections clamped together at 80                                 |

Omega-3 dose adequacy is now a category bonus inside Section A. `E_dose_adequacy`
is still emitted in `breakdown`/`section_scores` so existing consumers do not break,
but it is no longer added as a standalone term in `quality_raw`.

## 5) Section Details

### Section A: Ingredient Quality (max 25)

```text
core_quality = A1 + A2 + A3 + A4 + A5 + A6
category_bonus_total = min(5, probiotic_bonus + omega3_dose_bonus + future_bonus_terms...)
A = min(25, core_quality + category_bonus_total)
```

- A1 (max 18, config-driven): weighted bioavailability score.
  - Excludes blend containers (`is_proprietary_blend=true`).
  - Excludes rows without usable individual dose.
  - Excludes parent-total rows (`is_parent_total=true`) to prevent double-counting
    when a label lists both a nutrient total and its sub-forms.
  - Mapped row uses `score` and `dosage_importance`.
  - Unmapped row fallback is score `9.0`, weight `1.0`.
  - `single` and `single_nutrient`: force all weights to `1.0`.
  - `multivitamin`: smoothing `avg = 0.7*avg + 0.3*9.0` (factor and floor both config-driven).
  - Final: `clamp(0, max, (avg / range_max) * max)` where `range_max` comes from `range_score_field` (currently `0-18`).
- A2 (max 5, config-driven): premium forms bonus — count of unique ingredients with `score >= threshold_score` (default 14), scored as `points_per_additional_premium_form * max(0, count - 1)` when `skip_first_premium_form=true`.
  - excludes blend containers (`is_proprietary_blend=true`)
  - excludes parent-total rows (`is_parent_total=true`)
  - requires usable individual dose (same dose-anchored rule as A1/A6)
  - stacking 4+ premium forms can reach the full 5 pts
- A3 (max 3): delivery tier points (tier 1 → 3, tier 2 → 2, tier 3 → 1).
- A4 (max 3): absorption enhancer paired boolean.
- A5 (max 3): organic + standardized botanical + synergy cluster (+ optional gated non-GMO contribution).
- A6 (max 3): single-ingredient efficiency bonus for `supp_type in {single, single_nutrient}` using IQM form score tiers (`>=16`=3, `>=14`=2, `>=12`=1).
  - uses `score` as primary value
  - falls back to `bio_score` only when `score` is missing
- Category bonus pool (`category_bonus_pool.max_contribution`, default **5**):
  - Pools `probiotic_bonus + omega3_dose_bonus + enzyme_recognition_bonus + probiotic_cfu_adequacy_uplift`
  - Prevents stacked niche bonuses from dominating core ingredient quality
  - `A = min(25, core_quality + category_bonus_total)`
- **Probiotic bonus:**
  - default mode max 3
  - extended mode max 10 (gated by `probiotic_extended_scoring`)
  - non-probiotic strict-gate path enabled by `allow_non_probiotic_probiotic_bonus_with_strict_gate`
- **Probiotic CFU adequacy uplift** (Sprint E1.3.2.c, max 5 — config-driven):
  - per-strain CFU credit layered on probiotic_bonus
  - tier points: `low=0`, `adequate=1`, `good=2`, `excellent=3`
  - support-level caps: `high=1.0x`, `moderate=0.75x`, `weak=0.5x`
  - hard gates: blend-member without individual dose → 0; tier=None → 0; blend-total inference forbidden
- **Omega-3 dose bonus** (max 3 — config-driven):
  - only for products with explicit labelled EPA / DHA / EPA+DHA
  - bands: `≥4000`=3.0 (+`PRESCRIPTION_DOSE_OMEGA3`), `≥2000`=2.5, `≥1000`=2.0, `≥500`=1.0, `≥250`=0.5
  - parent-mass fallback (Sprint E1.3.3): when EPA/DHA individually NP but parent fish/krill oil carries total mass, infer `EPA+DHA = parent_mass * epa_dha_fraction_of_parent` (default 0.5); flags `omega3_dose_source="inferred_from_parent_mass"`
  - contributes through the Section A category bonus pool
- **Enzyme recognition bonus** (Sprint E1.3.4, max 2.5 — config-driven):
  - small credit for enzyme-containing products whose individual enzyme doses are labelled NP
  - `per_enzyme_points=0.5`, deduped by canonical enzyme name, cap 2.5
  - `min_activity_gate` currently disabled (placeholder until activity-unit audit data lands)

### Section B: Safety & Purity (max 30)

Sign convention: penalties are positive magnitudes and are subtracted once.

```text
B_raw = base_score + bonuses - penalties
B = clamp(0, 30, B_raw)
base_score = 25
bonuses = min(5, B3 + B4a + B4b + B4c + B_hypoallergenic)
penalties = B0_moderate + B1 + B2 + B5 + B6 + B7 + B8
```

- B0: immediate safety gate logic.
  - v5.0 status-based: `banned` -> UNSAFE, `recalled` -> BLOCKED, `high_risk` -> -10 + CAUTION, `watchlist` -> -5 + CAUTION.
  - Pre-5.0 severity fallback: `critical/high` -> UNSAFE, `moderate` -> -10 + CAUTION, `low` -> advisory.
  - Non-exact/alias matches -> review-only (`BANNED_MATCH_REVIEW_NEEDED`).
  - Source: `banned_recalled_ingredients.json` (143 entries, schema 5.0.0).
- B1: harmful additives penalty (cap **15**, config-driven via `B1_harmful_additives.cap`).
  - Named-sweetener / additive match path: risk points `high` = 2.0, `moderate` = 1.0, `low` = 0.5 (no critical tier — critical hazards use B0 gate; `critical=3.0` still accepted for pre-5.1 backward compat).
  - Source-aware suppression: low/moderate additives sourced from the Supplement Facts active panel are suppressed (already captured by IQM). High/critical still fire for actives.
  - Deduplicated by `additive_id` (highest severity wins).
  - Source: `harmful_additives.json` (115 entries, schema 5.1.0, 20 categories, all deep-audited).
  - Cap raised from 8 → 15 so products stacking 5+ critical additives take the full penalty without being compressed.
  - **Amount-based sugar penalty (v3.4.1, 2026-04-10)**: layered on top of the named-sweetener path. Reads `dietary_sensitivity_data.sugar.level` from the enricher and docks:
    - `moderate` level (3 g < sugar_g ≤ 5 g) → `-0.5`
    - `high` level (sugar_g > 5 g) → `-1.5`
    - `sugar_free`/`low` or missing data → no penalty (safe default).
    - Emits flags `SUGAR_LEVEL_MODERATE` / `SUGAR_LEVEL_HIGH` and an evidence entry with `type="dietary_sugar"`, `level`, `amount_g`, `penalty`.
    - Combined with the named-sweetener penalty, the total B1 penalty is still clamped to the existing B1 cap (8).
    - **Config-driven** via `section_B_safety_purity.B1_dietary_sugar_penalty` in `scoring_config.json` (keys: `enabled`, `moderate_penalty`, `high_penalty`, `cap`). This enables future per-user personalization — e.g. a stronger penalty for diabetic profiles — without touching scoring code.
    - Rationale: a gummy with 6 g added sugar previously received the same quality score as an identical 0 g formulation because the scorer ignored `dietary_sensitivity_data`. Users saw the "High Sugar" warning in `top_warnings` but the score didn't reflect it. This closes the UI-vs-score gap.
- B2: allergen penalty (capped at 2).
- B3: claim compliance bonus (max 4 inside shared bonus pool).
- B4: quality certifications (computed internally, pooled under bonus cap).
- B5: proprietary blend transparency penalty (max 10).
- B6: disease/marketing claim penalty (max 5).
- B7: dose safety penalty (max 3). Penalises products with ingredients exceeding 150% of highest adult UL. Per ingredient: -2.0, capped at -3.0 total. Below 150%, UL enforcement is deferred to phone-side Section E1 (user-profile-aware). Source: `rda_ul_data.safety_flags` from enricher, verified against `rda_optimal_uls.json`.
- B8: CAERS adverse event penalty (max 5). FDA pharmacovigilance signal — real-world adverse event reports from consumers/providers. Per ingredient: `strong` (100+ serious reports) = -4.0, `moderate` (25-99) = -2.0, `weak` (10-24) = -1.0, capped at -5.0 total. Distinct from B0 (regulatory actions) and B1 (excipient quality) — B8 captures statistical harm volume on active ingredients. Source: `caers_adverse_event_signals.json` (159 ingredients, schema 1.0.0), ingested from FDA CAERS bulk download via `ingest_caers.py`. Config-gated (`enabled: true` in `B8_caers_adverse_events`).
- Optional gated `B_hypoallergenic` contribution can be added to bonus pool.

#### B5 proprietary blend model

Per blend:

```text
hidden_mass_mg = max(blend_total_mg - disclosed_child_mg_sum, 0)
impact = clamp(hidden_mass_mg / total_active_mg, 0, 1)  # mg-share path
if hidden_mass_mg > 0 and impact < 0.1: impact = 0.1

fallback impact = clamp(hidden_count / max(total_active_count, 8), 0, 1)  # count-share path

presence = {full:0, partial:1, none:2}
coef = {full:0, partial:3, none:5}
blend_penalty = presence + coef * impact
B5 = clamp(0, 10, sum(blend_penalty))
```

The scorer also emits per-blend evidence payloads used for explainability.

### Section C: Evidence & Research (max 20)

- Match source: `evidence_data.clinical_matches[]`
- Reference DB: `backed_clinical_studies.json` (197 entries, 100% with PMID-backed key endpoints)
- Per-match formula (all multipliers config-driven):
  `raw = study_base_points * evidence_level_multiplier * effect_direction_multiplier * enrollment_quality_multiplier`
- **Effect-direction multipliers** (new in v3.4, `effect_direction_multipliers`): `positive_strong=1.0`, `positive_weak=0.85`, `mixed=0.6`, `null=0.25`, `negative=0.0`. Missing field defaults to `positive_strong`.
- **Enrollment quality bands** (new in v3.4, `enrollment_quality_bands`, RCT / meta only): `<50→0.6x`, `50-199→0.8x`, `200-499→1.0x`, `500-999→1.1x`, `≥1000→1.2x`. Observational / preclinical bypass this adjustment.
- Sub-clinical dose guard: multiply by `sub_clinical_dose_guard_multiplier` (default 0.25) when product dose < `min_clinical_dose`. Adds `SUB_CLINICAL_DOSE_DETECTED`.
- Supra-clinical flag: adds `SUPRA_CLINICAL_DOSE` when product dose > `supra_clinical_multiple` × max studied dose (default 3.0, informational only).
- Per-ingredient cap: `cap_per_ingredient` (default **7**).
- **Top-N diminishing-returns aggregation** (new in v3.4, `top_n_weights`, default `[1.0, 0.5, 0.25]`): per-ingredient scores sorted descending and multiplied by positional weights before summing. Prevents multivitamin inflation — best ingredient 100%, 2nd 50%, 3rd 25%, 4th+ 0%.
- **Depth bonus** (new in v3.4, `depth_bonus_bands` `[[20, 0.25], [40, 0.5]]`): reads `published_studies_count` from matched reference entry. 0-19 trials → +0.0, 20-39 → +0.25, ≥40 → +0.5. Added after top-N aggregation.
- Section cap: `cap_total` (default **20**).

Evidence DB coverage (as of 2026-04-02):
- 197 entries: 132 ingredient-human, 38 branded-rct, 17 product-human, 6 strain-clinical, 4 preclinical
- All 197 entries have `key_endpoints` populated with PubMed PMID-backed clinical outcome data
- All 197 entries have `references_structured` with verified citations
- All 197 entries have `effect_direction` classified (128 positive_strong, 40 positive_weak, 25 mixed, 4 null)
- Section C depth bonus reads numeric counts from `published_studies_count` when present. Legacy `published_studies` remains a human-readable evidence-tag field and is not parsed as a count.
- Discovery/enrichment tooling now keeps `registry_completed_trials_count` separate from `published_studies_count` and can carry `effect_direction_rationale`, `effect_direction_confidence`, and `endpoint_relevance_tags` for operator auditability.
- Auto-discovery via `discover_clinical_evidence.py` now auto-populates `key_endpoints` from
  ClinicalTrials.gov outcome measures with PubMed PMID cross-references (no manual review needed for endpoints)

### Section D: Brand Trust (max 5)

```text
D = min(5, D1 + D2 + min(2.0, D3 + D4 + D5))
```

- D1: trusted manufacturer path.
  - `2` for trusted/exact match.
  - optional gated middle-tier `1` for verifiable NSF/USP/GMP evidence.
- D2: full disclosure.
- D3: physician formulated.
- D4: high-standard region contribution.
- D5: sustainability.

### Legacy Section E Output: Dose Adequacy — EPA+DHA

`E_dose_adequacy` is now a backward-compatibility output only. The same EPA/DHA
math still runs, but the actual score contribution is stored in `A.omega3_dose_bonus`
and included in Section A through the category bonus pool.

Legacy E is **not applicable** to products with no labelled EPA or DHA quantities
(`score=0.0`, `max=0.0`, `applicable=false`).

```text
per_day_mid = (per_day_min + per_day_max) / 2
where:
  per_day_min = (EPA_mg + DHA_mg) per unit × min_servings_per_day
  per_day_max = (EPA_mg + DHA_mg) per unit × max_servings_per_day
```

Band table (highest matching threshold wins):

| Threshold (mg/day EPA+DHA) | Score | Label               | Clinical Anchor                                                                     |
| -------------------------- | ----- | ------------------- | ----------------------------------------------------------------------------------- |
| ≥ 4000                     | 3.0   | `prescription_dose` | AHA/ACC Rx dose for hypertriglyceridemia; also adds `PRESCRIPTION_DOSE_OMEGA3` flag |
| ≥ 2000                     | 2.5   | `high_clinical`     | EFSA health claim for blood triglycerides                                           |
| ≥ 1000                     | 2.0   | `aha_cvd`           | AHA recommendation for CVD patients                                                 |
| ≥ 500                      | 1.0   | `general_health`    | FDA qualified health claim minimum                                                  |
| ≥ 250                      | 0.5   | `efsa_ai_zone`      | EFSA Adequate Intake for general population                                         |
| ≥ 0                        | 0.0   | `below_efsa_ai`     | Below EFSA AI                                                                       |

Ingredient inclusion rules for the EPA+DHA sum:

- canonical_ids `"epa"`, `"dha"`, or `"epa_dha"` (combined node contributes to both buckets)
- Excludes `is_proprietary_blend`, `is_blend_header`, and `is_parent_total` rows
- Only `mg`, `g`, or `mcg` units accepted; others skipped

Serving basis resolution (in priority order):

1. `product.serving_basis.min_servings_per_day` / `max_servings_per_day`
2. `product.dosage_normalization.serving_basis.servings_per_day_min` / `_max`
3. Default: 1.0

### Output badges

- `FULL_DISCLOSURE` badge is emitted when:
  - product is not `BLOCKED`, `UNSAFE`, or `NOT_SCORED`
  - disclosure evaluation is true:
    - if enriched `has_full_disclosure` exists, scorer uses it directly
    - otherwise scorer computes from:
      - all non-blend active ingredients have usable individual doses
      - no proprietary blend is `partial` or `none`

Badge payload:

```json
{
  "id": "FULL_DISCLOSURE",
  "label": "FULL DISCLOSURE",
  "description": "This product lists exact amounts for every active ingredient."
}
```

### Category percentile output

Percentile is assigned after each batch is fully scored (cohort-aware pass).

- Cohort key priority:
  1. `percentile_category` from enrichment (recommended)
  2. scorer fallback inference chain
- Uses score on 100-equivalent scale.
- `top_percent` is lower-is-better (example: `Top 35%`).
- Requires minimum cohort size of `5`; otherwise scorer returns
  `category_percentile.available=false` with reason `insufficient_cohort_size`.
- `category_percentile` includes `category_source`, `category_confidence`, and `category_signals` for auditability.

## 6) Gates And Defaults (Current)

From current config (`feature_gates` block):

- `require_full_mapping = true` — any unmapped active returns `NOT_SCORED`
- `probiotic_extended_scoring = false`
- `allow_non_probiotic_probiotic_bonus_with_strict_gate = true`
- `shadow_mode = true` *(DEPRECATED — present for historical reasons, never read by the scorer)*
- `enable_non_gmo_bonus = true` — A5d: +0.5 for Non-GMO Project Verified
- `enable_hypoallergenic_bonus = false`
- `enable_d1_middle_tier = true` — D1 middle-tier reputation (+1) for verifiable NSF GMP / FDA registered / USP / named GMP evidence

Non-gate config switches (same file, other sections):

- `section_A_ingredient_quality.category_bonus_pool.max_contribution = 5`
- `section_A_ingredient_quality.enzyme_recognition.enabled = true`
- `section_A_ingredient_quality.enzyme_recognition.min_activity_gate.enabled = false`
- `section_A_ingredient_quality.probiotic_cfu_adequacy.enabled = true`
- `section_A_ingredient_quality.omega3_dose_bonus.fish_oil_parent_mass_fallback.enabled = true`
- `section_B_safety_purity.B1_dietary_sugar_penalty.enabled = true`
- `section_B_safety_purity.B8_caers_adverse_events.enabled = true`

## 7) Verdicts

Precedence:

1. `BLOCKED` — recalled substance (B0)
2. `UNSAFE` — banned substance (B0)
3. `NOT_SCORED` — mapping gate failed
4. `CAUTION` — `B0_HIGH_RISK_SUBSTANCE`, `B0_WATCHLIST_SUBSTANCE`, `B0_MODERATE_SUBSTANCE`, or `BANNED_MATCH_REVIEW_NEEDED`
5. `POOR` (`quality_score < 32`)
6. `SAFE`

Grade words (only for non-blocked, non-unsafe, non-not_scored):

- > = 90: Exceptional
- > = 80: Excellent
- > = 70: Good
- > = 60: Fair
- > = 50: Below Avg
- > = 32: Low
- < 32: Very Poor

## 8) Output Structure

Scored files:

```text
<output_dir>/
  scored/
    scored_<batch_name>.json
  reports/
    scoring_summary_<timestamp>.json
```

Core output fields include:

- `quality_score`, `score_80`, `score_100_equivalent`
- `verdict`, `safety_verdict`
- `badges`
- `category_percentile`, `category_percentile_text`
- `percentile_category`, `percentile_category_label`, `percentile_category_source`, `percentile_category_confidence`, `percentile_category_signals`
- `breakdown` (A/B/C/D plus legacy E compatibility output and penalties)
- `section_scores` (with config-driven max values)
- `flags` (including `PRESCRIPTION_DOSE_OMEGA3` when applicable)
- mapping KPI fields (`unmapped_actives_total`, `mapped_coverage`, etc.)

Legacy Section E fields in `section_scores.E_dose_adequacy`:

```json
{
  "score": 1.5,
  "max": 2.0,
  "applicable": true,
  "dose_band": "aha_cvd",
  "per_day_mid_mg": 1080.0,
  "per_day_min_mg": 900.0,
  "per_day_max_mg": 1260.0,
  "epa_mg_per_unit": 180.0,
  "dha_mg_per_unit": 120.0,
  "prescription_dose": false
}
```

When not applicable (no explicit EPA/DHA dose):

```json
{
  "score": 0.0,
  "max": 0.0,
  "applicable": false
}
```

## 9) Backward Compatibility Notes

- B and C section max values changed (B: 35 -> 30, C: 15 -> 20).
- `section_scores.*.max` now resolves from config, not hardcoded constants.
- B5 exposes both signed and magnitude penalty fields in evidence:
  - `computed_blend_penalty` (signed)
  - `computed_blend_penalty_magnitude` (positive)
- `E_dose_adequacy` remains exported for backward compatibility, but its score now comes from
  `A.omega3_dose_bonus` rather than a standalone scoring term.
- `is_parent_total` field on ingredients is new in v3.2.0 (propagated by enricher post-pass).
  Older enriched files without this field will have `is_parent_total` default to falsy via
  `.get()`, retaining old A1 behavior with no crash.

## 10) Interaction Layer (Non-Scoring)

The scorer does NOT apply interaction-based penalties. Interactions are handled separately:

- **Enrichment:** `enrich_supplements_v3.py` evaluates `ingredient_interaction_rules.json` and emits `interaction_profile` per product
- **Export:** `build_final_db.py` includes `condition_summary`, `drug_class_summary`, and per-ingredient interaction warnings in the detail blob
- **App:** Section F "fit score" is computed on-device based on user's health profile + `reference_data.interaction_rules`

This separation ensures the quality score (A/B/C/D plus legacy E compatibility output) remains objective and context-free, while the interaction layer provides personalized safety warnings.

## 11) Validation Commands

```bash
# Score tests only
cd scripts && python3 -m pytest tests/test_score_supplements.py -q

# Full suite (3906+ tests)
cd scripts && python3 -m pytest tests/ -q
```
