# Consolidated scientific completion handoff — October 23, 2026

## Scope and authority

Finish confirmed shared producer/source-attribution defects; preserve original 15,437-product
snapshot and 727-product positive-Evidence/incomplete cohort. Source inspection is not clinician
approval. No scoring weights, clinical approval authority, safety policy or release authorization
changed. No full corpus rebuild, export or publication performed in this batch.

Owner: `scripts/enrich_supplements_v3.py::_collect_probiotic_data/_form_token_context` — evidence:
fail-first physical-parent/constituent/form regressions and raw-label replay.
Owner: `scripts/data/backed_clinical_studies.json` through existing applicability/evidence resolvers —
evidence: exact-record source inspection, source eligibility and purpose-consumer regressions.
Owner: existing assessment readiness and botanical benchmark owners — evidence: saved contribution
census and all 4,259 frozen benchmark row decisions. Will NOT create another scorer, registry,
matcher, clinical approval authority or completeness system.

## One remaining-work list

1. **Clinical approval:** saved manifest-owned corpus has 153 contributing record IDs across
   6,389 record-product dependencies: 152 curated records and generated
   `RECOVERED_COLLAGEN_PEPTIDES_V1` (24 products). All 152 curated records lack study contexts.
   Five are now reference-only, ineligible for affirmative credit: INGR_MOLYBDENUM,
   INGR_PROPOLIS, INGR_SLIPPERY_ELM, INGR_VITAMIN_E, PRECLIN_BETAINE_HCL.
   **147 remaining source-eligible curated records require attributable context review before
   affirmative clinical use**, plus review of the generated collagen source binding/context.
   Verify identity/strain, preparation/delivery, dose/regimen, population, outcome and limitations.
   Reusable contexts can cover many products. These are not 147 separate literature searches.
   `clinical_review_holds.csv` is the sharing list: 155 union rows preserve all original 83 cohort
   records, add actual saved contributors and distinguish three historical-only records
   (INGR_BIFIDOBACTERIUM_BIFIDUM, INGR_GLYCINE, INGR_SAME). Unused history does not block release.
2. **Benchmarks/preparations:** 506 subjects / 4,259 frozen rows / 3,118 products remain open.
   Actual alias-aware owner lookup partitions rows into 43 preparation guards, 1,771 with
   literature study rows, 1,206 without study rows and 1,239 without an eligible exact owner.
   No row currently resolves a completed applicable benchmark. Review exact preparations and
   document supported regimen or defensible negative/no-general-benchmark findings through the
   existing owner. One tested dose is not an efficacy threshold, optimum or safety upper limit.
   These 506 subjects are not automatically clinician holds. The CSV records required actions;
   none is scientifically closed merely by this source packet.
3. **Identity/dose:** the frozen 238-label diagnostic remains a bounded sample, with causes and
   final replay counts: 133 identity-incomplete, 51 dose-incomplete, 10 overlapping,
   174 products in their union (baseline 177). Final replay confirms three resolved cases. Remaining cases include genuine species/
   plant-part conflicts, unknown preparations, conflicting label units, vitamin A DFE labelling,
   unresolved elemental potassium-iodide ownership, undisclosed mixtures and unscoreable source
   quantities. Label limitations must be documented separately from unfinished PharmaGuide work.
   Do not guess quantities, species or conversions to clear them.
4. **Verification after decisions:** rebuild the corpus once from the earliest stale stage, then
   enforce the complete evidence/dose invariant on every assessment and inspect Flutter, including
   original 20 labels and banned/recalled discoverability. Targeted replay is not corpus clearance.

## Implemented batch and verification limits

50 exact curated source records corrected together: trial design, actual preparation/regimen,
primary-versus-secondary/null findings, supported endpoints and source counts. Five reference-only
withdrawals preserve citations/history. Benfotiamine and spermidine describe mixed results.
Negated/null/adverse-event language remains in notes rather than affirmative purpose matching.
No clinician sign-off created; no required hold removed. Exact per-entry scope and primary source
receipts remain in research.md and the named owner tests.

Shared producer fixes distinguish physical probiotic container headings from actual strains,
preserve independent CFU totals, and retain structured constituent/plant-part provenance.
Named proprietary complexes, negation and real identity conflicts remain held; transient matching context is not exported.

Bibliographic owner verified 50 entries / 198 PMID claims, strict pass with no missing/title/ghost
findings. This proves citation binding, not full-text review or approved clinical applicability.
Publication corrections and restricted full texts remain explicit limitations, including PQQ
corrected Table 4 / GRN1118 attribution and B. bifidum correction 34652462. Earlier stopped or
uncovered generic verification is not counted as passing. See research.md for retained packets.

## Pipeline timing

**Do not run the full pipeline yet.** Finish required source/preparation decisions and obtain
attributable approvals for affirmative contexts, or retain their existing holds. The last saved
preflight reports 9,887 incomplete assessments (overlapping causes; not a new candidate result).
After decisions and corrections are stable, inspect current fingerprints and run the operator's
pipeline-only Clean → Enrich → Score command from main. Do not use release_full.sh to rebuild.
A diagnostic rebuild can preserve holds, but cannot establish release readiness. Publication
requires rebuilt invariant checks, consumer validation and separate release authorization.

Final CI correction: optional legacy outcome categories are omitted for 19 records whose exact
study endpoints do not fit a truthful coarse category. Detailed findings and sources remain;
no category or benefit claim is invented. Existing empty-reference-hold and source-vocabulary
assertions remain unchanged. The named Advanced Hair Complex hold remains, with no invented
component dose or d-biotin preparation. Cached and direct match results sanitize private context
at the same implementation boundary. Earlier provisional four-case clearance is superseded.

The clinical CSV explicitly separates source-content inspection, full-text verification,
exact applicability review, attributable clinician approval and downstream verification, with
owner/regression/closure columns. Bounded dependency replay does not imply corpus or scientific
closure. Unfinished full-text/applicability work remains visible for every record.

Final engineering qualification: candidate690e05ed passes [whole-fast CI40058400911](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/40058400911):
23,724 passed /192 declared skips, all skip guards pass. Local546passed/24declared skips;
736named owner/consumer checks; corrected285-label stable comparisons. These establish bounded
implementation verification. Scientific approval, whole-corpus integrity and actual app rendering
remain open as listed above. Workspace receipts: `.claude/state/completion-batch/`.
