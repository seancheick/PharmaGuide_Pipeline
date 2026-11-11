# ADR-0007 close-out batch receipts (2026-11-10)

Agent review by Claude; independent agent checks recorded below. Not clinician review.
Scope: the remaining topic cohorts from `~/pg_quality/evidence-v1-closeout-20261110/ZERO_AUDIT.md`
(eye, cognitive, men's, botanicals) plus the six scoring-eligible contexts that lacked `age_group`.

## 1. Cohort finding: nine of eleven zeros are already finished, signed decisions

Live probe (`evidence_resolver.resolve_evidence_for_canonical`) on the merged branch:

| Ingredient | Record | Disposition | Signed basis |
|---|---|---|---|
| Lutein | INGR_LUTEIN | `reference_only_clinical_record`, finished | A084 rejects both source transfers |
| Phosphatidylserine | INGR_PHOSPHATIDYLSERINE | finished | exact-form context, Dr. Pham 2026-10-26 |
| Huperzine A | PRECLIN_HUPERZINE_A | finished | two exact-form contexts, 2026-10-28 |
| GABA | INGR_GABA | finished | A068: reject high-certainty stress/sleep language |
| Saw palmetto | INGR_SAW_PALMETTO | finished | A109: no Permixon transfer; CAMUS null |
| Curcumin | PRECLIN_CURCUMIN_GENERIC | finished | A130: reject broad/generic benefit language |
| Panax ginseng | INGR_GINSENG | finished | A071 contexts |
| Echinacea | INGR_ECHINACEA | finished | Sean-confirmed 2026-10-28 ruling: no general credit |
| Red yeast rice | INGR_RED_YEAST_RICE | finished | A106: no blanket transfer to retail products |
| **Turmeric** | literature `turmeric` | **held** `literature_applicability_unestablished` | — |
| **Ginkgo** | literature `ginkgo` | **held** `literature_applicability_unestablished` | — |

The audit's "missing credit" class was wrong for the nine; no credit is owed under their signed
decisions. Turmeric and ginkgo (and collagen, same mechanism) were real holds.

## 2. Unnamed preparation on a no-credit literature review (code + 3 records)

The 2026-11-03 literature reviews of turmeric, ginkgo and collagen each conclude "this review earns
no Evidence credit" for every declared preparation, yet a row naming no preparation stayed open.
ADR-0007 rule 3 lets such a row finish at the record's own ingredient-level conclusion when the
record attests it. Change: `evidence_resolver` reads `documented_review_scope.preparation_uncertainty_reviewed`
(same field and readiness consumer as the backed path; no new status). It applies only when the
scope check returns `clinical_source_label_unresolved`, the flag is the boolean `true`, and no backed
clinical source for the ingredient is unresolved (a held source is a fact, not a zero: regression
`test_repeated_preparation_cannot_restore_a_held_source`). Broccoli is not attested: its only study
(sprout beverage) is positive.

Signed context: A115 (turmeric) rejects broad preparation-wide approval and keeps formulation review
open; the 2026-10-28 closure list assigns the remaining turmeric work to agent source extraction.
Finishing an unnamed preparation at no credit grants nothing, so it stays within A115.

Independent agent check (fresh context, 2026-11-10): attest all three, no blockers.
- NCCIH turmeric: not enough known to conclude benefit; osteoarthritis evidence initial, needs better studies.
- NCCIH ginkgo: not shown effective for any condition; dementia findings inconsistent.
- Collagen PMID 40324552 (23 RCTs): no skin effect in non-pharma-funded or high-quality studies.
- Branded records with points (BRAND_UCII, BRAND_EGB761, BRAND_BCM95, BRAND_LONGVIDA, BRAND_TAMAFLEX)
  need their brand token on the label, so a bare name cannot reach them.
- Wording fixes applied: "naming no preparation"; NCCIH phrasing; collagen "outside this review's studies".

## 3. age_group on six scoring-eligible contexts (PubMed efetch / PMC full text, 2026-11-10)

| Context | Source population | age_group |
|---|---|---|
| ingr_hyaluronic_acid_34203487 | 40 healthy Asian men and women aged 35-64 | adult |
| nac_oral_exercise_soreness_subset_39632267 | PMC11617117 Table: included-trial mean ages ~20-30 (rugby players 20.4) | adult |
| passionflower_short_term_anxiety_review_33352740 | participants no less than 18 years old | adult |
| honey_child_nocturnal_cough_22869830 | 300 children aged 1 to 5 years | child |
| creatine_monohydrate_..._39074168 | adults younger than 50 years | adult |
| alpha_gpc_alzheimer_monotherapy_subset_36683513 | adult-onset neurological disorders; subset = Moreno 2003, N=261 (PMC10041421 Table 1) | adult |

Effect: adult contexts become an explicit population conflict on children's products (was an
unresolved hold); the honey child study stops crediting adult products and applies to children's.

## 4. Text reconciliation with signed decisions (no Evidence movement)

PRECLIN_CURCUMIN_GENERIC (A130) and INGR_TURMERIC (A115): `positive_strong` with "no automated
downgrade signals" / "not reassessed" rationales contradicted the signed rulings. Now `mixed`
(retained PMID 40615851: CRP and TNF-alpha lower; ESR, IL-1 beta, IL-6, PGE2 not significant),
unverified enrollment/registry aggregates set to null, generic curcumin's rejected healthy-aging chips
removed and `primary_outcome` omitted (the vocab contract allows an absent key; an empty string needs
a record-level hold, which would turn curcumin's finished zero into a hold).

## Not changed

Red yeast rice, GABA, ginseng, echinacea, lutein, phosphatidylserine, huperzine A, saw palmetto:
text consistent enough with their signed decisions; reference-only text is not exported.
