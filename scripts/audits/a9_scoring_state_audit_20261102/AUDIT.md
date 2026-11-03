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
branch adds none and removes none.

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
