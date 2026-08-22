# Scoring Readiness Candidate — 2026-08-22

Status: **verified preproduction candidate; not published**

Follow-on to `scoring_integrity_candidate_2026_08_21.md`. That candidate was correct
engineering with one policy defect: the evidence-readiness gate quarantined a product for
naming an ingredient we had not curated, which is a gap in our curation rather than a defect
in the product. It reduced the app catalog from 13,271 to 6,637.

No Supabase upload, Flutter import or bundle mutation, push, cleanup, or production promotion
was performed. `scripts/dist/` was promoted locally only, through the gated candidate path.

## Release decision

| | baseline (2026-08-19) | prior candidate (08-21) | this candidate |
|---|---:|---:|---:|
| app catalog | 13,271 | 6,637 | **14,380** |
| quarantined | 14 | 8,775 | **1,032** |

The remaining 1,032 are data-integrity holds, not curation backlog:

- **929** unresolved material dose assessment
- **93** unresolved active identity
- **52** safety-suppressed (BLOCKED)
- **12** held for US safety-policy review (9 vinpocetine, 3 designer-steroid class)

Evidence backlog is unchanged and fully reported: **7,722 products / 17,636 material actives**
remain `not_yet_evaluated`, queued in the assessment-readiness shadow remediation queue.

## What changed

**Evidence readiness is measured, not gating.** `ENFORCED_READINESS_DIMENSIONS` is the single
place that decides which dimensions gate the live catalog; identity, dose, verification and
route still do, evidence does not. `is_live_ready` derives from it and the completeness gate
and source-of-truth audit both read the producer's declaration instead of repeating the list.
A product whose only gap is a shadow dimension is live-ready and still queued for remediation,
labelled `gates_catalog_eligibility: false` so the two states cannot be confused.

**Rows carry typed evidence applicability.** `protein`, `fiber`, `digestive_enzymes`,
`branched_chain_amino_acids`, `probiotic_cfu_total` and `epa_dha` name a product-level total,
not a substance; the owning module answers them and no per-ingredient clinical record exists or
could. Keyed on identity rather than on how the dose reached the row, because `protein` arrived
both as a `sports_primary_dose` and as a `blend_anchor_mass` projection and denoted the same
total either way.

**A digestive-enzyme panel must define the product.** The enzyme branch fired on any enzyme row,
above the fiber mass-share check, so it decided most `fiber_digestive` routes. Garden of Life
Vitamin Code RAW Vitamin C — one token enzyme in a raw-food base — was scored by the digestive
module. Routes now require the enzymes to be at least half of what the product discloses,
counting label rows and enzyme-activity projections together. `digestive_enzyme_context` routes
drop 72 → 16; `fiber_digestive` 402 → 350.

**Canonical allowlists may only name canonicals the vocabulary defines.** Five entries were
inert. Two were live defects: `DRI_ESSENTIAL_NUTRIENTS` carried only
`vitamin_b5_pantothenic_acid` so pantothenic acid never received nutrition authority, and
`supplement_taxonomy` did not recognise it as a B vitamin at all. A new gate reuses the
production resolvers so it cannot drift from what the enricher can emit.

**The coverage contract is pinned.** The unresolved-identity literals live once and are imported
by the producer; a canary reads the producer source and asserts every reason the contract
recognises is still emitted. `identity_reason_code` is now reported alongside `reason_code`.

**Dead code removed.** Five module-level symbols had no reference outside their own definition.

## Route diff

52 routes changed, all `fiber_digestive → generic`, each reviewed. Every one is a product that
is not a digestive-enzyme formula: the Vitamin Code RAW line, Perfect Food greens, Ora So Lean,
GNC Keto Protein and Re-Grow, Hair & Skin, Herbal Immune Balance Sinus. GlycemicPro
Transglucosidase also moves, correctly: it discloses zero scorable identities, so no content
evidence supports any route, and identity readiness holds it.

The vocabulary fixes produced no route change on this corpus.

## Verification

- Full corpus enrich + score: **37/37 datasets, 0 failures**
- `scripts/test.sh fast`: **11,815 passed**, 124 skipped
- `scripts/test.sh full`: **14,280 passed**, 178 skipped, 2 xfailed, **1 failed**
- `scripts/test.sh release`: **111 passed**, 1 skipped (with `SKIP_STALENESS_CHECK=1`; the only
  stale layer is `dist_vs_flutter`, which is the publish step deliberately not performed)
- Every strict source-of-truth gate passes: matrix, IQM form-evidence, cleaner, enrichment,
  clinical, identity integrity, RDA/UL reference parity, assessment readiness, snapshot
  contract, export contract, freshness
- Mapping: **84,492 / 84,492** score-eligible rows mapped, 0 products below full coverage,
  0 strict contract failures

The single full-suite failure is `test_red_yeast_rice_active_signals`, which asserts generic Red
Yeast Rice is not banned. The data has carried `is_banned: true` since before this branch — both
the 2026-08-19 build in this worktree and the shipped baseline have it — so it is a pre-existing
banned-rule policy question for the safety-rule audit, not a regression here.

## Open work before publication

1. **Operator decision on the dose gate.** It is precise per row (Athletic Pure Pack: 41 material
   actives, 1 unresolved) and unchanged from the prior candidate at 929 vs 930, but it is still
   all-or-nothing per product, so it correlates with formulation breadth: 2.3% of products with
   ≤3 material actives are held, against 56.0% of those with more than 30. Whether one unresolved
   row in 41 should hold a product is a policy call, not a defect.
2. **Red Yeast Rice banned-rule review**, per above.
3. **Sign off or retain quarantine** for the 12 US-policy holds.
4. **Evidence curation backlog**: 1,392 distinct canonicals block 7,722 products; the top 100
   unblock ~41%, the top 200 ~58%.
5. Then approve, import to Flutter, and publish as a separately authorised operation.
