# Current probiotic clinical 12-point decomposition

Status: verified production anatomy at `fe2972901`; no numerical policy approved.

## Production path

`probiotic_evidence.score_evidence` computes two clinical candidates and keeps
their maximum, capped at 12:

1. the shared generic clinical pipeline over accepted probiotic-owned matches;
2. the probiotic-native strain-context scorer.

The two paths do not add together. The separate 8-point
`dose_applicability` component is then added, producing the current 20-point
Evidence result.

## What the generic candidate already rewards

- study design (`systematic_review_meta`, multiple RCTs, single RCT, clinical
  strain, observational and preclinical bands);
- evidence scope/level (product, branded, ingredient or strain evidence);
- reviewed effect direction;
- enrollment for eligible human study types;
- per-ingredient caps and diminishing top-N aggregation;
- published-study depth bonus;
- marker-confidence scale when authored;
- identity and clinical-applicability filtering before points are calculated.

It also currently removes a match when the label amount is below the registered
minimum. That amount gate is the Phase 1 defect and must move to Dose.

## What the native candidate already rewards

- exact reviewed strain identity and accepted research ownership;
- support level: strong/high 12, moderate/medium 9, weak/low/limited 4.5;
- reviewed effect direction;
- mismatch/review status as an eligibility gate;
- exact studied-formula ownership where present.

The native scorer keeps only the strongest weighted record today
(`native_strain_evidence_weights = [1.0]`). It does not add independent
replication credit. The registry already carries `trial_family` specifically so
multiple publications from one cohort cannot be mistaken for independent
confirmation.

Native dose applicability currently affects the 8-point amount component and
which contexts are treated as fully applicable. Those amount decisions must
move to Dose without deleting the source facts.

## Already represented versus genuinely missing

| Evidence fact | Current treatment | Consequence for redesign |
|---|---|---|
| Study design/quality | Scored in the generic path; summarized by native support level | Do not award again in a new certainty component |
| Effect direction | Scored in both paths | Do not award again |
| Enrollment | Scored in the generic path | Do not add a second sample-size bonus |
| Exact strain/formula identity | Eligibility/ownership gate; evidence scope also affects generic points | Any new applicability scale must avoid rewarding identity twice |
| Preparation/population/outcome applicability | Mostly eligibility/context filtering | A graduated direct-versus-broad match may be a real missing dimension, but only after the gate result is reused |
| Label-purpose alignment | Computed as descriptive `claim_alignment`; it does not change points | Candidate missing dimension |
| Independent replication | Generic path partly rewards multiple-study type/top-N/depth; native path does not | Must use one shared `trial_family` result and suppress any duplicate generic depth reward |
| Trial amount/CFU | Current Evidence amount gate/component | Remove from Evidence; Dose owns it |

## Why 10/6/4 is not approved

The proposed labels were directionally sensible, but adding a new 10-point
certainty component and a 4-point replication component on top of the current
clinical calculation could score study quality, effect direction or research
depth twice. The current 12 must first be separated into reusable result facts.

## Candidates for measured comparison

### Candidate A: current-core plus missing applicability

- 0-12: current clinical result after all amount gates are removed;
- 0-8: one product-applicability result using the existing strain/formula,
  preparation, population, outcome and `claim_alignment` facts;
- no separate replication bonus, because the current generic core already
  contains multiple-study and depth signals.

This preserves the current clinical ranking most closely. The replay must test
whether eight applicability points are too influential.

### Candidate B: explicitly separated evidence facts

- 0-10: strongest applicable evidence-family certainty/effect result;
- 0-6: direct product applicability;
- 0-4: independent replication/consistency by distinct `trial_family`.

For Candidate B, the 10-point core must exclude top-N/depth/replication and the
4-point replication result must group a meta-analysis with its constituent
trials when they represent the same evidence family. Multiple papers, outcomes
or follow-ups from one cohort count once.

### Diagnostic only: normalized current core

Normalize the amount-free current 0-12 result to 0-20. This preserves ordering
and reveals the effect of the historical 12-point cap, but adds no new evidence
distinction. It is a comparator, not the default recommendation.

## Required replay

Run all candidates through the production probiotic Evidence seam on the same
542 frozen labels. Report component drivers, distribution, top and bottom
products, largest deltas, every production-rounded tier movement, safety/status
movement, exact-formula and single-strain canaries, unspecified blends,
combination-only records, null evidence, and any duplicated `trial_family`
credit. No candidate may land until the result is independently reviewed.
