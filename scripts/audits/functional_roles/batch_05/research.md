# Batch 5 — `botanical_ingredients.json` (all 459 entries)

**Date:** 2026-04-30 | **Vocab:** v1.0.0 LOCKED

## Disposition: all 459 entries → `functional_roles=[]`

### Rationale (clinician + V1 architectural decision)

`botanical_ingredients.json` is the **active-side** ingredient identification reference. Categories in this file (`root`, `herb`, `fruit`, `leaf`, `seed`, `bark`, `mushroom`, `vegetable`, `flower`, `grain`, `botanical`, `spice`, `seaweed`, `grass`, `resin`, `berry`, `essential oil`, `algae`, `legume`, `oil`) are plant-part descriptors, not functional roles in the FDA 21 CFR 170.3(o) sense.

Per clinician handoff: "Most botanicals are actives (no role assigned), but some serve as colorants (turmeric), flavorings, or carriers in formulation context."

Per clinician 4F: "Cinnamon (Natural Flavoring) → flavor_natural at flavoring doses (mg-scale). Higher clinical doses (500–1000+ mg) → active." This is a per-product context decision, not an entry-level one.

### V1 architectural decision

The `inactive_ingredients[]` blob row in the Flutter export **does not** pull from `botanical_ingredients.json` (`build_final_db.py:2294-2331` reads `harmful_ref` and `other_ref` only). So a botanical's `functional_roles[]` field, if populated, would never reach the Flutter UI in V1.

Setting `functional_roles=[]` on all 459 botanical entries:
- Maintains schema consistency across all 3 reference files
- Passes the integrity gate (empty is a valid V1 state)
- Documents intent: V1 botanicals are actives, full stop
- Defers per-product formulation-context disambiguation (turmeric as colorant in a multivitamin) to `other_ingredients.json` if/when the same canonical ingredient also appears there
- V1.1 attribute layer (per CLINICIAN_REVIEW.md Section 6) can revisit if dual-purpose botanical filtering becomes a UX requirement

## Coverage summary

After batch 5, Phase 3 backfill is complete across all 3 reference files:

| File | Total | Populated | Empty `[]` | Coverage |
|---|---|---|---|---|
| harmful_additives.json | 115 | 102 | 13 | 89% |
| other_ingredients.json | 673 | 466 | 207 | 69% |
| **botanical_ingredients.json** | **459** | **0** | **459** | **N/A (architectural)** |
| **TOTAL excipient-relevant** | **788** | **568** | **220** | **72% of excipient-relevant entries** |

The 459 botanical entries are intentionally `[]` and shouldn't be counted in the "needs backfill" denominator — they're an architectural exclusion, like contaminants in `harmful_additives`.

## Phase 3 milestone

**Phase 3 backfill complete.** All entries across all 3 reference files have `functional_roles[]` populated per clinician-locked decisions. Next:

- **Phase 4** (cleanup, post-backfill): physically retire descriptor entries, drop `additive_type` field, relocate move-to-actives entries (~117 from other_ingredients) to the active-ingredient pipeline, canonicalize `category` values
- **Phase 5** (final coverage gate): `coverage_gate.py` enforcement of 100% on populate-required entries before release. Architectural exclusions (contaminants, botanicals-as-actives, retired descriptors, V1.1-deferred) are explicitly allowlisted in the gate.
