# Evidence 0 on 1,061 scored products: root causes (2026-09-29)

Corpus: fresh pipeline run at 5b4b4f08 (15,421 products, 15,070 scored). Scope: scored products
whose Evidence pillar is 0 with state `clinical_review_not_covered` (336), `no_assessable_actives`
(715) or `identity_material_unresolved` (10). Sean rejected re-weighting the total around the gap
("that's hiding it"); this audit finds why Evidence is 0.

Method, reproducible: for each product, `evidence_resolver.resolve_product_evidence(product,
owner_scoped=True)` on the enriched record; one reason code per Evidence-owning row; the product
is filed under the first matching cause below. Scratch data: `~/pg_quality/ev0*.pkl`.

## Root causes

| # | Cause | Products | Blend/projection-only | Kind |
|---|---|---:|---:|---|
| A | The resolver finds reviewed evidence (DIM, fish oil, boron, choline, CLA, lecithin), but `generic_evidence` scores only `evidence_data.clinical_matches`, and the enricher never matched these rows | 59 | 41 | wiring defect |
| B | A safety-listed active (DHEA, yohimbe, cascara sagrada): the resolver returns `banned_or_recalled_ingredient` -> not efficacy relevant, shown as "no assessable actives"; Safety already charges it | 86 | 3 | policy + wording |
| C | The product's own active is read as an excipient (`excipient_not_therapeutic_active`): gelatin 1300 mg, MCT/coconut oil, silica gel | 138 | 0 | role defect |
| D | An inactive-database identity owns Evidence (`nha_stevia`, `nha_raspberry_natural`, `oi_beetroot_powder`, `pii_extra_virgin_coconut_oil`, `pii_test1700_marketing_descriptor`) | 186 | 128 | owner-selection defect |
| E | "Requires literature search": 180 distinct blend or marketing names minted as identities (`superfood_greens_herbal_blends`, `perfect_green_juice_blend`, `proprietary_fiber_blend`, `dark_green_layer_going_to_sleep`, `header`), plus 34 real ingredients with no record (essential amino acids 17, pancreatin 13, matcha 11, triphala 10, beet 7, aloe, green coffee, meratrim ...) | 283 | 100 | identity defect + library gap |
| F | Whole-food powders (spinach, barley grass, kale) and undosed blend members | 300 | 208 | mostly a real limit; state wording |
| G/H | Reviewed: no qualifying human studies, below studied dose, wrong form | 8 | 8 | honest 0 |

489 of the 1,061 have no scorable rows at all: every identity that owns their Evidence is a
label-level projection (blend total or anchor), which the enricher's clinical matcher
(`_collect_evidence_data` over `_primary_active_ingredients_for_enrichment`) never visits.

## Why earlier fixes did not remove it

"Which ingredients are this product's evidence subjects" has two owners that disagree:
the enricher matches clinical records over its primary actives; the scoring contract
(`get_scoring_ingredients`, product-level projections) decides the owners and scores only the
enricher's matches. RR-11 fixed the display; brand, alias and dose fixes fixed individual
records. None aligned the two row sets, and the owner selection admits inactive, excipient and
blend-name identities.

## Direction (each at its existing owner; measured before adoption)

1. The enricher's clinical matching covers every row the scoring contract can make an Evidence
   owner, including label-level projections (fixes A, the Sytrinol/Tesnor/Pycnogenol brand
   totals, the fiber/enzyme/caffeine blend owners in E/F).
2. `evidence_owner_canonicals` / `classify_ingredient_roles`: an inactive-database identity or a
   blend/marketing name is never an Evidence owner; the product's real actives own it (D, E-blend).
3. Excipient exclusion does not apply to an active-section row that is the product's purpose
   (C).
4. Safety-listed actives: Sean's call. Safety already charges the hazard (pillar 0 + CAUTION);
   Evidence either reports the literature or a distinct "not assessed: safety-listed" state,
   never "no assessable actives" (B).
5. Evidence records for the 34 real ingredients, one verified `/data-fix` batch at a time
   (essential amino acids, digestive enzymes/pancreatin, matcha/green tea, triphala, beet
   nitrate, aloe, green coffee ...) (E-real).
6. Whole-food and undosed members keep 0 with the applicability wording, not "not yet reviewed" (F).

## Rubric reference (verified against code and config at 5b4b4f08)

Public pillar = clamp(0, 20, raw / reference x 20) (`quality_score._pillar_formulation`,
`_pillar_evidence`). No evidence state forces 0; states only change wording, display_state and
`quality_assessment_status`.

| Route / profile | Formulation raw max -> reference | Evidence raw max -> reference |
|---|---|---|
| Generic (IQM) | A1 form 15 + delivery 3 + enhancer pairing 3 + standardized botanical 1 = 22 (cap 30) -> 15; unrated-form neutral 12/20 | per-entry base (meta 6, multi-RCT 5, single RCT 4, observational/animal 2, in vitro 1) x level (product 1.0, branded 0.9, ingredient 0.9, strain 0.65, preclinical 0.3) x effect (strong 1.0, weak 0.85, mixed 0.6, null 0) x enrollment 0.6-1.2; cap 7 per ingredient; top-N weights 1/.7/.5/.3; depth +0.25/+0.5; primary floors 18/14 or 17/11; nutrition-authority floor 10; max 18 -> 18 |
| Generic botanical | identity 6, plant part 2, dose 2, extract 2, standardization 1-4, branded 3 (cap 15) + delivery + pairing -> 15 | generic -> 18 |
| Generic collagen | collagen 6, hydrolyzed 2, type 2, source 3, dose 2, brand 3 (cap 15) -> 15 | generic + collagen peptide recovery -> 18 |
| Immune support | generic - herb-stack 3 -> 15 | generic, capped 17 -> 17 |
| Joint support | generic -> 15 | generic, capped 14 -> 18 (max ~15.6/20) |
| Sports protein | source 3-15, dose disclosure 5, amino profile 3, focus 4, clean use 2 = 29 -> 29 | generic -> 18 |
| Sports other | generic fallback -> 15 | generic -> 18 |
| Fiber | source 3-12, disclosure 6, focus 5, clean use 5, practicality 2 = 30 -> 28 | generic -> 18 |
| Omega | form tier 8 + EPA+DHA concentration 4 = 12 -> 12 | EPA+DHA/day: < 376 mg 0; 376-999 10.4; 1-2 g graduated; >= 2 g 20; prenatal DHA >= 200 mg 11.1 -> 20 (state borrowed from a generic audit call) |
| Probiotic | total CFU 4 + strain identity 8 + delivery 3 = 15 -> 15 | strain clinical 12 (strong 12, moderate 9, weak 4.5) + dose applicability 8 -> 20 |
| Multi / prenatal | panel form quality 12 (floor 9/15) + disclosure 2 = 14 -> 14 | authority panel coverage (covered / required x 20) -> 20 |
| B-complex | core panel 10 + form 8 + focus 3 + disclosure 2 = 23 -> 23 | 8-vitamin authority panel -> 20 |

Also found: the generic archetype formulation references (24/30/25) are unused because the
profile reference (15) always wins; several component magnitudes are hard-coded outside
`quality_score.json` (botanical, collagen, fiber, sports protein, b-complex, study-type base
points and level multipliers).

## Decisions (Sean, 2026-09-29)

- "One brain, one system, one shared provider, one owner."
- "Dose is dose, evidence is evidence": Evidence never zeroes or cuts a study for the label's
  dose; the Dose pillar owns dose adequacy. Evidence never re-charges a safety listing; Safety
  and the verdict own the hazard.
- Re-weighting the total around a gap was rejected as hiding the defect.
- Reviewers (Claude, Grok, pasted 2026-09-29) concur: one owner set; only purpose actives own
  Evidence; pillars orthogonal; one penalty for a safety-listed active ("not assessed:
  safety-listed", never "no assessable actives"); partial credit by evidence tier (product RCT >
  branded > generic ingredient > authority > preclinical), never by dose; undisclosed blend
  members keep their ingredient's evidence while Dose and Transparency charge the blend. Open:
  what a remaining true library gap shows ("insufficient data") once lanes 1-4 land.

## Further findings (same day)

- The evidence expansion is in `literature_evidence_records.json` (754 PubMed-verified reviews:
  14 positive_strong, 73 positive_moderate, 50 positive_weak, 14 mixed), a shadow registry: the
  resolver reads it for state only; points come solely from `backed_clinical_studies.json` (210).
- Dose gate inside Evidence: 256 scored products lose Evidence to a sub-clinical dose (152 to 0):
  MSM 92, L-carnitine 76, BCAA and its three amino acids 49, L-arginine 34, ashwagandha 6;
  their Dose pillar charges the same underdosing (BCAA Capsules 184308: Evidence 0, Dose 5.4).
- Blend anchors: `identity_bearing_blend_header_mass_from_nested_child` hands a blend's mass to its
  first child (BP Manager 212273: stevia over olive leaf and hawthorn); blend headers take
  `proprietary_blends` identities (`superfood_greens_herbal_blends`).
- Active rows resolve to inactive databases: "Beet" -> `oi_beetroot_powder` (colorant) instead of
  botanical beet (337241); "Raspberry" -> `nha_raspberry_natural` (flavor) on Raspberry Leaf 900 mg
  (251678).

## Plan: one evidence-subject owner

Each lane test-first on real labels, replayed on the 1,061 plus controls before the next; one
corpus run at the end, then the release checks.

1. **One provider of evidence subjects.** `scoring_input_contract` (scoring rows and
   `evidence_owner_canonicals`) already decides which rows own Evidence. The enricher's clinical
   matching (`_collect_evidence_data`) iterates that same provider, projections included, instead
   of its own list. Every owner row then has its matches (A; Sytrinol/Tesnor/Pycnogenol brand
   totals; enzyme, fiber, caffeine blends).
2. **Who may own Evidence.** Never an inactive-database identity, a flavor or sweetener, a
   proprietary-blend or marketing name; a blend's mass is not handed to an arbitrary first child;
   an active-section row that is the product's purpose is not an excipient (C, D, E-blend). Census
   the active rows that resolve to inactive databases and fix identity precedence at the cleaner
   (beet, raspberry leaf).
3. **Policy at the owner** (decided above). Probiotics too: on the 535 probiotic-route products
   median Evidence is 5.4/20 (191 at 0; 444 `research_present_applicability_unestablished`, 4
   `evaluated_applicable`): `probiotic_evidence` reserves 8 of 20 for an exact tested dose
   (`dose_applicability_credit` 1.0 only for EXACT_TESTED_DOSE) and gates strain credit on dose
   status, so the curated strain library rarely reaches the score. Move that dose judgment to Dose.
   Then drop the dose gate from Evidence (`generic_evidence`
   sub-clinical skip, resolver `dose_below_studied_clinical_range`), after confirming the Dose
   pillar carries the studied dose for MSM, L-carnitine, BCAA, L-arginine (overlaps the D24 Dose
   lane on `codex/dose-calibration`: coordinate); safety-listed actives assessed on their
   literature (B); undisclosed blend members and whole foods get their own capped lane and honest
   wording (F); "no studies found" and "studies show no effect" stay distinct.
4. **One evidence library.** Promote the verified positive/mixed literature reviews into
   `backed_clinical_studies.json` (the one owner) in topic batches, then records for the 34 real
   missing ingredients; retire the shadow registry's scoring role. Confidence shown beside thin
   evidence.
5. Cleanup: omega's own evidence state; hard-coded magnitudes into config; unused archetype
   references.
