# PharmaGuide V4 blinded reviewer benchmark protocol

Status: sample, protocol, and analysis contract frozen; reviewers not yet registered

Protocol version: 1.1.0

Freeze ID: `2026-08-06-v6`

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
3. their reviewer-slot rows from `reviewer_response_template.csv`, joined to
   the packet by `benchmark_id` and sorted by `reviewer_order`.

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

Use one fixed primary panel of exactly three independent reviewers. Each
primary reviewer rates every frozen product and keeps the same reviewer slot
throughout the study. This complete target-by-rater design is required for the
pre-specified two-way random-effects ICC. A substitute or rotating reviewer is
not treated as the same rater and is excluded from the primary ICC analysis.

Before assignment, record reviewer ID, fixed reviewer slot, credentials,
supplement-evaluation experience, conflicts of interest, and protocol training
completion in `reviewer_registry.csv`, using the frozen
`reviewer_registry_template.csv` contract.

At least two of the three primary-panel reviewers must be a
licensed pharmacist, physician, or registered dietitian with relevant
supplement or evidence-appraisal experience. No reviewer may evaluate a
product or brand for which they have a financial, employment, consulting, or
research conflict. Because the same panel rates every product, a primary-panel
reviewer must be conflict-free across the complete frozen sample.

Reviewers complete a training exercise on products outside the frozen sample.
Training explains the concepts and data-entry rules but never discloses V4
scores, thresholds, denominators, penalties, or sample assignments.
Each reviewer receives the products in an independently randomized order.
The three deterministic assignments are frozen in
`reviewer_response_template.csv`; `review_sequence` is the hidden master join
key, while `reviewer_order` is the only order used for reviewer distribution.

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
7. For `caution`, `unsafe`, or `blocked`, identify the substance, dose, or
   product-level event in `safety_concern_driver`.
8. Record confidence, whether the supplied label facts were sufficient, and a
   short rationale.
9. Do not discuss the product with another reviewer until all responses lock.

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

Primary analysis uses only products whose three responses pass the arithmetic
gates and contain no protocol deviation. If any reviewer records a deviation,
that whole product is excluded from the complete-panel primary analysis and
retained in the all-locked-responses sensitivity analysis. No imputation is
performed for missing ratings.

1. Require three eligible, blinded ratings per product.
2. Verify each reviewer overall equals the six-pillar sum.
3. Use the median of the three fixed-panel reviewer ratings as product
   consensus.
4. Report inter-rater absolute agreement for overall and each pillar with
   confidence intervals; use ICC(A,1), the two-way random-effects,
   absolute-agreement, single-rater coefficient. Also report ICC(A,3) for the
   reliability of the three-reviewer mean. Confidence intervals use the
   deterministic product-level bootstrap frozen in `ANALYSIS_SPEC.json`.
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

The fixed tier thresholds, safety severity order, bootstrap seed and
iterations, arithmetic tolerance, exclusion rules, and metric direction are
machine-readable in `ANALYSIS_SPEC.json`. The manifest fingerprints that file
and the analysis implementation. Any change creates a new benchmark freeze.
The development analyzer rejects the sealed holdout by filename and split
before reading its rows. Holdout analysis additionally requires an approved,
content-locked candidate record containing the frozen analysis hashes and
expected direction.

This protocol does not invent a pass/fail accuracy threshold before a
statistician and clinical owner sign it. Lack of a threshold cannot be used to
justify a score change: calibration remains frozen until the reviewer
registry, analysis implementation, and decision thresholds are version-locked.

## Deviations, exclusions, and audit trail

- Never overwrite a rating. Corrections append a new row with a new
  `review_round` and `correction_reason`.
- Record unblinding, conflict discovery, missing label facts, source-access
  failure, and reviewer substitution.
- Exclusions are decided without viewing engine output.
- Preserve raw responses, exclusions, adjudication, analysis code, and opened
  baseline hashes.
- Any evidence/config change after this freeze creates a new benchmark
  version; it does not silently update this baseline.
