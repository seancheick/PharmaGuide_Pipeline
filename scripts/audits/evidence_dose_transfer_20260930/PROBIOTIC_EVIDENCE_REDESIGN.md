# Probiotic Evidence redesign candidate

Status: design for measured replay; not approved production policy.

## Decision from review

A permanent 12/20 Evidence ceiling is rejected as structurally unfair. Removing
the 8-point dose-applicability component must not leave an otherwise excellent
probiotic unable to reach the same 20-point Evidence ceiling as every other
category. Dose still moves to the existing probiotic Dose owner.

Automatic multiplication of the existing 12-point clinical result to 20 is
also rejected. The measured P2 arm changed hundreds of products without adding
new evidence facts.

## Preliminary evidence-only structure

The initial 10/6/4 split below is one replay candidate, not an approved rubric.
The verified decomposition in `PROBIOTIC_CURRENT_12_DECOMPOSITION.md` shows that
the current 12 already rewards study design, evidence scope, effect direction,
enrollment and, on the generic path, some research depth. A replacement must
reuse those facts without awarding them twice.

| Component | Points | Owns |
|---|---:|---|
| Clinical certainty and effect | 0-10 | Quality of qualifying human evidence, reviewed effect direction and certainty |
| Direct applicability | 0-6 | Exact strain or studied formula, preparation, population, outcome and product purpose |
| Independent replication and consistency | 0-4 | Independent qualifying human studies or an applicable high-quality synthesis with consistent results |

The public Evidence maximum remains 20/20. No component reads CFU, trial dose,
label amount or industry potency.

## Guardrails

- No qualifying applicable human evidence means zero, even when the strain name
  is well known.
- Combination evidence belongs to the exact combination; it cannot credit one
  member strain.
- An unspecified probiotic blend cannot inherit strain-specific evidence.
- Adding strains does not stack Evidence points. The strongest applicable
  product-owned record or exact studied formula owns the result.
- One strong applicable trial can score well but cannot receive the replication
  maximum merely because it has several endpoints or publications.
- Null, negative, population-mismatched, route-mismatched and preparation-
  mismatched evidence remains visible but earns no positive component it does
  not establish.
- Trial amount remains a source fact consumed by Dose. It never changes these
  Evidence components.

## Expected examples for replay

- Strong, exact, independently replicated strain/formula: eligible for 20/20.
- Strong exact evidence from one controlled human trial: high but below 20.
- Moderate exact evidence from one trial: mid-range Evidence.
- Relevant research with broad product positioning: partial applicability,
  without manufacturing a direct outcome match.
- Combination-only record applied to a single strain: zero for that strain.
- Unspecified blend: zero until the formula or strains are identified.

These are directional examples. Exact band values must be compared against at
least one non-overlapping alternative on the frozen 542-label probiotic cohort
before approval.

## Required measurement

Replay this candidate through `probiotic_evidence.score_evidence`, never a
parallel calculator. Report:

1. every changed label and component driver;
2. category minimum, median, p90 and maximum;
3. counts reaching 80, 90, 95 and 100 overall;
4. every Poor-tier crossing using the production rounded-score tier rule;
5. every safety, status and publication change;
6. exact studied formulas, single-strain products, multi-strain products,
   unspecified blends, null evidence and combination-only controls;
7. whether any product reaches the ceiling through duplicated publications,
   strain count or broad positioning instead of stronger evidence.

External category scores may be used as a reasonableness comparison, but they
do not set PharmaGuide points. PharmaGuide remains an absolute, category-aware
quality rubric rather than a curve that awards a predetermined number of 95+
scores.
