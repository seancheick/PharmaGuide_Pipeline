# A9: can unfinished data earn a score that reads as complete?

Base: `origin/main` at `0bd492188`. Catalog read: `scripts/final_db_output`, db_version
`2026.11.02.191010`, 15,447 products. Live probes: `probe.py` in this folder, run against stored
enriched output with the production scorer. Line numbers are from this branch and are supplementary;
the symbol is the pointer.

## Answer

No state gives full credit by itself. No neutral, provisional or fail-open value reaches a pillar
maximum except Safety/Hygiene, where 10/10 means the catalog screen found nothing, and every
withheld state ships no number.

The defect was different. **A product whose assessment is unfinished kept the fields that say it is
finished.** 6,294 scored products are `partial`, and each one kept its number. Some also said
"96/100", "exceptional", "safety, purity and evidence", "top 0%" and "Strong" Evidence. Those fields
are fixed here. The app's score breakdown card still shows the total and tier on a partial product;
that is an app fix, listed below.

## Catalog census (before this branch)

| `quality_score_status` | `quality_assessment_status` | `product_safety_status` | Products |
|---|---|---|---|
| scored | complete | no_known_catalog_concern | 7,950 |
| scored | complete | caution | 885 |
| scored | partial | no_known_catalog_concern | 5,828 |
| scored | partial | caution | 466 |
| not_scored | partial | no_known_catalog_concern | 196 |
| not_scored | partial | caution | 53 |
| suppressed_safety | complete | blocked | 69 |

Not-scored and suppressed products have no score, tier, pillars or percentile in core. Complete
products with a release blocker: 0. Complete products with `not_yet_reviewed` Evidence: 0.

## Every path, and whether it can give full credit

Driver values are printed by `probe.py <enriched_root> <id>`.

| Path or state | Code | Real product | Driver | Full credit? |
|---|---|---|---|---|
| Hard safety stop | `score_supplements_v4.py::_score_v4_core`, `safety.short_circuits_scoring` (316) | 277705 Hemp CBD VESIsorb | `blocked_by_safety_gate`, score None, `blocked` | No, no number |
| Safety quarantine | same, `safety.quarantine_required` (326) | 0 in the catalog; code only | sets CAUTION, score continues | Not a credit path |
| Completeness gate | same, `is_live_eligible` (343) | 45+156 in the census; see low coverage below | `blocked_by_completeness_gate`, score None | No, no number |
| Intentional non-scoreable | same (351) | 329726 Maltodextrin Powder | `intentional_non_scoreable_product`, score None | No, no number |
| Safety resolver failed | same, `safety_resolvers_failed` (364) | 0 in the catalog; `test_safety_assessment_incomplete_withholds.py` breaks the resolver on 12012 | `safety_assessment_incomplete`, score None | No, no number |
| Held label | `scored_artifact.py::_held_assessment_label` (252) | 328831 Ginseng Plus | `release_assessment_incomplete`, score None, blocker `dose_benchmark_identity_unresolved` | No, no number |
| Capture gap | `scored_artifact.py::_product_safety_status` (83) | 329726 | `capture_unavailable:activeIngredients` | **F4**: read `no_known_catalog_concern`; fixed |
| Release assessment open, Evidence credit earned | `assessment_readiness.py::evaluate_release_assessment` (1437) | 328830 Basic Prenatal | 95.5, Evidence 20/20, blocker `evidence_assessment_incomplete` | **F1, F2, F3, F5**: read finished; fixed. Score unchanged |
| Evidence not yet reviewed | `quality_score.py::evidence_display_state` | 182704 ADR Formula, 245963 AdipoLean II | 11.1 and 0.0, `not_yet_reviewed` | No |
| Evidence applicability | same | 13567 Flax Seed Oil, 184730 Probiotic 123 | 0.0, `applicability_unestablished` | No, 0 points |
| Neutral Dose | `quality_score.py::_pillar_dose` | 298076 Memoractiv, 339541 Vitality | Dose neutral, highest 11.4/20 | No, see decision 2 |
| Neutral Formulation | `quality_score.py::_pillar_formulation` | census max | 12/20 | No |
| Transparency base | `_pillar_from_dim` | census | 9/15 | No |
| Verification fail-open | `quality_score.py` `neutral_baseline`, config 6.0 | census: 0 products report it | 6/15 | No |
| Safety/Hygiene screen | `quality_score.py::_pillar_safety_hygiene` | 6,767 at the max | `catalog_screen` neutral 10/10 | Yes by design: a clean screen. Never reads as `safe`; see F1 |
| Blend anchor as the only scoring row | `scoring_input_contract.py` | 284197 Boswellia Phytosome, 217182 ABC Dophilus | Dose highest 11.4/20 | See below |
| Completeness score cap, verdict ceiling | `gate_completeness.py` (`score_cap`, `verdict_ceiling`) | never set | always None | Dormant |

## Defects fixed here

| # | Defect | Owner | Example before | After |
|---|---|---|---|---|
| F1 | Share copy on a partial product published the number and tier, and every finished one claimed a safety analysis | `build_final_db.py::generate_share_metadata` | 328830: "Thorne Basic Prenatal - 96/100 ⭐", "Analyzed by PharmaGuide for safety, purity, and evidence" | No number or tier on partial; finished copy says it is not a safety rating |
| F2 | Partial products took percentile ranks and pushed finished products down | `build_final_db.py` percentile SQL | 328830: percentile 100, top 0.0 | Only complete products rank |
| F3 | Decision highlights praised partial products | `build_final_db.py::build_decision_highlights` | "Clinically-backed ingredients" | Says the assessment is not finished |
| F4 | A panel the screen never read reported a clean screen, and a scored label with one reported a finished assessment | `scored_artifact.py::_product_safety_status`, `assemble_scored_artifact` | 329726: `no_known_catalog_concern` | `not_assessed`, `partial`; hard verdicts and CAUTION unaffected |
| F5 | Evidence said `assessed` while a release blocker said its review was open | `assessment_readiness.py::evidence_review_open`, `quality_score.py::mark_evidence_review_open` | 328830: 20/20, 1 of 30 material actives `not_yet_evaluated` | `not_yet_reviewed`; points and receipt stay |

An independent review of the first version found these, each reproduced and fixed:

| # | Defect | Owner | Example before | After |
|---|---|---|---|---|
| F6 | `safety_assessment_status` read `complete` on an unresolved identity behind an Evidence blocker | `assessment_readiness.safety_assessment_status` | 252496 (141 omega labels), 307560 | `incomplete` |
| F7 | The same field ignored a printed nutrient amount the upper-limit check never read | same, `unread_printed_nutrient_amounts` | 16730 (9 sports labels) | `incomplete`; the quality tier is not held |
| F8 | The same field ignored a safety match still awaiting review | same, `needs_review` | 12031 (67 scored, 9 not scored) | `incomplete`; `caution` stays |
| F9 | An open review kept the "0 records" fact only a finished review may report | `quality_score.mark_evidence_review_open` | 216405 (24 by the review's count) | Fact removed |
| F10 | 15/15 probiotics said amounts were hidden while every strain's count is printed | `quality_score._pillar_from_dim`, `pillar_explanations.every_strain_count_printed` | 217182 (26 labels) | Names the missing weights; score unchanged |

A banned name on a label nothing else maps to still blocks: DMAA, 1,3-Dimethylamylamine, Ephedra and
Sibutramine beside an unknown row all return `blocked`, score None
(`test_a_banned_name_blocks_a_label_nothing_else_on_it_could_map`).

## Open by design or for Sean

Why the scored partial products are partial (6,294, `census_before.json` query over stored artifacts):
`evidence_assessment_incomplete` 5,884, `probiotic_evidence_assessment_incomplete` 239,
`omega_evidence_assessment_incomplete` 141 (an identity hold, not a pending review),
`probiotic_contributing_context_incomplete` 25, no blocker 5 (252560, 253359, 329658, 232945, 232952:
`not_yet_reviewed` Evidence with complete readiness). The 272 products with every ingredient assessed
yet still blocked are the 301 scored partial products with complete Evidence readiness, less 24
contributing-context and 5 no-blocker: 202 `evidence_assessment_incomplete` from the module aggregate
and 70 `probiotic_evidence_assessment_incomplete` from the native strain check.

Decisions for Sean:

1. Partial products keep their number and tier in core. Nothing here nulls them; the app hides or labels them.
2. Neutral Dose lets a finished label with hidden amounts reach about 81.8 (339541). Accepted policy, unchanged.
3. Nested-row blend anchors as the only scoring row (284197, 217182): owned by #335.
4. Evidence points stay visible while the review is open (328830, 20/20).
5. 2,581 partial products keep `applicability_unestablished` Evidence (182957, 184730) though a blocker says the review is open. Moving them contradicts copy that existing tests pin as policy, so it stays until decided. Quality status already reads partial.
6. Low-coverage not-scored products keep `no_known_catalog_concern` from a name-only screen; `safety_assessment_status` reads `incomplete` on all of them.
7. 10 of the 11 held labels with evidence-only blockers record "no safety clearance" in their `review_scope`, so they read `incomplete`. Changing that text changes the field.

For Dr Pham (pending delta review, none invented here): `DEP_ANTACIDS_IRON`, `DEP_DIURETICS_THIAMINE`,
`DEP_SSRIS_SODIUM`, `DEP_LEVOTHYROXINE_CALCIUM`, `DEP_LEVOTHYROXINE_IRON`, `DEP_ANTICOAGULANTS_VITAMINK`,
`DEP_ORLISTAT_VITAMINA`, `DEP_CHOLESTYRAMINE_VITAMINA`, `DEP_CHOLESTYRAMINE_VITAMIND`,
`DEP_CHOLESTYRAMINE_VITAMINE`, `DEP_CHOLESTYRAMINE_VITAMINK`. The 20 approved records are traced from
source to the bundled app copy by `test_a9_reviewed_depletion_examples.py`. The ledgers say
`licensed_pharmacist_signoff: false`, and the approver is recorded as "PharmaGuide Clinical Team"; the app
golden calls pending warfarin "Clinician-pinned", which an app fix should relabel.

## Measured before and after

Full rescore of all 38 stored inputs at `eb47098a8` against clean main, 15,447 products. Scores,
tiers, score status, quality status and blockers: 0 moved. `product_safety_status`: 4 moved to
`not_assessed` (329726-329729). Evidence `display_state`: 1,368 moved from `assessed` to
`not_yet_reviewed`, with points unchanged. Scratch strict export: 15,447 products, 0 errors.
`shadow-diff` passed. The scoring audit reports 0 `SCORING_SAFETY_ASSESSMENT_STATUS_MISMATCH` and 81
`SCORING_STRICT_CONTRACT_FAILED`: 51 `disclosed_form_unmapped`, 29 `identity_conflict`, 1
`form_quality_unassessed`. The same 81 ids and reasons are in main's stored scored artifacts, so this
branch adds none and removes none. Rerun with
`compare_strict_contract.py <products_root>`, which reads stored output against `strict_contract_findings.json`.

Export against `scripts/final_db_output`: percentile rows 15,129 to 8,834, because only complete products
rank and cohorts under 5 get none. The probiotic wording fix (F10, `fe968096f`) came after this rescore:
display only, measured on 217182 at 73.9, Good, and on the 26 labels by their stored reason.

## `safety_assessment_status` by state, with a real product

| Quality status | Quality assessment | Catalog safety | Safety assessment | Products | Example |
|---|---|---|---|---|---|
| scored | complete | no_known_catalog_concern | complete | 7,941 | 240875 |
| scored | partial | no_known_catalog_concern | complete | 5,686 | 268686 |
| scored | complete | caution | complete | 863 | 1060 |
| scored | partial | caution | complete | 421 | 1640 |
| suppressed_safety | complete | blocked | complete | 50 | 220094 |
| not_scored | partial | no_known_catalog_concern | incomplete | 192 | 16765 |
| scored | partial | no_known_catalog_concern | incomplete | 142 | 212388 |
| not_scored | partial | caution | incomplete | 53 | 19598 |
| scored | partial | caution | incomplete | 45 | 1179 |
| scored | complete | caution | incomplete | 22 | 12031 |
| suppressed_safety | complete | blocked | incomplete | 19 | 252358 |
| scored | complete | no_known_catalog_concern | incomplete | 9 | 16730 |
| not_scored | partial | not_assessed | incomplete | 4 | 329726 |

The field is a fact, not a display rule: an incomplete assessment or a caution shows no all-clear
(Sean, 2026-11-03), and `incomplete` never overrides a block. Open for Sean: 2,581 partial products
keep `applicability_unestablished` Evidence (182957), and quality status reads partial on them.

## Completion census (Sean's rule, November 3)

Both arms scored the same frozen corpus, `~/pg_quality/a9_corpus_20261103` (15,447 products, checksums in
`MANIFEST.tsv`), at `a225a6823`. That head has #335 and #340, not #339 or the dose batch, so this is not the
final figure: after those land, replay only the labels they change and report the delta here. The "before"
arm is the same head with the completion change reversed. 0 errors in either arm.

| Partial before | Partial after | Partial to complete | Complete to partial |
|---|---|---|---|
| 6,343 | 5,315 | 1,028 | 0 |

**What moved: nothing that scores.** Score, tier, score status, pillars, catalog safety status,
`safety_assessment_status`, verdict and confidence: 0 moves. Evidence wording moved on 930 labels (`display_state`
`not_yet_reviewed` to `assessed` 902, to `applicability_unestablished` 28) and 39 labels changed
`evidence_result_state` with no change in points. No complete label carries "not finished" wording, and every
complete label with an unread row carries the note that those rows weren't individually reviewed.

**Why 1,028 complete** (`completion_moved_labels.csv`):

| Reason | Labels | Evidence points |
|---|---|---|
| Nutrient panel answered; add-in rows unread and earn nothing | 720 | all earned |
| Reviewed owner earned credit; every row finished | 54 | earned |
| Reviewed owner earned credit; supporting rows unread | 107 | earned |
| Finished review, no credit; every row finished | 36 | 0 |
| Finished review, no credit; supporting rows unread | 111 | 0 |

The 147 no-credit labels read Needs improvement (111) or Poor (36). By module: multi or prenatal 692, generic 184,
sports 119, B complex 28, fiber or digestive 5.

**Why 5,315 stay partial** (labels; a label can have several reasons, 249 are not scored):

| Reason | Labels |
|---|---|
| Research on file, applicability not decided | 2,733 |
| Primary research never read | 1,850 |
| Explicit hold: a held ingredient is the open owner | 683 |
| Identity mismatch, including the omega identity blocker | 280 |
| Probiotic strain review | 267 |
| Evidence pillar still reads as unreviewed, with no required row open | 242 |
| Not scored by the completeness gate | 201 |
| Dose or benchmark unresolved | 63 |
| Explicit hold: source-bound label holds (all 40 unchanged) | 40 |
| Capture gap | 9 |
| Not scoreable by intent | 8 |
| Multi route with no panel nutrient reached (213567, 232945, 232952, 36330) | 4 |

All release blockers on those labels: evidence 4,788, probiotic evidence 242, omega evidence 141, identity 114,
dose 63, probiotic context 25, dose benchmark identity 24, unread dose amount 5.

**Shared-cause plan** (`completion_held_shared_causes.csv`): the open required rows on those labels come to 509
ingredients and 623 ingredient-and-preparation pairs, by role claim-named 3,589 rows, major 1,561, adjunct 2,462.
3,973 labels need one shared decision, 851 need two or more, and 446 have no open required row (other blockers,
or the Evidence pillar still reading as unreviewed). Reuse each decision across labels with #340's review format.

| Open reason code | Labels | Ingredients | Decision needed |
|---|---|---|---|
| `unverified_generated_record_cannot_complete_evidence` | 1,702 | 280 | read the primary research |
| `clinical_sources_ineligible` | 1,249 | 42 | which sources qualify; carnitine leads this group and stays held |
| `literature_applicability_unestablished` | 986 | 67 | does the research apply to this preparation and use |
| `clinical_source_contexts_missing` | 509 | 24 | record each source's context |
| `botanical_therapeutic_reference_unverified_studies` | 431 | 16 | read the studies behind the reference |
| `invalid_applicability_contract` | 165 | 7 | repair the record |
| `probiotic_species_or_stub_applicability_unestablished` | 157 | 32 | strain-level review |
| `culinary_matrix_review_cannot_complete_extract` | 129 | 20 | preparation decision |
| `active_identity_requires_literature_search` | 70 | 17 | identity, then research |

Held ingredients with their open-owner label counts: carnitine 179, elderberry 135, betaine 103, grape and grape
seed 112, collagen 73, phytosterols 57, taurine 53. These stay open; no blanket completion and no per-label approval.

**Vitamin A and beta-carotene, a canonical shared cause.** The resolver keys on the printed name
(`rda_ul_reference_entry`, `is_essential_dietary_nutrient`), so one `beta_carotene` row resolves by authority when the label
prints "Vitamin A" and falls to the reference-only record when it prints "Beta-Carotene". 170 labels carry
the canonical: 79 printed "Vitamin A" resolve by authority, and 84 rows printed "Beta-Carotene" or "Mixed Carotenoids" don't. 44 labels
had that row open; 43 complete with this rule because it's an add-in on a panel that answered, and 1 stays for
another reason.

| Label | Printed | Outcome | Closed by this fix? |
|---|---|---|---|
| 328830 | "Vitamin A" parent (`vitamin_a`), nested "Beta-Carotene" | complete, 95.5, Evidence 20, Beta-Carotene row recorded unread | Yes, for status. The row split remains. |
| 232945 | "Vitamin A" row with canonical `beta_carotene`, 220 mcg | partial, 42.5, Evidence 0, panel reaches 0 of 6 | No. |

The fix doesn't close them alike. 69 multi labels print "Vitamin A" on a `beta_carotene` row and the panel doesn't
count it, so they read short of Evidence (233635: Vitamin A 900 mcg, panel 5 of 6, 16.7); 67 are complete and 2 partial. 232945 is
in that group and also has no vitamin C, D, folate, B12 or zinc row, so counting vitamin A alone wouldn't finish it. Owner:
`evidence_resolver` panel reading and `scoring_reference_resolver.rda_ul_reference_entry`. Counting it raises Evidence on those
69, so it is a mapping decision with a score measurement, not a #340 review alone. Nothing here changes resolver order.

**Blend members (Group D).** 124 labels with a member of a mass-major blend open stay held, 0 moved. Control:
221423 prints whey isolate in its protein blend. Whey resolves `reviewed_human_clinical_evidence_matched`, the match
recovered is the whey record, and the label completes at 64.0, Needs improvement, Evidence 15.6. 256990 is the other side:
chamomile and lemon balm are open in a heavy blend, so it stays partial though magnesium earned credit. Both are pinned in
`test_a_blend_member_completes_only_on_its_own_reviewed_decision`.

**#340 recheck on the combined logic.** All 200 labels on its complete list stay complete. Of its 1,098 held labels, 322 complete here: 263
multi or prenatal, 1 B complex, 58 owner-scoped. No complete label has a held ingredient as a required open row.

**Known limits, each measured.**

- **The title-role owner misses some subjects (8 labels).** `_named_in_title` doesn't read a genus, class or brand word, so these read
  complete while the ingredient the title names is unread: 251695, 293389, 326688 (Sambucus, elderberry, a held
  ingredient), 178674 (Fish), 221657, 223436 (Omega), 243141 (Mushroom), 25921 (Reparagen). Found by alias match and by reading the 79 labels
  whose unread row outweighs every required owner, so a brand word elsewhere could still hide. This breaks "an unread primary can't be complete". Fixing it at
  `_ROLE_TITLE_ALIASES_BY_CANONICAL` moved 24 of 690 replayed scores and 4 tiers, including Formulation on multis and Evidence 11.1 to 0
  on Sambucus labels, so it needs its own measured batch.
- **Supporting owners can still earn credit (31 labels).** 31 moved labels have an unread route owner outside the required set,
  almost all isoleucine and valine (27). Reviewing them could in principle move credit; by materiality they are supporting rows, Sean's stated case.
- **Hold-listed rows on moved labels (276 labels).** The row isn't the owner: 204 multi add-ins, 72 others. The ingredient stays
  open and recorded unread, and it earns nothing.
- **No printed amount on a required row (23 moved labels).** Blend members such as whey in a protein blend. The dose gate raises no blocker on them,
  and federal labeling lets a blend omit these amounts, so this isn't a missing necessary amount. 0 moved labels have a capture gap.

**Safety contract.** Quality and personal safety stay separate. `safety_assessment_status` moved on 0 labels. Partial
quality with safety checks finished: 4,893. Partial with them unfinished: 422 (334 no known catalog concern, 84 caution, 4 not assessed). Complete with them
unfinished: 64 (36 caution, 19 blocked, 9 no known catalog concern), 14 of them moved here. "No known concerns" depends only on known catalog
safety, no finding, and `safety_assessment_status == 'complete'`.
