# PharmaGuide V4 blinded reviewer benchmark protocol

Status: sample and protocol frozen; reviewers not yet registered

Protocol version: 1.0.0

Freeze ID: `2026-08-06-v4`

## Purpose and context of use

This benchmark tests whether the V4 product-quality score agrees with
independent expert judgment on the same six concepts. It is not a clinical
trial, a diagnosis, or evidence that a supplement is effective for a specific
person. Its context of use is internal scoring validation and calibration
control.

The protocol follows the reliability-study principle that the rater
population, sample selection, blinding, measurement procedure, and statistical
analysis must be specified before ratings are interpreted. See the
[GRRAS reliability and agreement guideline](https://pubmed.ncbi.nlm.nih.gov/21514934/)
and the FDA's emphasis that an assessment is evaluated within a defined
[context of use](https://www.fda.gov/about-fda/clinical-outcome-assessment-coa-frequently-asked-questions).

## Frozen sample

- 120 released, scored products.
- 10 products from each of the 12 V4 scoring archetypes.
- Within each archetype: 6 deterministic core products and 4 deterministic
  challenge products.
- Challenge selection covers catalog safety caution, zero Evidence, low
  confidence, and proximity to a configured tier boundary.
- 96 products form the development analysis set.
- 24 products form a sealed holdout: one core and one challenge product per
  archetype.
- The sample, release, engine/config versions, label-fact inputs, baseline
  outputs, and artifacts are content-fingerprinted in `manifest.json`.

The core/challenge design is deliberately not a catalog-prevalence estimate.
Results must be reported overall and by archetype. Catalog-wide claims require
post-stratification or a separate prevalence-weighted sample.

## Blinding and artifact handling

Reviewers receive only:

1. this protocol;
2. `reviewer_packet.csv`; and
3. an individually assigned copy of `reviewer_response_template.csv`.

Reviewers must not receive or inspect:

- `development_baseline_key.csv`;
- `SEALED_HOLDOUT_KEY.csv`;
- the PharmaGuide app or catalog score for a sampled product;
- scoring source/configuration;
- another reviewer's ratings or rationale; or
- the development/holdout and core/challenge assignments.

Product and brand names remain visible because product-level certification and
manufacturer evidence are concepts under review. Reviewers must not search the
PharmaGuide app or repository. Accidental unblinding is recorded in
`protocol_deviation`; that rating is excluded from the primary analysis and
retained in a sensitivity analysis.

The baseline key is opened in two stages:

1. `development_baseline_key.csv` opens only after all reviewer responses and
   analysis code are locked.
2. `SEALED_HOLDOUT_KEY.csv` is access-restricted from both reviewers and the
   calibration analyst. It opens only after any calibration candidates, their
   expected direction, and the unchanged analysis code are locked.

## Reviewer eligibility and independence

Use at least three independent reviewers per product. Before assignment,
record reviewer ID, credentials, supplement-evaluation experience, conflicts
of interest, and protocol training completion in a separate reviewer registry.

At least two of the three assigned reviewers for every product must be a
licensed pharmacist, physician, or registered dietitian with relevant
supplement or evidence-appraisal experience. No reviewer may evaluate a
product or brand for which they have a financial, employment, consulting, or
research conflict.

Reviewers complete a training exercise on products outside the frozen sample.
Training explains the concepts and data-entry rules but never discloses V4
scores, thresholds, denominators, penalties, or sample assignments.

## Independent review procedure

For each assigned benchmark ID:

1. Review the supplied label facts.
2. Verify material dose, evidence, safety, and certification claims against
   authoritative primary or official sources.
3. Record every source used in `source_citations_json`. A PMID, DOI, or direct
   official URL is required for each material clinical conclusion.
4. Score each pillar independently using the anchors below.
5. Enter `overall_0_100` as the exact sum of the six pillar ratings.
6. Assign the independent product safety status.
7. Record confidence, whether the supplied label facts were sufficient, and a
   short rationale.
8. Do not discuss the product with another reviewer until all responses lock.

The review is product-level, not personalized. Drug/condition interactions are
considered only where they establish a catalog-level concern; they do not
replace personalized interaction logic.

## Rating concepts and anchors

Use any value within the stated range. Half-points are allowed. Do not infer a
missing fact as either positive or negative; reflect uncertainty in the score,
confidence, and rationale.

| Field | Range | Independent question | Anchor guidance |
|---|---:|---|---|
| `formulation_0_20` | 0–20 | Are the disclosed ingredient forms and formulation choices appropriate? | 0 = materially poor/incoherent; 10 = mixed or uncertain; 20 = consistently strong and fit for purpose. |
| `dose_0_20` | 0–20 | Are disclosed daily doses plausibly effective without material excess? | 0 = unusable/materially unsafe; 10 = partial or uncertain; 20 = well supported and appropriate. |
| `evidence_0_20` | 0–20 | Does human research support the actual actives, forms, doses, and intended use? | 0 = no comparable human support; 10 = limited/mixed support; 20 = strong, directly comparable support. Explain how study direction and comparability affected the rating. |
| `transparency_0_15` | 0–15 | Does the label disclose identities, amounts, serving basis, and blends adequately? | 0 = materially opaque; 7.5 = partial; 15 = complete and clear. |
| `verification_0_15` | 0–15 | Is product-specific independent testing or quality-system evidence verified? | 0 = material contrary evidence; 7.5 = partial or mixed verified evidence; 15 = strong product-specific verification. Unknown evidence has no automatic score: record the uncertainty and rationale. Brand-only claims are not product-specific proof. |
| `formula_quality_checks_0_10` | 0–10 | Are there known product-level safety, recall, additive, or quality-system concerns? | 0 = severe known concern; 5 = material caution/uncertainty; 10 = no known catalog-level concern after review. |

`product_safety_status` is independent of the quality score:

- `blocked`
- `unsafe`
- `caution`
- `no_known_catalog_concern`
- `not_assessed`

Under-warning is the higher-risk error. Any reviewer assigning `blocked`,
`unsafe`, or `caution` must cite the source and identify the substance, dose,
or product-level event that drives the rating.

`assessment_confidence` is `high`, `moderate`, or `low`.
`label_facts_sufficient` is `yes` or `no`.

## Locked analysis plan

Primary analysis uses only responses that pass the protocol and arithmetic
gates. No imputation is performed for missing ratings.

1. Require three eligible, blinded ratings per product.
2. Verify each reviewer overall equals the six-pillar sum.
3. Use the median of the three reviewer ratings as product consensus.
4. Report inter-rater absolute agreement for overall and each pillar with
   confidence intervals; use a two-way random-effects, absolute-agreement ICC
   for continuous ratings.
5. Compare engine versus consensus with signed error, absolute error,
   Spearman rank correlation, exact tier agreement, and within-one-tier
   agreement.
6. Report all measures overall, by archetype, by pillar, and by core/challenge
   cohort. Do not hide small strata inside the aggregate.
7. Report safety undercalls and overcalls separately. Every potential undercall
   receives blinded clinical adjudication before any calibration decision.
8. Use bootstrap confidence intervals for archetype/pillar signed bias.
   A scoring parameter becomes eligible for calibration only when a
   pre-specified mechanistic link exists, the development-set bias is
   directionally consistent, and the proposed change does not worsen safety.
9. Lock the candidate change and expected direction before opening the
   24-product holdout. The holdout is reported once; failed candidates are not
   retuned against it.

This protocol does not invent a pass/fail accuracy threshold before a
statistician and clinical owner sign it. Lack of a threshold cannot be used to
justify a score change: calibration remains frozen until the reviewer
registry, analysis implementation, and decision thresholds are version-locked.

## Deviations, exclusions, and audit trail

- Never overwrite a rating. Corrections append a new row with a new
  `review_round` and reason.
- Record unblinding, conflict discovery, missing label facts, source-access
  failure, and reviewer substitution.
- Exclusions are decided without viewing engine output.
- Preserve raw responses, exclusions, adjudication, analysis code, and opened
  baseline hashes.
- Any evidence/config change after this freeze creates a new benchmark
  version; it does not silently update this baseline.
