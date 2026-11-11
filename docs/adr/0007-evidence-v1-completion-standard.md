# ADR-0007 — Evidence V1: a finite, ingredient-first completion standard

**Status:** ACCEPTED (Sean, 2026-11-10)
**Date:** 2026-11-10
**Owners:** `scripts/evidence_resolver.py::resolve_product_evidence` / `_resolve_evidence_for_row`;
`scripts/clinical_applicability.py::assess_clinical_applicability`;
`scripts/scoring_v4/modules/generic_evidence.py::score_evidence` with
`scoring_v4/config/quality_score.json::evidence_magnitudes`;
`scripts/assessment_readiness.py::evaluate_release_assessment`. Data:
`scripts/data/backed_clinical_studies.json`, `scripts/data/literature_evidence_records.json`.

## Decision

1. **Evidence is about the ingredient, never the label's marketing.** A claim on the label neither
   adds nor removes Evidence points (`require_claim_alignment=False`, already in force).

2. **Completion rule.** Evidence is complete when each recognized, material ingredient has a
   documented, source-supported research conclusion under this standard. The conclusion may support
   points, justify limited or zero points, or state that particular research does not transfer to
   this product. It does not require an exhaustive search, and it never assumes an unknown
   formulation matches a studied one.

3. **Four conclusions, existing magnitudes.** No new scale, multiplier, engine or status.

   | Conclusion shown to the user | Points |
   |---|---|
   | Established nutritional role | existing authority floor |
   | Human research supports a benefit | existing grade (`positive_strong` / `positive_weak`) |
   | Limited or mixed research | existing reduced grade, may be 0 |
   | No qualifying support found in our review | 0 |

4. **Label row decision, in order.**
   1. Identity unknown → held.
   2. Label matches a studied preparation → existing full grade.
   3. Identity confirmed, preparation not confirmed → the record's own ingredient-level conclusion
      (`identity_scope: ingredient_general` contexts plus
      `applicability.preparation_uncertainty_reviewed: true`). A branded-trial grade is never
      downgraded onto other preparations automatically. Without a source-supported general
      conclusion the row shows the research and "applicability to this product not established",
      with no points.
   4. Preparation named not equivalent, or reviewed with no benefit → 0, with the reason shown.

5. **Finished judgment versus unresolved fact.** A reviewed limited or no-credit conclusion finishes
   Evidence. An unidentified ingredient, a safety-relevant missing amount, or an unfinished
   branded, exact-form or literature-source review does not, and none may be closed by a zero.

6. **One-pass review standard.** Per ingredient, once: identity by chemistry or botanical ID;
   authoritative sources, normally NIH ODS or NCCIH, then Cochrane or the latest systematic review,
   then EFSA or a clinical guideline; every identifier content-verified; the conclusion, studied
   uses in plain words, limits and sources recorded; an independent second check; attribution as
   agent review. Three sources is the normal starting point, not a ceiling: one fact sheet can be
   enough, and positive credit on a disputed claim gets a closer source read. Not required: full
   Methods for a no-credit conclusion, registry reconciliation, meta-analysis reconstruction, or
   every published paper.

7. **Reopen triggers.** A finished ingredient or product reopens only for a safety signal, a
   retraction or confirmed source correction, or a new guideline or high-quality review likely to
   change the conclusion. A newly found citation alone does not reopen it; it joins the scheduled
   maintenance cycle.

8. **Label-claim note.** Where the label's claim category is not among the ingredient's studied
   uses, the Evidence section shows one calm informational line. No points move. A Transparency
   penalty for misleading claims is deferred until after beta and needs measurement and Sean's
   value.

9. **Success measures.** Every product has an explicit disposition (scored-complete,
   intentionally non-scoreable, or held by a named source, identity, Dose or safety limitation).
   Scoreable coverage is measured after integration; the existing 99% gate stays until Sean
   approves a replacement, and is never met by changing the denominator.

## Context

The November 5 census of 15,447 products held 7,047 partial, 6,482 by Evidence review alone,
across 502 ingredients; 2,643 of 8,400 finished products scored Evidence 0, largely from
exact-preparation mismatches and reference-only records. Paper-by-paper review at a few ingredients
per batch could not close this, and would not scale to new catalog growth. PR #433 (ashwagandha)
is the first case implemented under this rule.

## Consequences

- Six pillars, the 20-point Evidence scale, Dose, Safety, interaction rules, signed clinical
  decisions and the glutamine numerical HOLD are unchanged.
- Literature questions that do not change a scoring decision go to a maintenance backlog, not a
  release blocker.
- The model is frozen for beta once the integrated census, real-product comparisons and the app
  scan checks pass.

## Rejected

- Awarding points to every ingredient to avoid zeros (fabricated credit).
- Treating unknown preparation or unread literature as a completed zero across the catalog.
- A separate Evidence engine, discovery screen or goal-based score for V1.
