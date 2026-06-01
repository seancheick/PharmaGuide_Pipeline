# V4 Phase 6 — Botanical Profile (design)

**Status:** shipped (feat(v4-botanical))
**Date:** 2026-06-01
**Plan:** `.planning/v4-finalization/PLAN.md` Step 6

## Problem

The generic module scored botanicals with vitamin/mineral assumptions: the A1/A2
bioavailability form logic and the RDA/UL dose proxy. Botanicals (herbs, extracts)
have no RDA/UL and their quality signals are different (plant part, extract vs whole
herb, marker standardization, branded clinically-studied extract). Result: botanicals
were structurally under- or mis-scored.

## Design

A Botanical Profile inside the generic module, routed by `is_botanical_product()`.

### Routing — `is_botanical_product(product)`
Returns True only when the product has a recognizable botanical **active**
(`_primary_botanical_active` — taxonomy category `botanical` or a known botanical
identity) **and that botanical is mass-dominant**: its comparable mass (mg) is
`>=` the heaviest non-botanical active. Missing masses count as 0, so pure-botanical
and anchor-only products still route.

- Anchored on the same `_primary_botanical_active` the adapters consume, so the
  router can never send a product the adapters can't score (avoids zeroing
  formulation+dose — the Quercetin regression).
- Mass-dominance gate (review P2#1): a mineral/vitamin-dominant product with a
  trace herb (Magnesium 400 mg + Ginger 50 mg, B-complex + eleuthero, krill +
  astaxanthin) stays on the generic path so the dominant nutrient keeps its RDA/UL
  dose adequacy and A1/A2 form logic. ~1232 mixed products route correctly this way.

### Formulation adapter — `score_botanical_formulation` (max 15, occupies A1 slot)
recognized identity +6, plant part disclosed +2, quantified dose +2, extract (not
whole-herb powder) +2, marker standardization declared +4, branded clinically-studied
extract +3, weak/unidentified −4 (clamped to 0). When active, the generic A2
premium-forms and A5b standardized-botanical credits are disabled (standardization is
now core formulation, no duplicate bonus). The formulation dimension still applies the
B-penalties (harmful additives etc.) and clamps to its DIMENSION_CAP.

### Dose adapter — `score_botanical_dose` (replaces RDA/UL proxy; never returns None)
Clinical therapeutic ranges from `scripts/data/rda_therapeutic_dosing.json`:

| Condition | Band | Score |
|-----------|------|-------|
| blend header / parent total | `blend_total_only` | 7 |
| anchor / `product_level_evidence` / `blend_anchor_mass` row | `blend_total_only` | 7 |
| no disclosed dose | `primary_no_dose` | 0 (not None) |
| no clinical reference for the herb | `disclosed_no_reference` | 10 |
| within studied range | `within_studied_range` | 21 |
| near range (0.8·lo–lo or hi–1.2·hi) | `near_studied_range` | 16 |
| below 0.8·lo | `below_studied_range` | 10 |
| well above range | `above_studied_range` | 12 |

- Anchor-only rows score as blend totals (review P2#3): a `product_level_evidence` /
  `blend_anchor_mass` mass is a blend/product total, not a verified per-ingredient
  dose, so it earns 7 — removing the `botanical_anchor_only_evidence` CAUTION ceiling
  (Step 6) no longer over-credits opaque blends.
- Megadose is not near-range (review P2#2): `above_studied_range` = 12 (< near 16).
  B7 can't fire for botanicals (no RDA/UL flags); true toxicity is caught by the
  Layer-1 safety gate, so this is credit fairness, not a safety control.

## Safety invariant
The botanical profile never overrides the Layer-1 safety gate (kava, comfrey,
yohimbe, ephedra, aristolochic acid). The gate runs before module scoring and
short-circuits BLOCKED/UNSAFE independently of botanical routing.

## Validation
- `scripts/tests/test_v4_botanical_profile.py` (14 tests): detector incl.
  mass-dominance, formulation caps/weak penalty, dose bands incl. megadose +
  anchor-only.
- Full v4 suite green (968 passed). Corpus-delta benchmark:
  `shipped_safety_downgrades=0`, NOT_SCORED=0, large-deltas (≥50)=0; SAFE→POOR
  improved 1286→1245 (mixed products rescued from the token-herb path).

## Deferred
- Raw-40 POOR floor still stamps POOR on calibrated-~50 botanicals (whole-herb
  powders) — Phase 9 recalibration.
- Title/claim-based primacy (beyond mass) is not used for routing; mass-dominance
  is the Phase-6 heuristic. Phase-2 role classifier could refine later.
