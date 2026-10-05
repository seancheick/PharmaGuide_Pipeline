# Evidence → Dose responsibility transfer

Status: all-route inventory complete; approved probiotic transfer Q47 and Q48/Q49/Q51/Q52/Q53 source corrections integrated on main through `0a24804f`. D26 preparation/source binding correction is measured at `fe3d39a0` and integrated/pushed at `c8f53b46`, with final fast and fresh review passed. Generic/omega transfer and D24 Dose policy remain open. No catalog release. Historical inventory and experiment figures below apply only to their named baseline, not the current candidate.

Inventory baseline: pipeline `880b17a7`; focused owner/role suite 103 passed, 7 skipped,
1 strict xfail. The frozen 1,261-label audit sample is
`~/pg_quality/closure_20261001/deadcode_6917_1261.jsonl`.

## Invariant and owners

An amount-based adequacy or exposure judgment may leave Evidence only when the
same judgment is already made by an existing Dose owner or is added to that
owner in the same change. Clinical trial amounts remain registry source facts.
Identity, preparation, intervention, population, purpose and outcome
applicability remain Evidence judgments.

Owner: `scripts/scoring_input_contract.py::get_evidence_subject_rows` for the
subject set; `scripts/scoring_v4/exposure.py::row_exposure`, enrichment
`rda_ul_data.adequacy_results`, and the existing route Dose modules for amount
assessment. Will NOT create a second subject provider or post-route Dose engine.

## Original amount inventory at `880b17a7` — historical

The table preserves the initial findings. The probiotic row is closed by Q47 and the approved certainty/applicability/replication model; it is not a pending 12/20 ceiling decision. Generic and omega transfers remain open.

| Route / decision | Baseline Evidence owner | Baseline Dose coverage | Original transfer classification |
|---|---|---|---|
| Generic record minimum (`min_clinical_dose`) and undisclosed amount | `clinical_applicability.py::assess_clinical_applicability`; `evidence_resolver.py::resolve_evidence_for_row`; `generic_evidence.py::score_evidence` | The registry has 16 dose-bearing records: 11 top-level studied-dose records plus 5 applicability-policy dose records. Existing Dose covers KSM-66, white kidney bean, amla, MSM/OptiMSM, BCAA and official nutrient adequacy. It does not yet own equivalent benchmarks for nine named groups below. | Add a typed, audit-visible studied-dose assessment to the existing Dose result before deleting the Evidence veto. Numerical treatment of a missing benchmark remains D24 policy. Shared removal cannot land while any record lacks an owner. |
| Generic primary floor amount gate | `generic_evidence.py::_primary_mass_floor` | Route Dose owns amount adequacy; shared role classifier owns prominence | Replace its private mass-primary selection with `classify_ingredient_roles`; Evidence floor eligibility may use research/role facts but not label amount. Dose retains the exposure judgment. |
| Literature `studied_dose_exposure` gate | `evidence_resolver.py::resolve_evidence_for_row` | Partial; only routes/reference families with an existing benchmark | Same as generic record minimum. Do not discard the studied exposure from the source record. |
| Probiotic trial-dose applicability, up to 8 Evidence points | `probiotic_evidence.py::score_evidence` via native context `dose_applicability_credit` | `probiotic_dose.py::score_dose` owns disclosed CFU and adequacy, but most current adequacy tiers are industry-potency rather than trial-dose judgments | Remove dose from Evidence only with an explicit Evidence magnitude decision. Preserve trial-dose comparison in Dose metadata; do not silently convert the 12-point clinical subscale to 20. |
| Omega Evidence selected/graduated by daily EPA+DHA or DHA | `evidence_resolver.py::resolve_omega_evidence_standard` | `omega_dose.py::score_dose` already owns the same explicit EPA+DHA exposure and directed-serving interval | Remove amount thresholds from Evidence. A purpose-only record-selection rule and its magnitudes require approval; do not award 20 merely because exposure leaves Evidence. |

The uncovered generic groups are lactoferrin; Carnipure/L-carnitine; ALCAR;
the zinc-lozenge 80–207 mg intervention; L-arginine; D-mannose; D-aspartic
acid; Tesnor; and Sytrinol. Generic Dose's current no-reference disclosure
credit is not an adequacy judgment and does not satisfy the transfer invariant.

Amount comparisons in `clinical_applicability`, `evidence_resolver`, and
`generic_evidence` are shared gates. Do not introduce a record allowlist or a
route-specific exception: globally removing them before those nine groups have
an existing Dose benchmark would create an assessment gap.

## Observed baseline

In the frozen 1,261-label sample, the route distribution is small but exposes
the coupling:

- Omega: 5 products; Evidence/Dose pairs are 0/0, 0/4.3, 13.9/17.5,
  0/4.5 and 0/7.3.
- Probiotic: 8 products; reviewed clinical strength can coexist with low Dose
  (for example Evidence 5.4 with Dose 3.1), and one product receives Evidence
  9.0 with Dose 18.2.
- Generic: 1,003 products; the most common combinations include Evidence 0
  with Dose 9.5 (329), 14.5 (246), and 11.4 (113). This is not by itself proof
  of a dose-gate defect because completed negative/no-evidence reviews also
  score zero; candidate replay must classify drivers per product.

## Required implementation tests

All tests pass through `build_scored_artifact` or the route's production scorer.

1. The same reviewed evidence record produces the same Evidence score at a
   disclosed studied dose, a lower dose, and an undisclosed member dose.
2. The three labels retain distinct Dose assessments and reasons.
3. A blend total never becomes a member dose; an exact studied formula can use
   only its own declared total.
4. Preparation, intervention and population mismatches still deny Evidence.
5. Probiotic Evidence does not contain `dose_applicability`; Dose retains the
   reviewed trial comparison and ordinary CFU assessment.
6. Omega Evidence record selection is unchanged by EPA+DHA amount; omega Dose
   remains amount-sensitive and rejects carrier-oil mass.
7. Every removed config key and explanation has no production consumer.

Real seams for the generic transfer include 305203 KSM-66, 182940 MSM,
293877/307547 ALCAR, 309486 CogniPhos, 54775 Sytrinol, and 1179/2219 Ravage
blend ownership. Probiotic canaries include 250851, 299239, 307727, 326762 and
327965. Omega canaries include raw labels 224615, 206295, 35718 and 77225 plus
enriched labels 327776, 288740, 273630, 239592, 184654, 261863 and 267461.

## Decisions required before score-changing implementation

1. **Probiotic decision CLOSED (Q47):** approved certainty 0–10, applicability 0–6 and independent same-condition replication 0/2/4 are integrated. CFU/trial-amount comparison stays in Dose. No automatic 12→20 rescale or category ceiling remains. Preserve the historical experiments below.
2. **Omega Evidence purpose mapping:** approve which existing reviewed record
   applies to an ordinary omega product, an explicit triglyceride-purpose
   product, and a prenatal DHA product, independent of amount. Existing point
   values may be compared, but their amount-triggered use is not approved as a
   purpose-only policy.
3. **Generic missing benchmark:** D24 must decide whether an otherwise complete
   product retains an ordinary numeric total. Until then, the transfer can
   preserve the assessment as `unassessable`; it cannot treat missing knowledge
   as zero dose.

No implementation agent may decide these magnitudes implicitly.

## Execution boundary from this packet

Immediately landable work is regression and replay scaffolding plus relocation
of a diagnostic only where the existing Dose result receives the same
comparison. Probiotic ownership and magnitudes are now closed by Q47. Generic shared amount gates and omega amount-triggered policy remain blocked until equivalent Dose coverage and the named decisions close. Phase2 primary-selection corrections may proceed through the existing shared role owner while retaining uncovered amount safeguards; they do not authorize deleting those safeguards. A partial removal would violate the transfer
invariant even if its focused tests passed.


## Measured packet closeout

`MEASUREMENT.md` is the frozen all-route comparison produced from 1,259 raw
omega/probiotic labels and 11 real generic canaries. Report SHA-256 before
tracking: `2a13f67cc5797e337c47b69664aaa949f31fc30707f185887254d2041b595b03`.
All experimental scorer/config edits were restored; none are part of this branch.

The packet proves that removing the amount gates without extending Dose loses an
assessment. It also shows that both illustrative omega mappings and the
probiotic 12-to-20 rescale create broad numerical policy changes. This is the original experimental receipt, not today's approval state. The later approved probiotic model is integrated (Q47). Remaining transfers require omega purpose mapping/magnitudes and the generic clinical-anchor mapping,
including reviewed-null trial amounts and brand/generic precedence.


## Phase2 cleaner function correction — October1

Owner: `scripts/enhanced_normalizer.py::EnhancedDSLDNormalizer._process_single_ingredient_enhanced` and `EnhancedDSLDNormalizer._process_ingredients_sequential`, using existing `other_ingredients_exact_lookup` for declared function aliases. Matrix source_section/cleaner_row_role and raw1179 trace establish ownership. Expanded identity lookup remains; no scorer bypass, new owner, registry, parser, field or borrowed member dose.

Sourceb39328b9; baseline7262d192. Full verified capture hashes:

- baseline: head `7262d192c041314e9f3533d68f9a30e4e5a002ba`, manifest `048ffd9669499ab9f94625f7ee1b2a237a163c9310e945a6dadadc488516be67`, output `c2a80028eaf37f51b51e29d0f5a9c715e45f5d4dca70b5bff7a3fb73dc70a68a`, 6 rows, source unchanged `true`.
- candidate: head `b39328b98c7cf83fe617c032b66fc4b6bfc67532`, manifest `048ffd9669499ab9f94625f7ee1b2a237a163c9310e945a6dadadc488516be67`, output `60c23ac620761a485375138ff2668ed74f94c552176829f6683c4f235560ce7c`, 6 rows, source unchanged `true`.
- extended_candidate: head `b39328b98c7cf83fe617c032b66fc4b6bfc67532`, manifest `cbe041440eb1eb565edf2564298e106adfc35175f413d1aab26782447a1e8286`, output `a20cea182bc18ecb6eeff4dc7dc54232c6452a2631c22a53b5b11e2560c5ea72`, 1259 rows, source unchanged `true`.

Targeted outcomes: Ravage1179 raw Formulation8.2846→8.4307, public11.0→11.2, total33.5→33.7; restored cinnamon raises the existing IQM assessment count21→22. GoldenMilk243271 gains cinnamon Evidence-owner metadata6→7 without score movement.2219,221108,49630,66953 complete payloads are unchanged. All six preserve Safety, route, status, Evidence and Dose scores. Extended1259 output is identical to approved productionSHAa20cea182bc18ecb6eeff4dc7dc54232c6452a2631c22a53b5b11e2560c5ea72.

Verification: failing regression5failed27passed; focused1427passed; normalizer covering143files3153passed12artifactskips; final `scripts/test.sh fast`17906passed167skippedzero xfails,543.63seconds. Fresh reviewer independently verified source, capture/input/output hashes, every targeted movement and extended equality. No clinical policy/data edited. Existing dual-use amount overrides and other Phase2 prominence/serving defects are separate open work; this checkpoint does not validate release.


## Phase2 shared EAA purpose correction — October 1

Owner: `scripts/scoring_input_contract.py::classify_ingredient_roles` — existing role/title-alias owner, matrix and raw `66953` production-boundary tests. Consumers `sports_helpers::primary_sports_identity`, `sports_subtype`, `sports_formulation::_is_protein_context` and `sports_dose::_best_primary_score` consume that purpose. Will NOT create another classifier, scorer, Dose engine, registry, public field or numerical policy.

Source `3ee91eae` fixes Q39(b). The label declares a 1,600 mg verified nine-EAA mixture and a separate 100 mg whey line. Named EAA/BCAA purpose no longer becomes protein purpose merely because whey exists. Co-named protein and genuine protein products remain protected; protein/stimulant subtype coexistence is explicitly tested. Dose still compares existing eligible anchors using unchanged bands. Blend totals remain formula totals, never member doses.

| Product `66953` | Before | After | Classification |
|---|---:|---:|---|
| Dose | 6.4 | 4.7 | Actual owner becomes `eaa` / `eaa_under_5_g`; existing partial-dose and completeness rules |
| Evidence | 7.2 | 0 | Incidental whey stops owning Evidence; EAA/member subjects retained |
| Formulation | 15.2 | 12 | Protein adapter no longer applies; existing generic rubric |
| Transparency | 3.3 | 3.3 | Unchanged |
| Verification | 8 | 8 | Unchanged |
| Safety/Hygiene | 9 | 9 | Unchanged |
| Total | 49.1 | 37.0 | Explained quality-tier change: Needs improvement → Poor |

Status remains `scored`, module remains `sports`, and safety judgments are unchanged. `clinical_review_not_covered` remains explicit: missing EAA research is a Phase3 task, not a completed negative review. This fix does not finish calibration or authorize release.

Clean source `3ee91eae9285b1a0fda492de2d0acdc6edae9fc6`, baseline `b39328b9`, full Clean→Enrich→Score captures:

- Six-label manifest SHA `048ffd9669499ab9f94625f7ee1b2a237a163c9310e945a6dadadc488516be67`; candidate SHA `eb126dbff734db2d1665eac3a6621629eda0dd22e86b77d18d5117274058f205`. Controls `1179`, `2219`, `243271`, `221108`, `49630` retain identical complete payloads.
- Extended 1,259-label manifest SHA `cbe041440eb1eb565edf2564298e106adfc35175f413d1aab26782447a1e8286`; candidate SHA `a20cea182bc18ecb6eeff4dc7dc54232c6452a2631c22a53b5b11e2560c5ea72`. All 1,259 complete payloads remain identical to baseline. Both captures report unchanged source and matching frozen input hashes.
- RED regressions cover original purpose, abbreviation, genuine protein/stimulant Formulation and actual Dose driver. Final focused suite: 74 passed; prior 62 consumer files: 2,150 passed, two artifact skips; final eight Dose consumer files: 117 passed.
- Fresh independent review accepted source and measured causality after catching and fixing both the Formulation subtype regression and Dose's separate best-credit protein path. Full fast checkpoint passed at source `3ee91eae`: **17,915 passed, 167 skipped, zero expected failures** (551.27 seconds). Q39(b) is closed for source/sample validation; source pushed to main with Sean's approval. Fresh review accepted source, causality and controls; no catalog release.

Receipts: integration worktree `.claude/state/trace_protein/final_receipt.json`, `final_candidate.jsonl`, `final_extended_candidate.jsonl`, focused logs and `final_fast.log`. Source push and catalog release are separate states.

## Phase2 generic Evidence prominence ownership — October 1 (Claude lane, pending Codex audit)

Owner: `scripts/scoring_input_contract.py::classify_ingredient_roles`, read through `scripts/evidence_resolver.py::evidence_owner_canonicals` / `evidence_prominent_row_keys` (one selection, two views). Generic Evidence's primary floor, ingredient recovery and collagen recovery now take *which rows are the product's purpose* from that owner; the authority floor was already scoped to its identities. Will NOT create another classifier, subject list, scorer, Dose engine, registry, public field or config key.

Transfer invariant: four amount comparisons in `generic_evidence` stay unchanged as retained exposure stand-ins, because no Dose owner judges those amounts on every route (only `generic_dose.py` reads DRI adequacy; 199 of 210 records carry no studied minimum): the floor's and recovery's half-heaviest mass, collagen recovery's half-heaviest mass (its 2,500 mg minimum is read from the heaviest "collagen" row, not the peptide row), and the authority floor's heaviest-owner rule. Decision packet D26; measured counterfactual: removing all four raises 793 of 2,781 targeted labels (median +4.4) and 22 of 2,964 raw-coverage labels. Clinical-dose (`min_clinical_dose`) gates are unchanged.

Boundary applied: a blend total is never a member's dose. Floors and recoveries that read a multi-member blend heading's total (or a total lent to a member) as an undisclosed member's amount are removed; a heading that the input contract resolves to its own identity, or whose own text names a verified branded record (Relora, UC-II), keeps its floor.

Branch `claude/generic-prominence-ownership`. Frozen raw replays of `9d65403f` against `e8687b39` first showed 67 movers. The full fast checkpoint then found that the approved probiotic model's inputs had changed (receipt defect 19); final source `68cae99a` keeps them unchanged: 66 distinct products move, all down, Evidence only; 0 of 1,259 controls move. Final full fast: 17,954 passed, 168 skipped, 0 failed. Receipt with every defect, regression, hash and mover: `scripts/audits/prominence_ownership_20261001/README.md`. Claude validation complete; Codex audit/integration pending; no catalog release.


## D26 preparation/source binding — October 1 continuation

Owner: `scripts/scoring_v4/modules/generic_evidence.py::_recover_contract_evidence_matches`,
`_stamp_recovery_source_ref` and `_converted_product_dose` — evidence: production
`resolved_clinical_matches` consumers, source-ref converter, failing production-artifact
regressions and raw `269490` trace. Private `_recovery_source_ref` factors the existing
stamp's whitespace validation; it creates no persisted field or policy.
Will NOT create: another scorer, preparation parser, prominence owner, Dose engine,
clinical registry, public field/status or numerical configuration.

- [x] Reproduce: 2 g peptides beside 3 g non-peptide collagen borrowed the sibling's
  amount for the existing 2,500 mg study minimum. Initial regressions: four failures.
- [x] Bind the recovered study to its actual peptide preparation through existing
  match provenance fields. Keep the four D26 safeguards and all magnitudes unchanged.
- [x] Contain ambiguous unreferenced/shared-name recovery. Blank references use the
  same validity rule as stamping; equal-dose ties prefer valid lineage. Review
  regressions reproduced two failures for missing refs and two for blank refs.
- [x] Preserve duplicate declarations of the same exactly named strict peptide
  preparation. Raw `269490` declares protein from that preparation (6 g) and the
  preparation itself (6.6 g); both retain reviewed Evidence linkage. Dose conversion
  takes the largest applicable amount, never their sum. Different preparations and
  lent blend mass remain excluded. The intermediate replay's one readiness regression
  was reproduced, fixed, and eliminated before acceptance.
- [x] Measure clean committed source: baseline `0a24804f`, candidate `fe3d39a0`;
  275 frozen collagen-containing labels and 10 distinct controls through Clean →
  Enrich → Score. **All 285 captures identical**, including scores, pillars, routes,
  statuses, readiness and confidence. This is bounded source validation, not a corpus
  or exported-verdict audit. Additional ignored FDA inputs in the primary baseline
  remain preserved; final release provenance must account for their input inventory.
- [x] Related owner sweep: **794 passed,14 skipped**; skips require enriched/catalog
  artifacts absent from this isolated lane. Ten focused defect/edge regressions pass.
- [x] Final fast checkpoint: **18,018 passed,168 skipped,zero failures/xfails** (exit0,749.09s). Fresh reviewer verified all285 frozen hashes and byte-identical captures and accepted bounded integration. Source integrated/pushed at `c8f53b46`; main/origin verified equal and clean.

Edited production-boundary probes (not real product score claims): a referenced
2 g peptide + 3 g other-collagen example changes total81.3→66.0, internal Evidence
14→0.25, with subclinical flag and no floor. A 3 g peptide control stays81.3;
ambiguous missing lineage loses unsupported recovery77.3→61.7. The residual0.25
is the unchanged depth component, not study efficacy credit. No thresholds or other
pillars are tuned. Probe and raw receipts: `/Users/seancheick/pg_quality/d26_peptide_20261001/`.

### Remaining critical path (not completed by this correction)

1. Research the nine uncovered benchmark groups listed in the original inventory;
   verify preparation-specific intervention and source amounts before reuse. Extend
   existing Dose owners/results, not a post-route override. Missing knowledge must
   remain unassessable rather than zero dose.
2. Produce the D24 one/two/three/four-purpose-ingredient decision packet, including
   wrong-preparation benchmarks, missing amounts and incidental ingredients. Decide
   denominators, publication behavior and exact numerical treatment with Sean.
3. Produce the purpose-based omega Evidence packet, preserving applicable literature
   and explicit EPA/DHA Dose ownership. Existing amount-triggered marks cannot simply
   become full Evidence credit. Approved purpose/magnitude mapping is still absent.
4. Transfer generic/resolver amount judgments only alongside equivalent existing
   Dose assessments; retire the four stand-ins only with coverage or an explicitly
   approved replacement. Relative mass is not a clinical benchmark.
5. Then calibrate with the required per-judgment numerical-owner table and inspect
   Q3's35 quality-threshold crossings plus every subsequent safer verdict change.
6. After the last integrated change, run one fresh Clean corpus without publishing,
   build the candidate/manifest, and run sequential release/full gates. Sean approves
   that exact candidate before runtime publication.

Q53 source attribution is fixed; its bounded nine-label research queue is still
clinical coverage work, not a reason to revive the invalid species credits.


## October 1 CFU consolidation and independent quality/safety

The existing CFU source owner now preserves declared totals, avoids subtree/member double counting, and binds warranty to the selected count's own statement. Accepted source3ec556cb gives33 score movements across1,259 frozen labels, with717 omega controls byte-identical and no Evidence/Safety/Verification/route/status/purpose changes. Final separation source4f894a43 changes only four config-provenance paths in that cohort;46 actual production artifact probes preserve numerical results and typed safety. No quality improvement is a safety improvement.

Owner: normalizer source-total preservation → enrichment count/warranty result → existing probiotic Dose; `quality_score::assemble_quality_score` for quality and `scored_artifact::_product_safety_status` for safety, consumed by the release gate and Flutter. Evidence: durable frozen source and public-artifact receipts in `/Users/seancheick/pg_quality/cfu_guarantee_20261001/`. Will NOT create: another count parser, scoring engine, persisted status, clinical registry or app calculation.

Final source gates/integration pending. The three raw label conflicts242637/242654/327966 and broader D26/D24/omega/clinical/calibration decisions remain open. None is hidden by this ownership correction.

Final export followup `50a2fb7d`: existing `build_decision_highlights` no longer selects caution copy from legacy SAFE/POOR/CAUTION. It reads typed safety and quality-assessment readiness independently; additive/danger copy is retained. Two reproduced failures plus missing/unknown-safety and retained-danger controls cover this class. Export-owner sweep:2,766 passed,72 generated-artifact skips. Independent review accepted the narrow fix. The interrupted broad rerun (8,894 passed,131 skipped) is not a final acceptance receipt; the final broad gate follows this last production change.

Final portable pipeline checkpoint at clean `91987d74`: **18,079 passed,168 skipped,zero failures/xfails**,751.29s,exit0. Fresh source review accepted;46 product export controls retain all four highlight buckets and numerical/safety facts. App broad gate and integration/push remain pending. Durable final receipt: `final_portable_fast.log` and `highlights_replay_receipt.json` under `/Users/seancheick/pg_quality/cfu_guarantee_20261001/`.


### Final integrated source receipt — October 1

Q54 and Q55 are **implemented / measured / independently reviewed / integrated and pushed**, not runtime-published. Pipeline source91987d74:18,079 passed168 skippedzero failures/xfails751.29s; integrated/pushed main0f9ca406 plus this documentation receipt. App merged source63eeabff preserves concurrentmainf8c08d80; analysis zero issues and3,742 tests passed1:56, focusedstack12passed. Canonical builder corrected only the derived verdict-vocabulary manifest hash; no golden images changed. Independent review accepts both. Git worktrees/contained branches cleaned; ignored handoffs and exact logs/replays preserved outside them. The old quality-completion UI attachment belongs to another chat but has no live Git worktree/branch.

Remaining: Q53 nine clinical determinations; D26 missing equivalent Dose benchmarks/retained stand-ins; D24/omega unapproved numerical decisions; raw242637/242654/327966; calibration (quality movements and typed safety independently); final Clean corpus/manifest/approval/runtime publication. No release closure is claimed.


## October 2 user-run audit — source accepted; release validation pending

Sean's Clean/Enrich/Score run used `fa8c50bc` and completed 38 datasets /
15,421 unique scored artifacts. All 114 owned stage manifests/hashes match.
The strict canary guard stopped at 7 failures; the run did not publish or
rebuild distribution artifacts. All 46 prior CFU/Transparency controls match
actual run scores, pillars, quality tiers and typed safety, including all five
Transparency repairs.

The production corrections preserve existing policy: INGR_OMEGA3 cannot
credit plant ALA; rejected names/aliases cannot revive it; all valid marine
siblings retain their identities. Applicability consumes the shared subject
provider's unique identity at the exact raw reference, including populated raw
canonical values in a different namespace. Source-only scopes, raw amount and
forms are preserved, and ambiguous subject identities do not override. Q40
projection preserves only its cleaner-owned linked plant part.

The intermediate 27- and 30-mover captures are **superseded/rejected**: the
former wrongly lost mixed marine credit, and the latter wrongly dropped six
valid marine records because applicability and scoring used different
canonical namespaces. They are diagnostic history, not calibration inputs.
Use only the final `candidate_verified.jsonl` and its source-unchanged receipt
for acceptance. Final source `b7eeb178` is measured/reviewed/integrated and
pushed on main through `54a374cb`:1496 raw labels, 24 explained movements
(13 Formulation, 11 Evidence),1472 totals unchanged, zero other-pillar/route/
purpose/scoring-status changes; 46 controls/33 canaries match. Final fast:
18,101 passed, 168 skipped, zero failures or xfails in 976.12s. No runtime
catalog publication occurred. ALA clinical review remains open where the
marine match was rejected; rejection is not a completed negative assessment.

Owner: existing `clinical_applicability::_rows` and
`assess_clinical_applicability`, `get_evidence_subject_rows`,
`generic_evidence::_matched_active_canonical`, existing curated INGR_OMEGA3,
cleaner plantPart projection and canonical canary freezer. Evidence: raw
18141/204571/70588/304676/179650/315698, live marine source 31567003, strict
13-claim citation verification, 188 focused checks and independent review.
Will NOT create: another scorer, subject list, prominence provider, registry,
count parser, public field/status or numerical magnitude.

D26 transfer remains open: no amount gate was deleted in this correction.
The nine benchmark groups, D24 denominator/publication policy, omega purpose
magnitudes, Q53 research queue, remaining serving cases and calibration stay
on the master plan. Durable receipts: `/Users/seancheick/pg_quality/post_pipeline_20261002/`.


## October 2 whole remaining Dose decision packet

This current baseline packet supersedes serial preparation tasks; implementation remains gated by explicit numerical/clinical decisions. The ALCAR parent-reference defect it identifies is fixed in the combined candidate: current500mg reference is excluded for ALCAR, without adding a new range. Candidate deltas are in the existing execution register. Other displayed numbers below are baseline753aa5cf probes, not post-fix candidate scores.

# Complete remaining Dose / omega decision packet — October 2, 2026

Baseline and all current probes: `753aa5cf3a9062695c362133cff753975cb305da`. Read-only; no source/config/registry edits, no new owner, no corpus run, no release. This packet prepares the whole remaining Phase 1/4 batch; it does not approve the numerical policy or close transfer/calibration/release.

## Owner Check

Owner: `scoring_input_contract::get_evidence_subject_rows`, `classify_ingredient_roles`, `epa_dha_amounts_per_serving`; `scoring_v4/exposure::row_exposure`; `SupplementEnricherV3::_collect_rda_ul_data` → `RDAULCalculator::_find_nutrient` / `_form_scoped_reference` → existing `rda_ul_data.adequacy_results`; existing route `score_dose` modules. Evidence gates: `clinical_applicability::assess_clinical_applicability`, `evidence_resolver::resolve_evidence_for_row` / `resolve_omega_evidence_standard`, `generic_evidence::score_evidence`. Public normalization/status: `quality_score::_pillar_dose` / `assemble_quality_score`, `scored_artifact::build_scored_artifact`; publication: `build_final_db::validate_export_contract` (see current export validation below). Evidence: current source searches, matrix concepts dose_class/public_quality_score/verdict_contract, glossary material active/assessment readiness/adequacy exposure, current probes and file hashes in the JSON. Will NOT create: second Dose engine, benchmark registry, parser, public status/field, role owner or clinical policy.

## Current measurements and limits

[Current measurements JSON](/Users/seancheick/pg_quality/clinical_completion_batch_20261002/dose_current_measurements.json) contains 86 synthetic production-boundary probes, 16 fresh real-label Clean → Enrich → Score results, full inputs, per-ingredient adequacy/dose assessments, module details, six pillars, total/tier/status/safety/readiness and source fingerprints. The synthetic matrix measures numerical/publication contracts; it is not evidence that a marketed formula or clinical benefit exists. Registry records copied into JSON are current source facts, not a new primary-source review. No historical receipt is reused as current candidate validation. Historical replay statistics below retain their exact source/baseline label.

All source fingerprints were rechecked after measurement; True. HEAD after real probes: `753aa5cf3a9062695c362133cff753975cb305da`. No pytest rung is needed for a read-only packet; safe probes ran in the selected Python 3.13 runtime, with no broad test/corpus job.

## Nine generic benchmark groups — current coverage and missing judgment

| Group / existing record | Existing clinical source amount | Current Dose owner / actual gap |
|---|---|---|
| `INGR_LACTOFERRIN` (positive_strong) | 200 mg/day | Generic disclosed-dose fallback; no lactoferrin trial comparison. A probiotic route containing lactoferrin also needs this comparison through its existing route result, not generic-only insertion. |
| `BRAND_CARNIPURE` (positive_weak) | 2000 mg/day | Same parent as generic L-carnitine. Parent legacy reference is not the 2 g tartrate recovery intervention. Branded/generic siblings must assess the same group once; precedence remains unapproved. |
| `INGR_L_CARNITINE` (mixed) | 1000 mg/day | Legacy parent reference already produces amount credit, but it is not the verified 1 g scoped clinical comparison. Existing clinical-anchor allowlist omits L-carnitine. |
| `INGR_ZINC_PICOLINATE` (positive_strong) | 80–207 mg/day | DRI zinc RDA/UL credit exists; no short-term zinc acetate/gluconate lozenge80–207mg clinical intervention comparison. Delivery, acute-cold purpose/population and UL appropriateness are distinct. |
| `INGR_ACETYL_L_CARNITINE` (mixed) | 1000 mg/day | Raw ALCAR rows use IQM parent l_carnitine and matched_form acetyl-l-carnitine (alcar); 500 mg earns public Dose 20 via parent pct_rda100%. This is not the separate ALCAR 1 g intervention. Form-reference binding needs explicit resolution, not claiming coverage. |
| `INGR_L_ARGININE` (mixed) | 1500 mg/day | Generic fallback; no free/base arginine1.5g comparison. Different arginine preparations remain excluded. |
| `INGR_D_MANNOSE` (null) | 2000 mg/day | Fallback; 2g source is a reviewed-null trial amount, not an established effective benchmark. Sean must decide whether/how a null intervention amount receives Dose adequacy credit. |
| `INGR_D_ASPARTIC_ACID` (null) | 3000 mg/day | Fallback; 3g source is reviewed-null and population-specific. No positive benchmark may be inferred from the studied amount. |
| `BRAND_TESNOR` (positive_weak) | 200 mg/day | Whole named preparation total is available in product_scoring_evidence, botanical adapter blend_total_only raw10/public9.5; botanical Dose does not compare its 200 mg intervention. Luteolin is not a substitute for Tesnor whole-formula exposure. |
| `BRAND_SYTRINOL` (mixed) | 300 mg/day | Whole named preparation150mg exists, botanical adapter blend_total_only raw10/public9.5; no 300 mg trial comparison. Whole-preparation total must not become citrus/member dose. |

Current generic Dose reads `quality_score.json::dose_magnitudes.generic`: raw cap 25, supplemental-window cap 22, no-reference individual 16/product-evidence 12. Public normalization uses `dose_subscale.archetype_reference`: generic single 22 → fallback 14.5/20; named botanical blend 21 → botanical_dose_blend_total_only10 produces 9.5/20; generic product-evidence fallback12 is a distinct path. `_band_credit` classifies DRI/approved clinical anchors/legacy references; current nine groups are not in `_clinical_anchor_reference_by_canonical`. A legacy amount reference is an amount judgment, but not automatically equivalent to the clinical gate being transferred.

Existing covered families remain owned by current adapters: botanical `score_botanical_dose` and `rda_therapeutic_dosing.json` (KSM-66, white kidney bean, amla), joint `score_joint_support_dose` and `category_magnitudes.joint_support.target_dose_mg` (MSM), sports `score_dose` / `group_bcaa` / `group_eaa` (complete sets only), collagen `score_collagen_dose` / subtype therapeutic ranges, multi/prenatal `score_dose` / `dose_magnitudes.multi_prenatal`, fiber `score_dose` / hard-coded gram/type bands. Generic-only clinical insertion cannot cover lactoferrin on probiotic or nutrient authority on sports/fiber.

## Fresh real-label consequences

| Label | Source-owned amount / identity | F / D / E / T / V / S | Total | Tier | Status |
|---|---|---|---:|---|---|
| 315654 Lactoferrin 250 mg | Bioferrin Lactoferrin: 250.0 mg | 8.0 / 14.5 / 15.6 / 15.0 / 8.0 / 10.0 | 71.1 | Good | scored |
| 33684 Carnitine 500 | Carnipure(TM): 500.0 mg | 20.0 / 20.0 / 0.0 / 15.0 / 8.0 / 10.0 | 73.0 | Good | scored |
| 293877 Acetyl-L-Carnitine 500 mg | Acetyl-L-Carnitine Hydrochloride: 500.0 mg | 20.0 / 20.0 / 0.0 / 15.0 / 10.0 / 10.0 | 75.0 | Good | scored |
| 307547 Acetyl L-Carnitine 500 mg | Acetyl-L-Carnitine: 500.0 mg | 18.0 / 20.0 / 0.0 / 15.0 / 5.5 / 10.0 | 68.5 | Needs improvement | scored |
| 332955 Zinc Lozenges Wild Berry Flavored | Vitamin C: 100.0 mg; Zinc: 23.0 mg; Echinacea purpurea: 20.0 mg | 17.3 / 8.2 / 11.1 / 15.0 / 10.0 / 7.0 | 68.6 | Needs improvement | scored |
| 318194 L-Arginine 500 mg | L-Arginine: 500.0 mg | 11.6 / 14.5 / 0.0 / 15.0 / 8.0 / 9.0 | 58.1 | Needs improvement | scored |
| 330006 D-Mannose 2000 mg Veg Capsules | D-Mannose: 2000.0 mg | 20.0 / 14.5 / 0.0 / 15.0 / 6.0 / 10.0 | 65.5 | Needs improvement | scored |
| 183352 D-Aspartic Acid | D-Aspartic Acid: 3.0 Gram(s) | 20.0 / 14.5 / 0.0 / 15.0 / 8.0 / 10.0 | 67.5 | Needs improvement | scored |
| 328726 Testosterone Elite | Luteolin: 275.0 mg | 0.0 / 9.5 / 10.4 / 6.0 / 10.0 / 10.0 | 45.9 | Poor | scored |
| 54775 Sytrinol | Sytrinol: 150.0 mg; Citrus sinensis L extract: 150.0 mg | 20.0 / 9.5 / 0.0 / 0.0 / 10.0 / 10.0 | 49.5 | Poor | scored |
| 224615 Ultimate Omega 2X Mini Soft Gels Strawberry | Eicosapentaenoic Acid: 586.0 mg; Docosahexaenoic Acid: 456.0 mg | 10.5 / 18.2 / 15.8 / 15.0 / 10.0 / 10.0 | 79.5 | Very good | scored |
| 206295 Baby DHA Drops Unflavored | Marinol Fish Oil: 588.0 mg; Docosahexaenoic Acid: 200.0 mg | 10.9 / 6.5 / 0.0 / 10.9 / 8.0 / 10.0 | 46.3 | Poor | scored |
| 35718 Dual Spectrum Omega-3 Krill & Fish Oil 1085 mg | Krill Oil: 500.0 mg; Eicosapentaenoic Acid: 40.0 mg; Docosahexaenoic Acid: 25.0 mg | 10.9 / 14.6 / 10.4 / 15.0 / 8.0 / 10.0 | 68.9 | Needs improvement | scored |
| 77225 Naturally Sourced Omega-3 Vegetarian DHA 200 mg | Docosahexaenoic Acid: 200.0 mg; life'sDHA Oil: 600.0 mg | 9.7 / 4.0 / 0.0 / 10.9 / 8.0 / 7.0 | 39.6 | Poor | scored |
| 305203 KSM-66 | KSM-66: 600.0 mg | 19.3 / 20.0 / 20.0 / 15.0 / 8.0 / 10.0 | 92.3 | Excellent | scored |
| 182940 Glucosamine/MSM | Glucosamine Sulfate: 500.0 mg; MSM: 500.0 mg; Ginger (Zingiber officinale) extract: 250.0 mg | 18.2 / 6.1 / 7.3 / 15.0 / 10.0 / 10.0 | 66.6 | Needs improvement | scored |

The ALCAR 500 mg/Dose 20 and Carnipure 500 mg/Dose 20 examples establish that current Dose can be numerically full while the distinct applicable clinical minimum still blocks Evidence. These are current observations, not proposals to fix them by raising Evidence. Zinc332955 directed use1–4lozenges gives benefit exposure23mg and maximum92mg; RDA/UL assessment exists, but neither amount establishes the short-term clinical intervention. Tesnor328726 has a400mg own-preparation exposure despite the individual scorable list containing luteolin275mg. Sytrinol54775 carries150mg named formula, with member amounts undisclosed.

## Four retained D26 stand-ins — all remain live

| Current production symbol | Amount judgment retained | Missing equivalent / transfer condition |
|---|---|---|
| `generic_evidence::_primary_mass_floor` | Own anchor amount ≥ `evidence_magnitudes.generic.primary_mass_fraction`0.5 × heaviest competing active | Every applicable purpose row must receive its own amount/reference assessment before removing this guard; preserve reviewed research and source/identity guards. |
| `generic_evidence::_recover_verified_primary_ingredient_matches` | Recovered owner amount ≥0.5×heaviest competing active | Existing shared role selection is already integrated; recovering an Evidence match still must not lose the retained exposure assessment. |
| `generic_evidence::_collagen_peptide_recovery_row` | Peptide preparation itself ≥0.5×heaviest active; linked dose supplied to recovered2500mg study | Existing source binding is corrected. Different collagen preparation/protein/borrowed heading must not donate amount; collagen route adapter alone does not prove all-route coverage. |
| `generic_evidence::_mass_dominant_essential_canonical` | Heaviest selected owner must be a DRI essential | Generic RDA Dose exists, but sports/fiber do not consume the same essential adequacy. Shared-purpose selection is not this amount assessment. |

Do not reinterpret these as approved long-term mass policy: 25%-of-heaviest purpose demotion was rejected under D24. The retained50% comparisons are temporary transfer safeguards, not purpose owners. Historical D26 deletion sensitivity (Q49 source, not753aa5cf):793/2781targeted and22/2964raw-coverage labels rose; median+4.4/+5.9;347+12tier crossings, none fell. OptionC record allowlists/route exceptions was rejected; all four cannot simply be deleted. No current all-corpus deletion sensitivity is claimed.

## Missing-benchmark matrix, one through four purpose ingredients

For eachN, the typed fixture starts withN declared purpose rows: Vitamin C90mg, then Magnesium100mg, Zinc8mg, Vitamin B120.0024mg as applicable. The last row becomes the tested missing-benchmark/wiring/preparation/missing-amount case. Incidental adds Lactoferrin1mg outside the title. Unbenchmarked last row is Lactoferrin500mg; preparation mismatch is Betaine HCl500mg carrying the TMG parent and its exact matched form. Known benchmark controls distinguish a wiring failure from absence of an applicable reference. All inputs and typed readiness are retained.

| N | Defect class | Assessable denominator (known bands/declared purposeN) | Raw Dose | F / D / E / T / V / S | Total | Tier / status |
|---:|---|---|---:|---|---:|---|
| 1 | unbenchmarked | 0/1; 1 source adequacy rows | 16.0 | 12.0 / 14.5 / 15.6 / 15.0 / 6.0 / 10.0 | 73.1 | Good / scored |
| 1 | wiring_miss | 0/1; 0 source adequacy rows | 16.0 | 12.0 / 14.5 / 11.1 / 15.0 / 6.0 / 10.0 | 68.6 | Needs improvement / scored |
| 1 | preparation_mismatch | 0/1; 1 source adequacy rows | 16.0 | 12.0 / 14.5 / 12.2 / 15.0 / 6.0 / 10.0 | 69.7 | Good / scored |
| 1 | missing_amount | 0/1; 0 source adequacy rows | None | None / None / None / None / None / None | None | None / not_scored |
| 1 | incidental | 1/1; 1 source adequacy rows | 22.0 | 12.0 / 20.0 / 11.1 / 15.0 / 6.0 / 10.0 | 74.1 | Good / scored |
| 2 | unbenchmarked | 1/2; 2 source adequacy rows | 16.0 | 12.0 / 14.5 / 15.6 / 15.0 / 6.0 / 10.0 | 73.1 | Good / scored |
| 2 | wiring_miss | 1/2; 1 source adequacy rows | 16.0 | 12.0 / 14.5 / 11.1 / 15.0 / 6.0 / 10.0 | 68.6 | Needs improvement / scored |
| 2 | preparation_mismatch | 1/2; 2 source adequacy rows | 16.0 | 12.0 / 14.5 / 12.2 / 15.0 / 6.0 / 10.0 | 69.7 | Good / scored |
| 2 | missing_amount | 1/2; 1 source adequacy rows | 22.0 | None / None / None / None / None / None | None | None / not_scored |
| 2 | incidental | 2/2; 2 source adequacy rows | 22.0 | 12.0 / 20.0 / 11.1 / 15.0 / 6.0 / 10.0 | 74.1 | Good / scored |
| 3 | unbenchmarked | 2/3; 3 source adequacy rows | 16.0 | 12.0 / 14.5 / 15.6 / 15.0 / 6.0 / 10.0 | 73.1 | Good / scored |
| 3 | wiring_miss | 2/3; 2 source adequacy rows | 22.0 | 12.0 / 20.0 / 11.1 / 15.0 / 6.0 / 10.0 | 74.1 | Good / scored |
| 3 | preparation_mismatch | 2/3; 3 source adequacy rows | 16.0 | 12.0 / 14.5 / 12.2 / 15.0 / 6.0 / 10.0 | 69.7 | Good / scored |
| 3 | missing_amount | 2/3; 2 source adequacy rows | 22.0 | None / None / None / None / None / None | None | None / not_scored |
| 3 | incidental | 3/3; 3 source adequacy rows | 20.75 | 12.0 / 18.9 / 11.1 / 15.0 / 6.0 / 10.0 | 73.0 | Good / scored |
| 4 | unbenchmarked | 3/4; 4 source adequacy rows | 16.0 | 12.0 / 14.5 / 15.6 / 15.0 / 6.0 / 10.0 | 73.1 | Good / scored |
| 4 | wiring_miss | 3/4; 3 source adequacy rows | 20.75 | 12.0 / 18.9 / 11.1 / 15.0 / 6.0 / 10.0 | 73.0 | Good / scored |
| 4 | preparation_mismatch | 3/4; 4 source adequacy rows | 16.0 | 12.0 / 14.5 / 12.2 / 15.0 / 6.0 / 10.0 | 69.7 | Good / scored |
| 4 | missing_amount | 3/4; 3 source adequacy rows | 20.75 | None / None / None / None / None / None | None | None / not_scored |
| 4 | incidental | 4/4; 4 source adequacy rows | 21.0625 | 12.0 / 19.1 / 11.1 / 15.0 / 6.0 / 10.0 | 73.2 | Good / scored |

Current denominator is the number of non-None `_band_credit` results, not all purpose rows. Missing benchmark rows are skipped; when no reference remains, disclosed individual fallback16 applies once regardless of1–4unbenchmarked purpose ingredients. When an unassessed row is mass-primary, `_mass_primary_without_reference` caps window credit at16; lighter unassessed purpose rows can be skipped without that cap. The wiring-miss3/4cases therefore retain near/full Dose even though a known row is absent from the input assessment. These injected misses are diagnostic controls, not evidence that the real producer currently drops these rows.

Typed missing amounts produce `not_scored`, null total/tier and null public pillars for allN. The direct route result remains available in JSON for diagnosis; null public pillars must not be presented as a numeric zero quality grade. Untyped legacy synthetic controls can remain scored with zero Dose; this is why readiness/provenance must be retained when measuring publication. Explicit unresolved VitaminA conversion control also returns `not_scored`; it is not an unbenchmarked ingredient.

`quality_score::assemble_quality_score` removes public number/tier/pillars for NOT_SCORED. `build_final_db.py` current integrity/readiness checks quarantine not_scored/incomplete products rather than inventing a live numeric score; confirmed banned/recalled products have a separate ship-with-warning contract. This packet probes scorer publication status and inspects export source; it does not build or publish a catalog.

Decisions prepared for Sean, not encoded: (1) applicable clinical benchmark eligibility, including null interventions and brand/generic precedence; (2) whether purpose-only assessment is an unweighted mean or another approved denominator, and whether supporting ingredients participate—70/30 remains unapproved; (3) whether missing applicable benchmark retains an ordinary numeric total/tier with explicit limitation or uses the existing not_scored publication gate; (4) explanations must distinguish missing knowledge, missing amount, preparation mismatch and wiring failure. Do not count missing knowledge as demonstrated0dose, and do not rescale known rows to a high grade silently. A new public meaning requires Sean.

Historical D24 A/B/C/R sensitivities in DOSE_PROPOSAL are evidence of consequences, not current measurements: zero missing knowledgeA mean−3.68/85crossings; omit/rescaleB−0.22/52; existing fixed fallbackC−0.09/63; primary0/supportskipR−1.13/61 on339scored labels. The proportional_dose draft was rejected: second post-route engine, unjustified mass demotion, unapproved70/30, literal invented benchmarks and excess caps.

## Excess: Dose appropriateness and Safety risk are separate judgments

Exposure owner uses minimum directed use for benefit and maximum for excess. Dose safety uses `dose_safety::evaluate_dose_safety` / `_classify` / `_resolve_pct_ul`, `quality_score.json::dose_safety_policy` (150%UL threshold,2perflag, cap3), and generic `_band_credit` (above100%UL →11raw; at/above150%→0). Public `quality_score::_dose_safety_penalty` separately mirrors capped B7 to Safety/Hygiene (`safety_hygiene_subscale.over_ul_max_penalty`3). Existing code therefore has two deductions/judgments; calibration must explicitly justify their distinct purposes, not call the same deduction new policy.

Current Zinc60mg/day and90mg/day synthetic probes use adult-neutral compatibility reference RDA11mg/UL40mg and150%/225%UL. Both give F12/D0/E11.1/T15/V6/S8, total52.1/Poor/scored. Appropriateness raw Dose 0 and B7flag2 coexist with Safety −2. The amount does not establish individual patient risk or supervised short-term cold treatment: exact preparation, intended adult/child/pregnancy population, duration, total dietary/other-product exposure and UL basis stay explicit. Source typed assessment records preserve population/age/sex/UL basis. General adult UL cannot be silently relabeled a studied short-course lozenge threshold; absence of an official UL cannot be silently treated as safe/full Dose. Sean’s later accepted preference permits considering both Dose appropriateness and Safety risk; the old Safety-only D24 wording is superseded. E1.75/E2.5caps and numerical deduplication remain unapproved.

## Omega: current amount coupling and complete decision inputs

Current source `evidence_resolver::resolve_omega_evidence_standard` joins INGR_OMEGA3 purpose records to `quality_score.json::evidence_magnitudes.omega.purpose_standards`: ordinary10.4only at≥376mg EPA+DHA/day; non-prenatal1000–2000mg linearly graduates10.4→20 and≥2000mg selects triglyceride_strong regardless of explicit outcome purpose; prenatal DHA≥200mg gets intake-authority11.1, otherwise0. `omega_evidence::score_evidence` uses this result only; generic adjunct studies remain metadata. `omega_dose::score_dose` separately reads explicit EPA/DHA and `omega_rubric.json::dose.epa_dha_bands`, existing cap/pregnancy bands; certification does not create EPA/DHA/formulation credit.

| Ordinary explicit EPA+DHA/day | Public Dose | Evidence | Total | Tier/status |
|---:|---:|---:|---:|---|
| 100 | 2.5 | 0.0 | 25.3 | Poor / scored |
| 500 | 10.0 | 10.4 | 43.2 | Poor / scored |
| 1000 | 16.0 | 10.4 | 49.2 | Poor / scored |
| 1500 | 18.0 | 15.2 | 56.0 | Needs improvement / scored |
| 2000 | 20.0 | 20.0 | 62.8 | Needs improvement / scored |
| 4500 | 20.0 | 20.0 | 62.8 | Needs improvement / scored |

All positive-amount ordinary fixtures otherwise retain F0/T6.8/V6/S10. Changing title to explicit Triglyceride Support does not change the amount-driven Evidence/Dose sequence today; Transparency changes to10.9, so totals differ by4.1. Prenatal fixtures at500mgcombined/250mgDHA get Dose 20/Evidence11.1/total53.9/Poor; at100mgcombined/50mgDHA get Dose10/Evidence0/total32.8/Poor. Purpose-independent Evidence should not be implemented by removing these thresholds and awarding20.

Omega decisions ready as one batch: ordinary marine EPA+DHA applicable evidence magnitude; explicit triglyceride-outcome purpose and population (not molecular triglyceride form) and magnitude; prenatal intake authority distinct from conditional pregnancy outcome evidence; DHA-only non-prenatal, child/baby, mixed-purpose, specialized delivery/unit and carrier-only identities each need an applicable determination/hold. Dose must retain the existing exposure interval and rejected-carrier boundary while Evidence uses supported identity/preparation/population/purpose/outcome. Existing shared role/purpose result must retain efficacy purpose alongside route prominence; no separate parser.

Rejected/unapproved historical alternatives: O1ordinary10.4/explicitTG20/prenatal11.1 was not approved blanket mapping; identity-gated717label replay301moved,−9.6to+10.4,56Poor→Needs improvement; Q45individually reviewed56versions/36names:38plausible ordinary crossings and18holds (4identity,7child/baby,4DHA-only,1specialized,2mixed-purpose). O2ordinary9.35/TG14/prenatal10was illustrative, not recommendation:655/717moved,−10.7to+9.3. Initial carrier-only58false awards were rejected. Historic tier counts use shipped half-up whole-score tier rules; legacyPOOR→SAFE is a quality alias, not safer risk. Neither sensitivity is current candidate approval.

## Whole-batch next implementation gate

Prepared now: nine-group current owner coverage; four current stand-ins;1–4 purpose cases for all five classes; current per-ingredient denominator/pillars/total/tier/status/publication consequences; excess Dose/Safety separation; omega mapping alternatives and18hold classes. Await explicit policy decisions, then extend existing producer/route consumers in the same change before removing shared Evidence amount gates. Preserve subject/purpose/preparation/source/population guards. Assert amount-independent Evidence but distinct Dose at low/studied/undisclosed exposure, complete BCAA/EAA once, no blended member borrowing, same-condition evidence independence, controls/safety unchanged where policy does not change them. Finished batch gets focused fail-first tests, bounded frozen raw measurements, independent review, exact-candidateCI/local as applicable, then approved corpus/release sequence. No phase marked implementation/measurement/integration/release complete by this preparation.

## Source index

* Current `docs/plans/PHARMAGUIDE_MASTER_COMPLETION_PLAN.md` Phases1/4/5, accepted excess refinement lines374–378; `scripts/audits/pending_items_20260926/LEDGER.md` D24,D26,Q45 and current continuation.
* `scripts/contracts/source_of_truth_matrix.json`; `scripts/GLOSSARY.md`; current production symbols/config/data named above, SHA256 in JSON.
* `scripts/audits/evidence_dose_transfer_20260930/README.md`, `MEASUREMENT.md`, `OMEGA_O1_CROSSING_REVIEW.md` (historical alternatives / transfer invariant).
* `scripts/audits/numerical_ownership_20260930/README.md` (draft numerical inventory, superseded probiotic and prominence details explicitly excluded).
* `scripts/audits/rr_correctness_20260928/DOSE_PROPOSAL.md` (accepted/rejected D24 rules; historical sensitivities, not specification).
* Current `backed_clinical_studies.json` exact ten records across nine groups plus source references/applicability in JSON; `rda_optimal_uls.json`, `rda_therapeutic_dosing.json`, `omega_rubric.json`. Their stored citations are not freshly content-verified in this Dose packet; primary clinical determinations remain separately required.
* Raw label paths and SHA256 per 16 current probes in JSON. Probe scripts/logs are local diagnostic support only, no production policy.

## October 2 approved transfer implementation

The decision gate above is complete for the pre-Clean candidate. Approved
production source `374fb4b6`:

- accepts only exact, positive and applicable preparation Dose benchmarks;
- uses one equal vote per shared-owner declared purpose and preserves existing
  collagen, botanical, sleep, joint and immune per-purpose Dose assessments;
- retains the disclosed-but-unbenchmarked fallback and existing required-amount
  `not_scored` gate;
- removes the four D26 Evidence amount/prominence safeguards after equivalent
  Dose ownership exists;
- makes omega Evidence amount-independent at 10.4 / 20 / 11.1 for the three
  approved applicable classes while holding the five excluded classes;
- retains separate Dose appropriateness and Safety threshold-risk judgments;
- removes the duplicate fixed fiber detox/laxative penalties.

The eight-class omega table, one-to-four-purpose denominator demonstrations,
all 71 frozen score movers and the recovered 35-product Q3 receipt are in
[`q53_d26_calibration_20261002`](../q53_d26_calibration_20261002/README.md).
Independent review found no remaining code finding. The transfer is implemented,
measured and reviewed; it is not full-corpus or release validated. The next gate
is Sean's fresh Clean/Enrich/Score run, followed by release and app rendering
verification against those rebuilt artifacts.


## October 5 remaining exposure decision packet — approval pending

The October 2 accepted transfer remains valid. This packet covers only the four
live remainder records reproduced in `clinical_completion_20261004/amount_transfer_remaining_review.md`;
Amla stays reference-only and its dormant amount scope is not released. No gate
has been removed and no new clinical or numerical benchmark is installed.

Owner: `clinical_applicability::assess_clinical_applicability` for existing
reviewed source/preparation/delivery scope; `scoring_v4.exposure::row_exposure`
for directed exposure; `dose_assessment::positive_clinical_benchmark` and
existing per-purpose Dose modules for positive adequacy. Evidence: current
four records, existing 15 boundary probes and reviewed October 2 policy. Will
NOT create a registry, post-route scorer, public field/status or null-as-positive
benchmark. `DoseAssessment` is the UL contract; do not repurpose UL statuses as
clinical efficacy grades.

| Existing record | Exposure judgment to preserve in Dose | Proposed numerical treatment requiring Sean's decision |
|---|---|---|
| INGR_ZINC_PICOLINATE (cold acetate/gluconate lozenges) | Below 80, 80–207, above 207 mg/day or undisclosed exposure; exact delivery/preparation and clinical population/purpose remain Evidence constraints. | Keep nutrient adequacy and existing UL/Safety judgments independently. A short-course trial envelope cannot turn 80–207 mg into routine-safe/full nutrient Dose. Decide whether equivalent exposure reporting alone closes this clinical transfer, with present Dose points unchanged. |
| INGR_WHITE_KIDNEY_BEAN | Below 1000 mg/day or disclosed studied 1000–3000 mg/day envelope; do not infer inhibitory activity from mass or blend totals. | Decide whether exact reviewed positive preparation may use the existing positive-benchmark ratio scale against the lowest studied amount, or whether range correspondence is diagnostic while current unbenchmarked disclosure credit remains. Lowest studied exposure must not be described as a demonstrated efficacy threshold. |
| INGR_D_MANNOSE | Compare label-directed amount with 2000 mg/day null-trial exposure; below/unknown exposure is not the exposure tested in that null result. | No positive benchmark, benefit credit or new dose reward. Decide whether to move exposure correspondence to Dose while retaining current amount-independent null Evidence and existing Dose fallback. |
| INGR_D_ASPARTIC_ACID | Compare label-directed amount with 3000 mg/day minimum and descriptive 3–6 g/day null-trial range; no borrowed blend mass. | Same null-context treatment: no positive adequacy anchor or reward. Preserve trained-young-adult-male population/endpoint restrictions in Evidence and report exposure correspondence through Dose. |

The concrete boundary packet already contains half-minimum/exact/double-minimum
probes for all four records and the dormant reference record, plus zinc 208 mg.
At current source, positive Dose benchmark is None for every case. Removing all
amount gates now would lose the exposure judgment. Equivalent Dose ownership
and chosen treatment must land together, tested through the public scorer with
low/studied/undisclosed exposures and preparation/delivery controls.

Recommendation for a bounded decision: allow Dose to report the existing
clinical exposure comparison for all four; retain null records as context only
and preserve zinc nutrient/UL/Safety scoring. Separately choose WKB numerical
range correspondence versus the existing unbenchmarked fallback. This is a
proposal, not recorded approval or an implemented transfer. The existing source
corrections can be validated independently while these gates remain intact.

## October 5 team review brief — four remaining exposure decisions

Historical October5 team-brief status (superseded by the approved implementation below): proposal, not approved policy. Code inspected on integrated main c67600da; the blend audit and isolated test repairs are integrated. Existing four Evidence amount gates remain. Sean will run the pipeline after remaining source work is ready. This packet does not close the separately classified clinical/preparation exceptions.

Owner: existing clinical applicability, directed exposure, positive clinical benchmark, nutrient adequacy and per-purpose Dose owners listed above; this existing README owns the transfer decision packet. Evidence: current source and records, 15 retained boundary probes, live Europe PMC content checks for eight source PMIDs on October5. Will NOT create: another scorer/registry, a null-study positive benchmark, assumed blend-member dose, potency conversion, new safety threshold or a second execution register.

### What happened and why work remains

The October2 transfer closed its bounded packet, not every amount constraint in the clinical registry. The subsequent census and owner audit found four records whose clinical match still depends on daily quantity. Generic Evidence, its sports/digestive consumers, readiness and confidence still use the shared collector with amount assessment enabled. Dose can normalize an amount but currently has no equivalent assessment of these four clinical exposure scopes. Their applicability.minimum_daily_dose fields are not automatically positive_clinical_benchmark inputs.

For matching forms and purpose, the retained probes show the distinction:40mg zinc,500mg WKB,1000mg D-mannose and1500mg DAA fail the current amount assessment and pass preparation-only assessment. Zinc208mg fails the maximum. These are synthetic boundary probes, not product totals or new clinical recommendations.

Evidence is intended to judge human support for the correct preparation/purpose; Dose judges the label-directed amount; Safety independently judges risk. Removing the Evidence checks before Dose retains the same exposure facts would lose information. Converting every studied amount into rewarded adequacy would introduce unsupported policy, especially for null results.

Correction to the earlier choice wording: keeping current points means keeping current **Dose** scoring. Evidence points, readiness or explanations can still change after amount rejection moves out of Evidence. Exact product effects require raw replay; zero total movement is not promised.

### Record-specific judgments

| Record | Current amount rule | What the team needs to distinguish |
|---|---|---|
| Zinc acetate/gluconate cold lozenges (legacy ID INGR_ZINC_PICOLINATE) |80–207mg/day envelope, matching lozenge form and acute adult cold context |Trial comparability is distinct from routine nutrient adequacy and safe intake. The reviewed meta-analysis includes80–92 and192–207mg/day groups; a continuous envelope is not proof that every intermediate amount was tested. Do not extend this record to swallowed picolinate capsules or prevention. |
| White Kidney Bean extract |At least1000mg/day; current curated narrative reports1000–3000mg/day trials |Weak positive weight-management research is distinct from a validated dose-response curve. Milligrams do not establish equivalent alpha-amylase inhibitory activity. The live Phaseolean abstract tests a specific standardized preparation at1500/3000mg/day; the1000mg registry minimum needs trial-table/preparation justification before becoming an operational scoring anchor. |
| D-mannose |At least2000mg/day |The598-woman trial tested2g/day and did not demonstrate recurrent-UTI prevention in its community population. The null finding cannot become benefit credit or a rewarded effective-dose target. The current minimum also accepts amounts above2g; that is not proof that those amounts were studied. |
| D-aspartic acid |At least3000mg/day; narrative describes3–6g/day |Small trials in trained/athletic men provide null findings for the reviewed outcomes.3g and6g are reported trial regimens, not proof of efficacy or a continuous dose-response curve. Retain population/outcome restrictions and no positive adequacy reward; amounts above6g are not automatically studied exposures. |

Primary sources rechecked by content: [zinc meta-analysis](https://pubmed.ncbi.nlm.nih.gov/28515951/); [2026 WKB meta-analysis](https://pubmed.ncbi.nlm.nih.gov/42066439/), [Phaseolean trial](https://pubmed.ncbi.nlm.nih.gov/39170208/); [D-mannose randomized trial](https://pubmed.ncbi.nlm.nih.gov/38587819/), [2025 synthesis](https://pubmed.ncbi.nlm.nih.gov/41004704/); [DAA resistance-training trial](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0182630), [climber trial](https://pubmed.ncbi.nlm.nih.gov/29893592/), [boxer trial](https://pubmed.ncbi.nlm.nih.gov/38201906/). [NIH Zinc guidance](https://ods.od.nih.gov/factsheets/Zinc-HealthProfessional/) gives an adult UL40mg/day, distinct from medically supervised treatment. Amounts in this packet describe records/studies, not intake advice. Eight API receipts are preserved at clinical_source_continuation_20261005/team_decision/.

### Recommended policy for team consideration

Move source-bound clinical exposure correspondence to the existing Dose owner for all four. Keep preparation, delivery, population and outcome support restrictions in Evidence. Retain existing Dose points, Zinc nutrient/UL/Safety judgments and zero affirmative Evidence credit for the two null records. Show exposure correspondence as below, within the reviewed envelope, above or unknown where those descriptions are supported; distinguish reported exact regimens from a descriptive envelope. A within-range result must not imply benefit, safety, or suitability for a person. Retain existing clinical holds, including reference-only Amla.

White Kidney Bean numerical scoring remains a separate choice. OptionA keeps existing disclosure/unbenchmarked Dose scoring and reports studied-exposure correspondence. OptionB uses the existing positive benchmark calculation only for an explicitly justified comparable preparation and operational anchor. OptionB needs the exact source/preparation/potency condition, anchor, below/above-range scoring and explanation. Do not silently make every WKB extract eligible because of a name match, or describe the lowest reported dose as a proven efficacy threshold. I recommendA until the team supplies that justification.

The team must also confirm whether a low/unknown-dose but otherwise matching positive preparation retains its research grade in Evidence with Dose separately explaining exposure uncertainty. This can raise Evidence credit that the current amount gate withholds. If another treatment is preferred, specify its single numerical owner and consumer explanation; do not introduce hidden duplicate deductions.

### Implementation and acceptance after the decision

1. Verify each record's sources, exact preparation/delivery, outcomes, reported regimens and any proposed operational anchor. Update structured constraints and contradictory narrative together. Preserve null directions and reference holds.
2. Reuse row_exposure for actual label-directed daily exposure and the existing same-source linkage. Preserve dose ranges, unknown directions and unknown quantities. No blend-total borrowing, extract/potency equivalence or invented elemental mass.
3. Extend the existing Dose assessment seam to preserve clinical exposure comparison separately from positive adequacy. Do not repurpose UL statuses for clinical efficacy. Reuse existing output contracts where compatible; any new public meaning/field needs a named owner and approval.
4. Change the shared Evidence collector, readiness and confidence consistently for only the reviewed scope. Avoid a global assess_amount=False switch that changes unrelated formula/strain scopes. Preparation/purpose/route restrictions remain active.
5. Test below/exact/above/unknown exposure, both ends of directed-serving ranges, wrong form/population/outcome, matched versus unknown potency, null versus positive direction, separate Zinc safety and blend-member unknowns through the public scorer. Test2g versus>2g D-mannose and3/6/>6g DAA contextual wording explicitly.
6. Freeze affected raw labels and unaffected controls; compare full pillar/total, role, source, safety, status, readiness and explanation changes. Group ordinary movements by cause; investigate every unsupported credit, lost warning or unexplained delta.
7. Fresh independent review, one completed-batch whole-fast CI checkpoint and applicable local checks; integrate before declaring source ready. Then inspect stage fingerprints. Sean runs the necessary pipeline fromClean; catalog/app/release validation follows the new artifacts.

### Requested team reply

Please provide:
- Approval or revision of exposure correspondence in Dose for all four, while Evidence retains preparation/purpose/population support judgments.
- Treatment of positive research credit when label amount is low or unknown; desired Evidence and Dose explanations.
- Zinc: confirmation that cold-trial comparability does not replace nutrient/UL/Safety scoring or imply routine-safe/full Dose at80–207mg/day.
- WKB: optionA orB. ForB, cite the preparation/potency condition, operational anchor, numerical treatment below/above the range and acceptable consumer wording.
- D-mannose/DAA: confirmation of zero new affirmative credit/adequacy reward; specify exact-regimen versus envelope correspondence and out-of-range wording.
- Any additional study/source that changes a recorded preparation, population, outcome or regimen, with a directly supporting link.

The58 classified pending ingredient/preparation groups are a separate research/source queue. Examples include whole powder versus extract, oral essential oil versus tea/aromatherapy, generic mushroom mixtures versus studied formulas, and mass-only pancreatin versus studied enzyme activity. Each needs its own verified determination or honest hold. A four-record policy decision does not close them or authorize blanket no-human-evidence conclusions.


## October 5 approved descriptive transfers — current execution

Sean approved the four transfers in attachment78db306d. The approval creates no new positive Dose benchmark: descriptive research correspondence is separate from efficacy, adequacy and Safety. Implementation is on `codex/clinical-regimens` from main a8d7eeae; integration, final measurement/review and CI are pending.

Owner: `scripts/dose_assessment.py::clinical_research_exposure_assessments` — evidence: existing Dose owner, `row_exposure`, clinical source linkage/applicability and declared-purpose seam. Enrichment produces `rda_ul_data.clinical_exposure_assessments` after clinical matching; the universal scorer and existing pillar-facts adapter project it into the existing Flutter fact renderer. Will NOT create: another registry/scorer, positive benchmark, new Safety threshold, assumed member amount, potency conversion or personal-population classifier.

- Zinc: amount-independent acetate/gluconate lozenge research; descriptive clusters80–92 and192–207mg/day. Intermediate amounts are between regimens, not a continuously studied range. Nutrient Dose and UL/Safety remain independent.
- WKB OptionA: retired1000mg Evidence floor, no numerical adequacy reference. The verified meta-analysis abstract does not establish a generic daily exposure envelope; per-meal amounts must not become daily limits. Phaseolean1500/3000mg/day for45days is reported as preparation-specific context. Generic extract mass cannot verify Phaseolean identity/potency; a comparable generic reference remains unestablished. No product-to-Phaseolean alias bridge is installed.
- D-mannose: amount-independent reviewed null; exact2000mg/day trial context is powder/sixmonths/community adult women with recurrent UTI. Correspondence earns no positive adequacy reward; higher exposure does not escape the null record.
- DAA: amount-independent reviewed no-benefit context in trained men; discrete3000/6000mg/day. Added content-verified PMID25844073 (24men,14days):3g null,6g reduced total/free testosterone. The12week6g training trial remains null; no training-harm threshold is invented. Largest-single-trial denominator now24.

Population remains the source's explicitly carried study context. Product tags cannot establish a patient's diagnosis, training status or cohort membership; the existing population-applicability review explains this boundary. Tests preserve source-scoped context rather than inventing patient membership or extending the claim to a different population.

Fail-first19failures/1pass reproduced amount gates and the absent producer. Current focused boundary regressions39pass, including full enrichment, hidden member amount, serving ranges, wrong zinc preparation/delivery, wrong declared purpose, null-no-positive-reward and Zinc UL coexistence. Strict changed-record citation gate22/22pass. Data batch check requires exactly the four record IDs. Frozen raw replay104labels contains all26D-mannose,28DAA,24WKB labels plus zinc and unrelated controls; final committed-candidate receipt follows. No full corpus run or release; Sean will run the pipeline himself. Remaining58 classified clinical/preparation groups are not closed by these transfers.
