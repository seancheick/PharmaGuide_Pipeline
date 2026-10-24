# Preparation and clinical review handoff — October 23, 2026

This is a shareable review request, not clinical approval or a release-readiness certificate.
The initial 15,437-product snapshot is unchanged. Product dependencies below come from retained
October 23 diagnostics; they are not a fresh corpus census. No production pipeline was rerun.

## What needs a clinician, and what needs source work first

A source's existence, chemical identity, an abstract review and a successful score calculation
are separate from a completed clinical assessment. The existing clinical context owner requires
attributable clinician approval for contexts used for affirmative clinical scoring. The reviewer
must also establish exact identity/preparation, delivery, dose/regimen, population, outcome,
evidence strength, limitations and product applicability. Approval cannot fill an undisclosed
manufacturer quantity or establish equivalence between different preparations.

The [83-record clinical review list](clinical_review_holds.csv) names every actual-used legacy
record in the frozen 727-product positive-Evidence/incomplete cohort, its exact dependent IDs,
source links and current source-review result. These records cover 410 distinct frozen products
(524 overlapping record-product dependencies), not all 727 cohort products. All 83 currently return
`clinical_source_contexts_missing` through `clinical_applicability::assess_clinical_source_review`.
This means source-context extraction and applicable review remain necessary; it does not mean
83 independent literature searches or 727 independent approvals. SAMe and glycine additionally
remain explicitly ineligible for scoring. Frozen dependencies do not assert current positive credit.
Previously approved native strain contexts are not revoked by this legacy-record list.

The [506-subject benchmark worklist](benchmark_review_backlog.csv) preserves the retained
3,118-product / 4,259-row diagnostic. Its subject lists overlap; counts must not be summed as
unique products. These are unresolved reviews, not 506 newly imposed clinician holds.
A completed, source-backed no-benchmark determination can be legitimate under the existing
owner; neither an unsuccessful bounded search nor a studied dose establishes that determination.

## Priority preparation reviews

| Subject / exact labels | Verified facts and limits | Requested decision / missing evidence |
|---|---|---|
| Schisandra: 210629,210738,232056,27350,294537–294540,295208,298046,311541–311544,312701,317646,327583,328521,330720–330723,67289 | [Trial 32260466](https://pmc.ncbi.nlm.nih.gov/articles/PMC7177795/): BPK-SC-001 extract, 20% ethanol extraction, measured schizandrin; 1,000 mg/day for 12 weeks; 52 randomized postmenopausal women, 45 completed. Quadriceps-strength result is not a universal benefit or dose threshold. | Establish exact preparation, directions and purpose for each shared label family. Do not convert total schisandrins to schizandrin or borrow muscle findings for liver claims. |
| Boswellia resin: 311175–311178,312866,329934,330458–330461 | Existing [5-Loxin](https://pubmed.ncbi.nlm.nih.gov/18667054/) and [Aflapin](https://pubmed.ncbi.nlm.nih.gov/35512759/) reviews describe specific preparations and knee-OA regimens. Rat source 32565872 remains nonhuman and ineligible. | Confirm exact preparation/standardization and applicability; generic resin mass does not establish branded preparation equivalence. No universal resin benchmark proposed. |
| Extramel 232942 | Stress-purpose label declares 140 IU daily in a liquid hemp combination. Trials used 10 mg/140 units in capsules of palm-oil-coated microgranules. | Establish protected-delivery equivalence and ingredient-level applicability in this combination/population. Do not infer mass from activity. |
| Extramel 328442 | 36 mg/500 IU daily in a multi-active softgel; arterial-support purpose. | The reviewed stress/fatigue trials do not support this arterial claim. Identify a separately applicable source if one exists; higher dose alone does not qualify. |
| Extramel + Schisandra 328521 | Label declares 10 mg/140 IU Extramel and 250 mg Schisandra with 9% total schisandrins; liver-metabolism purpose. | Neither reviewed trial family establishes this liver claim. Resolve exact preparation and purpose before affirmative credit. |
| Other SOD: 315306,67283 | Generic SOD, GliSODin and Extramel are not interchangeable. | Establish the exact preparation, protection/delivery, regimen and outcome. Existing nonhuman source 15742357 remains ineligible for human benefit credit. |
| Magnesium biotinate: 299744,336100 | Chemistry verified; distinct salt recognized without numerical form grade. Oral Lustriva trial is a biotin/silicon combination. | Evaluate preparation-specific human absorption/form quality separately from combination outcomes. Preserve ungraded status and existing holds; no invented elemental quantities. |
| Kelp: 331151,331152,331154,312063–312066 | Exact Laminaria japonica whole-source extract, 500 mg. Only 331151/52/54 declare 10:1; the ratio is not copied to the other labels. | Species routing correction does not complete preparation/benchmark review. Retain unresolved benchmark assessment. |
| Kelp source in iodine product 309387 | Exact thallus extract 33.75 mg; separately declared iodine 225 mcg and calcium 80 mg. | Retain the extract preparation and benchmark holds even when nutrient assessment completes. The prior mineral-route bypass is corrected; no inferred iodine concentration or generic kelp benchmark. |
| Cranberry 330664 | Label names Vaccinium oxycoccus/oxycoccos, not macrocarpon. | Establish species-specific preparation and applicability. Do not borrow macrocarpon form credit, benchmarks or remove warnings based solely on taxonomy. |
| Mixed grape 330882 | One row contains seed AND skin, total 210 mg; separate seed row is 125 mg. | Establish the actual mixed preparation and applicable evidence. No component quantities or BioVin equivalence are established by this label alone. |
| Cherry 294296 | Explicit Prunus avium fruit identity corrected previously; preparation remains ungraded. | Complete exact extract/preparation and benchmark review; identity correction does not approve a dose or clinical claim. |

Extramel sources: [2009 trial](https://pmc.ncbi.nlm.nih.gov/articles/PMC2757026/),
[2014 trial](https://pmc.ncbi.nlm.nih.gov/articles/PMC4073155/). Both had Seppic/Bionov support.
The later paper separately declares no conflict of interest. Both facts should be visible;
funding does not by itself invalidate results. Small studies and subjective stress/fatigue
outcomes limit transfer. This corrects the earlier packet's incomplete funding description.

## Required reviewer return and closure

For each shared cause or clinical subject, return the record/context ID; affected label IDs;
source citation and inspected section/full-text availability; exact preparation/delivery;
normalized dose and its provenance; population and outcome hierarchy; results and limitations;
applicable, inapplicable or still-unresolved conclusion with reasons; and reviewer identity,
qualifications and dated approval where required by the existing clinical owner.

Engineering then applies the result through the existing registry/assessment owner, adds
regressions, verifies affected labels and controls, and checks the eventual rebuilt outputs.
A source review or code fix is **implemented**, not **rebuilt-closed**. No blanket approval,
new numerical benchmark, scoring-weight change, manufactured amount or publication is requested.
Banned/recalled discoverability and warnings remain mandatory.

## Provenance and scope

Owner: `clinical_applicability::assess_clinical_source_review`,
`clinical_evidence_schema::validate_ingredient_context`,
`probiotic_measurements::context_accepted_for_scoring`, and
`botanical_profile::_botanical_benchmark`. These files own decisions; this document and CSVs
are static projections for review, not a second registry or completion authority.

Source baseline: `1012f3753`. Legacy dependency input SHA256:
`d19092d2f05e9c4d8a278ba9287ecb2ba4f8f998138b78352a5596a2e0f32d1b`.
Benchmark diagnostic input SHA256:
`53afc610bba5c1e938d6323b866d54548a1558aa02b7aeb0be11818766c53363`.
The existing research packets retain exact source and label hashes. The [research log](research.md)
and [execution ledger](../pending_items_20260926/LEDGER.md) record verification limits and results.
This bounded review does not establish that all literature has been searched or that every
remaining corpus hold is represented by the named priority cases.

## Read-only clearance audit update

The October23 continuation resolved the five-source citation inventory without curated writes.
All402citation links for the83legacy records resolve; all175available stored titles match. This is
bibliographic screening only. No clinical hold was cleared. The research log now separates
publication corrections, biotinate absorption versus combination efficacy, native registration
protocols, and five topic-screen dispositions. Full-text access and approval limitations remain
explicit. Use these receipts to avoid repeating verified lookups, while completing the missing
clinical/preparation/outcome review through the existing owners.

PQQ review must include corrected Table4 (notice35917215 for trial34415830) and reconcile
the abstract's adverse-event wording with the submitter's account in FDA-hosted GRN1118,
page53. Table retrieval remains unresolved; the secondary account is not FDA endorsement
and does not by itself establish a treatment-related risk or efficacy conclusion.
