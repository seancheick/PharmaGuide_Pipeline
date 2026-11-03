# Traces behind the review order

All counts come from the unpublished 2026.11.02 scored and enriched artifacts in the main checkout, re-resolved with code at `0bd492188`. Nothing here was published.

## Which rows actually block

The artifact labels 9,065 rows `no_reviewed_evidence_assessment`. Re-running the resolver gives the real reason for each row (11,318 rows across 6,289 Evidence-only products):

| Rows | Resolver reason | What it means |
|---|---|---|
| 3,475 | `unverified_generated_record_cannot_complete_evidence` | The record was never reviewed |
| 2,102 | `clinical_sources_ineligible` | A curated record is held on a source or clinician decision |
| 1,705 | `literature_applicability_unestablished` | Reviewed, but the review does not establish applicability |
| 1,098 | `probiotic_species_or_stub_applicability_unestablished` | Probiotic species or stub row |
| 789 | `botanical_therapeutic_reference_unverified_studies` | Botanical route with no reviewed studies |
| 748 | `clinical_source_contexts_missing` | Curated record has no approved contexts |
| 298 | `invalid_applicability_contract` | Scope present but not signed |
| 265 | `crude_vegetable_powder_cannot_inherit_purified_extract_trials` | Hard-coded broccoli rule |
| 246 | reviewed rows that resolve | Already finished |
| 211 | `culinary_matrix_review_cannot_complete_extract` | Culinary review on an extract row |
| 156 | `active_identity_requires_literature_search` | No record yet |
| 129 | `crude_seed_powder_cannot_inherit_purified_oil_trials` | Hard-coded pumpkin rule |

So about 2,600 rows are not waiting on research at all. They wait on a rule about what a finished review may close.

The probe disagreed with the artifact on 152 of 6,289 products: current code adds beetroot, red raspberry fruit, apple fruit and black tea leaf rows the artifact did not list. I did not trace why. The replay below re-derives everything from raw labels, so its measurements do not depend on this.

## Why `clinical_sources_ineligible` records fail

These records are held on purpose. None is a data error an agent can fix. Each one's October 28 ruling or hold needs a paper we cannot read, or a decision only a clinician can make. I checked OpenAlex and Europe PMC on 2026-11-03: six of the seven papers are closed. PMID 24287284 is hybrid access but returned 403, and I did not try to get around that.

| Record | Unlocks (rank) | What holds it |
|---|---|---|
| `INGR_L_CARNITINE` | 162 (1) | 32154768 and 32359762 unread (closed). 32958033 is finished as non-credit |
| `INGR_ELDERBERRY` | 124 (3) | 30670267 unread (closed). 33827515 is finished as non-credit |
| `PRECLIN_BETAINE_ANHYDROUS` | 82 (6) | Ruling asks for outcome-scoped lower-body strength from 39514262 (closed, not in the record). 30064450 and 37409757 are approved as non-credit |
| `INGR_PLANT_STEROLS` | 64 (8) | Ruling reopened capsule and tablet LDL. 24144075 is closed, 24287284 returned 403. 19109655 is a food-matrix non-credit |
| `INGR_TAURINE` | 63 (9) | No contexts at all. 32871172 and 41275513 are closed |
| `INGR_GRAPE_SEED_EXTRACT` | 58 (11) | 34798267 unread (closed). 33671310 is null on its primary outcome, approved as non-credit |
| `INGR_COLLAGEN_PEPTIDES` | part of collagen (2) | Ruling says complete as no-credit for skin. One field blocks it: signed context `collagen_skin_funding_40324552` has `included_study_pmids: "extraction_pending"` |

Also held: `INGR_OMEGA3` (omega nutrition path, in the Evidence calibration work), `INGR_GLYCINE`, `SAME` and `SPIRULINA` (record-level `scoring_eligible: false`, no contexts), `INGR_CINNAMON_EXTRACT` (Khan 2003 expression of concern), `PRECLIN_PQQ` (correction hold), and `INGR_AMLA` and `PRECLIN_AKG` (reference-only, contexts missing).

## Why fully assessed products stay blocked

The brief counted 272. With current code it is 298: fiber_digestive 105, generic 94, probiotic 93, sports 3, multi 3.

**Generic, sports and fiber (202 products).** The artifact marks module-scoped product-level rows `not_applicable` / `module_scoped_product_projection`, so every visible row looks assessed. `evaluate_release_assessment` then re-resolves those same rows with `resolve_product_evidence(owner_scoped=True, module=...)` and adds `evidence_assessment_incomplete`. The ledger and the release gate disagree about what counts. Split: evidence-completeness gap only 106, gap plus pending applicability 30, pending only 65, neither 1 (278416, which I did not resolve). Live probes: 278554 and 47339 both stop on a fiber row with `unverified_generated_record_cannot_complete_evidence`. The pending list is led by bromelain (contexts missing, 24), pancreatin 7, triphala 6, collagen 6, phytosterols 6, elderberry 5, sytrinol 4.

**Probiotic (93).** 69 have `probiotic_evidence_assessment_incomplete` (180210 and 60467: strain status `strain_context_not_applicable`, so no reviewed conclusion). 20 carry the contributing context `is2_adult_ibs_multicenter_31434935`, 4 carry `p299v_ibs_rome3_22912552`.

**Multi (3).** 204732, 241347 and 241349 are blocked in the artifact but complete on current code, because apple fruit is now `not_efficacy_relevant`. That is drift since the build, not an open question.

## Oddities for later

- The `fiber` canonical holds galactomannan and konjac glucomannan rows, and identical hydrolyzed collagen labels take two routes ("Collagen, Hydrolyzed" through the botanical path, "hydrolyzed Collagen" through the held backed record).
- `ginkgo`, `ginkgo_biloba`, `ginkgo_biloba_leaf` and `ginkgo_leaf_powder` are separate literature records for one botanical. The last two have different owners and purposes (Dose against Evidence), but the split is easy to trip over: adding `ginkgo` with the wrong status silently removed Dose points in this batch's first replay.
- `_metadata.verified_records_count` and `verified_studies_count` in `literature_evidence_records.json` already disagree with the file (809 against 783 authoritative records, 280 against 308 studies). The test comment says they record the last full verifier run, so this batch leaves them alone.
- PubMed turned up a turmeric liver-injury case series (32656820). The safety data already covers this signal: `RULE_IQM_TURMERIC_LIVER` and `RULE_INGREDIENT_CURCUMIN` in `ingredient_interaction_rules.json`, plus the `turmeric` CAERS entry. This batch changes none of them.
