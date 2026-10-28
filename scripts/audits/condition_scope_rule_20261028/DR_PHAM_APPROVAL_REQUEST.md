# Condition-specific clinical evidence: approval request for Dr Pham (October 28, 2026)

Status: **Approved within the signed scope relayed by Sean on October 28.** The rulings and
attestation below govern the implementation. The original proposal described `e6885790d` and
`a78f78bf9`; those are historical baselines, not the current integration state.

Sean's subsequent October 28 clarification, carried into the Codex takeover: no probiotic marketing
claim bonus; the same eligible research earns identical credit with an aligned claim or no claim.
An unrelated attributable claim, wrong population/preparation, held source or unqualified outcome
cannot earn affirmative benefit credit. Formula-level positioning is attributed through the existing
row/identity owner. Evidence strength follows the contexts that actually qualify (ginger uses its
eligible direct trial, not a stronger inapplicable sibling synthesis). Preserve actual legacy approvals
and independently established nutrition authority; a missing approval is never an invented negative.

Omega's existing signed nutritional decision is separate: see
`held_source_closure_20261028/DR_PHAM_RULINGS_20261028.md`, fifth ruling table, INGR_OMEGA3.
It withdraws routine retail heart-event credit while preserving disclosed EPA/DHA nutritional
contribution through the shared owner across routes. No new numerical magnitude is authorized here.

## The governing rule (Sean, October 28)

1. A label claim is not required for valid scientific credit.
2. Credit stays condition-specific. The app shows what was studied ("studied in adults with chronic
   heart failure"), never a benefit the study did not test.
3. An unrelated claim never inherits the credit. For example, an "energy" claim backed only by a
   heart-failure study gets nothing from that study.
4. The shopper is never assumed to have the studied condition.

The one shared owner gives every matched record one of four states:

| State | Label | Result |
|---|---|---|
| (a) | no claim for the ingredient | scoped credit |
| (b) | claim aligned with the studied outcome | scoped credit, the same points as (a): no bonus for claiming |
| (c) | only an unrelated claim | no credit from that record |
| (d) | the label's population explicitly conflicts with the studied population | not applicable |

## Why it needs a ruling: today's code does two different things

- **Gated records require an exact disease claim.** The gate (`clinical_applicability.py:603-630`)
  turns on only when a policy's `supported_outcomes` string exactly equals a context `condition`.
  US supplements cannot make disease claims, so these records credit almost no products:
  INGR_CRANBERRY, INGR_GINGER, INGR_INOSITOL, INGR_RHODIOLA, INGR_SELENIUM, INGR_VITAMIN_C and
  PRECLIN_QUERCETIN_PHYTOSOME.
- **Ungated records credit any matching preparation.** Only "not for children" is checked here:
  INGR_COQ10 (`heart_failure_adjunct` vs `chronic_heart_failure_adjunct`), INGR_BERBERINE_HCL
  (`fasting_glucose` vs `type_2_diabetes`), PRECLIN_BERBERINE_GENERIC (`fasting_glucose` vs
  `type_2_diabetes_glycemia`), INGR_POTASSIUM and INGR_MAGNESIUM_GENERIC
  (`cardiovascular` vs `blood_pressure`) and INGR_GARLIC (`cardiovascular` vs `hypertension`).
  Whether a record is gated depends on an accident of string spelling, not on clinical judgment.
- **Probiotic and branded strain contexts** (`probiotic_evidence.py:398`) also require an affirmative
  claim for treatment and challenge contexts, plus label positioning that matches the context.
- **The purpose matcher cannot see some aligned claims** (probe on `e6885790d`). "Supports heart
  health", "healthy blood pressure", "thyroid function" and "athletic performance and endurance"
  map to no category, and neither do the CoQ10, garlic, selenium and rhodiola outcomes. So an
  aligned claim can never match them. "PCOS menstrual cycle regularity" is categorized as
  *digestive* (from the word "regularity"), so a "digestive regularity" claim would wrongly align
  with the inositol PCOS evidence.

## Decisions requested (agent recommendation first)

**D1. One behavior for every consumer.** The four states apply to the generic, branded, sports and
probiotic/native-strain paths alike, and to `physiology`/`prevention` contexts as well as
`treatment`/`challenge`.
*Recommend: approve.* Consequence: probiotic strains studied for a condition (for example
antibiotic-associated diarrhea) earn scoped credit on labels without a matching claim. Today they
earn none. The movement will be measured before merge.

**D2. Population rule.** Pick one:
- **D2-A (recommended).** Two parts.
  - A context studied *only* in a special population (infants or children, pregnancy or lactation)
    applies only when the label names that population. A general product is not for that user,
    and assuming otherwise assumes the shopper's state. This is the existing probiotic rule
    (`_native_context_population_applies`), extended to every consumer.
  - Any other population restriction (adults, women, men, nonpregnant) fails only on an explicit
    label conflict: a children's label vs adult studies, a men-only label vs women-only studies,
    a pregnancy label vs nonpregnant studies.
- **D2-B.** Explicit conflict only, for every population. A general ginger product would then earn
  pregnancy-nausea credit, and a general probiotic would earn infant-colic credit.

Either way, a record with several approved contexts applies when at least one context passes
(ginger: the adult chemotherapy-nausea context still applies to a general adult label).

**D3. What counts as "unrelated".** The label's claim for that ingredient falls in no indication
category that the record's reviewed outcomes fall in, or it matches the record's reviewed
`excluded_claim_terms` (for example CoQ10: energy, statin, muscle pain, stamina).
- A label with one aligned claim and one unrelated claim gets the scoped credit. The unrelated
  claim gains nothing.

*Recommend: approve.*

**D4. Vocabulary additions** to the shared categorizer `evidence_resolver.INDICATION_KEYWORDS`.
These also feed the probiotic relevance and the evidence-calibration replication gate.
- `cardiovascular`: heart, cardiovascular, cardiac, hypertension, "blood pressure".
- `exercise_performance`: endurance, exercise, athletic, athletes, workout.
- `thyroid`: thyroid, hashimoto, thyroiditis.
- `women`: add menstrual, pcos.
- Fix: "cycle regularity" or "menstrual regularity" is not digestive.
- `digestive`: add nausea.

*Recommend: approve these lists exactly.* Anything not listed stays unmatched, which gives state (c)
for a categorized claim and state (a) for no claim. CoQ10's own exclusion of "stamina" still wins
over the new exercise category.

**D5. Fail-closed guards stay.** A signed condition context that lost its approval or its source
binding stays unresolved and cannot fall back to the old unscoped path. A reference-only record
stays not applicable.
*Recommend: approve (no change).*

## What happens after the signature

The order is fixed:
1. `claude/held-source-closure` merges.
2. Fail-first tests for states (a)-(d) and D2, through `build_scored_artifact`.
3. One owner change in `clinical_applicability.py` and `evidence_resolver.py`. The probiotic
   consumer reads the same decision. No new field, status or registry.
4. Replay on a frozen cohort: the original twenty, the gated and ungated records above,
   probiotic controls, and unaffected controls. Movement is reported by cause.

No merge to main without Sean.

## Signature

Dr Pham: approve D1 / D2-A or D2-B / D3 / D4 / D5, or amend: ________ (relayed by Sean, date ____)

## Rulings received (October 28, 2026)

Received from Sean in chat as "Claim and Population Applicability: Final Rulings". **Attestation:**
Sean confirmed on October 28, 2026, relayed by the closure session, that these rulings carry Dr
Pham's approval. His words: "she already answered and sent her message to that agent". They
authorize implementing and measuring the change. Merging waits for PR #273 and Sean's go-ahead.

- **D1: approved.** One shared clinical decision across generic, branded, sports, probiotic and
  native-strain paths, covering prevention, physiology, treatment and challenge contexts. No claim
  is required, the shopper is never assumed to have the condition, and category-specific formulas,
  exact-material requirements and holds are preserved. No new scorer or registry.
- **D2: option A, refined.** Infant, pediatric, pregnancy and lactation research earns credit only
  when the product is explicitly intended for that population. Targeting must come from affirmative
  label or use information, never from a precaution. Other populations fail on an explicit conflict,
  and the explanation keeps the exact studied population. One applicable context cannot lend its
  approval, population or outcome to another. Population and claim checks are independent: having
  no claim never bypasses a population restriction. Women with PCOS and pregnant women are not
  interchangeable, so a pregnancy-targeted product must not inherit a nonpregnant PCOS result.
- **D3: approved, with stricter claim interpretation.**
  - No claim: scoped credit. Aligned claim: the same credit.
  - Only an unrelated claim: no credit through that study.
  - Mixed claims: the supported outcome can count, but the unrelated claim gains nothing.
  - Signed product-level exclusions keep their exact meaning.
  - "Heart health" is not heart-failure proof, and a heart-failure study is not general
    cardiovascular protection.
  - A recognized claim that cannot be classified is not "no claim": keep its provenance and
    resolve it conservatively.
- **D4: rejected as written.** Use phrase-aware recognition. The categorizer tokenizes single words,
  so a literal "blood pressure" entry would never match. Fix the menstrual/bowel "regularity"
  collision, and keep PCOS, nausea and exercise outcomes separate from broad categories. A
  category can help find research and present it, but can never authorize Evidence points.
- **D5: approved.** No fall-through to legacy credit for a missing approval or source binding, a
  rejected context, reference-only research, the wrong preparation, an excluded combination or an
  incompatible population.

Implementation requirements from the ruling:
- Keep scientific eligibility, claim alignment (absent / aligned / unrelated / mixed / ambiguous)
  and population applicability (eligible / explicit conflict / special targeting absent /
  unresolved) as separate parts of one result.
- The role parser (`scoring_input_contract._role_function_claim_source`) cannot prove a claim is
  absent. Reuse the existing affirmative label-positioning source.
- Preserve `_excluded_claim_matches`.
- Report before/after separately for claim-free, explicit-claim and population-targeted products.


## Sean/team material-standardization ruling — October 28, 2026

This is Sean's explicit product-policy ruling, not an additional clinician attestation:
“Formulation depends verified material identity + standardization, NEVER approved clinical benefit.”
Clinical study eligibility does not establish, invalidate or substitute for a material specification.
An exact standardized material retains that Formulation trait when clinical benefit is held, null or
retracted, unless its material proof is independently invalid. A studied but unstandardized material
receives no automatic marker credit. Physical preparation identity/selection is distinct from marker
standardization and continues through the existing IQM/input-contract owner for Dose-related callers.

Testofen was independently checked against retained official DSLD raw304641: 600mg per two capsules,
Gencor trademark, seed extract. ANVISA Parecer7/2022 process25351.711676/2019-91, first page, records
supplier specification NLT50%saponins and identifies Fenusides as a proprietary glycoside matrix,
not a single chemical. Mirror content retrieved2026-10-28; official ANVISA URL returned403. PDF SHA256:
56bce88e2b0dda1ee5ed450350f88a34159babfdde03755dd3e90a5e99eeecc5.
https://anexosportal.datalegis.net/arquivos/1876554.pdf

The existing standardized_botanicals registry now owns that exact specification; IQMfenugreek::testofen
retains its existing identity/bio_score. No specification percentage is inserted into label-derived
percentage_found, no Verification/batch certificate is inferred, and no clinical hold is activated.
No new magnitude, registry, public field/status or scorer is introduced. Final bounded replay must
confirm the repair changes Formulation traits only, not Dose/Evidence/Verification/safety decisions.
