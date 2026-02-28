# PharmaGuide Scoring README (v3.1.0)

This document is the implementation-facing guide for the current scorer:

- Code: `/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/score_supplements.py`
- Config: `/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/config/scoring_config.json`

It is aligned to the current `v3.1.0` behavior in code and config.

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
- section breakdown (`A`, `B`, `C`, `D`)
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
6. Apply manufacturer violation penalty.
7. Derive final verdict and output payload.

## 4) Score Model (v3.1)

Final score:

```text
quality_raw = A + B + C + D + violation_penalty
quality_score = clamp(0, 80, quality_raw)
score_100_equivalent = (quality_score / 80) * 100
```

Section caps:

- A: 25
- B: 30
- C: 20
- D: 5
- Total: 80

## 5) Section Details

### Section A: Ingredient Quality (max 25)

```text
A = min(25, A1 + A2 + A3 + A4 + A5 + A6 + probiotic_bonus)
```

- A1 (max 15): weighted bioavailability score.
  - Excludes blend containers (`is_proprietary_blend=true`).
  - Excludes rows without usable individual dose.
  - Mapped row uses `score` and `dosage_importance`.
  - Unmapped row fallback is score `9.0`, weight `1.0`.
  - `single` and `single_nutrient`: force all weights to `1.0`.
  - `multivitamin`: smoothing `avg = 0.7*avg + 0.3*9.0`.
- A2 (max 3): premium forms bonus based on count of unique ingredients with score >= 14.
  - excludes blend containers (`is_proprietary_blend=true`)
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

- B0: immediate safety gate logic (blocked/unsafe/moderate/review).
- B1: harmful additives penalty (capped at 5).
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

1. `BLOCKED`
2. `UNSAFE`
3. `NOT_SCORED`
4. `CAUTION`
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
- `breakdown` (A/B/C/D and penalties)
- `section_scores` (with config-driven max values)
- `flags`
- mapping KPI fields (`unmapped_actives_total`, `mapped_coverage`, etc.)

## 9) Backward Compatibility Notes

- B and C section max values changed (B: 35 -> 30, C: 15 -> 20).
- `section_scores.*.max` now resolves from config, not hardcoded constants.
- B5 exposes both signed and magnitude penalty fields in evidence:
  - `computed_blend_penalty` (signed)
  - `computed_blend_penalty_magnitude` (positive)

See detailed release notes:

- `/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/SCORING_V3_1_ROLLOUT_NOTES.md`

## 10) Validation Commands

```bash
python3 -m pytest scripts/tests/test_score_supplements.py -q
python3 -m pytest scripts/tests -q
```
