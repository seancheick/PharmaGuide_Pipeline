# V4 Phase 4 — Trust → Verification Bonus (Design Spec)  ⚠️ HIGH RISK

**Date:** 2026-05-31
**Phase:** 4 of 12 (V4 Scoring Finalization)
**Commit prefix:** `refactor(v4-trust)`
**Pre-execute gates (mandatory):** `plan-eng-review` + `codex` before any code; `benchmark` after.

## Problem

Trust is a 15-pt **dimension inside the 100-pt denominator**. Absent
certification ≈ a 13% score penalty, crushing clean uncertified products.
Convert Trust from a denominator dimension to an additive **verification bonus
(0–8)**, like `manufacturer_trust`.

## Current architecture (verified)

`DIMENSION_CAPS` (generic, omega, probiotic, multi_prenatal each define their own):
`formulation 30 + dose 25 + evidence 20 + trust 15 + transparency 10 = 100`.

`_assemble_score` (generic.py:296; sports.py imports it; omega/probiotic/multi
each have a near-identical copy):
```
sum evaluable dims; if evaluable_max == 100 -> class_subtotal = sum
                     else                    -> class_subtotal = (sum/evaluable_max)*100   # renorm
adjusted = class_subtotal + manufacturer_trust + manufacturer_violations + safety_hygiene
raw_score_100 = clamp(adjusted, 0, 100); calibrated = 25 + 0.75*raw
```
Trust scorers: `generic_trust.score_trust` (B4a≤12, B4b≤4, B4c, B4d; clamp 15)
used by generic/sports/probiotic/multi; `omega_trust` (different B4a) used by omega.

## Target assembly

```
core = formulation + dose + evidence + transparency        # max 85, NATIVE scale
raw_score = core + verification_bonus(<=8) + manufacturer_trust(<=5)
                 + safety_hygiene(<=10, ->4 in Phase 5) - manufacturer_violations
raw_score_100 = clamp(raw_score, 0, 100); then calibrate
```
**Critical rule:** core stays on its native ≤85 scale. Do NOT do `(core/85)*100`.

## The danger (why this is HIGH RISK)

After removing trust, `evaluable_max` for the full core = **85, never 100**, so
the existing `else: (sum/evaluable_max)*100` branch would **always** fire and
renormalize 85→100 — the exact hidden inflation the plan forbids. `_assemble_score`
MUST be rewritten so the core is summed on its native scale.

## Decisions LOCKED (2026-05-31, user)

- **D1 = Cap 8, linear rescale ×8/15.** Scale the existing B4a–d component
  scores by 8/15 (keep scope-aware diminishing returns); max bonus 8. Rationale:
  the SAFE/POOR boundary is `raw_score = 40`, so an 8-cap lets full verification
  lift only products whose core already reaches raw ≈ 32 (v3's POOR line) — it
  rewards borderline products, never genuinely weak ones. Headroom math: core 85
  + manufacturer 5 + hygiene 4 (post-Phase-5) = 94 baseline, +8 → 100 for a
  strong verified product. Rescale (not hard-clamp) preserves differentiation
  between lightly- and thoroughly-verified products (hard-clamp saturates at one
  cert). 15 rejected (rescues raw-25 products; wastes ~9 clamped pts). NOTE: this
  intentionally refines the plan's literal "capped at 8" → "rescaled to 8".
- **D2 = Native ≤85 core, None→0, no renormalization.** Botanical/specialty
  dose deflation in the interim is covered by Phase 6 + retained botanical CAUTION
  ceiling; `benchmark` quantifies it.
- **D3 = Extract one shared assembly.** omega/probiotic/multi import the single
  shared `_assemble_score` + core caps (sports already does). Removes 4-copy drift.

## Three architecture decisions (resolved above)

### D1 — 0–15 trust → 0–8 bonus mapping
- **(A, recommended, plan-literal)** Same B4 components, hard-clamp the total at 8.
  Simple; high-cert products saturate at 8 (acceptable — verification is now a
  modest bonus, not a top-end differentiator).
- **(B)** Linear rescale `bonus = trust_score * 8/15`. Preserves gradation among
  well-verified products; diverges from the plan's "capped at 8" wording.

### D2 — `None` (non-evaluable) dimension handling
Today a `None` dim (e.g. botanical with no RDA/UL dose benchmark) is *excluded
from the denominator and the rest renormalized* so it isn't punished. With "no
renormalization," that trick is gone.
- **(A, recommended)** Native ≤85 core, no renorm; a `None` dim contributes 0.
  Botanicals/specialty deflate on dose in the interim — **covered by Phase 6**
  (botanical/collagen dose adapters) and the botanical-anchor CAUTION ceiling
  stays until then. Benchmark must quantify the interim deflation.
- **(B)** Preserve fairness by lowering that product's clamp ceiling by the
  excluded max (no upscaling of achieved points). More complex; partial renorm.

### D3 — Shared assembly vs 4 edited copies
- **(A, recommended)** Extract one shared `_assemble_score` + core `DIMENSION_CAPS`
  (sports already imports generic's). Make omega/probiotic/multi import it too.
  Kills the 4-divergent-copies risk. Higher one-time blast radius.
- **(B)** Surgically edit each of the 4 copies identically. Lower blast radius
  per edit, but perpetuates divergence risk.

## Migration path (plan)

1. New `scripts/scoring_v4/modules/verification_bonus.py` — `score_verification_bonus(product, module)` wraps the module-appropriate trust scorer (generic vs omega) and returns a bounded 0–8 bonus + components/metadata. Old `generic_trust.py` / `omega_trust.py` kept as **compatibility wrappers** until parity tests pass.
2. Remove `("trust", 15)` from core `DIMENSION_CAPS`; rewrite `_assemble_score` to sum core natively + add `verification_bonus` as an additive term.
3. Each module populates `verification_bonus` instead of the trust dimension.
4. Update `score_supplements_v4_shadow.py` assembly/breakdown to surface `verification_bonus`.
5. Old trust modules retired only after parity tests confirm identical signals → bounded bonus.

## Anti-regression tests (mandatory, from PHASE_MAP)

- No-cert product does NOT lose 15 points by default (it loses nothing in the denominator).
- Verified product gets a bounded bonus (≤8).
- Core dimensions + bonuses clamp at 100.
- NO hidden `(score/evaluable_max)*100` normalization after trust removal (assert core summed natively).
- Score cannot exceed 100.
- Parity: same trust input signals → same bounded bonus across generic & omega paths.

## Eng-review outcomes (plan-eng-review, 2026-05-31)

- **A4 resolved:** `generic_trust` and `omega_trust` BOTH cap at 15 (`CAP_TRUST=15.0`,
  `dim_cap=15`); only the B4a sub-cap differs (12 vs 10). So the ×8/15 rescale is
  valid uniformly across both module paths.
- **A1 blast radius:** five existing tests lock the current 5-dim assembly —
  `test_v4_{generic,omega,multi_prenatal,probiotic}_final_assembly_*.py` +
  `test_v4_confidence_p14.py`. They MUST be rewritten (not deleted) as part of the change.
- **M1 no double-count:** removing `trust` from `DIMENSION_CAPS` and adding the bonus
  is a clean cut — the trust *dimension* ceases to exist the instant the bonus is added.
  Compat wrappers keep `generic_trust.py`/`omega_trust.py` importable, not double-running.
- **A3 LOCKED (user):** accept the interim raw-score drop from removing the hidden
  85→100 renormalization; benchmark documents it as EXPECTED; do NOT touch the affine
  calibration until Phase 9 decides the final scale against the corrected raw distribution.

## Revision after outside-voice review (codex unavailable → opus adversarial subagent; verdict RECONSIDER)

The independent review surfaced blockers. Resolutions (user-locked 2026-05-31):

- **#2 Botanical POOR floor-flip (BLOCKER) → add a botanical raw-floor guard in
  Phase 4.** Today `dose=None` botanicals renorm *up* (evaluable_max=75); removing
  trust + renorm at once could drop them under the raw-40 POOR floor, and the
  botanical CAUTION ceiling (a Layer-1 carry, shadow.py:138) does NOT block that
  floor. Phase 4 MUST add a guard so anchor/`dose=None` botanicals do not get
  stamped POOR purely from the assembly change before Phase 6's dose adapter lands.
  Mechanism: exempt the botanical-anchor flag from the raw-40 POOR floor (keep its
  existing CAUTION ceiling), OR apply a minimum raw floor for that flag, until
  Phase 6. Test: a clean `dose=None` botanical does NOT flip SAFE→POOR across the change.
- **#5 Benchmark gate redesign.** The old "products rise / no inflation" criterion
  contradicts the accepted raw drop (A3). Replace with **per-category raw-delta
  tolerance bands + verdict-flip tracking**: expect a broad raw drop; BLOCK if
  (a) uncertified products drop *more* than certified (the relative fix failed),
  (b) any clean botanical flips SAFE→POOR, or (c) `shipped_safety_downgrades > 0`.
- **#3/#4 Parity reframed.** `verification_bonus` DELEGATES to the module-appropriate
  trust scorer and applies ×8/15. The test is **per-module** (`bonus == round(that
  module's trust_score × 8/15)`) + clamp/bound — NOT cross-module (generic B4a cap 12
  vs omega 10 structurally disagree). Old trust modules are KEPT (they are the
  implementation the bonus calls), not "retired after parity."
- **#0 B4d kept** in verification_bonus (carry-forward; Phase 4 doesn't introduce the
  brand/manufacturer_trust overlap, it preserves today's behavior).
- **#1 Interim top-compression accepted** (only core≥77 + heavy bonuses clamp; Phase 5
  hygiene→4 resolves it). Benchmark counts how many products clamp at 100.
- **#6 Implementation notes:** remove the `evaluable_max == 100.0` equality branch
  ENTIRELY (always native sum — do NOT rewrite to `== 85.0`, that silently re-adds
  renorm); check the completeness `score_cap` interaction (raw drop shifts products
  vs the calibrated-score cap); update the stale "capped at 100" docstring in
  `GenericModuleResult`.

## Exit gate

> "Certified products improve. Uncertified clean products not crushed. No hidden 90→100 inflation."

Verification: anti-regression tests green (incl. botanical no-SAFE→POOR-flip guard
and per-module parity); `benchmark` per-category raw-delta within tolerance with NO
uncertified-worse-than-certified, NO botanical SAFE→POOR flips, `shipped_safety_downgrades = 0`.
Interim raw-score drop is EXPECTED (renorm removal) and recalibrated in Phase 9 (A3).
