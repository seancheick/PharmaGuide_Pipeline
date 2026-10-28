# Condition-specific clinical evidence: approval request for Dr Pham (October 28, 2026)

Status: **awaiting Dr Pham's signature, relayed by Sean.** No production code has changed.
Prepared by an agent (Claude) from the code at `origin/main` `e6885790d` and the closure-batch
records in `claude/held-source-closure` (not yet merged).

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
  (`fasting_glucose` vs `type_2_diabetes`), INGR_POTASSIUM and INGR_MAGNESIUM_GENERIC
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
