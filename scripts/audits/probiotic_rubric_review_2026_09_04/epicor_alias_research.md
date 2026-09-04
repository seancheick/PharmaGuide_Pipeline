# EpiCor exact branded alias ownership

Verified 2026-09-04. Scope: move the single exact alias `epicor dried yeast fermentate` from `other_ingredients.NHA_YEAST_FERMENTATE_DRIED` to the existing `standardized_botanicals.epicor` preparation. This is an alias-ownership correction; generic fermentate names alone do not establish EpiCor identity.

## Primary identity evidence

- [Cargill, State-of-the-art prototyping](https://www.cargill.com/doc/1432208360027/state-of-the-art-prototypes.pdf), copyright 2022, PDF pages 8–9: the manufacturer uses the exact phrase “EpiCor Dried Yeast Fermentate” and identifies its fermentation organism as Saccharomyces cerevisiae. This directly supports the branded alias, not generic fermentate identity.
- [Cargill, EpiCor FAQs](https://www.cargill.com/supplements/epicor-faqs), accessed 2026-09-04: the identity and formulation answers describe EpiCor as a fermentation-derived, inanimate preparation. No efficacy, safety, dosing, or certification claims from this page are being imported.

The proposed EMEA product page timed out on two direct retrieval attempts. It is not relied on for this correction. The PDF text was retrieved successfully; the available screenshot tool could not render it.

## Executable root cause

On code `3ecf73d4`, the shared exact registry selects the generic NHA owner for the long branded label. The quality matcher first offers `yeast_fermentate`; label-first identity correctly refuses to treat that broad IQM match as the exact preparation. The typed 250/500 mg source projections remain material and counted, but have no form-quality fields. The standardized-preparation collector uses exact name/alias matches, so its EpiCor record does not match the long label under the old ownership.

The shipped 25492 artifact had instead acquired `brewers_yeast` / `brewer's yeast (unspecified)` quality credit. That organism-family credit must not be restored.

Controls 302655 and 7083 have exact `epicor` identities and existing branded-preparation recognition; neither has an EpiCor IQM bio-score. The loaded clinical database has no EpiCor/yeast-fermentate evidence entry. This correction leaves all quality values, marker fields, clinical records, and scoring code untouched and lets the existing EpiCor preparation policy consume its verified alias.

## Boundaries

- Keep the generic NHA entry and all its generic aliases; do not add a canonical equivalence or a generic-to-branded parent relationship.
- Keep bare `dried yeast fermentate` ambiguous and keep false branded/normalized/form-only labels rejected.
- Preserve literal source names, forms, doses, and row references, including inputs cleaned under the previous NHA ownership.
- Preserve both entry counts. Patch versions and touched-entry dates change. Recompute the directly affected standardized-registry alias total from actual alias arrays: 861 before, 862 after; the prior metadata value 982 was stale. Other historical aggregate statistics remain untouched.

## Verification

The updated exact-owner regression failed before the data correction: two long-label cases resolved to the NHA owner rather than `epicor`. The new aggregate assertion also failed on the stale alias count. After the correction, the six-file focused run passed **227 tests** through `scripts/test.sh fast`, including old cleaned-owner 250/500 mg cases, exact registry ownership, ambiguous generic names, false brands, microbial extracts, whole organisms, and scoring-input boundaries. `git diff --check` passed.

Isolated full clean-source re-enrichment compared the frozen `3ecf73d4` implementation with only the two data-file changes. Both runs completed all six targets with no errors and identical input hashes; the only production hash differences were `other_ingredients.json` and `standardized_botanicals.json`. The verified candidate data hashes match the working files.

- Baseline: `/tmp/pharmaguide_epicor_alias.v5F3Iq/baseline_six_canaries.json`
- Candidate: `/tmp/pharmaguide_epicor_alias.v5F3Iq/verified_six_canaries.json`

The corrected labels retain these candidate pillar outputs; all six pillars and total scores are numerically unchanged from the frozen baseline:

| Product | Formulation /20 | Dose /20 | Evidence /20 | Transparency /15 | Verification /15 | Safety/Hygiene /10 | Total /100 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 25491 — Daily Immune Defense | 12.7 | 6.4 | 12.0 | 15.0 | 6.0 | 9.0 | 61.1 |
| 25492 — Epicor 500 mg | 0.0 | 14.5 | 0.0 | 15.0 | 6.0 | 8.5 | 44.0 |

Both retain literal `EpiCor dried Yeast Fermentate` and the source's empty forms array. Their typed, material `label_active_projection` changes only the preparation canonical from `nha_yeast_fermentate_dried` to `epicor`:

- 25491: 250 mg, role `major`, source and linked row `ingredientRows[4]`; strict identity coverage remains 6 mapped / 0 unmapped, with 3 material dose assessments. Its separate source-eligibility diagnostic remains 3/3.
- 25492: 500 mg, role `claim_prominent`, source and linked row `ingredientRows[0]`; strict identity coverage remains 1 mapped / 0 unmapped, with 1 material dose assessment. Its separate source-eligibility diagnostic remains count 0 / coverage null in both runs; it must not be described as counting this row. The typed scoring denominator and material exposure do count it.

The existing standardized-preparation collector now recognizes the long alias. In 25492, existing A5b brand recognition changes 0 → 1, while A1 remains 0 and every other positive formulation component remains 0. The unchanged additive penalty is 1.5; net -0.5 clamps to Formulation 0, with no presence floor applied. In 25491, A5b was already capped at 1 from another preparation, so its formulation total does not change. No new form-quality assessment or clinical points were authored.

Controls 302655 and 7083 remain 47.0 and 72.6, respectively. Required unresolved conflicts 178352 and 264610 remain `not_scored`. Across all six targets, route, score/status/verdict, pillar values, clinical-match IDs, and complete probiotic-data objects are unchanged. Both corrected products remain non-probiotic; the EpiCor row remains `not_yet_evaluated` with no loaded clinical evidence IDs. Any further preparation-quality or evidence curation is a separate reviewed data/rubric task, not an alias fix.
