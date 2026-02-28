# PharmaGuide Scoring v3.1 Rollout Notes

Date: 2026-02-26
Scope: `/scripts/score_supplements.py`, `/scripts/config/scoring_config.json`

## 1) Changelog (Concise)

- Rebalanced section weights while keeping total score cap at 80:
  - `A=25` (unchanged cap, internal changes)
  - `B=30` (was 35)
  - `C=20` (was 15)
  - `D=5` (unchanged cap, formula adjusted so max is reachable)
- A1 bioavailability scaling now uses max 15 (was 13), config-driven.
- Added A6 single-ingredient efficiency bonus:
  - active for `supp_type in {"single", "single_nutrient"}`.
- B restructured to base+bonus-pool model:
  - `B_raw = 25 + min(5, bonuses) - penalties`.
- B5 proprietary blend penalty finalized:
  - hidden-mass model (`presence + proportional*impact`)
  - cap 10
  - mg-share first, count-share fallback
  - count-share denominator hard floor: `max(total_active_count, 8)`.
- Added B5 evidence payload fields for explainability:
  - `presence_penalty`, `proportional_coef`,
  - `computed_blend_penalty`, `computed_blend_penalty_magnitude`,
  - plus impact/disclosure breakdown fields.
- Section C caps increased:
  - per-ingredient cap 7 (was 5)
  - section cap 20 (was 15)
  - added supra-clinical informational flag (`SUPRA_CLINICAL_DOSE`).
- Section D reachability update:
  - D4 high-standard-region value to 1.0
  - D3+D4+D5 combined cap to 2.0
  - max 5 now reachable.
- Added gated D1 middle tier:
  - `enable_d1_middle_tier` supports `D1=1` for verifiable NSF/USP/GMP evidence.
- Added gated optional bonuses:
  - `enable_non_gmo_bonus` (A5d)
  - `enable_hypoallergenic_bonus` (B pooled bonus contribution).
- Removed stale hardcoded section max outputs:
  - blocked/unsafe/not_scored payloads and section score metadata now use config-driven caps.

## 2) Downstream Migration Note

## 2.1 Score interpretation changes

- `B_safety_purity.max` changed from 35 to 30.
- `C_evidence_research.max` changed from 15 to 20.
- Any dashboard, alert, or normalization logic using old B/C denominators must be updated.

## 2.2 Output fields added/changed

- `breakdown.A` now includes:
  - `A6`
  - `A5d` (when non-GMO bonus gate is enabled).
- `breakdown.B` now includes:
  - `B_hypoallergenic`
  - expanded `B5_blend_evidence` payload fields.
- `section_scores.*.max` values are now resolved from config, not hardcoded.

## 2.3 B5 sign convention and arithmetic

- B5 is stored as a positive penalty magnitude in section arithmetic.
- `computed_blend_penalty` in evidence is signed (negative display contribution).
- `computed_blend_penalty_magnitude` is positive.
- If a downstream consumer sums signed and unsigned fields together, it will double-count.

## 2.4 Feature-gate defaults in config

Default state for rollout:

- `enable_non_gmo_bonus = false`
- `enable_hypoallergenic_bonus = false`
- `enable_d1_middle_tier = false`
- `probiotic_extended_scoring = false`
- `allow_non_probiotic_probiotic_bonus_with_strict_gate = true`

This means v3.1 logic is live, but optional policy expansions remain opt-in.

## 2.5 Validation checklist for consumers

- Confirm section max labels show `A25/B30/C20/D5`.
- Confirm B5 charts use cap 10, not 15.
- Confirm C charts assume cap 20 and per-ingredient cap 7.
- Confirm single/single_nutrient products can show non-zero A6.
- Confirm D can reach 5 with qualifying products.
- Confirm trend comparisons against pre-v3.1 runs are version-segmented.
