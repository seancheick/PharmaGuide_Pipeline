# V4 Phase 3 — Role-Aware Completeness (Design Spec)

**Date:** 2026-05-31
**Phase:** 3 of 12 (V4 Scoring Finalization)
**Commit prefix:** `feat(v4-completeness)`
**File:** `scripts/scoring_v4/gate_completeness.py` (+ tests)

## Purpose

Stop products being capped / forced to CAUTION because an **adjunct** ingredient
lacks data. Consume the Phase-2 role classifier so caps key off ingredient
*role*, not mere existence.

## Verified current behavior (grounded, not assumed)

Mapping the 8-row treatment table against the live code shows **7 of 8 rows are
already correct** because the v4 module branches only fire their cap when that
ingredient class IS the routed module (i.e. the primary):

| # | Situation | Required | Current code | Verdict |
|---|---|---|---|---|
| 1 | Primary probiotic missing CFU | cap/CAUTION | `module=="probiotic"` branch caps 60 + CAUTION (gate_completeness.py:440-444) | already correct |
| 2 | Adjunct probiotic missing CFU | no cap | non-probiotic module → probiotic branch skipped; soft policy only tags `probiotic_product_cfu_evidence` (398-399), no cap | already correct |
| 3 | Primary omega missing EPA/DHA | cap/NOT_SCORED | `module=="omega"` branch → `missing.append("epa_or_dha_disclosed")` → NOT_SCORED (494-498) | already correct |
| 4 | **Adjunct omega missing** | **no product cap** | **soft policy caps 65 for ANY low-conf omega aggregate regardless of module (391-393)** | **BUG — fix** |
| 5 | Primary sports missing dose | cap/CAUTION | `module=="sports"` branch, gated on `_has_sports_primary_identity_signal` → cap 50 + CAUTION (516-521) | already correct |
| 6 | Adjunct sports missing dose | no cap | non-sports module → sports branch skipped; soft policy tags `sports_primary_dose_evidence` only (395-396) | already correct |
| 7 | Primary botanical missing dose | dose 0 / cap | `botanical_anchor_only_evidence` CAUTION only when whole product is the anchor (375-377) | already correct (until Phase 6) |
| 8 | Adjunct botanical missing dose | no bonus only | anchor-only CAUTION requires `not has_normal_scoring_row` → adjunct botanical doesn't trigger it | already correct |

Evidence emission confirmed module-agnostic: `omega_epa_dha_aggregate`
(scoring_input_contract.py:595-615) and `percent_dv_dose` (638-663) are emitted
per-row for any product, so their soft-policy caps leak onto adjuncts.

## The fix (surgical)

Role-gate the two soft-policy caps in `_soft_policy_from_scoring_evidence`:

1. **`low_confidence_omega_breakdown` → score_cap 65** (391-393): apply ONLY
   when the omega aggregate's identity is `primary`/`claim_prominent`. Otherwise
   keep the `soft_missing` audit tag but DROP the cap.
2. **`percent_dv_dose` → score_cap 60** (401-403): apply ONLY when the %DV
   ingredient (`anchor_canonical`) is `primary`/`claim_prominent`. Otherwise keep
   the tag, drop the cap.

Cap-eligibility = `{primary, claim_prominent}` (user Q2). `major`/`adjunct` never
product-cap.

### Mechanism

- `evaluate_completeness_gate` already derives `ingredients` via
  `get_scoring_ingredients`. Extend `classify_ingredient_roles` with an optional
  `rows=` param (additive, backward-compatible) so the gate classifies its
  already-derived rows without a second derivation pass.
- Build `cap_eligible = {r["canonical_id"] for r in roles if r["role"] in
  ("primary","claim_prominent")}`, pass into `_soft_policy_from_scoring_evidence`.
- Gate the two caps on membership: omega checks `"epa_dha"`/`clean_identity_id`;
  percent_dv checks `anchor_canonical`.

No change to module branches (already role-correct). No change to NOT_SCORED
hard gates. `botanical_anchor_only_evidence` CAUTION retained until Phase 6.

## Test plan (TDD — `test_v4_role_aware_completeness.py`)

8 parametrized rows + the regression for the actual fix:

- Row 4 (the bug, must go RED first): multivitamin/generic with an adjunct
  low-confidence omega aggregate → `score_cap is None`, `verdict_ceiling is None`,
  but `soft_missing` still contains the omega tag (credit suppressed, not capped).
- percent_dv adjunct → no cap; percent_dv on a primary/claim_prominent → cap 60 kept.
- Rows 1,3,5 (primary caps) still fire (pin existing correct behavior).
- Rows 2,6,8 (adjunct, no cap) pinned.
- A primary omega low-confidence product (module==omega) → cap 65 STILL applies
  (proves the gate didn't over-relax).

## Exit gate (PHASE_MAP)

> "No product becomes CAUTION because of adjunct-only missing data. No primary
> product looks complete when primary dose is absent."

Verification: row-4 + percent_dv adjunct tests green; primary-cap pins green;
full `test_v4_completeness_gate.py` + evidence-contract regression unchanged;
corpus delta shows adjunct-omega/percent-dv products lose their cap while
omega-module products keep theirs.
