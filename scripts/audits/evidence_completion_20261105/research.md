# Evidence completion corrections — November 5, 2026

Owner: `evidence_resolver.py::_resolve_evidence_for_row` consumes the existing
`clinical_applicability` preparation and source-review decisions. IQM form identity
and notes belong to `ingredient_quality_map.json`; the enricher and canonical form-note
export consume them. Evidence: current source, the shared ownership matrix, existing
form-identity regressions, and source-bound product204048. Will NOT create a scorer,
clinical approval, branded-material registry, clinical threshold or product exception.

## Completed records must compose

A row matching a finished preparation exclusion and a separately completed reference-only
review remained `clinical_sources_ineligible`: the old aggregation accepted only homogeneous
sets. The shared fix permits the mixed finished set, grants no points, and keeps each source's
conclusion. It does not finish an unreviewed, malformed, held or positive source.

The 143 L-carnitine screening products contain several distinct preparations. Only the 49
ALCAR-only candidates match this initially identified closure class; mixed/base/LCLT cases
remain separate. These are candidates until measured, not a fresh whole-catalog count.
No clinical source, study context, approval or Dose benchmark is changed by this fix.

## Elderberry: one canonical entry, two form corrections

Entry: `elderberry.forms` in `scripts/data/ingredient_quality_map.json`.

- Generic names, cultivar/ratio descriptions, ElderCraft and NordicElderberry aliases
  do not establish Sambucol identity. Move the 51 non-Sambucol aliases from that proprietary
  form to the existing unspecified form; retain the two explicit Sambucol aliases.
- Product204048 (Nature's Way) reproduced the error on its nested `premium cultivar
  Elderberries` source row and through the canonical exported form-note owner. Correct the
  upstream alias assignment rather than hiding the brand on that one product.
- The unspecified form's revised identity-uncertainty description is attributed to agent
  factual review. The previous August8 approval is not copied onto newly written text.
- Preserve all four existing bio scores, canonical/species identifiers, printed amounts,
  source paths, clinical decisions, warning rules and the Sambucol reviewed consumer note.
  A changed Formulation score caused by correcting a false form assignment is possible;
  it is not a new calibration. Verify actual movements in the bounded replay.

### Per-source factual verification

Root and independent review checked the live primary sources on November5 local date:

1. [Frank et al., 2007, PMID18040528](https://pubmed.ncbi.nlm.nih.gov/18040528/): six healthy
   volunteers; 0.27–0.39% unchanged anthocyanins recovered in urine within seven hours.
   This endpoint does not establish an absolute absorption fraction. Correct the wrong
   author/year and remove unsupported precise fractions for the branded and unspecified
   preparations, using the existing null/unknown representation. Preserve bio-score policy.
2. [Wieland et al., 2021, PMID33827515](https://link.springer.com/article/10.1186/s12906-021-03283-5):
   possible symptom-duration/severity benefits remain uncertain across heterogeneous
   preparations. Replace the strong fixed-duration/mechanistic claim with bounded,
   formulation-specific uncertainty; do not replace it with a blanket absence of benefit.

The changed-entry PubMed content verifier matched both citations. Factual source correction
is not clinical approval of a new scoring context. Other preparation-specific pharmacokinetic
estimates were not qualified by this bounded review.

## Validation and limits

Fail-first owner, form-matching, exported form-note and nullable-fraction regressions ran
before the corresponding fixes. Completed baseline captures at0170 are distinct from the
completed candidate416 comparison at8ca, later67 raw captures at889 across all seven modules,
and seven necessary follow-up captures at2f01 restoring the discovered vitaminE upper bound.
These bounded receipts do not qualify the current whole catalog. The later67 Score/export
projection atabbedafe0 reuses those captured Enrich inputs and preserves all numeric pillars,
statuses and warnings, with only enumerated copy/citation/review-provenance metadata changes.
Combined CI qualification is still pending; the correctly bound local artifact rung passed
564 checks with24 declared opt-in skips. Exact-source results and limits are in the execution
ledger. Do not infer invariance from unit tests or restamp completed304 output as current.

Newly accessible L-carnitine and elderberry full texts are preserved in the existing private
source packets. Access alone does not resolve their population, preparation, outcome or
source-approval holds. Betaine's lower-body-strength scope remains independently unresolved.
No release, new clinical credit, dose adequacy threshold or clinical sign-off is implied.

## November6 — completed reference sources without affirmative credit

Owner: `clinical_applicability.py::assess_clinical_source_review` and `evidence_resolver.py::_resolve_evidence_for_row`; existing `backed_clinical_studies.json` records `INGR_BORON` and `PRECLIN_AKG`. Will NOT create another matcher, registry, status, field, dose benchmark or credit policy. The source-review owner distinguishes fully covered canonical rejected-source conclusions from missing review, only when both classifications are reference. Parent scoring eligibility remains false where recorded. Approved/non-rejected holds, malformed/unbound/pending siblings, missing sources and classification conflicts stay incomplete. The resolver consumes that same completion result rather than independently vetoing completion by a points flag.

Boron sources PMID8508192 and7889885 describe the same19male bodybuilders,10boron/9placebo,2.5mg/day seven weeks. Reported plasma-boron exposure change is not erased; no between-group testosterone/lean-mass/strength benefit is transferred to general bone/joint claims or calcium fructoborate. The two publications are one experiment, not independent replication. Primary abstracts and the1994citation graph were checked; scanned full Methods were not represented as read. Existing reference grade, direction, identifiers, exclusions, Dose and safety fields are untouched.

AKG PMID37217632 (DOI10.1007/s11357-023-00813-6, official PMC10643463) is an ABLE trial protocol. PMID40819772 (DOI10.1016/j.exger.2025.112867) concerns recruitment feasibility, not efficacy. Official protocol full text and author-hosted publisher-version feasibility body were checked.120planned/enrolled participants are not completed efficacy observations, and the reports are not two independent efficacy trials. Existing parent scoring_eligible=false, all source facts, Dose and safety remain unchanged.

Actual delegated agent authoring and a separate independent agent check are recorded2026-11-06, under Sean's authorization; no physician attribution is fabricated. Three existing-schema rejected_source contexts are added to the two existing records, preserving every prior field and identifier. Source/API verification resolves all four PMIDs and both DOI links with zero broken/retracted records; manual primary-content/applicability review remains separately documented.

Fail-first: one source-owner failure with seven negative controls; two missing-data failures with the actual PQQ hold passing. Final named owner/readiness slice1066passed. Independent41boundary checks pass. Exact data_batch check: two keys changed, zero problems. The old synthetic record_hold case is explicitly a completed exclusion; ordinary approved/nonrejected parent holds and actual PQQ unread corrected source remain pinned incomplete.

Bounded full raw→Clean→Enrich→Score→blob comparison: all66 reached products plus four controls; baseline bf57f7b5e versus e3b40da91, identical frozen raw manifest and unchanged source during both captures. All70 captured successfully.13Boron and19AKG products move partial→complete (32total), zero reopens;34affected products retain other holds. All totals, six numeric pillars, score statuses, tiers, safety gates, source quantities/identities and warnings are unchanged. Clean and Enrich hashes are identical. Independent recursive comparison confirmed every one of51 changed paths, with only the intended Evidence readiness/state/explanation changes. This does not update the frozen global8,496/6,951 census. Private source/capture receipts are retained in `evidence-review-next/existing49/applied-replay/` and the independent source-review packet. Final combined local/CI qualification remains pending.
