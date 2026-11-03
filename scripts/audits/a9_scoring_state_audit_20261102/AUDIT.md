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

A banned name on a label nothing else maps to still blocks: DMAA, 1,3-Dimethylamylamine, Ephedra and
Sibutramine beside an unknown row all return `blocked`, score None
(`test_a_banned_name_blocks_a_label_nothing_else_on_it_could_map`).

## Open by design or for Sean

See the PR for the decision list and the measured before and after.
