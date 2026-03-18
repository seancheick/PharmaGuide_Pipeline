# PharmaGuide Scoring README (v3.2.0 / Data Schema 5.0.0)

> Last updated: 2026-03-18 | 2672 tests | 549 IQM parents | 33 data files

This document is the implementation-facing guide for the current scorer:

- Code: `scripts/score_supplements.py`
- Config: `scripts/config/scoring_config.json`
- Spec: `scripts/SCORING_ENGINE_SPEC.md`

It is aligned to the current `v3.2.0` behavior in code and config.

## 1) What The Scorer Does

The scorer is deterministic arithmetic + gate logic + batch-level percentile post-processing.
It does not perform enrichment/matching NLP.

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
6. Score section E (EPA+DHA dose adequacy — omega-3 products only).
7. Apply manufacturer violation penalty.
8. Derive final verdict and output payload.

## 4) Score Model (v3.2)

Final score:

```text
quality_raw = A + B + C + D + E + violation_penalty
quality_score = clamp(0, 80, quality_raw)
score_100_equivalent = (quality_score / 80) * 100
```

Section caps:

| Section | Max | Notes |
|---------|-----|-------|
| A: Ingredient Quality | 25 | |
| B: Safety & Purity | 30 | |
| C: Evidence & Research | 20 | |
| D: Brand Trust | 5 | |
| E: Dose Adequacy | 2 | Omega-3 products only; additive bonus within the 80-pt ceiling |
| **Total ceiling** | **80** | All sections clamped together at 80 |

Section E is an additive bonus for omega-3 products that have explicit labelled EPA/DHA amounts.
It helps qualifying products reach the 80-pt ceiling with slightly lower A/B/C/D scores rather
than pushing the score beyond 80.

## 5) Section Details

### Section A: Ingredient Quality (max 25)

```text
A = min(25, A1 + A2 + A3 + A4 + A5 + A6 + probiotic_bonus)
```

- A1 (max 15): weighted bioavailability score.
  - Excludes blend containers (`is_proprietary_blend=true`).
  - Excludes rows without usable individual dose.
  - Excludes parent-total rows (`is_parent_total=true`) to prevent double-counting
    when a label lists both a nutrient total and its sub-forms.
  - Mapped row uses `score` and `dosage_importance`.
  - Unmapped row fallback is score `9.0`, weight `1.0`.
  - `single` and `single_nutrient`: force all weights to `1.0`.
  - `multivitamin`: smoothing `avg = 0.7*avg + 0.3*9.0`.
- A2 (max 3): premium forms bonus based on count of unique ingredients with score >= 14.
  - excludes blend containers (`is_proprietary_blend=true`)
  - excludes parent-total rows (`is_parent_total=true`)
  - requires usable individual dose (same dose-anchored rule as A1/A6)
- A3 (max 3): delivery tier points.
- A4 (max 3): absorption enhancer paired boolean.
- A5 (max 3): organic + standardized botanical + synergy cluster (+ optional gated non-GMO contribution).
- A6 (max 3): single-ingredient efficiency bonus for `supp_type in {single, single_nutrient}` using IQM form score tiers:
  - uses `score` as primary value
  - falls back to `bio_score` only when `score` is missing
- Probiotic bonus:
  - default mode max 3
  - extended mode max 10 (gated)
  - non-probiotic strict-gate path enabled by config.

### Section B: Safety & Purity (max 30)

Sign convention: penalties are positive magnitudes and are subtracted once.

```text
B_raw = base_score + bonuses - penalties
B = clamp(0, 30, B_raw)
base_score = 25
bonuses = min(5, B3 + B4a + B4b + B4c + B_hypoallergenic)
penalties = B0_moderate + B1 + B2 + B5 + B6
```

- B0: immediate safety gate logic.
  - v5.0 status-based: `banned` -> UNSAFE, `recalled` -> BLOCKED, `high_risk` -> -10 + CAUTION, `watchlist` -> -5 + CAUTION.
  - Pre-5.0 severity fallback: `critical/high` -> UNSAFE, `moderate` -> -10 + CAUTION, `low` -> advisory.
  - Non-exact/alias matches -> review-only (`BANNED_MATCH_REVIEW_NEEDED`).
- B1: harmful additives penalty (capped at 8).
- B2: allergen penalty (capped at 2).
- B3: claim compliance bonus (max 4 inside shared bonus pool).
- B4: quality certifications (computed internally, pooled under bonus cap).
- B5: proprietary blend transparency penalty (max 10).
- B6: disease/marketing claim penalty.
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
- Per-match points: `study_type_base_points * evidence_level_multiplier`
- Sub-clinical dose guard: multiply by `0.25` when below minimum clinical dose.
- Supra-clinical flag: adds `SUPRA_CLINICAL_DOSE` when product dose > `3x` max studied dose (informational only).
- Per-ingredient cap: `7`
- Section cap: `20`

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

### Section E: Dose Adequacy — EPA+DHA (max 2.0, omega-3 products only)

Section E rewards omega-3 products that label explicit per-unit EPA and/or DHA amounts.
It is **not applicable** to products with no labelled EPA or DHA quantities (score and max both 0.0).

```text
per_day_mid = (per_day_min + per_day_max) / 2
where:
  per_day_min = (EPA_mg + DHA_mg) per unit × min_servings_per_day
  per_day_max = (EPA_mg + DHA_mg) per unit × max_servings_per_day
```

Band table (highest matching threshold wins):

| Threshold (mg/day EPA+DHA) | Score | Label | Clinical Anchor |
|---|---|---|---|
| ≥ 4000 | 2.0 | `prescription_dose` | AHA/ACC Rx dose for hypertriglyceridemia; also adds `PRESCRIPTION_DOSE_OMEGA3` flag |
| ≥ 2000 | 2.0 | `high_clinical` | EFSA health claim for blood triglycerides |
| ≥ 1000 | 1.5 | `aha_cvd` | AHA recommendation for CVD patients |
| ≥  500 | 1.0 | `general_health` | FDA qualified health claim minimum |
| ≥  250 | 0.5 | `efsa_ai_zone` | EFSA Adequate Intake for general population |
| ≥    0 | 0.0 | `below_efsa_ai` | Below EFSA AI |

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

From current config:

- `require_full_mapping = true`
- `probiotic_extended_scoring = false`
- `allow_non_probiotic_probiotic_bonus_with_strict_gate = true`
- `shadow_mode = true`
- `enable_non_gmo_bonus = false`
- `enable_hypoallergenic_bonus = false`
- `enable_d1_middle_tier = false`

## 7) Verdicts

Precedence:

1. `BLOCKED` — recalled substance (B0)
2. `UNSAFE` — banned substance (B0)
3. `NOT_SCORED` — mapping gate failed
4. `CAUTION` — `B0_HIGH_RISK_SUBSTANCE`, `B0_WATCHLIST_SUBSTANCE`, `B0_MODERATE_SUBSTANCE`, or `BANNED_MATCH_REVIEW_NEEDED`
5. `POOR` (`quality_score < 32`)
6. `SAFE`

Grade words (only for non-blocked, non-unsafe, non-not_scored):

- >= 90: Exceptional
- >= 80: Excellent
- >= 70: Good
- >= 60: Fair
- >= 50: Below Avg
- >= 32: Low
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
- `breakdown` (A/B/C/D/E and penalties)
- `section_scores` (with config-driven max values)
- `flags` (including `PRESCRIPTION_DOSE_OMEGA3` when applicable)
- mapping KPI fields (`unmapped_actives_total`, `mapped_coverage`, etc.)

Section E fields in `section_scores.E_dose_adequacy`:

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
- Section E (`E_dose_adequacy`) is new in v3.2.0. Older enriched files that lack explicit
  EPA/DHA quantities will simply return `applicable: false` with `score: 0.0` — no breaking change.
- `is_parent_total` field on ingredients is new in v3.2.0 (propagated by enricher post-pass).
  Older enriched files without this field will have `is_parent_total` default to falsy via
  `.get()`, retaining old A1 behavior with no crash.

## 10) Interaction Layer (Non-Scoring)

The scorer does NOT apply interaction-based penalties. Interactions are handled separately:

- **Enrichment:** `enrich_supplements_v3.py` evaluates `ingredient_interaction_rules.json` and emits `interaction_profile` per product
- **Export:** `build_final_db.py` includes `condition_summary`, `drug_class_summary`, and per-ingredient interaction warnings in the detail blob
- **App:** Section F "fit score" is computed on-device based on user's health profile + `reference_data.interaction_rules`

This separation ensures the quality score (A/B/C/D/E) remains objective and context-free, while the interaction layer provides personalized safety warnings.

## 11) Validation Commands

```bash
# Score tests only
cd scripts && python3 -m pytest tests/test_score_supplements.py -q

# Full suite (2672+ tests)
cd scripts && python3 -m pytest tests/ -q
```
