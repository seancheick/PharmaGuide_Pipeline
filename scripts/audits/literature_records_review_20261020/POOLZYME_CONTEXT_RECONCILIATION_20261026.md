# Poolzyme source-context reconciliation — October 26, 2026

Owner: `scripts/data/backed_clinical_studies.json::INGR_DIGESTIVE_ENZYMES`, existing `clinical_applicability.py`/ingredient-context and `evidence_resolver.py::clinical_record_sources_eligible` consumers. Evidence: signed returned batch6, primary PubMed API37976892, retained ISRCTN67691215 XML, current seven-product source-dependency group. Will NOT create another registry, scorer, numerical dose curve or approval authority.

## What is implemented

One source-specific context now records Poolzyme Multi, a named five-enzyme fungal preparation,200mg at lunch and200mg at dinner for60days, in120adults aged18–59 with functional dyspepsia. NDI-SF quality of life is primary; painVAS and sleepPSQI are secondary. Whole preparation mass does not determine individual enzyme masses, activity equivalence or a universal400mg/day efficacy threshold.

The current primary abstract confirms120participants (63men/57women), not the previous unsupported168aggregate. That count is corrected; the unsubstantiated seven-completed-trial field is set to null. This is one retained cited trial, not seven established preparation-specific RCTs.

**The signed return explicitly retains final source acceptance.** It accepts the preparation-name/exposure facts but asks for complete outcome-table appraisal and ethics/registration reconciliation. Therefore this context is `source_verified_pending_clinical_review`, with no fabricated approved stamp or acceptance date. Outcome-level directions remain unresolved until the actual comparison tables are appraised; favorable abstract wording alone is not encoded as verified between-group superiority.

The existing top-level `scoring_eligible=false` convention now contains this relationship while that explicit source-acceptance hold remains. It withholds affirmative scoring/benefit qualification without inventing a penalty, unsafe-product finding or replacement grade. The provisional historical tier/direction, trial, exposures and source history remain visible. Credit can return only after a qualifying exact-scope decision, not merely because context fields are populated.

## Source verification and exact residual

The live [PubMed API37976892](https://pubmed.ncbi.nlm.nih.gov/37976892/) was read on October26; [original DOI](https://doi.org/10.1016/j.biopha.2023.115858). The returned source review supplies the named material and lunch/dinner extraction from the original report. New publisher full-text access returned403; institutional metadata search supplied no full paper. This pass does not claim new complete paper/outcome-table inspection.

The retained [ISRCTN67691215](https://www.isrctn.com/ISRCTN67691215) XML shows:

- First enrolment **June16,2023**, registration **June28,2023**: retrospective relative to first enrolment. Do not claim prospective endpoint registration.
- Ethics approval **November7,2022**, Comitato Etico Campania Centro, reference591.
-400mg/day whole preparation for60days,120participants, primaryNDI-SF and secondaryVAS/PSQI.
- Functional-dyspepsia medication use was permitted and recorded. Empty co_therapies means none extracted here, not proof none was used.

Only these precise source dependencies remain:

1. Obtain and inspect original37976892outcome tables and analyzed-population/missing-data handling to establish the actual between-group effects.
2. Compare the original paper's reported ethics dates/identifiers with registry November7,2022/reference591. The signed return reports conflicting paper statements; this pass does not invent reconciliation or claim independently reading unavailable pages.
3. Complete final acceptance/rejection for that exact source scope after those facts are resolved. Preparation identity/dose retrieval does not need repeating.
4. For any product seeking credit, establish actual Poolzyme preparation/activity correspondence; common enzyme names and blend mass do not establish equivalence.

## RAW275412 and unused PrimaVie

Poolzyme Multi is not RAW Enzymes275412. The signed review rejects exact-RAW-trial transfer. Preserve620mg enzyme-group total,31mg probiotic group, groupCFU/activity declarations and previously verified daily regimen through their existing owners; no component masses/strain doses are invented here.

`BRAND_PRIMAVIE_SHILAJIT` exists but is outside the current146contributing-source blocker set. Its source facts were checked via the same API batch, but no runtime change is made to this unused subject. Unused historical rows do not block publication. Do not transfer hormone biomarkers to vitality, PK, strength, longevity or retail-batch purity/certification.

## Receipts and verification

- Live PubMed batch XML `.claude/state/clinical_context_migration_20261026/primavie_poolzyme_pubmed.xml`: SHA256`db43382da06d03cbefa7049505e8f253138506eaa599b4a0d2f220deaf3be4bf`.
- Retained ISRCTN XML `.claude/state/bryan_batches_6_7_20261025/ISRCTN67691215.xml`: SHA256`15607491c76ce1fd4f1c8ce28b0e00d471cb4a003a939b658bf0022fc8d4e909`.
- Signed returned batch6: SHA256`a5a19f6191af1c6c5dbc9b11bfff48b2b03e7a905af13e1275be68307e02aa8e`.

Missing-context regression failed first, then the context/schema/applicability slice passed227tests. The explicit eligibility regression also failed first, then the focused Poolzyme/source-role slice passed4tests. Final focused context test preserves unresolved outcome direction and the absence of invented approval. Existing source owner still reports incomplete review; no seven-product/full-corpus closure is claimed. Integration owns the combined affected/control replay, eligibility/point movements, safety/amount parity, CI and final source qualification. No corpus rerun, commit, export or publication occurred in this subtask.
