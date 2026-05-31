# V4 Phase 2 — Ingredient Role Classification (Design Spec)

**Date:** 2026-05-31
**Phase:** 2 of 12 (V4 Scoring Finalization)
**Commit prefix:** `feat(v4-roles)`
**Status:** design locked (user-approved 2026-05-31)

## Purpose

Add deterministic, scoring-time ingredient **role classification** so Phase 3
(role-aware completeness) can stop capping entire products because an *adjunct*
ingredient lacks data. Phase 2 **classifies only** — it does not change any
score, cap, or verdict. Caps are decided in Phase 3.

## Scope (YAGNI)

- One new public function: `classify_ingredient_role()` in
  `scripts/scoring_input_contract.py`.
- Compatibility mode: computed at scoring time from the enriched blob. Native
  enricher-emitted roles are explicitly **deferred** (plan "What's Deferred").
- No changes to caps, verdicts, or module routing in this phase.

## Role labels and the level→role mapping (user-approved Option 1)

| Priority | Meaning | Role | Notes |
|---|---|---|---|
| L1 | Drives the selected scoring module | `primary` | reuse `router.py` driver signals (single source of truth) |
| L2 | Named in product title | `claim_prominent` | `role_source: "product_name"`, `role_reason: "named_in_product_title"` |
| L3 | Front-label claim | `claim_prominent` | **only if a real claims field exists** — it does not today, so L3 is inert. Do NOT emit `role_reason: "front_label_claim"` or invent claims. |
| L4 | Required for subtype | `major` | from `primary_type` / `supplement_taxonomy` |
| L5 | High comparable-unit mass/dose ratio | `major` | unit-normalized (mg/mcg/g/IU) before comparison |
| L6 | Everything else | `adjunct` | |

First matching level wins (deterministic precedence). A row gets exactly one role.

## Honest provenance contract (non-negotiable, per user)

Every classified row emits:

```json
{
  "role": "primary | claim_prominent | major | adjunct",
  "role_reason": "<machine reason, e.g. drives_module_omega_epa_dha | named_in_product_title | required_for_subtype | high_comparable_mass_ratio | residual_adjunct>",
  "role_source": "<provenance, e.g. router_driver | product_name | primary_type | mass_ratio | default>",
  "role_confidence": "high | medium | low"
}
```

Rationale: never let the code pretend it has a front-label-claims signal it
does not have. Inferred classifications must be visibly inferred so a later
reader (or the native-roles rebuild) knows it was computed, not enriched.

## Level-1 driver signals (reuse, don't reinvent)

Source of truth = `scripts/scoring_v4/router.py`. Level 1 `primary` is assigned
to rows whose `canonical_id` is the module driver for the routed module:

- **omega** → EPA / DHA rows (`_has_any_epa_dha_row` / omega canonicals)
- **sports** → `_SPORTS_PROTEIN_CANONICALS`, `_BCAA_CANONICALS`, `_EAA_CANONICALS`, `_SPORTS_SINGLE_CANONICALS`
- **probiotic** → strain / CFU-bearing rows
- **multi_or_prenatal** → micronutrient panel members carrying dose
- **generic** → no intrinsic single driver; falls through to L2–L6

`classify_ingredient_role()` imports/queries these rather than duplicating the
canonical sets, so router and classifier never drift.

## Comparable-unit mass ratio (L5)

"High comparable-unit mass ratio" requires normalizing units before comparing
row masses. Reuse existing `_unit_is_mass` / `_positive_quantity` helpers.
Normalize mg/mcg/g to a common base (mg); IU and activity units (ALU/CFU) are
**not** mass-comparable and are excluded from the ratio (they route via L1/L4 or
fall to adjunct). Threshold: a row is `major` by mass if its normalized mass is
≥ a configurable fraction of the product's total comparable mass (default
documented in the test; conservative, e.g. ≥ 0.25). Single-active products: the
sole comparable-mass row is `major` only if not already `primary`/`claim_prominent`.

## Phase 3 forward-reference (NOT implemented here)

User-stated cap intent for Phase 3 (recorded so Phase 3 honors it):

| Role | Phase 3 completeness consequence |
|---|---|
| `primary` | missing dose/disclosure can cap strongly |
| `claim_prominent` | missing dose/disclosure can cap moderately |
| `major` | missing dose/disclosure can cap mildly/moderately |
| `adjunct` | no product-level score cap; transparency penalty only |

## Test plan (TDD — write failing first)

Parametrized cases in `scripts/tests/test_v4_role_classification.py`:

1. **multi + tiny blend** — the tiny proprietary blend rows classify `adjunct`, not primary; panel actives are `major`/`primary`.
2. **multi + adjunct probiotic** — a small probiotic add-on in a multivitamin is `adjunct` (so Phase 3 won't cap on missing CFU).
3. **omega primary** — EPA/DHA rows are `primary` via router driver.
4. **sports primary** — protein/creatine driver is `primary`; flavor/filler is `adjunct`.
5. **botanical primary** — the title-named botanical is `claim_prominent` (named_in_product_title) when it is not the module driver (generic module).
6. **melatonin-at-1mg** — small mass but title-named / module-relevant → NOT demoted to adjunct by mass (guards the "NOT raw mass first" rule).
7. **provenance contract** — every returned row has `role`, `role_reason`, `role_source`, `role_confidence`; no row emits `front_label_claim` reason.

Each test asserts a behavior, watched-fail-first, before implementation.

## Exit gate (from PHASE_MAP)

> "Role classifier computes roles deterministically at scoring time
> (compatibility mode). Native enrichment-emitted roles come in the next
> rebuild. Release gate eventually requires native roles after rebuild."

Verification: the 7 tests pass; running the classifier twice on the same product
yields identical roles (determinism); no score/verdict changes vs pre-Phase-2
(classification is observational only this phase).
